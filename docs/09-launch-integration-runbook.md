# 上线整合执行手册（落地页部署 · 流量承接 · T0 证据留痕 · 承诺卡 7 天兑现回收）

> **性质**：**装置 / 运维文档**，不是投放物料。本文件不产生任何对外文案；对外文案一律以
> `marketing/landing/copy_pack.json`（唯一现行文案包）为准。
> **承接**：PRO-24（上线整合移交，承接 PRO-20 放行并已完成 PRO-23 → PRO-25 → PRO-26 → PRO-27 → PRO-28 全部复审）。
> **放行状态（现行）**：以 `docs/08` **§15.6** 为准 —— PRO-26 判定 = 通过（0 阻断级）→ 执行包可进入
> 对外投放的上线整合；其后 PRO-28 窄范围复审判定 = **通过（0 阻断级）**，落地本手册不改变既有物料的任何判据。
> **本手册不写自身提交哈希**（提交哈希见 issue 评论）：pack 曾因文档内自指哈希失效而消耗一整轮复审。

---

## 1. 本单的四件事与当前完成度（如实）

| # | 交付物 | 本轮状态 | 证据位置 |
|---|---|---|---|
| 1 | 落地页部署为可访问 URL | **完成到本单可完成的边界**：装置已在**局域网**可达并留痕（`http://192.168.31.35:8088/`）；**公网部署已由 board 裁定推迟到 T0**（裁定 ③，见 §2.4 / §10）⇒ T0 前无「公网可达」待办 | §2 部署事实 · §3 冒烟回执 |
| 2 | 流量进入 | **未启动**（正确） | board 交互 `ba1deb68` 问题 1 已裁定 = **零预算、只用自然流量**；且裁定 ③ 明确 T0 前不开公网入口（§2.4）⇒ 无处引入流量 |
| 3 | T0 证据留痕与门禁纪律 | **装置与流程就绪**：演练 10/10 通过（含 `exit 3` 反证 + 信封边界取证） | §4 · `marketing/scripts/t0_evidence_drill.py` |
| 4 | 承诺卡发放与 7 天兑现回收 | **不可执行（登记为依赖）**：发卡前置「T0 到 + 兑现位可用」未成立；取数路径与责任人已逐条钉死 | §5 |

**本轮即开始的部分（不依赖 T0、不依赖流量裁定）全部完成**：部署环境与 URL 方案（§2）、落盘冒烟脚本（§3）、
`--t0-evidence` 填空演练（§4）、7 天兑现回收取数路径与责任人（§5）。

---

## 2. 部署环境与 URL 方案

### 2.1 装置事实（决定了部署形态）

`marketing/landing/app.py` 是**纯标准库** `ThreadingHTTPServer`，**零第三方依赖**、无框架、无外部服务，
因此部署 = 「用固定参数把该进程跑起来 + 一个可访问 URL 指向它」。三道启动硬门在启动时执行：
① 相位文案合规（`exit 2`）② `--phase t0` 的 T0 证据门禁（`exit 3`）③ 界面文案完整性（`exit 4`）。

### 2.2 部署参数（本轮实际使用，可复跑）

```bash
PD_BASE_URL="http://192.168.31.35:8088" bash marketing/scripts/landing_deploy.sh start
```

等效的等价手工命令（`landing_deploy.sh` 只是把下列参数固定下来）：

```bash
python3 marketing/landing/app.py \
  --host 0.0.0.0 --port 8088 \
  --db marketing/out/landing.prod.sqlite3 \
  --phase pre_t0 \
  --base-url http://192.168.31.35:8088
```

| 项 | 值 | 理由 |
|---|---|---|
| `--phase` | `pre_t0` | T0 前唯一可投相位；**不得**以 `--phase t0` 启动（T0 证据门禁，`exit 3`） |
| `--host/--port` | `0.0.0.0:8088` | 绑非回环地址，局域网内可达（已实测，见 §3.3）；`127.0.0.1` 只对本机可达 |
| `--db` | `marketing/out/landing.prod.sqlite3` | **正式分流统计库**（新库）：把此前装置自检遗留的 `marketing/out/landing.sqlite3`（11 招募 + 1 分享 `page_view`，12 条 `assignments`）与正式读数**物理隔离**，避免自检数据虚高样本门分母 |
| 日志 / pid | `marketing/out/landing.prod.log` / `.pid` | 上线运维与重启用；与数据库一同不纳入版本控制（`.gitignore`） |
| 进程托管 | `nohup setsid`（**无 supervisor**） | 见 §2.5 的如实限定 |

