# ⚠️ 合成流量装置自检，非业务判据，不得对外

> ⚠️ 合成流量装置自检，非业务判据，不得对外

- 生成时间（UTC）：2026-09-23T16:46:40+00:00
- base：`http://127.0.0.1:8088`
- 命令：`python3 marketing/scripts/simulate_traffic.py --base http://127.0.0.1:8088 --visitors 480 --rates "V1:0.11,V2:0.08,V3:0.07" --seed 42`
- 访客数：480，seed=42，rates={"V1": 0.11, "V2": 0.08, "V3": 0.07}
- 装置侧计数：{"page_view": 480, "cta_click": 39, "form_submit": 39, "duplicated": 0}

## /api/stats（合成流量，非业务结论）

```json
{
  "phase": "pre_t0",
  "sample": {
    "recruit_page_view": 480,
    "gate_300": true,
    "gate_500": false,
    "reached_300": true,
    "reached_500": false
  },
  "by_variant": {
    "recruit": {
      "V1": {
        "page_view": 160,
        "cta_click": 16,
        "form_submit": 16,
        "cta_rate": 0.1,
        "submit_rate": 0.1
      },
      "V2": {
        "page_view": 160,
        "cta_click": 15,
        "form_submit": 15,
        "cta_rate": 0.09375,
        "submit_rate": 0.09375
      },
      "V3": {
        "page_view": 160,
        "cta_click": 8,
        "form_submit": 8,
        "cta_rate": 0.05,
        "submit_rate": 0.05
      }
    },
    "share": {
      "V1": {
        "page_view": 0,
        "cta_click": 0,
        "register_click": 0,
        "cta_rate": null,
        "register_rate": null
      },
      "V2": {
        "page_view": 0,
        "cta_click": 0,
        "register_click": 0,
        "cta_rate": null,
        "register_rate": null
      },
      "V3": {
        "page_view": 0,
        "cta_click": 0,
        "register_click": 0,
        "cta_rate": null,
        "register_rate": null
      }
    }
  },
  "decision": {
    "submit_rate_ge_8pct": true,
    "v1_minus_max_v2_v3_pp": 0.63,
    "pass": false
  },
  "naming": {},
  "balance": {
    "recruit_page_view": {
      "V1": 160,
      "V2": 160,
      "V3": 160
    },
    "share_page_view": {
      "V1": 0,
      "V2": 0,
      "V3": 0
    },
    "assignments": {
      "V1": 180,
      "V2": 139,
      "V3": 161
    },
    "max_minus_min_pct": 0.0,
    "balanced": true
  }
}
```

**⚠️ 合成流量装置自检，非业务判据，不得对外**
