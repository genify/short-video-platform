"""假门 / 分享落地页服务 + 分流统计 + 合规门禁（纯标准库，零第三方依赖）。

    python3 marketing/landing/app.py --port 8088 --db marketing/out/landing.sqlite3 --phase pre_t0

启动硬门（三道，任一不过即拒绝启动）：
  ① 合规门禁：用 compliance.validate_copy_pack 校验当前 phase 下的全部文案
     （assets + naming_candidates + ui），命中 hard_ban / t0_gated 即拒绝启动
     （exit code 2，并打印违规清单）。
  ② T0 前置校验：`--phase t0` 必须同时给 `--t0-evidence <T0 证据 JSON>`，
     且证据里 PRO-7 交付与 §0.3 八项前置全绿均为 true，否则拒绝启动（exit code 3）。
     这是为了堵住「T0 前误传 --phase t0 即投出三个数字」的装置层路径
     （PRO-12 人工终审 §2.6-B / §5 D-3）。
  ③ 界面文案完整性：copy_pack.json 的 ui.* 必须包含全部必需键，缺失即拒绝启动
     （exit code 4，fail-closed，避免页面出现占位符）。

路由表
    GET  /                招募假门落地页（cookie 分流 + 粘性，写 page_view）
    GET  /v/1|2|3         强制指定变体的招募页（定向投放对照，事件记 forced=1）
    GET  /s/<video_id>    分享落地页（直连可播放、不强制注册、看满 3 条引导注册）
    POST /api/events      事件入账（page_view|cta_click|view3|register_click）
    POST /api/lead        留资（consent 必填，写 leads + form_submit 事件）
    POST /api/withdraw    撤回（按 contact 或 visitor_id，置空 contact、保留 hash）
    GET  /api/stats       分流统计 + 判据决策
    GET  /api/health      健康检查
    GET  /api/export/leads?token=...   CSV 导出（仅在设置 --export-token 时启用）
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

# --- 让 compliance 在「直接运行」与「importlib 加载」两种方式下都可导入 --------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import compliance  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))  # marketing/landing -> marketing -> <ROOT>
# 允许用环境变量覆盖路径：便于测试「门禁拒绝启动」而不改动受冻结的输入文件。
LEXICON_PATH = os.environ.get("PD_LEXICON") or os.path.join(
    ROOT, "marketing", "compliance", "lexicon.json"
)
COPY_PACK_PATH = os.environ.get("PD_COPY_PACK") or os.path.join(
    ROOT, "marketing", "landing", "copy_pack.json"
)

VARIANTS = ("V1", "V2", "V3")
ARM_SEED = "PRO-1-landing-v1"
CONSENT_TEXT_VERSION = "v1"
RETENTION_DAYS = 90
ALLOWED_EVENTS = ("page_view", "cta_click", "view3", "register_click")

# 界面文案必需键（copy_pack.json 的 ui.*）。缺失即拒绝启动（exit 4）。
REQUIRED_UI_KEYS: dict[str, tuple[str, ...]] = {
    "recruit": (
        "result_ok", "result_duplicate", "result_error_prefix",
        "result_error_unknown", "result_network_error", "naming_label",
    ),
    "share": (
        "player_note", "viewed_prefix", "viewed_suffix",
        "gate_text", "register_button", "register_done",
    ),
}
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content")

SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments(
    visitor_id   TEXT PRIMARY KEY,
    variant      TEXT NOT NULL,
    first_seen   TEXT NOT NULL,
    forced_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events(
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    event        TEXT NOT NULL,
    asset        TEXT NOT NULL,
    variant      TEXT,
    naming       TEXT,
    visitor_id   TEXT,
    video_id     TEXT,
    utm_source   TEXT,
    utm_medium   TEXT,
    utm_campaign TEXT,
    utm_content  TEXT,
    utm_ref      TEXT,
    meta         TEXT,
    ip_hash      TEXT,
    forced       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_asset_event ON events(asset, event);
CREATE INDEX IF NOT EXISTS idx_events_variant ON events(variant);
CREATE INDEX IF NOT EXISTS idx_events_naming ON events(naming);
CREATE TABLE IF NOT EXISTS leads(
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at           TEXT NOT NULL,
    last_seen            TEXT NOT NULL,
    contact              TEXT,
    contact_hash         TEXT UNIQUE,
    consent_text_version TEXT NOT NULL DEFAULT 'v1',
    retention_until      TEXT,
    variant              TEXT,
    utm_source           TEXT,
    utm_medium           TEXT,
    utm_campaign         TEXT,
    utm_content          TEXT,
    utm_ref              TEXT,
    withdrawn_at         TEXT,
    visitor_id           TEXT
);
CREATE TABLE IF NOT EXISTS meta_config(key TEXT PRIMARY KEY, value TEXT);
"""


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def assign(uid: str, arm_seed: str = ARM_SEED) -> str:
    """确定性、近似均匀的分流：sha256(uid + ":" + arm_seed) % 3。"""
    h = hashlib.sha256(f"{uid}:{arm_seed}".encode("utf-8")).hexdigest()
    return VARIANTS[int(h, 16) % 3]


def normalize_contact(contact: str) -> str:
    return " ".join(str(contact or "").strip().lower().split())


def contact_hash(contact: str) -> str:
    return hashlib.sha256(normalize_contact(contact).encode("utf-8")).hexdigest()