### 2.3 URL 规则（对外链接基址）= 已就绪但**待基址替换**

`docs/08` §1.1 的 URL 规则（顺序固定、不得手改）以 `{landing}` / `{app}` 为基址。**当前产物仍是占位基址**：
`marketing/out/links.csv` 中为 `https://landing.local/` 与 `https://app.local/`。

| 用途 | 模板 |
|---|---|
| 招募（发给创作者本人） | `{landing}/?utm_source={platform}&utm_medium=creator_recruit&utm_campaign=pro_launch_p1&utm_content={code}&ref={code}` |
| 分享（创作者发给自己观众） | `{app}/s/{video_id}?utm_source={platform}&utm_medium=creator_share&utm_campaign=pro_launch_p1&utm_content={code}&ref={code}&v={variant}` |

**依赖（不得由本单代做）**：基址一旦确定，`marketing/out/links.csv` 与 44 个二维码须由
**Marketing Strategist** 用 `marketing/scripts/make_creator_links.py`（幂等）重生成；
本单**不重跑物料生成脚本**（PRO-24 边界）。创作者链接未换成真实基址前，**该链接不可发出**。

### 2.4 公网可达：零预算下的**已裁定项**（board 裁定 = 选项 ③）

- 本机**无公网 IP**（`hostname -I` = `192.168.31.35` / `172.17.0.1`），仓内**无**反向代理与隧道工具
  （`cloudflared` / `ngrok` 均未安装）。
- 零预算 ⇒ 不购买云主机/域名；**又不做买量** ⇒ 自然流量仍需要一个**公开且稳定**的入口。
- 因此「落地页对外部署」的**公网部分**曾被登记为资源决策，按纪律提 issue 交互交 board（三选项：
  ① board/ops 提供公网主机 + 域名；② 批准零成本临时隧道（仅测试，地址会变）；③ 维持局域网可达、公网部署推迟到 T0）。
- **已裁定（board 交互 `1175c3ae-007d-4cb2-92e8-c8c79577f366`，答复时点 `2026-09-24T15:11:52Z`）= 选项 ③**：
  **维持局域网可达、公网部署推迟到 T0**。详见 §10 裁定落地记录。
- **裁定 ③ 的直接后果**：T0 前**不做**公网部署、**不引入**任何真实流量（与「零预算自然流量」裁定一致）；
  装置保持就绪（局域网可达）；`links.csv` 占位基址**维持**，链接在换到真实基址前**不得发出**（§2.3 / §7 #5）。
- **不得私自**把未做最小鉴权/限流的装置直接暴露到公网（装置无登录、无频控；`docs/05` §0.3 #1 尚未实现）。

### 2.5 如实限定（部署）

1. 本部署是**宿主进程**（`nohup setsid`），无 systemd/容器托管 ⇒ 宿主重启即失效；长期驻留需 board/ops 决定托管方式。
2. 本部署绑 `0.0.0.0` ⇒ **局域网内任何主机可访问**（采集页只有一个联系方式字段 + 明示同意 + 90 天保留 + 可撤回；无 IP/端口白名单）。
3. 本部署**不构成**「对外投放已开始」：公网入口已裁定为 T0 前不开（裁定 ③，§2.4）、流量未引入（§1 #2）。

---

## 3. 冒烟回执（本机实际输出，逐字）

脚本：`marketing/scripts/landing_smoke.py`（纯标准库，三模式）。**纪律：冒烟不得污染正式分流统计库**
（样本门 300/500 的分母只容许真实访客）。

### 3.1 装置链路全量冒烟（`--mode spawn`，独立实例 + 临时库 → 零污染）

```
$ python3 marketing/scripts/landing_smoke.py --mode spawn
[landing-smoke] mode=spawn base=http://127.0.0.1:8088
  · 启动命令：python3 marketing/landing/app.py --host 127.0.0.1 --port 38559 \
      --db /tmp/…/landing_smoke.sqlite3 --phase pre_t0 --base-url http://127.0.0.1:38559
  · 实例就绪：{"ok": true, "phase": "pre_t0", …}
[PASS] 实例启动 + /api/health — http://127.0.0.1:38559
[PASS] GET /api/stats（基线读数） — recruit/share page_view = {"recruit_page_view": 0, "share_page_view": 0}
[PASS] GET /（招募假门） — HTTP 200 · 页脚含 页面版本=pre_t0 · Set-Cookie=True
[PASS] GET /s/<video_id>（分享页） — HTTP 200 · 页脚含 视频=video-smoke-001
[PASS] POST /api/events（cta_click） — HTTP 200 · {"ok": true, "visitor_id": "ce44…", "variant": "V1"}
[PASS] POST /api/lead（consent=true） — HTTP 200 · {"ok": true, "lead_id": 1, "duplicated": false}
[PASS] POST /api/lead（重复 → duplicated=true） — HTTP 200 · {"ok": true, "lead_id": 1, "duplicated": true}
[PASS] POST /api/lead（无 consent → 400） — HTTP 400 · {"ok": false, "error": "必须同意数据使用说明（consent=true）"}
[PASS] POST /api/withdraw（撤回） — HTTP 200 · {"ok": true, "withdrawn": 1}
[PASS] GET /api/export/leads（未启用 → 404） — HTTP 404
[PASS] GET /no-such-route → 404 — HTTP 404
[PASS] GET /api/stats（末端复读：增量 = 1 招募 + 1 分享 page_view）
       — before={"recruit_page_view": 0, "share_page_view": 0} after={"recruit_page_view": 1, "share_page_view": 1} delta={"recruit": 1, "share": 1}
[PASS] GET /api/stats（判据字段齐备） — decision={"submit_rate_ge_8pct": true, "v1_minus_max_v2_v3_pp": null, "pass": false}
[PASS] 正式分流统计库未被触碰 — marketing/out/landing.sqlite3 mtime 不变
  · 实例已停止，临时库已清理：True
[landing-smoke] 检查 14/14 通过 → PASS
```

### 3.2 部署实例验收冒烟（`--mode live`，真实 `GET`）

```
$ python3 marketing/scripts/landing_smoke.py --mode live --base http://127.0.0.1:8088
[landing-smoke] mode=live base=http://127.0.0.1:8088
[PASS] GET /api/stats（基线读数） — recruit/share page_view = {"recruit_page_view": 0, "share_page_view": 0}
[PASS] GET /（招募假门） — HTTP 200 · 页脚相位标记=True
[PASS] GET /s/<video_id>（分享页） — HTTP 200
[PASS] GET /api/stats — HTTP 200
  · ⚠️ 本模式的已知污染：delta={"recruit": 1, "share": 1}（正式库需按 runbook §3 重建空库）
[landing-smoke] 检查 4/4 通过 → PASS
```

**污染处置（已执行并留痕）**：验收后立即 `fresh-db` —— 把受污染的库改名留档为
`marketing/out/landing.smoke-archive-20260924T150212Z.sqlite3`（**证据**，不删），并用**空库**重启。
这是「缺陷不隐藏、污染有据可查」的处理：正式读数从 0 起算。

### 3.3 交接态只读复核（`--mode readonly`，不写事件）

```
$ bash marketing/scripts/landing_deploy.sh smoke-readonly
[landing-smoke] mode=readonly base=http://127.0.0.1:8088
[PASS] GET /api/health — HTTP 200 · {"ok": true, "phase": "pre_t0", …}
[PASS] GET /api/stats（前读数） — recruit/share page_view = {"recruit_page_view": 0, "share_page_view": 0}
[PASS] HEAD / → 200 + Set-Cookie pd_uid — HTTP 200
[PASS] HEAD /s/<video_id> → 200 — HTTP 200
      ⚠️ 局限：do_HEAD 对未知路径也返回 200，故 HEAD 只能证明「实例在服务」，不能证明路由存在；路由存在性由 spawn 模式证明。
[PASS] 只读检查未写入事件（前后计数一致） — before={"recruit_page_view": 0, "share_page_view": 0} after={"recruit_page_view": 0, "share_page_view": 0}
[landing-smoke] 检查 5/5 通过 → PASS
```

局域网可达性（非回环地址，证明绑在 `0.0.0.0`）：

```
$ curl -sS -m 5 -o /dev/null -w "GET http://192.168.31.35:8088/api/health -> %{http_code}\n" \
    http://192.168.31.35:8088/api/health
GET http://192.168.31.35:8088/api/health -> 200
```

