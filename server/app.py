"""短视频平台 MVP —— HTTP API 与服务入口。

纯标准库实现（环境无 Flask/FastAPI）。路由表见 docs/api.md。

    POST /api/users                     创建用户（返回一次性 token）
    POST /api/sessions                  开发级会话：凭 handle 换 token
    POST /api/sessions/revoke           撤销当前 token
    POST /api/videos                    上传视频（multipart/form-data，需鉴权）
    GET  /api/videos/{id}               视频详情
    GET  /api/videos/{id}/file          媒体流（支持 Range）
    POST /api/engagements               上报互动（需鉴权，身份须与 token 一致）
    POST /api/follows                   关注创作者（需鉴权）
    GET  /api/feed?user_id=&size=       推荐流  <<< 核心（需鉴权）
    POST /api/admin/rebuild-cf          重建 item-item 协同过滤（需管理员凭据）
    GET  /api/health                    健康检查（免鉴权、免限流）

鉴权与限流（FR-3 / FR-4，P0）：
- `Authorization: Bearer <token>`；令牌只存 `sha256`，明文仅签发时返回一次；
- 身份一致性：请求体/查询里的 `user_id`/`creator_id` 必须等于 token 身份，
  否则 `403 identity_mismatch`（杜绝冒用）；
- 管理端点用独立管理员凭据（`SVP_ADMIN_TOKEN` 环境变量，未配置则一律拒绝）；
- 所有端点走令牌桶限流；上传/互动的限流在**读取请求体之前**执行；
- 错误与日志一律脱敏，不回显令牌。
"""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import auth, config, media, ratelimit
from .db import Database
from .recommend import RecommendEngine

MAX_JSON_BODY = 1 << 20  # 1MB
BODY_DRAIN_TIMEOUT = 3.0  # 排空请求体的单次 socket 超时（秒）


