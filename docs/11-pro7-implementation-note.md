# PRO-7 实现说明与交付证据（收口与硬化）

> 本文件是 PRO-7 的**交付回执（implementation note）**，随代码入库，属于交付物的一部分。
> 原始回执本应贴在 PRO-7 issue 评论中；本轮通过 Paperclip API 写入时被运行归属校验拒绝
> （详见文末「附：交付回执投递失败记录」），故改以本文件 + Git 提交作为持久证据。

| 项 | 值 |
|---|---|
| 议题 | PRO-7 `[P4-实现] MVP 实现：可运行的视频上传 + 推荐流原型` |
| 目标仓库 | `genify/short-video-platform` |
| 分支 | `PRO-1-pro-1` → 已快进合入 `main` |
| 交付提交 | `b411c0e` `48c746a` `778da8b` `330b36f` `d44d782` `66285d8` `506cecb`（`main` = `506cecb`，与远端一致） |
| 回归测试 | **118 项全绿**（`Ran 118 tests in 45.498s / OK`；改造前 86 项） |
| 冒烟测试 | **21/21 通过**（`python3 scripts/smoke.py`） |

## 一、交付物（issue 描述口径的四项 + 两项必须修缺陷）

| # | 交付物 | 落点 |
|---|---|---|
| ① | 推荐权重离线校准（NDCG@K 网格搜索） | `scripts/evaluate.py`、`docs/10-recommendation-weight-calibration.md`、`tests/test_evaluate.py` |
| ② | 鉴权与限流（上传 / 互动 / 推荐） | `server/auth.py`、`server/ratelimit.py`、`server/app.py`、`server/db.py`、`server/config.py`、`tests/test_auth.py` |
| ③ | `PRO-1-pro-1` 合入 `main` 并推送 | `git merge --ff-only` + `git push origin main` |
| ④ | 端到端冒烟 + README | `scripts/smoke.py`、`README.md`、`Makefile`、`docs/api.md` |
| 附 | PRD 点名的两项"必须先修"缺陷：G1 探索位死代码、ffprobe fail-open | `server/recommend.py`、`server/media.py`、`tests/test_exploration.py`、`tests/test_media.py` |

## 二、范围口径声明（本单存在两份不一致的范围声明）

| 来源 | 范围 |
|---|---|
| **issue 描述**（board 口径更正后） | 四项收口交付物（上表 ①~④），验收标准只覆盖这四项 |
| PRO-6 移交评论（2026-09-23 16:15） | 实施 PRD v2.0 的 **M0~M6 全量里程碑**（22 端点 / 69 条 AC / 目标 ≥140 项测试） |

**处置**：按"issue 描述即契约"执行四项，并把 PRO-6 评论中点名"必须先修"的两项缺陷一并修掉
（它们既是 PRD 的 P0/P1 缺陷，也直接影响本单验收口径：推荐流可解释性、上传校验可信）。
**其余里程碑（M1/M3/M4/M5/M6）不在本单范围**，已登记为子单 **PRO-31**（`backlog`，不阻断 PRO-24），
并写明硬约束（M1 不可跳过；M5 必须先于 M4 的 `dislike`）。未按 PRO-6 评论扩围，是为避免重复开发与重复花费。

## 三、实测证据（命令 + 原始输出）

### 3.1 全量回归（在 `main` 合并后实测）

```
$ git rev-parse --abbrev-ref HEAD && git log --oneline -1
main
506cecb docs: README 与 API 参考对齐现状（鉴权、fail-closed、诚实的缺口清单）

$ python3 -m unittest discover -s tests -t .
Ran 118 tests in 45.498s

OK
```

86 → 118 项，**无一项被削弱**：既有用例的断言全部保留；3 处契约变更（身份校验先于存在性校验、
feed 越权改判 403、纯 JSON 体上传需先过鉴权）就地改写并在用例 docstring 写明原因。

### 3.2 端到端冒烟（验收口径）