### 3.4 装置与基线未被本单改动（快照内复跑，避免复核器就地重写）

在 `tar` 快照（`--exclude=.git --exclude=__pycache__`）内复跑，**不在共享工作树上运行会就地重写报告的生成器**：

```
$ python3 marketing/scripts/compliance_lint.py
[compliance-lint] hard_ban=18 t0_gated=6 扫描目标=9
[compliance-lint] 阻断级违规：0，告警级：0                       # exit=0
$ python3 -m unittest discover -s marketing/tests -t .
Ran 42 tests in 20.306s … OK                                     # exit=0
```

> 读数限定：以上是**装置行为**，不是增长效果证据。业务判据仍**全部「不可计算」**（需真实访客 +
> PRO-7 的 T0 埋点）；300–500 访客的 MDE 为 10–14pp，**不具备 3pp 判定力**。

---

## 4. T0 证据留痕与门禁纪律

### 4.1 纪律（硬门，不得绕过）

1. **不得**以 `--phase t0` 启动（会被 T0 证据门禁拦住，`exit 3`）。
2. T0 当日**必须**提交 `--t0-evidence <真实证据文件>`（模板 `marketing/data/t0_evidence.template.json`），并把
   证据文件与启动记录一并留档。
3. **门禁能力边界（必须随交付一起说清）**：门禁只校验证据**信封**（`pro7_delivered` / `preconditions_all_green`
   为布尔 `true`、`preconditions` ≥ 8 条、`evidence_date` 非空），**不校验八项证据内容的真伪** ——
   真实性由**证据留档 + 人工复核**负责（PRO-14 R-6 / PRO-26）。
4. T0 由 **PRO-7 交付触发**（当前 PRO-7 = `blocked`）；本单**不**充当 T0 的启动器。

### 4.2 留痕位置（约定）

| 项 | 约定位置 |
|---|---|
| 真实 T0 证据文件 | `marketing/evidence/t0-evidence-<YYYY-MM-DD>.json`（由 T0 当日的执行人创建；门禁参数指向它） |
| 启动记录 | `marketing/evidence/t0-startup-<YYYY-MM-DD>.log`（`landing_deploy.sh start` 的启动输出 + `--phase t0` 的启动行） |
| 证据文件**不得**复用模板本身，也**不得**用任何演练件 | 见 §4.4 ⑨ |

### 4.3 演练脚本

`marketing/scripts/t0_evidence_drill.py` —— 用模板走一遍 `exit 3` 反证 + 信封边界取证。演练件全部写在临时目录，
**不落入仓库**，且演练只用临时数据库（不动正式分流统计库）。

### 4.4 演练回执（本机实际输出，逐字）

```
$ python3 marketing/scripts/t0_evidence_drill.py
[PASS] ① 无 --t0-evidence — exit=3（期望 3）
       |   - 未提供 --t0-evidence（T0 证据文件）
[PASS] ② 证据文件不存在 — exit=3（期望 3）
       |   - T0 证据文件不存在：…/nope.json
[PASS] ③ 直接拿模板当证据（pro7_delivered/preconditions_all_green=false） — exit=3（期望 3）
       |   - 证据字段 pro7_delivered 必须为 true（当前：False）
[PASS] ④ 信封缺 evidence_date — exit=3（期望 3）
       |   - 证据字段 evidence_date 缺失（须写明证据采集日）
[PASS] ⑤ preconditions 仅 7 条（< 8） — exit=3（期望 3）
       |   - 证据字段 preconditions 必须列出 §0.3 的八项前置（当前：7 项）
[PASS] ⑥ pro7_delivered="true"（字符串，非布尔） — exit=3（期望 3）
       |   - 证据字段 pro7_delivered 必须为 true（当前：'true'）
[PASS] ⑦ 信封完整（8 条 + 双开关 true + evidence_date）→ 门禁放行 — 门禁放行并开始监听
       | [compliance] phase=t0 T0 前置证据校验通过：…/envelope-ok.json
       | [landing] phase=t0 db=…/landing_drill.sqlite3 监听 http://127.0.0.1:0/

[边界取证] t0_evidence_gate() 返回值（逐条原因）
  · 无证据        → ["未提供 --t0-evidence（T0 证据文件）"]
  · 模板原件      → ["证据字段 pro7_delivered 必须为 true（当前：False）", "证据字段 preconditions_all_green 必须为 true（当前：False）", "证据字段 evidence_date 缺失（须写明证据采集日）"]
  · 信封完整演练件 → []（空列表 = 放行）
  · 结论：信封完整的**演练件**（内容全为演练占位）被判为放行 → 门禁确实只验信封、不验内容真伪。

[PASS] ⑧ 边界取证：门禁只验信封（演练占位内容亦放行）
[PASS] ⑨ 演练时仓库内无多余 T0 证据文件（仅模板）— 发现 0 个多余文件
[PASS] ⑩ 正式分流统计库未被触碰 — mtime before=1790184798.0568976 after=1790184798.0568976

[t0-drill] 用例 10/10 符合预期 → PASS
```

