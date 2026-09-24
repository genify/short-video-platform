"""可调参数集中管理（权重、阈值、限额）。

所有推荐权重与设计文档 docs/03-recommendation-design.md 第 4/6 章一一对应，
改动此处即可做权重实验（A/B 或离线网格搜索），无需触碰算法代码。
"""

from __future__ import annotations

import json
import os

# ---------------------------------------------------------------------------
# 排序权重：S = w_aff*Aff + w_pop*Pop + w_fresh*Fresh + w_social*Social + w_qual*Qual
# 设计文档 4.3 节给出的 MVP 初值（和须为 1.0）
#
# 初值来源：行业经验，**未经真实流量校准**（本项目最大未验证假设）。
# 校准方法见 `scripts/evaluate.py`（离线评测集 + NDCG@K 网格搜索）。
# 生产默认值保持冻结；如需启用校准结果，用环境变量注入而**不要改这里**：
#
#     SVP_RANK_WEIGHTS='{"aff":0.40,"pop":0.15,"fresh":0.20,"social":0.10,"qual":0.15}'
#
# 理由：合成/离线评测集上搜到的最优权重不等于线上最优，未经线上 A/B 验证前
# 不得把评测结论直接写进生产默认值（否则等于用一次离线实验冻死一个超参）。
# ---------------------------------------------------------------------------
DEFAULT_RANK_WEIGHTS: dict[str, float] = {
    "aff": 0.45,     # 标签兴趣匹配度（个性化核心）
    "pop": 0.20,     # 全局热度（大众偏好兜底）
    "fresh": 0.15,   # 新鲜度（时间衰减）
    "social": 0.10,  # 社交关系（关注 / 二跳）
    "qual": 0.10,    # 内容质量（完播率 + 点赞率复合）
}
RANK_WEIGHT_KEYS: tuple[str, ...] = ("aff", "pop", "fresh", "social", "qual")


def _weights_from_env() -> dict[str, float]:
    """解析 `SVP_RANK_WEIGHTS`（JSON 对象），非法输入直接回退到冻结默认值。

    校验口径：键集合必须完全一致、每个值非负、总和为 1（容差 1e-6）。
    """
    raw = (os.environ.get("SVP_RANK_WEIGHTS") or "").strip()
    if not raw:
        return dict(DEFAULT_RANK_WEIGHTS)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return dict(DEFAULT_RANK_WEIGHTS)
    if not isinstance(parsed, dict) or set(parsed) != set(RANK_WEIGHT_KEYS):
        return dict(DEFAULT_RANK_WEIGHTS)
    try:
        weights = {k: round(float(parsed[k]), 6) for k in RANK_WEIGHT_KEYS}
    except (TypeError, ValueError):
        return dict(DEFAULT_RANK_WEIGHTS)
    if any(v < 0 for v in weights.values()) or abs(sum(weights.values()) - 1.0) > 1e-6:
        return dict(DEFAULT_RANK_WEIGHTS)
    return weights


RANK_WEIGHTS: dict[str, float] = _weights_from_env()

# 重排参数
MMR_LAMBDA: float = 0.7          # MMR 相关性/多样性权衡，λ→1 纯相关性
MMR_CANDIDATE_POOL: int = 200    # 进入重排的候选池上限
FEED_DEFAULT_SIZE: int = 10      # 默认返回条数
CREATOR_CAP_PER_FEED: int = 2    # 单创作者在一条 feed 中的最大条数（打散）
RECENCY_WINDOW_HOURS: float = 168.0  # 7 天内已看过的视频不再推荐
FRESH_HALF_LIFE_HOURS: float = 48.0  # 新鲜度半衰期

# ---------------------------------------------------------------------------
# 探索-利用：ε-greedy（FR-2.4）
# ---------------------------------------------------------------------------
EPSILON_EXPLORE: float = 0.10    # 10% 流量给探索位
EXPLORE_MIN_FEED_LEN: int = 4    # feed 短于此长度不注入探索位（保证索引 ≥ 3 可替换）
EXPLORE_EXPOSURE_PCT: float = 0.30  # 探索候选的"低曝光分位"阈值（全站 P30）
EXPLORE_SLOT_INDEX: int = 3      # 固定注入位置（索引 ≥ 3，前 3 位保持纯相关性）

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

# ---------------------------------------------------------------------------
# FR-3 / FR-4：账号凭据、鉴权与限流（P0，上线阻塞项）
# 全部参数可经环境变量覆盖；**任何密钥都不得写进代码**。
# ---------------------------------------------------------------------------
TOKEN_TTL_DAYS: int = int(os.environ.get("SVP_TOKEN_TTL_DAYS", "30"))
AUTH_LEVEL: str = "dev"                    # MVP 为开发级身份（无密码/验证码），须显式标注
# 管理员凭据：仅从环境变量注入；未配置时管理端点**fail-closed**（一律 403 admin_required）
ADMIN_TOKEN: str = (os.environ.get("SVP_ADMIN_TOKEN") or "").strip()

# 注册期兴趣标签白名单（FR-3.1.e，恰好 3 个，用于 S3 判据基准）
INTEREST_TAG_WHITELIST: tuple[str, ...] = (
    "美食", "旅行", "宠物", "健身", "读书", "美妆", "数码", "汽车", "母婴", "职场",
)
INTEREST_TAG_COUNT: int = 3
REGISTER_SOURCES: frozenset[str] = frozenset({"seed_invite", "organic", "ad", "unknown"})

# CORS 白名单（FR-4.1.e）：逗号分隔环境变量驱动，**默认不为 `*`**
CORS_ORIGINS: tuple[str, ...] = tuple(
    origin.strip()
    for origin in (os.environ.get("SVP_CORS_ORIGINS")
                   or "http://127.0.0.1:8080,http://localhost:8080").split(",")
    if origin.strip()
)
CORS_ALLOWED_HEADERS: str = "Authorization, Content-Type, X-Request-Id"

# 令牌桶限流规则（FR-4.2）：端点类 -> 键 -> (容量, 窗口秒)
#
# - 键 `user` / `user_day` 用已鉴权身份，`ip` 用客户端地址（未鉴权兜底）
# - 上传的限流必须在**读取请求体之前**执行（FR-4.2.b）
# - `/api/health` 豁免（FR-4.2.d）
# - 单机进程内实现；多实例部署时须迁 Redis（已知限制，见 PRD §六）
RATE_LIMIT_ENABLED: bool = (os.environ.get("SVP_RATE_LIMIT", "1").strip() not in {"0", "false", "off"})
RATE_LIMITS: dict[str, dict[str, tuple[int, float]]] = {
    "users":        {"ip": (5, 3600)},                          # 防批量注册
    "sessions":     {"ip": (20, 3600)},
    "video_upload": {"user": (5, 60), "user_day": (20, 86400), "ip": (10, 60)},
    "engagements":  {"user": (120, 60), "ip": (300, 60)},
    "follows":      {"user": (120, 60), "ip": (300, 60)},
    "feed":         {"user": (60, 60), "ip": (120, 60)},
    "reads":        {"user": (120, 60), "ip": (300, 60)},
    "admin":        {"user": (10, 60)},
    "global":       {"ip": (600, 60)},                          # 全局兜底
    "health":       {},                                         # 探活豁免
}