```
$ python3 scripts/smoke.py
[1] 健康检查与鉴权契约
  [PASS] GET /api/health 免鉴权可用  —— HTTP 200
  [PASS] 无凭据上传被 401 拒绝（unauthenticated）  —— HTTP 401 code=unauthenticated
[2] 上传链路（真实 mp4 / ffprobe 元数据真值）
  [PASS] 演示视频运行时合成成功（仓库无二进制素材）  —— ffmpeg 合成 59315 字节
  [PASS] 用他人 creator_id 上传被 403 拒绝（identity_mismatch）  —— HTTP 403 code=identity_mismatch
  [PASS] 上传受支持格式视频返回 2xx  —— HTTP 201 id=52a5c4a2
  [PASS] 元数据来自 ffprobe 真值（时长/分辨率/去重哈希）  —— duration_ms=4000 360x640
  [PASS] 上传返回的地址可访问（返回完整字节）  —— GET /api/videos/52a5c4a2.../file → HTTP 200，59315 字节
  [PASS] 媒体流支持 Range（206 + 100 字节）  —— HTTP 206，100 字节
[3] 互动与推荐流（核心功能 2）
  [PASS] 观众点赞成功且计数可读  —— HTTP 201 stats={'views': 1, 'completes': 0, 'likes': 1, 'shares': 0}
  [PASS] 推荐流需凭据（401）  —— HTTP 401
  [PASS] 重复上传返回 409 且顶层回传 video_id（幂等契约）  —— HTTP 409 video_id=52a5c4a2
  [PASS] 新上传视频出现在推荐流中  —— HTTP 200，feed 条数=2，命中位置=1
  [PASS] 该条排序理由可解释（feature 归因 + 召回路径）  —— reason=大众热度主导（召回路径：冷启动兜底/热门新鲜）
  [PASS] feed 响应包含权重版本与探索位字段  —— weight_version={'aff': 0.45, ...} exploration_injected=False
  [PASS] 推荐流条数 > 1（说明命中的是排序结果而非唯一内容）  —— feed 条数=2

[smoke] 结果：21/21 项通过，用时 0.9s
[smoke] OK —— 上传链路与推荐流链路端到端可用
```

### 3.3 权重校准（交付物 ①）

```
$ python3 scripts/evaluate.py --out docs/10-recommendation-weight-calibration.md
[eval] 用户数=12 K=10 候选池上限=60
[eval] 现状权重 NDCG@10 = 0.7661  0.45 / 0.20 / 0.15 / 0.10 / 0.10
[search] 网格 1001 个点 → 最优 NDCG@10 = 0.8542  0.40 / 0.00 / 0.40 / 0.10 / 0.10
[search] 细化后（共评估 1033 个权重向量）NDCG@10 = 0.8735  0.40 / 0.00 / 0.35 / 0.15 / 0.10
```

* 校准前后：**0.7661 → 0.8735（+0.1074 / +14.0%）**；评测用户 12、评估向量 1033。
* **评测器自检通过**：默认权重下评测器排序与生产 `engine.feed` 逐项一致，否则报错、结论作废。
* **不直接改生产默认值**：合成集只能验证方法（搜索最优 ≠ 生成真值；`pop` 被压到 0 = 边界解 =
  过拟合信号）。启用路径为 `SVP_RANK_WEIGHTS` 环境变量作 A/B 实验臂；生产权重须由真实日志
  （`--from-db`）+ 线上 A/B 定。

### 3.4 交付收口（交付物 ③）

```
$ git merge --ff-only PRO-1-pro-1        # main: 082f29c → 506cecb（快进，无冲突）
$ git push origin PRO-1-pro-1
   ec475da..506cecb  PRO-1-pro-1 -> PRO-1-pro-1
$ git push origin main
   082f29c..506cecb  main -> main
$ git ls-remote origin
506cecb5ff93619cfa9d9b8fd45371482ce9a2a2  refs/heads/PRO-1-pro-1
506cecb5ff93619cfa9d9b8fd45371482ce9a2a2  refs/heads/main
```

### 3.5 分项测试（补充证据）

