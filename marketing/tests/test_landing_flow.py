"""落地页服务端到端测试（真实 HTTP，端口 0，临时 sqlite）。

覆盖：
  ① 分流确定性且近似均匀（600 uid，三臂各 150–250）
  ② 粘性（同一 cookie 多次请求 variant 不变；Set-Cookie 属性正确）
  ③ POST /api/events 入账并能被 /api/stats 聚合
  ④ /api/lead 缺 consent → 400
  ⑤ /api/lead 正常 → 200；重复提交 duplicated=true 且 leads 仍 1 行
  ⑥ /api/withdraw 后 contact 为空但统计不变
  ⑦ /api/stats 的 v1_minus_max_v2_v3_pp 算术正确（固定事件手算比对）
  ⑧ 启动门禁：含 "P10" 的 pre_t0 文案 → 子进程 exit code 2
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LANDING = os.path.join(ROOT, "marketing", "landing")
COPY_PACK_PATH = os.path.join(ROOT, "marketing", "landing", "copy_pack.json")
APP_PATH = os.path.join(LANDING, "app.py")
if LANDING not in sys.path:
    sys.path.insert(0, LANDING)


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


landing_app = _load_module("pd_landing_app", APP_PATH)


class LandingFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "landing.sqlite3")
        with open(COPY_PACK_PATH, "r", encoding="utf-8") as fh:
            pack = json.load(fh)
        self.application = landing_app.Application(
            db_path=self.db_path, phase="pre_t0", base_url="http://127.0.0.1:0", copy_pack=pack
        )
        self.httpd = landing_app.serve("127.0.0.1", 0, self.application)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    # -- HTTP 工具 ------------------------------------------------------
    def request(self, method, path, body=None, ctype="application/json", cookies=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {}
        if body is not None:
            headers["Content-Type"] = ctype
            headers["Content-Length"] = str(len(body))
        if cookies:
            headers["Cookie"] = cookies
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        status = resp.status
        set_cookie = resp.getheader("Set-Cookie")
        ctype_resp = resp.getheader("Content-Type") or ""
        conn.close()
        if ctype_resp.startswith("application/json"):
            data = json.loads(raw.decode("utf-8"))
        else:
            data = raw.decode("utf-8")
        return status, data, set_cookie

    @staticmethod
    def _j(payload):
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _stats(self):
        status, data, _ = self.request("GET", "/api/stats")
        self.assertEqual(status, 200)
        return data

    def _leads_count(self):
        with self.application.store.connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"]

    # -- ① 分流确定性 + 近似均匀 ----------------------------------------
    def test_assign_deterministic_and_balanced(self):
        counts = {v: 0 for v in landing_app.VARIANTS}
        for i in range(600):
            uid = f"uid-{i}"
            v = landing_app.assign(uid)
            self.assertEqual(v, landing_app.assign(uid), "同 uid 必须确定")
            self.assertIn(v, landing_app.VARIANTS)
            counts[v] += 1
        for v in landing_app.VARIANTS:
            self.assertGreaterEqual(counts[v], 150, f"{v} 过少: {counts}")
            self.assertLessEqual(counts[v], 250, f"{v} 过多: {counts}")

    # -- ② 粘性 ---------------------------------------------------------
    def test_assignment_sticky_via_cookie(self):
        status, html, cookie = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("pd_uid=", cookie or "")
        self.assertIn("Max-Age=2592000", cookie)
        self.assertIn("SameSite=Lax", cookie)
        uid_cookie = cookie.split(";")[0]

        variants = []
        for _ in range(3):
            status, html, _ = self.request("GET", "/", cookies=uid_cookie)
            match = re.search(r"变体=(V\d)", html)
            self.assertIsNotNone(match, "页面应显示变体")
            variants.append(match.group(1))
        self.assertEqual(len(set(variants)), 1, f"同 cookie 变体应不变: {variants}")
        # 数据库里的 assignment 也只有一行
        with self.application.store.connect() as conn:
            n = conn.execute("SELECT COUNT(*) AS n FROM assignments").fetchone()["n"]
        self.assertEqual(n, 1)

    # -- ③ /api/events 入账 + 聚合 --------------------------------------
    def test_events_ingest_and_aggregate(self):
        status, data, cookie = self.request(
            "POST", "/api/events", self._j({"event": "cta_click", "asset": "recruit", "variant": "V1"})
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["variant"], "V1")
        self.assertTrue(data["visitor_id"])

        # 再来一条 page_view（服务端渲染路径也可入账）
        status, _, _ = self.request("GET", "/")
        self.assertEqual(status, 200)

        stats = self._stats()
        self.assertEqual(stats["by_variant"]["recruit"]["V1"]["cta_click"], 1)
        self.assertGreaterEqual(stats["sample"]["recruit_page_view"], 1)

    # -- ④ 缺 consent → 400 ---------------------------------------------
    def test_lead_without_consent_is_400(self):
        status, data, _ = self.request(
            "POST", "/api/lead", self._j({"contact": "a@example.com", "consent": False})
        )
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])
        self.assertEqual(self._leads_count(), 0)
        # 缺 contact 同样 400
        status, data, _ = self.request("POST", "/api/lead", self._j({"contact": "", "consent": True}))
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    # -- ⑤ 正常留资 + 重复提交 ------------------------------------------
    def test_lead_success_and_duplicate(self):
        payload = self._j({"contact": "lead@example.com", "consent": True, "variant": "V1"})
        status, data, _ = self.request("POST", "/api/lead", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertFalse(data["duplicated"])
        self.assertIsInstance(data["lead_id"], int)

        status, data2, _ = self.request("POST", "/api/lead", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data2["ok"])
        self.assertTrue(data2["duplicated"])
        self.assertEqual(data2["lead_id"], data["lead_id"])
        self.assertEqual(self._leads_count(), 1, "重复提交不得新增行")

        # 归一化：大小写/空格差异视为同一 contact
        status, data3, _ = self.request(
            "POST", "/api/lead", self._j({"contact": "  Lead@Example.com ", "consent": True})
        )
        self.assertTrue(data3["duplicated"])
        self.assertEqual(self._leads_count(), 1)

    # -- ⑥ 撤回 ---------------------------------------------------------
    def test_withdraw_keeps_stats(self):
        self.request("GET", "/")  # 造一条 page_view
        payload = self._j({"contact": "w@example.com", "consent": True, "variant": "V2"})
        self.request("POST", "/api/lead", payload)
        before = self._stats()

        status, data, _ = self.request("POST", "/api/withdraw", self._j({"contact": "w@example.com"}))
        self.assertEqual(status, 200)
        self.assertEqual(data["withdrawn"], 1)

        with self.application.store.connect() as conn:
            row = conn.execute("SELECT contact, contact_hash, withdrawn_at FROM leads").fetchone()
        self.assertIsNone(row["contact"], "撤回后 contact 应为空")
        self.assertTrue(row["contact_hash"], "hash 应保留")
        self.assertTrue(row["withdrawn_at"], "withdrawn_at 应写入")

        after = self._stats()
        self.assertEqual(before["sample"]["recruit_page_view"], after["sample"]["recruit_page_view"])
        self.assertEqual(
            before["by_variant"]["recruit"], after["by_variant"]["recruit"], "统计口径不变"
        )

    # -- ⑦ v1_minus_max_v2_v3_pp 算术 -----------------------------------
    def test_decision_arithmetic(self):
        store = self.application.store
        table = {"V1": (10, 3), "V2": (10, 1), "V3": (10, 0)}  # (page_view, form_submit)
        for variant, (pv, subs) in table.items():
            for _ in range(pv):
                store.record_event(event="page_view", asset="recruit", variant=variant)
            for _ in range(subs):
                store.record_event(event="form_submit", asset="recruit", variant=variant)

        stats = self._stats()
        # V1=0.3, V2=0.1, V3=0.0 → (0.3 - max(0.1,0.0))*100 = 20.0
        self.assertAlmostEqual(stats["decision"]["v1_minus_max_v2_v3_pp"], 20.0, places=2)
        self.assertEqual(stats["by_variant"]["recruit"]["V1"]["form_submit"], 3)
        self.assertAlmostEqual(stats["by_variant"]["recruit"]["V1"]["submit_rate"], 0.3, places=6)
        self.assertEqual(stats["sample"]["recruit_page_view"], 30)
        self.assertFalse(stats["decision"]["pass"])  # 样本 < 300

        # 分母为 0 → submit_rate 为 null，pp 也为 null
        store2 = landing_app.Application(
            db_path=os.path.join(self.tmp.name, "empty.sqlite3"), phase="pre_t0",
            base_url="http://x", copy_pack={"assets": {}},
        )
        empty = store2.store.stats("pre_t0")
        self.assertIsNone(empty["by_variant"]["recruit"]["V1"]["submit_rate"])
        self.assertIsNone(empty["decision"]["v1_minus_max_v2_v3_pp"])

    # -- ⑧ 启动门禁 -----------------------------------------------------
    def test_startup_gate_rejects_p10(self):
        with open(COPY_PACK_PATH, "r", encoding="utf-8") as fh:
            pack = json.load(fh)
        pack["assets"]["recruit"]["variants"]["V1"]["pre_t0"]["h1"] = "首发 24 小时曝光 P10 ≥ 50 次"
        bad_path = os.path.join(self.tmp.name, "bad_copy_pack.json")
        with open(bad_path, "w", encoding="utf-8") as fh:
            json.dump(pack, fh, ensure_ascii=False)

        env = dict(os.environ)
        env["PD_COPY_PACK"] = bad_path
        proc = subprocess.run(
            [sys.executable, APP_PATH, "--port", "0",
             "--db", os.path.join(self.tmp.name, "gate.sqlite3"), "--phase", "pre_t0"],
            env=env, capture_output=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 2, f"应 exit 2，实际 {proc.returncode}\n{proc.stdout.decode()}")
        self.assertIn("拒绝启动", proc.stdout.decode("utf-8", "ignore"))

    def test_startup_gate_allows_clean_pack(self):
        """对照组：真实 pre_t0 文案应能通过门禁并把服务拉起来。"""
        env = dict(os.environ)
        proc = subprocess.Popen(
            [sys.executable, APP_PATH, "--port", "0",
             "--db", os.path.join(self.tmp.name, "ok.sqlite3"), "--phase", "pre_t0"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(1.5)
            self.assertIsNone(proc.poll(), "干净文案下服务应保持运行（未 exit 2）")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # -- ⑨ PRO-13：t0 相位的 T0 前置证据门禁（闭合 PRO-12 §5 D-3）---------
    def _t0_evidence(self, *, pro7=True, preconditions=True, count=8, date="2026-09-24"):
        return {
            "pro7_delivered": pro7,
            "preconditions_all_green": preconditions,
            "evidence_date": date,
            "preconditions": [{"id": "#%d" % (i + 1), "status": "green"} for i in range(count)],
        }

    def _run_t0_start(self, extra_args):
        return subprocess.run(
            [sys.executable, APP_PATH, "--port", "0",
             "--db", os.path.join(self.tmp.name, "t0.sqlite3"), "--phase", "t0"] + extra_args,
            env=dict(os.environ), capture_output=True, timeout=30,
        )

    def test_t0_phase_requires_evidence_file(self):
        proc = self._run_t0_start([])
        self.assertEqual(proc.returncode, 3, proc.stdout.decode("utf-8", "ignore"))
        self.assertIn("T0 前置证据", proc.stdout.decode("utf-8", "ignore"))

    def test_t0_phase_rejects_incomplete_evidence(self):
        path = os.path.join(self.tmp.name, "t0_bad.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._t0_evidence(pro7=False, count=3), fh, ensure_ascii=False)
        proc = self._run_t0_start(["--t0-evidence", path])
        self.assertEqual(proc.returncode, 3)
        out = proc.stdout.decode("utf-8", "ignore")
        self.assertIn("pro7_delivered", out)
        self.assertIn("preconditions", out)

    def test_t0_phase_starts_with_valid_evidence(self):
        path = os.path.join(self.tmp.name, "t0_ok.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._t0_evidence(), fh, ensure_ascii=False)
        proc = subprocess.Popen(
            [sys.executable, APP_PATH, "--port", "0",
             "--db", os.path.join(self.tmp.name, "t0_ok.sqlite3"),
             "--phase", "t0", "--t0-evidence", path],
            env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(1.5)
            self.assertIsNone(proc.poll(), "有效证据下 t0 相位服务应保持运行")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # -- ⑩ PRO-13：命名候选渲染 + 界面文案来自文案包 ----------------------
    def test_naming_candidate_renders_and_is_recorded(self):
        status, html, _ = self.request("GET", "/?naming=A1")
        self.assertEqual(status, 200)
        self.assertIn("光见", html, "候选名必须真的渲染出来（PRO-12 §3.2 L-8）")
        self.assertIn("规则写出来，你自己核对", html, "pre_t0 臂应展示机制类替代句")
        self.assertNotIn("发出来，就被看见", html, "结果承诺型 Slogan 不得在 pre_t0 出现")
        self.assertIn("候选=A1", html)

        stats = self._stats()
        self.assertEqual(stats["naming"]["A1"]["page_view"], 1)

        # 未登记的 id 一律忽略（不渲染、不入账）
        status, html2, _ = self.request("GET", "/?naming=ZZ9")
        self.assertEqual(status, 200)
        self.assertNotIn("本页展示的品牌候选", html2)
        stats2 = self._stats()
        self.assertNotIn("ZZ9", stats2["naming"])

    def test_ui_copy_comes_from_copy_pack(self):
        with open(COPY_PACK_PATH, "r", encoding="utf-8") as fh:
            pack = json.load(fh)
        pack = json.loads(json.dumps(pack))
        pack["ui"]["share"]["player_note"] = "SENTINEL-PLAYER"
        pack["ui"]["share"]["gate_text"] = "SENTINEL-GATE"
        pack["ui"]["recruit"]["result_ok"] = "SENTINEL-OK"
        node = pack["assets"]["share"]["variants"]["V1"]["pre_t0"]
        html = landing_app.render_share(node, "V1", "pre_t0", "vid1", pack["ui"]["share"])
        self.assertIn("SENTINEL-PLAYER", html)
        self.assertIn("SENTINEL-GATE", html)
        self.assertNotIn("直连可播放 · 无需注册 · 点击播放", html)
        recruit_html = landing_app.render_recruit(
            pack["assets"]["recruit"]["variants"]["V1"]["pre_t0"],
            pack["assets"]["recruit"]["form"], "V1", "pre_t0", pack["ui"]["recruit"],
        )
        self.assertIn("SENTINEL-OK", recruit_html)

    def test_ui_keys_gate(self):
        with open(COPY_PACK_PATH, "r", encoding="utf-8") as fh:
            pack = json.load(fh)
        self.assertEqual(landing_app.check_required_ui_keys(pack), [])
        self.assertTrue(landing_app.check_required_ui_keys({}))
        broken = json.loads(json.dumps(pack))
        broken["ui"]["share"].pop("gate_text")
        problems = landing_app.check_required_ui_keys(broken)
        self.assertTrue(any("ui.share.gate_text" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
