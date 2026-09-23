# marketing/ —— 渠道执行包（PRO-10 交付物）

本目录是 **PRO-10「渠道落地包」的执行物料与工具**。方案依据：`docs/08-gtm-channel-execution-pack.md`（本单交付文档）；
上游口径：`docs/05-gtm-plan.md` §0.3 / §3.3 / §3.4 / §3.5 / §5.4、`docs/06` §4.3。

> 纪律：**T0（MVP 可灰度日，PRO-7 交付）之前，对外只允许不含量化承诺的招募信息**。
> 本仓库用「相位（phase）」把这条纪律做成机器可检查的门：`pre_t0` / `t0`。

---

## 1. 目录结构

```
marketing/
  compliance/     lexicon.json（合规词表）· scan_manifest.json（扫描清单）
  landing/        app.py（假门/分享落地页服务）· compliance.py（词表校验器）· copy_pack.json（文案包，两臂）
  scripts/        make_creator_links.py · qr.py · compliance_lint.py · power_analysis.py · simulate_traffic.py
  data/           seed_creators.csv（创作者台账）· share_scripts.md · creator_outreach.md
                  creator_promise_card.md（T0 起才可发）· community_scripts.md · naming_test_brief.md
  tests/          30 项单测（合规 / 落地页链路 / 链接生成 / QR 参考比对）
  reports/        asset-compliance-report.md · pro10-power-and-mde.md · selftest-synthetic-receipt.md
  out/            links.csv + links/*.txt + qr/*.svg|png（生成物）
```

## 2. 四条最常用命令

```bash
# ① 生成种子创作者专属链接与二维码（幂等）
python3 marketing/scripts/make_creator_links.py \
  --input marketing/data/seed_creators.csv \
  --outdir marketing/out \
  --landing-base <招募落地页基址> --app-base <应用侧基址>

# ② 合规自检（退出码非 0 = 禁止投放）
python3 marketing/scripts/compliance_lint.py

# ③ 样本量与 MDE 回执（判据能不能判定，先算再测）
python3 marketing/scripts/power_analysis.py

# ④ 起落地页服务并跑装置自检
python3 marketing/landing/app.py --port 8088 --db marketing/out/landing.sqlite3 --phase pre_t0
python3 marketing/scripts/simulate_traffic.py --base http://127.0.0.1:8088 --visitors 480 \
  --rates "V1:0.11,V2:0.08,V3:0.07" --seed 42
```

全部测试：`python3 -m unittest discover -s marketing/tests -t .`

## 3. 落地页服务

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 招募假门落地页（哈希等分 + 粘性 cookie） |
| GET | `/v/1|2|3` | 强制变体的招募页（定向投放对照，事件记 `forced=1`） |
| GET | `/s/<video_id>` | 分享落地页（直连可播放、不强制注册、看满 3 条后引导注册） |
| POST | `/api/events` | 事件：`page_view` / `cta_click` / `form_submit` / `view3` / `register_click` |
| POST | `/api/lead` | 留资（必须带 consent；重复提交不新增行） |
| POST | `/api/withdraw` | 撤回（contact 置空，统计不变） |
| GET | `/api/stats` | 分变体统计 + `v1_minus_max_v2_v3_pp` + 样本门（300/500）+ 命名分流 |
| GET | `/api/health` | 健康检查 |

**启动门禁**：`--phase` 决定文案臂；若当前臂含禁用表述（`pre_t0` 相位下含量化承诺），服务**拒绝启动**（exit code 2）。
因此「T0 前误投量化承诺」在装置层不可能发生。

## 4. 隐私与数据

- 留资只收**一个联系方式字段**；页面文案写明收集目的、保留 90 天、退出方式。
- 撤回路径：`POST /api/withdraw`（支持按 contact 或 visitor_id）；撤回后 contact 置空、统计口径不变。
- `ip_hash` 加盐（盐值首次启动随机生成并持久化），日志与响应**不打印联系方式原文**。
- 导出：`GET /api/export/leads?token=...`，仅当启动时设置 `--export-token` 才启用，否则 404。

## 5. 合规词表

- 词表：`compliance/lexicon.json`，分 `hard_ban`（任何相位都禁）与 `t0_gated`（T0 起才可用）。
- 豁免：物料文件里「禁令政策行」（含 `policy_markers`）不会被判违规；但报告同时给出**无豁免的原始命中数**，供人工核对。
- **落地页启动门禁不走豁免**（严格模式）。
- 变更词表只能改 `lexicon.json`，不得在物料里逐条豁免。

## 6. 已知限制

1. 业务判据在 T0 前一律「不可计算」，`reports/` 里的合成数字只证明装置算术正确，**不是实验结果**。
2. 二维码掩码选择为编码器自选项（不影响解码）；已用独立实现做「同一掩码逐格相等」验证。
3. 本目录**不含**商标/域名初筛、不含对外部署（属上线整合，由 Director of Go-to-Market 承接）。
