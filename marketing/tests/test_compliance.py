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


class Pro13HardeningTest(unittest.TestCase):
    """PRO-13 返修后的装置加固测试（对应 PRO-12 人工终审 §5 的四处盲区）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lexicon = compliance.load_lexicon(LEXICON_PATH)
        with open(COPY_PACK_PATH, "r", encoding="utf-8") as fh:
            cls.pack = json.load(fh)

    def _ids(self, violations):
        return sorted(v["id"] for v in violations)

    # -- D-1：naming_candidates 必须进入扫描 -------------------------------
    def test_naming_candidates_are_scanned(self):
        bad = json.loads(json.dumps(self.pack))
        bad["naming_candidates"]["directions"]["A"]["candidates"][0]["pre_t0"]["slogan"] = "发出来，就被看见"
        violations = compliance.validate_copy_pack(bad, self.lexicon, "pre_t0")
        hits = [v for v in violations if "naming_candidates" in v.get("json_path", "")]
        self.assertTrue(hits, "naming_candidates 必须进入合规扫描（PRO-12 §5 D-1）")
        self.assertIn("TG-06", self._ids(hits))
        self.assertEqual(
            hits[0]["json_path"],
            "naming_candidates.directions.A.candidates[0].pre_t0.slogan",
        )

    def test_naming_t0_arm_deferred_out_of_pre_t0_scan(self):
        # 真实包：pre_t0 相位不得报出任何 naming_candidates 违规（结果承诺句都在 t0 臂）
        pre = compliance.validate_copy_pack(self.pack, self.lexicon, "pre_t0")
        self.assertEqual([v for v in pre if "naming_candidates" in v.get("json_path", "")], [])
        # 把 t0 臂的句子挪到 pre_t0 臂 → 必须报违规（证明这门禁真的有效，不是空跑）
        moved = json.loads(json.dumps(self.pack))
        cand = moved["naming_candidates"]["directions"]["A"]["candidates"][0]
        cand["pre_t0"]["slogan"] = cand["t0"]["slogan"]
        hits = [
            v for v in compliance.validate_copy_pack(moved, self.lexicon, "pre_t0")
            if "naming_candidates" in v.get("json_path", "")
        ]
        self.assertIn("TG-06", self._ids(hits))

    # -- D-4：界面文案（ui.*）必须进入扫描 ---------------------------------
    def test_ui_node_is_scanned(self):
        bad = json.loads(json.dumps(self.pack))
        bad["ui"]["share"]["gate_text"] = "注册就能保证有人看"
        violations = compliance.validate_copy_pack(bad, self.lexicon, "pre_t0")
        hits = [v for v in violations if v.get("json_path", "").startswith("ui.")]
        self.assertTrue(hits, "ui.* 必须进入合规扫描（PRO-12 §5 D-4）")
        self.assertIn("TG-06", self._ids(hits))

    def test_real_pack_clean_in_both_phases(self):
        for phase in ("pre_t0", "t0"):
            violations = compliance.validate_copy_pack(self.pack, self.lexicon, phase)
            self.assertEqual(
                compliance.blocking_violations(violations), [],
                "真实文案包在 %s 相位不应有阻断级违规" % phase,
            )

    # -- 新增词条的语义覆盖（PRO-12 §3.1 L-1～L-4 / §4.2）-------------------
    def test_semantic_blind_spots_now_covered(self):
        cases = [
            ("这点比我用过的平台都清楚", "HB-16"),          # L-2 竞品对照
            ("一个入口完成多平台分发", "HB-17"),            # L-4 未上线能力
            ("我能看到它被推给谁、为什么", "HB-17"),         # L-3 受众可见性超出实现
            ("把首发的曝光下限写成产品约束", "HB-18"),       # §4.2 「下限 = 保底」
            ("发出来，就被看见", "TG-06"),                  # L-1 命名候选无数字结果承诺
            ("每个字都有人看", "TG-06"),
            ("第一条就有人看见", "TG-06"),
        ]
        for text, rule_id in cases:
            found = self._ids(compliance.find_violations(text, self.lexicon, "pre_t0"))
            self.assertIn(rule_id, found, "%r 应命中 %s（实际：%s）" % (text, rule_id, found))
        # 反证：机制类替代句不得被误伤
        for ok in ("规则写出来，你自己核对", "每条理由都写出来", "首发走独立路由", "先育苗，再谈赛道"):
            self.assertEqual(
                compliance.find_violations(ok, self.lexicon, "pre_t0"), [], "%r 不应报违规" % ok
            )

    # -- D-2：必含项 scope 必须真的被执行 ----------------------------------
    def test_share_landing_required_scope_is_enforced(self):
        import importlib.util
        import tempfile
        from pathlib import Path

        lint_path = os.path.join(ROOT, "marketing", "scripts", "compliance_lint.py")
        spec_obj = importlib.util.spec_from_file_location("pd_compliance_lint", lint_path)
        lint = importlib.util.module_from_spec(spec_obj)
        sys.modules["pd_compliance_lint"] = lint
        spec_obj.loader.exec_module(lint)

        manifest = json.loads(Path(lint.MANIFEST_PATH).read_text(encoding="utf-8"))
        self.assertIn(
            "share_landing", manifest["required_token_scopes"],
            "share_landing 必须登记为必含项 scope（PRO-12 §5 D-2）",
        )
        # 真实物料：必含项 0 缺失
        self.assertEqual(lint.check_required_tokens(manifest, self.lexicon), [])

        # 反证：把 share 节点换成不含「直连可播放/不用注册」的最小节点 → RT-04 必须报缺失
        tmp = tempfile.mkdtemp()
        with open(COPY_PACK_PATH, "r", encoding="utf-8") as fh:
            stripped = json.load(fh)
        stripped["assets"]["share"] = {
            "variants": {
                v: {"pre_t0": {"h1": "看视频", "bullets": ["点开即播"]},
                    "t0": {"h1": "看视频", "bullets": ["点开即播"]}}
                for v in ("V1", "V2", "V3")
            }
        }
        target = Path(tmp) / "marketing" / "landing"
        target.mkdir(parents=True)
        (target / "copy_pack.json").write_text(
            json.dumps(stripped, ensure_ascii=False), encoding="utf-8"
        )
        original_root = lint.ROOT
        try:
            lint.ROOT = Path(tmp)
            missing = lint.check_required_tokens(manifest, self.lexicon)
        finally:
            lint.ROOT = original_root
        self.assertIn("RT-04", [v["id"] for v in missing])


if __name__ == "__main__":
    unittest.main()
