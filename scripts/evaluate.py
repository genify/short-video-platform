#!/usr/bin/env python3
"""推荐权重离线校准：NDCG@K 评测集 + 权重网格搜索（PRO-7 交付物 ①）。

背景
----
`server/config.py` 的排序权重 `0.45 / 0.20 / 0.15 / 0.10 / 0.10` 是**行业经验
初值**，从未被任何数据校准过 —— 这是本项目最大的未验证假设。

本脚本提供**可复现**的校准方法，并输出校准前后的 NDCG@K 对比：

    python3 scripts/evaluate.py                  # 合成评测集（默认，零依赖）
    python3 scripts/evaluate.py --from-db var/svp.db --out docs/10-*.md
    python3 scripts/evaluate.py --json out.json

评测口径（离线、无线上流量）
--------------------------
* **留出法（temporal holdout）**：把每个评测用户的一部分正反馈**从系统里彻底
  抹掉**，作为"真实相关集"（ground truth）。引擎看不到它们，因此它们就是
  合法的待排序候选 —— 这直接回答"排序能否把真正相关但系统尚未见过的内容排上来"。
* **NDCG@K**：指数增益 `2^rel - 1` / `log2(i+1)`，按每个用户理想排序归一化后取均值。
* **搜索空间**：权重单纯形上的网格（默认步长 0.05）+ 最优解邻域坐标细化。

⚠️ 诚实边界（必读，不要跳过）
--------------------------
1. **合成评测集只能验证"方法"，不能产出"生产权重"。** 默认数据集由一个已知
   隐式偏好模型的用户模拟器生成。**实测中搜索最优 ≠ 该真值权重** —— 因为引擎
   观测到的是*实现后的*特征（`pop`/`qual` 由真实互动计数算出，而不是生成时的
   隐变量），两者的映射并不等价。这本身就是"合成集不能直接产出生产权重"的
   实证证据，报告里会把这一差距显式打印出来。
2. **真实权重必须用真实行为日志校准**：用 `--from-db` 指向真实库，并在灰度期
   用线上 A/B（NDCG 是离线代理指标，与留存/完播不必然同向）。
3. 因此脚本**不会**自动改写 `config.RANK_WEIGHTS`；它只输出建议值与
   `SVP_RANK_WEIGHTS` 注入命令，由人决定何时启用（并留 A/B 证据）。

链路可信度由**自检**保证（而不是由"搜到真值"保证）：`OfflineEvaluator.self_check()`
断言"评测器在默认权重下的排序与生产 `engine.feed` 逐项一致"，不一致直接报错 ——
否则算得再快也是在优化一个与线上不同的目标。
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
import os
import random
import shutil
import sys
import tempfile
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import config  # noqa: E402
from server.db import Database  # noqa: E402
from server.recommend import Candidate, RecommendEngine  # noqa: E402

OUTPUT_SCALE = 10          # 权重网格步长 = 1 / OUTPUT_SCALE（默认 0.10）
CATEGORIES = ["美食", "旅行", "宠物", "健身", "读书", "数码"]

# 合成评测集的**真值权重**：故意与生产的经验初值不同，这样"能不能把真值搜回来"
# 才是一个有信息量的检验。真值不等于"正确答案"，只是标定用的参照系。
GT_WEIGHTS = {"aff": 0.40, "pop": 0.15, "fresh": 0.20, "social": 0.05, "qual": 0.20}

# 反馈 → 相关性增益（离线评测的相关性标注口径；与 ACTION_VALUE 分离，
# 因为"行为价值"是画像加权口径，"相关性标注"是评测口径，两者不应混用同一张表）
RELEVANCE = {"like": 1.0, "share": 0.9, "follow": 1.0, "complete": 0.6, "view": 0.25}


# ---------------------------------------------------------------------------
# 权重网格
# ---------------------------------------------------------------------------
def simplex_grid(step_units: int = OUTPUT_SCALE) -> list[dict[str, float]]:
    """生成权重单纯形上的网格点（5 个分量非负、和为 1、步长 1/scale）。

    用整数分拆生成，避免浮点累加误差导致"和不是 1"。
    """
    keys = list(config.RANK_WEIGHT_KEYS)
    out: list[dict[str, float]] = []
    for combo in _compositions(step_units, len(keys)):
        out.append({k: n / step_units for k, n in zip(keys, combo)})
    return out


def _compositions(total: int, parts: int):
    """把整数 total 分成 parts 个非负整数（递归生成，顺序稳定）。"""
    if parts == 1:
        yield (total,)
        return
    for head in range(total + 1):
        for tail in _compositions(total - head, parts - 1):
            yield (head,) + tail


def coordinate_refine(best: dict[str, float], step_units: int) -> list[dict[str, float]]:
    """在最优解邻域做坐标扰动（保持和为 1）。"""
    keys = list(config.RANK_WEIGHT_KEYS)
    unit = 1.0 / step_units
    out: list[dict[str, float]] = []
    for i, j in itertools.permutations(range(len(keys)), 2):
        if best[keys[i]] + unit > 1.0 + 1e-9:
            continue
        cand = dict(best)
        cand[keys[i]] = round(cand[keys[i]] + unit, 6)
        cand[keys[j]] = round(cand[keys[j]] - unit, 6)
        if cand[keys[j]] < -1e-9:
            continue
        cand[keys[j]] = max(0.0, cand[keys[j]])
        if abs(sum(cand.values()) - 1.0) < 1e-9:
            out.append(cand)
    return out


# ---------------------------------------------------------------------------
# 合成评测集
# ---------------------------------------------------------------------------
def build_synthetic_db(path: str, *, users: int = 12, videos_per_creator: int = 8,
                       creators: int = 6, holdout: int = 2, seed: int = 20260924) -> tuple[Database, dict]:
    """生成一个"有真值偏好结构"的合成库，返回 (db, 真值标注)。

    设计要点（决定了评测是否有信息量）：
    - 内容分成 6 个垂类；用户各有 2 个兴趣垂类 → `aff` 有区分度；
    - 质量与热度**独立**生成（高质量低热度长尾）→ `qual`/`pop` 可分离；
    - 年龄分布覆盖 0~240h → `fresh` 有区分度；关注关系稀疏 → `social` 可分离；
    - 用户的互动**由真值权重的隐式模型驱动**（加噪声），因此真值权重是可达最优。
    """
    rng = random.Random(seed)
    db = Database(path)

    creator_ids = []
    for i in range(creators):
        uid = uuid.uuid4().hex
        db.create_user(uid, f"creator_{i}")
        creator_ids.append(uid)

    now = time.time()
    videos: list[dict] = []
    for creator in creator_ids:
        for _ in range(videos_per_creator):
            tags = [rng.choice(CATEGORIES)]
            if rng.random() < 0.25:
                tags.append(rng.choice(CATEGORIES))
            age_h = rng.uniform(0.5, 240.0)
            vid = uuid.uuid4().hex
            db.create_video(
                video_id=vid, creator_id=creator, caption=f"clip-{vid[:6]}", tags=tags,
                duration_ms=int(rng.uniform(4000, 60000)), width=480, height=854,
                size_bytes=1000, sha256=vid, storage_path=f"var/media/{vid}.mp4",
            )
            db.execute("UPDATE videos SET created_at=? WHERE id=?", (now - age_h * 3600.0, vid))
            videos.append({
                "id": vid, "creator": creator, "tags": tags, "age_h": age_h,
                "quality": rng.random(),        # 隐式内容质量（0~1）
                "popularity": rng.random(),     # 隐式热度倾向（0~1）
            })

    ground_truth: dict[str, dict[str, float]] = {}
    for u in range(users):
        uid = uuid.uuid4().hex
        db.create_user(uid, f"viewer_{u}")
        interests = rng.sample(CATEGORIES, 2)
        followed = rng.sample(creator_ids, rng.choice([1, 1, 2]))
        for c in followed:
            db.add_follow(uid, c)

        scored = []
        for v in videos:
            feats = {
                "aff": 1.0 if set(v["tags"]) & set(interests) else 0.0,
                "pop": v["popularity"],
                "fresh": 0.5 ** (v["age_h"] / config.FRESH_HALF_LIFE_HOURS),
                "social": 1.0 if v["creator"] in followed else 0.0,
                "qual": v["quality"],
            }
            rel = sum(GT_WEIGHTS[k] * feats[k] for k in GT_WEIGHTS) + rng.gauss(0, 0.03)
            scored.append((rel, v))
        scored.sort(key=lambda kv: kv[0], reverse=True)

        # 相关性归一化到 [0,1]（NDCG 的标注增益口径）
        lo = min(r for r, _ in scored)
        hi = max(r for r, _ in scored)
        scale = (hi - lo) or 1.0

        held = scored[:holdout]                      # 真值相关集：**不留任何痕迹**
        ground_truth[uid] = {v["id"]: (rel - lo) / scale for rel, v in held}
        for rel, v in scored[holdout:holdout + 8]:   # 可见行为（引擎可学到）
            norm = (rel - lo) / scale
            db.add_engagement(uid, v["id"], "view",
                              watch_ms=int(1000 + 5000 * norm), created_at=now - rng.uniform(0, 72) * 3600)
            if norm > 0.75:
                db.add_engagement(uid, v["id"], "like", created_at=now - rng.uniform(0, 72) * 3600)
            if norm > 0.55:
                db.add_engagement(uid, v["id"], "complete", created_at=now - rng.uniform(0, 72) * 3600)

    return db, ground_truth


def load_from_real_db(source_path: str, *, holdout: int = 2, copy_to: str | None = None) -> tuple[Database, dict]:
    """在真实库上构造评测集：拷一份库，把每个用户最近的 N 条正反馈**删掉**作为真值。

    为什么必须"删掉"而不是"标记"：只要引擎还能看到这些互动，它们就会进入
    用户画像与去重（7 天已看过滤），评测就变成"复述历史"而不是"发现相关内容"。
    """
    target = copy_to or os.path.join(tempfile.mkdtemp(prefix="svp-eval-"), "replay.db")
    shutil.copy2(source_path, target)
    db = Database(target)

    ground_truth: dict[str, dict[str, float]] = {}
    rows = db.query(
        """SELECT user_id, video_id, kind FROM engagements
           WHERE kind IN ('like','share','follow') ORDER BY user_id, created_at DESC"""
    )
    per_user: dict[str, list[tuple[str, str]]] = {}
    for r in rows:
        per_user.setdefault(r["user_id"], []).append((r["video_id"], r["kind"]))
    for uid, items in per_user.items():
        picked = items[:holdout]
        if len(items) <= holdout:      # 正反馈太少，无法留出，跳过该用户（避免泄露）
            continue
        ground_truth[uid] = {vid: RELEVANCE.get(kind, 0.5) for vid, kind in picked}
        for vid, _kind in picked:
            db.execute("DELETE FROM engagements WHERE user_id=? AND video_id=?", (uid, vid))
    db.execute("DELETE FROM item_sim")            # 相似度缓存已被改写，重建一次
    db.rebuild_item_similarity()
    return db, ground_truth


# ---------------------------------------------------------------------------
# 评测器
# ---------------------------------------------------------------------------
class OfflineEvaluator:
    """对同一批用户反复评估不同权重向量。

    性能设计：候选特征与召回**只算一次**（与权重无关），权重搜索退化为纯内存
    线性组合 + MMR 重排。否则 1000+ 个权重向量 × 每向量全量 SQL = 不可接受的耗时。
    """

    def __init__(self, db: Database, ground_truth: dict, *, k: int = 10, seed: int = 4242,
                 pool_cap: int | None = None) -> None:
        self.db = db
        self.k = int(k)
        self.seed = int(seed)
        self.pool_cap = int(pool_cap or config.MMR_CANDIDATE_POOL)
        self.truth = {u: gt for u, gt in ground_truth.items() if gt}
        self._prepared: dict[str, list[Candidate]] = {}
        self._prepare()

    # -- 准备（一次）-----------------------------------------------------
    def _prepare(self) -> None:
        engine = RecommendEngine(self.db)
        for user_id in self.truth:
            state = self._user_state(engine, user_id)
            if state is None:
                continue
            self._prepared[user_id] = state

    def _user_state(self, engine: RecommendEngine, user_id: str) -> list[Candidate] | None:
        """复刻 `RecommendEngine.feed` 的召回合并步骤，但**不注入探索位**。

        ⚠️ 这段与 `feed()` 的合并逻辑重复。防重复漂移的手段：自检
        `self_check()` 会在默认权重下断言本评测器的排序与 `engine.feed` 完全一致，
        不一致就直接报错（宁可报错，也不要给出与生产不一致的"校准"结论）。
        """
        library = self.db.list_all_videos()
        if not library:
            return None
        engagements = self.db.user_engagements(user_id)
        now = time.time()
        seen = self.db.user_seen_video_ids(user_id, now - config.RECENCY_WINDOW_HOURS * 3600.0)
        routes = engine.recall(user_id, engagements, library, seen)
        by_id = {v["id"]: v for v in library}

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

        profile = engine.user_tag_profile(user_id, engagements)
        following = self.db.following_ids(user_id)
        second_hop = self.db.creator_second_hop(user_id) if following else set()
        max_total = float(max(1, self.db.max_engagement_total()))
        candidates = list(merged.values())
        for cand in candidates:
            cand.features = engine.features(
                user_id, cand, profile=profile, following=following, second_hop=second_hop,
                max_total=max_total, now=now, seen_video_ids=seen,
            )
        return candidates[: self.pool_cap]

    # -- 评估 -------------------------------------------------------------
    def ndcg(self, weights: dict[str, float]) -> float:
        engine = RecommendEngine(self.db, weights=weights)
        scores = []
        for user_id, candidates in self._prepared.items():
            for cand in candidates:
                cand.score = engine.score(cand.features)
            ranked = engine.rerank(sorted(candidates, key=lambda c: c.score, reverse=True),
                                  self.k, seed=self.seed)
            gains = [self.truth[user_id].get(c.video_id, 0.0) for c in ranked]
            ideal = list(self.truth[user_id].values())
            scores.append(_ndcg(gains, ideal, self.k))
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def users(self) -> int:
        return len(self._prepared)

    # -- 自检：评测器与生产 feed 的排序必须一致 ---------------------------
    def self_check(self, weights: dict[str, float], *, feed_seed: int = 0) -> tuple[bool, str]:
        engine = RecommendEngine(self.db, weights=weights)
        for user_id, candidates in list(self._prepared.items())[:3]:
            for cand in candidates:
                cand.score = engine.score(cand.features)
            mine = [c.video_id for c in engine.rerank(
                sorted(candidates, key=lambda c: c.score, reverse=True), self.k, seed=self.seed)]
            live = engine.feed(user_id, size=self.k, seed=feed_seed)
            if live["exploration_injected"]:
                return False, f"自检种子 {feed_seed} 触发了探索位，无法逐项比对"
            theirs = [i["video_id"] for i in live["items"]]
            if mine != theirs:
                return False, f"用户 {user_id[:8]} 排序不一致：harness={mine[:3]} feed={theirs[:3]}"
        return True, "评测器排序与生产 feed 一致（默认权重、无探索位注入）"


def _ndcg(gains: list[float], ideal: list[float], k: int) -> float:
    def dcg(values: list[float]) -> float:
        return sum((2.0 ** v - 1.0) / math.log2(i + 2) for i, v in enumerate(values[:k]))

    ideal_sorted = sorted(ideal, reverse=True)
    denom = dcg(ideal_sorted)
    return dcg(gains) / denom if denom > 0 else 0.0


# ---------------------------------------------------------------------------
# 搜索
# ---------------------------------------------------------------------------
def search(evaluator: OfflineEvaluator, *, step_units: int = OUTPUT_SCALE,
           rounds: int = 2, verbose: bool = True) -> dict:
    """网格 + 坐标细化。返回搜索过程与最优解。"""
    baseline = dict(config.RANK_WEIGHTS)
    base_score = evaluator.ndcg(baseline)
    if verbose:
        print(f"[eval] 用户数={evaluator.users} K={evaluator.k} "
              f"候选池上限={evaluator.pool_cap}")
        print(f"[eval] 现状权重 NDCG@{evaluator.k} = {base_score:.4f}  {_fmt_weights(baseline)}")

    grid = simplex_grid(step_units)
    best, best_score = baseline, base_score
    grid_scores: list[tuple[float, dict[str, float]]] = []
    evaluated = 0
    for weights in grid:
        score = evaluator.ndcg(weights)
        evaluated += 1
        grid_scores.append((score, weights))
        if score > best_score + 1e-9:
            best, best_score = weights, score
    if verbose:
        print(f"[search] 网格 {evaluated} 个点 → 最优 NDCG@{evaluator.k} = {best_score:.4f} "
              f"{_fmt_weights(best)}")

    for _round in range(rounds):
        improved = False
        for cand in coordinate_refine(best, step_units * 2):
            score = evaluator.ndcg(cand)
            evaluated += 1
            if score > best_score + 1e-9:
                best, best_score, improved = cand, score, True
        if not improved:
            break
    if verbose:
        print(f"[search] 细化后（共评估 {evaluated} 个权重向量）NDCG@{evaluator.k} = "
              f"{best_score:.4f} {_fmt_weights(best)}")

    return {
        "baseline": baseline,
        "baseline_ndcg": base_score,
        "best": best,
        "best_ndcg": best_score,
        "evaluated": evaluated,
        "lift": best_score - base_score,
        "lift_pct": (best_score - base_score) / base_score * 100 if base_score else 0.0,
        "users": evaluator.users,
        "k": evaluator.k,
        "grid_scores": grid_scores,
    }


def _fmt_weights(weights: dict[str, float]) -> str:
    return " / ".join(f"{weights[k]:.2f}" for k in config.RANK_WEIGHT_KEYS)


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def render_report(result: dict, evaluator: OfflineEvaluator, *, source: str,
                  self_check: tuple[bool, str], top_candidates: list[dict]) -> str:
    k = result["k"]
    truth_line = ("（合成集真值：" + _fmt_weights(GT_WEIGHTS) + "）"
                  if source == "synthetic" else "（真实库回放：以历史正反馈为真值）")
    l1_gap = (sum(abs(result["best"][key] - GT_WEIGHTS[key]) for key in config.RANK_WEIGHT_KEYS)
              if source == "synthetic" else 0.0)
    zeroed = [k for k in config.RANK_WEIGHT_KEYS if result["best"][k] <= 1e-9]
    boundary_note = (
        "\n> ⚠️ **最优解落在搜索空间边界**：`" + " / ".join(zeroed) + "` 被压到 0。\n"
        "> 边界解通常是**过拟合评测集**的信号（真值最优一般不会让某个特征完全消失，\n"
        "> 因为每个特征都承载独立信号）。这本身又是一条**不要直接上线**的理由。\n"
        if zeroed else ""
    )
    rows = []
    for entry in top_candidates:
        rows.append(
            f"| {_fmt_weights(entry['weights'])} | {entry['ndcg']:.4f} | "
            f"{entry['ndcg'] - result['baseline_ndcg']:+.4f} |"
        )
    return f"""# 推荐权重离线校准报告（NDCG@{k}）

