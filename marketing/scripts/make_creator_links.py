#!/usr/bin/env python3
"""渠道 2 落地包 —— 种子创作者专属链接 + 二维码生成器（纯标准库，离线可跑）。

用法：
    python3 marketing/scripts/make_creator_links.py \\
        --input marketing/data/seed_creators.csv \\
        --outdir marketing/out \\
        --landing-base http://127.0.0.1:8088 \\
        --app-base http://127.0.0.1:8080

输出（outdir 下）：
    links.csv               注册表（每行 = 一个创作者 × 一个平台）
    links/<link_id>.txt     人类可读清单（链接 + 用法）
    qr/<link_id>.svg        二维码（矢量，印刷用）
    qr/<link_id>.png        二维码（位图，社群发图用）

幂等性：同一输入文件重复运行输出**逐字节一致**（created_at 取输入文件 mtime，不取当前时间）。

utm 约定（顺序固定，不得插入其它参数）：
    recruit_url        = {landing}/?utm_source={platform}&utm_medium=creator_recruit
                         &utm_campaign=pro_launch_p1&utm_content={code}&ref={code}
    share_url_template = {app}/s/{video_id}?utm_source={platform}&utm_medium=creator_share
                         &utm_campaign=pro_launch_p1&utm_content={code}&ref={code}&v={variant}
两个链接是 §0.3 #5（来源参数 + 归因落库）的唯一取数依据，必须逐字使用，不得手改。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "marketing" / "scripts"))

import qr  # noqa: E402

CODE_RE = re.compile(r"^[a-z0-9]{4,16}$")
REQUIRED_COLUMNS = [
    "creator_code",
    "name",
    "platform",
    "vertical",
    "handle",
    "channel_url",
    "batch",
    "is_demo",
    "notes",
]
ALLOWED_VERTICALS = {"food-home", "food-dine-out", "local-life"}
ALLOWED_PLATFORMS = {"douyin", "xiaohongshu", "wechat", "bilibili", "kuaishou", "shipinhao"}
CAMPAIGN = "pro_launch_p1"

LEXICON_PATH = ROOT / "marketing" / "compliance" / "lexicon.json"


class InputError(Exception):
    """输入数据不合法（退出码 1）。"""


def load_hard_ban(lexicon_path: Path = LEXICON_PATH) -> list[dict]:
    data = json.loads(lexicon_path.read_text(encoding="utf-8"))
    return data.get("hard_ban", [])


def check_lexicon(text: str, rules: list[dict], where: str) -> list[str]:
    """hard_ban 命中即视为违规（对外链接与素材适用同一词表）。"""
    hits = []
    for rule in rules:
        m = re.search(rule["pattern"], text)
        if m:
            hits.append("%s [%s] 命中 %r（%s）" % (where, rule["id"], m.group(0), rule["reason"]))
    return hits


def build_urls(landing_base: str, app_base: str, platform: str, code: str) -> tuple[str, str]:
    landing = landing_base.rstrip("/")
    app = app_base.rstrip("/")
    recruit = (
        "%s/?utm_source=%s&utm_medium=creator_recruit&utm_campaign=%s&utm_content=%s&ref=%s"
        % (landing, platform, CAMPAIGN, code, code)
    )
    # {video_id} / {variant} 必须保留为字面量占位符：它们是模板，由分享时再填。
    share = (
        "%s/s/{video_id}?utm_source=%s&utm_medium=creator_share&utm_campaign=%s"
        "&utm_content=%s&ref=%s&v={variant}" % (app, platform, CAMPAIGN, code, code)
    )
    return recruit, share


def read_rows(csv_path: Path) -> list[dict]:
    if not csv_path.is_file():
        raise InputError("找不到输入台账：%s" % csv_path)
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise InputError("台账缺少列：%s（实际表头 %s）" % (missing, header))
        rows = []
        for idx, raw in enumerate(reader, start=2):  # 2 = 首个数据行
            row = {k: (raw.get(k) or "").strip() for k in REQUIRED_COLUMNS}
            if not any(row.values()):
                continue
            code = row["creator_code"]
            if not CODE_RE.match(code):
                raise InputError(
                    "第 %d 行 creator_code=%r 非法：必须匹配 ^[a-z0-9]{4,16}$" % (idx, code)
                )
            if row["vertical"] and row["vertical"] not in ALLOWED_VERTICALS:
                raise InputError(
                    "第 %d 行 vertical=%r 非法：只允许 %s"
                    % (idx, row["vertical"], sorted(ALLOWED_VERTICALS))
                )
            if row["platform"] not in ALLOWED_PLATFORMS:
                raise InputError(
                    "第 %d 行 platform=%r 非法：只允许 %s"
                    % (idx, row["platform"], sorted(ALLOWED_PLATFORMS))
                )
            row["_line"] = idx
            rows.append(row)

    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["creator_code"], row["platform"])
        if key in seen:
            raise InputError(
                "重复的 (creator_code, platform)=%s：第 %d 行与第 %d 行冲突"
                % (key, seen[key], row["_line"])
            )
        seen[key] = row["_line"]
    return rows


def render_entry(row: dict, recruit: str, share: str) -> str:
    return "\n".join(
        [
            "创作者：%s（%s / %s）" % (row["name"] or "待录入", row["creator_code"], row["handle"] or "待录入"),
            "平台：%s    垂类：%s    批次：%s" % (row["platform"], row["vertical"], row["batch"]),
            "",
            "【招募链接 · 直接发给创作者本人】",
            recruit,
            "",
            "【分享链接模板 · 创作者发给自己观众，需替换两个占位符】",
            share,
            "  {video_id} → 视频 id；{variant} → 1/2/3（对应 V1 确定性 / V2 收益透明 / V3 省时间）",
            "  示例：" + share.replace("{video_id}", "v_demo01").replace("{variant}", "1"),
            "",
            "【二维码】",
            "  qr/%s.svg（矢量，印刷 / 课件）    qr/%s.png（位图，社群发图）" % (row["_link_id"], row["_link_id"]),
            "  二维码内容 = 上面的招募链接（逐字一致，不得手改参数）",
            "",
            "注意：以上链接带来源参数，是站外回流归因（边 v / r）的唯一取数依据；",
            "      不得替换为短链或去参数链接，否则该创作者的贡献将无法计入循环。",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成种子创作者专属链接与二维码")
    parser.add_argument("--input", required=True, help="创作者台账 CSV")
    parser.add_argument("--outdir", required=True, help="输出目录（会创建 links/ 与 qr/）")
    parser.add_argument("--landing-base", required=True, help="招募假门落地页基址")
    parser.add_argument("--app-base", required=True, help="分享落地页（应用侧）基址")
    parser.add_argument("--ecc", default="M", help="二维码纠错等级（默认 M）")
    parser.add_argument("--scale", type=int, default=8, help="二维码像素倍率（默认 8）")
    args = parser.parse_args(argv)

    csv_path = Path(args.input).expanduser()
    outdir = Path(args.outdir).expanduser()
    try:
        rules = load_hard_ban()
        rows = read_rows(csv_path)
    except InputError as exc:
        print("[make_creator_links] 输入错误：%s" % exc, file=sys.stderr)
        return 1

    if not rows:
        print("[make_creator_links] 台账为空，无内容可生成", file=sys.stderr)
        return 1

    created_at = datetime.fromtimestamp(csv_path.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    links_dir = outdir / "links"
    qr_dir = outdir / "qr"
    links_dir.mkdir(parents=True, exist_ok=True)
    qr_dir.mkdir(parents=True, exist_ok=True)

    violations: list[str] = []
    registry: list[dict] = []
    written: list[str] = []

    for row in rows:
        code = row["creator_code"]
        platform = row["platform"]
        link_id = "%s_%s" % (code, platform)
        record = dict(row)
        record["_link_id"] = link_id
        recruit, share = build_urls(args.landing_base, args.app_base, platform, code)

        # 词表校验：链接、台账文本字段都要过 hard_ban
        for where, text in (
            ("links/%s recruit_url" % link_id, recruit),
            ("links/%s share_url_template" % link_id, share),
            ("台账 %s 文本字段" % link_id, " ".join(row[c] for c in REQUIRED_COLUMNS if c != "_line")),
        ):
            violations.extend(check_lexicon(text, rules, where))

        try:
            matrix = qr.encode(recruit, args.ecc)
        except ValueError as exc:
            violations.append("links/%s 二维码无法编码：%s" % (link_id, exc))
            continue

        txt_path = links_dir / ("%s.txt" % link_id)
        svg_path = qr_dir / ("%s.svg" % link_id)
        png_path = qr_dir / ("%s.png" % link_id)
        txt_path.write_text(render_entry(record, recruit, share), encoding="utf-8")
        svg_path.write_text(
            qr.to_svg(matrix, scale=args.scale, dark="#0b0b0b", light="#ffffff"), encoding="utf-8"
        )
        png_path.write_bytes(qr.to_png(matrix, scale=args.scale))

        written += [str(txt_path), str(svg_path), str(png_path)]
        registry.append(
            {
                "creator_code": code,
                "platform": platform,
                "vertical": row["vertical"],
                "handle": row["handle"],
                "batch": row["batch"],
                "is_demo": row["is_demo"],
                "link_id": link_id,
                "recruit_url": recruit,
                "share_url_template": share,
                "qr_svg": str(svg_path.relative_to(outdir)),
                "qr_png": str(png_path.relative_to(outdir)),
                "qr_version": qr.version_of(recruit, args.ecc),
                "created_at": created_at,
            }
        )

    if violations:
        print("[make_creator_links] 词表校验失败，未写出注册表：", file=sys.stderr)
        for v in violations:
            print("  - %s" % v, file=sys.stderr)
        return 1

    registry.sort(key=lambda r: (r["creator_code"], r["platform"]))
    csv_out = outdir / "links.csv"
    fields = [
        "creator_code",
        "platform",
        "vertical",
        "handle",
        "batch",
        "is_demo",
        "link_id",
        "recruit_url",
        "share_url_template",
        "qr_svg",
        "qr_png",
        "qr_version",
        "created_at",
    ]
    with csv_out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for rec in registry:
            writer.writerow({k: rec.get(k, "") for k in fields})

    real = sum(1 for r in registry if r["is_demo"] == "0")
    print("[make_creator_links] 完成：%d 名创作者 / %d 条链接（其中正式 %d、演示 %d）"
          % (len({r["creator_code"] for r in registry}), len(registry), real, len(registry) - real))
    print("[make_creator_links] 注册表：%s" % csv_out)
    print("[make_creator_links] 二维码：%s（svg+png 各 %d 个）" % (qr_dir, len(registry)))
    print("[make_creator_links] 词表校验：%d 条 hard_ban 规则全部通过" % len(rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
