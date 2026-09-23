"""推荐引擎单元测试：特征计算、线性打分、MMR 重排、冷启动。

运行： python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import config  # noqa: E402
from server.db import Database  # noqa: E402
from server.recommend import (  # noqa: E402
    Candidate,
    RecommendEngine,
    _cosine,
    _jaccard,
    _l2_normalize,
    _video_tag_vector,
)


class BaseCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "t.db"))
        self.engine = RecommendEngine(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.tmp.cleanup()

    # -- 造数工具 ---------------------------------------------------------
    def mkuser(self, handle: str) -> str:
        return self.db.create_user(handle, handle)["id"]

    def mkvideo(self, creator: str, caption: str, tags: list[str], age_h: float = 0.0,
                views: int = 0, completes: int = 0, likes: int = 0, shares: int = 0) -> str:
        vid = os.urandom(8).hex()
        self.db.create_video(
            video_id=vid, creator_id=creator, caption=caption, tags=tags,
            duration_ms=15000, width=720, height=1280, size_bytes=1024,
            sha256=os.urandom(16).hex(), storage_path="/dev/null",
        )
        if age_h:
            self.db.execute("UPDATE videos SET created_at=? WHERE id=?", (time.time() - age_h * 3600, vid))
        if views or completes or likes or shares:
            self.db.execute(
                "UPDATE video_stats SET views=?, completes=?, likes=?, shares=?, updated_at=? WHERE video_id=?",
                (views, completes, likes, shares, time.time(), vid),
            )
        return vid


# ---------------------------------------------------------------------------
# 基础数学工具
# ---------------------------------------------------------------------------
class TestVectorUtils(BaseCase):
    def test_l2_normalize_gives_unit_norm(self):
        v = _l2_normalize({"a": 3.0, "b": 4.0})
        self.assertAlmostEqual(sum(x * x for x in v.values()) ** 0.5, 1.0, places=9)

    def test_l2_normalize_empty_is_empty(self):
        self.assertEqual(_l2_normalize({}), {})

    def test_cosine_of_identical_vectors_is_one(self):
        v = _l2_normalize({"a": 1.0, "b": 1.0})
        self.assertAlmostEqual(_cosine(v, v), 1.0, places=9)

    def test_cosine_orthogonal_is_zero(self):
        self.assertEqual(_cosine({"a": 1.0}, {"b": 1.0}), 0.0)

    def test_jaccard(self):
        # 交集 {美食} 大小 1，并集 {美食, 旅行} 大小 2 => 0.5
        self.assertAlmostEqual(_jaccard(["美食", "旅行"], ["美食"]), 0.5, places=9)
        self.assertAlmostEqual(_jaccard(["a", "b"], ["b", "c"]), 1 / 3, places=9)
        self.assertEqual(_jaccard([], ["美食"]), 0.0)

    def test_video_tag_vector_is_normalized_multi_tag(self):
        vec = _video_tag_vector({"tags": ["美食", "旅行"]})
        self.assertAlmostEqual(sum(x * x for x in vec.values()) ** 0.5, 1.0, places=9)
        self.assertAlmostEqual(vec["美食"], vec["旅行"], places=9)


# ---------------------------------------------------------------------------
# 用户画像
# ---------------------------------------------------------------------------
class TestUserProfile(BaseCase):
    def test_profile_weights_high_value_actions_more(self):
        u = self.mkuser("u1")
        c1 = self.mkuser("c1")
        v_like = self.mkvideo(c1, "美食", ["美食"])
        v_skip = self.mkvideo(c1, "宠物", ["宠物"])
        self.db.add_engagement(u, v_like, "like")     # 权重 3
        self.db.add_engagement(u, v_skip, "skip")     # 权重 -2
        prof = self.engine.user_tag_profile(u)
        self.assertIn("美食", prof)
        self.assertNotIn("宠物", prof, "负向行为不应进入兴趣画像")

    def test_profile_empty_for_new_user(self):
        u = self.mkuser("fresh")
        self.assertEqual(self.engine.user_tag_profile(u), {})


# ---------------------------------------------------------------------------
# 特征与打分
# ---------------------------------------------------------------------------
class TestFeaturesAndScoring(BaseCase):
    def _ctx(self, **kw):
        return {"profile": {}, "following": set(), "second_hop": set(),
                "max_total": 100.0, "now": time.time(), **kw}

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(config.RANK_WEIGHTS.values()), 1.0, places=9)

    def test_score_is_weighted_sum(self):
        feats = {"aff": 1.0, "pop": 1.0, "fresh": 1.0, "social": 1.0, "qual": 1.0}
        self.assertAlmostEqual(self.engine.score(feats), 1.0, places=6)

    def test_score_matches_manual_formula(self):
        feats = {"aff": 0.5, "pop": 0.2, "fresh": 0.1, "social": 1.0, "qual": 0.8}
        expect = 0.45 * 0.5 + 0.20 * 0.2 + 0.15 * 0.1 + 0.10 * 1.0 + 0.10 * 0.8
        self.assertAlmostEqual(self.engine.score(feats), round(expect, 6), places=6)

    def test_freshness_halves_after_half_life(self):
        c = self.mkuser("c")
        v = self.mkvideo(c, "x", ["美食"], age_h=config.FRESH_HALF_LIFE_HOURS)
        video = self.db.get_video(v)
        self.assertAlmostEqual(self.engine._freshness(video, time.time()), 0.5, places=2)

    def test_quality_uses_completion_and_like_rate(self):
        c = self.mkuser("c2")
        v = self.mkvideo(c, "x", ["美食"], views=100, completes=55, likes=12)
        video = self.db.get_video(v)
        # 完播率 0.55 / 基准 0.55 = 1.0；点赞率 0.12 / 基准 0.12 = 1.0
        self.assertAlmostEqual(self.engine._quality(video), 1.0, places=6)

    def test_quality_zero_without_views(self):
        c = self.mkuser("c3")
        v = self.mkvideo(c, "x", ["美食"])
        self.assertEqual(self.engine._quality(self.db.get_video(v)), 0.0)

    def test_social_is_one_for_followed_creator(self):
        u = self.mkuser("u"); c = self.mkuser("c")
        v = self.mkvideo(c, "x", ["美食"])
        cand = Candidate(video=self.db.get_video(v))
        feats = self.engine.features(u, cand, **self._ctx(following={c}))
        self.assertEqual(feats["social"], 1.0)

    def test_social_is_half_for_second_hop(self):
        u = self.mkuser("u2"); c = self.mkuser("c_far")
        v = self.mkvideo(c, "x", ["美食"])
        cand = Candidate(video=self.db.get_video(v))
        feats = self.engine.features(u, cand, **self._ctx(second_hop={c}))
        self.assertEqual(feats["social"], 0.5)

    def test_affinity_reflects_tag_interest(self):
        u = self.mkuser("u3"); c = self.mkuser("c4")
        liked = self.mkvideo(c, "美食", ["美食"])
        other = self.mkvideo(c, "钓鱼", ["钓鱼"])
        self.db.add_engagement(u, liked, "like")
        profile = self.engine.user_tag_profile(u)
        v_match = Candidate(video=self.db.get_video(liked))
        v_other = Candidate(video=self.db.get_video(other))
        f_match = self.engine.features(u, v_match, **self._ctx(profile=profile))
        f_other = self.engine.features(u, v_other, **self._ctx(profile=profile))
        self.assertGreater(f_match["aff"], f_other["aff"])
        self.assertEqual(f_other["aff"], 0.0)


# ---------------------------------------------------------------------------
# 重排
# ---------------------------------------------------------------------------
class TestRerank(BaseCase):
    def test_mmr_prefers_diversity_over_pure_score(self):
        c = self.mkuser("c")
        # 两条同标签高分视频 + 一条异标签次高分视频
        v1 = self.mkvideo(c, "美食1", ["美食"], views=100, completes=60, likes=15)
        v2 = self.mkvideo(c, "美食2", ["美食"], views=100, completes=60, likes=15)
        v3 = self.mkvideo(c, "宠物", ["宠物"], views=50, completes=25, likes=5)
        cands = []
        for vid, sc in ((v1, 0.9), (v2, 0.89), (v3, 0.7)):
            cand = Candidate(video=self.db.get_video(vid))
            cand.features = {"aff": 0, "pop": 0, "fresh": 0, "social": 0, "qual": 0}
            cand.score = sc
            cands.append(cand)
        # λ=0.5 时多样性权重更高：v3 应排到第 2 位
        ranked = self.engine.rerank(cands, size=3, lam=0.5)
        self.assertEqual(ranked[0].video_id, v1)
        self.assertEqual(ranked[1].video_id, v3, "MMR 应把异标签视频提前以提升多样性")
        self.assertEqual(ranked[2].video_id, v2)

    def test_pure_relevance_when_lambda_one(self):
        c = self.mkuser("c")
        ids = [self.mkvideo(c, f"v{i}", ["美食"]) for i in range(3)]
        cands = []
        for i, vid in enumerate(ids):
            cand = Candidate(video=self.db.get_video(vid))
            cand.score = 0.9 - i * 0.1
            cands.append(cand)
        ranked = self.engine.rerank(cands, size=3, lam=1.0)
        self.assertEqual([r.video_id for r in ranked], ids)

    def test_creator_cap_diversifies_feed(self):
        c1 = self.mkuser("prolific")
        c2 = self.mkuser("other")
        c1_videos = [self.mkvideo(c1, f"a{i}", ["美食"]) for i in range(5)]
        c2_video = self.mkvideo(c2, "b0", ["宠物"])
        cands = []
        for vid in c1_videos:
            cand = Candidate(video=self.db.get_video(vid))
            cand.score = 0.95
            cands.append(cand)
        cand2 = Candidate(video=self.db.get_video(c2_video))
        cand2.score = 0.5
        cands.append(cand2)
        ranked = self.engine.rerank(cands, size=3)
        creators = [r.creator_id for r in ranked]
        self.assertLessEqual(
            creators.count(c1), config.CREATOR_CAP_PER_FEED,
            "单创作者不得超过打散上限",
        )
        self.assertIn(c2, creators, "低分但不同创作者应被提上来")

    def test_rerank_returns_empty_for_empty_input(self):
        self.assertEqual(self.engine.rerank([], size=10), [])


# ---------------------------------------------------------------------------
# 端到端 feed
# ---------------------------------------------------------------------------
class TestFeed(BaseCase):
    def test_feed_returns_requested_size(self):
        u = self.mkuser("u")
        c = self.mkuser("c")
        for i in range(8):
            self.mkvideo(c, f"v{i}", ["美食"], views=20 + i, completes=10, likes=2)
        out = self.engine.feed(u, size=5, seed=1)
        self.assertEqual(out["size"], 5)
        self.assertEqual(len(out["items"]), 5)
        self.assertTrue(out["cold_start"], "新用户应被判定为冷启动")

    def test_feed_excludes_recently_seen(self):
        u = self.mkuser("u"); c = self.mkuser("c")
        ids = [self.mkvideo(c, f"v{i}", ["美食"], views=10, completes=5, likes=1) for i in range(4)]
        self.db.add_engagement(u, ids[0], "view")
        out = self.engine.feed(u, size=10, seed=2)
        returned = {i["video_id"] for i in out["items"]}
        self.assertNotIn(ids[0], returned, "7 天内看过的视频不应重复推荐")

    def test_feed_prefers_matching_tags_for_warm_user(self):
        u = self.mkuser("u"); c = self.mkuser("c")
        match = self.mkvideo(c, "美食合集", ["美食"], views=30, completes=20, likes=5)
        other = self.mkvideo(c, "钓鱼", ["钓鱼"], views=30, completes=20, likes=5)
        # 造出"非冷启动"的用户行为历史
        warm = [self.mkvideo(c, f"seed{i}", ["美食"]) for i in range(4)]
        for v in warm:
            self.db.add_engagement(u, v, "like")
        out = self.engine.feed(u, size=5, seed=3)
        self.assertFalse(out["cold_start"])
        first = out["items"][0]
        self.assertEqual(first["video_id"], match)
        self.assertGreater(first["features"]["aff"], 0.0)

    def test_feed_includes_score_explanation(self):
        u = self.mkuser("u"); c = self.mkuser("c")
        self.mkvideo(c, "x", ["美食"], views=5, completes=2)
        out = self.engine.feed(u, size=3, seed=4)
        self.assertIn("features", out["items"][0])
        self.assertEqual(set(out["items"][0]["features"]),
                         {"aff", "pop", "fresh", "social", "qual"})
        self.assertIn("reason", out["items"][0])
        self.assertIn("recall_routes", out["items"][0])

    def test_feed_handles_empty_library(self):
        u = self.mkuser("lonely")
        out = self.engine.feed(u, size=5)
        self.assertEqual(out["items"], [])
        self.assertTrue(out["cold_start"])

    def test_weights_are_configurable(self):
        u = self.mkuser("u"); c = self.mkuser("c")
        self.mkvideo(c, "x", ["美食"], views=100, completes=60, likes=15)
        hot_only = RecommendEngine(self.db, weights={
            "aff": 0.0, "pop": 1.0, "fresh": 0.0, "social": 0.0, "qual": 0.0
        })
        out = hot_only.feed(u, size=1, seed=5)
        self.assertAlmostEqual(out["items"][0]["features"]["pop"], out["items"][0]["score"], places=5)

    def test_candidate_pool_not_starved_by_recall_quotas(self):
        """回归测试：召回配额作用于候选池深度，不得限制最终 feed 长度。

        历史缺陷：配额乘以请求 size，导致"行为多的小内容库"用户候选池被饿死
        （6 条视频、看过 2 条，却只召回 2 条而不是 4 条）。召回阶段必须求"广"。
        """
        u = self.mkuser("warm_user")
        c = self.mkuser("creator_x")
        videos = [
            self.mkvideo(c, f"v{i}", [f"tag{i}"], views=10 + i, completes=5, likes=1)
            for i in range(6)
        ]
        # 看过 2 条 => 剩余 4 条可见
        for vid in videos[:2]:
            self.db.add_engagement(u, vid, "view")
            self.db.add_engagement(u, vid, "like")
        out = self.engine.feed(u, size=4, seed=11)
        self.assertFalse(out["cold_start"])
        returned = [i["video_id"] for i in out["items"]]
        self.assertEqual(len(returned), 4, f"应有 4 条可见视频，实得 {returned}")
        for seen in videos[:2]:
            self.assertNotIn(seen, returned)

    def test_feed_length_limited_by_available_content_not_quotas(self):
        """可用内容少于请求量时，应返回全部可用内容而非被配额截断。"""
        u = self.mkuser("tiny_user")
        c = self.mkuser("tiny_creator")
        self.mkvideo(c, "only-one", ["美食"], views=5, completes=2)
        out = self.engine.feed(u, size=20, seed=12)
        self.assertEqual(len(out["items"]), 1)


# ---------------------------------------------------------------------------
# 协同过滤
# ---------------------------------------------------------------------------
class TestCollaborativeFiltering(BaseCase):
    def test_item_similarity_rebuilt_from_co_engagement(self):
        c = self.mkuser("c")
        v1 = self.mkvideo(c, "v1", ["美食"])
        v2 = self.mkvideo(c, "v2", ["美食"])
        v3 = self.mkvideo(c, "v3", ["宠物"])
        for u in ("a", "b", "d"):
            uid = self.mkuser(u)
            self.db.add_engagement(uid, v1, "view")
            self.db.add_engagement(uid, v2, "view")
        uid = self.mkuser("e")
        self.db.add_engagement(uid, v3, "view")
        n = self.db.rebuild_item_similarity()
        self.assertGreater(n, 0)
        sims = self.db.item_similarity([v1])
        neighbours = dict(sims[v1])
        self.assertIn(v2, neighbours)
        self.assertGreater(neighbours[v2], 0)
        self.assertNotIn(v3, neighbours)

    def test_cf_route_contributes_candidates(self):
        c = self.mkuser("c")
        v_seed = self.mkvideo(c, "种子", ["美食"])
        v_next = self.mkvideo(c, "下一个", ["美食"])
        u = self.mkuser("u")
        self.db.add_engagement(u, v_seed, "view")
        for extra in ("x", "y"):
            uid = self.mkuser(extra)
            self.db.add_engagement(uid, v_seed, "view")
            self.db.add_engagement(uid, v_next, "view")
        self.db.rebuild_item_similarity()
        routes = self.engine.recall(u, self.db.user_engagements(u), self.db.list_all_videos(), set())
        cf_ids = [vid for vid, _ in routes["cf"]]
        self.assertIn(v_next, cf_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
