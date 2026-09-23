#!/usr/bin/env python3
"""合成流量自检装置（纯标准库）。

    python3 marketing/scripts/simulate_traffic.py \
        --base http://127.0.0.1:8088 --visitors 480 \
        --rates "V1:0.11,V2:0.08,V3:0.07" --seed 42

它用 urllib 打真实 HTTP 接口：606 个访客依次
  ① GET /v/1|2|3   —— 强制变体的招募页（服务端入账 page_view）
  ② 以 rates[V] 的概率 POST /api/lead（consent=true）→ form_submit
最后取 /api/stats 并把结果写入 marketing/reports/selftest-synthetic-receipt.md。

⚠️ 这是装置自检，不是业务判据：产出数字全部是合成的。
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # marketing/scripts -> marketing -> <ROOT>
REPORT_PATH = os.path.join(ROOT, "marketing", "reports", "selftest-synthetic-receipt.md")
VARIANT_TO_INDEX = {"V1": 1, "V2": 2, "V3": 3}
VARIANT_ORDER = ("V1", "V2", "V3")

WARNING = "⚠️ 合成流量装置自检，非业务判据，不得对外"


def parse_rates(text: str) -> dict[str, float]:
    rates: dict[str, float] = {v: 0.0 for v in VARIANT_ORDER}
    for chunk in (text or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        key, _, value = chunk.partition(":")
        key = key.strip().upper()
        if key not in rates:
            raise SystemExit(f"未知变体 {key!r}，应为 V1/V2/V3")
        try:
            rates[key] = float(value)
        except ValueError:
            raise SystemExit(f"概率无法解析：{chunk!r}")
    return rates


def _fetch(opener: urllib.request.OpenerDirector, url: str, data: bytes | None = None) -> str:
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with opener.open(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def _post_json(opener: urllib.request.OpenerDirector, url: str, payload: dict) -> dict:
    return json.loads(_fetch(opener, url, json.dumps(payload).encode("utf-8")))


def run(base: str, visitors: int, rates: dict[str, float], seed: int) -> dict:
    base = base.rstrip("/")
    rng = random.Random(seed)
    counters = {"page_view": 0, "cta_click": 0, "form_submit": 0, "duplicated": 0}

    for i in range(visitors):
        variant = VARIANT_ORDER[i % 3]  # 均衡投放三臂
        idx = VARIANT_TO_INDEX[variant]
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        # ① 落地页浏览（强制变体，服务端 page_view 入账）
        _fetch(opener, f"{base}/v/{idx}")
        counters["page_view"] += 1

        # ② 按概率留资
        if rng.random() < rates.get(variant, 0.0):
            _post_json(
                opener, f"{base}/api/events",
                {"event": "cta_click", "asset": "recruit", "variant": variant},
            )
            counters["cta_click"] += 1
            result = _post_json(
                opener, f"{base}/api/lead",
                {"contact": f"synth-{seed}-{i}@example.com", "consent": True, "variant": variant},
            )
            if result.get("duplicated"):
                counters["duplicated"] += 1
            else:
                counters["form_submit"] += 1

    stats = json.loads(_fetch(opener, f"{base}/api/stats"))
    return {"counters": counters, "stats": stats}


def write_receipt(command: str, base: str, visitors: int, rates: dict, seed: int, result: dict) -> str:
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"# {WARNING}",
        "",
        f"> {WARNING}",
        "",
        f"- 生成时间（UTC）：{stamp}",
        f"- base：`{base}`",
        f"- 命令：`{command}`",
        f"- 访客数：{visitors}，seed={seed}，rates={json.dumps(rates, ensure_ascii=False)}",
        f"- 装置侧计数：{json.dumps(result['counters'], ensure_ascii=False)}",
        "",
        "## /api/stats（合成流量，非业务结论）",
        "",
        "```json",
        json.dumps(result["stats"], ensure_ascii=False, indent=2),
        "```",
        "",
        f"**{WARNING}**",
        "",
    ]
    text = "\n".join(lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(text)
    return REPORT_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合成流量自检（纯标准库）")
    parser.add_argument("--base", default="http://127.0.0.1:8088")
    parser.add_argument("--visitors", type=int, default=480)
    parser.add_argument("--rates", default="V1:0.11,V2:0.08,V3:0.07")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    rates = parse_rates(args.rates)
    command = (
        f"python3 marketing/scripts/simulate_traffic.py --base {args.base} "
        f'--visitors {args.visitors} --rates "{args.rates}" --seed {args.seed}'
    )
    try:
        result = run(args.base, args.visitors, rates, args.seed)
    except urllib.error.URLError as exc:
        print(f"无法连接服务 {args.base}：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result["stats"], ensure_ascii=False, indent=2))
    path = write_receipt(command, args.base, args.visitors, rates, args.seed, result)
    print(f"\n[selftest] 合成回执已写入 {path}")
    print(f"[selftest] {WARNING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
