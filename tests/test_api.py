"""端到端 HTTP 测试：真实起服务，走完整"注册 -> 上传 -> 互动 -> 推荐流"链路。

这是本项目最重要的一组测试——它证明 MVP 的核心功能（视频上传 + 推荐流）
在真实 HTTP 协议下可用，而不只是在单元层面成立。

**鉴权契约（FR-3/FR-4）下的写法**：`mkuser()` 通过 HTTP 注册用户并**记住其
token**，同时把该用户设为"当前身份"；之后的请求默认带上它的 `Authorization`
头。需要无凭据请求时显式传 `token=None`。测试档限流被放宽（逐端点限流行为
由 `tests/test_auth.py` 用严格档覆盖），以免用例互相挤占额度。
"""

from __future__ import annotations

import http.client
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
import uuid
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import config  # noqa: E402
from server.app import Application, serve  # noqa: E402
from server.db import Database  # noqa: E402
from tests.test_media import BOUNDARY, build_multipart, make_real_mp4  # noqa: E402

_NO_TOKEN = object()          # 哨兵：区分"用当前身份"与"显式不带凭据"
_BIG = 100000                 # 测试档限流容量（等价于"不限流"）

# 测试档：按生产配置的**形状**生成宽松额度，避免用例互相挤占令牌桶。
# 这里刻意不写死端点名，生产新增/改名端点时测试档自动跟随。
TEST_RATE_LIMITS = {
    name: {key: (_BIG, window) for key, (_limit, window) in rules.items()}
    for name, rules in config.RATE_LIMITS.items()
}


class ApiServerCase(unittest.TestCase):
    """起一个真实 HTTP 服务，端口由系统分配（port=0）。"""

    # 预先合成 12 段不同时长的真实 mp4。
    # 为什么必须不同：上传接口按 sha256 去重，若夹具复用同一份字节，第 2 条
    # 起都会 409，正常路径根本走不到，测试会"假通过"。
    # 用极低帧率（4fps）控制合成耗时——目标是字节差异与时长元数据，不是画质。
    clips: list[bytes] = []

    @classmethod
    def setUpClass(cls) -> None:
        cls.clips = [
            make_real_mp4(duration_s=2.0 + i, size="320x480", fps=4) for i in range(12)
        ]

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        self._old_media = config.MEDIA_ROOT
        self._old_limits = config.RATE_LIMITS
        self._old_admin = config.ADMIN_TOKEN
        config.DB_PATH = os.path.join(self.tmp.name, "api.db")
        config.MEDIA_ROOT = os.path.join(self.tmp.name, "media")
        config.RATE_LIMITS = TEST_RATE_LIMITS
        # 管理员凭据：运行时生成，**不得在代码里写死任何密钥**
        self.admin_token = secrets.token_urlsafe(24)
        config.ADMIN_TOKEN = self.admin_token

        self.tokens: dict[str, str] = {}
        self.actor: str | None = None

        self.db = Database(config.DB_PATH)
        self.app = Application(self.db)
        self.httpd = serve("127.0.0.1", 0, self.app)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.db.close()
        config.DB_PATH = self._old_db
        config.MEDIA_ROOT = self._old_media
        config.RATE_LIMITS = self._old_limits
        config.ADMIN_TOKEN = self._old_admin
        self.tmp.cleanup()

    # -- HTTP 工具 --------------------------------------------------------
    def request(self, method: str, path: str, body: bytes | None = None,
                ctype: str = "application/json", token: Any = _NO_TOKEN,
                extra_headers: dict[str, str] | None = None) -> tuple[int, dict | bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        headers: dict[str, str] = dict(extra_headers or {})
        if token is _NO_TOKEN:
            token = self.tokens.get(self.actor or "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            headers["Content-Type"] = ctype
            headers["Content-Length"] = str(len(body))
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        status = resp.status
        conn.close()
        if (resp.getheader("Content-Type") or "").startswith("application/json"):
            return status, json.loads(raw.decode("utf-8"))
        return status, raw

    def post_json(self, path: str, payload: dict, token: Any = _NO_TOKEN) -> tuple[int, dict]:
        return self.request(  # type: ignore[return-value]
            "POST", path, json.dumps(payload).encode("utf-8"), token=token
        )

    def get_json(self, path: str, token: Any = _NO_TOKEN) -> tuple[int, dict]:
        return self.request("GET", path, token=token)  # type: ignore[return-value]

    def clip(self, i: int = 0) -> bytes:
        return self.clips[i % len(self.clips)]

    # -- 造数 -------------------------------------------------------------
    def mkuser(self, handle: str, **extra: Any) -> str:
        """注册用户并把其设为当前身份；返回 user_id。"""
        status, data = self.post_json("/api/users", {"handle": handle, **extra})
        self.assertEqual(status, 201, data)
        self.tokens[data["id"]] = data["token"]
        self.actor = data["id"]
        return data["id"]

    def list_videos(self) -> list[dict]:
        status, data = self.get_json("/api/videos")
        self.assertEqual(status, 200, data)
        return data["videos"]

    def upload(self, creator_id: str, caption: str, tags: str = "", data: bytes | None = None,
               filename: str = "clip.mp4", mime: str = "video/mp4",
               token: Any = _NO_TOKEN) -> tuple[int, dict]:
        body = build_multipart(
            {"creator_id": creator_id, "caption": caption, "tags": tags},
            [("file", filename, mime, data if data is not None else self.clip(0))],
        )
        if token is _NO_TOKEN:
            token = self.tokens.get(creator_id)
        return self.request(  # type: ignore[return-value]
            "POST", "/api/videos", body, f"multipart/form-data; boundary={BOUNDARY}", token=token
        )


# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------
class TestHealth(ApiServerCase):
    def test_health(self):
        status, data = self.get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])


