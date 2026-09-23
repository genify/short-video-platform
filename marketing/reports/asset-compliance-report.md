# 投放素材合规审查报告（PRO-10）

> 由 `marketing/scripts/compliance_lint.py` 生成。词表：`marketing/compliance/lexicon.json`（hard_ban 15 条 + t0_gated 6 条）；清单：`marketing/compliance/scan_manifest.json`。
> 生成时间（UTC）：2026-09-23T16:49:04+00:00

## 结论

- 阻断级违规（带标记词豁免后的判定，即真正会进入投放的表述）：**0**
- 告警级（必含项缺失）：**0**
- 判定：**通过（可投放）**

### 豁免方法与透明性说明

物料文件同时包含「正文」与「禁令政策」（例：某文件写着「本期不做 X」）。审查器对**同一行**命中时，
若该行含 `quoted_context_markers` 或 `policy_markers` 任一词，则视为政策/引用语境而豁免，并把
**无豁免的原始命中数**一并列在下方（供人工逐条核对，避免用豁免掩盖真实违规）。
**落地页启动门禁不走豁免路径**（`marketing/landing/app.py` 调用时不传 `markers_ok`），保持严格。

## 逐目标结果

| # | 扫描目标 | 模式 | 豁免后判定 | 原始命中（含政策语境） |
|---|---|---|---|---:|
| T-01 | `marketing/landing/copy_pack.json` | strict | ✅ 通过 | 0 |
| T-02 | `marketing/data/community_scripts.md` | strict | ✅ 通过 | 3 |
| | ↳ 原始命中明细 | | | HB-08:站内关系链、HB-12:收入承诺、HB-15:买量 |
| T-03 | `marketing/data/share_scripts.md` | strict | ✅ 通过 | 0 |
| T-04 | `marketing/data/creator_outreach.md` | strict | ✅ 通过 | 2 |
| | ↳ 原始命中明细 | | | HB-15:买量、TG-06:承诺（如曝光 |
| T-05 | `marketing/data/naming_test_brief.md` | strict | ✅ 通过 | 2 |
| | ↳ 原始命中明细 | | | HB-08:站内关系链、HB-15:买量 |
| T-06 | `docs/08-gtm-channel-execution-pack.md` | quoted | ✅ 通过 | 5 |
| | ↳ 原始命中明细 | | | HB-01:保底曝光、HB-08:站内关系链、HB-09:算法更准、HB-14:对手不透明、HB-15:买量 |
| T-07 | `marketing/out/links.csv` | strict | ✅ 通过 | 0 |
| T-08 | `marketing/out/qr/` | strict_text_only | ✅ 通过 | 0 |
| T-09 | `marketing/data/creator_promise_card.md` | strict | ✅ 通过 | 1 |
| | ↳ 原始命中明细 | | | HB-12:收入承诺 |

无任何命中：所有扫描目标均未出现 §3.5 黑名单词与 §5.4 红线表述。


## 复审要求

- 本报告是**机器自检**，不是人工终审：Editor 仍需按 §3.5/§5.4 做一次人工通读（机器只能证明「没有出现禁用表述」）。
- 词表与本清单变更后必须重跑本脚本；报告文件就地覆盖，不保留历史版本。
