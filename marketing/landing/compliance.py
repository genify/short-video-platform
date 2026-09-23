"""投放素材合规校验（纯标准库，零第三方依赖）。

输入契约（只读，不修改）：
  marketing/compliance/lexicon.json   合规词表
  marketing/landing/copy_pack.json    落地页文案包

phase 语义（与 lexicon.json 的 phases 一致）：
  pre_t0 臂 = hard_ban + t0_gated 全禁
  t0 臂    = 只禁 hard_ban

对外 API：
  load_lexicon(path) -> dict
  find_violations(text, lexicon, phase, quoted=False) -> list[dict]
  validate_copy_pack(copy_pack, lexicon, phase) -> list[dict]
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator

SEVERITY_HARD = "hard_ban"
SEVERITY_T0 = "t0_gated"
SEVERITY_REQUIRED = "required_missing"

# required_token 的 scope -> 在 copy_pack 中检查的节点路径（用于错误信息里的 JSON 路径）
_REQUIRED_SCOPE_PATHS = {
    "recruit_form": ("assets", "recruit", "form"),
    "share_landing": ("assets", "share"),
}
# 更精确的展示路径（错误信息用）
_REQUIRED_SCOPE_LABEL = {
    "recruit_form": "assets.recruit.form.consent_text",
    "share_landing": "assets.share",
}


def load_lexicon(path: str) -> dict:
    """读取词表并补齐缺省键，保证下游不必再做防御。"""
    with open(path, "r", encoding="utf-8") as fh:
        lex = json.load(fh)
    if not isinstance(lex, dict):
        raise ValueError("lexicon 必须是 JSON 对象")
    for key in ("hard_ban", "t0_gated", "required_tokens", "quoted_context_markers"):
        if not isinstance(lex.get(key), list):
            lex[key] = []
    return lex


def _rules_for_phase(lexicon: dict, phase: str) -> list[tuple[str, dict]]:
    """按 phase 返回 (severity, rule) 列表。

    pre_t0 = hard_ban + t0_gated；t0 = 只 hard_ban；未知 phase 保守按 hard_ban。
    """
    rules: list[tuple[str, dict]] = [(SEVERITY_HARD, r) for r in lexicon.get("hard_ban", [])]
    if phase == "pre_t0":
        rules += [(SEVERITY_T0, r) for r in lexicon.get("t0_gated", [])]
    return rules


def _line_of(text: str, index: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end == -1:
        end = len(text)
    return start, end


def _first_hit(text: str, rule: dict, severity: str, quoted: bool, markers: list[str]) -> dict | None:
    """返回该规则在文本中的第一条命中（quoted 时跳过带豁免标记的行）。"""
    pattern = rule.get("pattern") or ""
    if not pattern:
        return None
    try:
        compiled = re.compile(pattern)
    except re.error:
        return None
    for m in compiled.finditer(text):
        if quoted and markers:
            start, end = _line_of(text, m.start())
            line = text[start:end]
            if any(mk in line for mk in markers):
                continue  # 同一行含引用上下文标记 -> 豁免
        return {
            "id": rule.get("id", ""),
            "pattern": pattern,
            "matched": m.group(0),
            "reason": rule.get("reason", ""),
            "source": rule.get("source", ""),
            "severity": severity,
        }
    return None


def find_violations(
    text: str,
    lexicon: dict,
    phase: str,
    quoted: bool = False,
    markers_ok: bool = False,
) -> list[dict]:
    """在单段文本里查找违规项。

    每项：{id, pattern, matched, reason, source, severity}
    severity ∈ {"hard_ban", "t0_gated"}。

    豁免（两档，默认都不开）：
      quoted=True      → 命中所在行含 lexicon.quoted_context_markers 任一词则豁免
                         （用于「引用黑名单」的规则文档本身）。
      markers_ok=True  → 命中所在行含 lexicon.quoted_context_markers 或
                         lexicon.policy_markers 任一词则豁免
                         （用于审查器扫描「既含正文又含禁令政策」的物料文件；
                          落地页启动门禁不走这条路径，保持严格）。
    """
    if text is None:
        return []
    s = str(text)
    markers: list[str] = []
    if markers_ok:
        markers = list(lexicon.get("quoted_context_markers", [])) + list(
            lexicon.get("policy_markers", [])
        )
    elif quoted:
        markers = list(lexicon.get("quoted_context_markers", []))
    use_markers = bool(markers)
    out: list[dict] = []
    for severity, rule in _rules_for_phase(lexicon, phase):
        hit = _first_hit(s, rule, severity, use_markers, markers)
        if hit:
            out.append(hit)
    return out


# copy_pack 中的两个臂的节点键名（与 lexicon.phases 一致）
ARM_KEYS = ("pre_t0", "t0")


def _iter_strings(node: Any, path: str = "", phase: str | None = None) -> Iterator[tuple[str, str]]:
    """递归遍历 JSON，产出 (json_path, 字符串值)。

    phase 不为 None 且为某个臂名时，只下钻当前臂的节点
    （pre_t0 只校验 pre_t0 文案、t0 只校验 t0 文案），这是「分臂校验」的关键。
    """
    if isinstance(node, dict):
        only_phase = phase in ARM_KEYS
        for key, value in node.items():
            if only_phase and key in ARM_KEYS and key != phase:
                continue  # 跳过另一臂：另一臂用另一套 phase 单独校验
            child = f"{path}.{key}" if path else str(key)
            yield from _iter_strings(value, child, phase)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _iter_strings(value, f"{path}[{i}]", phase)
    elif isinstance(node, str):
        yield path, node


def _node_text(copy_pack: dict, keys: tuple[str, ...]) -> str:
    node: Any = copy_pack
    for key in keys:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return ""
    return "\n".join(text for _p, text in _iter_strings(node))


def validate_copy_pack(copy_pack: dict, lexicon: dict, phase: str) -> list[dict]:
    """全量校验文案包：递归遍历所有字符串值查违规 + 校验 required_tokens。

    违规项在 find_violations 的基础上多一个 json_path 字段；
    required_tokens 缺失记为 severity="required_missing"。
    """
    violations: list[dict] = []

    # 只校验对外物料（assets.*）：顶层 rules/source/title 等属说明性文档，
    # 会引用白名单数字（是「两臂定义」本身），不属投放文案。
    if isinstance(copy_pack, dict) and isinstance(copy_pack.get("assets"), dict):
        walk_root: Any = copy_pack["assets"]
        prefix = "assets"
    else:
        walk_root = copy_pack
        prefix = ""

    for rel_path, value in _iter_strings(walk_root, phase=phase):
        full_path = f"{prefix}.{rel_path}" if prefix else rel_path
        for item in find_violations(value, lexicon, phase):
            enriched = dict(item)
            enriched["json_path"] = full_path
            violations.append(enriched)

    for rule in lexicon.get("required_tokens", []):
        scope = rule.get("scope")
        pattern = rule.get("pattern") or ""
        keys = _REQUIRED_SCOPE_PATHS.get(scope)
        if not keys or not pattern:
            continue
        corpus = _node_text(copy_pack, keys)
        if corpus and re.search(pattern, corpus):
            continue
        violations.append(
            {
                "id": rule.get("id", ""),
                "pattern": pattern,
                "matched": "",
                "reason": rule.get("reason", ""),
                "source": rule.get("source", ""),
                "severity": SEVERITY_REQUIRED,
                "json_path": _REQUIRED_SCOPE_LABEL.get(scope, ".".join(keys)),
            }
        )
    return violations


def blocking_violations(violations: list[dict]) -> list[dict]:
    """会阻断上线的违规项：hard_ban / t0_gated（required_missing 为数据完整性告警）。"""
    return [v for v in violations if v.get("severity") in (SEVERITY_HARD, SEVERITY_T0)]


# ---------------------------------------------------------------------------
# 自测断言（python3 marketing/landing/compliance.py 直接运行）
# ---------------------------------------------------------------------------
def _selftest() -> None:
    lex = {
        "hard_ban": [
            {"id": "HB-01", "pattern": "保底\\s*曝光|保底\\s*500", "reason": "旧口径", "source": "05 §0.2"},
            {"id": "HB-08", "pattern": "社交冷启动|关系链分发", "reason": "已改写", "source": "05 §0.2"},
        ],
        "t0_gated": [
            {"id": "TG-01", "pattern": "P10", "reason": "量化承诺", "source": "05 §0.3"},
            {"id": "TG-02", "pattern": "≥\\s*50|不低于\\s*50", "reason": "量化承诺", "source": "05 §0.3"},
            {"id": "TG-06", "pattern": "保证.{0,8}(有人看|被看见)", "reason": "结果承诺", "source": "本单"},
        ],
        "required_tokens": [],
        "quoted_context_markers": ["禁止", "不得", "黑名单"],
    }
    # pre_t0：P10 / ≥ 50 / 保证有人看 必须报违规
    assert find_violations("首发曝光 P10 ≥ 50", lex, "pre_t0"), "pre_t0 应命中 P10/≥50"
    assert find_violations("我们保证有人看", lex, "pre_t0"), "pre_t0 应命中保证有人看"
    # t0：P10 不再违规；保底曝光 500 / 社交冷启动 仍违规
    assert not find_violations("首发曝光 P10", lex, "t0"), "t0 不应命中 P10"
    assert not find_violations("首发 24h 曝光 ≥ 50 次", lex, "t0"), "t0 不应命中 ≥50"
    assert find_violations("保底曝光 500", lex, "t0"), "t0 应命中保底曝光"
    assert find_violations("社交冷启动", lex, "t0"), "t0 应命中社交冷启动"
    # quoted 豁免：同一行含标记则不报
    assert not find_violations("禁止出现：保底曝光 500", lex, "pre_t0", quoted=True)
    assert find_violations("保底曝光 500", lex, "pre_t0", quoted=True)
    print("compliance.py 自测断言全部通过")


if __name__ == "__main__":
    _selftest()
