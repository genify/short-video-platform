#!/usr/bin/env python3
"""T0 证据门禁演练装置（纯标准库）。

用途：上线整合（PRO-24）第 3 项 —— T0 证据留痕与门禁纪律的**可复跑演练**。
用模板走一遍 `exit 3` 反证，并逐条钉住门禁的能力边界。

被演练的门禁：`marketing/landing/app.py::t0_evidence_gate()`（`--phase t0` 的前置校验）。
门禁只校验证据**信封**（envelope）的结构完整性：
    ① `pro7_delivered` 必须为布尔 true
    ② `preconditions_all_green` 必须为布尔 true
    ③ `preconditions` 必须是数组且条目数 ≥ 8
    ④ `evidence_date` 必须非空
它**不校验**这八项证据内容的真伪 —— 真实性由证据留档 + 人工复核负责（PRO-14 R-6 已登记）。

本脚本用**构造的演练件**证明上述边界（演练件写在临时目录，绝不落入仓库；仓库内除模板外
不得存在任何 T0 证据文件，脚本会自查并打印结论）。

用法：
    python3 marketing/scripts/t0_evidence_drill.py
    python3 marketing/scripts/t0_evidence_drill.py --json /tmp/drill.json

退出码：0 = 全部演练用例符合预期；1 = 有用例不符合预期。
"""

from __future__ import annotations

import argparse
import json
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
APP_PATH = os.path.join(ROOT, "marketing", "landing", "app.py")
TEMPLATE = os.path.join(ROOT, "marketing", "data", "t0_evidence.template.json")


def run_app_phase_t0(evidence: str | None, db: str | None = None, timeout: float = 6.0) -> dict:
    """跑 `--phase t0 --port 0`；返回 {exit_code, stdout, started}。

    exit 3 = 门禁拦住；若门禁通过，服务会开始监听并一直运行 → 由 timeout 终止，
    此时 started=True 且 stdout 含「T0 前置证据校验通过」。

    `db` 必须指向临时库：演练**不得**触碰正式分流统计库 marketing/out/landing.sqlite3。
    """
    cmd = [sys.executable, "-u", APP_PATH, "--phase", "t0", "--port", "0"]
    if db:
        cmd += ["--db", db]
    if evidence is not None:
        cmd += ["--t0-evidence", evidence]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return {"exit_code": proc.returncode, "stdout": out or "", "started": False}
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        return {"exit_code": None, "stdout": out or "", "started": True}


