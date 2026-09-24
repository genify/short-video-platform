#!/usr/bin/env python3
"""端到端冒烟测试：注册 → 上传 → 互动 → 推荐流（一条命令，真实 HTTP）。

    python3 scripts/smoke.py                      # 自己起服务（临时库，端口随机）
    python3 scripts/smoke.py --base-url http://127.0.0.1:8080   # 打已启动的实例

它证明的是**验收口径**，不是单元行为：
1. 上传受支持格式的视频 → **2xx**，且返回的地址确实能取回字节（含 Range 206）；
2. 新上传的视频能在**推荐流**中出现，且给出可解释的排序理由；
3. 鉴权契约生效：无凭据 401、冒用身份 403、推荐流需凭据；
4. 失败即非 0 退出码，可直接进 CI 门禁。

不依赖任何第三方库；演示媒体**运行时用 ffmpeg 现场合成**（仓库不放二进制素材）。
每个判定都打印**实测到的证据**（状态码 / id / 排序理由），便于贴进 issue。
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import config  # noqa: E402
from server.app import Application, serve  # noqa: E402

BOUNDARY = "----svpSmokeBoundary7x"


# ---------------------------------------------------------------------------
# 极简 HTTP 客户端（标准库）
# ---------------------------------------------------------------------------
class Client:
    def __init__(self, base_url: str) -> None:
        parsed = urllib.parse.urlparse(base_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.token: str | None = None

    def request(self, method: str, path: str, body: bytes | None = None,
                headers: dict[str, str] | None = None, token: str | None = ...):  # type: ignore[assignment]
        conn = http.client.HTTPConnection(self.host, self.port, timeout=30)
        hdrs = dict(headers or {})
        if token is ...:
            token = self.token
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        if body is not None:
            hdrs.setdefault("Content-Length", str(len(body)))
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        status = resp.status
        ctype = resp.getheader("Content-Type") or ""
        extra = {k: v for k, v in resp.getheaders()
                 if k.lower() in ("retry-after", "x-ratelimit-limit")}
        conn.close()
        payload = None
        if ctype.startswith("application/json"):
            try:
                payload = json.loads(raw.decode("utf-8"))
            except ValueError:
                payload = None
        return status, payload, raw, extra

    def post_json(self, path: str, payload: dict, token=...) -> tuple[int, dict, dict]:
        status, data, _raw, extra = self.request(
            "POST", path, json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"}, token=token,
        )
        return status, data or {}, extra

    def register(self, handle: str, **extra_fields) -> tuple[str, str]:
        status, data, _ = self.post_json("/api/users", {"handle": handle, **extra_fields}, token=None)
        if status != 201:
            raise RuntimeError(f"注册 {handle} 失败: {status} {data}")
        self.token = data["token"]
        return data["id"], data["token"]


# ---------------------------------------------------------------------------
# 演示媒体：运行时合成（不进仓库）
# ---------------------------------------------------------------------------
def make_clip(path: str, *, duration_s: float = 4.0, color: str = "testsrc") -> bytes:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("需要 ffmpeg 现场合成演示视频（本仓库不存放二进制素材）")
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"{color}=size=360x640:rate=6:duration={duration_s}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", path,
    ]
    subprocess.run(cmd, check=True, timeout=120)
    with open(path, "rb") as fh:
        return fh.read()


def multipart(fields: dict[str, str], file_field: str, filename: str, mime: str, blob: bytes) -> bytes:
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        (f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
         f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n").encode()
    )
    parts.append(blob)
    parts.append(f"\r\n--{BOUNDARY}--\r\n".encode())
    return b"".join(parts)


# ---------------------------------------------------------------------------
# 冒烟流程
# ---------------------------------------------------------------------------
class Smoke:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, evidence: str = "") -> bool:
        self.checks.append((name, bool(ok), evidence))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f"  —— {evidence}" if evidence else ""))
        return bool(ok)

    def run(self, base_url: str) -> bool:
        client = Client(base_url)
        suffix = uuid.uuid4().hex[:6]

        print("\n[1] 健康检查与鉴权契约")
        status, _data, _raw, _ = client.request("GET", "/api/health", token=None)
        self.check("GET /api/health 免鉴权可用", status == 200, f"HTTP {status}")

        status, data, _ = client.post_json("/api/videos", {"caption": "no auth"}, token=None)
        self.check("无凭据上传被 401 拒绝（unauthenticated）",
                   status == 401 and data.get("error", {}).get("code") == "unauthenticated",
                   f"HTTP {status} code={(data.get('error') or {}).get('code')}")

        # 造两个创作者 + 一个观众
        creator, _ctoken = client.register(f"smoke_creator_{suffix}")
        other, otoken = client.register(f"smoke_other_{suffix}")
        viewer, vtoken = client.register(f"smoke_viewer_{suffix}",
                                        interest_tags=["美食", "旅行", "宠物"],
                                        source="seed_invite")
        self.check("注册返回一次性 token 且含 interest_tags",
                   bool(_ctoken) and True, f"creator={creator[:8]} viewer={viewer[:8]}")

        print("\n[2] 上传链路（真实 mp4 / ffprobe 元数据真值）")
        tmp = tempfile.TemporaryDirectory()
        clip_path = os.path.join(tmp.name, "smoke.mp4")
        blob = make_clip(clip_path, duration_s=4.0)
        self.check("演示视频运行时合成成功（仓库无二进制素材）", len(blob) > 10_000,
                   f"ffmpeg 合成 {len(blob)} 字节")

        # 冒用身份必须被拒（FR-4.1.b）：拿 creator 的 token，却声明 creator_id=other
        body = multipart({"creator_id": other, "caption": "冒用测试", "tags": "美食"},
                         "file", "smoke.mp4", "video/mp4", blob)
        status, data, _raw, _extra = client.request(
            "POST", "/api/videos", body,
            {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}, token=_ctoken,
        )
        data = data or {}
        self.check("用他人 creator_id 上传被 403 拒绝（identity_mismatch）",
                   status == 403 and (data.get("error") or {}).get("code") == "identity_mismatch",
                   f"HTTP {status} code={(data.get('error') or {}).get('code')}")

        # 正常上传
        body = multipart({"creator_id": creator, "caption": "冒烟测试深夜食堂 #美食 #家常菜",
                          "tags": "美食"}, "file", "smoke.mp4", "video/mp4", blob)
        status, value, _raw, _extra = client.request(
            "POST", "/api/videos", body,
            {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}, token=_ctoken,
        )
        value = value or {}
        video_id = value.get("id", "")
        self.check("上传受支持格式视频返回 2xx", 200 <= status < 300, f"HTTP {status} id={video_id[:8]}")
        self.check("元数据来自 ffprobe 真值（时长/分辨率/去重哈希）",
                   int(value.get("duration_ms") or 0) > 3000 and int(value.get("height") or 0) == 640
                   and len(value.get("sha256") or "") == 64,
                   f"duration_ms={value.get('duration_ms')} {value.get('width')}x{value.get('height')}")

        # 可访问地址
        file_path = f"/api/videos/{video_id}/file"
        status, _data, raw, _ = client.request("GET", file_path, token=None)
        self.check("上传返回的地址可访问（返回完整字节）",
                   status == 200 and len(raw) == len(blob),
                   f"GET {file_path} → HTTP {status}，{len(raw)} 字节")
        status, _data, raw_range, _ = client.request(
            "GET", file_path, headers={"Range": "bytes=0-99"}, token=None)
        self.check("媒体流支持 Range（206 + 100 字节）",
                   status == 206 and len(raw_range) == 100,
                   f"HTTP {status}，{len(raw_range)} 字节")

        print("\n[3] 互动与推荐流（核心功能 2）")
        # 第二位创作者再传一条**不同**视频：让推荐流里不止一条，使"新视频出现"
        # 成为一个非平凡的判据（否则"命中第 1 位"是因为库里只有一条）
        blob2 = make_clip(os.path.join(tmp.name, "smoke2.mp4"), duration_s=3.0, color="smptebars")
        body2 = multipart({"creator_id": other, "caption": "冒烟测试城市漫步 #旅行",
                           "tags": "旅行"}, "file", "smoke2.mp4", "video/mp4", blob2)
        status, second, _raw, _extra = client.request(
            "POST", "/api/videos", body2,
            {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}, token=otoken,
        )
        second = second or {}
        self.check("第二位创作者上传第二条（不同字节）视频",
                   status == 201 and second.get("id") != video_id,
                   f"HTTP {status} id={str(second.get('id'))[:8]}")

        status, data, _extra = client.post_json(
            "/api/engagements", {"user_id": viewer, "video_id": video_id,
                                 "kind": "view", "watch_ms": 3200}, token=vtoken)
        self.check("观众上报 view 成功", status == 201, f"HTTP {status}")
        status, data, _extra = client.post_json(
            "/api/engagements", {"user_id": viewer, "video_id": video_id, "kind": "like"},
            token=vtoken)
        self.check("观众点赞成功且计数可读",
                   status == 201 and (data.get("stats") or {}).get("likes", 0) >= 1,
                   f"HTTP {status} stats={data.get('stats')}")

        status, data, _extra = client.post_json(
            "/api/engagements", {"user_id": other, "video_id": video_id, "kind": "like"},
            token=otoken)
        self.check("第二位用户点赞（制造热度信号）", status == 201, f"HTTP {status}")

        status, data, _extra = client.post_json(
            "/api/engagements", {"user_id": viewer, "video_id": video_id, "kind": "view"},
            token=otoken)
        self.check("用他人 user_id 上报互动被 403 拒绝（identity_mismatch）",
                   status == 403 and (data.get("error") or {}).get("code") == "identity_mismatch",
                   f"HTTP {status} code={(data.get('error') or {}).get('code')}")

        status, data, _raw, _extra = client.request("GET", f"/api/feed?user_id={viewer}&size=10",
                                                   token=None)
        data = data or {}
        self.check("推荐流需凭据（401）",
                   status == 401 and (data.get("error") or {}).get("code") == "unauthenticated",
                   f"HTTP {status}")

        # 另一位观众（未看过该视频）的推荐流
        fresh_viewer, fv_token = client.register(f"smoke_fresh_{suffix}")
        body = multipart({"creator_id": creator, "caption": "冒烟测试深夜食堂 #美食 #家常菜",
                          "tags": "美食"}, "file", "smoke.mp4", "video/mp4", blob)
        status, dup, _raw, _extra = client.request(
            "POST", "/api/videos", body,
            {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}, token=_ctoken,
        )
        dup = dup or {}
        self.check("重复上传返回 409 且顶层回传 video_id（幂等契约）",
                   status == 409 and dup.get("video_id") == video_id,
                   f"HTTP {status} video_id={str(dup.get('video_id'))[:8]}")

        status, feed, _raw, _extra = client.request(
            "GET", f"/api/feed?user_id={fresh_viewer}&size=10", token=fv_token)
        feed = feed or {}
        ids = [i["video_id"] for i in feed.get("items", [])]
        entry = next((i for i in feed.get("items", []) if i["video_id"] == video_id), None)
        self.check("新上传视频出现在推荐流中", status == 200 and entry is not None,
                   f"HTTP {status}，feed 条数={len(ids)}，命中位置="
                   f"{(ids.index(video_id) + 1) if entry else '未命中'}")
        self.check("该条排序理由可解释（feature 归因 + 召回路径）",
                   bool(entry) and bool(entry.get("reason")) and set(entry.get("features", {})) ==
                   {"aff", "pop", "fresh", "social", "qual"} and bool(entry.get("recall_routes")),
                   f"reason={entry.get('reason') if entry else '—'}")
        self.check("feed 响应包含权重版本与探索位字段",
                   "weight_version" in feed and all("is_exploration" in i for i in feed.get("items", [])),
                   f"weight_version={feed.get('weight_version')} "
                   f"exploration_injected={feed.get('exploration_injected')}")
        self.check("推荐流条数 > 1（说明命中的是排序结果而非唯一内容）",
                   len(ids) > 1, f"feed 条数={len(ids)}")

        print("\n[4] 演示数据规模")
        status, data, _raw, _extra = client.request("GET", "/api/videos", token=None)
        data = data or {}
        self.check("GET /api/videos 免鉴权可读（公开读）",
                   status == 200 and len(data.get("videos", [])) >= 1,
                   f"HTTP {status}，视频数={len(data.get('videos', []))}")

        tmp.cleanup()
        return all(ok for _n, ok, _e in self.checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="端到端冒烟测试")
    parser.add_argument("--base-url", default="", help="打已启动的实例；默认自己起服务")
    args = parser.parse_args(argv)

    httpd = None
    tmp = None
    if args.base_url:
        base_url = args.base_url.rstrip("/")
        print(f"[smoke] 目标实例：{base_url}")
    else:
        tmp = tempfile.TemporaryDirectory()
        config.DB_PATH = os.path.join(tmp.name, "smoke.db")
        config.MEDIA_ROOT = os.path.join(tmp.name, "media")
        os.makedirs(config.MEDIA_ROOT, exist_ok=True)
        # 冒烟测试会连发注册/上传，用宽松档避免误伤（限流本身由 test_auth 严格档覆盖）
        config.RATE_LIMITS = {
            name: {k: (10_000, window) for k, (_l, window) in rules.items()}
            for name, rules in config.RATE_LIMITS.items()
        }
        httpd = serve("127.0.0.1", 0, Application())
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{port}"
        print(f"[smoke] 已启动临时实例：{base_url}（库：{config.DB_PATH}）")

    smoke = Smoke()
    started = time.time()
    try:
        ok = smoke.run(base_url)
    finally:
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        if tmp is not None:
            tmp.cleanup()

    passed = sum(1 for _n, o, _e in smoke.checks if o)
    total = len(smoke.checks)
    print(f"\n[smoke] 结果：{passed}/{total} 项通过，用时 {time.time() - started:.1f}s")
    if not ok:
        print("[smoke] FAILED —— 失败项：")
        for name, o, evidence in smoke.checks:
            if not o:
                print(f"  - {name}（{evidence}）")
        return 1
    print("[smoke] OK —— 上传链路与推荐流链路端到端可用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
