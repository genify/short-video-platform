#!/usr/bin/env python3
"""投放素材合规审查器（按 docs/05-gtm-plan.md §3.5 黑名单与 §5.4 红线逐条自检）。

用法：
    python3 marketing/scripts/compliance_lint.py                # 扫描 + 写报告
    python3 marketing/scripts/compliance_lint.py --report-only  # 只打印不写文件

规则来源与优先级：
    marketing/compliance/lexicon.json（唯一词表，只能通过修订该文件变更）
    marketing/compliance/scan_manifest.json（扫描目标、模式、必含项）

扫描模式：
    strict             命中即违规
    quoted             仅当同一行不含 lexicon.quoted_context_markers 之一时判违规
                       （用于引用黑名单本身的规则文档）
    strict_text_only   目录：跳过二进制文件，只扫文本
退出码：0 = 全部通过；1 = 存在违规。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "marketing" / "landing"))
sys.path.insert(0, str(ROOT / "marketing" / "scripts"))

import compliance  # noqa: E402  (marketing/landing/compliance.py)

LEXICON_PATH = ROOT / "marketing" / "compliance" / "lexicon.json"
MANIFEST_PATH = ROOT / "marketing" / "compliance" / "scan_manifest.json"
REPORT_PATH = ROOT / "marketing" / "reports" / "asset-compliance-report.md"

TEXT_SUFFIXES = {".md", ".json", ".csv", ".txt", ".html", ".svg", ".py", ".yaml", ".yml"}


def lint_copy_pack(target: dict, lexicon: dict) -> list[dict]:
    """T-01：文案包必须两个相位都校验（pre_t0 严于 t0）。"""
    path = ROOT / target["path"]
    pack = json.loads(path.read_text(encoding="utf-8"))
    violations: list[dict] = []
    for phase in ("pre_t0", "t0"):
        for item in compliance.validate_copy_pack(pack, lexicon, phase):
            item = dict(item)
            item["path"] = "%s[phase=%s]" % (target["path"], phase)
            item["mode"] = "strict(phase=%s)" % phase
            violations.append(item)
    return violations


def lint_text_file(target: dict, lexicon: dict) -> list[dict]:
    path = ROOT / target["path"]
    if not path.is_file():
        return [
            {
                "id": "MISSING",
                "path": target["path"],
                "mode": target["mode"],
                "reason": "清单中的扫描目标不存在（缺少物料即视为不合规）",
                "matched": "",
                "severity": "missing_target",
            }
        ]
    phase = target.get("phase") or ("pre_t0" if target["mode"] == "strict" else "t0")
    quoted = target["mode"] == "quoted"
    text = path.read_text(encoding="utf-8", errors="replace")
    # ① 带豁免标记的判定（物料文件里「禁令政策行」会合法地提到禁用词）
    out = []
    for item in compliance.find_violations(text, lexicon, phase, quoted=quoted, markers_ok=True):
        item = dict(item)
        item["path"] = target["path"]
        item["mode"] = target["mode"]
        out.append(item)
    # ② 无豁免的原始命中数（透明性：报告里两个数都给）
    raw = compliance.find_violations(text, lexicon, phase, quoted=False, markers_ok=False)
    target["_raw_hits"] = len(raw)
    target["_raw_detail"] = ["%s:%s" % (r["id"], r["matched"]) for r in raw]
    return out


def lint_dir(target: dict, lexicon: dict) -> list[dict]:
    base = ROOT / target["path"]
    if not base.exists():
        return [
            {
                "id": "MISSING",
                "path": target["path"],
                "mode": target["mode"],
                "reason": "清单中的扫描目录不存在",
                "matched": "",
                "severity": "missing_target",
            }
        ]
    out: list[dict] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        sub_target = {"path": str(path.relative_to(ROOT)), "mode": "strict"}
        out.extend(lint_text_file(sub_target, lexicon))
    return out


def check_required_tokens(manifest: dict, lexicon: dict) -> list[dict]:
    """必含项（如留资页必须写明收集目的/保留期/退出方式）。"""
    out: list[dict] = []
    scopes = manifest.get("required_token_scopes", {})
    for scope, spec in scopes.items():
        path = ROOT / spec["path"]
        if not path.is_file():
            out.append(
                {
                    "id": "RT-SCOPE",
                    "path": spec["path"],
                    "mode": "required",
                    "reason": "必含项所在文件不存在（scope=%s）" % scope,
                    "matched": "",
                    "severity": "required_missing",
                }
            )
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        node = data
        for part in spec["node"].split("."):
            node = node[part] if isinstance(node, dict) else {}
        text = node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)
        for rule in lexicon.get("required_tokens", []):
            if rule["scope"] != scope:
                continue
            import re

            if not re.search(rule["pattern"], text):
                out.append(
                    {
                        "id": rule["id"],
                        "path": "%s[%s]" % (spec["path"], spec["node"]),
                        "mode": "required",
                        "reason": rule["reason"],
                        "matched": "(缺失：%s)" % rule["pattern"],
                        "severity": "required_missing",
                    }
                )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="投放素材合规审查")
    parser.add_argument("--report-only", action="store_true", help="不写报告文件")
    args = parser.parse_args(argv)

    lexicon = compliance.load_lexicon(str(LEXICON_PATH))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    results: list[dict] = []
    per_target: list[tuple[dict, list[dict]]] = []
    for target in manifest["targets"]:
        if target["path"] == "marketing/landing/copy_pack.json":
            found = lint_copy_pack(target, lexicon)
        elif target["mode"] == "strict_text_only":
            found = lint_dir(target, lexicon)
        else:
            found = lint_text_file(target, lexicon)
        found += check_required_tokens(manifest, lexicon) if target["id"] == "T-01" else []
        per_target.append((target, found))
        results += found

    blocking = [v for v in results if v.get("severity") != "required_missing"]
    warnings = [v for v in results if v.get("severity") == "required_missing"]

    lines = [
        "# 投放素材合规审查报告（PRO-10）",
        "",
        "> 由 `marketing/scripts/compliance_lint.py` 生成。词表：`marketing/compliance/lexicon.json`（hard_ban %d 条 + t0_gated %d 条）；"
        "清单：`marketing/compliance/scan_manifest.json`。"
        % (len(lexicon.get("hard_ban", [])), len(lexicon.get("t0_gated", []))),
        "> 生成时间（UTC）：%s" % datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "",
        "## 结论",
        "",
        "- 阻断级违规（带标记词豁免后的判定，即真正会进入投放的表述）：**%d**" % len(blocking),
        "- 告警级（必含项缺失）：**%d**" % len(warnings),
        "- 判定：**%s**" % ("通过（可投放）" if not blocking else "不通过（禁止投放）"),
        "",
        "### 豁免方法与透明性说明",
        "",
        "物料文件同时包含「正文」与「禁令政策」（例：某文件写着「本期不做 X」）。审查器对**同一行**命中时，",
        "若该行含 `quoted_context_markers` 或 `policy_markers` 任一词，则视为政策/引用语境而豁免，并把",
        "**无豁免的原始命中数**一并列在下方（供人工逐条核对，避免用豁免掩盖真实违规）。",
        "**落地页启动门禁不走豁免路径**（`marketing/landing/app.py` 调用时不传 `markers_ok`），保持严格。",
        "",
        "## 逐目标结果",
        "",
        "| # | 扫描目标 | 模式 | 豁免后判定 | 原始命中（含政策语境） |",
        "|---|---|---|---|---:|",
    ]
    for target, found in per_target:
        bad = [v for v in found if v.get("severity") != "required_missing"]
        warn = [v for v in found if v.get("severity") == "required_missing"]
        verdict = "✅ 通过" if not bad and not warn else ("⚠️ 告警 %d" % len(warn) if not bad else "❌ 违规 %d" % len(bad))
        lines.append(
            "| %s | `%s` | %s | %s | %s |"
            % (target["id"], target["path"], target["mode"], verdict, target.get("_raw_hits", 0))
        )
        if target.get("_raw_detail"):
            lines.append(
                "| | ↳ 原始命中明细 | | | %s |"
                % "、".join(sorted(set(target["_raw_detail"])))[:220]
            )

    if blocking or warnings:
        lines += ["", "## 明细", "", "| 级别 | 规则 | 位置 | 命中 | 依据 |", "|---|---|---|---|---|"]
        for v in blocking + warnings:
            lines.append(
                "| %s | %s | `%s` | `%s` | %s |"
                % (
                    v.get("severity", ""),
                    v.get("id", ""),
                    v.get("path", ""),
                    str(v.get("matched", ""))[:60],
                    v.get("reason", ""),
                )
            )
    else:
        lines += ["", "无任何命中：所有扫描目标均未出现 §3.5 黑名单词与 §5.4 红线表述。", ""]

    lines += [
        "",
        "## 复审要求",
        "",
        "- 本报告是**机器自检**，不是人工终审：Editor 仍需按 §3.5/§5.4 做一次人工通读（机器只能证明「没有出现禁用表述」）。",
        "- 词表与本清单变更后必须重跑本脚本；报告文件就地覆盖，不保留历史版本。",
        "",
    ]

    text = "\n".join(lines)
    if not args.report_only:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(text, encoding="utf-8")

    print("[compliance-lint] hard_ban=%d t0_gated=%d 扫描目标=%d"
          % (len(lexicon.get("hard_ban", [])), len(lexicon.get("t0_gated", [])), len(manifest["targets"])))
    print("[compliance-lint] 阻断级违规：%d，告警级：%d" % (len(blocking), len(warnings)))
    for v in blocking + warnings:
        print("  - [%s] %s @ %s :: %s" % (v.get("severity"), v.get("id"), v.get("path"), str(v.get("matched"))[:70]))
    if not args.report_only:
        print("[compliance-lint] 报告：%s" % REPORT_PATH)
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