> 生成方式：`python3 scripts/evaluate.py`（评测集来源：{source}）{truth_line}
> 本文件由脚本生成，**可随时重跑复现**；不要手工编辑结论数字。

## 一、结论（先说风险，再说数字）

1. **方法可用**：评测链路自检 {('通过' if self_check[0] else '失败')} —— {self_check[1]}
2. **校准前后对比**（同一评测集、同一评测用户、同一 K）：

   | 权重（aff / pop / fresh / social / qual） | NDCG@{k} | 相对现状 |
   |---|---|---|
   | **{_fmt_weights(result['baseline'])}（现状，经验初值）** | {result['baseline_ndcg']:.4f} | — |
   | {_fmt_weights(result['best'])}（搜索最优） | {result['best_ndcg']:.4f} | {result['lift']:+.4f}（{result['lift_pct']:+.1f}%） |

   - 评测用户数：{result['users']}；评估过的权重向量：{result['evaluated']} 个。
3. **离线上限 ≈ {result['best_ndcg']:.4f}**：这是"只有在评测集上"的上界，
   **不是**线上收益承诺。
4. **本次结论不足以直接改生产权重**（见第二节边界 1~3）。{boundary_note}

### 该不该用最优权重替换现状？

* ✅ 可以用：作为**下一轮线上 A/B 的实验臂**（`SVP_RANK_WEIGHTS` 注入），
  并以留存/完播/退出率为主指标，NDCG 只作辅证。