def normalize_variant(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    if s in VARIANTS:
        return s
    if s in ("1", "2", "3"):
        return f"V{s}"
    return None


def utm_from_flat(mapping: dict[str, Any]) -> dict[str, str]:
    mapping = mapping or {}
    out = {k: str(mapping.get(k) or "") for k in UTM_KEYS}
    out["utm_ref"] = str(mapping.get("ref") or mapping.get("utm_ref") or "")
    return out


def utm_from_query(query: dict[str, list[str]]) -> dict[str, str]:
    flat = {k: (v[0] if isinstance(v, list) and v else v) for k, v in (query or {}).items()}
    return utm_from_flat(flat)


def utm_from_referer(referer: str) -> dict[str, str]:
    if not referer:
        return utm_from_flat({})
    try:
        return utm_from_query(parse_qs(urlparse(referer).query))
    except Exception:  # noqa: BLE001
        return utm_from_flat({})


def merge_utm(*sources: dict[str, str]) -> dict[str, str]:
    out = utm_from_flat({})
    for src in sources:
        for k, v in (src or {}).items():
            if v:
                out[k] = v
    return out


# ---------------------------------------------------------------------------
# 存储层（每调用一条短连接 + 进程内写锁，够用且免第三方）
# ---------------------------------------------------------------------------
class Store:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._init()
        self.salt = self._load_salt()

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init(self) -> None:
        with self._lock, self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _load_salt(self) -> str:
        with self._lock, self.connect() as conn:
            row = conn.execute("SELECT value FROM meta_config WHERE key='ip_salt'").fetchone()
            if row:
                return row["value"]
            salt = secrets.token_hex(16)  # 首次启动随机生成、持久化，不写日志
            conn.execute("INSERT INTO meta_config(key, value) VALUES('ip_salt', ?)", (salt,))
            conn.commit()
            return salt

    def ip_hash(self, ip: str | None) -> str:
        return hashlib.sha256(f"{ip or ''}{self.salt}".encode("utf-8")).hexdigest()

    # -- assignments ----------------------------------------------------
    def get_assignment(self, visitor_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT variant FROM assignments WHERE visitor_id=?", (visitor_id,)
            ).fetchone()
            return row["variant"] if row else None

    def ensure_assignment(self, visitor_id: str) -> str:
        existing = self.get_assignment(visitor_id)
        if existing:
            return existing
        variant = assign(visitor_id)
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO assignments(visitor_id, variant, first_seen, forced_count)"
                " VALUES(?,?,?,0)",
                (visitor_id, variant, now_iso()),
            )
            conn.commit()
        return variant

    def bump_forced(self, visitor_id: str) -> None:
        with self._lock, self.connect() as conn:
            conn.execute(
                "UPDATE assignments SET forced_count = forced_count + 1 WHERE visitor_id=?",
                (visitor_id,),
            )
            conn.commit()

    # -- events ---------------------------------------------------------
    def record_event(
        self,
        *,
        event: str,
        asset: str,
        variant: str | None = None,
        naming: str | None = None,
        visitor_id: str | None = None,
        video_id: str | None = None,
        utm: dict[str, str] | None = None,
        meta: Any = None,
        ip: str | None = None,
        forced: int = 0,
    ) -> int:
        utm = utm_from_flat(utm or {})
        meta_json = json.dumps(meta, ensure_ascii=False) if meta is not None else None
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO events(ts,event,asset,variant,naming,visitor_id,video_id,"
                "utm_source,utm_medium,utm_campaign,utm_content,utm_ref,meta,ip_hash,forced)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    now_iso(), event, asset, variant, naming, visitor_id, video_id,
                    utm["utm_source"], utm["utm_medium"], utm["utm_campaign"],
                    utm["utm_content"], utm["utm_ref"], meta_json, self.ip_hash(ip), int(forced),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _counts(self, conn: sqlite3.Connection, asset: str, event: str) -> dict[str, int]:
        rows = conn.execute(
            "SELECT variant, COUNT(*) AS n FROM events WHERE asset=? AND event=? GROUP BY variant",
            (asset, event),
        ).fetchall()
        return {r["variant"]: r["n"] for r in rows}

    @staticmethod
    def _rate(num: int, den: int) -> float | None:
        return None if not den else round(num / den, 6)

    def stats(self, phase: str) -> dict[str, Any]:
        with self.connect() as conn:
            recruit_pv = self._counts(conn, "recruit", "page_view")
            recruit_cta = self._counts(conn, "recruit", "cta_click")
            recruit_sub = self._counts(conn, "recruit", "form_submit")
            share_pv = self._counts(conn, "share", "page_view")
            share_cta = self._counts(conn, "share", "cta_click")
            share_reg = self._counts(conn, "share", "register_click")
            naming_rows = conn.execute(
                "SELECT naming, event, COUNT(*) AS n FROM events"
                " WHERE naming IS NOT NULL AND naming != '' GROUP BY naming, event"
            ).fetchall()
            assign_rows = conn.execute(
                "SELECT variant, COUNT(*) AS n FROM assignments GROUP BY variant"
            ).fetchall()

        recruit: dict[str, Any] = {}
        for v in VARIANTS:
            pv, cta, sub = recruit_pv.get(v, 0), recruit_cta.get(v, 0), recruit_sub.get(v, 0)
            recruit[v] = {
                "page_view": pv,
                "cta_click": cta,
                "form_submit": sub,
                "cta_rate": self._rate(cta, pv),
                "submit_rate": self._rate(sub, pv),
            }

        share: dict[str, Any] = {}
        for v in VARIANTS:
            pv, cta, reg = share_pv.get(v, 0), share_cta.get(v, 0), share_reg.get(v, 0)
            share[v] = {
                "page_view": pv,
                "cta_click": cta,
                "register_click": reg,
                "cta_rate": self._rate(cta, pv),
                "register_rate": self._rate(reg, pv),
            }

        naming: dict[str, Any] = {}
        for row in naming_rows:
            slot = naming.setdefault(row["naming"], {"page_view": 0, "cta_click": 0})
            if row["event"] in slot:
                slot[row["event"]] = row["n"]
        for slot in naming.values():
            slot["cta_rate"] = self._rate(slot["cta_click"], slot["page_view"])

        recruit_total_pv = sum(recruit_pv.values())
        recruit_total_sub = sum(recruit_sub.values())
        sample = {
            "recruit_page_view": recruit_total_pv,
            "gate_300": recruit_total_pv >= 300,
            "gate_500": recruit_total_pv >= 500,
            "reached_300": recruit_total_pv >= 300,
            "reached_500": recruit_total_pv >= 500,
        }

        v1_rate = recruit["V1"]["submit_rate"]
        v2_rate = recruit["V2"]["submit_rate"]
        v3_rate = recruit["V3"]["submit_rate"]
        if None in (v1_rate, v2_rate, v3_rate):
            delta_pp: float | None = None
        else:
            delta_pp = round((v1_rate - max(v2_rate, v3_rate)) * 100, 2)

        submit_rate_ge_8pct = recruit_total_pv > 0 and (recruit_total_sub / recruit_total_pv) >= 0.08
        passed = bool(
            submit_rate_ge_8pct
            and delta_pp is not None
            and delta_pp >= 3.0
            and sample["recruit_page_view"] >= 300
        )

        assign_counts = {v: 0 for v in VARIANTS}
        for row in assign_rows:
            assign_counts[row["variant"]] = row["n"]
        pv_counts = [recruit_pv.get(v, 0) for v in VARIANTS]
        total = sum(pv_counts) or 1
        balance = {
            "recruit_page_view": {v: recruit_pv.get(v, 0) for v in VARIANTS},
            "share_page_view": {v: share_pv.get(v, 0) for v in VARIANTS},
            "assignments": assign_counts,
            "max_minus_min_pct": round((max(pv_counts) - min(pv_counts)) / total * 100, 2),
            "balanced": (max(pv_counts) - min(pv_counts)) <= max(1, round(total * 0.1)),
        }

        return {
            "phase": phase,
            "sample": sample,
            "by_variant": {"recruit": recruit, "share": share},
            "decision": {
                "submit_rate_ge_8pct": submit_rate_ge_8pct,
                "v1_minus_max_v2_v3_pp": delta_pp,
                "pass": passed,
            },
            "naming": naming,
            "balance": balance,
        }

    # -- leads ----------------------------------------------------------
    def create_lead(
        self, *, contact: str, variant: str | None, utm: dict[str, str],
        visitor_id: str | None,
    ) -> dict[str, Any]:
        chash = contact_hash(contact)
        now = now_iso()
        retention = (datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS)).isoformat(
            timespec="seconds"
        )
        utm = utm_from_flat(utm)
        with self._lock, self.connect() as conn:
            row = conn.execute("SELECT id FROM leads WHERE contact_hash=?", (chash,)).fetchone()
            if row:
                conn.execute("UPDATE leads SET last_seen=? WHERE id=?", (now, row["id"]))
                conn.commit()
                return {"lead_id": row["id"], "duplicated": True}
            cur = conn.execute(
                "INSERT INTO leads(created_at,last_seen,contact,contact_hash,consent_text_version,"
                "retention_until,variant,utm_source,utm_medium,utm_campaign,utm_content,utm_ref,"
                "visitor_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    now, now, contact, chash, CONSENT_TEXT_VERSION, retention, variant,
                    utm["utm_source"], utm["utm_medium"], utm["utm_campaign"],
                    utm["utm_content"], utm["utm_ref"], visitor_id,
                ),
            )
            conn.commit()
            return {"lead_id": int(cur.lastrowid), "duplicated": False}

    def withdraw(self, *, contact: str | None, visitor_id: str | None) -> int:
        now = now_iso()
        with self._lock, self.connect() as conn:
            if contact:
                cur = conn.execute(
                    "UPDATE leads SET withdrawn_at=?, contact=NULL"
                    " WHERE contact_hash=? AND withdrawn_at IS NULL",
                    (now, contact_hash(contact)),
                )
            elif visitor_id:
                cur = conn.execute(
                    "UPDATE leads SET withdrawn_at=?, contact=NULL"
                    " WHERE visitor_id=? AND withdrawn_at IS NULL",
                    (now, visitor_id),
                )
            else:
                return 0
            conn.commit()
            return int(cur.rowcount)

    def export_leads_csv(self) -> str:
        cols = [
            "id", "created_at", "last_seen", "contact", "contact_hash",
            "consent_text_version", "retention_until", "variant",
            "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_ref",
            "withdrawn_at",
        ]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(cols)
        with self.connect() as conn:
            for row in conn.execute(
                "SELECT " + ",".join(cols) + " FROM leads ORDER BY id"
            ).fetchall():
                record = dict(row)
                if record.get("withdrawn_at"):
                    record["contact"] = ""  # 撤回后不导出 contact 原文
                writer.writerow([record[c] if record[c] is not None else "" for c in cols])
        return buf.getvalue()