class TestUsers(ApiServerCase):
    def test_create_and_get_user(self):
        uid = self.mkuser("alice")
        status, data = self.get_json(f"/api/users/{uid}")
        self.assertEqual(status, 200)
        self.assertEqual(data["handle"], "alice")

    def test_duplicate_handle_conflicts(self):
        self.mkuser("dup")
        status, data = self.post_json("/api/users", {"handle": "dup"})
        self.assertEqual(status, 409)
        self.assertEqual(data["error"]["code"], "handle_taken")

    def test_invalid_handle_rejected(self):
        status, data = self.post_json("/api/users", {"handle": "!"})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "invalid_handle")

    def test_missing_user_returns_404(self):
        self.mkuser("probe_reads")   # 读接口需凭据（FR-4.1.c）
        status, data = self.get_json(f"/api/users/{uuid.uuid4().hex}")
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "user_not_found")

    def test_connection_reusable_after_error_response(self):
        """回归测试：错误响应不得破坏 keep-alive 连接。

        历史缺陷：请求体已被 `_read_json` 消费后，错误分支又调用排空逻辑去读
        Content-Length 字节，导致永久阻塞（死锁）。也验证残留字节不会被当成
        下一个请求解析。
        """
        self.mkuser("keepalive")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            # 第 1 个请求：重复 handle，服务端在读体之后才报 409
            body = json.dumps({"handle": "keepalive"}).encode()
            conn.request("POST", "/api/users", body=body,
                         headers={"Content-Type": "application/json",
                                  "Content-Length": str(len(body))})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 409)
            resp.read()

            # 第 2 个请求：复用同一条连接，必须仍然可用
            conn.request("GET", "/api/health")
            resp2 = conn.getresponse()
            self.assertEqual(resp2.status, 200)
            self.assertTrue(json.loads(resp2.read().decode())["ok"])
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 视频上传（MVP 核心功能 1）
# ---------------------------------------------------------------------------
class TestVideoUpload(ApiServerCase):
    def test_upload_real_mp4_extracts_metadata_via_ffprobe(self):
        c = self.mkuser("creator")
        status, video = self.upload(c, "我的第一个短视频 #美食 #旅行", data=self.clip(0))
        self.assertEqual(status, 201, video)
        self.assertEqual(video["caption"], "我的第一个短视频 #美食 #旅行")
        self.assertEqual(sorted(video["tags"]), ["旅行", "美食"])
        # 元数据必须来自 ffprobe 真值，而非客户端上报
        self.assertAlmostEqual(video["duration_ms"] / 1000.0, 2.0, delta=0.5)
        self.assertEqual(video["width"], 320)
        self.assertEqual(video["height"], 480)
        self.assertTrue(os.path.isfile(video["storage_path"]), "视频文件应已落盘")
        self.assertEqual(len(video["sha256"]), 64)

    def test_upload_twice_is_rejected_as_duplicate(self):
        c = self.mkuser("creator2")
        s1, v1 = self.upload(c, "重复测试", data=self.clip(1))
        self.assertEqual(s1, 201)
        s2, data = self.upload(c, "重复测试", data=self.clip(1))
        self.assertEqual(s2, 409)
        self.assertEqual(data["error"]["code"], "duplicate_video")
        self.assertIn(v1["id"], data["error"]["message"])
        # 冻结契约（PRD §8.5）：顶层 video_id 必须回传，客户端按幂等成功处理
        self.assertEqual(data["video_id"], v1["id"])

    def test_upload_rejects_oversize_duration(self):
        """400 秒视频超过 180 秒短视频上限，必须被拒绝。

        用 1fps 编码长时长样本，避免测试变慢（目标是时长元数据，不是画质）。
        """
        long_clip = make_real_mp4(duration_s=200.0, size="320x240", fps=1)
        c = self.mkuser("creator3")
        status, data = self.upload(c, "超长视频", data=long_clip)
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "duration_too_long")

    def test_upload_rejects_non_video_payload(self):
        c = self.mkuser("creator4")
        status, data = self.upload(c, "假视频", data=b"this is not a video" * 200)
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "unprobeable_media")

    def test_upload_rejects_bad_extension(self):
        c = self.mkuser("creator5")
        status, data = self.upload(c, "扩展名错误", filename="clip.avi")
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "unsupported_extension")

    def test_upload_requires_existing_creator(self):
        """身份校验优先于存在性校验（FR-4.1.b）。

        契约变更说明：鉴权上线前，用任意（不存在的）creator_id 上传会走到
        `user_not_found` 404；上线后必须先通过身份一致性校验 —— 用别人的 id
        上传是**越权冒用**，语义上就该是 403 而非 404（404 还会泄露"该用户是否
        存在"）。不存在用户的 404 仍有覆盖：见下方 deleted-user 用例与
        `GET /api/users/{id}` 的 404 用例。
        """
        self.mkuser("creator_owner")
        status, data = self.upload(uuid.uuid4().hex, "冒用他人身份上传",
                                   token=self.tokens[self.actor])
        self.assertEqual(status, 403)
        self.assertEqual(data["error"]["code"], "identity_mismatch")

    def test_upload_with_token_of_deleted_user_is_rejected(self):
        """凭据对应用户已被删除 → 401（fail-closed，不得凭残留 token 上传）。"""
        ghost = self.mkuser("ghost_creator")
        self.db.execute("DELETE FROM users WHERE id=?", (ghost,))
        status, data = self.upload(ghost, "幽灵用户上传")
        self.assertEqual(status, 401)
        self.assertEqual(data["error"]["code"], "token_invalid")

    def test_upload_rejects_plain_json_body(self):
        self.mkuser("jsonbody")
        status, data = self.post_json("/api/videos", {"caption": "no file"})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "bad_content_type")

    def test_media_stream_serves_bytes_and_supports_range(self):
        c = self.mkuser("creator6")
        _, video = self.upload(c, "流媒体测试", data=self.clip(2))
        status, body = self.request("GET", f"/api/videos/{video['id']}/file")
        self.assertEqual(status, 200)
        self.assertEqual(len(body), video["size_bytes"])

        # 带 Range 的请求应返回 206 + Content-Range
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("GET", f"/api/videos/{video['id']}/file", headers={"Range": "bytes=0-99"})
        resp = conn.getresponse()
        chunk = resp.read()
        self.assertEqual(resp.status, 206)
        self.assertEqual(len(chunk), 100)
        self.assertIn("bytes 0-99/", resp.getheader("Content-Range") or "")
        conn.close()


