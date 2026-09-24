"""探索位（ε-greedy）的**行为**测试 —— AC-F-08 / AC-F-08b / AC-F-08c。

为什么单独一组、且必须断言"行为发生"：
历史缺陷 G1 里，`is_exploration` 字段**恒为 False**（计算了 explore_slots 却
从未使用），而 86 项回归测试全绿 —— 因为它们只断言了响应"形状"（字段存在、
条数正确），从没断言"探索位真的被投放"。字段存在 ≠ 行为发生。

因此这里断言的是可证伪的行为：
1. 命中探索分支时，**恰好 1 条** `is_exploration=true`，且索引 ≥ 3；
2. 该条必须是"低曝光分位"的候选，且原本不在 top-size 内；
3. 无合格候选时**不注入**（宁缺毋滥），feed 长度不受影响；
4. 1000 个 seed 下注入率 ≈ ε（0.10）；
5. 冷启动用户不注入。

⚠️ 曝光口径：真正的曝光量（`FeedImpression`）尚未实现（PRD M1），此处以
`views` 作为代理口径 —— 测试随之断言 views 分位，M1 落地后需同步更新用例。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import config  # noqa: E402
from server.db import Database  # noqa: E402
from server.recommend import RecommendEngine  # noqa: E402

TAIL_TAG = "冷门垂类"
POPULAR_VIEWS = 100


class ExplorationCase(unittest.TestCase):
    """构造"热门 + 低曝光长尾"两段分布的内容库。"""

    POPULAR_CREATORS = 6
    POPULAR_PER_CREATOR = 5
    TAIL_CREATORS = 2
    TAIL_PER_CREATOR = 5
    FEED_SIZE = 10

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "exp.db"))
        self.engine = RecommendEngine(self.db)
        self.popular_ids: list[str] = []
        self.tail_ids: list[str] = []
        self._build_library(views_for_popular=POPULAR_VIEWS, views_for_tail=0)

    def tearDown(self) -> None:
        self.db.close()
        self.tmp.cleanup()

    # -- 造数 -------------------------------------------------------------
    def _mkvideo(self, creator: str, tags: list[str], views: int, age_hours: float) -> str:
        vid = uuid.uuid4().hex
        self.db.create_video(
            video_id=vid, creator_id=creator, caption=f"video-{vid[:6]}", tags=tags,
            duration_ms=5000, width=480, height=854, size_bytes=1000,
            sha256=vid, storage_path=f"var/media/{vid}.mp4",
        )
        # 直接落统计数据与创建时间（本组测重排行为，不走 HTTP 上传链路）
        self.db.execute(
            """UPDATE video_stats SET views=?, completes=?, likes=?, shares=?, updated_at=?
               WHERE video_id=?""",
            (views, int(views * 0.6), int(views * 0.25), 0, time.time(), vid),
        )
        self.db.execute("UPDATE videos SET created_at=? WHERE id=?",
                        (time.time() - age_hours * 3600.0, vid))
        return vid

    def _mkuser(self, handle: str) -> str:
        uid = uuid.uuid4().hex
        self.db.create_user(uid, handle)
        return uid

    def _build_library(self, *, views_for_popular: int, views_for_tail: int) -> None:
        popular_creators = [self._mkuser(f"pc{i}") for i in range(self.POPULAR_CREATORS)]
        tail_creators = [self._mkuser(f"tc{i}") for i in range(self.TAIL_CREATORS)]
        for creator in popular_creators:
            for _ in range(self.POPULAR_PER_CREATOR):
                self.popular_ids.append(
                    self._mkvideo(creator, ["美食"], views_for_popular, age_hours=1.0)
                )
        for creator in tail_creators:
            for _ in range(self.TAIL_PER_CREATOR):
                self.tail_ids.append(
                    self._mkvideo(creator, [TAIL_TAG], views_for_tail, age_hours=200.0)
                )

    def _swap_to_fresh_db(self) -> None:
        """换一个空库（用于构造与 setUp 不同的曝光分布），并清空 id 台账。"""
        self.db.close()
        self.db = Database(os.path.join(self.tmp.name, f"exp-{uuid.uuid4().hex[:8]}.db"))
        self.engine = RecommendEngine(self.db)
        self.popular_ids.clear()
        self.tail_ids.clear()

    def _active_user(self, handle: str = "active_viewer") -> str:
        """造一个**非冷启动**用户：行为数 ≥ COLD_START_MAX_ENGAGEMENTS。"""
        uid = self._mkuser(handle)
        now = time.time()
        for vid in self.popular_ids[:4]:
            self.db.add_engagement(uid, vid, "view", watch_ms=3000, created_at=now)
        return uid

    # -- 断言工具 ---------------------------------------------------------
    def _feed(self, user_id: str, seed: int, size: int | None = None) -> dict:
        return self.engine.feed(user_id, size=size or self.FEED_SIZE, seed=seed)

    def _first_injecting_seed(self, user_id: str, limit: int = 300) -> tuple[int, dict]:
        for seed in range(limit):
            result = self._feed(user_id, seed)
            if result["exploration_injected"]:
                return seed, result
        self.fail(f"前 {limit} 个 seed 均未注入探索位 —— ε-greedy 未生效（G1 回归）")


class TestExplorationInjection(ExplorationCase):
    def test_injects_exactly_one_exploration_item_at_index_at_least_three(self):
        """AC-F-08：恰好 1 条、索引 ≥ 3、来自低曝光候选、feed 长度不变。"""
        user = self._active_user()
        seed, result = self._first_injecting_seed(user)
        items = result["items"]

        flagged = [i for i, item in enumerate(items) if item["is_exploration"]]
        self.assertEqual(len(flagged), 1, f"seed={seed} 应恰好注入 1 条探索位：{flagged}")
        index = flagged[0]
        self.assertGreaterEqual(index, 3, "探索位必须注入在第 3 位之后（前 3 位保持纯相关性）")
        self.assertEqual(len(items), self.FEED_SIZE, "探索位是**替换**一个位置，不得改变 feed 长度")

        explore = items[index]
        self.assertIn(explore["video_id"], self.tail_ids,
                      "探索项必须来自低曝光分位（此处代理口径为 views < 全站 P30）")
        self.assertIn("探索位", explore["reason"], "探索位必须可归因（排序理由需解释）")
        # 替换语义：被探索项顶掉的是一条普通推荐，探索项自身不得重复出现
        ids = [i["video_id"] for i in items]
        self.assertEqual(ids.count(explore["video_id"]), 1, "探索项不得重复出现")
        self.assertTrue(all(not i["is_exploration"] for i in items[:3]),
                        "前 3 位必须保持纯相关性")

    def test_no_injection_when_no_low_exposure_candidate(self):
        """AC-F-08b：全部候选都高曝光 → 不注入，且 feed 长度不受影响。"""
        self._swap_to_fresh_db()
        self._build_library(views_for_popular=POPULAR_VIEWS, views_for_tail=POPULAR_VIEWS)
        user = self._active_user()

        for seed in range(50):
            result = self._feed(user, seed)
            flags = [i for i in result["items"] if i["is_exploration"]]
            self.assertEqual(flags, [], f"seed={seed} 无合格候选却注入了探索位")
            self.assertFalse(result["exploration_injected"])
            self.assertEqual(len(result["items"]), self.FEED_SIZE, "feed 长度不得受影响")

    def test_cold_start_users_never_get_exploration(self):
        """FR-2.4.e：冷启动用户不注入探索位（兜底池已承担探索职能）。"""
        newbie = self._mkuser("brand_newbie")
        for seed in range(50):
            result = self._feed(newbie, seed)
            self.assertTrue(result["cold_start"])
            self.assertFalse(result["exploration_injected"], f"seed={seed} 冷启动不应注入")
            self.assertEqual([i for i in result["items"] if i["is_exploration"]], [])

    def test_injection_rate_matches_epsilon(self):
        """AC-F-08c：1000 个 seed 下注入率落在 ε=0.10 的置信区间 [0.07, 0.13]。"""
        user = self._active_user("rate_user")
        n = 1000
        hits = sum(1 for seed in range(n) if self._feed(user, seed)["exploration_injected"])
        rate = hits / n
        self.assertGreaterEqual(rate, 0.07, f"注入率过低：{rate:.4f}（ε={config.EPSILON_EXPLORE}）")
        self.assertLessEqual(rate, 0.13, f"注入率过高：{rate:.4f}（ε={config.EPSILON_EXPLORE}）")

    def test_reason_and_features_still_explainable_for_exploration_item(self):
        """探索位也必须带完整归因（分数构成 + 召回路径），不得是"黑盒塞入"。"""
        user = self._active_user("explain_user")
        _seed, result = self._first_injecting_seed(user)
        item = next(i for i in result["items"] if i["is_exploration"])
        self.assertEqual(set(item["features"]), {"aff", "pop", "fresh", "social", "qual"})
        self.assertTrue(item["recall_routes"], "探索项必须能说明它从哪条召回路径来")


if __name__ == "__main__":
    unittest.main(verbosity=2)