> **⑦ 的解读（不得简化）**：该用例证明的是门禁**放行**路径存在，**不是**「T0 已到」。演练件内容全为演练占位
> （`evidence_date=1970-01-01`、八条 `status=green` 但无真实链接）⇒ 这正是「门禁只验信封」的**证据**，
> 也说明**不能用门禁替代人工复核**。T0 是否已到，仍以 PRO-7 交付 + §0.3 八项前置**真实**全绿为准。

---

## 5. 承诺卡发放与 7 天兑现回收

### 5.1 发卡硬前置（不成立则**不得发卡**）

| 前置 | 说明 | 当前 |
|---|---|---|
| T0 已到 | PRO-7 交付 + §0.3 八项前置全绿（真实证据留档，见 §4.2） | ❌ PRO-7 = `blocked` |
| 承诺卡的兑现位可用 | 见 §5.2 —— 3 个数字需 `exposure` 埋点与 `/api/videos/{id}/exposure`；2 条非数字承诺需作品页回读位与规则文本公开 | ❌ 均未实现（`docs/08` §6.1 登记） |
| 卡片本体合规 | 发出前跑一次 `python3 marketing/scripts/compliance_lint.py`（本文件按 `t0` 相位扫描，只禁 `hard_ban`） | ✅ 当前 0/0（但**不得**据此提前发卡：前置 1/2 未成立） |
| `pre_t0` 锁定 | **T0 前不得发放**（T0 前不得出现任何量化承诺与结果承诺，含无数字） | ✅ 维持 |

### 5.2 兑现取数路径与责任人（逐条钉死）

卡片 5 条承诺 = 3 个数字（`docs/05` §3.5 白名单，只允许这 3 个）+ 2 条非数字承诺。

| # | 承诺 | 取数路径（必须真实） | 责任人 | 当前可用性 |
|---|---|---|---|---|
| 1 | 首发 24h 曝光 **P10 ≥ 50** | `exposure` 埋点 → `GET /api/videos/{id}/exposure` 的 `creator_exposure_p10`；同批创作者 24h 曝光分布取 P10 | 实现 = PRO-7；读数 = Marketing Strategist | ❌ 接口未实现 |
| 2 | 同批创作者曝光 **Gini ≤ 0.6** | 同上取同批 24h 曝光量，算基尼系数 | 实现 = PRO-7；计算与读数 = Marketing Strategist | ❌ 同上 |
| 3 | 单 feed 内同一创作者 **≤ 2 条**、7 天内不重复推荐同一条 | feed 组成日志（§0.3 #6）+ 推荐侧去重记录 | 实现 = PRO-7；读数 = Marketing Strategist | ❌ 未实现 |
| 4 | 推荐理由**可见**（非数字） | 作品页「推荐理由回读位」+ 分享页「推荐理由」渲染位 | 实现 = PRO-7；文案 = Marketing Strategist | ❌ 未实现（`docs/08` §6.1） |
| 5 | 分成规则**先公开后结算**（非数字） | 规则文本公开（不结算、不谈收入） | 文本 = Marketing Strategist；发布 = Director of GTM | ❌ 未公开 |

### 5.3 7 天回收流程与停投触发

