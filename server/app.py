"""短视频平台 MVP —— HTTP API 与服务入口。

纯标准库实现（环境无 Flask/FastAPI）。路由表见 docs/api.md。

    POST /api/users                     创建用户
    POST /api/videos                    上传视频（multipart/form-data）
    GET  /api/videos/{id}               视频详情
    GET  /api/videos/{id}/file          媒体流（支持 Range）
    POST /api/engagements               上报互动（view/complete/like/share/skip/follow）
    POST /api/follows                   关注创作者
    GET  /api/feed?user_id=&size=       推荐流  <<< 核心
    POST /api/admin/rebuild-cf          重建 item-item 协同过滤相似度
    GET  /api/health                    健康检查
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import config, media
from .db import Database
from .recommend import RecommendEngine

MAX_JSON_BODY = 1 << 20  # 1MB

# ---------------------------------------------------------------------------
# 应用（与 HTTP 层解耦，便于单元测试直接调用）
# ---------------------------------------------------------------------------
class Application:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database(config.DB_PATH)
        self.engine = RecommendEngine(self.db)

    # -- 用户 -----------------------------------------------------------
    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        handle = str(payload.get("handle") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,32}", handle):
            raise ApiError("handle 需为 2~32 位字母/数字/下划线/中文", code="invalid_handle")
        if self.db.get_user_by_handle(handle):
            raise ApiError(f"handle 已存在: {handle}", status=409, code="handle_taken")
        return self.db.create_user(uuid.uuid4().hex, handle, str(payload.get("display") or ""))

    def get_user(self, user_id: str) -> dict[str, Any]:
        user = self.db.get_user(user_id)
        if not user:
            raise ApiError("用户不存在", status=404, code="user_not_found")
        return user

    # -- 视频 -----------------------------------------------------------
    def upload_video(self, multipart: media.ParsedMultipart) -> dict[str, Any]:
        creator_id = (multipart.fields.get("creator_id") or "").strip()
        if not creator_id:
            raise ApiError("缺少 creator_id 字段", code="missing_creator")
        self.get_user(creator_id)
        if not multipart.files:
            raise ApiError("缺少文件字段 file", code="missing_file")
        upload = multipart.files[0]
        if upload.field_name not in ("file", "video"):
            raise ApiError(f"未知文件字段 {upload.field_name}，应为 file", code="bad_file_field")

        meta = media.probe_media(upload.tmp_path)
        media.validate_upload(upload, meta)
        upload.compute_hash()

        dup = self.db.hash_exists(upload.sha256)
        if dup:
            raise ApiError(
                f"视频已存在（去重命中 video_id={dup['id']}）", status=409, code="duplicate_video"
            )

        caption = (multipart.fields.get("caption") or "").strip()[:500]
        tags = media.extract_tags(caption, multipart.fields.get("tags"))

        video_id = uuid.uuid4().hex
        rel_path = media.storage_path_for(video_id, upload.filename)
        media.persist(upload, rel_path)
        return self.db.create_video(
            video_id=video_id,
            creator_id=creator_id,
            caption=caption,
            tags=tags,
            duration_ms=int(meta.get("duration_ms") or 0),
            width=int(meta.get("width") or 0),
            height=int(meta.get("height") or 0),
            size_bytes=upload.size_bytes,
            sha256=upload.sha256,
            storage_path=rel_path,
        )

    def get_video(self, video_id: str) -> dict[str, Any]:
        video = self.db.get_video(video_id)
        if not video:
            raise ApiError("视频不存在", status=404, code="video_not_found")
        return video

    # -- 互动 -----------------------------------------------------------
    _KINDS = {"view", "complete", "like", "share", "skip", "comment", "follow"}

    def add_engagement(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "")
        video_id = str(payload.get("video_id") or "")
        kind = str(payload.get("kind") or "")
        if kind not in self._KINDS:
            raise ApiError(f"kind 非法，允许 {sorted(self._KINDS)}", code="invalid_kind")
        self.get_user(user_id)
        video = self.get_video(video_id)
        watch_ms = int(payload.get("watch_ms") or 0)
        self.db.add_engagement(user_id, video_id, kind, watch_ms)
        if kind == "follow":
            self.db.add_follow(user_id, video["creator_id"])
        views = self.db.get_video(video_id) or {}
        return {
            "ok": True,
            "video_id": video_id,
            "kind": kind,
            "stats": {
                "views": views.get("views", 0),
                "completes": views.get("completes", 0),
                "likes": views.get("likes", 0),
                "shares": views.get("shares", 0),
            },
        }

    def add_follow(self, payload: dict[str, Any]) -> dict[str, Any]:
        follower = str(payload.get("follower_id") or "")
        followee = str(payload.get("followee_id") or "")
        self.get_user(follower)
        self.get_user(followee)
        if follower == followee:
            raise ApiError("不能关注自己", code="self_follow")
        self.db.add_follow(follower, followee)
        return {"ok": True, "follower_id": follower, "followee_id": followee}

    # -- 推荐流 ---------------------------------------------------------
    def feed(self, query: dict[str, list[str]]) -> dict[str, Any]:
        user_id = (query.get("user_id") or [""])[0]
        if not user_id:
            raise ApiError("缺少 user_id 查询参数", code="missing_user_id")
        self.get_user(user_id)
        try:
            size = int((query.get("size") or [str(config.FEED_DEFAULT_SIZE)])[0])
        except ValueError:
            raise ApiError("size 必须是整数", code="invalid_size")
        seed_raw = (query.get("seed") or [""])[0]
        seed = int(seed_raw) if seed_raw.isdigit() else None
        return self.engine.feed(user_id, size=size, seed=seed)

    def rebuild_cf(self) -> dict[str, Any]:
        n = self.db.rebuild_item_similarity()
        return {"ok": True, "item_sim_pairs": n}


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


# ---------------------------------------------------------------------------
# HTTP 层
# ---------------------------------------------------------------------------
_VIDEO_FILE_RE = re.compile(r"^/api/videos/([0-9a-f]+)/file$")
_VIDEO_RE = re.compile(r"^/api/videos/([0-9a-f]+)$")
_USER_RE = re.compile(r"^/api/users/([0-9a-f]+)$")


class Handler(BaseHTTPRequestHandler):
    server_version = "SVP/0.1"
    protocol_version = "HTTP/1.1"
    app: Application  # 由 serve() 注入

    # -- 工具 -----------------------------------------------------------
    def _drain_body(self) -> bool:
        """确保请求体已被读完，返回 True 表示连接可以安全复用。

        HTTP/1.1 默认 keep-alive：若校验先于读取体失败（例如 Content-Type
        不对），残留字节会被当成下一个请求解析，导致连接错乱。

        两个必须避开的陷阱：
        1. 请求体已被 `_read_json()` 消费过时，再读会永久阻塞（等永远不会
           到来的字节）——因此用 `_body_consumed` 标记。
        2. 直接对 socket 调 `read(65536)` 在 keep-alive 下会阻塞——因此
           multipart 路径改用 `LengthLimitedReader` 显式限制读取长度。
        """
        reader = getattr(self, "_body_reader", None)
        if reader is not None:
            return reader.drain()
        if getattr(self, "_body_consumed", False):
            return True
        try:
            remaining = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            remaining = 0
        while remaining > 0:
            chunk = self.rfile.read(min(1 << 16, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
        self._body_consumed = True
        return remaining <= 0

    def _send_json(self, payload: Any, status: int = 200, close: bool = False) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int, code: str, close: bool = False) -> None:
        self._send_json({"error": {"code": code, "message": message}}, status=status, close=close)

    def _query(self) -> dict[str, list[str]]:
        parsed = urllib.parse.urlparse(self.path)
        return urllib.parse.parse_qs(parsed.query)

    def _path(self) -> str:
        return urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._body_consumed = True
            return {}
        if length > MAX_JSON_BODY:
            raise ApiError("JSON 请求体过大", status=413, code="payload_too_large")
        raw = self.rfile.read(length)
        self._body_consumed = True
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError("请求体不是合法 JSON", code="invalid_json")
        if not isinstance(data, dict):
            raise ApiError("请求体必须是 JSON 对象", code="invalid_json_shape")
        return data

    def log_message(self, fmt: str, *args) -> None:  # 静默（由外层统一收集）
        if os.environ.get("SVP_HTTP_LOG"):
            super().log_message(fmt, *args)

    # -- 路由 -----------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self._path()
        try:
            if path == "/api/health":
                return self._send_json({"ok": True, "ts": time.time()})
            if path == "/api/feed":
                return self._send_json(self.app.feed(self._query()))
            if path == "/api/videos":
                return self._send_json({"videos": self.app.db.list_all_videos()})
            m = _VIDEO_FILE_RE.match(path)
            if m:
                return self._serve_media(self.app.get_video(m.group(1)))
            m = _VIDEO_RE.match(path)
            if m:
                return self._send_json(self.app.get_video(m.group(1)))
            m = _USER_RE.match(path)
            if m:
                return self._send_json(self.app.get_user(m.group(1)))
            if path in ("/", "/index.html"):
                return self._serve_home()
            self._send_error_json(f"未找到路由 {path}", 404, "not_found")
        except ApiError as exc:
            self._send_error_json(exc.message, exc.status, exc.code)
        except media.UploadError as exc:
            self._send_error_json(exc.message, exc.status, exc.code)
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(f"服务内部错误: {exc}", 500, "internal_error")

    def do_POST(self) -> None:  # noqa: N802
        path = self._path()
        tmpdir = ""
        self._body_consumed = False
        self._body_reader = None
        try:
            if path == "/api/users":
                return self._send_json(self.app.create_user(self._read_json()), 201)
            if path == "/api/videos":
                ctype = self.headers.get("Content-Type") or ""
                length = int(self.headers.get("Content-Length") or 0)
                if length > config.MAX_UPLOAD_BYTES + (1 << 20):
                    raise ApiError(
                        f"上传体积超过上限 {config.MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
                        status=413,
                        code="payload_too_large",
                    )
                # 关键：用显式长度限制的读取器包裹 socket，绝不依赖 EOF。
                # 直接把 socket 交给解析器会在 keep-alive 下阻塞。
                reader = media.LengthLimitedReader(self.rfile, length)
                self._body_reader = reader
                parsed = media.parse_multipart(reader, ctype, config.MAX_UPLOAD_BYTES + (1 << 20))
                tmpdir = parsed.tmpdir
                return self._send_json(self.app.upload_video(parsed), 201)
            if path == "/api/engagements":
                return self._send_json(self.app.add_engagement(self._read_json()), 201)
            if path == "/api/follows":
                return self._send_json(self.app.add_follow(self._read_json()), 201)
            if path == "/api/admin/rebuild-cf":
                return self._send_json(self.app.rebuild_cf())
            self._send_error_json(f"未找到路由 {path}", 404, "not_found")
        except ApiError as exc:
            self._send_error_json(exc.message, exc.status, exc.code, close=not self._drain_body())
        except media.UploadError as exc:
            self._send_error_json(exc.message, exc.status, exc.code, close=not self._drain_body())
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(
                f"服务内部错误: {exc}", 500, "internal_error", close=not self._drain_body()
            )
        finally:
            if tmpdir:
                import shutil

                shutil.rmtree(tmpdir, ignore_errors=True)

    # -- 媒体流 ---------------------------------------------------------
    def _serve_media(self, video: dict[str, Any]) -> None:
        path = os.path.abspath(video.get("storage_path") or "")
        if not path or not os.path.isfile(path):
            return self._send_error_json("媒体文件缺失", 404, "media_missing")
        size = os.path.getsize(path)
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        status = 200
        if rng and rng.startswith("bytes="):
            spec = rng[6:].split(",")[0].strip()
            lo, _, hi = spec.partition("-")
            try:
                if lo:
                    start = int(lo)
                    end = int(hi) if hi else size - 1
                elif hi:
                    start = max(0, size - int(hi))
                status = 206
            except ValueError:
                start, end = 0, size - 1
                status = 200
        end = min(end, size - 1)
        length = max(0, end - start + 1)
        ctype = "video/mp4"
        ext = os.path.splitext(path)[1].lower()
        ctype = {".mp4": "video/mp4", ".mov": "video/quicktime",
                 ".webm": "video/webm", ".mkv": "video/x-matroska"}.get(ext, "application/octet-stream")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(1 << 16, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    # -- 首页（演示页）--------------------------------------------------
    def _serve_home(self) -> None:
        videos = self.app.db.list_all_videos()
        rows = "".join(
            f"<tr><td>{v['id'][:8]}</td><td>{_esc(v['caption']) or '（无文案）'}</td>"
            f"<td>{_esc(', '.join(v['tags']))}</td><td>{v['duration_ms']/1000:.1f}s</td>"
            f"<td>{v['views']}</td><td>{v['likes']}</td><td>{v['creator_id'][:8]}</td></tr>"
            for v in videos[:50]
        )
        html = (
            "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
            "<title>短视频平台 MVP</title>"
            "<style>body{font-family:system-ui,-apple-system,'Noto Sans CJK SC',sans-serif;"
            "background:#0d1117;color:#e6edf3;margin:0;padding:32px}"
            "h1{font-size:22px}code{background:#161b22;padding:2px 6px;border-radius:4px}"
            "table{border-collapse:collapse;width:100%;margin-top:16px;font-size:13px}"
            "th,td{border:1px solid #30363d;padding:6px 10px;text-align:left}"
            "th{background:#161b22}</style>"
            "<h1>短视频平台 MVP · 已发布视频</h1>"
            f"<p>视频总数：<b>{len(videos)}</b>。推荐流接口："
            "<code>GET /api/feed?user_id=&lt;uuid&gt;&amp;size=10</code></p>"
            "<table><tr><th>ID</th><th>文案</th><th>标签</th><th>时长</th>"
            "<th>播放</th><th>点赞</th><th>创作者</th></tr>"
            f"{rows or '<tr><td colspan=7>暂无视频，请先调用 POST /api/videos 上传</td></tr>'}"
            "</table></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def _esc(text: Any) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def serve(host: str = "127.0.0.1", port: int = 8080, app: Application | None = None) -> ThreadingHTTPServer:
    app = app or Application()
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd
