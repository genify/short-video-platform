"""账号凭据与鉴权原语（FR-3.1 / FR-4.1）。

本模块只放**纯函数**（令牌生成、哈希、头部解析、脱敏），不含任何 HTTP 或
业务逻辑，便于单测与安全审计；编排逻辑在 `app.py`。

安全口径（与 PRD §3.5.2 对齐）：
1. 令牌**只存 `sha256`**，服务端永不持有明文；明文仅在签发响应中出现一次。
2. 校验用 `secrets.compare_digest` 常量时间比较，避免时序侧信道。
3. 任何日志/错误响应都不得回显令牌 —— 统一走 `redact()`。
4. 管理员凭据与用户令牌**不共用签发路径**（前者来自环境变量，后者来自 DB）。
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

# 令牌形态：32 随机字节的 URL-safe base64（无填充），≈43 字符
TOKEN_BYTES = 32
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{20,128}$")

# 需要脱敏的形态：`Bearer xxx`、密钥字段、**非纯十六进制**的长随机串
_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]+")
_SECRET_FIELD_RE = re.compile(
    r"(?i)\b(token|authorization|api[_-]?key|secret|password)\b\s*[:=]\s*(?!bearer\b)[^\s,;\"'}]+"
)
# 只匹配"看起来像令牌"的长串：长度 ≥32 且含大写/`-`/`_`。
# 为什么排除纯小写十六进制：video_id / sha256 摘要都是纯 hex，误伤它们会
# 污染用户可见的错误消息（例如 duplicate_video 需要回传 video_id）。
_TOKEN_LIKE_RE = re.compile(r"\b(?=[A-Za-z0-9_\-]{32,}\b)(?=[^\s]*[A-Z_\-])[A-Za-z0-9_\-]{32,}\b")


def new_token() -> str:
    """生成不可预测的用户令牌（32 字节熵）。"""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    """令牌的服务端存储形式：sha256 十六进制摘要。"""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def looks_like_token(token: str) -> bool:
    return bool(_TOKEN_RE.match(token or ""))


def parse_bearer(header_value: str | None) -> str | None:
    """从 `Authorization` 头解析令牌；缺失或格式错误返回 None。

    只接受 `Bearer <token>`（大小写不敏感），其余一律视为缺失 —— 宽容解析
    会让 `Basic`/裸令牌等歧义写法进入校验路径，不如直接拒绝。
    """
    if not header_value:
        return None
    parts = header_value.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def tokens_equal(a: str, b: str) -> bool:
    """常量时间比较（用于管理员令牌等直接比对场景）。"""
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


def redact(text: object) -> str:
    """把可能出现在消息/日志里的令牌替换为 `***`（FR-4.1.f）。"""
    out = str(text)
    out = _BEARER_RE.sub(r"\1 ***", out)
    out = _SECRET_FIELD_RE.sub(lambda m: f"{m.group(1)}=***", out)
    out = _TOKEN_LIKE_RE.sub("***", out)
    return out