| 步骤 | 动作 | 责任人 | 时点 |
|---|---|---|---|
| 1 | 发卡前置复核（§5.1 四项）并留档 | Director of GTM | 发卡前 |
| 2 | 逐创作者替换 `{专属招募链接}` 后发卡（与链接一一对应） | Marketing Strategist | T0 起 |
| 3 | 按 `creator_code` 回收 5 条承诺的真实数据 | Marketing Strategist（取数）| 发卡后 **D+7 内** |
| 4 | 逐条比对：**任一数字或非数字承诺无法以真实数据兑现 → 立即停止全部投放** | Director of GTM | 回收当日 |
| 5 | 未兑现处置：24 小时内向已发卡创作者逐条说明 + 复盘写入 PRO-8 §6.2 失败信号台账 | Director of GTM | 停投后 24h 内 |
| 6 | 回收结果按 `creator_code` 记入台账（供 A7 与 θ 归因） | Marketing Strategist | 每次回收后 |

> **伦理红线（PRO-4 §4.3 → PRO-8 §0.3）**：卡片一旦发出，7 天内**必须**以真实数据兑现；无法兑现即视为欺骗性设计，
> **立即停投**。因此「兑现位不可用」时**不得发卡** —— 这是发卡前置的第 2 项，不是告警。

---

## 6. 硬门清单（不得绕过，照抄 `docs/08` §15.6 与本单边界）

1. 不买量、不买创作者、不做站内关系链、不做变现承诺（PRO-5 SD5 / NG7 / NG10）。
2. 对外**只允许** `docs/05` §3.5 白名单的 3 个数字（P10 ≥ 50 / Gini ≤ 0.6 / 单 feed ≤ 2 条），**且只在 T0 后**；
   **T0 前不得出现任何量化承诺与结果承诺（含无数字）**。
3. **新增人工门禁**：首发机制类句子（「首发那条走了独立路由」「把首发曝光写成产品硬约束」）在其机制
   （R6 `newcomer`）**可见前不得用于对外投放**（`docs/08` §6.1 使用前置 / §13.1；**人工门禁，装置不覆盖**）。
4. 渠道 3（垂类社群）受 `docs/08` §2.2「③ 的启动前置」约束：T0 前只做深度运营、**不发量**。
5. 上线**不得**以 `--phase t0` 启动（`exit 3`）；T0 当日须提交 `--t0-evidence` 并留痕（§4）。
6. §6.1 全部**未实现兑现位**（`exposure` 埋点 / 来源参数归因落库 / 分享页理由渲染位 / 作品页两个回读位 / 首发独立路由 R6）
   **不得**当作已实现对外表述。
7. 零预算自然流量 + 方向性判定：**每次结论必须标注「低功效 / MDE 10–14pp」**，**不得**宣称 3pp 判定。
8. 本单**不改**物料文案、**不重跑**物料生成脚本、**不**充当 T0 启动器。

---

## 7. 未决与依赖（接手前请复核，勿以本手册描述为准）

| # | 事项 | 归属 | 状态 |
|---|---|---|---|
| 1 | 公网入口（主机 + 域名，或隧道授权） | board / ops | ✅ **已裁定 = 选项 ③「维持局域网可达、公网部署推迟到 T0」**（交互 `1175c3ae`，`2026-09-24T15:11:52Z`；见 §2.4 / §10） |
| 2 | MVP 可灰度日（T0） | PRO-7 | ❌ `blocked` |
| 3 | `exposure` 埋点 / `/api/videos/{id}/exposure` / feed 组成日志 / 来源参数归因落库 | PRO-7 | ❌ 未实现 |
| 4 | 作品页两个回读位 + 分享页理由渲染位 + 首发独立路由 R6 | PRO-7 | ❌ 未实现 |
| 5 | 创作者链接与二维码按真实基址重生成（`links.csv` 现为 `landing.local` / `app.local` 占位） | Marketing Strategist | ⏳ 待 **T0**（裁定 ③：T0 前不公网部署 ⇒ 暂无真实基址可换） |
| 6 | 商标与域名初筛（命名方向 A 的前置） | 超出本包授权 | ❌ 未做 |
| 7 | 本手册与 3 个新脚本**未登记进** `marketing/compliance/scan_manifest.json` 的 `device_files` | Marketing Strategist | ⏳ **已另派单**（注册欠账，`backlog`、未指派、目标 Owner = Marketing Strategist）；**须在既有两项观察项之后执行**（那两单验收以 `扫描目标=9` 为准，本项会改动该计数） |

---

## 8. 本轮的文件与复跑命令