# ---------------------------------------------------------------------------
# 推荐流（MVP 核心功能 2）
# ---------------------------------------------------------------------------
class TestFeedApi(ApiServerCase):
    # 创作者 A：观众会看完全部，用于制造兴趣画像与"已看"历史
    CATALOG_A = [
        ("美食探店", "美食"), ("家常菜教程", "美食"), ("宠物日常", "宠物"),
        ("旅行vlog", "旅行"), ("健身打卡", "健身"), ("读书笔记", "读书"),
    ]
    # 创作者 B：观众从未看过，用于验证"个性化排序"而非"已看过滤"
    CATALOG_B = [
        ("深夜食堂番外 #美食", "美食"), ("空气炸锅食谱 #美食", "美食"), ("猫咪打呼 #宠物", "宠物"),
    ]

    def _populate(self) -> dict[str, list[dict]]:
        """两个创作者各上传一批互不相同的视频，返回 {'a': [...], 'b': [...]}。"""
        out: dict[str, list[dict]] = {}
        for key, handle, catalog, offset in (
            ("a", "feed_creator_a", self.CATALOG_A, 0),
            ("b", "feed_creator_b", self.CATALOG_B, 6),
        ):
            creator = self.mkuser(handle)
            videos = []
            for i, (cap, tag) in enumerate(catalog):
                status, v = self.upload(creator, cap, tag, data=self.clip(offset + i))
                self.assertEqual(status, 201, v)
                videos.append(v)
            out[key] = videos
        return out

    def test_feed_returns_cold_start_for_new_user(self):
        self._populate()
        u = self.mkuser("brand_new")
        status, data = self.get_json(f"/api/feed?user_id={u}&size=5")
        self.assertEqual(status, 200, data)
        self.assertTrue(data["cold_start"])
        self.assertEqual(data["size"], 5)
        self.assertIn("weight_version", data)

    def test_feed_requires_user_id(self):
        self.mkuser("feed_no_id")   # 未鉴权会在参数校验之前被 401 拦下
        status, data = self.get_json("/api/feed")
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "missing_user_id")

    def test_feed_404_for_unknown_user(self):
        """契约变更：查询他人 user_id 属越权冒用 → 403；未知用户的 404 落在业务层。"""
        mine = self.mkuser("feed_self")
        status, data = self.get_json(f"/api/feed?user_id={uuid.uuid4().hex}")
        self.assertEqual(status, 403)
        self.assertEqual(data["error"]["code"], "identity_mismatch")

        # 业务层仍必须对不存在的用户返回 404（绕过 HTTP 鉴权直达 Application）
        from server.app import ApiError

        with self.assertRaises(ApiError) as ctx:
            self.app.feed({"user_id": [uuid.uuid4().hex]})
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(ctx.exception.code, "user_not_found")
        self.assertTrue(mine)

    def test_feed_respects_size_parameter(self):
        self._populate()
        u = self.mkuser("sizer")
        for size in (1, 3, 4):
            _, data = self.get_json(f"/api/feed?user_id={u}&size={size}")
            self.assertEqual(len(data["items"]), size, f"size={size} 应返回同等条数")

    def test_feed_is_personalized_by_liked_tags(self):
        """点赞"美食"后，未看过的美食视频应排在未看过的宠物视频之前。"""
        clips = self._populate()
        u = self.mkuser("foodie")
        a_videos = clips["a"]

        # 对 A 的美食视频表达强兴趣（like 权重 3，显著高于 view 的 1）
        food_ids = {v["id"] for v in a_videos if "美食" in v["tags"]}
        self.assertEqual(len(food_ids), 2)
        for vid in food_ids:
            self.post_json("/api/engagements", {"user_id": u, "video_id": vid, "kind": "like"})
        # 其余 A 视频只看一眼，凑够行为数脱离冷启动
        for v in a_videos:
            if v["id"] not in food_ids:
                self.post_json("/api/engagements",
                               {"user_id": u, "video_id": v["id"], "kind": "view", "watch_ms": 800})

        status, data = self.get_json(f"/api/feed?user_id={u}&size=10&seed=7")
        self.assertEqual(status, 200, data)
        self.assertFalse(data["cold_start"])

        items = data["items"]
        self.assertGreater(len(items), 0, "B 的内容未被看过，feed 不应为空")
        # A 的内容在 7 天窗口内已看，必须全部过滤
        for item in items:
            self.assertNotIn(item["video_id"], {v["id"] for v in a_videos})

        # 个性化：美食（被点赞，权重 3）应显著强于宠物（仅被看过，权重 1）
        food_items = [i for i in items if "美食" in i["tags"]]
        pet_items = [i for i in items if "宠物" in i["tags"]]
        self.assertTrue(food_items)
        self.assertTrue(pet_items)
        self.assertGreater(food_items[0]["features"]["aff"], 0.0)
        self.assertGreater(
            food_items[0]["features"]["aff"], pet_items[0]["features"]["aff"],
            "被点赞的标签应比仅浏览过的标签获得更高兴趣权重",
        )
        self.assertGreater(
            food_items[0]["score"], pet_items[0]["score"],
            "有更强标签兴趣的内容应获得更高总分",
        )
        self.assertIn("美食", items[0]["tags"], "首位应是命中所喜标签的内容")

    def test_feed_does_not_repeat_seen_videos(self):
        clips = self._populate()
        u = self.mkuser("seen_user")
        seen = clips["a"][0]["id"]
        self.post_json("/api/engagements", {"user_id": u, "video_id": seen, "kind": "view"})
        _, data = self.get_json(f"/api/feed?user_id={u}&size=10&seed=8")
        self.assertNotIn(seen, [i["video_id"] for i in data["items"]])

    def test_feed_items_explain_scores(self):
        self._populate()
        u = self.mkuser("explain")
        _, data = self.get_json(f"/api/feed?user_id={u}&size=2")
        item = data["items"][0]
        self.assertEqual(set(item["features"]), {"aff", "pop", "fresh", "social", "qual"})
        self.assertIn("reason", item)
        self.assertTrue(item["recall_routes"])
        self.assertAlmostEqual(
            item["score"],
            round(
                0.45 * item["features"]["aff"] + 0.20 * item["features"]["pop"]
                + 0.15 * item["features"]["fresh"] + 0.10 * item["features"]["social"]
                + 0.10 * item["features"]["qual"],
                6,
            ),
            places=5,
        )

    def test_feed_is_deterministic_given_seed(self):
        self._populate()
        u = self.mkuser("det")
        _, a = self.get_json(f"/api/feed?user_id={u}&size=5&seed=42")
        _, b = self.get_json(f"/api/feed?user_id={u}&size=5&seed=42")
        self.assertEqual([i["video_id"] for i in a["items"]],
                         [i["video_id"] for i in b["items"]])


# ---------------------------------------------------------------------------
# 互动与关注
# ---------------------------------------------------------------------------
class TestEngagementsApi(ApiServerCase):
    def test_engagement_updates_stats(self):
        c = self.mkuser("creator_eng")
        u = self.mkuser("viewer_eng")
        _, v = self.upload(c, "互动测试", data=self.clip(0))
        for kind in ("view", "complete", "like"):
            status, data = self.post_json(
                "/api/engagements", {"user_id": u, "video_id": v["id"], "kind": kind, "watch_ms": 2000}
            )
            self.assertEqual(status, 201, data)
        status, data = self.post_json(
            "/api/engagements", {"user_id": u, "video_id": v["id"], "kind": "like"}
        )
        self.assertEqual(data["stats"]["views"], 1)
        self.assertEqual(data["stats"]["completes"], 1)
        self.assertEqual(data["stats"]["likes"], 2)

    def test_invalid_kind_rejected(self):
        c = self.mkuser("creator_kind"); u = self.mkuser("viewer_kind")
        _, v = self.upload(c, "x", data=self.clip(1))
        status, data = self.post_json(
            "/api/engagements", {"user_id": u, "video_id": v["id"], "kind": "punch"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "invalid_kind")

    def test_follow_engagement_creates_follow_edge(self):
        c = self.mkuser("creator_follow"); u = self.mkuser("follower_x")
        _, v = self.upload(c, "关注测试", data=self.clip(2))
        self.post_json("/api/engagements", {"user_id": u, "video_id": v["id"], "kind": "follow"})
        self.assertIn(c, self.db.following_ids(u))

    def test_follow_endpoint_and_social_feature(self):
        c = self.mkuser("creator_social"); u = self.mkuser("follower_y")
        _, v = self.upload(c, "社交信号", data=self.clip(3))
        status, _ = self.post_json("/api/follows", {"follower_id": u, "followee_id": c})
        self.assertEqual(status, 201)
        _, data = self.get_json(f"/api/feed?user_id={u}&size=5&seed=9")
        top = data["items"][0]
        self.assertEqual(top["video_id"], v["id"])
        self.assertEqual(top["features"]["social"], 1.0)

    def test_self_follow_rejected(self):
        u = self.mkuser("narcissus")
        status, data = self.post_json("/api/follows", {"follower_id": u, "followee_id": u})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "self_follow")


# ---------------------------------------------------------------------------
# 协同过滤重建
# ---------------------------------------------------------------------------
class TestCfRebuildApi(ApiServerCase):
    def test_rebuild_builds_similarity_pairs(self):
        c = self.mkuser("cf_creator")
        _, v1 = self.upload(c, "美食A", "美食", data=self.clip(0))
        _, v2 = self.upload(c, "美食B", "美食", data=self.clip(1))
        for i in range(3):
            u = self.mkuser(f"cf_user{i}")
            for v in (v1, v2):
                self.post_json("/api/engagements",
                               {"user_id": u, "video_id": v["id"], "kind": "view"})
        status, data = self.post_json("/api/admin/rebuild-cf", {}, token=self.admin_token)
        self.assertEqual(status, 200, data)
        self.assertGreater(data["item_sim_pairs"], 0)
        sims = self.db.item_similarity([v1["id"]])
        self.assertIn(v2["id"], dict(sims[v1["id"]]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
