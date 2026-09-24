"""鉴权与限流的行为测试（PRD §5.3 / §5.4 的 AC-S-* / AC-A-* 对应用例）。

**为什么必须有这组测试**：鉴权与限流是"上线阻塞项"，它们的失效方式不是崩溃
而是**静默放行**（fail-open）——例如"少一个 Authorization 头也照样能上传"。
这类缺陷在功能测试里完全看不出来，只有把 401/403/429 钉成断言才守得住。

本组测试**刻意使用生产档限流**（与 `test_api.py` 的宽松测试档不同），
否则限流用例永远是绿的、等于没测。
"""

from __future__ import annotations

import copy
import json
import os
import secrets
import socket
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import auth, config  # noqa: E402
from tests.test_api import ApiServerCase  # noqa: E402

# 生产档限流（在 import 时深拷贝，避免被其他测试模块的宽松档污染）
PROD_RATE_LIMITS = copy.deepcopy(config.RATE_LIMITS)


class AuthCase(ApiServerCase):
    """通用基类：切回生产档限流，其余复用 HTTP 夹具。"""

    def setUp(self) -> None:
        super().setUp()
        config.RATE_LIMITS = PROD_RATE_LIMITS
        self.app.limiter.reset()

    # -- 工具 -------------------------------------------------------------
    def raw_headers_only(self, request_line: str, headers: dict[str, str]) -> bytes:
        """只发请求头、**不发请求体**，返回服务端首个响应包。

        用途：证明"鉴权/限流先于读取请求体"（AC-A-01 / AC-A-05 的硬要求）。
        若服务端先读体，它会阻塞等待永远不会到来的字节，这里就会超时。
        """
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        try:
            payload = request_line + "\r\n"
            payload += "".join(f"{k}: {v}\r\n" for k, v in headers.items())
            payload += "\r\n"
            sock.sendall(payload.encode())
            return sock.recv(65536)
        finally:
            sock.close()

    def bearer(self, token: str | None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"} if token else {}


# ---------------------------------------------------------------------------
# FR-3.1 账号与会话
# ---------------------------------------------------------------------------
class TestAccountsAndSessions(AuthCase):
    def test_register_returns_token_once_and_stores_only_hash(self):
        """AC-S-01 + FR-3.1.a：注册响应含 token；库里只有 sha256。"""
        status, data = self.post_json(
            "/api/users",
            {"handle": "creator_a1", "display": "林小厨",
             "interest_tags": ["美食", "旅行", "宠物"], "source": "seed_invite"},
        )
        self.assertEqual(status, 201, data)
        for field in ("id", "handle", "display", "created_at"):
            self.assertIn(field, data, f"{field} 字段必须保持不变（向后兼容）")
        self.assertTrue(data["token"])
        self.assertEqual(data["auth_level"], "dev")
        self.assertEqual(data["interest_tags"], ["美食", "旅行", "宠物"])

        row = self.db.get_token(auth.token_hash(data["token"]))
        self.assertIsNotNone(row, "令牌摘要应已落库")
        self.assertNotEqual(row["token_hash"], data["token"], "禁止存明文令牌")
        self.assertEqual(row["auth_level"], "dev")
        # 有效期 30 天（容差 60s）
        self.assertAlmostEqual(row["expires_at"] - row["created_at"], 30 * 86400, delta=60)

    def test_interest_tags_must_be_exactly_three_from_whitelist(self):
        status, data = self.post_json(
            "/api/users", {"handle": "bad_tags", "interest_tags": ["美食"]}
        )
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "invalid_interest_tags")

        status, data = self.post_json(
            "/api/users",
            {"handle": "bad_tags2", "interest_tags": ["美食", "旅行", "量子力学"]},
        )
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "invalid_interest_tags")
        self.assertIn("量子力学", data["error"]["message"])

    def test_get_user_never_returns_credential(self):
        """AC-S-04：查询用户不得回传令牌原文。"""
        uid = self.mkuser("profile_owner")
        status, data = self.get_json(f"/api/users/{uid}")
        self.assertEqual(status, 200, data)
        self.assertNotIn("token", data)
        self.assertNotIn("token_hash", data)

    def test_session_endpoint_issues_dev_level_token(self):
        """AC-S-05：`POST /api/sessions` 必须显式标注 auth_level=dev。"""
        self.mkuser("session_user")
        status, data = self.post_json("/api/sessions", {"handle": "session_user"},
                                      token=None)
        self.assertEqual(status, 200, data)
        self.assertEqual(data["auth_level"], "dev")
        self.assertIn("token", data)
        self.assertIn("expires_at", data)

        # 新令牌应可直接使用
        status, feed = self.get_json(f"/api/feed?user_id={data['user_id']}&size=1",
                                     token=data["token"])
        self.assertEqual(status, 200, feed)

    def test_session_for_unknown_handle_is_404(self):
        status, data = self.post_json("/api/sessions", {"handle": "nobody_here"}, token=None)
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "user_not_found")

    def test_revoke_makes_token_unusable(self):
        """FR-3.1.d：撤销后原令牌立即失效。"""
        uid = self.mkuser("revoker")
        token = self.tokens[uid]
        status, data = self.post_json("/api/sessions/revoke", {}, token=token)
        self.assertEqual(status, 200, data)

        status, data = self.get_json(f"/api/feed?user_id={uid}&size=1", token=token)
        self.assertEqual(status, 401)
        self.assertEqual(data["error"]["code"], "token_invalid")