# ---------------------------------------------------------------------------
# 应用层
# ---------------------------------------------------------------------------
class Application:
    def __init__(
        self, db_path: str, phase: str, base_url: str,
        copy_pack: dict, export_token: str | None = None,
    ) -> None:
        self.store = Store(db_path)
        self.phase = phase
        self.base_url = base_url.rstrip("/")
        self.copy_pack = copy_pack
        self.export_token = export_token

    # -- 文案 -----------------------------------------------------------
    def recruit_node(self, variant: str) -> dict:
        return self.copy_pack["assets"]["recruit"]["variants"][variant].get(self.phase, {})

    def share_node(self, variant: str) -> dict:
        return self.copy_pack["assets"]["share"]["variants"][variant].get(self.phase, {})

    def recruit_form(self) -> dict:
        return self.copy_pack["assets"]["recruit"].get("form", {})

    def ui(self, asset: str) -> dict:
        """用户可见的界面文案（PRO-13 起从本文件的硬编码字符串抽到 copy_pack.json 的 ui.*）。

        这样「页面/脚本里用户能看到的每一句话」都与 assets/naming 一起受
        compliance.validate_copy_pack 扫描（闭合 PRO-12 §5 D-4）。
        """
        node = self.copy_pack.get("ui", {})
        return node.get(asset, {}) if isinstance(node, dict) else {}

    # -- 命名候选（第二批分流维度）--------------------------------------
    def naming_ids(self) -> tuple[str, ...]:
        """copy_pack.json 里已登记的命名候选 id（形如 A1/B2/C3）。"""
        node = self.copy_pack.get("naming_candidates", {})
        directions = node.get("directions", {}) if isinstance(node, dict) else {}
        ids: list[str] = []
        if isinstance(directions, dict):
            for direction in directions.values():
                for cand in (direction or {}).get("candidates", []) or []:
                    cid = cand.get("id")
                    if isinstance(cid, str) and cid:
                        ids.append(cid)
        return tuple(ids)

    def naming_candidate(self, naming_id: str | None) -> dict | None:
        """按 id 取候选：返回 {id, name, slogan}（slogan 取当前相位那一臂）；未登记则 None。

        PRO-13：原装置只在事件表里记 `naming` 字段，**页面从不渲染候选**，
        因此第二批的 cta_click 差异无法归因（PRO-12 §3.2 L-8）。本方法供渲染用。
        """
        if not naming_id or not isinstance(naming_id, str):
            return None
        node = self.copy_pack.get("naming_candidates", {})
        directions = node.get("directions", {}) if isinstance(node, dict) else {}
        if not isinstance(directions, dict):
            return None
        for direction in directions.values():
            for cand in (direction or {}).get("candidates", []) or []:
                if cand.get("id") == naming_id:
                    arm = cand.get(self.phase)
                    arm = arm if isinstance(arm, dict) else {}
                    return {
                        "id": cand.get("id", ""),
                        "name": cand.get("name", ""),
                        "slogan": arm.get("slogan"),
                    }
        return None


# ---------------------------------------------------------------------------
# HTML 渲染
# ---------------------------------------------------------------------------
_CSS = (
    "*{box-sizing:border-box}"
    "body{margin:0;font-family:system-ui,-apple-system,'Noto Sans CJK SC','PingFang SC',"
    "sans-serif;background:#0f1115;color:#e8eaed;line-height:1.6}"
    ".wrap{max-width:640px;margin:0 auto;padding:20px 18px 48px}"
    ".eyebrow{font-size:12px;letter-spacing:.06em;color:#8ab4f8}"
    "h1{font-size:24px;margin:12px 0 8px}"
    ".sub{color:#bdc1c6;margin:0 0 16px}"
    "ul{padding-left:20px;margin:0 0 20px}"
    "li{margin:8px 0}"
    ".cta{display:block;width:100%;padding:15px;border:0;border-radius:10px;background:#8ab4f8;"
    "color:#0f1115;font-size:16px;font-weight:700;cursor:pointer}"
    ".field{margin:14px 0}"
    "label.lbl{display:block;font-size:13px;color:#9aa0a6;margin-bottom:6px}"
    "input[type=text],input[type=tel],input[type=email]{width:100%;padding:13px;border-radius:8px;"
    "border:1px solid #3c4043;background:#1a1d21;color:#e8eaed;font-size:16px}"
    ".consent{display:flex;gap:8px;font-size:12px;color:#9aa0a6;margin:12px 0}"
    ".micro{font-size:12px;color:#9aa0a6;margin:8px 0 0;text-align:center}"
    ".result{font-size:13px;color:#81c995;min-height:18px;margin-top:10px}"
    "footer{font-size:12px;color:#9aa0a6;border-top:1px solid #2a2d31;margin-top:28px;padding-top:12px}"
    ".player{aspect-ratio:9/16;max-height:440px;background:#05070a;border-radius:14px;display:flex;"
    "flex-direction:column;align-items:center;justify-content:center;cursor:pointer;"
    "border:1px solid #2a2d31;color:#9aa0a6;user-select:none}"
    ".playbtn{font-size:54px;line-height:1;color:#8ab4f8}"
    ".vc{font-size:13px;color:#9aa0a6;margin:12px 0}"
    ".gate{margin-top:12px;padding:14px;border:1px solid #3c4043;border-radius:12px;background:#161a1f}"
    ".gate button{margin-top:10px;padding:10px 16px;border:0;border-radius:8px;background:#8ab4f8;"
    "color:#0f1115;font-weight:700;cursor:pointer}"
    ".naming{border:1px dashed #3c4043;border-radius:12px;padding:12px 14px;margin:0 0 18px}"
    ".naming h2{font-size:20px;margin:6px 0 4px}"
    ".naming-slogan{color:#bdc1c6;margin:0;font-size:14px}"
)

_RECRUIT_JS = """
(function(){
  var VARIANT = "__VARIANT__";
  var NAMING = "__NAMING__";
  function post(payload){
    try {
      return fetch('/api/events', {method:'POST', headers:{'Content-Type':'application/json'},
        keepalive:true, body:JSON.stringify(payload)});
    } catch(e){ return null; }
  }
  var btn = document.getElementById('submit-btn');
  if(btn){ btn.addEventListener('click', function(){
    post({event:'cta_click', asset:'recruit', variant:VARIANT, naming:NAMING || undefined});
  }); }
  var form = document.getElementById('lead-form');
  if(form){ form.addEventListener('submit', function(ev){
    ev.preventDefault();
    var contact = document.getElementById('contact').value.trim();
    var consent = document.getElementById('consent').checked;
    var box = document.getElementById('result');
    fetch('/api/lead', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({contact:contact, consent:consent, variant:VARIANT, naming:NAMING || undefined})})
      .then(function(r){ return r.json(); })
      .then(function(j){
        if(j && j.ok){
          box.style.color = '#81c995';
          box.textContent = j.duplicated ? "__UI_RESULT_DUPLICATE__" : "__UI_RESULT_OK__";
        } else {
          box.style.color = '#f28b82';
          box.textContent = "__UI_RESULT_ERROR_PREFIX__" + ((j && j.error) || "__UI_RESULT_ERROR_UNKNOWN__");
        }
      })
      .catch(function(){ box.style.color='#f28b82'; box.textContent='__UI_RESULT_NETWORK_ERROR__'; });
  }); }
})();
"""

_SHARE_JS = """
(function(){
  var VARIANT = "__VARIANT__";
  var VIDEO = "__VIDEO__";
  function post(payload){
    try { fetch('/api/events', {method:'POST', headers:{'Content-Type':'application/json'},
      keepalive:true, body:JSON.stringify(payload)}); } catch(e){}
  }
  var views = parseInt(sessionStorage.getItem('pd_share_views') || '0', 10);
  var vc = document.getElementById('vc');
  var gate = document.getElementById('gate');
  function render(){
    if(vc){ vc.textContent = '__UI_VIEWED_PREFIX__' + views + '__UI_VIEWED_SUFFIX__'; }
    if(gate && views >= 3){ gate.hidden = false; }
  }
  window.playOne = function(){
    views++;
    try { sessionStorage.setItem('pd_share_views', String(views)); } catch(e){}
    render();
    if(views === 3){ post({event:'view3', asset:'share', variant:VARIANT, video_id:VIDEO}); }
  };
  var reg = document.getElementById('reg-btn');
  if(reg){ reg.addEventListener('click', function(){
    post({event:'register_click', asset:'share', variant:VARIANT, video_id:VIDEO});
    reg.textContent = '__UI_REGISTER_DONE__';
  }); }
  render();
})();
"""


def _esc(text: Any) -> str:
    return (
        str(text if text is not None else "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _page(title: str, body: str, js: str) -> str:
    return (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<main class=\"wrap\">{body}</main><script>{js}</script></body></html>"
    )


def _ui_text(ui: dict, key: str) -> str:
    """取出界面文案；缺失时返回空串（缺失由启动门禁 fail-closed 拦住，见 REQUIRED_UI_KEYS）。"""
    value = ui.get(key)
    return value if isinstance(value, str) else ""


def _js_literal(text: str) -> str:
    """把文案安全嵌进单/双引号 JS 字面量（转义引号与反斜杠）。"""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def render_recruit(
    node: dict, form: dict, variant: str, phase: str, ui: dict | None = None,
    naming: dict | None = None,
) -> str:
    """招募假门页。

    naming：{id, name, slogan}。只有请求带已登记的 `naming` 参数时才渲染候选
    展示区——批次一（价值主张）不带该参数，因此不受影响；批次二（命名）靠这一段
    让被测者真的看到候选名/Slogan，否则 cta_click 无法归因（PRO-12 §3.2 L-8）。
    """
    ui = ui or {}
    bullets = "".join(f"<li>{_esc(b)}</li>" for b in node.get("bullets", []))
    field = (form.get("fields") or [{}])[0]
    consent_text = form.get("consent_text", "")
    naming_html = ""
    naming_id = ""
    if naming:
        slogan = naming.get("slogan")
        slogan_html = (
            f"<p class=\"naming-slogan\">{_esc(slogan)}</p>" if isinstance(slogan, str) and slogan else ""
        )
        naming_html = (
            f"<section class=\"naming\"><p class=\"eyebrow\">{_esc(_ui_text(ui, 'naming_label'))}</p>"
            f"<h2>{_esc(naming.get('name', ''))}</h2>{slogan_html}</section>"
        )
        naming_id = naming.get("id", "")
    body = (
        naming_html
        + f"<p class=\"eyebrow\">{_esc(node.get('eyebrow', ''))}</p>"
        f"<h1>{_esc(node.get('h1', ''))}</h1>"
        f"<p class=\"sub\">{_esc(node.get('sub', ''))}</p>"
        f"<ul>{bullets}</ul>"
        "<form id=\"lead-form\" novalidate>"
        f"<div class=\"field\"><label class=\"lbl\" for=\"contact\">{_esc(field.get('label', '联系方式'))}</label>"
        "<input id=\"contact\" name=\"contact\" type=\"text\" autocomplete=\"off\" required></div>"
        f"<label class=\"consent\"><input id=\"consent\" type=\"checkbox\" required>"
        f"<span>{_esc(consent_text)}</span></label>"
        f"<button id=\"submit-btn\" class=\"cta\" type=\"submit\">{_esc(node.get('cta_label', '提交申请'))}</button>"
        f"<p class=\"micro\">{_esc(node.get('cta_microcopy', ''))}</p>"
        "<p id=\"result\" class=\"result\"></p>"
        "</form>"
        f"<footer>{_esc(node.get('footer_note', ''))}<br>页面版本={_esc(phase)} · 变体={_esc(variant)}"
        f"{' · 候选=' + _esc(naming_id) if naming_id else ''}</footer>"
    )
    js = _RECRUIT_JS.replace("__VARIANT__", variant).replace("__NAMING__", _js_literal(naming_id))
    for placeholder, key in (
        ("__UI_RESULT_OK__", "result_ok"),
        ("__UI_RESULT_DUPLICATE__", "result_duplicate"),
        ("__UI_RESULT_ERROR_PREFIX__", "result_error_prefix"),
        ("__UI_RESULT_ERROR_UNKNOWN__", "result_error_unknown"),
        ("__UI_RESULT_NETWORK_ERROR__", "result_network_error"),
    ):
        js = js.replace(placeholder, _js_literal(_ui_text(ui, key)))
    return _page(node.get("h1", "内测名额申请"), body, js)


def render_share(node: dict, variant: str, phase: str, video_id: str, ui: dict | None = None) -> str:
    ui = ui or {}
    bullets = "".join(f"<li>{_esc(b)}</li>" for b in node.get("bullets", []))
    body = (
        f"<h1>{_esc(node.get('h1', ''))}</h1>"
        f"<p class=\"sub\">{_esc(node.get('sub', ''))}</p>"
        "<div class=\"player\" id=\"player\" onclick=\"playOne()\">"
        "<div class=\"playbtn\">▶</div>"
        f"<div>{_esc(_ui_text(ui, 'player_note'))}</div></div>"
        f"<p class=\"vc\" id=\"vc\">{_esc(_ui_text(ui, 'viewed_prefix'))}0{_esc(_ui_text(ui, 'viewed_suffix'))}</p>"
        f"<ul>{bullets}</ul>"
        "<div class=\"gate\" id=\"gate\" hidden>"
        f"{_esc(_ui_text(ui, 'gate_text'))}"
        f"<div><button id=\"reg-btn\" type=\"button\">{_esc(_ui_text(ui, 'register_button'))}</button></div></div>"
        f"<footer>视频={_esc(video_id)} · 页面版本={_esc(phase)} · 变体={_esc(variant)}</footer>"
    )
    js = _SHARE_JS.replace("__VARIANT__", variant).replace("__VIDEO__", json.dumps(video_id)[1:-1])
    for placeholder, key in (
        ("__UI_VIEWED_PREFIX__", "viewed_prefix"),
        ("__UI_VIEWED_SUFFIX__", "viewed_suffix"),
        ("__UI_REGISTER_DONE__", "register_done"),
    ):
        js = js.replace(placeholder, _js_literal(_ui_text(ui, key)))
    return _page(node.get("h1", "分享"), body, js)


# ---------------------------------------------------------------------------
# HTTP 层
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "PDPRO1/0.1"
    protocol_version = "HTTP/1.1"
    app: Application  # 由 serve() 注入

    # -- 基础工具 -------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # 静默：绝不打印 contact 原文
        if os.environ.get("PD_HTTP_LOG"):
            super().log_message(fmt, *args)

    def _cookies(self) -> dict[str, str]:
        raw = self.headers.get("Cookie") or ""
        out: dict[str, str] = {}
        for part in raw.split(";"):
            if "=" in part:
                key, _, value = part.partition("=")
                out[key.strip()] = value.strip()
        return out

    def _path(self) -> str:
        return urlparse(self.path).path.rstrip("/") or "/"

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    def _flat_query(self) -> dict[str, str]:
        return {k: (v[0] if v else "") for k, v in self._query().items()}

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"__invalid__": True}
        if not isinstance(data, dict):
            return {"__invalid__": True}
        return data

    def _send_json(self, payload: Any, status: int = 200, cookies: list[str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, cookies: list[str] | None = None, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, content_type: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _visitor(self) -> tuple[str, list[str]]:
        """取（或新建）pd_uid，返回 (uid, set_cookie 头列表)。"""
        uid = self._cookies().get("pd_uid")
        if uid:
            return uid, []
        uid = uuid.uuid4().hex
        cookie = f"pd_uid={uid}; Max-Age=2592000; Path=/; SameSite=Lax"
        return uid, [cookie]

    def _client_ip(self) -> str:
        return self.client_address[0] if self.client_address else ""

    # -- 路由 -----------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        """仅返回响应头（供 `curl -I` 核对 Set-Cookie），不写事件、不返回 body。"""
        path = self._path()
        uid, cookies = self._visitor()
        content_type = "application/json; charset=utf-8" if path.startswith("/api/") else "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", "0")
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self._path()
        try:
            if path == "/api/health":
                return self._send_json(
                    {"ok": True, "phase": self.app.phase, "db": self.app.store.db_path}
                )
            if path == "/api/stats":
                return self._send_json(self.app.store.stats(self.app.phase))
            if path == "/api/export/leads":
                return self._export_leads()
            if path == "/":
                return self._recruit_page(forced=None)
            if path.startswith("/v/"):
                forced = normalize_variant(path.split("/")[-1])
                if forced:
                    return self._recruit_page(forced=forced)
                return self._send_json({"ok": False, "error": "未知变体"}, status=404)
            if path.startswith("/s/"):
                return self._share_page(path[len("/s/"):])
            return self._send_json({"ok": False, "error": f"未找到路由 {path}"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": f"服务内部错误: {exc}"}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        path = self._path()
        body = self._read_json()
        try:
            if path == "/api/events":
                return self._post_events(body)
            if path == "/api/lead":
                return self._post_lead(body)
            if path == "/api/withdraw":
                return self._post_withdraw(body)
            return self._send_json({"ok": False, "error": f"未找到路由 {path}"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": f"服务内部错误: {exc}"}, status=500)

    # -- 页面 -----------------------------------------------------------
    def _recruit_page(self, forced: str | None) -> None:
        uid, cookies = self._visitor()
        assigned = self.app.store.ensure_assignment(uid)
        variant = forced or assigned
        node = self.app.recruit_node(variant)
        # 命名候选（第二批分流维度）：只接受 copy_pack 里已登记的 id，未登记视为未指定
        naming = self.app.naming_candidate(self._flat_query().get("naming"))
        html = render_recruit(
            node, self.app.recruit_form(), variant, self.app.phase, self.app.ui("recruit"), naming
        )
        self.app.store.record_event(
            event="page_view", asset="recruit", variant=variant, visitor_id=uid,
            naming=(naming or {}).get("id") or None,
            utm=utm_from_query(self._query()), ip=self._client_ip(),
            forced=1 if forced else 0,
        )
        if forced:
            self.app.store.bump_forced(uid)
        self._send_html(html, cookies=cookies)

    def _share_page(self, video_id: str) -> None:
        uid, cookies = self._visitor()
        assigned = self.app.store.ensure_assignment(uid)
        variant = normalize_variant(self._flat_query().get("v")) or assigned
        node = self.app.share_node(variant)
        html = render_share(node, variant, self.app.phase, video_id, self.app.ui("share"))
        self.app.store.record_event(
            event="page_view", asset="share", variant=variant, visitor_id=uid,
            video_id=video_id, utm=utm_from_query(self._query()), ip=self._client_ip(),
        )
        self._send_html(html, cookies=cookies)

    # -- API ------------------------------------------------------------
    def _post_events(self, body: dict[str, Any]) -> None:
        if body.get("__invalid__"):
            return self._send_json({"ok": False, "error": "请求体不是合法 JSON 对象"}, status=400)
        event = str(body.get("event") or "")
        if event not in ALLOWED_EVENTS:
            return self._send_json(
                {"ok": False, "error": f"event 非法，允许 {list(ALLOWED_EVENTS)}"}, status=400
            )
        asset = str(body.get("asset") or "")
        if not asset:
            return self._send_json({"ok": False, "error": "缺少 asset"}, status=400)
        uid, cookies = self._visitor()
        variant = normalize_variant(body.get("variant")) or self.app.store.ensure_assignment(uid)
        utm = merge_utm(
            body.get("meta") if isinstance(body.get("meta"), dict) else {},
            utm_from_flat({k: body.get(k) for k in (*UTM_KEYS, "ref")}),
            utm_from_referer(self.headers.get("Referer") or ""),
        )
        self.app.store.record_event(
            event=event, asset=asset, variant=variant,
            naming=(str(body["naming"]) if body.get("naming") else None),
            visitor_id=uid, video_id=(str(body["video_id"]) if body.get("video_id") else None),
            utm=utm, meta=body.get("meta"), ip=self._client_ip(),
        )
        self._send_json({"ok": True, "visitor_id": uid, "variant": variant}, cookies=cookies)

    def _post_lead(self, body: dict[str, Any]) -> None:
        if body.get("__invalid__"):
            return self._send_json({"ok": False, "error": "请求体不是合法 JSON 对象"}, status=400)
        contact = str(body.get("contact") or "").strip()
        consent = body.get("consent")
        consent_ok = consent is True or str(consent).lower() in ("true", "1", "yes", "on")
        if not contact:
            return self._send_json({"ok": False, "error": "contact 不能为空"}, status=400)
        if not consent_ok:
            return self._send_json({"ok": False, "error": "必须同意数据使用说明（consent=true）"}, status=400)
        uid, cookies = self._visitor()
        variant = normalize_variant(body.get("variant")) or self.app.store.ensure_assignment(uid)
        utm = merge_utm(
            {k: body.get(k) for k in (*UTM_KEYS, "ref")},
            utm_from_referer(self.headers.get("Referer") or ""),
        )
        result = self.app.store.create_lead(
            contact=contact, variant=variant, utm=utm, visitor_id=uid
        )
        if not result["duplicated"]:
            # 新留资才记一条 form_submit（重复提交不重复计数，保证分母口径）
            self.app.store.record_event(
                event="form_submit", asset="recruit", variant=variant, visitor_id=uid,
                utm=utm, ip=self._client_ip(),
            )
        self._send_json(
            {"ok": True, "lead_id": result["lead_id"], "duplicated": result["duplicated"]},
            cookies=cookies,
        )

    def _post_withdraw(self, body: dict[str, Any]) -> None:
        if body.get("__invalid__"):
            return self._send_json({"ok": False, "error": "请求体不是合法 JSON 对象"}, status=400)
        contact = str(body.get("contact") or "").strip() or None
        visitor_id = str(body.get("visitor_id") or "").strip() or None
        if not contact and not visitor_id:
            return self._send_json(
                {"ok": False, "error": "需要 contact 或 visitor_id"}, status=400
            )
        n = self.app.store.withdraw(contact=contact, visitor_id=visitor_id)
        self._send_json({"ok": True, "withdrawn": n})

    def _export_leads(self) -> None:
        if not self.app.export_token:
            return self._send_json({"ok": False, "error": "未启用导出"}, status=404)
        token = self._flat_query().get("token")
        if token != self.app.export_token:
            return self._send_json({"ok": False, "error": "token 无效"}, status=404)
        csv_text = self.app.store.export_leads_csv()
        self._send_text(csv_text, "text/csv; charset=utf-8")


# ---------------------------------------------------------------------------
# 启动 / 门禁
# ---------------------------------------------------------------------------
def load_copy_pack(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def compliance_gate(phase: str) -> list[dict]:
    """加载词表与文案包，跑合规校验；打印清单并返回全部发现。"""
    lexicon = compliance.load_lexicon(LEXICON_PATH)
    copy_pack = load_copy_pack(COPY_PACK_PATH)
    return compliance.validate_copy_pack(copy_pack, lexicon, phase)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="假门 / 分享落地页服务（纯标准库）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--db", default=os.path.join(ROOT, "marketing", "out", "landing.sqlite3"))
    parser.add_argument("--phase", choices=("pre_t0", "t0"), default="pre_t0")
    parser.add_argument(
        "--t0-evidence",
        default=os.environ.get("PD_T0_EVIDENCE") or None,
        help="t0 相位必填：T0 证据 JSON 路径（PRO-7 交付 + §0.3 八项前置全绿）。"
             "缺失或不合规则拒绝启动（exit 3）。模板：marketing/data/t0_evidence.template.json",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--export-token", default=None)
    return parser


def t0_evidence_gate(path: str | None) -> list[str]:
    """`--phase t0` 的前置校验：必须有 T0 已到的机器可读证据。

    返回问题清单（空 = 通过）。这是 PRO-12 §5 D-3 的装置层处置：
    把「T0 是否已到」从操作人记忆变成启动参数 + 证据文件。
    """
    problems: list[str] = []
    if not path:
        return ["未提供 --t0-evidence（T0 证据文件）"]
    if not os.path.isfile(path):
        return ["T0 证据文件不存在：%s" % path]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        return ["T0 证据文件不是合法 JSON：%s" % exc]
    if not isinstance(data, dict):
        return ["T0 证据文件必须是 JSON 对象"]
    for key in ("pro7_delivered", "preconditions_all_green"):
        if data.get(key) is not True:
            problems.append("证据字段 %s 必须为 true（当前：%r）" % (key, data.get(key)))
    preconditions = data.get("preconditions")
    if not isinstance(preconditions, list) or len(preconditions) < 8:
        problems.append(
            "证据字段 preconditions 必须列出 §0.3 的八项前置（当前：%s 项）"
            % (len(preconditions) if isinstance(preconditions, list) else 0)
        )
    if not data.get("evidence_date"):
        problems.append("证据字段 evidence_date 缺失（须写明证据采集日）")
    return problems


def check_required_ui_keys(copy_pack: dict) -> list[str]:
    """界面文案完整性（fail-closed）：缺失键会让页面出现占位符，必须拦住启动。"""
    problems: list[str] = []
    ui = copy_pack.get("ui")
    if not isinstance(ui, dict):
        return ["copy_pack.json 缺少 ui 节点（界面文案必须统一受合规扫描）"]
    for asset, keys in REQUIRED_UI_KEYS.items():
        node = ui.get(asset)
        if not isinstance(node, dict):
            problems.append("ui.%s 节点缺失" % asset)
            continue
        for key in keys:
            value = node.get(key)
            if not isinstance(value, str) or not value.strip():
                problems.append("ui.%s.%s 缺失或为空" % (asset, key))
    return problems


def serve(host: str, port: int, app: Application) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # 门禁 ②：t0 相位必须附 T0 证据（PRO-12 §5 D-3）
    if args.phase == "t0":
        t0_problems = t0_evidence_gate(args.t0_evidence)
        if t0_problems:
            print("[compliance] phase=t0 缺少有效的 T0 前置证据，拒绝启动（exit 3）：")
            for problem in t0_problems:
                print("  - %s" % problem)
            print("  说明：T0 = MVP 可灰度日（PRO-7 交付 + §0.3 八项前置全绿）。")
            print("  模板：marketing/data/t0_evidence.template.json")
            return 3
        print("[compliance] phase=t0 T0 前置证据校验通过：%s" % args.t0_evidence)

    findings = compliance_gate(args.phase)
    blocking = compliance.blocking_violations(findings)
    warnings = [f for f in findings if f.get("severity") == compliance.SEVERITY_REQUIRED]
    if findings:
        print(f"[compliance] phase={args.phase} 发现 {len(findings)} 项：")
        for item in findings:
            note = "（告警：不阻断启动）" if item["severity"] == compliance.SEVERITY_REQUIRED else "（禁投词）"
            print(
                f"  - [{item['severity']}] {item.get('json_path', '')} "
                f"id={item['id']} pattern={item.get('pattern', '')!r} "
                f"matched={item.get('matched', '')!r} {note}"
            )
    if blocking:
        print(f"[compliance] 命中硬禁词 {len(blocking)} 项，拒绝启动（exit 2）。")
        return 2
    if warnings:
        print(f"[compliance] 提示：{len(warnings)} 项 required_tokens 未在文案包中命中（不阻断）。")

    copy_pack = load_copy_pack(COPY_PACK_PATH)

    # 门禁 ③：界面文案完整性（fail-closed）
    ui_problems = check_required_ui_keys(copy_pack)
    if ui_problems:
        print("[compliance] 界面文案不完整，拒绝启动（exit 4）：")
        for problem in ui_problems:
            print("  - %s" % problem)
        return 4

    app = Application(
        db_path=args.db, phase=args.phase, base_url=args.base_url,
        copy_pack=copy_pack, export_token=args.export_token,
    )
    httpd = serve(args.host, args.port, app)
    print(f"[landing] phase={args.phase} db={args.db} 监听 http://{args.host}:{args.port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