| 路径 | 作用 |
|---|---|
| `docs/09-launch-integration-runbook.md` | 本手册（上线整合执行口径） |
| `marketing/scripts/landing_smoke.py` | 落地页冒烟装置（`spawn` / `live` / `readonly` 三模式，纯标准库） |
| `marketing/scripts/t0_evidence_drill.py` | T0 证据门禁演练装置（`exit 3` 反证 + 信封边界取证） |
| `marketing/scripts/landing_deploy.sh` | 部署助手（`start` / `stop` / `status` / `fresh-db` / `smoke-readonly` / `smoke-live`） |
| `marketing/evidence/README.md` | T0 证据留痕位置约定（§4.2） |
| `.gitignore` | 补 `marketing/out/*.log` / `*.pid`（运行时产物不入版本控制） |

```bash
# 复跑（快照内即可，不改动共享工作树）
python3 marketing/scripts/t0_evidence_drill.py          # 期望：用例 10/10 符合预期 → PASS
python3 marketing/scripts/landing_smoke.py --mode spawn # 期望：检查 14/14 通过 → PASS
bash   marketing/scripts/landing_deploy.sh smoke-readonly   # 期望：检查 5/5 通过 → PASS
```

---

## 9. 诚实限定（不得省略）

1. 本手册是**装置与执行口径**，不是实验结果；所有业务判据仍**不可计算**（§3.4）。
2. 落地页**尚未公网可达**；`可访问 URL` 目前只到**局域网**（§2.4）—— 且**公网部署已由 board 裁定推迟到 T0**（裁定 ③，§10）。本单**不声称**对外投放已开始。
3. 承诺卡**未发放**，且在其兑现位可用前**不得发放**（§5.1）—— 「7 天兑现回收」目前**不可执行**，只有流程与责任人已就绪。
4. 门禁只验证据信封、不验真伪（§4.1/§4.4 ⑦）。
5. 部署为无 supervisor 的宿主进程（§2.5）；宿主重启即失效。
6. 本手册与 3 个新脚本未纳入合规扫描清单（§7 #7，**已另派单**）；正文不含任何对外文案。

---

## 10. board 裁定落地记录（本轮新增）

**裁定来源**：本单 issue 交互 `1175c3ae-007d-4cb2-92e8-c8c79577f366`（`ask_user_questions`；`continuationPolicy = wake_assignee`；`addresseeUserId = local-board`）。

**裁定结果**：`status = answered`；`result.answers[0] = {questionId: "public_ingress", optionIds: ["local_only"]}`；答复时点 `2026-09-24T15:11:52Z`（`resolvedByUserId = local-board`）。

**裁定含义（选项 ③ 的原文口径）**：维持局域网可达。结果：**对外部署停止，直到 MVP 可灰度日（T0）**；不会到达任何**真实流量**；装置**保持就绪**。

**落点（本手册内已逐处同步）**

| 落点 | 改动 |
|---|---|
| §1 交付物表 #1 | 「公网可达未完成」→「**完成到本单可完成的边界**」+ 裁定 ③ 指针 |
| §1 交付物表 #2 | 流量未启动的原因补「裁定 ③ 明确 T0 前不开公网入口」 |
| §2.4 | 标题由「未决项（已提 board 裁定）」→「**已裁定项**（= 选项 ③）」；补裁定 id / 时点 / 直接后果 |
| §2.5 #3 | 「公网入口未定」→「已裁定为 T0 前不开」 |
| §7 #1 | 状态 `⏳ 已提交互` → `✅ 已裁定 = ③` |
| §7 #5 | 「待 #1」→「待 **T0**（裁定 ③ ⇒ 暂无真实基址可换）」 |
| §7 #7 | 「登记留给下一轮」→「**已另派单**，须在既有两项观察项之后执行」 |

**裁定 ③ 不改变的三件事**（不得误读为放宽）：① `pre_t0` 相位锁定**维持**；② T0 前**不得**出现任何量化承诺与结果承诺（含无数字）；③ 兑现位缺口清单（`docs/08` §6.1）与首发机制类句子的人工门禁**维持**。

**本裁定不解除的前置**：`T0` —— 由 PRO-7 交付 + `docs/08` §0.3 八项前置**真实**全绿触发。

---

*文档结束 · 上线整合（PRO-24）· 唯一现行版本，就地修订、不留历史版本*