* ❌ 不要用：直接把默认值改成搜索结果 —— 那等于用一次离线实验把一个超参冻死。

## 二、方法与边界（为什么可信 / 哪里不可信）

* **留出法**：评测用户的真值相关项被**彻底移除**（引擎看不到），因此排序任务
  是"能否发现真正相关但尚未见过的内容"，而不是"复述历史"。若只标记不删除，
  7 天已看过滤会让评测变成自证。
* **边界 1：合成集只能验证方法。** 本报告的默认评测集由已知隐式偏好模型
  （真值 {_fmt_weights(GT_WEIGHTS)}）生成。**搜索最优与真值的 L1 距离 =
  {l1_gap:.2f}** —— 两者不相等是**预期行为**：引擎观测的是*实现后的*特征
  （`pop`/`qual` 由真实互动计数算出），与生成时的隐变量不是同一组坐标。
  这恰恰证明"合成集上搜出的权重不能直接上线"。
* **链路可信度由自检保证**：评测器在默认权重下的排序必须与生产 `engine.feed`
  逐项一致（见第一节第 1 条），否则本报告的一切数字都不成立。
* **边界 2：真实校准必须用真实日志。** 用 `--from-db <库路径>` 在真实互动
  历史回放（脚本会拷贝一份库、删除留出项，不动原库）。