# ---------------------------------------------------------------------------
# FR-4.1 鉴权
# ---------------------------------------------------------------------------
class TestBearerAuth(AuthCase):
    def test_write_without_authorization_is_401_before_body_read(self):
        """AC-A-01：缺 Authorization → 401，且**在读体之前**返回。"""
        # 1) 常规请求（会被读完体）也要 401
        status, data = self.post_json("/api/videos", {"caption": "no auth"}, token=None)
        self.assertEqual(status, 401)
        self.assertEqual(data["error"]["code"], "unauthenticated")

        # 2) 只发头、不发体：若服务端先读体就会阻塞，这里有响应即证前置
        raw = self.raw_headers_only(
            "POST /api/videos HTTP/1.1",
            {"Host": f"127.0.0.1:{self.port}", "Content-Type": "video/mp4",
             "Content-Length": "1000000"},
        )
        self.assertIn(b" 401 ", raw.split(b"\r\n")[0], f"应在读体前 401：{raw[:80]!r}")

    def test_identity_mismatch_is_403(self):
        """AC-A-02：拿自己的 token 冒充他人身份 → 403。"""
        a = self.mkuser("mimic_a")
        b = self.mkuser("mimic_b")
        status, data = self.post_json(
            "/api/engagements", {"user_id": b, "video_id": "0" * 8 + "0" * 0, "kind": "like"},
            token=self.tokens[a],
        )
        self.assertEqual(status, 403)
        self.assertEqual(data["error"]["code"], "identity_mismatch")

    def test_invalid_and_expired_tokens(self):
        """AC-A-03：无效 → token_invalid；过期 → token_expired。"""
        status, data = self.get_json("/api/feed?user_id=x", token="not-a-real-token")
        self.assertEqual(status, 401)
        self.assertEqual(data["error"]["code"], "token_invalid")

        uid = self.mkuser("expiry_user")
        expired = secrets.token_urlsafe(32)
        self.db.execute(
            """INSERT INTO user_tokens(token_hash, user_id, created_at, expires_at,
                                       last_seen_at, revoked, auth_level)
               VALUES(?,?,?,?,?,0,'dev')""",
            (auth.token_hash(expired), uid, time.time() - 40 * 86400,
             time.time() - 10 * 86400, time.time() - 10 * 86400),
        )
        status, data = self.get_json(f"/api/feed?user_id={uid}&size=1", token=expired)
        self.assertEqual(status, 401)
        self.assertEqual(data["error"]["code"], "token_expired")

    def test_public_reads_stay_open(self):
        """AC-A-04：`/api/health`、`GET /api/videos/{id}` 免鉴权。"""
        status, data = self.get_json("/api/health", token=None)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])

        creator = self.mkuser("public_creator")
        _, video = self.upload(creator, "公开视频", data=self.clip(0))
        status, data = self.get_json(f"/api/videos/{video['id']}", token=None)
        self.assertEqual(status, 200, data)
        self.assertEqual(data["id"], video["id"])

    def test_feed_requires_auth(self):
        status, data = self.get_json("/api/feed?user_id=" + "a" * 32, token=None)
        self.assertEqual(status, 401)
        self.assertEqual(data["error"]["code"], "unauthenticated")

    def test_admin_endpoint_requires_admin_credential(self):
        """AC-S-07 / AC-S-07b：非管理员 403；管理员 200。"""
        uid = self.mkuser("not_admin")
        status, data = self.post_json("/api/admin/rebuild-cf", {}, token=self.tokens[uid])
        self.assertEqual(status, 403)
        self.assertEqual(data["error"]["code"], "admin_required")

        status, data = self.post_json("/api/admin/rebuild-cf", {}, token=self.admin_token)
        self.assertEqual(status, 200, data)
        self.assertTrue(data["ok"])

    def test_admin_endpoint_fails_closed_without_configured_credential(self):
        """未配置 SVP_ADMIN_TOKEN 时必须**一律拒绝**，而不是放开。"""
        old = config.ADMIN_TOKEN
        config.ADMIN_TOKEN = ""
        try:
            status, data = self.post_json("/api/admin/rebuild-cf", {},
                                          token=self.admin_token)
            self.assertEqual(status, 403)
            self.assertEqual(data["error"]["code"], "admin_required")
        finally:
            config.ADMIN_TOKEN = old

    def test_error_responses_never_echo_token(self):
        """AC-A-09：错误响应不得回显令牌（脱敏为 ***）。"""
        secret_token = secrets.token_urlsafe(32)
        status, data = self.get_json("/api/feed?user_id=x", token=secret_token)
        self.assertEqual(status, 401)
        self.assertNotIn(secret_token, json.dumps(data, ensure_ascii=False))

        # 纯函数层面：Bearer 头与密钥字段都必须被脱敏
        self.assertEqual(auth.redact(f"Authorization: Bearer {secret_token}"),
                         "Authorization: Bearer ***")
        self.assertIn("***", auth.redact(f"token={secret_token}"))
        # 反向要求：hex 形态的 video_id/sha256 不得被误伤（否则污染用户可见消息）
        self.assertIn("a" * 32, auth.redact(f"video_id={'a' * 32}"))

    def _options_headers(self, origin: str) -> dict[str, str]:
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("OPTIONS", "/api/videos", headers={"Origin": origin})
            resp = conn.getresponse()
            resp.read()
            return {k.lower(): v for k, v in resp.getheaders()}
        finally:
            conn.close()

    def test_cors_is_whitelist_driven(self):
        """FR-4.1.e：CORS 白名单驱动，默认不放开 `*`。"""
        allowed = config.CORS_ORIGINS[0]
        headers = self._options_headers(allowed)
        self.assertEqual(headers.get("access-control-allow-origin"), allowed)
        self.assertIn("Authorization", headers.get("access-control-allow-headers") or "")

        denied = self._options_headers("https://evil.example")
        self.assertIsNone(denied.get("access-control-allow-origin"),
                          "白名单外来源不得下发 CORS 头")


