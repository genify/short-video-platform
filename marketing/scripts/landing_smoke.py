#!/usr/bin/env python3
"""落地页冒烟装置（纯标准库，零第三方依赖）。

用途：上线整合（PRO-24）的落地页可达性与链路冒烟。三种模式：

  spawn     在**独立实例 + 独立数据库**上跑完整冒烟：GET / · GET /s/<video_id>
            · GET /api/stats · POST /api/events · POST /api/lead · POST /api/withdraw
            并在末端复读 /api/stats 核对计数增量。
  live      对**已部署实例**跑真实 GET 冒烟（GET / · GET /s/<video_id> · GET /api/stats）。
            ⚠️ 会写入 2 条 page_view（1 招募 + 1 分享），污染正式分流统计库 —— 只在
            「部署后一次性验收」时使用，用后必须按 runbook 重建空库。
  readonly  对**已部署实例**只跑不写事件的检查：GET /api/health · GET /api/stats
            · HEAD / · HEAD /s/<video_id>，并在前后各读一次 /api/stats 证明计数未变。

纪律（重要）：
  1. 冒烟**不得**污染正式分流统计库。三次读数（样本门 300/500）要求分母只含真实访客；
     装置自检、冒烟、合成流量都必须用独立数据库。
  2. `--mode spawn` 使用临时数据库与随机空闲端口，运行后自动清理，不触碰任何既有库。
  3. `--mode live` 的污染是**已知且有据**的：脚本会打印污染前后计数与差值，供留痕与
     事后扣减判断；正式库重建步骤见 docs/09 上线整合执行手册 §3。

用法：
    python3 marketing/scripts/landing_smoke.py --mode spawn
    python3 marketing/scripts/landing_smoke.py --mode live     --base http://127.0.0.1:8088
    python3 marketing/scripts/landing_smoke.py --mode readonly  --base http://127.0.0.1:8088

退出码：0 = 全部检查通过；1 = 有检查失败（逐条打印 PASS/FAIL）。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # marketing/scripts -> marketing -> <ROOT>
APP_PATH = os.path.join(ROOT, "marketing", "landing", "app.py")
SMOKE_VIDEO_ID = "video-smoke-001"
SMOKE_CONTACT = "smoke-test@example.invalid"


# ---------------------------------------------------------------------------
# HTTP 小工具（标准库）
# ---------------------------------------------------------------------------
class Result:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        mark = "PASS" if ok else "FAIL"
        line = "[%s] %s" % (mark, name)
        if detail:
            line += " — %s" % detail
        print(line)
        return bool(ok)

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.checks)


def http(method: str, url: str, body: dict | None = None, timeout: float = 10.0) -> tuple[int, dict, str]:
    """返回 (status, headers(dict), text)。网络错误返回 (-1, {}, 错误文本)。"""
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "replace")
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, text
    except urllib.error.HTTPError as exc:  # 4xx/5xx 也返回 body
        text = exc.read().decode("utf-8", "replace")
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, text
    except Exception as exc:  # noqa: BLE001  连接失败等
        return -1, {}, "%s: %s" % (type(exc).__name__, exc)


def stats_of(base: str) -> dict | None:
    status, _, text = http("GET", base.rstrip("/") + "/api/stats")
    if status != 200:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def page_view_counts(stats: dict | None) -> dict:
    if not stats:
        return {"recruit_page_view": None, "share_page_view": None}
    recruit = sum(v["page_view"] for v in stats["by_variant"]["recruit"].values())
    share = sum(v["page_view"] for v in stats["by_variant"]["share"].values())
    return {"recruit_page_view": recruit, "share_page_view": share}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_health(base: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _, text = http("GET", base.rstrip("/") + "/api/health", timeout=3.0)
        if status == 200:
            print("  · 实例就绪：%s" % text.strip())
            return True
        time.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# 模式实现
# ---------------------------------------------------------------------------
def mode_spawn(args: argparse.Namespace, res: Result) -> dict:
    """独立实例 + 临时库的完整冒烟。"""
    tmpdir = tempfile.mkdtemp(prefix="landing-smoke-")
    db = os.path.join(tmpdir, "landing_smoke.sqlite3")
    port = free_port()
    base = "http://127.0.0.1:%d" % port
    cmd = [
        sys.executable, APP_PATH,
        "--host", "127.0.0.1", "--port", str(port), "--db", db,
        "--phase", "pre_t0", "--base-url", base,
    ]
    print("  · 启动命令：%s" % " ".join(cmd))
    print("  · 临时库：%s" % db)
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    receipt: dict = {"base": base, "db": db, "mode": "spawn"}
    try:
        if not wait_health(base):
            out = proc.stdout.read() if proc.stdout else ""
            res.add("实例启动 + /api/health", False, "20s 内未就绪；启动输出：%s" % out[:400])
            return receipt
        res.add("实例启动 + /api/health", True, "%s" % base)

        # 0) GET /api/stats（基线读数，必须在任何渲染请求之前）
        before = stats_of(base)
        res.add("GET /api/stats（基线读数）", before is not None,
                "recruit/share page_view = %s" % json.dumps(page_view_counts(before), ensure_ascii=False))

        # 1) GET / （招募假门）
        status, headers, text = http("GET", base + "/?utm_source=douyin&utm_medium=creator_recruit&utm_content=c001")
        ok = status == 200 and "text/html" in headers.get("content-type", "") and "页面版本=pre_t0" in text
        res.add("GET /（招募假门）", ok, "HTTP %s · 页脚含 页面版本=pre_t0 · Set-Cookie=%s"
                % (status, "pd_uid" in headers.get("set-cookie", "")))
        receipt["get_root"] = {"status": status, "phase_footer": "页面版本=pre_t0" in text,
                               "set_cookie": "pd_uid" in headers.get("set-cookie", "")}

        # 2) GET /s/<video_id> （分享页）
        status, _, text = http("GET", base + "/s/" + SMOKE_VIDEO_ID)
        ok = status == 200 and ("视频=%s" % SMOKE_VIDEO_ID) in text
        res.add("GET /s/<video_id>（分享页）", ok, "HTTP %s · 页脚含 视频=%s" % (status, SMOKE_VIDEO_ID))
        receipt["get_share"] = {"status": status, "footer": "视频=%s" % SMOKE_VIDEO_ID in text}

        # 3) （基线已在渲染请求之前读取，见上方 step 0）

        # 4) POST /api/events
        status, _, text = http("POST", base + "/api/events", {"event": "cta_click", "asset": "recruit"})
        ok = status == 200 and json.loads(text or "{}").get("ok") is True
        res.add("POST /api/events（cta_click）", ok, "HTTP %s · %s" % (status, text.strip()[:120]))

        # 5) POST /api/lead（consent=true；用不可投递的测试地址）
        status, _, text = http("POST", base + "/api/lead", {"contact": SMOKE_CONTACT, "consent": True})
        lead1 = json.loads(text or "{}")
        res.add("POST /api/lead（consent=true）", status == 200 and lead1.get("ok") is True and
                lead1.get("duplicated") is False, "HTTP %s · %s" % (status, text.strip()[:160]))

        # 6) 重复留资 → duplicated=true（保证分母口径）
        status, _, text = http("POST", base + "/api/lead", {"contact": SMOKE_CONTACT, "consent": True})
        lead2 = json.loads(text or "{}")
        res.add("POST /api/lead（重复 → duplicated=true）", status == 200 and lead2.get("duplicated") is True,
                "HTTP %s · %s" % (status, text.strip()[:160]))

        # 7) POST /api/lead（consent 缺失 → 400，合规硬门）
        status, _, text = http("POST", base + "/api/lead", {"contact": SMOKE_CONTACT})
        res.add("POST /api/lead（无 consent → 400）", status == 400, "HTTP %s · %s" % (status, text.strip()[:120]))

        # 8) POST /api/withdraw（撤回）
        status, _, text = http("POST", base + "/api/withdraw", {"contact": SMOKE_CONTACT})
        wd = json.loads(text or "{}")
        res.add("POST /api/withdraw（撤回）", status == 200 and wd.get("withdrawn") == 1,
                "HTTP %s · %s" % (status, text.strip()[:120]))

        # 9) /api/export/leads 未启用 → 404（默认关闭）
        status, _, text = http("GET", base + "/api/export/leads?token=x")
        res.add("GET /api/export/leads（未启用 → 404）", status == 404, "HTTP %s" % status)

        # 10) 未知路由 → 404
        status, _, text = http("GET", base + "/no-such-route")
        res.add("GET /no-such-route → 404", status == 404, "HTTP %s" % status)

        # 11) 末端复读：计数增量必须是「1 招募 + 1 分享 page_view」
        after = stats_of(base)
        b, a = page_view_counts(before), page_view_counts(after)
        delta = {"recruit": (a["recruit_page_view"] or 0) - (b["recruit_page_view"] or 0),
                 "share": (a["share_page_view"] or 0) - (b["share_page_view"] or 0)}
        status, _, text = http("GET", base + "/api/stats")
        decision = json.loads(text or "{}").get("decision", {})
        res.add("GET /api/stats（末端复读：增量 = 1 招募 + 1 分享 page_view）",
                delta == {"recruit": 1, "share": 1},
                "before=%s after=%s delta=%s" % (json.dumps(b), json.dumps(a), json.dumps(delta)))
        res.add("GET /api/stats（判据字段齐备）",
                set(["submit_rate_ge_8pct", "v1_minus_max_v2_v3_pp", "pass"]) <= set(decision.keys()),
                "decision=%s" % json.dumps(decision, ensure_ascii=False))
        receipt["stats_after"] = {"counts": a, "delta": delta, "decision": decision}

        # 12) 正式库未被触碰（本模式只写临时库）
        prod_db = os.path.join(ROOT, "marketing", "out", "landing.sqlite3")
        stamp = os.path.getmtime(prod_db) if os.path.exists(prod_db) else None
        res.add("正式分流统计库未被触碰", stamp == args.prod_db_mtime_before,
                "marketing/out/landing.sqlite3 mtime 不变（before=%s after=%s）" % (args.prod_db_mtime_before, stamp))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
        shutil.rmtree(tmpdir, ignore_errors=True)
        receipt["temp_dir_removed"] = not os.path.exists(tmpdir)
        print("  · 实例已停止，临时库已清理：%s" % receipt["temp_dir_removed"])
    return receipt


def mode_live(args: argparse.Namespace, res: Result) -> dict:
    """对已部署实例跑真实 GET 冒烟（会写入 2 条 page_view）。"""
    base = args.base.rstrip("/")
    receipt: dict = {"base": base, "mode": "live"}
    before = stats_of(base)
    if before is None:
        res.add("GET /api/stats（基线读数）", False, "未取到读数，实例不可达？")
        return receipt
    res.add("GET /api/stats（基线读数）", True,
            "recruit/share page_view = %s" % json.dumps(page_view_counts(before), ensure_ascii=False))

    status, headers, text = http("GET", base + "/")
    res.add("GET /（招募假门）", status == 200 and "text/html" in headers.get("content-type", "")
            and "页面版本=pre_t0" in text, "HTTP %s · 页脚相位标记=%s"
            % (status, "页面版本=pre_t0" in text))

    status, _, text = http("GET", base + "/s/" + SMOKE_VIDEO_ID)
    res.add("GET /s/<video_id>（分享页）", status == 200 and ("视频=%s" % SMOKE_VIDEO_ID) in text,
            "HTTP %s" % status)

    status, _, text = http("GET", base + "/api/stats")
    after = json.loads(text) if status == 200 else None
    res.add("GET /api/stats", after is not None, "HTTP %s" % status)
    b, a = page_view_counts(before), page_view_counts(after or {})
    delta = {"recruit": (a["recruit_page_view"] or 0) - (b["recruit_page_view"] or 0),
             "share": (a["share_page_view"] or 0) - (b["share_page_view"] or 0)}
    receipt["pollution"] = {"counts_before": b, "counts_after": a, "delta": delta}
    print("  · ⚠️ 本模式的已知污染：delta=%s（正式库需按 runbook §3 重建空库）" % json.dumps(delta))
    return receipt


def mode_readonly(args: argparse.Namespace, res: Result) -> dict:
    """对已部署实例只做不写事件的检查，并证明计数未变。"""
    base = args.base.rstrip("/")
    receipt: dict = {"base": base, "mode": "readonly"}
    status, _, text = http("GET", base + "/api/health")
    health_ok = status == 200 and json.loads(text or "{}").get("ok") is True
    res.add("GET /api/health", health_ok, "HTTP %s · %s" % (status, text.strip()[:160]))

    before = stats_of(base)
    res.add("GET /api/stats（前读数）", before is not None,
            "recruit/share page_view = %s" % json.dumps(page_view_counts(before), ensure_ascii=False))

    # HEAD 不写事件、不建分流，仅验证路由可达 + 下发 pd_uid cookie（app.py do_HEAD）
    status, headers, _ = http("HEAD", base + "/")
    res.add("HEAD / → 200 + Set-Cookie pd_uid", status == 200 and "pd_uid" in headers.get("set-cookie", ""),
            "HTTP %s" % status)
    status, headers, _ = http("HEAD", base + "/s/" + SMOKE_VIDEO_ID)
    res.add("HEAD /s/<video_id> → 200", status == 200, "HTTP %s" % status)
    print("      ⚠️ 局限：do_HEAD 对未知路径也返回 200，故 HEAD 只能证明「实例在服务」，"
          "不能证明路由存在；路由存在性由 spawn 模式证明。")

    after = stats_of(base)
    b, a = page_view_counts(before), page_view_counts(after or {})
    same = b == a
    res.add("只读检查未写入事件（前后计数一致）", same,
            "before=%s after=%s" % (json.dumps(b), json.dumps(a)))
    receipt["counts"] = {"before": b, "after": a, "unchanged": same}
    return receipt


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="落地页冒烟装置（纯标准库）")
    p.add_argument("--mode", choices=("spawn", "live", "readonly"), default="spawn")
    p.add_argument("--base", default="http://127.0.0.1:8088", help="live/readonly 模式的已部署基址")
    p.add_argument("--json", dest="json_out", default=None, help="把回执 JSON 另存到该路径")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.started_at = time.time()
    prod_db = os.path.join(ROOT, "marketing", "out", "landing.sqlite3")
    args.prod_db_mtime_before = os.path.getmtime(prod_db) if os.path.exists(prod_db) else None
    res = Result()
    print("[landing-smoke] mode=%s base=%s" % (args.mode, args.base))
    if args.mode == "spawn":
        receipt = mode_spawn(args, res)
    elif args.mode == "live":
        receipt = mode_live(args, res)
    else:
        receipt = mode_readonly(args, res)

    receipt["checks"] = res.checks
    receipt["ok"] = res.ok
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(receipt, fh, ensure_ascii=False, indent=2)
        print("[landing-smoke] 回执已写入：%s" % args.json_out)
    passed = sum(1 for c in res.checks if c["ok"])
    print("[landing-smoke] 检查 %d/%d 通过 → %s" % (passed, len(res.checks), "PASS" if res.ok else "FAIL"))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