* **边界 3：NDCG 与业务指标不必然同向。** 离线相关性排序好 ≠ 留存好。上线前
  必须 A/B；`EPSILON_EXPLORE`、`MMR_LAMBDA`、`CREATOR_CAP_PER_FEED` 同样未校准。

## 三、Top 候选权重（前 {len(top_candidates)} 名）

   | 权重 | NDCG@{k} | 相对现状 |
   |---|---|---|
{chr(10).join(rows)}

## 四、如何启用（人工决定 + 留痕）

```bash
# 1) 先用实验臂跑（不改代码、不改默认值）
export SVP_RANK_WEIGHTS='{json.dumps(result['best'], ensure_ascii=False)}'
python3 run.py

# 2) 线上 A/B 通过后，再评估是否把这些值写进 server/config.py 的 DEFAULT_RANK_WEIGHTS
```

## 五、复现命令

```bash
python3 scripts/evaluate.py --json /tmp/eval.json      # 合成评测集
python3 scripts/evaluate.py --from-db var/svp.db       # 真实库回放
python3 -m unittest tests.test_evaluate -v             # 评测器一致性自检
```
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="推荐权重离线校准（NDCG@K）")
    parser.add_argument("--k", type=int, default=10, help="NDCG@K 的 K（默认 10）")
    parser.add_argument("--from-db", default="", help="用真实库回放评测（路径）")
    parser.add_argument("--synthetic-users", type=int, default=12)
    parser.add_argument("--synthetic-videos-per-creator", type=int, default=8)
    parser.add_argument("--pool-cap", type=int, default=60,
                        help="评测候选池上限（越小越快；默认 60，生产为 MMR_CANDIDATE_POOL）")
    parser.add_argument("--step-units", type=int, default=OUTPUT_SCALE,
                        help="网格步长的倒数（20 → 0.05）")
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--out", default="", help="报告写到哪里（markdown）")
    parser.add_argument("--json", default="", help="把结果写成 JSON")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.from_db:
        if not os.path.exists(args.from_db):
            print(f"[error] 找不到库文件：{args.from_db}", file=sys.stderr)
            return 2
        db, truth = load_from_real_db(args.from_db)
        source = "real-replay"
    else:
        tmp = tempfile.mkdtemp(prefix="svp-eval-synth-")
        db, truth = build_synthetic_db(
            os.path.join(tmp, "eval.db"), users=args.synthetic_users,
            videos_per_creator=args.synthetic_videos_per_creator, seed=args.seed,
        )
        source = "synthetic"

    if len(truth) < 2:
        print("[error] 评测用户不足（<2），无法给出有意义的均值", file=sys.stderr)
        return 2

    started = time.time()
    evaluator = OfflineEvaluator(db, truth, k=args.k, pool_cap=args.pool_cap,
                                 seed=args.seed)
    self_check = evaluator.self_check(dict(config.RANK_WEIGHTS))
    if not self_check[0]:
        print(f"[warn] 评测器自检未通过：{self_check[1]}", file=sys.stderr)

    result = search(evaluator, step_units=args.step_units, verbose=not args.quiet)

    # 取若干互不相同的候选权重（供人工挑选"稳妥臂"）—— 直接复用网格评分，不重算
    scored = sorted(result.pop("grid_scores"), key=lambda kv: kv[0], reverse=True)
    top_candidates: list[dict] = []
    for score, weights in scored:
        if any(_close(weights, e["weights"]) for e in top_candidates):
            continue
        top_candidates.append({"weights": weights, "ndcg": score})
        if len(top_candidates) >= 5:
            break

    result["elapsed_s"] = round(time.time() - started, 1)
    result["source"] = source
    result["self_check"] = self_check

    report = render_report(result, evaluator, source=source, self_check=self_check,
                           top_candidates=top_candidates)
    if not args.quiet:
        print("\n" + report)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"[eval] 报告已写入 {args.out}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"result": result, "top_candidates": top_candidates}, fh,
                      ensure_ascii=False, indent=2)
        print(f"[eval] 结果 JSON 已写入 {args.json}")

    db.close()
    return 0


def _close(a: dict[str, float], b: dict[str, float], tol: float = 1e-9) -> bool:
    return all(abs(a[k] - b[k]) < tol for k in config.RANK_WEIGHT_KEYS)


if __name__ == "__main__":
    sys.exit(main())
