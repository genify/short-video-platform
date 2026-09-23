"""合规校验单元测试（marketing/landing/compliance.py）。

覆盖：hard_ban / t0_gated 的分臂行为、quoted 豁免、required_tokens 缺失检测、
错误信息里的 JSON 路径、以及「分臂校验」不会误伤另一臂。
"""

from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LANDING = os.path.join(ROOT, "marketing", "landing")
if LANDING not in sys.path:
    sys.path.insert(0, LANDING)

import compliance  # noqa: E402

LEXICON_PATH = os.path.join(ROOT, "marketing", "compliance", "lexicon.json")
COPY_PACK_PATH = os.path.join(ROOT, "marketing", "landing", "copy_pack.json")


class ComplianceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lexicon = compliance.load_lexicon(LEXICON_PATH)
        with open(COPY_PACK_PATH, "r", encoding="utf-8") as fh:
            cls.pack = json.load(fh)

    def _severities(self, violations):
        return sorted(v["severity"] for v in violations)

    def _ids(self, violations):
        return sorted(v["id"] for v in violations)

    # -- hard_ban / t0_gated 分臂 --------------------------------------
    def test_hard_ban_flagged_in_both_phases(self):
        for phase in ("pre_t0", "t0"):
            v = compliance.find_violations("首发保底曝光 500 次", self.lexicon, phase)
            self.assertIn("HB-01", self._ids(v), f"{phase} 应命中 HB-01")
            v = compliance.find_violations("用社交冷启动做召回", self.lexicon, phase)
            self.assertIn("HB-08", self._ids(v), f"{phase} 应命中 HB-08")

    def test_t0_gated_blocked_before_t0_only(self):
        # TG-02 只针对「曝光下限承诺」的表述（≥50 次 / 50 次真实曝光），
        # 不针对内部指标里的「≥ 50%（留资率）」「≥ 50 名（参与创作者）」，
        # 否则会把内部 KPI 误判为对外承诺（见 lexicon.json TG-02 reason 的说明）。
        text = "首发 24 小时曝光 P10 ≥ 50 次，基尼系数 ≤ 0.6"
        pre = compliance.find_violations(text, self.lexicon, "pre_t0")
        self.assertEqual(self._severities(pre), ["t0_gated"] * len(pre))
        self.assertTrue({"TG-01", "TG-02", "TG-03"} <= set(self._ids(pre)))
        # t0 臂：上述量化承诺不再违规
        self.assertEqual(compliance.find_violations(text, self.lexicon, "t0"), [])

    def test_result_promise_blocked_before_t0(self):
        text = "我们保证有人看"
        self.assertIn("TG-06", self._ids(compliance.find_violations(text, self.lexicon, "pre_t0")))
        self.assertEqual(compliance.find_violations(text, self.lexicon, "t0"), [])

    def test_violation_shape(self):
        v = compliance.find_violations("保底曝光 500", self.lexicon, "t0")[0]
        self.assertEqual(
            set(v.keys()), {"id", "pattern", "matched", "reason", "source", "severity"}
        )
        self.assertEqual(v["severity"], "hard_ban")
        self.assertEqual(v["matched"], "保底曝光")

    # -- quoted 豁免 ----------------------------------------------------
    def test_quoted_exemption_per_line(self):
        # 只有被引用的那一行豁免
        exempt = "禁止出现「保底曝光 500」"
        self.assertEqual(compliance.find_violations(exempt, self.lexicon, "pre_t0", quoted=True), [])
        self.assertEqual(
            len(compliance.find_violations(exempt, self.lexicon, "pre_t0", quoted=False)), 1
        )
        # 混合：第 1 行被引用（含标记「禁止」）→ HB-08 豁免；第 2 行仍命中 HB-01
        text = "禁止：社交冷启动\n保底曝光 500"
        quoted = compliance.find_violations(text, self.lexicon, "pre_t0", quoted=True)
        self.assertEqual([v["id"] for v in quoted], ["HB-01"])
        strict = compliance.find_violations(text, self.lexicon, "pre_t0", quoted=False)
        self.assertEqual(sorted(v["id"] for v in strict), ["HB-01", "HB-08"])

    # -- required_tokens ------------------------------------------------
    def test_required_tokens_missing_reported_with_path(self):
        bare = {"assets": {"recruit": {"form": {"consent_text": "谢谢参与"}},
                           "share": {"variants": {"V1": {"pre_t0": {"h1": "看视频"}}}}}}
        violations = compliance.validate_copy_pack(bare, self.lexicon, "pre_t0")
        required = [v for v in violations if v["severity"] == "required_missing"]
        self.assertEqual(self._ids(required), ["RT-01", "RT-02", "RT-03", "RT-04"])
        paths = {v["id"]: v["json_path"] for v in required}
        self.assertEqual(paths["RT-01"], "assets.recruit.form.consent_text")
        self.assertEqual(paths["RT-04"], "assets.share")

    def test_required_tokens_present_when_consent_text_covers(self):
        pack = {"assets": {"recruit": {"form": {
            "consent_text": "收集目的：仅用于邀请；保留 90 天到期删除；可回复「退出」撤回。"
        }}, "share": {"variants": {"V1": {"pre_t0": {"sub": "先看，不用注册"}}}}}}
        violations = compliance.validate_copy_pack(pack, self.lexicon, "pre_t0")
        self.assertEqual([v for v in violations if v["severity"] == "required_missing"], [])

    # -- JSON 路径 ------------------------------------------------------
    def test_json_path_in_error_message(self):
        bad = json.loads(json.dumps(self.pack))
        bad["assets"]["recruit"]["variants"]["V1"]["pre_t0"]["h1"] = "首发 P10 ≥ 50 次"
        violations = compliance.validate_copy_pack(bad, self.lexicon, "pre_t0")
        paths = {v["json_path"] for v in violations}
        self.assertIn("assets.recruit.variants.V1.pre_t0.h1", paths)
        hit = [v for v in violations if v["json_path"].endswith("pre_t0.h1")][0]
        self.assertEqual(hit["severity"], "t0_gated")

    # -- 分臂校验不误伤另一臂 -------------------------------------------
    def test_arm_scoping(self):
        # pre_t0 校验不应把 t0 臂的量化承诺算进来
        pre = compliance.validate_copy_pack(self.pack, self.lexicon, "pre_t0")
        self.assertTrue(all(".t0." not in v.get("json_path", "") for v in pre))
        self.assertEqual(compliance.blocking_violations(pre), [])
        # t0 校验只禁 hard_ban：真实 t0 臂无 hard_ban 命中
        t0 = compliance.validate_copy_pack(self.pack, self.lexicon, "t0")
        self.assertEqual(compliance.blocking_violations(t0), [])


if __name__ == "__main__":
    unittest.main()
