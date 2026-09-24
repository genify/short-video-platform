"""评测器（离线校准）的一致性测试。

**为什么必须测这个**：校准脚本最容易出的错不是崩溃，而是**悄悄算错** ——
评测器自己复刻了一遍召回合并逻辑，一旦与生产 `engine.feed` 漂移，搜出来的
"最优权重"就是在优化另一个目标，且没有任何报错。因此这里把"两者排序必须
逐项一致"钉成断言。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import evaluate  # noqa: E402
from server import config  # noqa: E402
from server.db import Database  # noqa: E402


class EvaluateHarnessCase(unittest.TestCase):
    """用小型合成集（快）覆盖评测器的核心不变式。"""

    USERS = 4

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db, cls.truth = evaluate.build_synthetic_db(
            os.path.join(cls._tmp.name, "eval.db"),
            users=cls.USERS, creators=3, videos_per_creator=5, seed=7,
        )
        cls.evaluator = evaluate.OfflineEvaluator(cls.db, cls.truth, k=5, pool_cap=40, seed=7)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close()
        cls._tmp.cleanup()

    def test_harness_matches_production_feed(self):
        """核心不变式：评测器排序 == 生产 feed 排序（默认权重、无探索位）。"""
        ok, message = self.evaluator.self_check(dict(config.RANK_WEIGHTS))
        self.assertTrue(ok, message)

    def test_ndcg_is_bounded_and_weight_sensitive(self):
        """NDCG ∈ [0,1]，且对权重变化敏感（否则"校准"没有意义）。"""
        pure_aff = {"aff": 1.0, "pop": 0.0, "fresh": 0.0, "social": 0.0, "qual": 0.0}
        pure_pop = {"aff": 0.0, "pop": 1.0, "fresh": 0.0, "social": 0.0, "qual": 0.0}
        a = self.evaluator.ndcg(pure_aff)
        b = self.evaluator.ndcg(pure_pop)
        for value in (a, b, self.evaluator.ndcg(dict(config.RANK_WEIGHTS))):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)
        self.assertNotAlmostEqual(a, b, places=4, msg="不同权重应给出不同 NDCG")

    def test_ndcg_ideal_ranking_is_one(self):
        """排序与真值完全一致时 NDCG 必须为 1.0（度量定义的自检）。"""
        gains = [0.9, 0.5, 0.2]
        self.assertAlmostEqual(evaluate._ndcg(gains, gains, 10), 1.0, places=9)
        self.assertAlmostEqual(evaluate._ndcg([0.2, 0.5, 0.9], gains, 10) < 1.0, True)

    def test_grid_points_are_valid_probability_vectors(self):
        grid = evaluate.simplex_grid(step_units=4)
        self.assertEqual(len(grid), 70)   # C(4+4,4) = 70 个分拆
        for weights in grid:
            self.assertEqual(set(weights), set(config.RANK_WEIGHT_KEYS))
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)
            self.assertTrue(all(v >= 0 for v in weights.values()))

    def test_hardcoded_boundary_flags_stay_true(self):
        """标注/评测口径的边界不自相矛盾：真值权重与现状默认值必须不同。

        若两者相同，"校准前后对比"会退化成"自己和自己比"，
        报告看起来有提升/无提升都无法解释。
        """
        self.assertNotEqual(
            {k: round(v, 6) for k, v in evaluate.GT_WEIGHTS.items()},
            {k: round(v, 6) for k, v in config.DEFAULT_RANK_WEIGHTS.items()},
        )


class FromRealDbCase(unittest.TestCase):
    """`--from-db` 回放路径：留出项必须被真的删掉，且不动原库。"""

    def test_replay_removes_holdout_and_keeps_source_intact(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            source = os.path.join(tmp.name, "source.db")
            db = Database(source)
            creator = db.create_user("c" * 8, "creator_x")["id"]
            viewer = db.create_user("v" * 8, "viewer_x")["id"]
            vids = []
            for i in range(4):
                vid = f"{i:032x}"
                db.create_video(video_id=vid, creator_id=creator, caption=f"c{i}", tags=["美食"],
                                duration_ms=5000, width=480, height=854, size_bytes=1,
                                sha256=vid, storage_path=f"var/media/{vid}.mp4")
                vids.append(vid)
            for vid in vids[:3]:
                db.add_engagement(viewer, vid, "like")
            db.close()

            replay_db, truth = evaluate.load_from_real_db(source, holdout=2)
            self.assertEqual(len(truth), 1)
            self.assertEqual(len(truth[viewer]), 2)
            remaining = replay_db.query(
                "SELECT COUNT(*) AS c FROM engagements WHERE user_id=?", (viewer,)
            )[0]["c"]
            self.assertEqual(remaining, 1, "留出的 2 条正反馈必须已从回放库删除")

            # 原库不受影响
            src = Database(source)
            self.assertEqual(
                src.query("SELECT COUNT(*) AS c FROM engagements")[0]["c"], 3,
                "回放不得修改原库",
            )
            src.close()
            replay_db.close()
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