```
$ python3 -m unittest tests.test_auth        → Ran 19 tests ... OK   （AC-S-* / AC-A-*，生产限流档）
$ python3 -m unittest tests.test_exploration → Ran  5 tests ... OK   （AC-F-08 / 08b / 08c）
$ python3 -m unittest tests.test_evaluate    → Ran  6 tests ... OK   （harness == feed 一致性）
```

## 四、实现要点（鉴权与限流，FR-3 / FR-4）

* 令牌：32 字节 URL-safe base64，**只存 `sha256`**；30 天有效、可撤销、`auth_level=dev` 显式标注；
  明文仅签发响应返回一次。
* 身份一致性：`user_id` / `creator_id` / `follower_id` 必须等于凭据身份，否则 `403 identity_mismatch`
  —— HTTP 层 + 业务层**双重**校验（防绕过 HTTP 直接调业务层造成越权）。
* 管理端点：独立 `SVP_ADMIN_TOKEN`（环境变量注入）；**未配置则一律 403**（fail-closed）。
* 限流：令牌桶（用户级 + IP 级 + 全局兜底）；429 带 `Retry-After` + `X-RateLimit-Limit/Remaining/Reset`；
  `/api/health` 豁免；**上传/互动的鉴权与限流均在读取请求体之前**（用"只发请求头不带体"的 socket
  用例钉住，否则保护对象已被消耗）。
* CORS：`SVP_CORS_ORIGINS` 白名单驱动，未命中不下发 CORS 头；`Allow-Headers` 含 `Authorization`。
* 秘密卫生：错误与日志统一脱敏；且**不误伤纯 hex** 的 `video_id`/`sha256`（否则会污染用户可见错误消息）。

## 五、实现中发现并修掉的 3 个真实缺陷（非计划内，均为实证）

1. **读体前被拒的请求会阻塞工作线程**：错误分支去"排空"永远不会到来的请求体 → 只发请求头即可挂死
   连接（同时是慢速攻击面，属 FR-4.2.c 同类）。现改为读体前被拒直接关连接（`Connection: close`），
   排空读取带 3s socket 超时。
2. **探索位即使接线也永远选不出候选**：多路召回的深度截断**按定义**淘汰低曝光长尾（`fresh` 路由要求
   HN 分 > 0、`fallback` 按热度取前 N 条），而低曝光长尾正是探索位的目标物 —— 实测 40 条库含 10 条
   零曝光长尾，**300 个 seed 零注入**。现把库内低曝光候选显式补入候选集，并用同一套特征/打分函数评分
   （排序口径与主链路一致，仍完全可解释）。
3. **409 `duplicate_video` 未回传顶层 `video_id`**（PRD §8.5 冻结契约要求的唯一重试幂等机制）。
   现已顶层回传，同时保留原 `error.message`。

## 六、如何运行

```bash
make test            # 全量回归（118 项）
make smoke           # 端到端冒烟（21 项判定，默认自起临时实例）
make evaluate        # 权重离线校准 → docs/10-*.md
make test-auth / test-exploration / test-evaluate
make run             # 启动服务（README 内含带 Authorization 的三分钟链路示例）
```

前置条件：Python 3.10+、ffmpeg/ffprobe（**缺失时上传被拒**：`503 probe_unavailable`）。零第三方依赖。

## 七、未实现 / 未测试（诚实清单）

**未实现**

* **M1 曝光埋点与度量基础设施**：无 `FeedImpression`、无 `exposure` 事件、无 `/api/impressions`、
  无 `/api/admin/metrics` → **S1（首发 24h 曝光 P10 ≥ 50）与 S2（Gini ≤ 0.6）在数学上不可计算**；
  `exploration_slot_rate` / `feed_p99_ms` 亦无度量。探索位"低曝光"判据现用 `views` **代理**，
  M1 落地后须切换为真实曝光分位（改动点：`server/recommend.py::exploration_candidates`）。
* **M5 互动幂等与负反馈**：重复 `like` 仍会重复计数（无唯一索引）；无 `unlike` / `dislike` / `report`；
  无 `user_video_suppression` 永久排除表。**限流已上，幂等尚未** —— 反刷量只做了一半。