# ---------------------------------------------------------------------------
# FR-4.2 限流
# ---------------------------------------------------------------------------
class TestRateLimit(AuthCase):
    def test_sixth_upload_in_a_minute_is_429_before_body_read(self):
        """AC-A-05：1 分钟内第 6 次上传 → 429 + Retry-After + 三个 X-RateLimit 头。"""
        creator = self.mkuser("upload_limiter")
        token = self.tokens[creator]
        for i in range(5):
            status, data = self.upload(creator, f"限流测试 {i}", data=self.clip(i))
            self.assertEqual(status, 201, data)

        status, data = self.post_json("/api/videos", {"creator_id": creator})
        self.assertEqual(status, 429)
        self.assertEqual(data["error"]["code"], "rate_limited")

        # 只发头不发体：限流必须先于读体
        raw = self.raw_headers_only(
            "POST /api/videos HTTP/1.1",
            {"Host": f"127.0.0.1:{self.port}",
             "Content-Type": f"multipart/form-data; boundary={'x' * 8}",
             "Content-Length": "500000",
             "Authorization": f"Bearer {token}"},
        )
        head = raw.split(b"\r\n")[0]
        self.assertIn(b" 429 ", head, f"第 6 次上传应在读体前被拒：{head!r}")
        lowered = raw.lower()
        for header in (b"retry-after", b"x-ratelimit-limit", b"x-ratelimit-remaining",
                       b"x-ratelimit-reset"):
            self.assertIn(header, lowered, f"429 契约缺响应头 {header!r}")

    def test_registration_is_rate_limited_per_ip(self):
        """AC-A-07：同一 IP 1 小时内第 6 次注册 → 429（防批量注册）。"""
        for i in range(5):
            status, data = self.post_json("/api/users", {"handle": f"bulk_{i}"}, token=None)
            self.assertEqual(status, 201, data)
        status, data = self.post_json("/api/users", {"handle": "bulk_5"}, token=None)
        self.assertEqual(status, 429)
        self.assertEqual(data["error"]["code"], "rate_limited")

    def test_health_is_exempt_from_rate_limit(self):
        """FR-4.2.d：探活接口不限流（否则监控会把服务探死）。"""
        for _ in range(200):
            status, _data = self.get_json("/api/health", token=None)
            self.assertEqual(status, 200)

    def test_limiter_disabled_switch(self):
        """`SVP_RATE_LIMIT=0`（config.RATE_LIMIT_ENABLED=False）时放行 —— 仅限本地调试。"""
        old = config.RATE_LIMIT_ENABLED
        config.RATE_LIMIT_ENABLED = False
        try:
            self.app.limiter.reset()
            for i in range(12):
                status, data = self.post_json("/api/users", {"handle": f"nolimit_{i}"},
                                              token=None)
                self.assertEqual(status, 201, data)
        finally:
            config.RATE_LIMIT_ENABLED = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
