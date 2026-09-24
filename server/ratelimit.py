"""令牌桶限流器（FR-4.2）。

算法：token bucket。每个 `(endpoint_class, key)` 一个桶，容量 = 规则容量，
按 `容量 / 窗口秒` 的速率匀速补充。桶初始为满（允许突发 = 容量）。

为什么用令牌桶而不是固定窗口计数：
- 固定窗口在窗口边界可被"两倍突发"击穿（59s 一次 + 61s 一次 = 2 倍速率）；
- 令牌桶天然平滑突发，且能给出有意义的 `Retry-After`（下一次有令牌的时间）。

已知限制（必须显式登记，不假装没有）：单进程内存实现，多实例不共享 ——
水平扩展时必须迁 Redis（PRD §六 / 已知限制）。
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass


@dataclass
class Decision:
    """一次限流判定的结果（可序列化为 429 响应头）。"""

    allowed: bool
    limit: int
    remaining: int
    reset_after: float      # 距离下一次有令牌的秒数（向上取整后给 Retry-After）
    rule_key: str = ""

    @property
    def retry_after(self) -> int:
        return max(1, int(math.ceil(self.reset_after)))


class TokenBucket:
    """单个桶：容量 `capacity`，窗口 `window_s` 秒内匀速补满。"""

    __slots__ = ("capacity", "window_s", "_tokens", "_updated")

    def __init__(self, capacity: int, window_s: float, now: float) -> None:
        self.capacity = max(1, int(capacity))
        self.window_s = max(0.001, float(window_s))
        self._tokens = float(self.capacity)
        self._updated = now

    def _refill(self, now: float) -> None:
        rate = self.capacity / self.window_s            # 每秒补充的令牌数
        self._tokens = min(float(self.capacity), self._tokens + (now - self._updated) * rate)
        self._updated = now

    def consume(self, now: float) -> Decision:
        self._refill(now)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return Decision(True, self.capacity, int(self._tokens), 0.0)
        wait = (1.0 - self._tokens) / (self.capacity / self.window_s)
        return Decision(False, self.capacity, 0, wait)

    def peek_reset(self, now: float) -> float:
        self._refill(now)
        if self._tokens >= 1.0:
            return 0.0
        return (1.0 - self._tokens) / (self.capacity / self.window_s)


class RateLimiter:
    """多规则、多键的令牌桶集合。

    线程安全：全局单锁（临界区只有字典读写，开销远小于一次 SQLite 查询）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str, str], TokenBucket] = {}
        self.hits_total: int = 0        # 放行计数（可观测）
        self.limited_total: int = 0     # 拒绝计数（`rate_limited_total{endpoint}`）

    def check(
        self,
        endpoint_class: str,
        rules: dict[str, tuple[int, float]],
        *,
        user_id: str | None,
        client_ip: str,
        enabled: bool = True,
        global_rules: dict[str, tuple[int, float]] | None = None,
        now: float | None = None,
    ) -> Decision:
        """按规则逐条判定；任一规则超限即拒绝（返回该规则的 Decision）。

        `user` / `user_day` 键在未鉴权时跳过（没有身份就没有用户级额度），
        IP 规则始终生效 —— 这正是"免鉴权不等于免限流"的落点。
        """
        if not enabled:
            return Decision(allowed=True, limit=0, remaining=0, reset_after=0.0)

        ts = time.time() if now is None else now
        candidates: list[tuple[str, str, int, float]] = []
        for rule_key, (limit, window) in dict(rules or {}).items():
            if rule_key.startswith("user"):
                if not user_id:
                    continue
                subject = user_id
            else:
                subject = client_ip
            candidates.append((rule_key, subject, int(limit), float(window)))

        if global_rules:
            for rule_key, (limit, window) in global_rules.items():
                candidates.append((f"global:{rule_key}", client_ip, int(limit), float(window)))

        with self._lock:
            decisions: list[Decision] = []
            for rule_key, subject, limit, window in candidates:
                bucket = self._buckets.get((endpoint_class, rule_key, subject))
                if bucket is None or bucket.capacity != limit or bucket.window_s != window:
                    bucket = TokenBucket(limit, window, ts)
                    self._buckets[(endpoint_class, rule_key, subject)] = bucket
                dec = bucket.consume(ts)
                dec.rule_key = rule_key
                decisions.append(dec)
                if not dec.allowed:
                    break  # 已超限：后续规则不再消耗额度（最短拒绝路径）

        allowed = all(d.allowed for d in decisions)
        if allowed:
            self.hits_total += 1
        else:
            self.limited_total += 1
        if not decisions:
            return Decision(allowed=True, limit=0, remaining=0, reset_after=0.0)
        return next((d for d in decisions if not d.allowed), decisions[-1])

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self.hits_total = 0
            self.limited_total = 0