* **M4 推荐流增强**：无游标分页、无会话级曝光去重、无冷启动首屏槽位配额（3+3+2+2）、无新视频保底曝光。
* **M3 上传增强**：无审核回调 `POST /api/internal/moderation/callback`。
* **M6 权限矩阵**：视频无 `private`/`hidden` 语义（当前全为 `published`），故媒体流未做可见性 ACL
  （FR-4.1.g）；`GET /api/videos` 无分页（全量返回）。
* 身份真实性（`auth_level=dev`，仅凭 handle 换 token）；限流单机（多实例需迁 Redis）；
  无并发连接上限（`MAX_CONCURRENT_CONNS`）与请求读超时；`user_tag_profile` 的 N+1 查询（NF-2）、
  `item_similarity` 未批量查询（NF-3）。

**未测试（测试盲区）**

* `feed` P99 性能门禁（NF-1）与压测未做。
* 限流"窗口过后恢复"的时间行为未测（只测了"第 6 次被拒"）。
* CORS 只测响应头是否下发，未在真实浏览器跨域场景验证。
* 权重校准的 `--from-db` 真实日志回放路径已实现，但**未在真实流量上跑过**。
* 未覆盖：SQLite 磁盘写满、媒体文件被外部删除、`ffprobe` 30s 超时边界。

## 八、验收标准逐条核对

| 验收标准 | 结果 | 证据 |
|---|---|---|
| 上传受支持格式视频 → 2xx 与可访问地址 | ✅ | 3.2：HTTP 201 + `/file` HTTP 200（59315 字节）+ Range 206 |
| 新上传视频可在推荐流中出现（排序理由可解释） | ✅ | 3.2：命中位置 1/2，`reason=大众热度主导（召回路径：…）` |
| `scripts/evaluate.py` 可复现运行并给出 NDCG@K 校准前后对比 | ✅ | 3.3：0.7661 → 0.8735；`docs/10-*` |
| `main` 分支包含全部交付物且回归通过 | ✅ | 3.1 / 3.4：`main @ 506cecb`，118 项 OK，远端已同步 |
| 冒烟测试实跑通过，输出贴回 issue 评论 | ⚠️ 部分 | 实跑输出见 3.2；**评论投递被平台校验拒绝**（见下），已落盘为本文件 |

## 九、后续

* **PRO-31**（PRO-7 子单，`backlog`）：承接 PRD v2.0 剩余里程碑 M1/M3/M4/M5/M6，含开工顺序与硬约束。
  是否开工由 board / VP of Product Execution 决定。
* **GTM 侧口径提醒**：本轮新增 `docs/10-recommendation-weight-calibration.md` 与 `docs/11-*.md`。
  若 `marketing/compliance/scan_manifest.json` 的登记纪律要求覆盖新增文档/装置，请由 GTM Owner 决定
  是否登记（属 GTM 侧口径，本单未代行判断）。

---

## 附：交付回执投递失败记录（已按"停止重试"纪律退出）

* 目标：`PATCH /api/issues/7b29bcf2-...`（`{status: "done", comment: "<回执全文>"}`）
  以及 `POST /api/issues/7b29bcf2-.../comments`。
* 结果：HTTP 错误 `Cross-issue writes need a run to attribute them to (Heartbeat run context).`
  —— "This request arrived without a valid run"（即便已带 `X-Paperclip-Run-Id: $PAPERCLIP_RUN_ID`）。
* 已尝试：① 先 `POST /api/issues/<id>/checkout`（**成功**，`status` → `in_progress`，
  `checkoutRunId`/`executionRunId` 已指向本轮 run）；② 再投递评论（仍被同一错误拒绝）。
* 按运行纪律（同一控制面写入连续失败 2 次即停止重试）**未继续重试**。回执全文（含证据与口径声明）
  即本文件，已随提交入库并推送；PRO-31 子单已创建成功（写入该端点未被拒绝）。
* 需要人工/board 动作：由有 run 归属的通道（board 会话或为 PRO-7 派发的任务运行）把本条回执
  贴回 PRO-7 评论，并把状态置 `done`（验收标准已逐条满足，见第八节）。
