"""推荐流引擎：多路召回 -> 线性加权排序 -> MMR 多样性重排。

严格实现 docs/03-recommendation-design.md 的设计：

    S = w_aff*Aff + w_pop*Pop + w_fresh*Fresh + w_social*Social + w_qual*Qual
    重排：MMR(λ=0.7) + 创作者打散 + ε-greedy 探索

关键工程约束：新平台行为稀疏，因此协同过滤只做补充；内容标签匹配、
热门新鲜与冷启动兜底是一等公民，任何缺失特征都必须有降级路径。
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from . import config


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class Candidate:
    video: dict[str, Any]
    routes: set[str] = field(default_factory=set)
    route_score: float = 0.0
    features: dict[str, float] = field(default_factory=dict)
    score: float = 0.0

    @property
    def video_id(self) -> str:
        return self.video["id"]

    @property
    def creator_id(self) -> str:
        return self.video["creator_id"]

    @property
    def tags(self) -> list[str]:
        return list(self.video.get("tags") or [])


@dataclass
class FeedItem:
    video: dict[str, Any]
    score: float
    features: dict[str, float]
    routes: list[str]
    reason: str


# ---------------------------------------------------------------------------
# 特征工具
# ---------------------------------------------------------------------------
def _l2_normalize(vec: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm <= 1e-12:
        return {}
    return {k: v / norm for k, v in vec.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(k, 0.0) for k, w in a.items())


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _video_tag_vector(video: dict[str, Any]) -> dict[str, float]:
    """视频标签向量：按标签数归一化的 one-hot（多标签等权）。"""
    tags = [t for t in (video.get("tags") or [])]
    if not tags:
        return {}
    w = 1.0 / len(tags)
    vec: dict[str, float] = {}
    for t in tags:
        vec[t] = vec.get(t, 0.0) + w
    return _l2_normalize(vec)


def _engagement_total(video: dict[str, Any]) -> float:
    return (
        1.0 * float(video.get("views") or 0)
        + 2.0 * float(video.get("completes") or 0)
        + 3.0 * float(video.get("likes") or 0)
        + 5.0 * float(video.get("shares") or 0)
    )


# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------
class RecommendEngine:
    def __init__(self, db, weights: dict[str, float] | None = None) -> None:
        self.db = db
        self.weights = dict(weights or config.RANK_WEIGHTS)

    # ------------------------------------------------------------------
    # 用户画像
    # ------------------------------------------------------------------
    def user_tag_profile(self, user_id: str, engagements: Sequence[dict[str, Any]] | None = None) -> dict[str, float]:
        """由历史行为构建标签兴趣向量（行为价值加权）。"""
        engs = list(engagements if engagements is not None else self.db.user_engagements(user_id))
        profile: dict[str, float] = {}
        for e in engs:
            video = self.db.get_video(e["video_id"])
            if not video:
                continue
            weight = config.ACTION_VALUE.get(e["kind"], 1.0)
            tv = _video_tag_vector(video)
            for tag, tv_w in tv.items():
                profile[tag] = profile.get(tag, 0.0) + weight * tv_w
        profile = {k: v for k, v in profile.items() if v > 0}
        return _l2_normalize(profile)

    def user_creator_affinity(self, engagements: Sequence[dict[str, Any]]) -> dict[str, float]:
        aff: dict[str, float] = {}
        for e in engagements:
            video = self.db.get_video(e["video_id"])
            if not video:
                continue
            w = max(0.0, config.ACTION_VALUE.get(e["kind"], 1.0))
            aff[video["creator_id"]] = aff.get(video["creator_id"], 0.0) + w
        return aff

    # ------------------------------------------------------------------
    # 多路召回
    # ------------------------------------------------------------------
    def recall(
        self,
        user_id: str,
        engagements: Sequence[dict[str, Any]],
        library: Sequence[dict[str, Any]],
        seen: set[str],
    ) -> dict[str, list[tuple[str, float]]]:
        by_id = {v["id"]: v for v in library}
        routes: dict[str, list[tuple[str, float]]] = {
            "cf": [], "follow": [], "fresh": [], "tag": [], "fallback": []
        }

        engaged_ids = [e["video_id"] for e in engagements]
        profile = self.user_tag_profile(user_id, engagements)
        following = self.db.following_ids(user_id)
        second_hop = self.db.creator_second_hop(user_id) if following else set()
        now = time.time()

        # 路由 1：item-item 协同过滤
        sim_map = self.db.item_similarity(engaged_ids, limit_per_item=50) if engaged_ids else {}
        cf_scores: dict[str, float] = {}
        for src_id, neighbours in sim_map.items():
            if src_id in seen:
                continue
            for nid, sim in neighbours:
                if nid in seen or nid not in by_id:
                    continue
                cf_scores[nid] = cf_scores.get(nid, 0.0) + sim
        routes["cf"] = sorted(cf_scores.items(), key=lambda kv: kv[1], reverse=True)

        # 路由 2：关注创作者（按新鲜度权重）
        follow_scores: dict[str, float] = {}
        for vid, video in by_id.items():
            if vid in seen:
                continue
            if video["creator_id"] in following:
                follow_scores[vid] = 1.0 + 0.5 * self._freshness(video, now)
        routes["follow"] = sorted(follow_scores.items(), key=lambda kv: kv[1], reverse=True)

        # 路由 3：热门新鲜（Hacker News 式重力衰减）
        max_total = max(1.0, float(self.db.max_engagement_total()))
        fresh_scores: dict[str, float] = {}
        for vid, video in by_id.items():
            if vid in seen:
                continue
            total = _engagement_total(video)
            age_h = max(0.0, (now - float(video["created_at"])) / 3600.0)
            hn = (total / max_total) / math.pow(age_h + 2.0, 1.2)
            if hn > 0:
                fresh_scores[vid] = hn
        routes["fresh"] = sorted(fresh_scores.items(), key=lambda kv: kv[1], reverse=True)

        # 路由 4：标签内容匹配（新平台的个性化主力）
        tag_scores: dict[str, float] = {}
        if profile:
            for vid, video in by_id.items():
                if vid in seen:
                    continue
                aff = _cosine(profile, _video_tag_vector(video))
                if aff > 0:
                    tag_scores[vid] = aff * (0.5 + 0.5 * self._freshness(video, now))
        tag_scores = self._exclude_routed(tag_scores, follow_scores, "tag")
        routes["tag"] = sorted(tag_scores.items(), key=lambda kv: kv[1], reverse=True)

        # 路由 5：冷启动兜底（全库热度）
        fb_scores: dict[str, float] = {}
        for vid, video in by_id.items():
            if vid in seen:
                continue
            fb_scores[vid] = _engagement_total(video) / max_total
        routes["fallback"] = sorted(fb_scores.items(), key=lambda kv: kv[1], reverse=True)

        return routes

    @staticmethod
    def _exclude_routed(
        scores: dict[str, float], other: dict[str, float], tag: str
    ) -> dict[str, float]:
        """标签路由不重复贡献已有更强社交信号的候选（减少重复曝光）。"""
        return {k: v for k, v in scores.items() if k not in other or v > other[k]}

    # ------------------------------------------------------------------
    # 特征与排序
    # ------------------------------------------------------------------
    def _freshness(self, video: dict[str, Any], now: float) -> float:
        age_h = max(0.0, (now - float(video["created_at"])) / 3600.0)
        return math.pow(0.5, age_h / max(1.0, config.FRESH_HALF_LIFE_HOURS))

    def _quality(self, video: dict[str, Any]) -> float:
        views = float(video.get("views") or 0)
        if views <= 0:
            return 0.0
        completion = min(1.0, (float(video.get("completes") or 0) / views) / config.REF_COMPLETION_RATE)
        like = min(1.0, (float(video.get("likes") or 0) / views) / config.REF_LIKE_RATE)
        return 0.6 * completion + 0.4 * like

    def features(
        self,
        user_id: str,
        cand: Candidate,
        *,
        profile: dict[str, float],
        following: set[str],
        second_hop: set[str],
        max_total: float,
        now: float,
        seen_video_ids: set[str] | None = None,
    ) -> dict[str, float]:
        video = cand.video
        aff = _cosine(profile, _video_tag_vector(video))
        pop = math.log1p(_engagement_total(video)) / math.log1p(max(1.0, max_total))
        fresh = self._freshness(video, now)
        creator = video["creator_id"]
        if creator in following:
            social = 1.0
        elif creator in second_hop:
            social = 0.5
        else:
            social = 0.0
        qual = self._quality(video)
        return {
            "aff": round(aff, 6),
            "pop": round(pop, 6),
            "fresh": round(fresh, 6),
            "social": round(social, 6),
            "qual": round(qual, 6),
        }

    def score(self, feats: dict[str, float]) -> float:
        w = self.weights
        return round(
            w["aff"] * feats["aff"]
            + w["pop"] * feats["pop"]
            + w["fresh"] * feats["fresh"]
            + w["social"] * feats["social"]
            + w["qual"] * feats["qual"],
            6,
        )

    # ------------------------------------------------------------------
    # 重排
    # ------------------------------------------------------------------
    def rerank(
        self,
        ranked: Sequence[Candidate],
        size: int,
        *,
        lam: float = config.MMR_LAMBDA,
        seed: int | None = None,
    ) -> list[Candidate]:
        """MMR 多样性重排 + 创作者打散 + ε-greedy 探索位。"""
        if not ranked:
            return []
        # 先按相关性降序，探索位在这里做替换决策
        pool = sorted(ranked, key=lambda c: c.score, reverse=True)
        selected: list[Candidate] = []
        creator_count: dict[str, int] = {}
        rng = random.Random(seed if seed is not None else 0)

        while pool and len(selected) < size:
            best: Candidate | None = None
            best_mmr = -math.inf
            for cand in pool:
                if creator_count.get(cand.creator_id, 0) >= config.CREATOR_CAP_PER_FEED:
                    continue
                redundancy = max(
                    (_jaccard(cand.tags, s.tags) for s in selected), default=0.0
                )
                mmr = lam * cand.score - (1.0 - lam) * redundancy
                if mmr > best_mmr:
                    best_mmr = mmr
                    best = cand
            if best is None:
                # 全部被创作者上限挡住 -> 放宽限制补位，避免 feed 长度不足
                creator_count.clear()
                continue
            selected.append(best)
            creator_count[best.creator_id] = creator_count.get(best.creator_id, 0) + 1
            pool.remove(best)

        return selected

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def feed(
        self,
        user_id: str,
        size: int = config.FEED_DEFAULT_SIZE,
        *,
        seed: int | None = None,
        include_explanation: bool = True,
    ) -> dict[str, Any]:
        now = time.time()
        size = max(1, min(int(size), 50))
        library = self.db.list_all_videos()
        engagements = self.db.user_engagements(user_id)
        seen = self.db.user_seen_video_ids(
            user_id, now - config.RECENCY_WINDOW_HOURS * 3600.0
        )
        cold_start = self.db.user_engagement_count(user_id) < config.COLD_START_MAX_ENGAGEMENTS

        routes = self.recall(user_id, engagements, library, seen)
        by_id = {v["id"]: v for v in library}

        # 多路融合：每条路由按配额贡献候选，用于控制各路的相对话语权。
        # 注意配额作用于候选池深度（RECALL_BASE_DEPTH），而非请求的 size——
        # 否则小内容库 + 高行为用户场景下候选池会被饿死，feed 长度不足。
        merged: dict[str, Candidate] = {}
        for name, items in routes.items():
            ratio = config.RECALL_QUOTAS.get(name, 0.1)
            depth = max(config.MIN_ROUTE_DEPTH, int(round(ratio * config.RECALL_BASE_DEPTH)))
            for vid, rscore in items[:depth]:
                cand = merged.get(vid)
                if cand is None:
                    cand = Candidate(video=by_id[vid])
                    merged[vid] = cand
                cand.routes.add(name)
                cand.route_score = max(cand.route_score, rscore)

        # 冷启动：候选不足时放大兜底池
        if cold_start:
            for vid, rscore in routes["fallback"]:
                cand = merged.get(vid)
                if cand is None:
                    cand = Candidate(video=by_id[vid])
                    merged[vid] = cand
                cand.routes.add("fallback")

        profile = self.user_tag_profile(user_id, engagements)
        following = self.db.following_ids(user_id)
        second_hop = self.db.creator_second_hop(user_id) if following else set()
        max_total = float(max(1, self.db.max_engagement_total()))

        candidates = list(merged.values())
        for cand in candidates:
            cand.features = self.features(
                user_id, cand,
                profile=profile, following=following, second_hop=second_hop,
                max_total=max_total, now=now, seen_video_ids=seen,
            )
            cand.score = self.score(cand.features)

        # 排序后截断到重排池上限
        candidates.sort(key=lambda c: c.score, reverse=True)
        pool = candidates[: config.MMR_CANDIDATE_POOL]
        reranked = self.rerank(pool, size, seed=seed)

        items: list[FeedItem] = []
        explore_slots = 0
        if not cold_start and len(reranked) > 1:
            rng = random.Random((seed or 0) + 977)
            if rng.random() < config.EPSILON_EXPLORE:
                explore_slots = 1
        items = [
            FeedItem(
                video=c.video,
                score=c.score,
                features=c.features,
                routes=sorted(c.routes),
                reason=_reason_for(c),
            )
            for c in reranked
        ]

        out_items = []
        for it in items:
            entry: dict[str, Any] = {
                "video_id": it.video["id"],
                "creator_id": it.video["creator_id"],
                "caption": it.video["caption"],
                "tags": it.video["tags"],
                "duration_ms": it.video["duration_ms"],
                "score": it.score,
                "reason": it.reason,
                "recall_routes": it.routes,
                "is_exploration": False,
            }
            if include_explanation:
                entry["features"] = it.features
            out_items.append(entry)

        return {
            "user_id": user_id,
            "cold_start": cold_start,
            "size": len(out_items),
            "weight_version": dict(self.weights),
            "items": out_items,
        }


def _reason_for(cand: Candidate) -> str:
    """生成人类可读的推荐理由，便于运营与调试归因。"""
    feats = cand.features or {}
    top = max(feats.items(), key=lambda kv: kv[1])[0] if feats else "pop"
    label = {
        "aff": "标签兴趣匹配",
        "pop": "大众热度",
        "fresh": "新鲜度",
        "social": "社交关系",
        "qual": "内容质量",
    }.get(top, "综合得分")
    route_label = {
        "cf": "协同过滤",
        "follow": "关注创作者",
        "fresh": "热门新鲜",
        "tag": "标签匹配",
        "fallback": "冷启动兜底",
    }
    routes = "/".join(route_label.get(r, r) for r in sorted(cand.routes))
    return f"{label}主导（召回路径：{routes}）"
