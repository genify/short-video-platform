"""可调参数集中管理（权重、阈值、限额）。

所有推荐权重与设计文档 docs/03-recommendation-design.md 第 4/6 章一一对应，
改动此处即可做权重实验（A/B 或离线网格搜索），无需触碰算法代码。
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# 排序权重：S = w_aff*Aff + w_pop*Pop + w_fresh*Fresh + w_social*Social + w_qual*Qual
# 设计文档 4.3 节给出的 MVP 初值（和须为 1.0）
# ---------------------------------------------------------------------------
RANK_WEIGHTS: dict[str, float] = {
    "aff": 0.45,     # 标签兴趣匹配度（个性化核心）
    "pop": 0.20,     # 全局热度（大众偏好兜底）
    "fresh": 0.15,   # 新鲜度（时间衰减）
    "social": 0.10,  # 社交关系（关注 / 二跳）
    "qual": 0.10,    # 内容质量（完播率 + 点赞率复合）
}

# 重排参数
MMR_LAMBDA: float = 0.7          # MMR 相关性/多样性权衡，λ→1 纯相关性
MMR_CANDIDATE_POOL: int = 200    # 进入重排的候选池上限
FEED_DEFAULT_SIZE: int = 10      # 默认返回条数
CREATOR_CAP_PER_FEED: int = 2    # 单创作者在一条 feed 中的最大条数（打散）
RECENCY_WINDOW_HOURS: float = 168.0  # 7 天内已看过的视频不再推荐
FRESH_HALF_LIFE_HOURS: float = 48.0  # 新鲜度半衰期

# 探索-利用：ε-greedy
EPSILON_EXPLORE: float = 0.10    # 10% 流量给探索位

# 多路召回配额（决定每条召回路由向候选池贡献的深度占比，归一化后使用）
#
# 重要：配额作用于**候选池深度**，不是最终 feed 长度。早期实现把配额乘
# 以请求的 size，导致行为稀疏的小库场景下候选池被饿死（6 条视频只召回
# 2 条），是典型的多路融合陷阱——召回阶段求"广"，配额只应控制各路的
# 相对贡献，不应限制绝对深度。
RECALL_QUOTAS: dict[str, float] = {
    "cf": 0.30,        # item-item 协同过滤
    "follow": 0.25,    # 关注创作者
    "fresh": 0.20,     # 热门新鲜
    "tag": 0.15,       # 标签内容匹配
    "fallback": 0.10,  # 冷启动兜底（全库热门）
}
RECALL_BASE_DEPTH: int = 200   # 候选池基准深度（配额乘以此值得到每路召回深度）
MIN_ROUTE_DEPTH: int = 20      # 单路最小召回深度，保证小内容库不被饿死

# 行为价值权重：用于构建用户标签兴趣画像（设计文档 3.2 节）
ACTION_VALUE: dict[str, float] = {
    "view": 1.0,
    "complete": 2.0,
    "like": 3.0,
    "share": 5.0,
    "follow": 6.0,
    "skip": -2.0,
    "comment": 4.0,
}

# 质量分的参考基准（用于把比率归一化到 0~1，便于人工解释）
REF_COMPLETION_RATE: float = 0.55
REF_LIKE_RATE: float = 0.12

# ---------------------------------------------------------------------------
# 上传限额与媒体校验
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES: int = int(os.environ.get("SVP_MAX_UPLOAD_MB", "200")) * 1024 * 1024
MAX_DURATION_MS: int = 180_000        # 短视频上限 3 分钟
MIN_DURATION_MS: int = 1_000
ALLOWED_MIME: frozenset[str] = frozenset(
    {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}
)
ALLOWED_EXT: frozenset[str] = frozenset({".mp4", ".mov", ".webm", ".mkv"})

# 存储与数据库位置
MEDIA_ROOT: str = os.environ.get("SVP_MEDIA_ROOT", os.path.join("var", "media"))
DB_PATH: str = os.environ.get("SVP_DB_PATH", os.path.join("var", "svp.db"))

# 冷启动判定阈值
COLD_START_MAX_ENGAGEMENTS: int = 3   # 用户行为数少于此值视为新用户