# ---------------------------------------------------------------------------
# 应用（与 HTTP 层解耦，便于单元测试直接调用）
# ---------------------------------------------------------------------------
class Application:
    def __init__(self, db: Database | None = None, limiter: ratelimit.RateLimiter | None = None) -> None:
        self.db = db or Database(config.DB_PATH)
        self.engine = RecommendEngine(self.db)
        self.limiter = limiter or ratelimit.RateLimiter()

    # -- 用户 -----------------------------------------------------------
    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        handle = str(payload.get("handle") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,32}", handle):
            raise ApiError("handle 需为 2~32 位字母/数字/下划线/中文", code="invalid_handle")
        if self.db.get_user_by_handle(handle):
            raise ApiError(f"handle 已存在: {handle}", status=409, code="handle_taken")

        interest_tags = payload.get("interest_tags")
        if interest_tags is not None:
            interest_tags = self._validate_interest_tags(interest_tags)
        source = str(payload.get("source") or "unknown").strip() or "unknown"
        if source not in config.REGISTER_SOURCES:
            raise ApiError(
                f"source 非法，允许 {sorted(config.REGISTER_SOURCES)}", code="invalid_source"
            )

        user = self.db.create_user(
            uuid.uuid4().hex,
            handle,
            str(payload.get("display") or ""),
            interest_tags=interest_tags or [],
            source=source,
        )
        # 凭据只在创建响应中返回一次；服务端仅保存 sha256
        token, expires_at = self._issue_token(user["id"])
        return {**self.public_user(user), "token": token, "expires_at": expires_at,
                "auth_level": config.AUTH_LEVEL}

    @staticmethod
    def _validate_interest_tags(raw: Any) -> list[str]:
        if not isinstance(raw, list):
            raise ApiError("interest_tags 必须是字符串数组", code="invalid_interest_tags")
        tags = [str(t).strip() for t in raw]
        if len(tags) != config.INTEREST_TAG_COUNT:
            raise ApiError(
                f"interest_tags 必须恰好 {config.INTEREST_TAG_COUNT} 个", code="invalid_interest_tags"
            )
        bad = [t for t in tags if t not in config.INTEREST_TAG_WHITELIST]
        if bad:
            raise ApiError(
                f"interest_tags 含白名单外标签: {bad}；允许 {list(config.INTEREST_TAG_WHITELIST)}",
                code="invalid_interest_tags",
            )
        return list(dict.fromkeys(tags))

    @staticmethod
    def public_user(user: dict[str, Any]) -> dict[str, Any]:
        """对外用户视图：**不含**任何凭据字段（token 明文从不落库）。"""
        return {
            "id": user.get("id"),
            "handle": user.get("handle"),
            "display": user.get("display"),
            "created_at": user.get("created_at"),
            "interest_tags": user.get("interest_tags") or [],
            "source": user.get("source") or "",
        }

    def get_user(self, user_id: str) -> dict[str, Any]:
        user = self.db.get_user(user_id)
        if not user:
            raise ApiError("用户不存在", status=404, code="user_not_found")
        return self.public_user(user)

    # -- 会话（FR-3.1）--------------------------------------------------
    def _issue_token(self, user_id: str) -> tuple[str, float]:
        token = auth.new_token()
        info = self.db.create_token(
            auth.token_hash(token), user_id, config.TOKEN_TTL_DAYS, config.AUTH_LEVEL
        )
        return token, float(info["expires_at"])

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """开发级会话（MVP 无密码/验证码）—— 响应必须显式标注 `auth_level: dev`。"""
        handle = str(payload.get("handle") or "").strip()
        if not handle:
            raise ApiError("缺少 handle", code="missing_handle")
        user = self.db.get_user_by_handle(handle)
        if not user:
            raise ApiError("用户不存在", status=404, code="user_not_found")
        token, expires_at = self._issue_token(user["id"])
        return {
            "token": token,
            "user_id": user["id"],
            "expires_at": expires_at,
            "auth_level": config.AUTH_LEVEL,
        }

    def revoke_session(self, token_digest: str) -> dict[str, Any]:
        if not self.db.revoke_token(token_digest):
            raise ApiError("令牌不存在", status=401, code="token_invalid")
        return {"ok": True, "revoked": True}

    def authenticate(self, token: str | None) -> dict[str, Any]:
        """校验 Bearer 令牌，返回 `{user_id, token_hash}`；失败抛 401。"""
        if not token:
            raise ApiError("缺少 Authorization 头", status=401, code="unauthenticated")
        digest = auth.token_hash(token)
        record = self.db.get_token(digest)
        # 令牌不存在 / 已撤销 / 用户已被删除 —— 一律按"无效"处理（fail-closed）
        if not record or record.get("revoked") or not record.get("user_exists"):
            raise ApiError("令牌无效或已撤销", status=401, code="token_invalid")
        if float(record["expires_at"]) < time.time():
            raise ApiError(
                f"令牌已过期（有效期 {config.TOKEN_TTL_DAYS} 天）", status=401, code="token_expired"
            )
        self.db.touch_token(digest)
        return {"user_id": record["user_id"], "token_hash": digest}

    @staticmethod
    def require_identity(identity: dict[str, Any], claimed: Any, field: str) -> str:
        """FR-4.1.b：请求声明的身份必须等于 token 身份，否则 403。"""
        claimed_id = str(claimed or "").strip()
        if not claimed_id:
            raise ApiError(f"缺少 {field} 字段", code=f"missing_{'creator' if field == 'creator_id' else 'user'}")
        if claimed_id != identity["user_id"]:
            raise ApiError(
                f"{field} 与凭据身份不一致（拒绝越权冒用）", status=403, code="identity_mismatch"
            )
        return claimed_id

    # -- 视频 -----------------------------------------------------------
    def upload_video(self, multipart: media.ParsedMultipart, actor_id: str | None = None) -> dict[str, Any]:
        creator_id = (multipart.fields.get("creator_id") or "").strip()
        if not creator_id:
            raise ApiError("缺少 creator_id 字段", code="missing_creator")
        if actor_id is not None and creator_id != actor_id:
            # 纵深防御：HTTP 层已校验，业务层再校验一次（避免绕过 HTTP 层直接调用）
            raise ApiError("creator_id 与凭据身份不一致", status=403, code="identity_mismatch")
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
            # 契约（PRD §8.5，冻结）：409 必须回传**顶层 `video_id`**，客户端据此
            # 按"幂等成功"处理 —— 这是本 MVP 唯一的重试幂等机制。
            raise ApiError(
                f"视频已存在（去重命中 video_id={dup['id']}）",
                status=409,
                code="duplicate_video",
                extra={"video_id": dup["id"]},
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

    def add_engagement(self, payload: dict[str, Any], actor_id: str | None = None) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "")
        video_id = str(payload.get("video_id") or "")
        kind = str(payload.get("kind") or "")
        if kind not in self._KINDS:
            raise ApiError(f"kind 非法，允许 {sorted(self._KINDS)}", code="invalid_kind")
        if actor_id is not None and user_id != actor_id:
            raise ApiError("user_id 与凭据身份不一致", status=403, code="identity_mismatch")
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

    def add_follow(self, payload: dict[str, Any], actor_id: str | None = None) -> dict[str, Any]:
        follower = str(payload.get("follower_id") or "")
        followee = str(payload.get("followee_id") or "")
        if actor_id is not None and follower != actor_id:
            raise ApiError("follower_id 与凭据身份不一致", status=403, code="identity_mismatch")
        self.get_user(follower)
        self.get_user(followee)
        if follower == followee:
            raise ApiError("不能关注自己", code="self_follow")
        self.db.add_follow(follower, followee)
        return {"ok": True, "follower_id": follower, "followee_id": followee}

    # -- 推荐流 ---------------------------------------------------------
    def feed(self, query: dict[str, list[str]], actor_id: str | None = None) -> dict[str, Any]:
        user_id = (query.get("user_id") or [""])[0]
        if not user_id:
            raise ApiError("缺少 user_id 查询参数", code="missing_user_id")
        if actor_id is not None and user_id != actor_id:
            raise ApiError("user_id 与凭据身份不一致", status=403, code="identity_mismatch")
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
    def __init__(
        self,
        message: str,
        status: int = 400,
        code: str = "bad_request",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.extra = extra or {}   # 顶层附加字段（如 duplicate_video 的 video_id）


# ---------------------------------------------------------------------------
# HTTP 层
# ---------------------------------------------------------------------------
_VIDEO_FILE_RE = re.compile(r"^/api/videos/([0-9a-f]+)/file$")
_VIDEO_RE = re.compile(r"^/api/videos/([0-9a-f]+)$")
_USER_RE = re.compile(r"^/api/users/([0-9a-f]+)$")


class Handler(BaseHTTPRequestHandler):
    server_version = "SVP/0.2"
    protocol_version = "HTTP/1.1"
    app: Application  # 由 serve() 注入

    # -- 工具 -----------------------------------------------------------
    def _drain_body(self) -> bool:
        """确保请求体已被读完，返回 True 表示连接可以安全复用。

        HTTP/1.1 默认 keep-alive：若校验先于读取体失败（例如 Content-Type
        不对），残留字节会被当成下一个请求解析，导致连接错乱。

        四个必须避开的陷阱：
        1. 请求体已被 `_read_json()` 消费过时，再读会永久阻塞（等永远不会
           到来的字节）——因此用 `_body_consumed` 标记。
        2. 直接对 socket 调 `read(65536)` 在 keep-alive 下会阻塞——因此
           multipart 路径改用 `LengthLimitedReader` 显式限制读取长度。
        3. 在**读体之前**就被拒的请求（鉴权/限流/404）不能排空：客户端可能
           只发了请求头就停下（或声明了 Content-Length 却不再发送），排空会
           永久阻塞工作线程。此时直接放弃连接复用（`Connection: close`）。
        4. 即使需要排空，读取也必须带 socket 超时——慢速发送的客户端同样能
           把线程挂死（慢速攻击面）。
        """
        reader = getattr(self, "_body_reader", None)
        if reader is not None:
            return reader.drain()
        if getattr(self, "_body_consumed", False):
            return True
        if not getattr(self, "_body_started", False):
            return False   # 陷阱 3：读体之前被拒，不排空、直接关连接
        try:
            remaining = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            remaining = 0
        if remaining <= 0:
            self._body_consumed = True
            return True
        try:
            self.connection.settimeout(BODY_DRAIN_TIMEOUT)   # 陷阱 4
            while remaining > 0:
                chunk = self.rfile.read(min(1 << 16, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (socket.timeout, TimeoutError, OSError):
            return False
        finally:
            try:
                self.connection.settimeout(None)
            except OSError:
                pass
        self._body_consumed = True
        return remaining <= 0

    def _cors_headers(self) -> dict[str, str]:
        """FR-4.1.e：CORS 白名单驱动，**默认不为 `*`**。

        命中白名单才回显 Origin；未命中则完全不下发该头（浏览器自行拦截），
        比回显 `null` 更安全（`null` 会被部分浏览器当作通配）。
        """
        origin = self.headers.get("Origin") or ""
        if origin and origin in config.CORS_ORIGINS:
            return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
        return {"Vary": "Origin"}

    def _send_json(
        self,
        payload: Any,
        status: int = 200,
        close: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in self._cors_headers().items():
            self.send_header(key, value)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(
        self,
        message: str,
        status: int,
        code: str,
        close: bool = False,
        extra_headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        # 脱敏：错误消息绝不回显令牌（FR-4.1.f）
        payload: dict[str, Any] = {"error": {"code": code, "message": auth.redact(message)}}
        payload.update(extra or {})
        self._send_json(
            payload, status=status, close=close, extra_headers=extra_headers
        )

    def _query(self) -> dict[str, list[str]]:
        parsed = urllib.parse.urlparse(self.path)
        return urllib.parse.parse_qs(parsed.query)

    def _path(self) -> str:
        return urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._body_consumed = True
            self._body_started = True
            return {}
        if length > MAX_JSON_BODY:
            raise ApiError("JSON 请求体过大", status=413, code="payload_too_large")
        self._body_started = True
        raw = self.rfile.read(length)
        self._body_consumed = True
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError("请求体不是合法 JSON", code="invalid_json")
        if not isinstance(data, dict):
            raise ApiError("请求体必须是 JSON 对象", code="invalid_json_shape")
        return data

    # -- 鉴权 / 限流 -----------------------------------------------------
    def _identity(self, required: bool = True) -> dict[str, Any] | None:
        """解析并校验 Bearer 令牌；`required=False` 时缺失返回 None。"""
        token = auth.parse_bearer(self.headers.get("Authorization"))
        if not token:
            if required:
                return self.app.authenticate(None)
            return None
        return self.app.authenticate(token)

    def _require_admin(self) -> None:
        """管理端点：独立管理员凭据；未配置则 fail-closed。"""
        expected = config.ADMIN_TOKEN
        if not expected:
            raise ApiError(
                "管理端点未配置管理员凭据（SVP_ADMIN_TOKEN），已拒绝访问",
                status=403,
                code="admin_required",
            )
        provided = auth.parse_bearer(self.headers.get("Authorization")) or ""
        if not auth.tokens_equal(provided, expected):
            raise ApiError("需要管理员凭据", status=403, code="admin_required")

    def _check_rate_limit(self, endpoint_class: str, user_id: str | None) -> None:
        rules = config.RATE_LIMITS.get(endpoint_class, {})
        global_rules = None if endpoint_class == "health" else config.RATE_LIMITS.get("global")
        decision = self.app.limiter.check(
            endpoint_class,
            rules,
            user_id=user_id,
            client_ip=self.client_address[0] if self.client_address else "unknown",
            enabled=config.RATE_LIMIT_ENABLED,
            global_rules=global_rules,
        )
        if decision.allowed:
            return
        raise RateLimited(decision)

    def log_message(self, fmt: str, *args) -> None:  # 静默（由外层统一收集）
        if os.environ.get("SVP_HTTP_LOG"):
            super().log_message(auth.redact(fmt), *[auth.redact(a) for a in args])

    # -- 路由 -----------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        for key, value in self._cors_headers().items():
            self.send_header(key, value)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", config.CORS_ALLOWED_HEADERS)
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle_get(self) -> None:
        path = self._path()
        if path == "/api/health":
            self._check_rate_limit("health", None)   # 规则为空 + 豁免全局桶
            return self._send_json({"ok": True, "ts": time.time()})

        if path == "/api/feed":
            identity = self._identity(required=True)
            self._check_rate_limit("feed", identity["user_id"])
            return self._send_json(self.app.feed(self._query(), actor_id=identity["user_id"]))

        if path == "/api/videos":
            identity = self._identity(required=False)
            self._check_rate_limit("reads", (identity or {}).get("user_id"))
            return self._send_json({"videos": self.app.db.list_all_videos()})

        m = _VIDEO_FILE_RE.match(path)
        if m:
            identity = self._identity(required=False)
            self._check_rate_limit("reads", (identity or {}).get("user_id"))
            return self._serve_media(self.app.get_video(m.group(1)))

        m = _VIDEO_RE.match(path)
        if m:
            identity = self._identity(required=False)
            self._check_rate_limit("reads", (identity or {}).get("user_id"))
            return self._send_json(self.app.get_video(m.group(1)))

        m = _USER_RE.match(path)
        if m:
            identity = self._identity(required=True)
            self._check_rate_limit("reads", identity["user_id"])
            return self._send_json(self.app.get_user(m.group(1)))

        if path in ("/", "/index.html"):
            self._check_rate_limit("reads", None)
            return self._serve_home()

        self._send_error_json(f"未找到路由 {path}", 404, "not_found")

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._handle_get()
        except RateLimited as exc:
            self._send_error_json("请求过于频繁", 429, "rate_limited",
                                  extra_headers=exc.headers())
        except ApiError as exc:
            self._send_error_json(exc.message, exc.status, exc.code, extra=exc.extra)
        except media.UploadError as exc:
            self._send_error_json(exc.message, exc.status, exc.code)
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(f"服务内部错误: {exc}", 500, "internal_error")

    def do_POST(self) -> None:  # noqa: N802
        path = self._path()
        tmpdir = ""
        self._body_consumed = False
        self._body_reader = None
        self._body_started = False
        try:
            if path == "/api/users":
                self._check_rate_limit("users", None)
                return self._send_json(self.app.create_user(self._read_json()), 201)

            if path == "/api/sessions":
                self._check_rate_limit("sessions", None)
                return self._send_json(self.app.create_session(self._read_json()), 200)

            if path == "/api/sessions/revoke":
                identity = self._identity(required=True)
                self._check_rate_limit("sessions", identity["user_id"])
                self._read_json()
                return self._send_json(self.app.revoke_session(identity["token_hash"]))

            if path == "/api/videos":
                # 顺序是关键（FR-4.2.b / AC-A-01 / AC-A-05）：
                # 鉴权 -> 限流 -> 体积预检，三者都必须在**读取请求体之前**完成，
                # 否则保护对象（IO/磁盘）已经被消耗。
                identity = self._identity(required=True)
                self._check_rate_limit("video_upload", identity["user_id"])
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
                self._body_started = True
                reader = media.LengthLimitedReader(self.rfile, length)
                self._body_reader = reader
                parsed = media.parse_multipart(reader, ctype, config.MAX_UPLOAD_BYTES + (1 << 20))
                tmpdir = parsed.tmpdir
                creator = self.app.require_identity(
                    identity, parsed.fields.get("creator_id"), "creator_id"
                )
                return self._send_json(self.app.upload_video(parsed, actor_id=creator), 201)

            if path == "/api/engagements":
                identity = self._identity(required=True)
                self._check_rate_limit("engagements", identity["user_id"])
                payload = self._read_json()
                actor = self.app.require_identity(identity, payload.get("user_id"), "user_id")
                return self._send_json(self.app.add_engagement(payload, actor_id=actor), 201)

            if path == "/api/follows":
                identity = self._identity(required=True)
                self._check_rate_limit("follows", identity["user_id"])
                payload = self._read_json()
                actor = self.app.require_identity(identity, payload.get("follower_id"), "follower_id")
                return self._send_json(self.app.add_follow(payload, actor_id=actor), 201)

            if path.startswith("/api/admin/") or path.startswith("/api/internal/"):
                self._require_admin()
                self._check_rate_limit("admin", "admin")
                if path == "/api/admin/rebuild-cf":
                    self._read_json()
                    return self._send_json(self.app.rebuild_cf())
                return self._send_error_json(f"未找到路由 {path}", 404, "not_found")

            self._send_error_json(f"未找到路由 {path}", 404, "not_found")
        except RateLimited as exc:
            self._send_error_json("请求过于频繁", 429, "rate_limited",
                                  close=not self._drain_body(), extra_headers=exc.headers())
        except ApiError as exc:
            self._send_error_json(exc.message, exc.status, exc.code,
                                  close=not self._drain_body(), extra=exc.extra)
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
        for key, value in self._cors_headers().items():
            self.send_header(key, value)
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
            f"<p>视频总数：<b>{len(videos)}</b>。推荐流接口（需 <code>Authorization: Bearer &lt;token&gt;</code>）："
            "<code>GET /api/feed?user_id=&lt;uuid&gt;&amp;size=10</code></p>"
            "<p>令牌获取：<code>POST /api/users</code> 或 <code>POST /api/sessions {handle}</code>（开发级身份，"
            "<code>auth_level=dev</code>）。</p>"
            "<table><tr><th>ID</th><th>文案</th><th>标签</th><th>时长</th>"
            "<th>播放</th><th>点赞</th><th>创作者</th></tr>"
            f"{rows or '<tr><td colspan=7>暂无视频，请先调用 POST /api/videos 上传</td></tr>'}"
            "</table></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        for key, value in self._cors_headers().items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(html)


class RateLimited(Exception):
    """限流拒绝：由 HTTP 层翻译为 429 + 契约响应头（FR-4.2.a）。"""

    def __init__(self, decision: ratelimit.Decision) -> None:
        super().__init__("rate_limited")
        self.decision = decision

    def headers(self) -> dict[str, str]:
        dec = self.decision
        return {
            "Retry-After": str(dec.retry_after),
            "X-RateLimit-Limit": str(dec.limit),
            "X-RateLimit-Remaining": str(dec.remaining),
            "X-RateLimit-Reset": str(int(time.time() + dec.reset_after)),
            "X-RateLimit-Rule": dec.rule_key,
        }


def _esc(text: Any) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def serve(host: str = "127.0.0.1", port: int = 8080, app: Application | None = None) -> ThreadingHTTPServer:
    app = app or Application()
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd
