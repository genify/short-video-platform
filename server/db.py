"""SQLite 持久层：用户、视频、行为埋点、关注关系、视频统计与物品相似度缓存。

不使用任何第三方依赖（环境无 ORM 可用），全部走标准库 sqlite3。
线程安全策略：连接按线程隔离（threading.local），写操作走单写锁 + WAL 模式。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Iterable, Sequence

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    handle      TEXT NOT NULL UNIQUE,
    display     TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL
);

-- FR-3.1：账号凭据与会话令牌（只存 sha256，永不存明文）
CREATE TABLE IF NOT EXISTS user_tokens (
    token_hash   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   REAL NOT NULL,
    expires_at   REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    revoked      INTEGER NOT NULL DEFAULT 0,
    auth_level   TEXT NOT NULL DEFAULT 'dev'
);
CREATE INDEX IF NOT EXISTS idx_user_tokens_user ON user_tokens(user_id);

CREATE TABLE IF NOT EXISTS videos (
    id           TEXT PRIMARY KEY,
    creator_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    caption      TEXT NOT NULL DEFAULT '',
    tags         TEXT NOT NULL DEFAULT '[]',      -- JSON 数组
    duration_ms  INTEGER NOT NULL DEFAULT 0,
    width        INTEGER NOT NULL DEFAULT 0,
    height       INTEGER NOT NULL DEFAULT 0,
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    sha256       TEXT NOT NULL DEFAULT '',
    storage_path TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'published', -- published|hidden|removed
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_videos_creator ON videos(creator_id);
CREATE INDEX IF NOT EXISTS idx_videos_created ON videos(created_at DESC);

CREATE TABLE IF NOT EXISTS engagements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    video_id   TEXT NOT NULL,
    kind       TEXT NOT NULL,          -- view|complete|like|share|follow|skip|comment
    watch_ms   INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eng_user ON engagements(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_eng_video ON engagements(video_id);

CREATE TABLE IF NOT EXISTS follows (
    follower_id TEXT NOT NULL,
    followee_id TEXT NOT NULL,
    created_at  REAL NOT NULL,
    PRIMARY KEY (follower_id, followee_id)
);

-- 反规范化计数器：推荐打分需要高频读取，避免每次聚合扫描
CREATE TABLE IF NOT EXISTS video_stats (
    video_id    TEXT PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
    views       INTEGER NOT NULL DEFAULT 0,
    completes   INTEGER NOT NULL DEFAULT 0,
    likes       INTEGER NOT NULL DEFAULT 0,
    shares      INTEGER NOT NULL DEFAULT 0,
    comments    INTEGER NOT NULL DEFAULT 0,
    skips       INTEGER NOT NULL DEFAULT 0,
    watch_ms    INTEGER NOT NULL DEFAULT 0,
    updated_at  REAL NOT NULL
);

-- item-item 协同过滤相似度缓存（由后台任务或 /api/admin/rebuild-cf 触发重建）
CREATE TABLE IF NOT EXISTS item_sim (
    video_a    TEXT NOT NULL,
    video_b    TEXT NOT NULL,
    co_users   INTEGER NOT NULL DEFAULT 0,
    score      REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (video_a, video_b)
);
CREATE INDEX IF NOT EXISTS idx_itemsim_a ON item_sim(video_a);
"""


class Database:
    """轻量数据访问层。"""

    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self._init_schema()

    # -- 连接管理 ---------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            if self.path != ":memory:":
                conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        with self._write_lock:
            conn = self.connect()
            conn.executescript(SCHEMA)
            self._migrate(conn)

    # 幂等增量迁移：老库（无这些列）升级到新 schema 时补齐，新库无操作。
    # 为什么不用 `ALTER TABLE ... IF NOT EXISTS`：SQLite 不支持该语法，
    # 只能先查 PRAGMA table_info 再决定是否加列 —— 重复执行必须安全。
    _MIGRATIONS: tuple[tuple[str, str, str], ...] = (
        ("users", "interest_tags", "TEXT NOT NULL DEFAULT '[]'"),
        ("users", "source", "TEXT NOT NULL DEFAULT ''"),
    )

    def _migrate(self, conn: sqlite3.Connection) -> None:
        for table, column, ddl in self._MIGRATIONS:
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # -- 写操作 -----------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self._write_lock:
            self.connect().execute(sql, params)

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self._write_lock:
            self.connect().executemany(sql, rows)

    # -- 读操作 -----------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return self.connect().execute(sql, params).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self.connect().execute(sql, params).fetchone()

    # ------------------------------------------------------------------
    # 用户
    # ------------------------------------------------------------------
    def create_user(
        self,
        user_id: str,
        handle: str,
        display: str = "",
        interest_tags: Sequence[str] | None = None,
        source: str = "",
    ) -> dict[str, Any]:
        now = time.time()
        tags = json.dumps(list(interest_tags or []), ensure_ascii=False)
        self.execute(
            """INSERT OR IGNORE INTO users(id, handle, display, created_at, interest_tags, source)
               VALUES(?,?,?,?,?,?)""",
            (user_id, handle, display or handle, now, tags, source or ""),
        )
        return self.get_user(user_id) or {}

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = self.query_one("SELECT * FROM users WHERE id=?", (user_id,))
        return _user_row_to_dict(row) if row else None

    def get_user_by_handle(self, handle: str) -> dict[str, Any] | None:
        row = self.query_one("SELECT * FROM users WHERE handle=?", (handle,))
        return _user_row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # 会话令牌（FR-3.1；只存 sha256）
    # ------------------------------------------------------------------
    def create_token(
        self,
        token_hash: str,
        user_id: str,
        ttl_days: float,
        auth_level: str = "dev",
    ) -> dict[str, Any]:
        now = time.time()
        expires_at = now + float(ttl_days) * 86400.0
        self.execute(
            """INSERT INTO user_tokens(token_hash, user_id, created_at, expires_at,
                                       last_seen_at, revoked, auth_level)
               VALUES(?,?,?,?,?,0,?)""",
            (token_hash, user_id, now, expires_at, now, auth_level),
        )
        return {"user_id": user_id, "created_at": now, "expires_at": expires_at,
                "auth_level": auth_level}

    def get_token(self, token_hash: str) -> dict[str, Any] | None:
        """按摘要取令牌记录（含用户是否仍存在），供鉴权层判 401/过期。"""
        row = self.query_one(
            """SELECT t.*, (SELECT 1 FROM users u WHERE u.id = t.user_id) AS user_exists,
                      (SELECT u.handle FROM users u WHERE u.id = t.user_id) AS handle
               FROM user_tokens t WHERE t.token_hash=?""",
            (token_hash,),
        )
        if not row:
            return None
        data = dict(row)
        data["user_exists"] = bool(data.get("user_exists"))
        return data

    def touch_token(self, token_hash: str, when: float | None = None) -> None:
        self.execute(
            "UPDATE user_tokens SET last_seen_at=? WHERE token_hash=?",
            (time.time() if when is None else when, token_hash),
        )

    def revoke_token(self, token_hash: str) -> bool:
        row = self.get_token(token_hash)
        if not row:
            return False
        self.execute("UPDATE user_tokens SET revoked=1 WHERE token_hash=?", (token_hash,))
        return True

    def count_active_tokens(self, user_id: str) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS c FROM user_tokens WHERE user_id=? AND revoked=0",
            (user_id,),
        )
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------
    # 视频
    # ------------------------------------------------------------------
    def create_video(
        self,
        video_id: str,
        creator_id: str,
        caption: str,
        tags: Sequence[str],
        duration_ms: int,
        width: int,
        height: int,
        size_bytes: int,
        sha256: str,
        storage_path: str,
    ) -> dict[str, Any]:
        now = time.time()
        with self._write_lock:
            conn = self.connect()
            conn.execute(
                """INSERT INTO videos(id, creator_id, caption, tags, duration_ms, width,
                       height, size_bytes, sha256, storage_path, status, created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?, 'published', ?)""",
                (
                    video_id, creator_id, caption, json.dumps(list(tags), ensure_ascii=False),
                    int(duration_ms), int(width), int(height), int(size_bytes),
                    sha256, storage_path, now,
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO video_stats(video_id, updated_at) VALUES(?,?)",
                (video_id, now),
            )
        return self.get_video(video_id) or {}

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        row = self.query_one(
            """SELECT v.*, s.views, s.completes, s.likes, s.shares, s.comments,
                      s.skips, s.watch_ms
               FROM videos v LEFT JOIN video_stats s ON s.video_id = v.id
               WHERE v.id=?""",
            (video_id,),
        )
        return _video_row_to_dict(row) if row else None

    def list_videos_by_creator(self, creator_id: str) -> list[dict[str, Any]]:
        rows = self.query(
            """SELECT v.*, s.views, s.completes, s.likes, s.shares, s.comments,
                      s.skips, s.watch_ms
               FROM videos v LEFT JOIN video_stats s ON s.video_id = v.id
               WHERE v.creator_id=? AND v.status='published'
               ORDER BY v.created_at DESC""",
            (creator_id,),
        )
        return [_video_row_to_dict(r) for r in rows]

    def list_all_videos(self) -> list[dict[str, Any]]:
        rows = self.query(
            """SELECT v.*, s.views, s.completes, s.likes, s.shares, s.comments,
                      s.skips, s.watch_ms
               FROM videos v LEFT JOIN video_stats s ON s.video_id = v.id
               WHERE v.status='published'
               ORDER BY v.created_at DESC""",
        )
        return [_video_row_to_dict(r) for r in rows]

    def hash_exists(self, sha256: str) -> dict[str, Any] | None:
        row = self.query_one("SELECT id FROM videos WHERE sha256=? AND sha256<>''", (sha256,))
        return self.get_video(row["id"]) if row else None

    # ------------------------------------------------------------------
    # 行为埋点 / 关注
    # ------------------------------------------------------------------
    def add_engagement(
        self,
        user_id: str,
        video_id: str,
        kind: str,
        watch_ms: int = 0,
        created_at: float | None = None,
    ) -> None:
        now = created_at if created_at is not None else time.time()
        counter_col = {
            "view": "views",
            "complete": "completes",
            "like": "likes",
            "share": "shares",
            "comment": "comments",
            "skip": "skips",
        }.get(kind)
        with self._write_lock:
            conn = self.connect()
            conn.execute(
                "INSERT INTO engagements(user_id, video_id, kind, watch_ms, created_at) VALUES(?,?,?,?,?)",
                (user_id, video_id, kind, int(watch_ms), now),
            )
            if counter_col:
                conn.execute(
                    f"""INSERT INTO video_stats(video_id, {counter_col}, watch_ms, updated_at)
                        VALUES(?,?,?,?)
                        ON CONFLICT(video_id) DO UPDATE SET
                          {counter_col} = {counter_col} + excluded.{counter_col},
                          watch_ms = watch_ms + excluded.watch_ms,
                          updated_at = excluded.updated_at""",
                    (video_id, 1, int(watch_ms), now),
                )

    def add_follow(self, follower_id: str, followee_id: str) -> None:
        self.execute(
            "INSERT OR IGNORE INTO follows(follower_id, followee_id, created_at) VALUES(?,?,?)",
            (follower_id, followee_id, time.time()),
        )

    def following_ids(self, user_id: str) -> set[str]:
        return {
            r["followee_id"]
            for r in self.query("SELECT followee_id FROM follows WHERE follower_id=?", (user_id,))
        }

    def user_engagements(self, user_id: str, limit: int = 500) -> list[dict[str, Any]]:
        rows = self.query(
            """SELECT video_id, kind, watch_ms, created_at FROM engagements
               WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        )
        return [dict(r) for r in rows]

    def user_seen_video_ids(self, user_id: str, since_ts: float) -> set[str]:
        return {
            r["video_id"]
            for r in self.query(
                "SELECT DISTINCT video_id FROM engagements WHERE user_id=? AND created_at>=?",
                (user_id, since_ts),
            )
        }

    def user_engagement_count(self, user_id: str) -> int:
        row = self.query_one("SELECT COUNT(*) AS c FROM engagements WHERE user_id=?", (user_id,))
        return int(row["c"]) if row else 0

    def max_engagement_total(self) -> int:
        row = self.query_one(
            """SELECT MAX(views + 2*completes + 3*likes + 5*shares) AS m FROM video_stats"""
        )
        return int(row["m"]) if row and row["m"] else 0

    # ------------------------------------------------------------------
    # item-item 协同过滤
    # ------------------------------------------------------------------
    def rebuild_item_similarity(self) -> int:
        """基于共同互动用户重建 item-item 相似度（余弦口径，含 Swing 冷启动回退）。

        相似度定义为 co_users / sqrt(pop_a * pop_b)，即共现余弦的常用近似，
        对小样本稳定且可解释。
        """
        now = time.time()
        rows = self.query(
            """WITH co AS (
                   SELECT a.video_id AS va, b.video_id AS vb, COUNT(DISTINCT a.user_id) AS c
                   FROM engagements a
                   JOIN engagements b
                     ON a.user_id = b.user_id AND a.video_id <> b.video_id
                   GROUP BY a.video_id, b.video_id
               ),
               pop AS (SELECT video_id, COUNT(DISTINCT user_id) AS p
                       FROM engagements GROUP BY video_id)
               SELECT co.va, co.vb, co.c, pop_a.p AS pa, pop_b.p AS pb
               FROM co
               JOIN pop pop_a ON pop_a.video_id = co.va
               JOIN pop pop_b ON pop_b.video_id = co.vb
               WHERE co.c >= 1"""
        )
        payload = [
            (
                r["va"], r["vb"], int(r["c"]),
                float(r["c"]) / max(1.0, (float(r["pa"]) * float(r["pb"])) ** 0.5),
                now,
            )
            for r in rows
        ]
        with self._write_lock:
            conn = self.connect()
            conn.execute("DELETE FROM item_sim")
            conn.executemany(
                "INSERT OR REPLACE INTO item_sim(video_a, video_b, co_users, score, updated_at) VALUES(?,?,?,?,?)",
                payload,
            )
        return len(payload)

    def item_similarity(self, video_ids: Sequence[str], limit_per_item: int = 50) -> dict[str, list[tuple[str, float]]]:
        """返回 {源视频: [(相似视频, 分数), ...]}，用于 CF 召回。"""
        out: dict[str, list[tuple[str, float]]] = {}
        for vid in video_ids:
            rows = self.query(
                """SELECT video_b, score FROM item_sim WHERE video_a=?
                   ORDER BY score DESC LIMIT ?""",
                (vid, limit_per_item),
            )
            out[vid] = [(r["video_b"], float(r["score"])) for r in rows]
        return out

    def creator_second_hop(self, user_id: str) -> set[str]:
        """二跳社交：我关注的人所关注的创作者（弱社交信号）。"""
        rows = self.query(
            """SELECT DISTINCT f2.followee_id AS cid
               FROM follows f1 JOIN follows f2 ON f1.followee_id = f2.follower_id
               WHERE f1.follower_id=? AND f2.followee_id<>?""",
            (user_id, user_id),
        )
        return {r["cid"] for r in rows}


def _user_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["interest_tags"] = json.loads(d.get("interest_tags") or "[]")
    except (TypeError, ValueError):
        d["interest_tags"] = []
    return d


def _video_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except (TypeError, ValueError):
        d["tags"] = []
    for k in ("views", "completes", "likes", "shares", "comments", "skips", "watch_ms"):
        d.setdefault(k, 0)
        d[k] = d[k] or 0
    return d
