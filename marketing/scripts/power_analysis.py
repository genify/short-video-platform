#!/usr/bin/env python3
"""假门/命名测试的样本量与最小可检测差异（MDE）计算器（纯标准库）。

为什么需要它：PRO-8 §3.2 / §4.2 与 PRO-10 判据写的是「样本 300–500 访客、判据
V1 − max(V2,V3) ≥ 3pp」。这是**判据**，但 300–500 访客是否足以判定 3pp，需要先算出来，
否则会出现「样本没到、却按 3pp 下结论」的假结论。

用法：
    python3 marketing/scripts/power_analysis.py                 # 打印并写回执
    python3 marketing/scripts/power_analysis.py --out marketing/reports/pro10-power-and-mde.md

约定：两比例 z 检验，双侧；三臂等分（V1/V2/V3 各 1/3 流量）；
     「V1 − max(V2,V3) ≥ 3pp」是两次比较（V1 vs V2、V1 vs V3），故同时给出
     Bonferroni 修正（每次比较 α=0.025）下所需的样本量。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

Z_ALPHA_05 = 1.959963985  # 双侧 0.05
Z_ALPHA_025 = 2.241402728  # 双侧 0.05 + Bonferroni(2 次比较)
Z_BETA_80 = 0.841621234  # 80% 功效


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def power_two_proportions(p1: float, p2: float, n_per_arm: int, z_alpha: float = Z_ALPHA_05) -> float:
    """等样本两比例 z 检验的双侧功效（正态近似）。"""
    if n_per_arm <= 0:
        return 0.0
    se_null = math.sqrt((p1 + p2) / 2.0 * (1 - (p1 + p2) / 2.0) * 2.0 / n_per_arm)
    se_alt = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n_per_arm)
    if se_alt == 0:
        return 1.0
    return _phi((abs(p1 - p2) - z_alpha * se_null) / se_alt)


def n_per_arm_required(p1: float, p2: float, power: float = 0.80, z_alpha: float = Z_ALPHA_05) -> float:
    """达到指定功效所需每臂样本量（正态近似闭式，再迭代 3 次收敛）。"""
    z_beta = Z_BETA_80 if abs(power - 0.80) < 1e-9 else 0.0
    n = 1.0
    for _ in range(60):
        p_bar = (p1 + p2) / 2.0
        num = z_alpha * math.sqrt(2 * p_bar * (1 - p_bar)) + z_beta * math.sqrt(
            p1 * (1 - p1) + p2 * (1 - p2)
        )
        n = (num / (p1 - p2)) ** 2
    return n


def mde(baseline: float, n_per_arm: int, power: float = 0.80, z_alpha: float = Z_ALPHA_05) -> float:
    """给定每臂样本量下可检测的最小差异（绝对百分点，二分法）。"""
    lo, hi = 1e-6, 0.95 - baseline
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if power_two_proportions(baseline + mid, baseline, n_per_arm, z_alpha) >= power:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def build_report() -> dict:
    scenarios = []
    # 场景：假门留资（主判据 form_submit），基线 = 较弱臂的留资率
    for total in (300, 360, 450, 500, 1500, 3000, 4500):
        for baseline in (0.06, 0.08, 0.10):
            n_arm = total / 3.0
            scenarios.append(
                {
                    "test": "假门留资 V1 vs max(V2,V3)",
                    "total_visitors": total,
                    "n_per_arm": round(n_arm, 1),
                    "baseline_rate": baseline,
                    "target_diff_pp": 3.0,
                    "power_for_3pp": round(power_two_proportions(baseline + 0.03, baseline, int(round(n_arm))), 3),
                    "power_for_3pp_bonferroni": round(
                        power_two_proportions(baseline + 0.03, baseline, int(round(n_arm)), Z_ALPHA_025), 3
                    ),
                    "mde_pp_80power": round(100 * mde(baseline, int(round(n_arm))), 2),
                    "n_per_arm_needed_for_3pp": int(math.ceil(n_per_arm_required(baseline + 0.03, baseline))),
                    "n_total_needed_for_3pp": int(3 * math.ceil(n_per_arm_required(baseline + 0.03, baseline))),
                    "n_total_needed_for_3pp_bonferroni": int(
                        3 * math.ceil(n_per_arm_required(baseline + 0.03, baseline, z_alpha=Z_ALPHA_025))
                    ),
                }
            )
    # 场景：命名分流（判据 cta_click 差异 ≥ 3pp），单批 3 候选
    naming = []
    for total in (300, 500, 900, 1500, 3000):
        for baseline in (0.10, 0.15, 0.25, 0.35):
            n_arm = total / 3.0
            naming.append(
                {
                    "test": "命名分流（每批 3 个候选）",
                    "total_visitors": total,
                    "n_per_arm": round(n_arm, 1),
                    "baseline_cta_rate": baseline,
                    "power_for_3pp": round(power_two_proportions(baseline + 0.03, baseline, int(round(n_arm))), 3),
                    "mde_pp_80power": round(100 * mde(baseline, int(round(n_arm))), 2),
                    "n_total_needed_for_3pp": int(3 * math.ceil(n_per_arm_required(baseline + 0.03, baseline))),
                }
            )
    # 场景：9 个候选一次分流（PRO-8 §4.2 明确反对的做法）
    nine = []
    for total in (300, 500):
        n_arm = total / 9.0
        nine.append(
            {
                "test": "命名分流（9 个候选一批，仅作反例）",
                "total_visitors": total,
                "n_per_arm": round(n_arm, 1),
                "baseline_cta_rate": 0.15,
                "mde_pp_80power": round(100 * mde(0.15, int(round(n_arm))), 2),
            }
        )
    return {
        "assumptions": {
            "test": "two-proportion z-test, two-sided",
            "alpha": 0.05,
            "power": 0.80,
            "split": "V1/V2/V3 等分（各 1/3）",
            "note": "「V1 − max(V2,V3)」是 2 次比较，另一列给出 Bonferroni(α=0.025) 所需样本量",
        },
        "fake_door": scenarios,
        "naming": naming,
        "naming_nine_cell_antipattern": nine,
    }


def render_markdown(data: dict) -> str:
    lines = [
        "# 假门 / 命名测试样本量与 MDE 回执（PRO-10）",
        "",
        "> ⚠️ 本文件由 `marketing/scripts/power_analysis.py` 生成，是**统计功效计算**（设计参数），",
        "> **不是实验结果**，也不是已发生的业务数据；不得作为对外数字使用。",
        "",
        "假设：" + json.dumps(data["assumptions"], ensure_ascii=False),
        "",
        "## 1. 假门留资（主判据 form_submit，判据 V1 − max(V2,V3) ≥ 3pp）",
        "",
        "| 总访客 | 每臂 | 较弱臂基线 | 检测 3pp 的功效 | 功效(α=0.025) | 80% 功效下 MDE | 检测 3pp 所需总样本 | 所需总样本(Bonferroni) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in data["fake_door"]:
        lines.append(
            "| {total_visitors} | {n_per_arm} | {b:.0%} | {p:.1%} | {pb:.1%} | {m:.1f}pp | {n} | {nb} |".format(
                b=s["baseline_rate"],
                p=s["power_for_3pp"],
                pb=s["power_for_3pp_bonferroni"],
                m=s["mde_pp_80power"],
                n=s["n_total_needed_for_3pp"],
                nb=s["n_total_needed_for_3pp_bonferroni"],
                **{k: s[k] for k in ("total_visitors", "n_per_arm")},
            )
        )
    lines += [
        "",
        "## 2. 命名分流（判据 cta_click 差异 ≥ 3pp，每批 3 个候选）",
        "",
        "| 总访客 | 每臂 | 基线 cta_click | 检测 3pp 的功效 | 80% 功效下 MDE | 检测 3pp 所需总样本 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for s in data["naming"]:
        lines.append(
            "| {total_visitors} | {n_per_arm} | {b:.0%} | {p:.1%} | {m:.1f}pp | {n} |".format(
                b=s["baseline_cta_rate"],
                p=s["power_for_3pp"],
                m=s["mde_pp_80power"],
                n=s["n_total_needed_for_3pp"],
                **{k: s[k] for k in ("total_visitors", "n_per_arm")},
            )
        )
    lines += [
        "",
        "## 3. 反例：9 个候选一批分流（PRO-8 §4.2 明确反对）",
        "",
        "| 总访客 | 每臂 | 基线 | 80% 功效下 MDE |",
        "|---:|---:|---:|---:|",
    ]
    for s in data["naming_nine_cell_antipattern"]:
        lines.append(
            "| {total_visitors} | {n_per_arm} | {b:.0%} | {m:.1f}pp |".format(
                b=s["baseline_cta_rate"], m=s["mde_pp_80power"], **{k: s[k] for k in ("total_visitors", "n_per_arm")}
            )
        )
    lines += ["", "## 4. 结论（判据回执口径）", "", _conclusion(data), ""]
    return "\n".join(lines)


def _conclusion(data: dict) -> str:
    rows = [s for s in data["fake_door"] if s["total_visitors"] in (300, 500) and s["baseline_rate"] == 0.08]
    l1 = (
        "- 在判据给定的 300–500 访客、三臂等分下，每臂仅 100–167 人；以较弱臂 8% 留资率为基线，"
        "80% 功效下可检测的最小差异约 {a:.1f}–{b:.1f}pp，远大于判据要求的 3pp。"
    ).format(a=min(r["mde_pp_80power"] for r in rows), b=max(r["mde_pp_80power"] for r in rows))
    l2 = (
        "- 即：300–500 访客不足以判定 3pp。要判定 3pp（80% 功效、α=0.05）需约 {n} 名访客（三臂合计）；"
    ).format(n=min(r["n_total_needed_for_3pp"] for r in rows))
    l3 = "- 若为避免多重比较做 Bonferroni 修正（α=0.025），所需样本进一步升至约 {n} 名访客。".format(
        n=min(r["n_total_needed_for_3pp_bonferroni"] for r in rows)
    )
    l4 = "- 因此本单不把 300–500 访客的读数当作「3pp 判定」，只作为方向性判据；正式判定按预设规则执行。"
    l5 = (
        "- 命名分流必须分批（每批 3 个候选）：9 个候选一批会把每臂压到 33–56 人，"
        "MDE 达到 {a:.0f}–{b:.0f}pp，等于放弃判定能力（与 PRO-8 §4.2 的结论一致）。"
    ).format(
        a=min(s["mde_pp_80power"] for s in data["naming_nine_cell_antipattern"]),
        b=max(s["mde_pp_80power"] for s in data["naming_nine_cell_antipattern"]),
    )
    return "\n".join([l1, l2, l3, l4, l5]) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="样本量与 MDE 计算")
    parser.add_argument(
        "--out",
        default=str(ROOT / "marketing" / "reports" / "pro10-power-and-mde.md"),
        help="Markdown 回执输出路径",
    )
    parser.add_argument("--json", action="store_true", help="同时输出 JSON")
    args = parser.parse_args(argv)

    data = build_report()
    md = render_markdown(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")

    # 控制台：只打印最关键的三行，避免刷屏
    key = [s for s in data["fake_door"] if s["total_visitors"] == 500 and s["baseline_rate"] == 0.08][0]
    print("[power] 500 访客 / 每臂 %s 人 / 基线 8%%：检测 3pp 的功效 %.1f%%，80%% 功效下 MDE %.1fpp"
          % (key["n_per_arm"], 100 * key["power_for_3pp"], key["mde_pp_80power"]))
    print("[power] 判定 3pp 所需总样本：%d（Bonferroni: %d）"
          % (key["n_total_needed_for_3pp"], key["n_total_needed_for_3pp_bonferroni"]))
    print("[power] 回执写入：%s" % out)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