def gate_problems(evidence: str | None) -> list[str] | None:
    """直接调用门禁函数取问题清单（用于展示逐条原因）。"""
    sys.path.insert(0, os.path.join(ROOT, "marketing", "landing"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("landing_app_under_drill", APP_PATH)
    mod = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
    spec.loader.exec_module(mod)                          # type: ignore[union-attr]
    return mod.t0_evidence_gate(evidence)


def envelope(approved: str = "演练件（非真实证据）") -> dict:
    """构造一个「信封完整」的演练件。内容为演练占位，不是真实 T0 证据。"""
    data = {
        "purpose": "演练件：仅用于验证门禁信封校验，不得作为 T0 证据使用",
        "pro7_delivered": True,
        "preconditions_all_green": True,
        "evidence_date": "1970-01-01",
        "preconditions": [
            {"id": "#%d" % i, "name": "演练占位第 %d 项" % i, "status": "green",
             "evidence": "演练占位（无真实链接）"}
            for i in range(1, 9)
        ],
        "approved_by": approved,
        "notes": "演练件。真实 T0 证据必须逐条附真实证据链接并由人工复核。",
    }
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="T0 证据门禁演练装置")
    p.add_argument("--json", dest="json_out", default=None)
    args = p.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="t0-drill-")
    prod_db_path = os.path.join(ROOT, "marketing", "out", "landing.sqlite3")
    prod_db_before = os.path.getmtime(prod_db_path) if os.path.exists(prod_db_path) else None
    results: list[dict] = []
    print("[t0-drill] 临时演练目录：%s（脚本结束后清理，不落入仓库）" % tmp)

    def write(name: str, data: dict) -> str:
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return path

    def case(name: str, path: str | None, expect: str) -> None:
        """expect: 'exit3' = 必须被门禁拦住；'start' = 门禁放行并开始监听。"""
        run = run_app_phase_t0(path, db=os.path.join(tmp, "landing_drill.sqlite3"))
        if expect == "exit3":
            ok = run["exit_code"] == 3
            detail = "exit=%s（期望 3）" % run["exit_code"]
        else:
            ok = run["started"] and "T0 前置证据校验通过" in run["stdout"]
            detail = "门禁放行并开始监听（进程由演练超时终止）；stdout 含「T0 前置证据校验通过」=%s" % (
                "T0 前置证据校验通过" in run["stdout"])
        first = [ln for ln in run["stdout"].splitlines() if ln.strip()][:2]
        print("[%s] %s — %s" % ("PASS" if ok else "FAIL", name, detail))
        for ln in first:
            print("       | %s" % ln)
        results.append({"case": name, "expected": expect, "ok": ok, "detail": detail,
                        "exit_code": run["exit_code"], "stdout_head": first})

    try:
        # 反证 1：不给 --t0-evidence
        case("① 无 --t0-evidence", None, "exit3")

        # 反证 2：给一个不存在的路径
        case("② 证据文件不存在", os.path.join(tmp, "nope.json"), "exit3")

        # 反证 3：直接用模板（顶层开关仍为 false）
        case("③ 直接拿模板当证据（pro7_delivered/preconditions_all_green=false）", TEMPLATE, "exit3")

        # 反证 4：信封缺 evidence_date
        d = envelope(); d["evidence_date"] = ""
        case("④ 信封缺 evidence_date", write("no-date.json", d), "exit3")

        # 反证 5：preconditions 只有 7 条
        d = envelope(); d["preconditions"] = d["preconditions"][:7]
        case("⑤ preconditions 仅 7 条（< 8）", write("seven.json", d), "exit3")

        # 反证 6：开关写成字符串 "true"（不是布尔 true）
        d = envelope(); d["pro7_delivered"] = "true"
        case("⑥ pro7_delivered=\"true\"（字符串，非布尔）", write("string-true.json", d), "exit3")

        # 正证：信封完整 → 门禁放行（注意：这正是边界 —— 内容真伪门禁不管）
        good = envelope()
        case("⑦ 信封完整（8 条 + 双开关 true + evidence_date）→ 门禁放行",
             write("envelope-ok.json", good), "start")

        # 边界取证：逐条打印门禁返回值，证明「只验信封」
        problems_missing = gate_problems(None)
        problems_template = gate_problems(TEMPLATE)
        problems_good = gate_problems(os.path.join(tmp, "envelope-ok.json"))
        print("\n[边界取证] t0_evidence_gate() 返回值（逐条原因）")
        print("  · 无证据        → %s" % json.dumps(problems_missing, ensure_ascii=False))
        print("  · 模板原件      → %s" % json.dumps(problems_template, ensure_ascii=False))
        print("  · 信封完整演练件 → %s（空列表 = 放行）" % json.dumps(problems_good, ensure_ascii=False))
        envelope_only = problems_good == [] and any("演练" in json.dumps(x, ensure_ascii=False) for x in
                                                    [good]) is True
        print("  · 结论：信封完整的**演练件**（内容全为演练占位）被判为放行 → 门禁确实只验信封、"
              "不验内容真伪。真实性由证据留档 + 人工复核负责（PRO-14 R-6 / PRO-26）。")
        results.append({"case": "⑧ 边界取证：信封 vs 真伪", "expected": "envelope-only",
                        "ok": bool(envelope_only), "detail": "门禁只验信封（演练占位内容亦放行）"})
        print("[%s] ⑧ 边界取证：门禁只验信封（演练占位内容亦放行）" % ("PASS" if envelope_only else "FAIL"))

        # 自查：仓库内除模板外不得存在任何 T0 证据文件（演练件绝不落库）
        stray = [f for f in glob.glob(os.path.join(ROOT, "**", "t0_evidence*.json"), recursive=True)
                 if os.path.abspath(f) != os.path.abspath(TEMPLATE)]
        ok = not stray
        print("[%s] ⑨ 演练时仓库内无多余 T0 证据文件（仅模板）— 发现 %d 个多余文件"
              % ("PASS" if ok else "FAIL", len(stray)))
        results.append({"case": "⑨ 演练时仓库内无 T0 证据文件", "expected": "no-stray",
                        "ok": ok, "detail": json.dumps(stray, ensure_ascii=False)})

        # 自查：正式分流统计库未被演练触碰（演练全程只用临时库）
        prod_db = os.path.join(ROOT, "marketing", "out", "landing.sqlite3")
        stamp = os.path.getmtime(prod_db) if os.path.exists(prod_db) else None
        ok = stamp == prod_db_before
        print("[%s] ⑩ 正式分流统计库未被触碰 — mtime before=%s after=%s"
              % ("PASS" if ok else "FAIL", prod_db_before, stamp))
        results.append({"case": "⑩ 正式分流统计库未被触碰", "expected": "prod-db-untouched",
                        "ok": ok, "detail": "before=%s after=%s" % (prod_db_before, stamp)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok_all = all(r["ok"] for r in results)
    passed = sum(1 for r in results if r["ok"])
    print("\n[t0-drill] 用例 %d/%d 符合预期 → %s" % (passed, len(results), "PASS" if ok_all else "FAIL"))
    print("[t0-drill] 提醒：正式 T0 当日必须提交**真实**证据文件（模板结构 + 逐条真实证据链接），"
          "并随启动记录一并留档；不得以本演练件或模板本身启动。")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"ok": ok_all, "cases": results, "ts": int(time.time())}, fh,
                      ensure_ascii=False, indent=2)
        print("[t0-drill] 回执已写入：%s" % args.json_out)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
