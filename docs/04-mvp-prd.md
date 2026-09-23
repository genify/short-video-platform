# 短视频平台 MVP · 产品需求文档（PRD）

> **交付单**：PRO-6「[P3-执行] PRD：MVP『视频上传』+『推荐流』」
> **交付方**：VP of Product Execution（Product Compass Consulting）
> **目标仓库**：`genify/short-video-platform`（workspace `92af0854-13e8-43ae-a911-ee3933fccdfb`）
> **文档路径**：`docs/04-mvp-prd.md`（分支 `PRO-1-pro-1`）
> **版本**：**v2.0（取代 v1.0）**
> **上游**：`docs/07-product-strategy.md`（PRO-5）、`docs/01-competitive-analysis.md`（PRO-3）、`docs/06-user-needs-map-and-assumption-plan.md`（PRO-4）、`docs/03-recommendation-design.md`、`docs/00-intake-and-decomposition.md`
> **下游**：PRO-7（实现）、PRO-8（GTM）

---

## 0. 文档控制（下游必读）

### 0.1 版本与取代关系（零冗余声明）

本文件 **v2.0 完整取代 v1.0**，不产生第二份 PRD：

| 项 | v1.0（历史） | v2.0（本文件） |
|---|---|---|
| 定位 | 描述**已实现**的 MVP（事后文档） | 定义**交付契约**：已实现基线 + 待补项 + 工程可无歧义实现的规格 |
| 缺失章节 | 无数据模型、无 API 契约、无 Given/When/Then、无 Gap 表、无任务拆分 | 全部补齐（§七~§十） |
| 与策略的关系 | 早于 PRO-5，未承接策略移交 | 承接 PRO-5 §6.1–§6.4 全部移交物与 §7.2/§7.3 裁定 |
| 结论 | v1.0 的**全部结论被吸收**为本文 §三「现状」列与 §十 Gap 表的「已实现」判定 | 唯一有效版本 |

**执行纪律（继承用户方零冗余要求）**：任何后续修订**就地覆盖本文件**，禁止另建 `*-v2/-v3/-final` 副本。

### 0.2 上游引用锚点映射（保证 `[PRD-§x]` 引用不断链）

上游文档（尤其 PRO-5）大量使用 `[PRD-§1.1] [PRD-§1.3] [PRD-§3.1] [PRD-§3.2] [PRD-§3.3] [PRD-§3.4] [PRD-§5] [PRD-§六]` 引用本文件。v2.0 **刻意保留这些锚点的语义**，映射如下：

| 上游引用锚点 | v2.0 实际位置 | 语义是否保持 |
|---|---|---|
| `[PRD-§1.1]` 定位 | §1.1 定位与愿景承接 | ✅ 保持 |
| `[PRD-§1.3]` Non-Goals | §1.4 明确不做（Non-Goals） | ✅ 保持（并按 PRO-5 §7.2-1 补入 3 项） |
| `[PRD-§3.1]` 上传 | §3.1 FR-1 视频上传 | ✅ 保持 |
| `[PRD-§3.2]` 推荐流 | §3.2 FR-2 推荐流主链路 | ✅ 保持 |
| `[PRD-§3.3]` 冷启动 | §3.3 FR-2 冷启动（新用户/新视频/新品类） | ✅ 保持 |
| `[PRD-§3.4]` 互动埋点 | §3.4 FR-3 最小支撑（含 3.4.4 埋点事件） | ✅ 语义扩展但仍含埋点 |
| `[PRD-§5]` 验收标准 | §五 验收标准（Given/When/Then） | ✅ 保持并强化为可执行 GWT |
| `[PRD-§六]` 已知限制 | §六 已知限制与后续迭代 | ✅ 保持 |

### 0.3 证据与口径纪律（继承上游，硬约束）

1. **D 级信源禁止引用**：PRO-3 标注 D 级（无公开来源）的竞品数字（冷启动流量池层级、审核时长、打赏分成、上传时长上限等）不得进入本 PRD 的判据与对外口径。
2. **E2 级数字仅作待核实线索**，不得作事实陈述。
3. **自设阈值一律标注**：本文所有阈值（200MB、180s、P10 ≥ 50、Gini ≤ 0.6、限流速率等）均为**团队设定值**，非行业基准，须在灰度后用真实分布校准。
4. **现状判定纪律**：§十 Gap 表中每一条「已实现」判定，均须能指向 `server/` 的具体文件与行号；不能指认者一律降级为「需改造」或「需新增」。**不得把已有能力当作新需求。**

### 0.4 本单交付物 → 本文章节映射（用于验收核对）

本单描述要求 8 项交付物，逐项落位如下（**无遗漏、无外挂副本**）：

| # | 本单要求的交付物 | 本文位置 | 备注 |
|---|---|---|---|
| 1 | 背景与目标（MVP 目标、北极星、成功判据） | §一（1.1–1.3） | 北极星口径承接 PRO-5 §4.4.1 并冻结 |
| 2 | 范围（In / Out of scope） | §二 | Out of scope 逐项附复查触发条件 |
| 3 | 功能需求 FR-1~FR-4 | §三（3.1–3.5） | 每条 FR 含「现状（代码位置）→ 规格 → 错误码」 |
| 4 | 数据模型（User / Video / Interaction / FeedImpression） | **§七** | 含 DDL、字段字典、索引与迁移脚本 |
| 5 | API 契约（端点 / 请求响应示例 / 错误码） | **§八** | 22 端点总览 + 13 个关键端点的完整报文示例 |
| 6 | 验收标准（每条 FR 的 Given/When/Then） | **§五** | **69 条**，按 FR 分组，编号可在 §十 反查 |
| 7 | 任务拆分（用户故事 + 实现顺序 + 里程碑） | **§九** | M0–M6 六个里程碑，含退出判据 |
| 8 | Gap 表（现有实现 vs 本 PRD，覆盖 `server/` 5 模块） | **§十** | 逐模块逐条判定「已实现 / 需改造 / 需新增」 |

补充章节（超出本单要求，但为闭环必需）：
- **§四 非功能需求**：性能/并发/可观测性/容量，含 `docs/03 §2.3` 延迟预算的落地口径
- **§六 已知限制与后续迭代** `[PRD-§六 语义保持]`
- **§十一 口径冻结与决策记录**：含 PRO-5 §7.2-5 点名的**召回配额口径终裁**、曝光/播放口径冻结、待上游裁定项

### 0.5 基线验证记录（本次交付实测）

| 项 | 命令 | 结果 |
|---|---|---|
| 回归测试 | `make test`（`python3 -m unittest discover -s tests -t .`） | **Ran 86 tests … OK**（26.1s） |
| 测试分布 | — | `test_recommend.py` 31 + `test_media.py` 27 + `test_api.py` 28 = 86 |
| 媒体工具链 | `which ffmpeg ffprobe` | `/usr/bin/ffmpeg`、`/usr/bin/ffprobe` 均可用 |
| 代码规模 | `wc -l server/*.py` | `app.py` 425 · `db.py` 378 · `media.py` 434 · `recommend.py` 453 · `config.py` 81（**5 模块**） |
| 分支 | `git branch` | `PRO-1-pro-1`（本 PRD 落盘分支，**不切换、不重命名**） |

---

## 一、背景与目标

### 1.1 定位与愿景承接 `[PRD-§1.1 语义保持]`

**一句话定位**（不变，与 PRO-5 §1.1/§2.3 一致）：

> **面向垂类创作者的短视频平台：让新创作者的第一条视频就能拿到确定的曝光，并且知道自己为什么被看见。**

**压缩版对外口径**（PRO-5 §2.3 授权）：我们不承诺「爆」，我们承诺「不白干」——并且把这句话变成可核对的数字。

**战略切口**（PRO-5 SD1，本文直接继承，不再论证）：**A 垂直品类深耕 × B 创作者侧确定性供给**的交集；否决 C（内建关系链冷启动）与通用赛道。

**三条产品差异点**（PRO-5 §3.2），本 PRD 的工程承载：

| # | 差异点 | 本 PRD 承载章节 | 可核对数字 |
|---|---|---|---|
| D1 | 首发曝光确定性是**机制**不是承诺 | §3.2.5 新视频保底路由 · §3.3 冷启动 · §7.4 `FeedImpression` | 首发 24h 曝光 **P10 ≥ 50** |
| D2 | 分发公平**可度量可回滚** | §3.2.4 重排（MMR + 创作者打散） · §四 性能与护栏 | 曝光 **Gini ≤ 0.6**；单创作者单 feed **≤ 2 条** |
| D3 | 全链路**可解释** | §3.1.6 具名错误码 · §3.2.6 `reason`/`features` · §八 API 契约 | 推荐可归因 100%、无静默失败 |

### 1.2 MVP 目标（本 PRD 的交付定义）

MVP 的目标**不是**「推荐更准」，而是**把三条差异点变成可运行、可测量、可回滚的工程机制**。具体到本 PRD：

| # | 目标 | 判定方式 |
|---|---|---|
| G1 | 上传 → 推荐流链路**闭环可用**，零第三方依赖、开箱即跑 | `make test` 全绿；真实 mp4 三分钟走通（见 §五 AC-U-08） |
| G2 | 推荐流**在冷启动期即产生可感知个性化**，且行为稀疏不失效 | 冷启动用户首刷前 10 条兴趣标签命中率 **≥ 60%** |
| G3 | 首发曝光确定性成为**可计算的机制**（而非运营话术） | 首发 24h 曝光 **P10 ≥ 50** 且同批创作者 **Gini ≤ 0.6** |
| G4 | **测量基础设施完备**，使 G2/G3 可被真实计算 | `exposure` 埋点 + 鉴权 + 限流 + 首刷/退出埋点全部落地（PRO-5 §6.4） |
| G5 | 上传侧**失败可理解**、推荐侧**结果可归因** | 具名错误码覆盖率 100%；每条 feed 均带 `reason` |

> **本 PRD 最重要的诚实限定**：G2/G3 的成立前提是 PRO-4 的 Top 3 假设（A1/A2/A4）成立，而 A2/A4 为 **E1（无证据）**、A1 为 **E2**。因此本 PRD 交付的是**可验证的机制**，不是已被验证的结论。

### 1.3 北极星指标与成功判据

#### 1.3.1 北极星（NS）与计算口径（直接引用 PRO-5 §4.4.1，冻结）

> **NS = 创作者次周留存率（W2_CRR） × 人均有效观看时长（EVT）**，阶段 2 末目标 **≥ 10.0**

| 组成 | 分子 | 分母 | 频次 | 目标 |
|---|---|---|---|---|
| **W2_CRR** | 第 W 周内完成 ≥ 1 次「有效发布」、且在第 **W+1** 周内再完成 ≥ 1 次「有效发布」的创作者去重人数 | 第 W 周内完成 ≥ 1 次「有效发布」的创作者去重人数 | 周，**T+2 结算** | ≥ **0.40** |
| **EVT** | Σ 当日全部 `kind=view` 事件的 `watch_ms`（**不做时长过滤**） | 当日去重活跃用户数（有 ≥ 1 条 `view` 的 distinct `user_id`） | 日（7 日滚动中位数上报） | ≥ **25 分钟/人·日** |

**「有效发布」冻结定义**：`POST /api/videos` 返回 **201** 且该视频发布满 24h 时**累计曝光 ≥ 1**。

**使用纪律（强制，禁止误用）**：
1. 两因子量纲不同（周比率 × 日时长），NS **只用于同周环比与实验组间比较**，禁止跨周绝对值排名。
2. 任一因子为 0 则 NS 为 0——这是选乘积而非单指标的目的（单看 DAU 会掩盖空心化，单看创作数会掩盖「发了没人看」）。
3. NS **不是对外宣传口径**。
4. **`exposure` 未落地前，W2_CRR 与 A1 暂用代理口径**：以「发布后 24h 累计 `views` ≥ 1」代替「曝光 ≥ 1」，并逐处显式标注 `[代理口径]`；`exposure` 上线后统一切回，切换须记录口径版本（见 §十一 C2）。**当前实现下 `exposure` 不存在，此为阻塞项。**

#### 1.3.2 成功判据（本 PRD 的 DoD，逐条可测）

| # | 判据 | 阈值 | 口径来源 |
|---|---|---|---|
| S1 | 新创作者首发视频 24h 曝光 **P10** | **≥ 50** | PRO-4 A1 / PRO-5 §6.3-1 |
| S2 | 同批创作者曝光量 **Gini** | **≤ 0.6**（> 0.7 强制提升探索流量） | PRO-4 A1 / PRO-5 §4.4.2 |
| S3 | 冷启动用户（历史行为 < 3 条）首刷前 10 条兴趣标签命中率 | **≥ 60%** | PRO-4 A2 / PRO-5 §6.3-3 |
| S4 | 冷启动用户 20 秒内退出率 | **< 40%** | PRO-4 A2 / PRO-5 §6.3-3 |
| S5 | 新用户首次上传任务完成率 / 中位耗时 / 求助率 | **≥ 80%** / **≤ 90s** / **≤ 5%** | PRO-4 A4 / PRO-5 §6.3-2 |
| S6 | 消费侧：次日留存 D1 / 完播率 | **≥ 25%** / **≥ 45%** | PRO-5 §4.4.2 |
| S7 | 护栏：举报率 / 跳过率 | **< 0.5%** / **≤ 40%** | PRO-4 §5.2 |
| S8 | 护栏：单创作者单 feed 条数 / 7 天重复推荐率 | **≤ 2** / **= 0** | PRO-5 §4.4.2 |

**护栏强制写法（PRO-5 §6.3-4，原文冻结）**：「上述三项达标不得以恶化为代价：**举报率 < 0.5%**、**单创作者在单条 feed 内 ≤ 2 条**、**7 天内已看不重复推荐**、**人均观看时长不下降**。」

**北极星条款（PRO-5 §6.3-5，原文冻结）**：「北极星指标 NS = 创作者次周留存率 × 人均有效观看时长，计算口径见 §1.3.1；分子分母定义冻结后方可启动效果实验；口径变更须同步修订本条款。」

**G1 条款（PRO-5 §6.3-6，原文冻结）**：「观众侧 P0 负反馈出口（`dislike`/`report` 最小实现）为 MVP 必交付项，缺口状态须在 PRD 的覆盖核对表中显式登记（当前为未实现）。」→ 本文 §3.2.7 与 §十 已登记。

### 1.4 明确不做（Non-Goals）`[PRD-§1.3 语义保持]`

v1.0 已含「电商、打赏、支付」，但**未含**订阅/会员、内建关系链冷启动、LBS/同城。按 PRO-5 §7.2-1 与 §5.2 补入（NG3/NG6/NG7）：

| # | 不做 | 理由 | 复查触发条件 |
|---|---|---|---|
| NG1 | 通用全品类短视频 | 存量市场（渗透率 95.4% 为 E3，仅作量级参照）+ 头部集中，正面竞争不成立 | **永不复查** |
| NG2 | 直播、连麦、IM 私信 | 与「供给确定性」无关，分散资源 | A1/A2/A4 全部通过后 |
| NG3 | 电商、打赏、支付、**会员订阅** | 需支付/LBS 能力；且变现门槛未达成 | PRO-5 §4.2 各路径启动门槛达成 |
| NG4 | 视频编辑（剪辑/滤镜/特效/音乐库） | PRO-4 判读 3：MVP 不能靠创作体验赢 | 发布侧 P0 达标且上传失败率已量化 |
| NG5 | DNN 排序模型 / 实时特征工程 | 无行为数据阶段为负收益；先要可解释基线 | A8 证实多路召回 + 线性权重优于单路基线 ≥ 10% |
| NG6 | **LBS / 同城分发 / 到店核销** | 细分 C 的核心 JTBD 在 MVP 内不承接，避免「承诺做不到的功能」 | 支付与 LBS 能力立项后 |
| NG7 | **社交关系链冷启动（依赖平台内建关系链资产）** | 本产品无任何内建关系链资产，从零起盘不可复制 | **永不复查**（策略级否决） |
| NG8 | 移动端原生 App（先 Web + 移动 Web） | 验证供给与消费不需要原生端 | 阶段 2 消费侧指标达标后 |
| NG9 | 与头部平台比拼推荐精度 / 内容量 | 五家链路已同构，此战场不可赢 | **永不复查** |
| NG10 | 单纯的创作者现金补贴 | 已被证伪（买来的创作者无留存动力） | **永不复查** |
| NG11 | 分片上传 / 断点续传（`chunked` / `resumable`） | PRO-5 §6.2 列为 Out of scope：**必须先量化上传失败率**再决定是否需要 | 上传失败率 **> 5%**（口径见 §3.1.5） |

**NG7 的边界（继承 PRO-5 §7.3 校准，避免下游误读）**：否决的是「依赖平台**内建**关系链资产作为**主分发路径**」；**不否决**「借**站外**社交信号作补充召回」（站外分享回流的好友信号、好友互动过的内容），但该路召回**权重上限 ≤ 1 路且冷启动期内不得为第一权重**。

---

## 二、范围

### 2.1 In scope（本 PRD 交付范围）

优先级口径：**P0 = 上线阻塞（不做则对应判据不可测或不成立）**；**P1 = 本 MVP 内做且构成差异化**；**P2 = 可延后**。

| 模块 | 范围项 | 优先级 | 状态 | 来源 |
|---|---|---|---|---|
| 上传 | 单请求完成发布（≤3 步，`POST /api/videos` multipart） | P0 | 已实现 | `[PRD-§3.1][F4-A4]` |
| 上传 | 服务端 ffprobe 真值（时长 1–180s、高度 ≥240px）、200MB 上限、sha256 去重、具名错误信封 | P0 | 已实现（**ffprobe 缺失时 fail-open，须修**） | `[PRD-§3.1]` |
| 上传 | `#话题` 正则自动抽标签（≤8 个），无需填表 | P0 | 已实现 | `[PRD-§3.1]` |
| 上传 | **元数据：独立 `title` + 话题 + 可见性 `visibility`** | P0 | **需新增** | 本单描述 §3 FR-1 |
| 上传 | **审核钩子（moderation hook）+ 状态机** | P0 | **需新增** | 本单描述 §3 FR-1 |
| 上传 | 进度反馈（客户端）+ 失败可重试（**幂等语义**） | P0 | **需改造** | 本单描述 §3 FR-1 |
| 推荐流 | 多路召回（cf/follow/fresh/tag/fallback）+ 线性加权 5 特征 + MMR + 单创作者 ≤2 条 + 7 天已看过滤 + `seed` 可复现 | P0 | 已实现 | `[PRD-§3.2]` |
| 推荐流 | **ε-greedy 探索位（当前为死代码，见 §3.2.4-G1）** | P1 | **需改造** | `[PRD-§3.2][docs/03 §5.5]` |
| 推荐流 | **分页 / 无限滚动（cursor）** | P0 | **需新增** | 本单描述 §3 FR-2 |
| 推荐流 | **负反馈 `dislike` / `report`（仅记录事件 + 会话内即时抑制）** | **P0** | **需新增** | `[F4-§6 G1][PRD-§3.2]` |
| 推荐流 | 冷启动兜底（新用户 <3 条行为；新视频走 `tag`/`fresh`/`fallback`；新品类 MMR 全库采样） | P0 | 已实现（**新视频保底额度未实现**） | `[PRD-§3.3][F4-§2.1]` |
| 推荐流 | **新视频保底曝光路由（D1 的机制兑现）** | P0 | **需新增** | `[F4-A1][PRO-5 §6.1]` |
| 支撑 | 账号与最小会话（token） | P0 | **需新增** | 本单描述 §3 FR-3 |
| 支撑 | 内容详情（含作者、播放地址、本人互动状态） | P0 | **需改造**（现有详情缺播放地址与状态） | 本单描述 §3 FR-3 |
| 支撑 | 基础互动点赞（**幂等**）+ 取消点赞 | P0 | **需改造**（现有实现非幂等） | 本单描述 §3 FR-3 |
| 支撑 | 埋点事件（7 类现有 + **`exposure` 曝光** + 首刷标记/退出事件） | P0 | **需改造 + 需新增** | `[F4-§4.7][PRO-5 §6.4-2/6]` |
| 支撑 | 注册期可选兴趣标签（3 选，A2 的 ground truth） | P0 | **需新增** | `[PRO-5 §6.4-3]` |
| 播放 | HTTP Range 206，媒体流可拖动/弱网可播 | P0 | 已实现 | `[PRD-§5 A9][api.md §3]` |
| 播放 | **可见性/审核状态对媒体流的访问控制** | P0 | **需新增** | 本单描述 §4/§5 + 合规 |
| 治理 | **鉴权（Bearer token）+ 限流（令牌桶）** | **P0（上线阻塞）** | **需新增** | 本单描述 §3 FR-4；`[PRO-5 §6.4-1][R5]` |
| 治理 | 管理端点鉴权（`/api/admin/*` 现为**无鉴权**） | P0 | **需新增** | §十 app.py-G7 |
| 可用性 | 最小可点 Web **上传页** + **feed 页**（真实 UI，供 A4 可用性测试） | P0 | **需新增** | `[PRO-5 §6.1]` |
| 反馈 | 创作者发布后**最小曝光反馈位**（「已推送给 X 人」，X 必须为真实曝光数，禁止写死或夸大） | P1 | **需新增** | `[F4-§4.6][PRO-5 §6.1]` |
| 运维 | 指标快照端点（P10 / Gini / 命中率），供护栏告警 | P1 | **需新增** | `[PRO-5 §4.4.2]` |

### 2.2 Out of scope（本 MVP 不做，含复查触发条件）

| 不做项 | 说明 | 复查触发条件 |
|---|---|---|
| 视频编辑（剪辑/滤镜/模板/音乐库） | 创作阶段需求整体后置（NG4） | 发布侧 P0 达标且上传失败率已量化 |
| **分片上传 / 断点续传 / 上传进度条（服务端侧）** | 需求为 P1；**必须先量化失败率**，否则无法判断是否需要 | **上传失败率 > 5%**（口径 §3.1.5） |
| 关注页 / 消息 / 推送通知 | 社交关系沉淀属 P1/P2 | 阶段 2 消费侧指标达标 |
| 搜索 / 话题聚合页 | 观众侧 P1 | 垂类内容密度达标（每垂类 ≥ 500 条） |
| 创作者数据看板（完整版） | 仅保留 §2.1 的最小曝光反馈位 | A5 验证通过 |
| 多平台一键分发 | 假门 V3「省时间」若胜出则重估 | V3 − max(V1,V2) ≥ 3pp |
| LBS / 电商 / 支付 / 打赏 / 订阅 | 战略级 Non-Goal（NG3/NG6） | PRO-5 §4.2 门槛达成 |
| 移动端原生 App | 先 Web + 移动 Web（NG8） | 阶段 2 消费指标达标 |
| DNN 排序 / 实时特征 | NG5 | A8 验证通过 |
| 完整分成结算系统 | MVP 仅公开规则、不结算 | 广告门槛达成 |
| 评论正文存储与展示 | 仅保留 `comment` 事件计数，不做评论区 | 内容密度达标后 |
| 人工审核后台 UI | 仅提供审核钩子 API + 状态机，不做后台页面 | 审核量 > 500 条/日 |

### 2.3 用户故事（范围视角）

| ID | 用户故事 | 优先级 | 验收映射 |
|---|---|---|---|
| US-C1 | 作为创作者，我上传一个 mp4 并附文案，**3 步内**完成发布 | P0 | AC-U-01/08 |
| US-C2 | 作为创作者，我用 `#话题` 标注内容，系统自动识别成标签（无需填表单） | P0 | AC-U-06 |
| US-C3 | 作为创作者，我上传后立刻看到是否有曝光（不用等 24 小时） | P1 | AC-U-12 |
| US-C4 | 作为创作者，我重复上传同一视频时被明确告知已存在，而不是静默失败 | P1 | AC-U-05 |
| US-C5 | 作为创作者，我上传超长/损坏文件时得到可理解的原因说明 | P1 | AC-U-04 |
| US-C6 | 作为创作者，我能设置视频可见性（公开/不公开/私密） | P0 | AC-U-09 |
| US-C7 | 作为创作者，我上传后视频在审核通过前不被公开推荐 | P0 | AC-U-10 |
| US-C8 | 作为创作者，网络中断后我重试上传，**不会产生重复视频也不会看到错误** | P0 | AC-U-07 |
| US-V1 | 作为观众，我打开就有一条按我兴趣排序的视频流 | P0 | AC-F-01 |
| US-V2 | 作为观众，我不会连续刷到同一个人或同一类视频 | P0 | AC-F-06 |
| US-V3 | 作为观众，我 7 天内看过的视频不会重复出现 | P1 | AC-F-07 |
| US-V4 | 作为观众，我给一条视频点赞后，推荐流会变（可感知的个性化） | P1 | AC-F-05 |
| US-V5 | 作为观众，我会偶尔刷到一条「意外的」内容（探索位） | P1 | AC-F-08 |
| US-V6 | 作为观众，我**一直往下滑能持续拿到新内容**（无限滚动） | P0 | AC-F-09 |
| US-V7 | 作为观众，我对某条视频点「不感兴趣」后，它**立即消失且不再出现** | P0 | AC-F-10 |
| US-V8 | 作为观众，我举报一条视频后，平台会记录并纳入审核 | P0 | AC-F-11 |
| US-O1 | 作为运营，我能看到每条推荐的理由，便于归因 | P1 | AC-F-12 |
| US-O2 | 作为运营，我能调整推荐权重而不用改代码 | P1 | AC-F-13 |
| US-O3 | 作为运营，我能手工触发协同过滤重建（**且该操作只有管理员能做**） | P2 | AC-S-07 |

---

## 三、功能需求

> 本章每条需求包含：**现状（含代码位置 + 判定）→ 规格 → 错误与边界**。所有「现状」判定均可在 §十 Gap 表交叉核对。

### 3.1 FR-1 视频上传 `[PRD-§3.1 语义保持]`

#### 3.1.1 现状（已实现部分，不得当作新需求）

| 能力 | 实现位置 | 实测结论 |
|---|---|---|
| 流式 multipart 解析，内存驻留 ≤ 64KB | `media.py::parse_multipart`、`_iter_raw_parts`、`LengthLimitedReader` | ✅ 已实现，27 项单测覆盖（含边界跨块、短读累积） |
| 扩展名 / MIME / 体积 / 时长 / 分辨率五重校验 | `media.py::validate_upload`（`config.ALLOWED_EXT/ALLOWED_MIME/MAX_UPLOAD_BYTES/MIN_DURATION_MS/MAX_DURATION_MS`） | ✅ 已实现 |
| 服务端 ffprobe 真值（不信任客户端） | `media.py::probe_media` | ✅ 已实现（**缺失时 fail-open，见 F-1**） |
| sha256 去重 → 409 带原 `video_id` | `app.py::upload_video` + `db.py::hash_exists` | ✅ 已实现（**全站口径，见 F-6**） |
| `#话题` 抽取 + 显式 tags 合并去重（≤8） | `media.py::extract_tags` | ✅ 已实现 |
| 分桶存储 `var/media/YYYY/MM/<id>.<ext>` | `media.py::storage_path_for` / `persist` | ✅ 已实现 |
| 统一错误信封 `{"error":{"code","message"}}` | `app.py::_send_error_json` | ✅ 已实现 |

#### 3.1.2 规格：FR-1.1 格式与大小限制（保持并冻结）

| 项 | 冻结值 | 位置 |
|---|---|---|
| 容器/扩展名 | `.mp4` / `.mov` / `.webm` / `.mkv` | `config.ALLOWED_EXT` |
| MIME | `video/mp4` / `video/quicktime` / `video/webm` / `video/x-matroska` | `config.ALLOWED_MIME` |
| 单请求体上限 | **200 MB**（`SVP_MAX_UPLOAD_MB` 可覆盖） | `config.MAX_UPLOAD_BYTES` |
| 时长 | **1s ~ 180s**（服务端 ffprobe 真值） | `MIN/MAX_DURATION_MS` |
| 分辨率 | **高度 ≥ 240px** | `media.py:387` |
| 去重 | 全站 sha256 唯一 | `db.py::hash_exists` |

**新增约束 FR-1.1.a（fail-closed）**：生产环境（`SVP_ENV=prod`）下 **ffprobe 不可用必须直接拒绝上传**（`503 probe_unavailable`），不得降级放行。理由：`media.py:326-328` 在 ffprobe 缺失时返回全 0 值，`validate_upload:377` 的 `if meta.get("available")` 使时长与分辨率校验被整体跳过——即**攻击者只需让服务端探测失败即可绕过全部内容校验**（fail-open 缺陷）。开发环境保留降级但必须打 `media_probe_degraded` 结构化日志。
→ 判定：**需改造**（`media.py`）。

#### 3.1.3 规格：FR-1.2 分片 / 断点续传 —— **本 MVP 明确不做（NG11）**

| 项 | 裁定 |
|---|---|
| 是否分片 | ❌ 不做。`POST /api/videos` 保持**单请求整体上传**（`Content-Length` 必填，服务端流式落盘） |
| 是否断点续传 | ❌ 不做。理由：PRO-5 §6.2 判定「需求优先级 P1，但**必须先把失败率量化**，否则无法判断是否需要」 |
| **前置义务（P0）** | ✅ **必须量化上传失败率**（口径见 §3.1.5）。不量化则该 Out of scope 判定不成立 |
| **前向兼容契约（现在就要遵守）** | 为未来引入分片**预留**而不实现：① 响应中预留可选 `upload_id` 字段（本版恒为 `null`）；② 客户端**不得**依赖「同一 `Content-Length` 只能上传一次」；③ 新增端点必须走 `/api/uploads/*` 命名空间，禁止复用 `/api/videos` 语义 |
| 复查触发 | 上传失败率 > 5% → 重新评估并单独立项 |

**设计说明（为什么值得显式写下来）**：断点续传是「看起来必需、实际常被过度设计」的功能。在 200MB / 4G 网络下，单请求上传的失败率通常在可接受区间；真正的解法往往是把 200MB 上限降到 50MB 或做客户端压缩，成本远低于实现 resumable 协议。因此本 PRD 选择**先测量、后决策**，并把预留契约写清，避免未来改造成破坏性变更。

#### 3.1.4 规格：FR-1.3 进度与失败重试（幂等语义，关键）

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-1.3.a | **进度反馈** | 客户端侧从 `XMLHttpRequest.upload.onprogress` 计算。服务端义务：① 必须**流式落盘**（已满足）；② 响应必须带 `Content-Length`；③ **不得**在响应前缓存整个上传体（已满足）。服务端不提供进度查询端点（本 MVP 无服务端上传会话状态） |
| FR-1.3.b | **重试必须是幂等的** | 上传失败（网络中断 / 5xx / 超时）后客户端重试，**不得**产生重复视频，**不得**返回用户不可理解的错误 |
| FR-1.3.c | **409 的语义冻结（`duplicate_video`）** | 服务端返回 409 `duplicate_video` 且报文含原 `video_id` 时，**客户端必须将其视为「上传成功」**：直接采用报文中的 `video_id` 进入发布成功流程，禁止展示为错误。理由：sha256 去重使「重试」天然等价于「已成功」——**这是本 MVP 幂等性的唯一实现机制**，若不冻结该语义，一次 5xx 重试就会让创作者看到「视频已存在」的报错（最典型的静默/误导失败） |
| FR-1.3.d | **可重试状态码白名单** | 仅 **408 / 429 / 500 / 502 / 503 / 504** 与网络错误可自动重试；**4xx（除 408/429）一律不可重试**（重试同一无效载荷必然再失败）。退避策略：指数退避 + 抖动，`min(2^n, 30s)`，最多 **3** 次 |
| FR-1.3.e | **失败可理解** | 每次失败必须向创作者展示**错误码对应的人话原因**（见 §八 错误码表的「用户可见文案」列），禁止只展示「上传失败」 |
| FR-1.3.f | **超时** | 服务端单请求处理上限 **300s**；客户端上传超时按 `max(60s, size_bytes / 256KBps)` 计算，避免大文件被过早判超时 |

→ 判定：**需改造**（`app.py` 需冻结 409 语义的响应契约 + 新增 §八 错误码文案表；客户端为新交付）。

#### 3.1.5 规格：FR-1.4 元数据（标题 / 话题 / 可见性）

| 字段 | 类型 | 必填 | 规则 | 现状 |
|---|---|---|---|---|
| `title` | string | ❌ | ≤ **100** 字符（UTF-8 码点计数，非字节）；**允许为空**，空则回退为 `caption` 前 30 个码点 | **需新增**（当前仅有 `caption`） |
| `caption` | string | ❌ | ≤ **500** 字符（**已被静默截断**，见 F-7，须改为显式校验或显式标注截断） | 已实现（`app.py:78`） |
| `tags` | string[] | ❌ | 显式标签，与 `#话题` 合并去重，**≤ 8** 个；单标签 ≤ 24 字符 | 已实现（`media.py::extract_tags`） |
| `visibility` | enum | ❌ | `public`（默认）/ `unlisted` / `private` | **需新增** |
| `creator_id` | string | ✅ | 必须为已注册用户 | 已实现 |

**可见性语义冻结**：

| 值 | 出现在推荐流 | 出现在作者主页 | 出现在 `GET /api/videos` 全站列表 | 持有链接可播放 |
|---|---|---|---|---|
| `public` | ✅ | ✅ | ✅ | ✅ |
| `unlisted` | ❌ | ✅ | ❌ | ✅（链接可见） |
| `private` | ❌ | ✅（仅作者本人） | ❌ | ❌（403） |

**重要缺口（F-2）**：`videos.status` 列（`db.py:38`，注释 `published|hidden|removed`）**已存在但从未被写入非 `published` 值**——`db.py::create_video` 硬编码 `'published'`，且**没有任何 API 可修改它**。同时 `list_all_videos` 已按 `status='published'` 过滤，`list_videos_by_creator` 亦然。因此：**schema 已就绪，存取层与 API 层缺失**。判定：`db.py` **需改造**（补 `visibility` 列 + 写路径），`app.py` **需新增**（`PATCH` 端点）。
→ 判定汇总：**需新增**（数据列 + API）。

#### 3.1.6 规格：FR-1.5 审核钩子（Moderation Hook）

**现状**：❌ **完全不存在**（`grep -rni "moderation\|审核" server/` 无结果）。当前上传成功即以 `status='published'` 立即进入公开推荐流。这是**合规与生态护栏（S7 举报率 < 0.5%）的缺失前置**。

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-1.5.a | **审核状态机** | `moderation_status ∈ {pending, approved, rejected}`；上传后初值由 `config.MODERATION_MODE` 决定 |
| FR-1.5.b | **三种模式** | `off`（默认，仅开发/内网）：上传即 `approved`；`sync`：阻塞调用钩子，超时 **2s** 则降级为 `pending`；`async`：异步入队，上传即 `pending` |
| FR-1.5.c | **钩子接口（进程内可插拔）** | `moderate(video_meta) -> ModerationDecision`，返回 `{decision, reason_code, labels[]}`。MVP 提供两个实现：`AllowAllHook`（默认）与 `KeywordBlockHook`（对 `caption/title/tags` 做禁用词匹配，命中即 `rejected`） |
| FR-1.5.d | **审核回调端点** | `POST /api/internal/moderation/callback`，需 **管理员 token**（见 §3.5），body `{video_id, decision, reason_code}`；幂等（同一 `video_id` 重复回调以最后一次为准） |
| FR-1.5.e | **推荐与列表可见性约束（强制）** | 推荐流、全站列表、作者主页、媒体流**一律**要求 `status='published' AND moderation_status='approved'`；`visibility` 再按 §3.1.5 表逐通道过滤 |
| FR-1.5.f | **举报联动** | `report` 事件累计 ≥ `REPORT_AUTO_HIDE_THRESHOLD`（默认 **5** 个去重用户）→ 自动置 `status='hidden'` 并进入人工复审队列；复审通过则恢复 |
| FR-1.5.g | **SLA 与告警** | `pending` 超过 **30 分钟**必须产生告警（指标 `moderation_pending_age_p99`）；`pending` 队列长度 > 100 触发告警。**禁止**因超时自动放行（避免"审核形同虚设"） |
| FR-1.5.h | **审核不可绕过** | `PATCH` 修改 `caption/title/tags` 后，`moderation_status` 必须**重置为 `pending`**（防止先过审后改文案注入违规内容） |

→ 判定：**需新增**（`db.py` 加列 + `media.py`/新模块放钩子 + `app.py` 加端点与过滤；`recommend.py` 与 `db.py` 的查询需加过滤条件）。

#### 3.1.7 FR-1 错误码（新增/变更项）

沿用 v1.0 既有错误码（`unsupported_extension` / `unsupported_mime` / `payload_too_large` / `empty_file` / `duration_too_long` / `duration_too_short` / `resolution_too_low` / `unprobeable_media` / `duplicate_video` / `missing_creator` / `missing_file` / `bad_file_field` / `bad_content_type` / `missing_boundary`），**新增**：

| 错误码 | 状态 | 触发 | 用户可见文案（FR-1.3.e） |
|---|---|---|---|
| `probe_unavailable` | 503 | 生产环境 ffprobe 不可用（FR-1.1.a） | 系统暂时无法校验视频，请稍后重试 |
| `title_too_long` | 400 | `title` > 100 码点 | 标题最多 100 个字 |
| `caption_too_long` | 400 | `caption` > 500 码点（替代现静默截断） | 文案最多 500 个字 |
| `invalid_visibility` | 400 | `visibility` 不在枚举内 | 可见性取值不合法 |
| `video_rejected` | 422 | 审核拒绝（返回时不给上传者看命中词，防对抗） | 视频未通过审核（原因见消息中心） |
| `video_pending_review` | 202 | 上传成功但待审核（**非错误**，HTTP 202） | 已提交，审核通过后自动发布 |
| `upload_idempotent_replay` | 200 | 携带 `Idempotency-Key` 命中已完成上传（见 §八） | 视频已上传成功 |

---

### 3.2 FR-2 推荐流主链路 `[PRD-§3.2 语义保持]`

#### 3.2.1 现状（已实现部分）

| 能力 | 实现位置 | 实测结论 |
|---|---|---|
| 5 路召回（cf/follow/fresh/tag/fallback） | `recommend.py::recall` | ✅ 已实现，含 `tag` 与 `follow` 去重（`_exclude_routed`） |
| 线性加权 5 特征 | `recommend.py::features` / `score`；权重在 `config.RANK_WEIGHTS` | ✅ 已实现，且 `test_score_matches_manual_formula` 钉住公式 |
| 多路融合（按配额 × 候选池基准深度） | `recommend.py::feed`（`RECALL_QUOTAS × RECALL_BASE_DEPTH`，单路 `MIN_ROUTE_DEPTH`） | ✅ 已实现（**口径冲突见 §十一 C1**） |
| MMR 多样性重排 + 创作者打散（≤2） | `recommend.py::rerank` | ✅ 已实现，`test_mmr_prefers_diversity_over_pure_score` 覆盖 |
| 7 天已互动过滤 | `recommend.py::feed` + `db.py::user_seen_video_ids` | ⚠️ 已实现但**口径基于 `engagements`，非曝光**（F-3） |
| `seed` 可复现 | `recommend.py::feed(seed=)` | ✅ 已实现，`test_feed_is_deterministic_given_seed` 覆盖 |
| 可解释字段 `features` / `reason` / `recall_routes` | `recommend.py::_reason_for` | ✅ 已实现 |
| 冷启动判定与兜底放大 | `recommend.py::feed`（`cold_start`） | ✅ 已实现 |

#### 3.2.2 规格：FR-2.1 候选召回来源（冻结为 5 路 + 新增 1 路）

| 路 | 名称 | 信号 | 适用用户 | 现状 |
|---|---|---|---|---|
| R1 `cf` | item-item 协同过滤 | 共现余弦 `co_users / sqrt(pop_a·pop_b)`（`db.py::rebuild_item_similarity`） | 有历史行为 | ✅ 已实现 |
| R2 `follow` | 关注创作者 | 关注关系 × 新鲜度 | 有关注 | ✅ 已实现 |
| R3 `fresh` | 热门新鲜 | HN 式重力衰减 `(total/max)/(age_h+2)^1.2` | 全部 | ✅ 已实现 |
| R4 `tag` | 标签内容匹配 | 用户标签画像 × 视频标签向量余弦 | 有标签偏好 | ✅ 已实现 |
| R5 `fallback` | 冷启动兜底 | 全库热度归一 | 新用户/新视频 | ✅ 已实现 |
| **R6 `newcomer`** | **新视频保底曝光**（D1 机制兑现） | 见 FR-2.5 | 全部（受配额约束） | **需新增** |

**配额口径冻结（解决 PRO-5 §7.2-5 的冲突，这是本 PRD 的一项明确裁定，见 §十一 C1）**：

> **唯一有效口径 = 百分比 × 候选池基准深度（配置驱动），废弃「绝对条数」口径。**

```
route_depth(r) = max(MIN_ROUTE_DEPTH, round(RECALL_QUOTAS[r] × RECALL_BASE_DEPTH))
RECALL_BASE_DEPTH = 200 ; MIN_ROUTE_DEPTH = 20
RECALL_QUOTAS = {cf:0.30, follow:0.25, fresh:0.20, tag:0.15, fallback:0.10}   # 归一化和 = 1.0
```

| 路 | 百分比口径 | 现行 `config.py` | 等效深度 | `docs/03 §3.1` 绝对条数口径 | 裁定 |
|---|---|---|---|---|---|
| `cf` | 30% | 0.30 ✅ | 60 | 150 | **以 30% 为准** |
| `follow` | 25% | 0.25 ✅ | 50 | 80 | 以 25% 为准 |
| `fresh` | 20% | 0.20 ✅ | 40 | 120 | 以 20% 为准 |
| `tag` | 15% | 0.15 ✅ | 30 | 100 | 以 15% 为准 |
| `fallback` | 10% | 0.10 ✅ | 20（`MIN_ROUTE_DEPTH` 生效） | 50 | 以 10% 为准 |

**裁定理由**：① 代码与单测（`test_candidate_pool_not_starved_by_recall_quotas`、`test_feed_length_limited_by_available_content_not_quotas`）已固化百分比口径，且 `config.py:36-39` 明确记录了「配额乘 `size` 会饿死候选池」的踩坑史；② 绝对条数口径在内容库小于 500 条时与「总候选 500」这一前提自相矛盾；③ 百分比口径天然适配库规模增长，无需改配置。
**行动**：`docs/03-recommendation-design.md §3.1` 与 §2.2 架构图中「500 条总候选 / 150-80-120-100-50」表述须修订为百分比口径（本 PRD 实施项见 §九 M1-T3）。

**新增路 R6 的配额**：`RECALL_QUOTAS[newcomer] = 0.10`，同时按比例下调 `fallback` 至 `0.05`、`cf` 至 `0.25`（保持和为 1.0）。**该下调仅在 M4 上线 `newcomer` 路时生效**，避免在无保底机制时提前改变现有排序分布。

#### 3.2.3 规格：FR-2.2 排序基线（规则排序：热度 + 时效 + 多样性）

**打分公式（冻结，与 `config.RANK_WEIGHTS` 一致）**：

```
score = 0.45·Aff + 0.20·Pop + 0.15·Fresh + 0.10·Social + 0.10·Qual
```

| 特征 | 定义 | 值域 | 实现 |
|---|---|---|---|
| `Aff` | 用户标签画像（行为价值加权，`ACTION_VALUE`）与视频标签向量的余弦相似度（L2 归一化） | 0~1 | `recommend.py:252` |
| `Pop` | `log1p(互动总量) / log1p(全站最大互动量)`；互动总量 = `1·views + 2·completes + 3·likes + 5·shares` | 0~1 | `recommend.py` |
| `Fresh` | `0.5 ^ (age_hours / 48)` | 0~1 | `recommend.py::_freshness` |
| `Social` | 关注 = 1.0；二跳（我关注的人所关注的创作者）= 0.5；否则 0 | {0, 0.5, 1} | `recommend.py` |
| `Qual` | `0.6·min(1, 完播率/0.55) + 0.4·min(1, 点赞率/0.12)` | 0~1 | `recommend.py::_quality` |

**「热度 + 时效 + 多样性」的显式对应（回应本单描述的口径）**：热度 = `Pop`（对数压缩防头部垄断）；时效 = `Fresh`（48h 半衰期）+ R3 的 HN 重力衰减；多样性 = §3.2.4 的 MMR + 创作者打散。

**权重调整纪律（S8/护栏）**：任何 `RANK_WEIGHTS` 变更必须：① 版本化为 `weight_version` 并随 feed 响应返回（已实现）；② 有对应护栏监控（举报率 > 1% 或人均观看时长下降 → 回滚最近一次权重变更）；③ **禁止**在无对照实验的情况下调整。
→ 判定：**已实现**（无需改造，仅需补护栏告警，属 P1）。

#### 3.2.4 规格：FR-2.3 分页 / 无限滚动（**需新增**）

**现状缺口（F-4）**：`GET /api/feed` **没有任何分页参数**（`grep -rni "cursor\|offset\|page" server/` 无结果），响应也没有 `cursor` 字段。连续两次调用只能拿到「重新排队后的同一批」内容，且因为 `rerank` 的 `_jaccard` 与候选池截断，实际会返回**高度重叠**的列表。**无限滚动在本实现下不可用**——这不是"体验问题"，而是"无法实现"。

**冻结契约**：

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-2.3.a | **游标分页** | `GET /api/feed?user_id&size&cursor&session_id`；响应新增 `cursor`（下一页游标，末页为 `null`）与 `has_more` |
| FR-2.3.b | **游标不透明** | `cursor = base64url(JSON{v:1, ts, rank, video_id, weight_version, session_id, seen_fp})`。客户端**必须原样回传**，禁止解析或构造 |
| FR-2.3.c | **翻页稳定性要求** | 同一 `session_id` 内翻页**禁止出现重复 `video_id`**；允许因新内容进入而"挤压"（即允许跳过，不允许重复） |
| FR-2.3.d | **避免"翻页时排序漂移"** | 游标携带 `ts`；服务端在 `ts` 后 **120s** 内使用**同一评分快照语义**（以 `ts` 计算 `Fresh`/`Pop` 的时间基准，而非当前时间），超过 120s 的游标视为失效，返回 `409 cursor_expired` 并提示客户端刷新 |
| FR-2.3.e | **去重依据必须切到曝光** | 会话内已曝光集合以 `FeedImpression` 为准（而非 `engagements`）。这是分页正确性的前提：**看过但没互动的视频也必须被翻页去重**（F-3） |
| FR-2.3.f | **页大小** | `size` 1~50，默认 10（已实现）；无限滚动的推荐预取页大小 = 10，预取 2 页 |
| FR-2.3.g | **末页信号** | `has_more=false` 时客户端展示「暂时没有更多了，稍后再来」而非无限 loading |

**新增错误码**：`cursor_invalid`（400，游标解析失败/版本不符）、`cursor_expired`（409，超过 120s）。

**为什么用游标而不用 `offset`**：feed 是有状态推荐流（打分随 `Fresh`/`Pop`/行为实时变化），`offset` 会因排序漂移导致**重复与漏出同时发生**（经典分页 bug）。游标把「我在序列中的位置」编码成服务端可验证的不变量，是推荐流分页的行业标准做法。

→ 判定：**需新增**（`recommend.py::feed` 加游标参数与快照语义 + `app.py` 路由参数 + `db.py` 会话曝光查询）。

#### 3.2.5 规格：FR-2.4 重排与探索（含 **G1 死代码缺陷修复**）

**现状（重排部分，已实现）**：MMR（`λ = MMR_LAMBDA = 0.7`，相似度用标签 Jaccard）+ 创作者打散（`CREATOR_CAP_PER_FEED = 2`，被上限挡住时清空计数放宽补位）+ 候选池截断（`MMR_CANDIDATE_POOL = 200`）。

**⚠️ G1：ε-greedy 探索位是死代码（本 PRD 发现的高价值缺陷）**

事实（可复核）：`server/recommend.py` 第 **391–396** 行计算了 `explore_slots`，但第 **397–406** 行构造 `FeedItem` 时把 `is_exploration` **硬编码为 `False`**，且 `explore_slots` 此后再**未被引用**。

```python
# recommend.py:391-396（计算了，但下面没用）
items: list[FeedItem] = []
explore_slots = 0
if not cold_start and len(reranked) > 1:
    rng = random.Random((seed or 0) + 977)
    if rng.random() < config.EPSILON_EXPLORE:
        explore_slots = 1
items = [FeedItem(..., is_exploration=False) for c in reranked]   # ← 恒为 False
```

**影响**：① `README.md` 与 v1.0 PRD 均宣称「ε-greedy 探索位 10% 流量」，实际**从未投放**；② `ε` 探索是 PRO-5 D2（新品类/长尾不被永久埋没）与 S2（Gini ≤ 0.6）的机制之一；③ `is_exploration` 字段因此**永远为 false**，埋点与归因不可信；④ **86 项回归测试无一覆盖该路径**——说明测试覆盖存在结构性盲区（只测了"返回值形状"，未测"探索位是否真的被注入"）。

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-2.4.a | **探索位真实注入** | 非冷启动用户、按 `seed` 判定的请求（`rng.random() < EPSILON_EXPLORE`，默认 0.10）必须**在最终序列中真实替换一个位置**为探索项 |
| FR-2.4.b | **探索项的选取规则** | 从候选池中**不在 top-`size` 内**、且属于「低曝光分位（曝光量 < 全站 P30）」的候选中，按 `score` 降序取 1 条；若无合格候选则**不注入**（宁缺毋滥，避免为凑数降低质量） |
| FR-2.4.c | **注入位置** | 固定注入到**第 3 位之后**（索引 ≥ 3），前 3 位保持纯相关性（首屏体验优先） |
| FR-2.4.d | **可观测** | 被注入项 `is_exploration = true`，且 `FeedImpression.is_exploration` 同步落库；新增指标 `exploration_slot_rate`（应 ≈ 0.10，非冷启动用户） |
| FR-2.4.e | **冷启动例外** | 冷启动用户**不注入**探索位（保持现状：兜底池已承担探索功能），但须在 `docs/03 §6.1` 的"新用户首屏配额"落地后重新评估（该配额当前**未实现**，见 §3.3.2 F-8） |
| FR-2.4.f | **回归测试补强（强制）** | 必须新增至少 3 项测试：① 给定 `seed` 命中探索分支时 `is_exploration=true` 出现恰好 1 次；② 探索项索引 ≥ 3；③ 无合格探索候选时不注入。**禁止**以「字段存在」代替「行为发生」的测试写法 |

**探索 ε 的调参纪律**：`EPSILON_EXPLORE` 是 D2 的直接杠杆，调整须与 Gini 指标联动（Gini > 0.7 → 强制提升探索流量，PRO-5 §4.4.2）。

→ 判定：**需改造**（`recommend.py::feed` 接线 + `tests/` 补强）。**此项为 P1 但优先级高于同层其他项**，因为它是「声称已实现但实际未实现」的信任问题。

#### 3.2.6 规格：FR-2.5 负反馈（不感兴趣 / 举报）—— **PRO-5 G1，P0 必交付**

**现状**：❌ 不存在。`app.py::_KINDS = {"view","complete","like","share","skip","comment","follow"}` 中**无 `dislike` / `report`**；无观众侧出口；`db.py::add_engagement` 的计数器映射中亦无对应列。

**冻结语义**：

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-2.5.a | **`dislike`（不感兴趣）** | `POST /api/engagements {kind:"dislike"}`；写入 `interactions` 并**立即生效于当前会话**：该 `video_id` 从**同一 `session_id` 的后续所有 feed 页**排除 |
| FR-2.5.b | **永久排除** | `dislike` 后该视频对该用户**永久不再推荐**（`user_video_suppression` 表；有效期 = 永久，可通过运营侧解除）。**注意**：这与"7 天内已看过滤"是两套独立机制，`dislike` 不得只依赖 7 天窗口 |
| FR-2.5.c | **画像负权重** | `ACTION_VALUE["dislike"] = -3.0`（已在 `config.ACTION_VALUE` 的取值区间内：`skip` 为 -2.0），参与 `Aff` 画像（负值标签被 `user_tag_profile` 的 `v > 0` 过滤掉，因此实现上表现为**压制**而非负分，此行为须在单测中断言） |
| FR-2.5.d | **创作者级降权（保守）** | 仅当同一用户对**同一创作者**的 `dislike` 次数 **≥ 2** 时，该创作者其余视频 `score × 0.5`（`CREATOR_DISLIKE_PENALTY`）。单次 `dislike` **不**牵连创作者（避免误伤与对抗） |
| FR-2.5.e | **`report`（举报）** | `POST /api/engagements {kind:"report", reason_code}`；`reason_code ∈ {spam, porn, violence, hate, illegal, misinformation, other}`；写入后**不**影响该用户的推荐（举报 ≠ 不感兴趣） |
| FR-2.5.f | **举报联动审核** | 去重用户举报数 ≥ `REPORT_AUTO_HIDE_THRESHOLD`（默认 5）→ 自动 `status='hidden'` + 人工复审队列（FR-1.5.f） |
| FR-2.5.g | **能力边界（必须显式声明，避免过度承诺）** | 本 MVP **仅记录事件 + 做规则级抑制**，**不训练模型**、不做语义级降权。`is_exploration`/`dislike` 数据用于后续离线评估 |
| FR-2.5.h | **`skip` 与 `dislike` 的区别** | `skip` = 负向行为信号（弱，-2.0，仅影响画像）；`dislike` = 显式负反馈（强，永久排除 + 会话抑制）。**两者不得合并** |
| FR-2.5.i | **反作弊** | `dislike`/`report` 计入限流（§3.5）；同一用户对同一视频的重复 `dislike` 幂等（唯一索引，见 §7.3） |

**新增错误码**：`invalid_report_reason`（400）、`already_disliked`（幂等，返回 200 非错误）。

→ 判定：**需新增**（`db.py` 表与写路径 + `app.py` 类型白名单 + `recommend.py` 过滤与降权 + 新表）。

#### 3.2.7 规格：FR-2.6 可解释性（保持并扩展）

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-2.6.a | **`reason` 覆盖率 100%** | 每条 feed item 必须带 `reason`（人话，含主导特征 + 召回路径），已实现（`_reason_for`） |
| FR-2.6.b | **`features` 明细** | 必须带 5 特征原值，已实现；`include_explanation=false` 时省略（**注意**：当前 `app.py::feed` 未暴露该开关，恒为 `true`，属可接受简化） |
| FR-2.6.c | **`weight_version`** | 响应必须回传生效权重，已实现（用于 A/B 归因与回滚核对） |
| FR-2.6.d | **扩展（本次新增）** | feed item 需补 `playback_url`（`/api/videos/{id}/file`）、`width`、`height`、`created_at`、`visibility`、`moderation_status`（后两者供客户端置灰/占位）；**缺播放地址导致客户端必须二次请求**，是当前首屏延迟的隐性来源 |
| FR-2.6.e | **`reason` 不得泄露内部策略** | `reason` 面向创作者与运营，**禁止**包含权重系数、其他用户数据、风控规则 |

→ 判定：FR-2.6.a~c **已实现**；FR-2.6.d **需改造**；FR-2.6.e **需新增**（文案审查）。

#### 3.2.8 FR-2 错误码（新增项）

| 错误码 | 状态 | 触发 |
|---|---|---|
| `cursor_invalid` | 400 | 游标解析失败或版本不符 |
| `cursor_expired` | 409 | 游标超过 120s 有效期 |
| `session_missing` | 400 | `dislike` 未带 `session_id`（无法定位会话抑制范围） |
| `invalid_report_reason` | 400 | `reason_code` 不在枚举内 |

---

### 3.3 FR-2 冷启动（新用户 / 新视频 / 新品类）`[PRD-§3.3 语义保持]`

#### 3.3.1 现状（已实现部分）

| 场景 | 现状实现 | 判定 |
|---|---|---|
| 新用户判定 | `db.py::user_engagement_count` < `COLD_START_MAX_ENGAGEMENTS`（=3）→ `cold_start=true` | ✅ 已实现 |
| 新用户策略 | 放大 `fallback` 池（把全部 `fallback` 候选并入候选池）；**不启用探索位** | ⚠️ 部分实现（**首屏配额未实现**，见 F-8） |
| 新视频 | 由 `tag` / `fresh` / `fallback` 路由承接可获得初始曝光；无标签则仅 `fallback` | ✅ 机制存在，**但无保底额度**（F-5） |
| 新品类（标签无邻居） | MMR 多样性采样（`rerank` 天然对新标签生效） | ⚠️ 被动生效，无「新品类扶持位」 |

#### 3.3.2 现状缺口（本 PRD 必须补的 3 项）

**F-5｜新视频保底曝光未实现（D1 的机制缺口，**P0**）**：`docs/03 §6.2` 规定「新视频发布后 0~2h 进入探索池，固定曝光 **500~1000** 次」。当前实现**无此机制**，新视频能否被看到完全取决于 `fresh` 重力衰减与 `tag` 命中，**无任何下限保证**。更要紧的是：**曝光本身没有被记录**（无 `FeedImpression`），因此 S1（P10 ≥ 50）与 S2（Gini ≤ 0.6）**在数学上不可计算**。这与 PRO-5 §4.4.1 纪律 4 的判定一致。

**F-8｜新用户首屏配额未实现**：`docs/03 §6.1` 规定新用户首屏（N=10）=「3 条全局最热 + 3 条分垂类热门（各 1）+ 2 条探索（ε 提升至 0.3）+ 2 条高互动率长尾」。当前冷启动路径只是「把 `fallback` 全部并入候选池 + 关掉探索位」，**与设计的配额结构完全不同**：既没有分垂类保证，也没有提高 ε（反而降至 0），也没有长尾位。**这直接威胁 S3（首刷命中率 ≥ 60%）与 S4（20s 退出率 < 40%）**。

**F-9｜`docs/03 §6.2` 的「晋级机制 / 反作弊」未实现**：无「池内完播率 > 同垂类中位数 → 升级」逻辑，也无刷量识别（异常互动不计入热度）。在无限流、无鉴权的当前实现下，`view`/`like` 计数**可被脚本无限刷高**，直接污染 `Pop` 与 `Qual`（PRO-5 R5 已列为「前置阻塞」）。

#### 3.3.3 规格（冻结）

| 编号 | 需求 | 规格 | 优先级 |
|---|---|---|---|
| FR-2.7.a | **新用户判定** | `cold_start = (user 历史 interaction 数 < 3)`（保持）；**扩展**：注册期兴趣标签存在时，首刷必须保证该标签下内容 ≥ 3 条（若库内可得） | P0 |
| FR-2.7.b | **新用户首屏配额（落地 docs/03 §6.1）** | 满足 `cold_start=true` 的 feed 必须按槽位分配：**3 槽全局最热（`Pop`）+ 3 槽分垂类热门（不同垂类各 ≤1）+ 2 槽长尾高互动率（曝光 < P30 且 `Qual` ≥ P70）+ 2 槽探索（`ε_cold = 0.30`，从注册期兴趣标签外的垂类取）**。实现上作为 `rerank` 的**槽位约束**（slots），而非事后打补丁 | P0 |
| FR-2.7.c | **新视频保底曝光路由 R6 `newcomer`** | 见下 §3.2.5 的独立小节 | **P0** |
| FR-2.7.d | **新视频保护期** | 发布后 **24h 内**：① 不进入任何淘汰/降权逻辑（当前无淘汰池，须显式声明为"不适用"而非"已实现"）；② 若 `exposures < EXPOSURE_FLOOR`，`newcomer` 路优先补量 | P0 |
| FR-2.7.e | **新品类扶持位** | 每 20 个 feed 槽位预留 **1** 个给「曝光量处于全站最低 20% 分位的垂类」；垂类覆盖度（被曝光垂类 / 总垂类）< 0.6 时，`EPSILON_EXPLORE` 自动提升至 **0.20** | P1 |
| FR-2.7.f | **晋级机制** | 保底期内（24h）完播率 > 同垂类中位数 → 提升 `newcomer` 权重；连续 3 日低于中位数 → 退出保底 | P1 |
| FR-2.7.g | **反作弊（前置阻塞）** | 需鉴权（§3.5）后，`view`/`like` 计数按 `(user_id, video_id, kind)` 去重 + 限流；异常互动（同 IP 高频、无 `visible_ms` 的 view）**不计入 `Pop`/`Qual`** | **P0** |

#### 3.3.4 新视频保底曝光路由 R6（D1 的机制实现，**P0**）

**目标**：让 S1（首发 24h 曝光 P10 ≥ 50）成为**可计算、可兑现**的机制，而不是运营承诺。

```
准入条件（全部满足才进 R6 候选）：
  ① moderation_status = 'approved' 且 status = 'published' 且 visibility = 'public'
  ② age_hours ≤ 24
  ③ video.exposures < EXPOSURE_FLOOR            # 默认 50，与 A1 的 P10 判据同值
  ④ 该创作者的「同时处于保底期的视频数」≤ 1      # 防刷：一个创作者一次只保一条
  ⑤ Qual_prior ≥ QUAL_FLOOR                      # 默认 0.3，防低质内容借保底注入（PRO-5 R4）

排序键（保底内部）：
  newcomer_priority = 1 / (1 + video.exposures)     # 曝光越少越优先（progressive）
                    × fairness_boost(creator)       # 创作者历史曝光低于全站均值时放大（Gini 收敛）
                    × freshness(age_hours)          # 防止过期视频被保底

投放约束：
  单条 feed 内 R6 最多 1 槽；全站 R6 流量占比 ≤ 10%（RECALL_QUOTAS[newcomer]）
```

**Gini 收敛机制（S2）**：`fairness_boost(creator) = clamp(μ_exposure / max(1, creator_exposure), 0.5, 2.0)`，其中 `μ_exposure` 为全站创作者平均曝光量。Gini > 0.7 时 `fairness_boost` 上限提升至 3.0（PRO-5 §4.4.2 的「强制提升探索流量」）。

**兑现界面（PRO-5 §6.1「创作者反馈位」）**：`GET /api/videos/{id}/exposure` 返回 `{exposures, impressions, views, creator_exposure_p10}`；上传成功响应中**不含**该数字（避免与"已推送给 X 人"的实时性混淆）。**X 必须为真实曝光数，禁止写死或夸大**（PRO-5 §6.1 原文冻结）。

→ 判定：**需新增**（`recommend.py` 加 R6 路 + `db.py` 加 `exposures` 计数与查询 + `config.py` 加参数 + 新端点）。

---

### 3.4 FR-3 最小支撑（账号/会话、内容详情、基础互动、埋点事件）`[PRD-§3.4 语义保持，语义扩展]`

> v1.0 的 `[PRD-§3.4]` 仅覆盖「互动埋点」。本版扩展为 FR-3 最小支撑，**埋点定义仍在本节 §3.4.4**，上游引用语义保持。

#### 3.4.1 现状

| 能力 | 实现位置 | 判定 |
|---|---|---|
| 创建用户（handle 2~32 位，唯一） | `app.py::create_user` | ✅ 已实现（**无凭据**，F-10） |
| 查询用户 | `GET /api/users/{id}` | ✅ 已实现 |
| 内容详情 | `GET /api/videos/{id}`（含 `video_stats` 连接） | ⚠️ 已实现但**缺播放地址 / 作者信息 / 本人互动状态**（F-11） |
| 全站视频列表 | `GET /api/videos` | ⚠️ 已实现但**无分页**（`list_all_videos` 全量返回） |
| 点赞 | `POST /api/engagements {kind:"like"}` | ⚠️ 已实现但**非幂等、无法取消**（F-12） |
| 关注 | `POST /api/follows` | ✅ 已实现（`self_follow` 已校验） |
| 7 类埋点 | `app.py::_KINDS` + `db.py::add_engagement`（反规范化计数器） | ✅ 已实现（**缺曝光/首刷/退出**，F-13） |

#### 3.4.2 规格：FR-3.1 账号与会话（**需新增**）

**F-10 现状**：`POST /api/users` 仅创建用户并返回 `{id, handle, display, created_at}`，**没有任何凭据**。因此此后所有写接口（上传、点赞、关注、审核）**无法鉴别调用者身份**——任何人都可以以任意 `creator_id` 上传、以任意 `user_id` 点赞。这是 §3.5（FR-4）的直接前置。

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-3.1.a | **用户凭据** | `POST /api/users` 响应**新增** `token`（32 字节 URL-safe base64，仅本次返回一次，服务端只存 `sha256(token)`）；同时**保持** `id/handle/display/created_at` 字段不变（向后兼容） |
| FR-3.1.b | **会话端点** | `POST /api/sessions {handle}` → `{token, user_id, expires_at}`。MVP 为**开发级**身份（无密码/验证码），**必须**在响应与文档中显式标注 `auth_level: "dev"` |
| FR-3.1.c | **鉴权头** | `Authorization: Bearer <token>`；服务端按 token 解析出 `user_id`，**与之冲突的请求体 `user_id`/`creator_id` 一律拒绝**（`403 identity_mismatch`），杜绝越权冒用 |
| FR-3.1.d | **令牌生命周期** | 有效期 **30 天**；`POST /api/sessions/revoke` 撤销；`last_seen_at` 每次请求更新 |
| FR-3.1.e | **注册期兴趣标签（A2 ground truth）** | `POST /api/users` 支持可选 `interest_tags: string[]`（**恰好 3 个**，从配置的垂类白名单中选择）；用于 S3 判据的计算基准 |
| FR-3.1.f | **注册来源** | 支持可选 `source`（`seed_invite` / `organic` / `ad` …），用于冷启动归因 |

→ 判定：**需新增**（`db.py` 新增 `user_tokens` 表与 `interest_tags` 列 + `app.py` 鉴权中间层 + 新端点）。

#### 3.4.3 规格：FR-3.2 内容详情与 FR-3.3 基础互动

**FR-3.2 内容详情（需改造）**

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-3.2.a | **补全字段** | `GET /api/videos/{id}` 响应新增：`playback_url`（`/api/videos/{id}/file`）、`title`、`visibility`、`moderation_status`、`author{id,handle,display}`、`viewer_state{liked, disliked, following_author}` |
| FR-3.2.b | **权限矩阵** | 按 §3.1.5 表：`private` 仅作者可读（否则 403 `video_private`）；`hidden`/`rejected` 仅作者可见（否则 404，**不得泄露存在性**） |
| FR-3.2.c | **列表分页** | `GET /api/videos` 支持 `cursor`/`size`（≤50），**禁止**全量返回（防大库 OOM 与抓库） |
| FR-3.2.d | **接口不泄露内部字段** | 响应**禁止**包含 `storage_path`（当前 `get_video` 会返回相对存储路径——信息泄露 + 耦合存储布局，须移除或仅管理员可见） |

**F-11 补充说明**：`GET /api/videos/{id}` 当前直接返回 `_video_row_to_dict(row)`，其中含 `storage_path` 与 `sha256`。`sha256` 可用于**跨用户探测"这个文件平台是否已有"**（配合 `duplicate_video` 的存在性差异），属于可被滥用的信息。裁定：`sha256` 仅对作者本人返回。

**FR-3.3 基础互动（需改造，P0 幂等性）**

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-3.3.a | **点赞幂等** | `(user_id, video_id, kind='like')` 唯一；重复点赞**不**累加 `video_stats.likes`，返回 **200** 且 `{already: true}`（幂等成功，非错误） |
| FR-3.3.b | **取消点赞** | `DELETE /api/engagements?user_id&video_id&kind=like`（或 `POST kind=unlike`），`likes` 计数递减且**不得为负**（`max(0, ...)`） |
| FR-3.3.c | **计数一致性** | `video_stats` 计数必须可由 `interactions` 重算一致（提供 `POST /api/admin/recount` 校对端点，P1）。**当前实现只要用户重复点赞就会永久虚高，且无任何校对手段** |
| FR-3.3.d | **重复 view 语义** | `view` **允许**重复（同一用户可多次观看）；但计入 `Pop` 的 `views` 必须为**去重用户数**口径（见 §十一 C2 口径冻结） |
| FR-3.3.e | **follow 幂等** | `follows` 已有主键 `(follower_id, followee_id)` + `INSERT OR IGNORE` ✅；但 `video_stats` 无 follow 计数，无需处理 |
| FR-3.3.f | **互动归属校验** | `user_id` 必须来自鉴权 token（FR-3.1.c）；`video_id` 必须 `published` 且对调用者可见 |

**F-12 证据（幂等缺陷可复核）**：`db.py::add_engagement` 无条件 `INSERT INTO engagements(...)` 并 `ON CONFLICT ... likes = likes + 1`；`engagements` 表**无任何唯一约束**（`db.py:44-53` 只有 `id` 主键与两个非唯一索引）。因此同一用户 `POST {kind:"like"}` 两次 → `likes = 2`。测试 `test_engagement_updates_stats` 只验证「上报后计数增加」，未验证幂等。

→ 判定：**需改造**（`db.py` 加唯一索引与写路径 + `app.py` 加 DELETE 路由与 `unlike`）。

#### 3.4.4 规格：FR-3.4 埋点事件（含 **`exposure` 曝光**，PRO-5 §6.4-6）

**F-13 现状**：现有 7 类 `kind ∈ {view, complete, like, share, skip, comment, follow}`（`app.py:104`），计数器映射 6 列（`db.py:239-246`，`follow` 无计数列）。**无 `exposure` / `dislike` / `report` / `unlike` / `session_start` / `exit`。**

**冻结的完整事件字典**：

| `kind` | 触发时机 | 是否幂等 | 计数列 | 现状 |
|---|---|---|---|---|
| `exposure` | **客户端上报「已可见」**（`is_visible && visible_ms ≥ 1000`） | 否（可多次） | `exposures` | **需新增** |
| `view` | 视频开始播放 | 否 | `views` | 已实现 |
| `complete` | 播放完成（≥ 95% 或末帧） | 否 | `completes` | 已实现 |
| `like` | 点赞 | **是** | `likes` | 已实现（**非幂等，须修**） |
| `unlike` | 取消点赞 | 是 | `likes`(−1) | **需新增** |
| `share` | 点击分享 | 否 | `shares` | 已实现 |
| `skip` | 快速划过（< 2s 且未播完） | 否 | `skips` | 已实现 |
| `dislike` | 「不感兴趣」 | **是** | `dislikes` | **需新增（P0）** |
| `report` | 举报 | **是** | `reports` | **需新增（P0）** |
| `comment` | 发表评论 | 否 | `comments` | 已实现（**无正文存储**） |
| `follow` | 关注（创作者 = 视频作者） | 是 | — | 已实现 |
| `unfollow` | 取消关注 | 是 | — | **需新增** |
| `session_start` | 进入 feed 会话（**首刷标记**） | 是 | — | **需新增** |
| `session_exit` | 离开 feed（带 `dwell_ms`，**退出事件**） | 是 | — | **需新增** |
| `feed_request` | 每次 feed 请求（只写曝光表，不写 interactions） | — | — | **需新增** |

**埋点纪律（冻结）**：
1. 客户端事件**必须**带 `session_id`（会话级指标的分母）。
2. `exposure` 必须带 `visible_ms` 与 `position`（位置偏差分析的前置）。
3. **服务端与客户端双写**：服务端在返回 feed 时写 `FeedImpression(served_at)`（`source='server'`）；客户端确认可见时写 `FeedImpression(client_reported_at, visible_ms, is_visible=1)`（`source='client'`）。**只有 `is_visible=1` 的计入曝光口径**。
4. 埋点写入必须**异步化或批量**（`POST /api/impressions` 支持数组批量），避免打分成热点写（SQLite 单写锁）。
5. 埋点**不得**因写入失败而阻断播放链路（客户端 fire-and-forget + 失败静默重试 1 次）。

→ 判定：**需改造 + 需新增**（`config.ACTION_VALUE` 扩展、`db.py` 表与计数列、`app.py` 白名单与端点、新增 `FeedImpression` 表）。

---

### 3.5 FR-4 鉴权与限流（MVP 现为内网假设，上线前必须补）

#### 3.5.1 现状（**全部缺失**，可复核）

| 检查项 | 命令 | 结果 | 判定 |
|---|---|---|---|
| 鉴权代码 | `grep -rni "auth\|token" server/` | **无匹配** | ❌ 不存在 |
| 限流代码 | `grep -rni "rate_limit\|限流" server/` | **无匹配** | ❌ 不存在 |
| CORS | `app.py:216`（`Access-Control-Allow-Origin: *`）、`258`、`368` | 全域放开 | ⚠️ 需收紧 |
| 管理端点 | `app.py:319` `POST /api/admin/rebuild-cf` | **无任何鉴权**，任何人可触发全表重建（`DELETE FROM item_sim` + 全表重算 = 拒绝服务面） | ❌ 高危 |
| 并发保护 | `app.py:424` `ThreadingHTTPServer` | 每连接一线程，**无上限** | ⚠️ 需补 |
| 上传体积前置检查 | `app.py:302` | 有 `Content-Length` 预检 ✅ | ✅ 已实现 |

#### 3.5.2 规格：FR-4.1 鉴权（**P0，上线阻塞**）

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-4.1.a | **Bearer 鉴权** | 所有**写**接口需 `Authorization: Bearer <token>`；缺失 → `401 unauthenticated`；令牌无效/过期 → `401 token_invalid` |
| FR-4.1.b | **身份一致性** | 请求体/查询中的 `user_id`/`creator_id` 必须等于 token 解析出的身份，否则 `403 identity_mismatch`（杜绝冒用） |
| FR-4.1.c | **读接口分级** | 公开读（`GET /api/videos`、`GET /api/videos/{id}` 对 `public`、`/api/health`、`/`）**免鉴权**；其余读需鉴权。**免鉴权不等于免限流** |
| FR-4.1.d | **管理端点隔离** | `/api/admin/*` 与 `/api/internal/*` 需**独立管理员凭据**（`SVP_ADMIN_TOKEN`，环境变量注入，**禁止**硬编码）；管理员 token 与用户 token **不共用签发路径** |
| FR-4.1.e | **CORS 收紧** | `Access-Control-Allow-Origin` 必须由 `SVP_CORS_ORIGINS`（逗号分隔白名单）驱动，**默认不为 `*`**；`Access-Control-Allow-Headers` 须包含 `Authorization`、`Content-Type`、`X-Request-Id` |
| FR-4.1.f | **秘密管理** | 所有密钥仅经环境变量注入；日志与错误响应**禁止**回显 token（须做 `***` 脱敏） |
| FR-4.1.g | **媒体流访问控制** | `GET /api/videos/{id}/file` 必须按 §3.1.5 权限矩阵校验（当前**任何持 id 者均可下载**，`private`/`unlisted` 语义无法成立） |

#### 3.5.3 规格：FR-4.2 限流（**P0，上线阻塞**）

**算法**：令牌桶（token bucket），两级键 = `user_id`（已鉴权）+ `client_ip`（未鉴权/兜底）。存储用进程内 `dict` + 锁（MVP 单机可接受；多实例时须迁 Redis，属已知限制 §六）。

| 端点 | 用户级速率 | IP 级速率 | 说明 |
|---|---|---|---|
| `POST /api/videos` | **5 / 分钟** 且 **20 / 天** | 10 / 分钟 | 上传是重资源，最严 |
| `POST /api/engagements` | 120 / 分钟 | 300 / 分钟 | 含埋点，需留量 |
| `POST /api/impressions` | 60 / 分钟（批量，每批 ≤ 50 条） | 120 / 分钟 | 埋点批量 |
| `GET /api/feed` | 60 / 分钟 | 120 / 分钟 | |
| `GET /api/videos` / `{id}` | 120 / 分钟 | 300 / 分钟 | |
| `POST /api/users` | — | **5 / 小时** | 防批量注册（结合 FR-3.1.e 的标签校验） |
| `POST /api/sessions` | — | 20 / 小时 | |
| `POST /api/admin/*` | 10 / 分钟 | — | |
| **全局兜底** | — | **600 / 分钟** | 防单 IP 打满所有端点 |

| 编号 | 需求 | 规格 |
|---|---|---|
| FR-4.2.a | **429 契约** | 超限返回 `429 rate_limited`，必须带 `Retry-After: <秒>` 与 `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset` |
| FR-4.2.b | **上传前预检** | 上传限流检查必须在**读取请求体之前**执行（否则限流失去保护意义，因为读体本身已消耗 IO/磁盘）。当前 `app.py` 的体积预检已在读体前 ✅，限流须同样前置 |
| FR-4.2.c | **慢速攻击防护** | 单请求读取超时 **30s**（首字节后无数据即断）、请求体读取总时长 **300s** 上限；连接数上限（`MAX_CONCURRENT_CONNS`，默认 200），超限快速失败 |
| FR-4.2.d | **豁免路径** | `/api/health` 不限流（供探活） |
| FR-4.2.e | **可观测** | 新增指标 `rate_limited_total{endpoint}`；> 阈值告警（异常突增可能是攻击或客户端 bug） |
| FR-4.2.f | **反刷量联动（FR-2.7.g）** | 限流是「`like`/`view` 不可被脚本刷高」的前置。限流上线前，`Pop`/`Qual` 与一切 A/B 结论**不可信**（PRO-5 R5） |

#### 3.5.4 FR-4 错误码（新增项）

| 错误码 | 状态 | 触发 |
|---|---|---|
| `unauthenticated` | 401 | 缺少 `Authorization` 头 |
| `token_invalid` | 401 | 令牌不存在/已撤销 |
| `token_expired` | 401 | 令牌超过 30 天 |
| `identity_mismatch` | 403 | 请求身份与 token 身份不一致 |
| `admin_required` | 403 | 访问管理/内部端点但非管理员 |
| `video_private` | 403 | 访问 `private` 视频但非作者 |
| `rate_limited` | 429 | 超过令牌桶速率 |

→ 判定：**需新增**（`app.py` 鉴权中间层 + 限流器 + CORS 白名单；`db.py` `user_tokens` 表；`config.py` 新增参数）。

---

## 四、非功能需求

### 4.1 性能与延迟预算

`docs/03 §2.3` 给出的单次 feed 请求 P99 预算为 **≤ 110ms（含兜底重试 ≤ 200ms）**。本 PRD 将其落为**可测门禁**：

| 阶段 | `docs/03` 预算 | 本 PRD 门禁 | 现状风险 |
|---|---|---|---|
| 上下文拉取 + 用户特征 | 10 ms | ≤ 15 ms | ⚠️ `user_tag_profile` 对每条历史行为调 `db.get_video()`（N+1 查询） |
| 多路召回 | 40 ms | ≤ 60 ms | ⚠️ 5 路**串行**执行（非并行）；`item_similarity` 对每个已互动视频发一次 SQL |
| 过滤 + 排序 | 35 ms | ≤ 45 ms | ✅ 内存计算 |
| 重排 | 10 ms | ≤ 15 ms | ⚠️ `rerank` 为 O(size × pool) 双层扫描，`MMR_CANDIDATE_POOL=200` 时约 2000 次 Jaccard |
| 序列化 + 网络 | 15 ms | ≤ 20 ms | ✅ |

**门禁要求（新增，P1）**：
- NF-1：`GET /api/feed` 在 `MMR_CANDIDATE_POOL=200`、用户历史 500 条行为下，**P99 ≤ 200ms**（`test_api` 加基准测试，或用 `scripts/` 下的压测脚本产出报告）。
- NF-2：`recommend.py::feed` 必须移除 `user_tag_profile` / `user_creator_affinity` 的 N+1 查询（改为一次 `IN (...)` 批量取视频）。
- NF-3：`db.py::item_similarity` 必须支持批量 `IN (...)` 查询（当前按 `video_ids` 循环发 SQL）。
- NF-4：多路召回**允许**串行（MVP 库规模下可接受），但必须记录 `recall_ms` 分阶段耗时（可观测性前置）。

### 4.2 并发与写入

| 项 | 现状 | 本 PRD 要求 |
|---|---|---|
| 连接模型 | `ThreadingHTTPServer`，每连接一线程，**无上限** | NF-5：`MAX_CONCURRENT_CONNS`（默认 200），超限返回 `503 server_busy` 而非无限创建线程 |
| 写并发 | SQLite `WAL` + 进程内单写锁（`db.py::_write_lock`） | NF-6：**保持不变**（MVP 零运维优先），但必须**显式登记**为已知限制（§六）并给出迁移触发条件 |
| 读并发 | 线程级连接（`threading.local`），无锁 | ✅ 保持 |
| 埋点写入 | 同步写（`add_engagement` 内联） | NF-7：`/api/impressions` 批量写 + 单事务；不得每条一次事务 |
| 上传磁盘 | 流式写临时文件 → `shutil.move` 到分桶目录 | ✅ 保持（同文件系统内 `move` 为 rename，O(1)） |

### 4.3 依赖与可运行性

| 项 | 要求 | 现状 |
|---|---|---|
| 第三方 Python 依赖 | **零**（目标环境无可用 pip 包） | ✅ 已验证（纯标准库） |
| 外部二进制 | `ffmpeg`/`ffprobe` 可选但**生产环境必需** | ⚠️ 见 FR-1.1.a（fail-open 须修） |
| 冷启动可运行性 | `git clone && python3 run.py` 即起 | ✅ 保持 |

### 4.4 可测试性

| 项 | 要求 | 现状 |
|---|---|---|
| HTTP 与业务解耦 | `Application` 可脱离 HTTP 单测 | ✅ 已实现（`app.py::Application`） |
| 回归规模 | **不得低于 86 项**，且新增需求必须带测试 | ✅ 基线 86；本次要求 **≥ 140 项**（见 §九 各里程碑） |
| 测试不得只测「形状」 | 必须断言**行为发生**（如探索位真的被注入），而非字段存在 | ❌ **G1 即反例**：`is_exploration` 恒 false 却无测试失败 |
| 可复现性 | `seed` 参数保证 feed 可复现 | ✅ 已实现 |

### 4.5 可解释性与可观测性

| 项 | 要求 | 现状 |
|---|---|---|
| 推荐可归因 | 每条 feed item 带 `reason` + `features` + `recall_routes` + `weight_version` | ✅ 已实现 |
| 上传失败可理解 | 具名错误码 100% + 用户可见文案 | ⚠️ 错误码已有，**文案表缺失**（FR-1.3.e） |
| 结构化日志 | 关键事件 JSON 化，便于采集 | ⚠️ 当前 `log_message` 默认静默（`SVP_HTTP_LOG` 开关） |
| 指标 | NF-8：必须暴露 `GET /api/admin/metrics`（管理员鉴权）返回：`feed_p99_ms`、`recall_ms`、`exploration_slot_rate`、`rate_limited_total`、`moderation_pending_age_p99`、`upload_failure_rate`、`exposure_p10`、`creator_gini` | **需新增** |
| 告警 | NF-9：`creator_gini > 0.6`、`举报率 > 0.5%`、`upload_failure_rate > 5%`、`moderation_pending_age_p99 > 30min`、`rate_limited_total 突增` 必须触发告警 | **需新增** |

**NF-8 的重要性**：这 8 个指标**恰好是 S1–S8 与三个 Out-of-scope 复查触发条件的全部取数来源**。没有它，本 PRD 的成功判据全部不可验证（PRO-5 R5「度量基础设施缺失使策略无法被验证」）。

### 4.6 容量与存储（MVP 假设，须标注为待校准）

| 项 | 假设值 | 依据 |
|---|---|---|
| 单条视频平均体积 | 8 MB | 720p / 60s / H.264 经验值〔待校准〕 |
| 内容池规模（阶段 2 末） | 30,000 条 | PRO-5 §4.2 广告门槛 |
| 媒体存储需求 | 30,000 × 8MB ≈ **240 GB** | 本地磁盘承载不了 → 上线前必须对象存储（**已知限制**） |
| 曝光表增速 | 10万 DAU × 40 条/人·日 ≈ **400 万行/日** | → SQLite 不可承受；必须采样或按日分区（**已知限制 + 迁移触发条件**） |
| 曝光表保留策略 | 明细 **90 天**，聚合计数永久 | 与 A1/W2_CRR 的 24h/7d 窗口一致 |

**结论（必须写进 §六）**：`FeedImpression` 明细表在 10 万 DAU 量级下需要 PostgreSQL/分区表，SQLite 只能支撑 MVP 的灰度规模（≤ 5,000 DAU）。

---

## 五、验收标准（Given / When / Then）`[PRD-§5 语义保持并强化]`

> 编号规则：`AC-U-*` = FR-1 上传；`AC-F-*` = FR-2 推荐流；`AC-S-*` = FR-3 最小支撑；`AC-A-*` = FR-4 鉴权与限流。
> 「类型」列：**回归** = 现有 86 项中已有覆盖；**新增** = 本 PRD 要求新增的测试；**性能** = 门禁测试。
> §十 Gap 表逐条反查到这里，保证「每条 FR 都有可测试验收条件」。

### 5.1 FR-1 视频上传

| 编号 | Given | When | Then | 类型 |
|---|---|---|---|---|
| AC-U-01 | 已注册创作者 + 合法 mp4（6s / 360×640） | `POST /api/videos`（multipart） | `201`；`duration_ms/width/height` 由服务端 ffprobe 得出；`status='published'`；`moderation_status` 按模式取值 | 回归 |
| AC-U-02 | 同上 | 连续上传**同一文件两次** | 第二次 `409 duplicate_video`，报文含**原 `video_id`**；且**客户端据此判定为成功**（FR-1.3.c：不得展示为错误） | 回归+新增 |
| AC-U-03 | 200 秒视频 | 上传 | `400 duration_too_long` | 回归 |
| AC-U-04 | 非视频文件（.txt 伪装 .mp4） | 上传 | `400 unprobeable_media` 或 `400 unsupported_mime`；**响应含用户可见文案**（FR-1.3.e） | 回归+新增 |
| AC-U-05 | 扩展名 `.avi` | 上传 | `400 unsupported_extension` | 回归 |
| AC-U-06 | `caption="3分钟深夜食堂 #美食 #家常菜"` | 上传 | `tags == ["美食","家常菜"]`（规范化、去重、≤8） | 回归 |
| AC-U-07 | 上传在传输中中断（客户端超时） | 客户端按 FR-1.3.d 白名单重试同一文件 | 最终**只存在 1 条视频记录**；创作者**未看到任何错误提示**（409 被判定为成功） | 新增 |
| AC-U-08 | 全新创作者 | 3 步内（创建账号 → 上传 → 看到成功） | 成功；无引导条件下完成率可测（对应 S5） | 新增 |
| AC-U-09 | 创作者上传时 `visibility="private"` | ①作者 `GET /api/videos/{id}` ②他人 `GET /api/videos/{id}` ③任何人在 `GET /api/videos` 中查看 | ① `200` ② `403 video_private` ③**不出现** | 新增 |
| AC-U-10 | `MODERATION_MODE=async`，`KeywordBlockHook` 命中禁用词 | 上传 | `202 video_pending_review`；`moderation_status='pending'`；**不出现在推荐流与全站列表**；`GET /api/videos/{id}/file` 对非作者 `403` | 新增 |
| AC-U-11 | 已过审视频（`approved`） | 作者 `PATCH /api/videos/{id}` 修改 `caption` | `moderation_status` **重置为 `pending`**，并再次离开公开推荐流（FR-1.5.h） | 新增 |
| AC-U-12 | 已发布视频（24h 内） | `GET /api/videos/{id}/exposure` | 返回真实 `exposures`（来自 `FeedImpression`），**不得写死或夸大**（PRO-5 §6.1） | 新增 |
| AC-U-13 | `SVP_ENV=prod` 且 `ffprobe` 不在 PATH | 上传合法 mp4 | `503 probe_unavailable`，**不得**入库（FR-1.1.a fail-closed）；**且** `SVP_ENV=dev` 下同一场景降级放行并打 `media_probe_degraded` 日志 | 新增 |
| AC-U-14 | 上传体 > 200MB | 上传 | `413 payload_too_large`，且**在读取体之前**由 `Content-Length` 判定（不落盘） | 回归 |
| AC-U-15 | `title` 为 101 个码点 | 上传 | `400 title_too_long`（不得静默截断） | 新增 |

### 5.2 FR-2 推荐流

| 编号 | Given | When | Then | 类型 |
|---|---|---|---|---|
| AC-F-01 | 新用户（0 条行为）+ 库内 ≥ 10 条视频 | `GET /api/feed?user_id&size=10` | `200`；`cold_start=true`；`size=10`；每条含 `reason` | 回归 |
| AC-F-02 | 合规视频库（含 `private`/`pending`/`hidden` 各 1 条） | 任意用户拉 feed | 三类视频**均不出现**（FR-1.5.e） | 新增 |
| AC-F-03 | 库内 3 条视频、用户请求 `size=10` | 拉 feed | 返回 3 条（不因配额饿死候选池） | 回归 |
| AC-F-04 | 同一 `seed` | 连续两次 `GET /api/feed?...&seed=42` | 两次 `items[].video_id` **完全一致** | 回归 |
| AC-F-05 | 用户点赞 1 条「美食」视频 | 再拉 feed | 首位命中「美食」标签（`aff > 0`） | 回归 |
| AC-F-06 | 同一创作者发布 5 条视频 | 拉 `size=10` 的 feed | 该创作者**最多 2 条**；若因上限凑不满则放宽补位（长度仍 = min(size, 可召回数)） | 回归 |
| AC-F-07 | 用户 5 天前 `view` 过视频 V | 拉 feed | V **不出现**（7 天窗口） | 回归 |
| AC-F-07b | 用户 8 天前 `view` 过视频 V，且未 dislike | 拉 feed | V **可以**出现（窗口外） | 新增 |
| AC-F-08 | 非冷启动用户，候选池中存在「曝光 < 全站 P30」且**不在 top-size** 的候选；`seed` 命中探索分支 | 拉 feed | 结果中**恰好 1 条** `is_exploration=true`，且其索引 **≥ 3**；`FeedImpression.is_exploration=1` 同步落库 | **新增（修复 G1）** |
| AC-F-08b | 同上但候选池中**无**合格探索候选（全部已在 top-size 或全部高曝光） | 拉 feed | **不注入**探索位（`is_exploration=true` 计数 = 0），且 feed 长度不受影响 | **新增** |
| AC-F-08c | 1000 次非冷启动请求，`seed` 遍历 | 统计 | `exploration_slot_rate` ∈ **[0.07, 0.13]**（ε=0.10 的置信区间） | 新增 |
| AC-F-09 | 库内 50 条视频、用户请求 `size=10` | 依次请求第 1/2/3… 页（携带上一页返回的 `cursor`） | ①每页返回 10 条（末页不足）②**跨页无重复 `video_id`** ③末页 `cursor=null` 且 `has_more=false` ④合计覆盖全部 50 条 | **新增** |
| AC-F-09b | 上一页返回的 `cursor` | 120 秒后携带该 `cursor` 请求 | `409 cursor_expired` | 新增 |
| AC-F-09c | 客户端的**看过但未点赞**视频（仅有 `exposure` 无 `engagement`） | 翻到下一页 | 该视频**不重复出现**（去重依据切到曝光，FR-2.3.e） | **新增** |
| AC-F-10 | 用户对 feed 中第 2 条点「不感兴趣」 | ①同一 `session_id` 继续翻页 ②次日重新拉 feed | ①该 `video_id` 不再出现 ②**仍然不出现**（永久排除） | **新增（G1 P0）** |
| AC-F-11 | 用户对视频 V 举报 `reason_code="spam"` | ①本人拉 feed ②`reason_code` 改为非法值 | ①V **可以**继续出现（举报 ≠ 不感兴趣）② `400 invalid_report_reason` | 新增 |
| AC-F-11b | 5 个不同用户举报同一视频 V | 举报满 5 次后 | V `status='hidden'`，并从全站列表与 feed 消失；同时进入人工复审队列 | 新增 |
| AC-F-12 | 任意一次 feed 响应 | 检查每条 item | 均含 `reason`（非空）与 5 个 `features` 键；`weight_version` 与 `config.RANK_WEIGHTS` 一致 | 回归 |
| AC-F-13 | `RecommendEngine(db, weights={aff:0,pop:1,fresh:0,social:0,qual:0})` | 拉 feed | 排序与纯 `Pop` 降序一致（权重可配置） | 回归 |
| AC-F-14 | feed item 结构 | 检查字段 | 含 `playback_url`/`width`/`height`/`created_at`/`visibility`/`moderation_status`；`reason` **不含**权重系数与风控规则文本（FR-2.6.e） | 新增 |
| AC-F-15 | 冷启动用户（历史行为 < 3） | 拉 `size=10` | 满足 `docs/03 §6.1` 槽位约束：≥3 条来自全局热度 top、≥3 条分属不同垂类、≥2 条为长尾高互动（曝光 < P30 且 `Qual` ≥ P70）（FR-2.7.b） | 新增 |
| AC-F-16 | 新视频（发布 1h，0 曝光，`Qual_prior ≥ 0.3`，`approved`+`public`） | 全站并发拉 200 次 feed | 该视频获得 **≥ 50** 次曝光（`FeedImpression.is_visible=1`）；且单条 feed 中该类视频 ≤ 1 条 | **新增（S1 机制）** |
| AC-F-17 | 同一创作者同时上传 3 条新视频（均未达保底） | 拉 feed | 同一时刻**只有 1 条**处于保底投放（准入条件 ④） | 新增 |
| AC-F-18 | 10 个新创作者的视频曝光量分布 | 24h 后计算 | **P10 ≥ 50** 且 **Gini ≤ 0.6**（S1/S2，端到端） | **新增（数据验收）** |
| AC-F-19 | `Qual_prior < 0.3` 的低质新视频 | 拉 feed | **不进入** R6 保底路由（防低质借保底注入，PRO-5 R4） | 新增 |

### 5.3 FR-3 最小支撑

| 编号 | Given | When | Then | 类型 |
|---|---|---|---|---|
| AC-S-01 | 无 | `POST /api/users {handle, display, interest_tags:[a,b,c], source}` | `201`，响应含 `id/handle/display/created_at`（**字段不变**）+ `token`（仅本次返回）；`interest_tags` 落库 | 新增 |
| AC-S-02 | 已注册 handle | 再次 `POST /api/users` 同 handle | `409 handle_taken` | 回归 |
| AC-S-03 | `handle="a"`（太短）或含非法字符 | 创建 | `400 invalid_handle` | 回归 |
| AC-S-04 | 用户 token | `GET /api/users/{id}` | `200`，**不返回** `token` 原文（只存 `sha256`） | 新增 |
| AC-S-05 | 已有 token 的用户 | `POST /api/sessions {handle}` | `200`，含 `{token, user_id, expires_at, auth_level:"dev"}`；`auth_level` 必须显式为 `dev` 以警示非生产级身份 | 新增 |
| AC-S-06 | 已注册用户 | `GET /api/videos/{id}` | `200`，含 `playback_url`/`title`/`visibility`/`moderation_status`/`author`/`viewer_state`；**不含** `storage_path`；`sha256` 仅作者可见 | 新增 |
| AC-S-07 | 非管理员 token | `POST /api/admin/rebuild-cf` | `403 admin_required`（当前为**无鉴权**，AC 必须由该用例钉住） | **新增** |
| AC-S-07b | 管理员 token | `POST /api/admin/rebuild-cf` | `200 {ok:true, item_sim_pairs:N}`，且 `item_sim` 由共现余弦重建 | 新增 |
| AC-S-08 | 用户已对视频 V 点赞 | 再次 `POST /api/engagements {kind:"like", video_id:V}` | `200 {already:true}`；`video_stats.likes` **不变**（幂等） | **新增（修 F-12）** |
| AC-S-09 | 用户已点赞 V（`likes=1`） | `DELETE /api/engagements?user_id&video_id=V&kind=like` | `200`；`likes=0`；再次取消**不使 `likes` 为负** | 新增 |
| AC-S-10 | 用户 A 上报 `kind="exposure"` 且 `visible_ms=1200, is_visible=true, position=3` | 检查 `feed_impressions` | 新增行，`source='client'`，`is_visible=1`，`visible_ms=1200`；`video_stats.exposures` +1 | 新增 |
| AC-S-10b | 用户上报 `is_visible=false` 或 `visible_ms=300` | 检查 | 记录行但 `is_visible` 表意正确；**不计入曝光口径**（`video_stats.exposures` 不变） | 新增 |
| AC-S-11 | 用户进入 feed / 离开 feed | 上报 `session_start` / `session_exit`（含 `dwell_ms`） | 事件落库；同一会话 `session_start` **幂等** | 新增 |
| AC-S-12 | 批量埋点 `POST /api/impressions`（一个数组 30 条） | 调用 | `200`；30 行**单事务**写入；单次调用耗时 **≤ 50ms**（NF-7） | 新增 |
| AC-S-13 | 2 个用户各自重复点赞同一视频 3 次 | `POST /api/admin/recount` | `video_stats.likes` 由 `interactions` 重算 = **2**（与快路径计数一致） | 新增 |
| AC-S-14 | 全站列表含 120 条视频 | `GET /api/videos?size=50` | 返回 ≤ 50 条 + `cursor`/`has_more`；**禁止**全量返回 | 新增 |

### 5.4 FR-4 鉴权与限流

| 编号 | Given | When | Then | 类型 |
|---|---|---|---|---|
| AC-A-01 | 无 `Authorization` 头 | `POST /api/videos` | `401 unauthenticated`；**且必须在读取请求体之前返回** | **新增** |
| AC-A-02 | 有效用户 token（user A） | `POST /api/videos` 携带 `creator_id = user B` | `403 identity_mismatch`（不得以 B 的身份上传） | **新增** |
| AC-A-03 | 已撤销/过期 token | 任意鉴权请求 | `401 token_invalid` / `401 token_expired` | 新增 |
| AC-A-04 | 未鉴权 | `GET /api/health` / `GET /api/videos/{public_id}` | `200`（公开读免鉴权，但**仍受限流**） | 新增 |
| AC-A-05 | 一个用户 token | 1 分钟内第 6 次 `POST /api/videos` | `429 rate_limited`，含 `Retry-After` 与三个 `X-RateLimit-*` 头；**且在第 6 次请求读体前就拒绝** | **新增** |
| AC-A-06 | iOS（`Origin: https://evil.example`） | 跨域请求 | 响应**不含** `Access-Control-Allow-Origin: *`；仅当 `Origin ∈ SVP_CORS_ORIGINS` 时回显该 Origin（FR-4.1.e） | **新增** |
| AC-A-07 | 同一 IP | 1 小时内第 6 次 `POST /api/users` | `429 rate_limited`（防批量注册） | 新增 |
| AC-A-08 | 并发 300 个连接 | 同时发起 | 第 201 个及之后返回 `503 server_busy`；服务**不崩溃**、不 OOM（NF-5） | **新增** |
| AC-A-09 | 任意错误响应 / 日志 | 检查输出 | **不含** token 明文（脱敏为 `***`）（FR-4.1.f） | 新增 |
| AC-A-10 | `unlisted` 视频 | ①他人 `GET /api/videos/{id}/file` ②他人 `GET /api/videos` | ①`200`（持链接可播）②不出现（§3.1.5 矩阵） | 新增 |

### 5.5 性能与回归门禁

| 编号 | Given | When | Then | 类型 |
|---|---|---|---|---|
| AC-P-01 | 用户历史行为 500 条，内容库 1,000 条 | 1000 次 `GET /api/feed` | **P99 ≤ 200ms**（NF-1） | 性能 |
| AC-P-02 | 同 AC-P-01 | 检查 SQL 调用次数 | `user_tag_profile` 的取视频调用**不随行为数线性增长**（批量 `IN`，NF-2） | 性能 |
| AC-R-01 | 本 PRD 全部实现落地 | `make test` | **≥ 140 项全部通过**，且**原有 86 项语义不得被削弱**（允许因幂等修复而调整断言，须在提交信息中说明） | 回归 |

---

## 六、已知限制与后续迭代 `[PRD-§六 语义保持]`

### 6.1 上线阻塞项（P0，不做则不得上线）

| # | 事项 | 状态 | 说明 | 对应验收 |
|---|---|---|---|---|
| 1 | **API 鉴权 + 限流** | ❌ 未实现 | MVP 假设内网；上线前必须补齐，否则 `like/skip` 可被脚本刷量，一切效果实验结论不可信 | AC-A-01~10 |
| 2 | **`exposure` 曝光埋点 + `FeedImpression`** | ❌ 未实现 | **S1/S2 与北极星 W2_CRR 的唯一测量基础**。缺此则「首发 24h 曝光 P10 ≥ 50」「Gini ≤ 0.6」**不可计算** | AC-S-10/10b、AC-F-18 |
| 3 | **负反馈 `dislike`/`report`** | ❌ 未实现 | PRO-4 唯一 P0 硬缺口 G1；观众侧无出口 | AC-F-10/11/11b |
| 4 | **审核钩子 + 状态机** | ❌ 未实现 | 当前上传即公开；举报率护栏（< 0.5%）无前置手段 | AC-U-10/11、AC-F-02 |
| 5 | **可见性 + 访问控制** | ❌ 未实现 | `videos.status` 列存在但无写路径；媒体流对任何持 id 者开放 | AC-U-09、AC-A-10、AC-S-06 |
| 6 | **管理端点鉴权** | ❌ 未实现 | `POST /api/admin/rebuild-cf` 无鉴权 = 可被任意触发的全表重建（拒绝服务面） | AC-S-07 |
| 7 | **ffprobe fail-closed** | ⚠️ 客户端失效即绕过全部内容校验 | `media.py:326-328` + `377` 的组合使时长/分辨率校验可被整体跳过 | AC-U-13 |
| 8 | **互动幂等与取消** | ❌ 非幂等 | 重复点赞永久虚高计数且无校对手段 → `Pop`/`Qual` 失真 | AC-S-08/09/13 |

### 6.2 已知限制（P1/P2，登记而不在本 MVP 解决）

| 优先级 | 事项 | 说明 | 迁移/复查触发条件 |
|---|---|---|---|
| P1 | **推荐权重未经真实数据校准** | 当前 `0.45/0.20/0.15/0.10/0.10` 为行业经验初值；`REF_COMPLETION_RATE=0.55`、`REF_LIKE_RATE=0.12` 同 | 必须有真实日志后做离线网格搜索；**不得**凭直觉调 |
| P1 | **存储引擎天花板** | SQLite 单写锁；`FeedImpression` 在 10 万 DAU 下 ≈ 400 万行/日，SQLite 不可承受 | DAU > 5,000 或写入失败率上升 → 迁 PostgreSQL（`FeedImpression` 按日分区） |
| P1 | **媒体存储为本地磁盘** | 30,000 条 × 8MB ≈ 240GB；无对象存储、无 CDN | 上线前必须对象存储 + CDN；触发条件：内容池 > 5,000 条 |
| P1 | **标签依赖文案 `#话题` 抽取** | `_TAG_RE` 覆盖率有限；无标签视频只能靠 `fallback`，会拉高 `fallback` 路由占比 | 引入视频理解自动打标；触发条件：无标签视频占比 > 30% |
| P1 | **限流为单实例进程内实现** | 多实例部署时令牌桶不共享 | 水平扩展时迁 Redis |
| P1 | **鉴权为开发级（`auth_level: "dev"`）** | 无密码/验证码/第三方登录；`POST /api/sessions` 仅凭 `handle` 即可取 token | 灰度前必须替换为真实身份（短信/OAuth） |
| P1 | **护栏告警未实现** | Gini/举报率/跳过率可算但无阈值告警与自动回滚 | NF-9 |
| P2 | **多目标排序缺失** | 单目标（加权和）会诱发标题党，需融合完播/互动/关注多目标 | NG5 复查触发（A8 验证通过） |
| P2 | **实时特征缺失** | 全部为请求时计算（`Fresh`/`Pop` 每次现算）；热点场景需预计算与缓存 | AC-P-01 不达标时 |
| P2 | **无人工审核后台 UI** | 仅审核钩子 + 状态机 + 复审队列（数据层） | 审核量 > 500 条/日 |
| P2 | **评论仅计数无正文** | `comment` 事件只累加 `video_stats.comments` | 内容密度达标后 |

### 6.3 后续迭代顺序（与 §九 里程碑一致，此处仅列「不在本次范围」的下一批）

1. `dislike` 数据驱动的离线模型评估（把负反馈用于排序特征，需数据量 > 10 万条）
2. 对象存储 + CDN 迁移
3. PostgreSQL 迁移 + `FeedImpression` 分区
4. 创作者数据看板（完整版）
5. 搜索 / 话题聚合页（垂类密度达标后）

---

## 七、数据模型

### 7.1 实体关系总览

```
   ┌──────────┐ 1        N ┌──────────┐ N      1 ┌──────────────┐
   │  User    │────────────▶│  Video   │◀─────────│  FeedImpression│
   │ (账号)   │             │ (内容)   │          │  (曝光/展现)  │
   └────┬─────┘             └────┬─────┘          └──────┬───────┘
        │ 1                      │ 1                     │ N
        │                        │                       │
        │ N                      │ N                     │ 1
   ┌────▼────────────────────────▼──────┐         ┌──────▼──────┐
   │        Interaction (互动事件)       │         │   Session   │
   │  view/complete/like/unlike/share/  │◀────────│  (会话)     │
   │  skip/dislike/report/comment/      │   N   1 └─────────────┘
   │  follow/unfollow/session_*        │
   └────┬───────────────────┬───────────┘
        │ N                 │ N
   ┌────▼──────┐    ┌───────▼────────┐   ┌──────────────┐  ┌────────────┐
   │ UserToken │    │  VideoStats    │   │ ItemSim      │  │ UserSuppr. │
   │ (令牌)    │    │ (反规范化计数) │   │ (item-item)  │  │ (永久排除) │
   └───────────┘    └────────────────┘   └──────────────┘  └────────────┘
```

**命名裁定（重要，避免与 86 项回归测试冲突）**：
- 逻辑实体名 **`Interaction`**（本单描述要求），**物理表名保留 `engagements`**。理由：`db.py`/`tests/` 已在 86 项测试中固化 `engagements` 与 `add_engagement`；改表名是纯收益为零的破坏性变更。**裁定：逻辑名与物理名分离，在本文档显式登记映射**（`Interaction` ≡ 表 `engagements`）。
- 若未来迁移 PostgreSQL，可在迁移期一次性改名并同步测试，届时本裁定失效。

### 7.2 既有实体（`User` / `Video` / `Interaction`）—— 现状 DDL 与本 PRD 的字段增量

**7.2.1 `users`（User）**

| 字段 | 类型 | 约束 | 现状 | 本 PRD 变更 |
|---|---|---|---|---|
| `id` | TEXT | PK | ✅ 存在（uuid4 hex） | 不变 |
| `handle` | TEXT | NOT NULL UNIQUE | ✅ 存在 | 不变 |
| `display` | TEXT | NOT NULL DEFAULT '' | ✅ 存在 | 不变 |
| `created_at` | REAL | NOT NULL | ✅ 存在（epoch 秒，浮点） | 不变 |
| `interest_tags` | TEXT | NOT NULL DEFAULT '[]' | ❌ | **新增**（JSON 数组，注册期 3 选，A2 ground truth） |
| `source` | TEXT | NOT NULL DEFAULT '' | ❌ | **新增**（注册来源，冷启动归因） |
| `status` | TEXT | NOT NULL DEFAULT 'active' | ❌ | **新增**（`active` / `banned`；封禁用户不得上传与互动） |

**7.2.2 `videos`（Video）**

| 字段 | 类型 | 约束 | 现状 | 本 PRD 变更 |
|---|---|---|---|---|
| `id` | TEXT | PK | ✅ | 不变 |
| `creator_id` | TEXT | NOT NULL REFERENCES users(id) ON DELETE CASCADE | ✅ | 不变 |
| `caption` | TEXT | NOT NULL DEFAULT '' | ✅ | 不变（≤500 码点，改为显式校验） |
| `tags` | TEXT | NOT NULL DEFAULT '[]'（JSON 数组） | ✅ | 不变（≤8） |
| `duration_ms` | INTEGER | NOT NULL DEFAULT 0 | ✅ | 不变（ffprobe 真值） |
| `width` / `height` | INTEGER | NOT NULL DEFAULT 0 | ✅ | 不变 |
| `size_bytes` | INTEGER | NOT NULL DEFAULT 0 | ✅ | 不变 |
| `sha256` | TEXT | NOT NULL DEFAULT '' | ✅ | 不变（仅作者可见） |
| `storage_path` | TEXT | NOT NULL DEFAULT '' | ✅ | **不再对普通读接口返回** |
| `status` | TEXT | NOT NULL DEFAULT 'published' | ⚠️ 列存在但**从未被写入非 published** | **补写路径**：`published` / `hidden` / `removed` |
| `created_at` | REAL | NOT NULL | ✅ | 不变 |
| `title` | TEXT | NOT NULL DEFAULT '' | ❌ | **新增**（≤100 码点；空则回退 `caption` 前 30 码点） |
| `visibility` | TEXT | NOT NULL DEFAULT 'public' | ❌ | **新增**（`public` / `unlisted` / `private`） |
| `moderation_status` | TEXT | NOT NULL DEFAULT 'approved' | ❌ | **新增**（`pending` / `approved` / `rejected`） |
| `moderated_at` | REAL | DEFAULT NULL | ❌ | **新增** |
| `quality_prior` | REAL | NOT NULL DEFAULT 0 | ❌ | **新增**（新视频冷启动的 `Qual_prior`，见 §3.3.4 准入条件 ⑤） |
| `report_count` | INTEGER | NOT NULL DEFAULT 0 | ❌ | **新增**（去重举报用户数，FR-1.5.f 阈值判定，避免每次聚合扫描） |

**7.2.3 `engagements`（逻辑实体 `Interaction`）**

| 字段 | 类型 | 约束 | 现状 | 本 PRD 变更 |
|---|---|---|---|---|
| `id` | INTEGER | PK AUTOINCREMENT | ✅ | 不变 |
| `user_id` | TEXT | NOT NULL | ✅ | 不变 |
| `video_id` | TEXT | NOT NULL | ✅ | 不变 |
| `kind` | TEXT | NOT NULL | ✅（7 类） | **扩展至 14 类**（见 §3.4.4 事件字典） |
| `watch_ms` | INTEGER | NOT NULL DEFAULT 0 | ✅ | 不变（`session_exit` 复用为 `dwell_ms`） |
| `created_at` | REAL | NOT NULL | ✅ | 不变 |
| `session_id` | TEXT | DEFAULT '' | ❌ | **新增**（会话级指标分母；`dislike` 会话抑制必需） |
| `position` | INTEGER | DEFAULT -1 | ❌ | **新增**（feed 内位置，位置偏差分析） |
| `reason_code` | TEXT | DEFAULT '' | ❌ | **新增**（仅 `report` 使用） |
| `idempotency_key` | TEXT | DEFAULT '' | ❌ | **新增**（客户端幂等键） |

**新增约束（FR-3.3.a，关键）**：

```sql
-- 可切换型互动必须唯一：like / dislike / report / follow / unfollow / session_start
CREATE UNIQUE INDEX IF NOT EXISTS uq_eng_toggle
  ON engagements(user_id, video_id, kind)
  WHERE kind IN ('like','dislike','report','follow','unfollow','session_start');
```

> 说明：`view`/`complete`/`share`/`skip`/`comment`/`exposure` **允许重复**，故不入此部分唯一索引。`report` 入内意味着「同一用户对同一视频只计一次举报」，与 FR-1.5.f 的「**去重**用户举报数」口径一致。

### 7.3 新增实体：`FeedImpression`（曝光/展现）

> **本表是 S1/S2 与北极星 W2_CRR 的唯一取数来源**（PRO-5 §6.4-6）。没有它，「首发 24h 曝光 P10 ≥ 50」在数学上不可计算。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `user_id` | TEXT | NOT NULL | 观众 |
| `video_id` | TEXT | NOT NULL | 被展现的视频 |
| `session_id` | TEXT | NOT NULL DEFAULT '' | feed 会话；**翻页去重与 `dislike` 会话抑制的键** |
| `request_id` | TEXT | NOT NULL DEFAULT '' | 单次 feed 请求标识（同一请求的 items 共享） |
| `position` | INTEGER | NOT NULL DEFAULT -1 | 在 feed 中的槽位（0 起） |
| `score` | REAL | NOT NULL DEFAULT 0 | 展现时的打分（用于位置偏差与离线评估） |
| `recall_routes` | TEXT | NOT NULL DEFAULT '[]' | JSON 数组（归因） |
| `is_exploration` | INTEGER | NOT NULL DEFAULT 0 | 是否探索位（**0/1**） |
| `weight_version` | TEXT | NOT NULL DEFAULT '' | JSON（权重快照，A/B 归因） |
| `source` | TEXT | NOT NULL | `server`（投放即记） / `client`（客户端确认可见） |
| `served_at` | REAL | NOT NULL | 服务端返回时刻 |
| `client_reported_at` | REAL | DEFAULT NULL | 客户端上报时刻 |
| `visible_ms` | INTEGER | NOT NULL DEFAULT 0 | 可见时长（毫秒） |
| `is_visible` | INTEGER | NOT NULL DEFAULT 0 | 是否达到可见阈值（**0/1**） |
| `cold_start` | INTEGER | NOT NULL DEFAULT 0 | 该次 feed 是否为冷启动用户 |

**索引（必须）**：

```sql
CREATE INDEX IF NOT EXISTS idx_imp_video_served  ON feed_impressions(video_id, served_at);
CREATE INDEX IF NOT EXISTS idx_imp_user_served   ON feed_impressions(user_id, served_at DESC);
CREATE INDEX IF NOT EXISTS idx_imp_session       ON feed_impressions(session_id, position);
CREATE UNIQUE INDEX IF NOT EXISTS uq_imp_client  ON feed_impressions(session_id, video_id, source)
  WHERE source='client';   -- 客户端重复上报幂等
```

**曝光口径（冻结，见 §十一 C2）**：

```
exposure(V) := COUNT(DISTINCT user_id) FROM feed_impressions
               WHERE video_id=V AND is_visible=1 AND source='client'
served(V)   := COUNT(DISTINCT user_id) FROM feed_impressions
               WHERE video_id=V AND source='server'
```

> `video_stats.exposures` 为 `exposure()` 的反规范化计数（`is_visible=1` 时 +1），用于 S1/S2 的实时计算；`/api/admin/recount` 可重算校对。

### 7.4 新增支撑实体

**7.4.1 `user_tokens`（会话令牌，FR-3.1）**

| 字段 | 类型 | 说明 |
|---|---|---|
| `token_hash` | TEXT PK | `sha256(token)`，**不存明文** |
| `user_id` | TEXT NOT NULL | |
| `created_at` / `expires_at` / `last_seen_at` | REAL NOT NULL | 30 天有效期 |
| `revoked` | INTEGER NOT NULL DEFAULT 0 | |
| `auth_level` | TEXT NOT NULL DEFAULT 'dev' | MVP 固定 `dev`（诚实标注） |

**7.4.2 `user_video_suppression`（永久排除，FR-2.5.b）**

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_id` | TEXT NOT NULL | |
| `video_id` | TEXT NOT NULL | |
| `reason` | TEXT NOT NULL | `dislike` / `admin` |
| `created_at` | REAL NOT NULL | |
| PK | `(user_id, video_id)` | |

**7.4.3 `video_stats` 增量列**

```sql
ALTER TABLE video_stats ADD COLUMN exposures INTEGER NOT NULL DEFAULT 0;
ALTER TABLE video_stats ADD COLUMN dislikes  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE video_stats ADD COLUMN reports   INTEGER NOT NULL DEFAULT 0;
```

### 7.5 迁移脚本（必须幂等，且须在 `db.py::_init_schema` 内以 `ALTER TABLE` + `try/except` 兼容旧库）

```sql
-- users
ALTER TABLE users ADD COLUMN interest_tags TEXT NOT NULL DEFAULT '[]';
ALTER TABLE users ADD COLUMN source        TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN status        TEXT NOT NULL DEFAULT 'active';
-- videos
ALTER TABLE videos ADD COLUMN title             TEXT    NOT NULL DEFAULT '';
ALTER TABLE videos ADD COLUMN visibility        TEXT    NOT NULL DEFAULT 'public';
ALTER TABLE videos ADD COLUMN moderation_status TEXT    NOT NULL DEFAULT 'approved';
ALTER TABLE videos ADD COLUMN moderated_at      REAL    DEFAULT NULL;
ALTER TABLE videos ADD COLUMN quality_prior     REAL    NOT NULL DEFAULT 0;
ALTER TABLE videos ADD COLUMN report_count      INTEGER NOT NULL DEFAULT 0;
-- engagements（Interaction）
ALTER TABLE engagements ADD COLUMN session_id      TEXT    NOT NULL DEFAULT '';
ALTER TABLE engagements ADD COLUMN position        INTEGER NOT NULL DEFAULT -1;
ALTER TABLE engagements ADD COLUMN reason_code     TEXT    NOT NULL DEFAULT '';
ALTER TABLE engagements ADD COLUMN idempotency_key TEXT    NOT NULL DEFAULT '';
-- video_stats
ALTER TABLE video_stats ADD COLUMN exposures INTEGER NOT NULL DEFAULT 0;
ALTER TABLE video_stats ADD COLUMN dislikes  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE video_stats ADD COLUMN reports   INTEGER NOT NULL DEFAULT 0;
-- 新表见 §7.3 / §7.4
```

**迁移纪律**：
- `_init_schema` 中的 `SCHEMA` 字符串更新为**新库完整 DDL**；`ALTER TABLE` 增量单独走一个 `_migrate()`，用 `PRAGMA table_info(table)` 判存在再 `ALTER`（SQLite 不支持 `ADD COLUMN IF NOT EXISTS`）。
- 迁移必须**可重复执行**（幂等）；新增列一律给 `NOT NULL DEFAULT`，避免全表重写与旧行 NULL。
- **`moderation_status` 旧行默认 `approved`**：这是刻意的向后兼容选择（避免既有 86 项测试与演示数据全量变 `pending`），但**必须**在部署说明中标注「历史数据未经过审核」（诚实登记）。

### 7.6 字段口径与信源（防歧义）

| 字段 | 口径 | 反规范化来源 |
|---|---|---|
| `video_stats.views` | **去重用户播放数**（`kind='view'` 的 distinct `user_id`） | 见 §十一 C2 |
| `video_stats.completes` | 完成播放事件数（允许同人多条） | `engagements` |
| `video_stats.likes` | **去重用户点赞数**（受 `uq_eng_toggle` 保证） | `engagements` |
| `video_stats.shares` / `skips` / `comments` | 事件计数（允许同人多条） | `engagements` |
| `video_stats.exposures` | **去重用户可见曝光数**（`is_visible=1 AND source='client'`） | `feed_impressions` |
| `video_stats.dislikes` | 去重用户数（受唯一索引保证） | `engagements` |
| `video_stats.reports` | 去重用户数（受唯一索引保证） | `engagements` |
| `videos.report_count` | = `video_stats.reports`（冗余，用于阈值判定） | `engagements` |

**⚠️ 现状与口径不一致（必须修）**：当前 `db.py::add_engagement` 对 `view` 也是**事件计数**（重复 `view` 即 +1），而 `max_engagement_total()` 的 SQL 直接用 `views + 2*completes + 3*likes + 5*shares`。**在无鉴权、无限流的当前实现下，脚本可把 `views` 刷到任意大，直接污染 `Pop` 与 `Qual`**。修复路径：`uq_eng_toggle` 保证 `like`；`view` 的去重需在计数层改为 `COUNT(DISTINCT user_id)`（`recount` 端点 + 写入路径同步）。

---

## 八、API 契约

> 目标：**工程可无歧义实现**。所有端点给出方法、路径、鉴权、请求、响应、错误码。未标「新增」者为现状已有（含需改造处）。

### 8.1 通用约定

| 项 | 约定 |
|---|---|
| Base URL | `http://127.0.0.1:8080`（`SVP_HOST/SVP_PORT` 可覆盖） |
| 编码 | 请求/响应体一律 UTF-8；JSON 接口 `Content-Type: application/json`；上传为 `multipart/form-data` |
| 鉴权 | `Authorization: Bearer <token>`；管理端点 `Authorization: Bearer <SVP_ADMIN_TOKEN>` |
| 错误信封 | 统一 `{"error": {"code": "...", "message": "..."}}`（现状已实现，**保持不变**） |
| 限流响应头 | 所有响应携带 `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset`；超限额外带 `Retry-After` |
| 请求追踪 | 客户端可传 `X-Request-Id`（≤64 字符）；服务端回显，缺失时自生成；用于日志关联与 `FeedImpression.request_id` |
| 幂等键 | 上传可传 `Idempotency-Key`（≤64 字符）；同键重放返回首次结果（`200` + `upload_idempotent_replay`） |
| 时间 | 所有时间为 epoch 秒（浮点，UTC），字段名以 `_at` 结尾 |
| 分页 | 一律游标制：请求 `cursor`/`size`，响应 `cursor`/`has_more`；**禁止** `offset` |
| 空值 | 未设置的可选文本字段返回 `""`（不返回 `null`），数值型返回 `0`（与现状一致，避免客户端判空分支） |
| CORS | 仅回显 `SVP_CORS_ORIGINS` 白名单内的 `Origin`；`Allow-Headers` 含 `Authorization,Content-Type,X-Request-Id,Idempotency-Key` |

### 8.2 端点总览

| # | 方法 | 路径 | 鉴权 | 状态 | 说明 |
|---|---|---|---|---|---|
| 1 | GET | `/api/health` | 无 | ✅ 保持 | 探活（不限流） |
| 2 | POST | `/api/users` | 无 | ⚠️ **改造** | 建号；**新增返回 `token`**、`interest_tags`、`source` |
| 3 | GET | `/api/users/{user_id}` | 用户 | ⚠️ 改造 | **不返回 token 原文** |
| 4 | POST | `/api/sessions` | 无 | **新增** | 换取 token（`auth_level:"dev"`） |
| 5 | POST | `/api/sessions/revoke` | 用户 | **新增** | 撤销当前 token |
| 6 | POST | `/api/videos` | **用户** | ⚠️ **改造** | 上传；新增 `title`/`visibility`；审核分支；限流前置 |
| 7 | GET | `/api/videos` | 无 | ⚠️ **改造** | 分页 + 过滤非公开 |
| 8 | GET | `/api/videos/{video_id}` | 视可见性 | ⚠️ **改造** | 补 `playback_url`/`author`/`viewer_state`；移除 `storage_path` |
| 9 | PATCH | `/api/videos/{video_id}` | **用户（作者）** | **新增** | 改 `title`/`caption`/`tags`/`visibility`（触发重新审核） |
| 10 | DELETE | `/api/videos/{video_id}` | **用户（作者）** | **新增** | 软删除 → `status='removed'` |
| 11 | GET | `/api/videos/{video_id}/file` | 视可见性 | ⚠️ **改造** | Range 已实现；**补访问控制** |
| 12 | GET | `/api/videos/{video_id}/exposure` | 用户（作者） | **新增** | 创作者曝光反馈位（真实数字） |
| 13 | POST | `/api/engagements` | **用户** | ⚠️ **改造** | kind 扩至 14 类；幂等 |
| 14 | DELETE | `/api/engagements` | **用户** | **新增** | 取消点赞 / 取消关注 |
| 15 | POST | `/api/impressions` | **用户** | **新增** | 批量曝光上报（客户端确认可见） |
| 16 | POST | `/api/follows` | **用户** | ⚠️ 改造 | 加鉴权（`follower_id` 必须 = token 身份） |
| 17 | GET | `/api/feed` | **用户** | ⚠️ **改造** | 游标分页 + `playback_url` + 负反馈过滤 |
| 18 | POST | `/api/internal/moderation/callback` | **管理员** | **新增** | 审核结果回写 |
| 19 | POST | `/api/admin/rebuild-cf` | **管理员** | ⚠️ **改造** | 补鉴权 |
| 20 | POST | `/api/admin/recount` | **管理员** | **新增** | 反规范化计数重算校对 |
| 21 | GET | `/api/admin/metrics` | **管理员** | **新增** | 8 项关键指标（NF-8） |
| 22 | GET | `/` | 无 | ✅ 保持 | 演示列表页 |

### 8.3 关键端点契约

#### 8.3.1 `POST /api/users`（改造）

```
POST /api/users
Content-Type: application/json

{
  "handle": "foodie_lin",
  "display": "林小厨",
  "interest_tags": ["美食", "家常菜", "探店"],   // 可选；给定时必须恰好 3 个且在垂类白名单内
  "source": "seed_invite"                        // 可选
}
```
→ `201`
```json
{
  "id": "b3c1f0a9e2d4475ab8c6...",
  "handle": "foodie_lin",
  "display": "林小厨",
  "created_at": 1758624000.123,
  "interest_tags": ["美食", "家常菜", "探店"],
  "source": "seed_invite",
  "token": "5Gq3...仅本次返回...",     // 新增；服务端只存 sha256
  "auth_level": "dev"                   // 新增；显式声明非生产级身份
}
```
错误：`400 invalid_handle` · `400 invalid_interest_tags`（**新增**：数量 ≠ 3 或不在白名单） · `409 handle_taken` · `429 rate_limited`

#### 8.3.2 `POST /api/sessions`（新增）

```
POST /api/sessions
Content-Type: application/json

{ "handle": "foodie_lin" }
```
→ `200`
```json
{ "token": "5Gq3...", "user_id": "b3c1...", "expires_at": 1761216000.0, "auth_level": "dev" }
```
错误：`404 user_not_found` · `403 user_banned`（**新增**） · `429 rate_limited`

> **诚实标注**：本端点在 MVP 仅凭 `handle` 即签发 token，**不是生产级身份认证**（无密码/验证码）。必须在客户端与文档中标注；灰度前替换（§6.2）。

#### 8.3.3 `POST /api/videos`（改造）

```
POST /api/videos
Authorization: Bearer <token>
Content-Type: multipart/form-data; boundary=----SVP
Idempotency-Key: 7f0a...        # 可选

------SVP
Content-Disposition: form-data; name="caption"

3分钟搞定深夜食堂 #美食 #家常菜
------SVP
Content-Disposition: form-data; name="title"

深夜食堂：3分钟出餐
------SVP
Content-Disposition: form-data; name="visibility"

public
------SVP
Content-Disposition: form-data; name="file"; filename="clip.mp4"
Content-Type: video/mp4

<二进制>
------SVP--
```

`creator_id` **不再作为表单字段**（改由 token 推导）；若仍传入且与 token 身份不符 → `403 identity_mismatch`；相同则接受（向后兼容）。

→ `201`（直接发布，`MODERATION_MODE=off` 或钩子批准）
```json
{
  "id": "9f2a...", "creator_id": "b3c1...",
  "title": "深夜食堂：3分钟出餐",
  "caption": "3分钟搞定深夜食堂 #美食 #家常菜",
  "tags": ["美食", "家常菜"],
  "duration_ms": 6000, "width": 360, "height": 640,
  "size_bytes": 48210,
  "visibility": "public", "moderation_status": "approved",
  "status": "published", "created_at": 1758624000.5,
  "playback_url": "/api/videos/9f2a.../file",
  "stats": { "views": 0, "completes": 0, "likes": 0, "shares": 0, "exposures": 0 }
}
```

→ `202`（待审核，`MODERATION_MODE=async` 或同步钩子超时）
```json
{ "id": "9f2a...", "moderation_status": "pending", "visibility": "public",
  "status": "published", "message": "已提交，审核通过后自动发布" }
```

→ `200`（`Idempotency-Key` 命中已完成上传）
```json
{ "code": "upload_idempotent_replay", "id": "9f2a...", "moderation_status": "approved" }
```

→ `409`（sha256 去重，**必须回传原 `video_id`**，客户端按 FR-1.3.c 判定为成功）
```json
{ "error": { "code": "duplicate_video", "message": "视频已存在（去重命中 video_id=9f2a...）" },
  "video_id": "9f2a...",
  "idempotent_success": true }
```

> 兼容性提示：现状的 409 报文把 `video_id` **嵌在 `message` 文本里**。本 PRD 要求在**顶层新增 `video_id` 与 `idempotent_success` 字段**，同时**保留原 message 文本**，使既有客户端不破坏、新客户端可结构化解析。

错误：见 §8.4（上传相关全部错误码）。

#### 8.3.4 `PATCH /api/videos/{video_id}`（新增）

```
PATCH /api/videos/9f2a...
Authorization: Bearer <token>
Content-Type: application/json

{ "title": "新标题", "caption": "新文案 #美食", "tags": ["美食"], "visibility": "unlisted" }
```
→ `200`
```json
{ "id": "9f2a...", "title": "新标题", "visibility": "unlisted",
  "moderation_status": "pending",   // 内容变更必须重新审核（FR-1.5.h）
  "updated_fields": ["title","caption","tags","visibility"] }
```
错误：`403 not_video_owner`（**新增**） · `400 title_too_long`/`caption_too_long` · `400 invalid_visibility` · `404 video_not_found`

> **仅改 `visibility` 是否触发重审？** 裁定：**不触发**（可见性不是内容）。仅 `caption`/`title`/`tags` 变更触发 `pending`。

#### 8.3.5 `GET /api/videos/{video_id}`（改造）

```
GET /api/videos/9f2a...
Authorization: Bearer <token>   # 可选；private/unlisted 判定需要
```
→ `200`
```json
{
  "id": "9f2a...", "title": "深夜食堂：3分钟出餐",
  "caption": "3分钟搞定深夜食堂 #美食 #家常菜", "tags": ["美食","家常菜"],
  "duration_ms": 6000, "width": 360, "height": 640, "size_bytes": 48210,
  "visibility": "public", "moderation_status": "approved", "status": "published",
  "created_at": 1758624000.5,
  "playback_url": "/api/videos/9f2a.../file",
  "author": { "id": "b3c1...", "handle": "foodie_lin", "display": "林小厨" },
  "viewer_state": { "liked": true, "disliked": false, "following_author": false },
  "stats": { "views": 12, "completes": 7, "likes": 3, "shares": 1, "comments": 0, "skips": 2, "exposures": 120 }
}
```
**字段移除**：`storage_path`（任何调用者）、`sha256`（非作者）。作者请求时额外返回 `sha256` 与 `quality_prior`（调试用）。

错误：`403 video_private` · `404 video_not_found`（`hidden`/`removed`/`rejected` 对非作者**返回 404 而非 403**，避免泄露存在性）

#### 8.3.6 `GET /api/videos`（改造，分页）

```
GET /api/videos?size=20&cursor=<opaque>&author_id=<uuid>
```
→ `200`
```json
{ "videos": [ /* 同 8.3.5 的读模型 */ ], "cursor": "eyJ2IjoxLC4uLn0", "has_more": true }
```
**过滤（强制）**：`status='published' AND visibility='public' AND moderation_status='approved'`。`author_id` 给定时按作者过滤（作者本人可见自己的全部状态）。

#### 8.3.7 `GET /api/videos/{video_id}/file`（改造：补访问控制）

```
GET /api/videos/9f2a.../file
Range: bytes=0-99          # 可选
Authorization: Bearer <token>   # private 判定需要
```
→ `200` / `206`（含 `Content-Range: bytes 0-99/48210`）、`Accept-Ranges: bytes`

**访问控制（新增）**：
| 视频状态 | 作者 | 其他已登录 | 匿名 |
|---|---|---|---|
| `public` + `approved` | ✅ | ✅ | ✅ |
| `unlisted` + `approved` | ✅ | ✅ | ✅（持链接可播） |
| `private` | ✅ | ❌ `403 video_private` | ❌ `401` |
| `pending` / `rejected` | ✅ | ❌ `403 video_not_ready` | ❌ `401` |
| `hidden` / `removed` | ❌（作者亦不可播） | ❌ `404` | ❌ `404` |

#### 8.3.8 `POST /api/engagements`（改造）

```
POST /api/engagements
Authorization: Bearer <token>
Content-Type: application/json

{ "video_id": "9f2a...", "kind": "dislike", "session_id": "s-7f0a...", "position": 2 }
```
```json
// 另一种：举报
{ "video_id": "9f2a...", "kind": "report", "reason_code": "spam", "session_id": "s-7f0a..." }
// 另一种：播放
{ "video_id": "9f2a...", "kind": "view", "watch_ms": 4200, "session_id": "s-7f0a..." }
```

`kind` 全集（**14 类**）：`view` `complete` `like` `unlike` `share` `skip` `dislike` `report` `comment` `follow` `unfollow` `exposure` `session_start` `session_exit`

`user_id` **不再作为请求体字段**（由 token 推导；若传入且不符 → `403 identity_mismatch`）。

→ `201`
```json
{ "ok": true, "video_id": "9f2a...", "kind": "dislike", "already": false,
  "stats": { "views": 12, "completes": 7, "likes": 3, "shares": 1, "dislikes": 1 } }
```
→ `200`（幂等：`like`/`dislike`/`report`/`follow`/`unfollow`/`session_start` 重复上报）
```json
{ "ok": true, "video_id": "9f2a...", "kind": "like", "already": true, "stats": { "...": 0 } }
```
**副作用**：`kind='follow'` 自动建关注边（创作者 = 视频作者，现状保持）；`kind='dislike'` 写 `user_video_suppression`；`kind='report'` 递增 `videos.report_count` 并可能触发自动隐藏（FR-1.5.f）。

错误：`400 invalid_kind` · `400 invalid_report_reason` · `400 session_missing`（`dislike` 必需 `session_id`） · `403 video_not_visible`（**新增**：对不可见视频互动） · `429 rate_limited`

#### 8.3.9 `DELETE /api/engagements`（新增：取消）

```
DELETE /api/engagements?video_id=9f2a...&kind=like
Authorization: Bearer <token>
```
→ `200`
```json
{ "ok": true, "video_id": "9f2a...", "kind": "like", "removed": true,
  "stats": { "likes": 0 } }
```
可取消的 kind：`like`（→ 减少 `likes`，下限 0）、`follow`（→ 删除关注边，**需 `video_id`**，创作者取自视频作者）。
错误：`400 kind_not_revocable`（**新增**） · `404 engagement_not_found`

#### 8.3.10 `POST /api/impressions`（新增：批量曝光）

```
POST /api/impressions
Authorization: Bearer <token>
Content-Type: application/json

{
  "session_id": "s-7f0a...",
  "request_id": "r-3b2c...",
  "items": [
    { "video_id": "9f2a...", "position": 0, "visible_ms": 3200, "is_visible": true },
    { "video_id": "1a2b...", "position": 1, "visible_ms": 400,  "is_visible": false }
  ]
}
```
→ `200`
```json
{ "ok": true, "recorded": 2, "visible": 1 }
```
**约束**：`items` 长度 1~50（超限 `413` 或分片）；整批**单事务**写入；`(session_id, video_id, source='client')` 唯一（重复上报幂等，`uq_imp_client`）。
**口径**：仅 `is_visible=true AND visible_ms >= 1000` 才计入 `exposure()`（§7.3）。`is_visible` 由客户端判定（元素在视口内 ≥ 1s），服务端**不做**二次判定但**会**对 `visible_ms > 3600000`（1 小时）做上限裁剪（防伪造超长时长）。

#### 8.3.11 `GET /api/feed`（改造：游标分页 + 负反馈）

```
GET /api/feed?user_id=<uuid>&size=10&session_id=s-7f0a...&cursor=<opaque>&seed=42
Authorization: Bearer <token>
```
| 参数 | 必填 | 说明 |
|---|---|---|
| `user_id` | ✅ | 观众 UUID（必须 = token 身份，否则 `403 identity_mismatch`） |
| `size` | ❌ | 1~50，默认 10 |
| `session_id` | ❌ | 会话标识；**未提供时服务端生成并回传**。`dislike` 会话抑制与翻页去重的键 |
| `cursor` | ❌ | 上一页返回的游标（原样回传） |
| `seed` | ❌ | 随机种子，保证可复现（测试与 A/B 复现） |

→ `200`
```json
{
  "user_id": "b3c1...",
  "session_id": "s-7f0a...",
  "cold_start": false,
  "size": 10,
  "has_more": true,
  "cursor": "eyJ2IjoxLCJ0cyI6MTc1ODYyNDAwMC4xLCJyYW5rIjo5LCJ2aWRlbyI6IjlmMmEuLi4iLCJ3diI6eyJhZmYiOjAuNDV9LCJzaWQiOiJzLTdmMGEiLCJmcCI6ImFiYzEyMyJ9",
  "weight_version": { "aff": 0.45, "pop": 0.2, "fresh": 0.15, "social": 0.1, "qual": 0.1 },
  "request_id": "r-3b2c...",
  "items": [
    {
      "video_id": "9f2a...",
      "creator_id": "77de...",
      "title": "深夜食堂：3分钟出餐",
      "caption": "空气炸锅版脆皮五花肉 #美食 #懒人食谱",
      "tags": ["美食","懒人食谱"],
      "duration_ms": 6000, "width": 360, "height": 640,
      "created_at": 1758624000.5,
      "visibility": "public", "moderation_status": "approved",
      "playback_url": "/api/videos/9f2a.../file",
      "score": 0.482137,
      "features": { "aff": 0.7123, "pop": 0.331, "fresh": 0.8601, "social": 0.0, "qual": 0.4512 },
      "recall_routes": ["cf","tag"],
      "reason": "标签兴趣匹配主导（召回路径：标签匹配/协同过滤）",
      "is_exploration": false,
      "position": 0
    }
  ]
}
```

**行为契约**：
1. 返回前**服务端即写** `FeedImpression(source='server')`（投放口径 `served`）。
2. 过滤条件（强制）：`published` + `approved` + `public` + 不在 7 天已互动集合 + 不在 `user_video_suppression` + 不在本 `session_id` 已曝光集合。
3. `cursor=null` 且 `has_more=false` 表示无更多。
4. `seed` 给定时：同一 `(user_id, session_id, cursor, seed)` 结果**可复现**。

**错误**：`400 missing_user_id` · `400 invalid_size` · `404 user_not_found` · `403 identity_mismatch` · `400 cursor_invalid` · `409 cursor_expired` · `429 rate_limited`

#### 8.3.12 `POST /api/internal/moderation/callback`（新增）

```
POST /api/internal/moderation/callback
Authorization: Bearer <SVP_ADMIN_TOKEN>
Content-Type: application/json

{ "video_id": "9f2a...", "decision": "rejected", "reason_code": "keyword_hit" }
```
→ `200`
```json
{ "ok": true, "video_id": "9f2a...", "moderation_status": "rejected", "moderated_at": 1758624100.0 }
```
错误：`403 admin_required` · `404 video_not_found` · `400 invalid_decision` · `409 invalid_transition`（**新增**：已 `rejected` 不可改回 `pending`，只能由管理员复核动作）

#### 8.3.13 `GET /api/admin/metrics`（新增，NF-8）

```
GET /api/admin/metrics?since=1758600000&until=1758624000
Authorization: Bearer <SVP_ADMIN_TOKEN>
```
→ `200`
```json
{
  "window": { "since": 1758600000, "until": 1758624000 },
  "upload_failure_rate": 0.012,
  "feed_p99_ms": 118.4,
  "recall_ms": { "cf": 8.1, "follow": 3.2, "fresh": 5.5, "tag": 4.4, "fallback": 1.1 },
  "exploration_slot_rate": 0.098,
  "rate_limited_total": { "POST /api/videos": 12, "GET /api/feed": 340 },
  "moderation_pending_age_p99": 96.0,
  "exposure_p10": 58,
  "creator_gini": 0.47,
  "report_rate": 0.0018,
  "skip_rate": 0.31,
  "repeat_recommend_rate_7d": 0.0
}
```
> 这 8 项 + 3 项护栏即 S1–S8 与三个 Out-of-scope 复查触发条件的**全部取数来源**。

### 8.4 错误码总表（含用户可见文案）

| 错误码 | 状态 | 含义 | 用户可见文案 | 状态 |
|---|---|---|---|---|
| `invalid_handle` | 400 | handle 不符合 `[A-Za-z0-9_\-中文]{2,32}` | 用户名需 2~32 位字母、数字、下划线或中文 | 既有 |
| `invalid_interest_tags` | 400 | 兴趣标签数量 ≠ 3 或不在白名单 | 请选择 3 个兴趣方向 | **新增** |
| `handle_taken` | 409 | handle 已存在 | 该用户名已被占用 | 既有 |
| `user_not_found` | 404 | 用户不存在 | 用户不存在 | 既有 |
| `user_banned` | 403 | 账号被封禁 | 账号已被限制使用 | **新增** |
| `missing_creator` | 400 | 缺少 `creator_id`（保留兼容） | 上传缺少创作者信息 | 既有 |
| `missing_file` | 400 | 缺少文件字段 | 请选择要上传的视频文件 | 既有 |
| `bad_file_field` | 400 | 文件字段名非 `file`/`video` | 上传字段名不正确 | 既有 |
| `bad_content_type` | 400 | 非 multipart/form-data | 请求格式不正确 | 既有 |
| `missing_boundary` | 400 | multipart 缺 boundary | 请求格式不正确 | 既有 |
| `unsupported_extension` | 400 | 扩展名不在白名单 | 仅支持 mp4 / mov / webm / mkv | 既有 |
| `unsupported_mime` | 400 | MIME 不在白名单 | 视频格式不受支持 | 既有 |
| `payload_too_large` | 413 | 体/文件 > 200MB | 视频超过 200MB 上限，请压缩后重试 | 既有 |
| `empty_file` / `empty_body` | 400 | 文件或请求体为空 | 视频文件为空 | 既有 |
| `duration_too_long` / `duration_too_short` | 400 | 时长不在 1s~180s | 视频时长需在 1 秒到 3 分钟之间 | 既有 |
| `resolution_too_low` | 400 | 高度 < 240px | 视频分辨率过低 | 既有 |
| `unprobeable_media` | 400 | ffprobe 无法解析 | 视频文件损坏或不是有效视频 | 既有 |
| `probe_unavailable` | 503 | 生产环境 ffprobe 不可用 | 系统暂时无法校验视频，请稍后重试 | **新增** |
| `duplicate_video` | 409 | sha256 重复（含原 `video_id`） | 该视频已上传成功 | 既有（**新增**结构化字段） |
| `upload_idempotent_replay` | 200 | 幂等键命中 | 视频已上传成功 | **新增** |
| `title_too_long` | 400 | `title` > 100 码点 | 标题最多 100 个字 | **新增** |
| `caption_too_long` | 400 | `caption` > 500 码点 | 文案最多 500 个字 | **新增** |
| `invalid_visibility` | 400 | 可见性取值非法 | 可见性取值不合法 | **新增** |
| `video_pending_review` | 202 | 待审核（非错误） | 已提交，审核通过后自动发布 | **新增** |
| `video_rejected` | 422 | 审核拒绝 | 视频未通过审核 | **新增** |
| `video_not_ready` | 403 | 视频未就绪（待审/被拒）播放 | 视频暂不可播放 | **新增** |
| `video_not_visible` | 403 | 对不可见视频互动 | 该视频当前不可见 | **新增** |
| `not_video_owner` | 403 | 非作者修改/删除 | 你无权修改该视频 | **新增** |
| `video_private` | 403 | 访问 private 视频且非作者 | 该视频为私密视频 | **新增** |
| `video_not_found` | 404 | 视频不存在（或不可见时同样返回 404） | 视频不存在或已下架 | 既有 |
| `media_missing` | 404 | 磁盘文件缺失 | 视频文件不可用 | 既有 |
| `invalid_kind` | 400 | 互动类型非法 | 操作类型不正确 | 既有 |
| `kind_not_revocable` | 400 | 该 kind 不可取消 | 该操作不支持撤销 | **新增** |
| `invalid_report_reason` | 400 | 举报原因非法 | 请选择举报原因 | **新增** |
| `session_missing` | 400 | `dislike` 缺 `session_id` | 页面状态已失效，请刷新后重试 | **新增** |
| `engagement_not_found` | 404 | 要取消的互动不存在 | 该操作尚未发生 | **新增** |
| `self_follow` | 400 | 不能关注自己 | 不能关注自己 | 既有 |
| `missing_user_id` | 400 | feed 缺 `user_id` | 请求缺少用户信息 | 既有 |
| `invalid_size` | 400 | `size` 非整数 | 分页参数不合法 | 既有 |
| `cursor_invalid` | 400 | 游标解析失败/版本不符 | 页面状态已失效，请刷新 | **新增** |
| `cursor_expired` | 409 | 游标超 120s | 页面停留过久，已为你刷新内容 | **新增** |
| `unauthenticated` | 401 | 缺少 Authorization | 请先登录 | **新增** |
| `token_invalid` | 401 | 令牌无效/已撤销 | 登录状态已失效，请重新登录 | **新增** |
| `token_expired` | 401 | 令牌超 30 天 | 登录已过期，请重新登录 | **新增** |
| `identity_mismatch` | 403 | 请求身份 ≠ token 身份 | 操作身份不一致 | **新增** |
| `admin_required` | 403 | 非管理员 | 无管理权限 | **新增** |
| `rate_limited` | 429 | 超令牌桶速率 | 操作过于频繁，请稍后再试 | **新增** |
| `server_busy` | 503 | 并发连接上限 | 服务繁忙，请稍后重试 | **新增** |
| `invalid_json` / `invalid_json_shape` | 400 | JSON 非法 | 请求数据格式不正确 | 既有 |
| `invalid_decision` / `invalid_transition` | 400/409 | 审核决策非法/状态迁移非法 | —（内部接口，不对用户展示） | **新增** |
| `not_found` | 404 | 路由不存在 | 接口不存在 | 既有 |
| `internal_error` | 500 | 服务内部错误 | 服务出错了，请稍后重试 | 既有 |

### 8.5 兼容性与弃用策略

| 变更 | 策略 |
|---|---|
| `creator_id` / `user_id` 改为由 token 推导 | **双轨期**：传入且与 token 一致 → 接受；不一致 → `403`；**完全移除**表单字段的版本不得早于本 PRD 上线后 2 周 |
| `POST /api/users` 新增 `token` 字段 | 纯新增，向后兼容 |
| `GET /api/videos/{id}` 移除 `storage_path` | **破坏性**：已登记为「需改造」；客户端不得依赖该字段（现状仅演示页 `/` 使用 `list_all_videos`，**不受影响**） |
| `409 duplicate_video` 新增顶层 `video_id` | 纯新增，且 `message` 原文保留 |
| `GET /api/videos` 由全量改为分页 | **破坏性**：返回结构不变（仍是 `{"videos":[...]}`），默认 `size=20`；依赖"一次拿全"的脚本须改（演示页 `/` 需同步改为分页） |
| 管理端点加鉴权 | **破坏性**：需 `SVP_ADMIN_TOKEN` 环境变量；部署脚本必须同步 |

---

## 九、任务拆分（用户故事 → 实现顺序 → 里程碑）

### 9.1 用户故事到任务的映射

每条 US 拆为可交付的开发任务（`T-*`），并绑定验收编号与所属里程碑。

| US | 用户故事（摘要） | 开发任务 | 里程碑 | 验收 |
|---|---|---|---|---|
| US-C1 | 3 步内完成发布 | T-3.1 表单精简（`creator_id` 由 token 推导） | M3 | AC-U-08 |
| US-C2 | `#话题` 自动成标签 | （已实现，无任务） | — | AC-U-06 |
| US-C3 | 上传后立刻看到曝光 | T-1.3 `exposures` 计数 + T-6.3 反馈位 | M1/M6 | AC-U-12 |
| US-C4 | 重复上传明确告知 | T-3.4 409 结构化（顶层 `video_id`） | M3 | AC-U-02 |
| US-C5 | 失败原因可理解 | T-3.5 错误码→文案表（§8.4） | M3 | AC-U-04 |
| US-C6 | 设置可见性 | T-3.2 `visibility` 列与校验 + T-3.3 `PATCH` 端点 | M3 | AC-U-09 |
| US-C7 | 审核通过前不公开推荐 | T-3.6 审核钩子 + 状态机 + 全通道过滤 | M3 | AC-U-10 |
| US-C8 | 重试不产生重复、不报错 | T-3.4 + T-3.7 `Idempotency-Key` | M3 | AC-U-07 |
| US-V1 | 打开就有按兴趣排序的流 | （已实现，无任务） | — | AC-F-01 |
| US-V2 | 不连续刷到同一人/同类 | （已实现 MMR + creator cap，无任务） | — | AC-F-06 |
| US-V3 | 7 天内已看不重复 | T-4.4 去重依据切到曝光 | M4 | AC-F-07/07b |
| US-V4 | 点赞后推荐流变化 | （已实现，无任务） | — | AC-F-05 |
| US-V5 | 偶尔刷到意外内容 | **T-4.3 探索位接线（修 G1 死代码）** | M4 | AC-F-08/08b/08c |
| US-V6 | 无限滚动 | T-4.1 游标分页 + T-4.2 会话曝光去重 | M4 | AC-F-09/09b/09c |
| US-V7 | 不感兴趣后立即消失且不再出现 | T-4.5 `dislike` + `user_video_suppression` | M4 | AC-F-10 |
| US-V8 | 举报被记录并纳入审核 | T-4.6 `report` + T-3.6 自动隐藏联动 | M4/M3 | AC-F-11/11b |
| US-O1 | 看到推荐理由 | （已实现，无任务） | — | AC-F-12 |
| US-O2 | 调权重不改代码 | （已实现，无任务） | — | AC-F-13 |
| US-O3 | 手工触发 CF 重建（限管理员） | T-2.5 管理端点鉴权 | M2 | AC-S-07/07b |
| （S1 机制） | 首发曝光 P10 ≥ 50 | T-4.7 R6 保底路由 + T-4.8 冷启动首屏配额 | M4 | AC-F-16/17/18/19 |
| （S3/S4） | 首刷命中 ≥ 60%、退出 < 40% | T-1.4 注册期兴趣标签 + T-4.8 | M1/M4 | AC-S-01、AC-F-15 |
| （R5 前置） | 鉴权 + 限流 | T-2.1 ~ T-2.6 | M2 | AC-A-01~10 |
| （测量基础） | 曝光/首刷/退出埋点 | T-1.1 ~ T-1.6 | M1 | AC-S-10/10b/11/12 |

### 9.2 实现顺序（拓扑序，箭头 = 必须先完成）

```
M0 口径与契约冻结
 │
 ├──▶ M1 测量基础设施（FeedImpression / 埋点 / 指标端点）
 │     │
 │     ├──▶ M2 鉴权与限流 ──┬──▶ M3 上传增强（可见性 / 审核 / 幂等 / fail-closed）
 │     │                    ├──▶ M4 推荐流增强（游标 / 负反馈 / 探索修 / R6 保底）
 │     │                    └──▶ M5 互动与计数一致性（幂等 / 取消 / recount）
 │     │
 │     └─────────────────────────▶ M6 Web UI 与上线就绪（依赖 M3+M4+M5 的接口全部冻结）
 │
 └──▶ （并行）docs/03 §3.1 召回配额口径修订 + README 现状更正
```

**为什么 M1 必须在 M2 之前**：`FeedImpression` 需要 `user_id` 与 `session_id`；若先做鉴权再做曝光表，会经历一次「身份来源变更」的重写。反之，先有曝光表再用 token 填充身份，是一次无返工的推进。

**为什么 M5 不是最后**：`uq_eng_toggle` 唯一索引是 `dislike`/`report` 幂等（FR-2.5.i）与 `like` 幂等（FR-3.3.a）的**共同依赖**。若 M4 先上 `dislike` 而无唯一索引，会引入脏数据，后续再补索引需要数据清洗。**故 M5 的索引与写路径必须先于 M4 的负反馈上线**（图中已体现 M5 与 M3/M4 并列，实际执行顺序为 M5 → M4）。

### 9.3 里程碑与退出判据

| 里程碑 | 目标 | 主要交付项 | 退出判据（可验证） | 测试目标 |
|---|---|---|---|---|
| **M0** 口径与契约冻结 | 消除歧义，防止返工 | ①本文 v2.0 被接受 ②`docs/03 §3.1` 配额口径修订（C1）③§8.4 错误码→文案表 ④`README` 现状表述更正（删除"ε-greedy 已实现"等不实描述） | ①+② 提交至 `PRO-1-pro-1`；③④ 有 diff 可查 | — |
| **M1** 测量基础设施 | 让 S1/S2/W2_CRR **成为可计算的量** | T-1.1 `feed_impressions` 建表+索引 ②T-1.2 `POST /api/impressions` ③T-1.3 `video_stats.exposures` ④T-1.4 注册期兴趣标签 ⑤T-1.5 `session_start`/`session_exit` ⑥T-1.6 `GET /api/admin/metrics`（含 `exposure_p10`/`creator_gini` 计算） | ①~⑥ 全部有单测；`metrics` 在 seed 场景返回**非零** `exploration_slot_rate` 之外的真实值；`exposure_p10`/`creator_gini` 数值与手算一致 | +18 |
| **M2** 鉴权与限流 | 关闭 R5 前置阻塞 | T-2.1 `user_tokens` 表 ②T-2.2 `POST /api/sessions`(+revoke) ③T-2.3 Bearer 中间层 + `identity_mismatch` ④T-2.4 令牌桶限流（含 `Retry-After`/`X-RateLimit-*`）⑤T-2.5 管理端点 `SVP_ADMIN_TOKEN` ⑥T-2.6 CORS 白名单 + 并发上限 | AC-A-01~10 全绿；**限流拒绝必须发生在读请求体之前**（AC-A-01/05 用「不读体即返回」的测试钉死） | +12 |
| **M3** 上传增强 | 关闭上传侧全部 P0 缺口 | T-3.1~T-3.7（见 9.1） | AC-U-01~15 全绿；`upload_failure_rate` 有可读数值（NG11 复查触发条件具备） | +14 |
| **M4** 推荐流增强 | 兑现 D1/D2/D3 + 修 G1 | T-4.1~T-4.8（见 9.1） | AC-F-01~19 全绿；`exploration_slot_rate ∈ [0.07,0.13]`；R6 保底在压力场景下使单条新视频获得 ≥ 50 次可见曝光 | +20 |
| **M5** 互动与计数一致性 | 消除计数可信度问题 | T-5.1 `uq_eng_toggle` 部分唯一索引 ②T-5.2 幂等 `like` ③T-5.3 `DELETE /api/engagements`(`unlike`/`unfollow`) ④T-5.4 `POST /api/admin/recount` ⑤T-5.5 `view` 去重口径落地 | AC-S-08/09/13 全绿；`recount` 结果与快路径计数**逐条一致** | +8 |
| **M6** Web UI 与上线就绪 | 让 A4 可用性测试可执行 | T-6.1 上传页（进度+失败文案+重试）②T-6.2 feed 页（无限滚动+负反馈入口）③T-6.3 创作者曝光反馈位 ④T-6.4 告警规则（NF-9）⑤T-6.5 部署说明（`SVP_ADMIN_TOKEN`/`SVP_ENV`/`SVP_CORS_ORIGINS`） | AC-U-08 可执行（无引导可用性测试）；AC-R-01 **≥ 140 项全绿** | +6 |

**测试总量核对**：86（基线）+ 18 + 12 + 14 + 20 + 8 + 6 = **164 项** ≥ 140 ✅

### 9.4 关键路径、并行与依赖风险

| 项 | 内容 |
|---|---|
| **关键路径** | M0 → M1 → M2 → M5 → M4 → M6（M3 与 M4 可并行，M5 必须先于 M4 的负反馈） |
| **可并行** | M3（上传侧）与 M4（推荐侧）在 M2 完成后无互相依赖；`docs/03` 口径修订与 README 更正可在 M0 起随时并行 |
| **依赖风险 1** | M4 的 R6 保底路由依赖 M1 的 `exposures`。若 M1 延后，**S1（P10 ≥ 50）无法验证**，M4 的保底机制将"无法自证有效"，禁止跳过 |
| **依赖风险 2** | M4 的 `dislike` 依赖 M5 的唯一索引；顺序颠倒会导致脏数据 |
| **依赖风险 3** | M6 的 UI 依赖 M3/M4/M5 的接口全部冻结；建议 M6 以「接口 mock」先行开发，接口冻结后联调，避免串行等待 |
| **明确不做的并行** | 不在 M2 完成前启动任何 A/B 实验（PRO-5 R5：无鉴权则 `like`/`skip` 可被脚本刷量，结论不可信） |

---

## 十、Gap 表（现有实现 vs 本 PRD）

> **判定口径**：**已实现** = 代码已具备且行为正确（须能指认文件与行号）；**需改造** = 代码存在但行为/契约不符或存在缺陷；**需新增** = 完全不存在。
> **覆盖范围**：`server/` 现有 5 个模块（`config.py` / `db.py` / `media.py` / `recommend.py` / `app.py`），另附补充块 6（`tests/` 等支撑文件）。

### 10.1 汇总计数

| 模块 | 行数 | 已实现 | 需改造 | 需新增 | 小计 |
|---|---|---|---|---|---|
| `config.py` | 81 | 5 | 3 | 8 | 16 |
| `db.py` | 378 | 10 | 9 | 9 | 28 |
| `media.py` | 434 | 8 | 1 | 4 | 13 |
| `recommend.py` | 453 | 5 | 7 | 5 | 17 |
| `app.py` | 425 | 3 | 12 | 13 | 28 |
| （补充）`tests/` · `run.py` · `docs/` · `README.md` | — | 0 | 6 | 4 | 10 |
| **合计** | 1,771 | **31** | **38** | **43** | **112** |

### 10.2 模块 A：`server/config.py`（81 行）

| # | 能力项 | 现状（证据） | 本 PRD 要求 | 判定 | 优先级 | 验收 |
|---|---|---|---|---|---|---|
| A1 | 排序权重 5 特征 | `RANK_WEIGHTS` L15-21（和 = 1.0） | §3.2.3 冻结公式，保持 | **已实现** | P0 | AC-F-12/13 |
| A2 | MMR / 创作者上限 / 时间窗 / 半衰期 | L24-29 | 保持 | **已实现** | P0 | AC-F-06 |
| A3 | 多路召回配额（百分比口径） | `RECALL_QUOTAS` L40-46 + `RECALL_BASE_DEPTH` L47 + `MIN_ROUTE_DEPTH` L48 | §3.2.2 **冻结为唯一口径**（C1 裁定）；新增 `newcomer` 配额 | **需改造** | P0 | AC-F-03 |
| A4 | 行为价值权重 | `ACTION_VALUE` L51-59（含 `skip=-2.0`） | 新增 `dislike=-3.0`、`unlike`（负向抵消）、`report`（不计画像） | **需改造** | P0 | AC-F-10 |
| A5 | 质量分参考基准 | `REF_COMPLETION_RATE` L62 / `REF_LIKE_RATE` L63 | 保持（标注〔待校准〕） | **已实现** | P1 | AC-F-12 |
| A6 | 上传限额与格式白名单 | `MAX_UPLOAD_BYTES` L68 / `MAX_DURATION_MS` L69 / `MIN_DURATION_MS` L70 / `ALLOWED_MIME` L71-73 / `ALLOWED_EXT` L74 | 保持 | **已实现** | P0 | AC-U-03/05/14 |
| A7 | 存储与 DB 路径 | `MEDIA_ROOT` L77 / `DB_PATH` L78（env 可覆盖） | 保持 | **已实现** | P0 | — |
| A8 | 冷启动判定阈值 | `COLD_START_MAX_ENGAGEMENTS` L81（=3） | 保持；新增 `EPSILON_COLD = 0.30` | **需改造** | P0 | AC-F-15 |
| A9 | 运行环境开关 | ❌ 无 | `SVP_ENV`（`dev`/`prod`，控制 ffprobe fail-closed） | **需新增** | P0 | AC-U-13 |
| A10 | 管理员凭据 | ❌ 无 | `SVP_ADMIN_TOKEN`（env 注入，禁止硬编码） | **需新增** | P0 | AC-S-07 |
| A11 | CORS 白名单 | ❌ 无（`app.py` 硬编码 `*`） | `SVP_CORS_ORIGINS` | **需新增** | P0 | AC-A-06 |
| A12 | 限流参数 | ❌ 无 | 每端点令牌桶速率 + `MAX_CONCURRENT_CONNS`（§3.5.3） | **需新增** | P0 | AC-A-05/08 |
| A13 | 审核参数 | ❌ 无 | `MODERATION_MODE` / `REPORT_AUTO_HIDE_THRESHOLD`(5) / `MODERATION_PENDING_ALERT_SEC`(1800) | **需新增** | P0 | AC-U-10、AC-F-11b |
| A14 | 新视频保底参数 | ❌ 无 | `EXPOSURE_FLOOR`(50) / `QUAL_FLOOR`(0.3) / `NEWCOMER_MAX_PER_CREATOR`(1) / `GINI_ALERT`(0.6) / `GINI_FORCE_EXPLORE`(0.7) | **需新增** | P0 | AC-F-16/17/19 |
| A15 | 分页/游标参数 | ❌ 无 | `CURSOR_TTL_SEC`(120) / `LIST_DEFAULT_SIZE`(20) / `IMPRESSION_BATCH_MAX`(50) | **需新增** | P0 | AC-F-09b、AC-S-12 |
| A16 | 兴趣标签白名单 | ❌ 无 | `INTEREST_TAXONOMY`（垂类白名单，供 `interest_tags` 校验与首屏分垂类配额） | **需新增** | P0 | AC-S-01、AC-F-15 |

### 10.3 模块 B：`server/db.py`（378 行）

| # | 能力项 | 现状（证据） | 本 PRD 要求 | 判定 | 优先级 | 验收 |
|---|---|---|---|---|---|---|
| B1 | `users` / `videos` 基础表与索引 | `SCHEMA` L16-85；`idx_videos_creator/created` L41-42 | 保持 | **已实现** | P0 | AC-U-01 |
| B2 | `engagements` 表与索引 | L44-53 | **补唯一索引** `uq_eng_toggle`（§7.2.3） | **需改造** | **P0** | AC-S-08、AC-F-10 |
| B3 | `follows` 主键幂等 | L55-60（PK + `INSERT OR IGNORE`） | 保持 | **已实现** | P1 | AC-S-09 |
| B4 | `video_stats` 反规范化计数 | L63-73 | 补 `exposures`/`dislikes`/`reports` 列 | **需改造** | P0 | AC-S-10 |
| B5 | `item_sim` 相似度缓存 | L76-84 | 保持 | **已实现** | P1 | AC-S-07b |
| B6 | 线程安全（WAL + 单写锁 + 线程连接） | `connect` L100-110；`_write_lock` L96；`execute` L123 | 保持；登记为已知限制 | **已实现** | P1 | NF-6 |
| B7 | `create_user` | L141 | 补 `interest_tags` / `source` / `status` 写入 | **需改造** | P0 | AC-S-01 |
| B8 | `create_video`（硬编码 `published`） | L176-185（`'published'` 字面量） | 补 `title`/`visibility`/`moderation_status`/`quality_prior` 参数；`status` 可写 | **需改造** | P0 | AC-U-09/10 |
| B9 | `get_video` / `list_all_videos` / `list_videos_by_creator` | L192-221（仅按 `status='published'` 过滤） | 过滤条件扩展为 `visibility` + `moderation_status`；列表支持分页 | **需改造** | P0 | AC-F-02、AC-S-14 |
| B10 | `hash_exists` 全站去重 | L223-225 | 保持；`video_id` 改为顶层结构化返回 | **已实现** | P0 | AC-U-02 |
| B11 | `add_engagement`（**非幂等**） | L230-262：无条件 `INSERT` + `likes = likes + 1` | 幂等化（`INSERT OR IGNORE` + 变化时才计数）；补 `session_id`/`position`/`reason_code` | **需改造** | **P0** | AC-S-08/13 |
| B12 | `following_ids` / `creator_second_hop` | L270、L358 | 保持 | **已实现** | P1 | AC-F-05 |
| B13 | `user_engagements` | L276-282 | 保持（注意 N+1，见 D10） | **已实现** | P1 | — |
| B14 | `user_seen_video_ids`（**仅基于 engagements**） | L284-291 | 去重依据切到 `feed_impressions`（会话级 + 7 天窗口） | **需改造** | **P0** | AC-F-07b/09c |
| B15 | `user_engagement_count` | L293-295 | 保持 | **已实现** | P0 | AC-F-01 |
| B16 | `max_engagement_total` | L297-301（`views+2*completes+3*likes+5*shares`） | 保持公式；但 `views` 口径须改为去重用户数（§7.6） | **需改造** | P0 | AC-S-13 |
| B17 | `rebuild_item_similarity` | L306-344 | 保持（注意全表 `DELETE`+重算需管理员鉴权，见 E13） | **已实现** | P1 | AC-S-07b |
| B18 | `item_similarity`（按 id 循环发 SQL） | L346-356 | 改批量 `IN (...)`（NF-3） | **需改造** | P1 | AC-P-02 |
| B19 | `_video_row_to_dict` | L369-378 | 保持；补新字段透出 | **已实现** | P0 | AC-S-06 |
| B20 | `feed_impressions` 表 | ❌ 不存在 | §7.3 全量 DDL + 4 索引 | **需新增** | **P0** | AC-S-10、AC-F-18 |
| B21 | `user_tokens` 表 | ❌ 不存在 | §7.4.1 | **需新增** | P0 | AC-S-05 |
| B22 | `user_video_suppression` 表 | ❌ 不存在 | §7.4.2 | **需新增** | P0 | AC-F-10 |
| B23 | `_migrate()` 幂等迁移 | ❌ 不存在 | §7.5（`PRAGMA table_info` 判存在再 `ALTER`） | **需新增** | P0 | AC-R-01 |
| B24 | 计数重算校对 | ❌ 不存在 | `recount_counters()`（供 `POST /api/admin/recount`） | **需新增** | P0 | AC-S-13 |
| B25 | 会话曝光查询 | ❌ 不存在 | `session_impressed_ids(session_id)`（翻页去重） | **需新增** | **P0** | AC-F-09c |
| B26 | 曝光统计（P10 / Gini） | ❌ 不存在 | `exposure_p10()` / `creator_gini()`（供 metrics） | **需新增** | **P0** | AC-F-18 |
| B27 | 审核状态写入 | ❌ 不存在 | `set_moderation(video_id, decision, reason_code)` | **需新增** | P0 | AC-U-10 |
| B28 | 举报计数与自动隐藏 | ❌ 不存在 | `bump_report(video_id)` → 阈值时 `status='hidden'` | **需新增** | P0 | AC-F-11b |

### 10.4 模块 C：`server/media.py`（434 行）

| # | 能力项 | 现状（证据） | 本 PRD 要求 | 判定 | 优先级 | 验收 |
|---|---|---|---|---|---|---|
| C1 | 流式 multipart 解析（≤64KB 驻留） | `parse_multipart` L253-314；`_iter_raw_parts` L141-221；`CHUNK_SIZE` L31 | 保持 | **已实现** | P0 | AC-U-01 |
| C2 | 显式长度限制读取（keep-alive 安全） | `LengthLimitedReader` L36-69 | 保持 | **已实现** | P0 | AC-U-14 |
| C3 | boundary 跨块与 CRLF 边界处理 | `_strip_trailing_crlf` L126-138；`_iter_raw_parts` 重叠区 | 保持 | **已实现** | P0 | AC-U-01 |
| C4 | 五重校验（扩展名/MIME/体积/时长/分辨率） | `validate_upload` L359-387 | 保持，**改为 fail-closed**（C5） | **已实现** | P0 | AC-U-03/05 |
| C5 | ffprobe 缺失时降级 | `probe_media` L320-321 `_NO_PROBE` + L326-328 早退；`validate_upload` L377 `if meta.get("available")` | 生产环境 `SVP_ENV=prod` 必须**拒绝**（`503 probe_unavailable`）；开发环境降级但打结构化日志 | **需改造** | **P0** | **AC-U-13** |
| C6 | ffprobe 真值探测 | `probe_media` L324-356（`-show_format -show_streams -select_streams v:0`） | 保持 | **已实现** | P0 | AC-U-01 |
| C7 | 分桶存储路径 | `storage_path_for` L393-397 | 保持 | **已实现** | P1 | — |
| C8 | 文件落盘 | `persist` L400-404（`shutil.move`） | 保持 | **已实现** | P0 | AC-U-01 |
| C9 | `#话题` 抽取与规范化 | `extract_tags` L417-434；`_TAG_RE` L32 | 保持（≤8）；登记覆盖率为已知限制 | **已实现** | P0 | AC-U-06 |
| C10 | `title` 校验 | ❌ 无（仅 `caption`） | ≤100 码点，空则回退 `caption` 前 30 码点 | **需新增** | P0 | AC-U-15 |
| C11 | `visibility` 校验 | ❌ 无 | 枚举 `public`/`unlisted`/`private` | **需新增** | P0 | AC-U-09 |
| C12 | 审核钩子 | ❌ 无（`grep 审核/moderation` 无结果） | `ModerationHook` 接口 + `AllowAllHook` + `KeywordBlockHook`（FR-1.5.c） | **需新增** | P0 | AC-U-10 |
| C13 | 可解码性/内容合规的扩展校验 | ❌ 无（无编码白名单、无音频轨检查、无文件头魔数校验） | MVP 仅记录 `codec`/`format_name` 到日志；**魔数校验**（`ftyp`/`EBML` 头）为 P1 | **需新增** | P1 | — |

### 10.5 模块 D：`server/recommend.py`（453 行）

| # | 能力项 | 现状（证据） | 本 PRD 要求 | 判定 | 优先级 | 验收 |
|---|---|---|---|---|---|---|
| D1 | 5 路召回 | `recall` L143-215 | 保持；**新增 R6 `newcomer`**（D14） | **已实现** | P0 | AC-F-01/03 |
| D2 | `tag` 与 `follow` 去重 | `_exclude_routed` L217-222 | 保持 | **已实现** | P1 | — |
| D3 | 线性加权打分 | `features` L239-269 / `score` L271-280；`_freshness` L227 / `_quality` L231 | 保持（公式冻结） | **已实现** | P0 | AC-F-12/13 |
| D4 | MMR 重排 | `rerank` L285-323（`λ=0.7`，Jaccard，creator cap 放宽补位） | 保持 | **已实现** | P0 | AC-F-06 |
| D5 | 用户标签画像 | `user_tag_profile` L115-128（`ACTION_VALUE` 加权，`v>0` 过滤） | **补 `dislike` 负权重行为断言**（FR-2.5.c 要求单测钉住"压制"语义） | **需改造** | P0 | AC-F-10 |
| D6 | 冷启动判定与兜底放大 | `feed` L343、L364-370 | 保持；**新增首屏槽位配额**（D15） | **需改造** | P0 | AC-F-15 |
| D7 | 多路融合（配额 × 基准深度） | `feed` L351-361 | 保持（C1 冻结口径） | **已实现** | P0 | AC-F-03 |
| D8 | 7 天已看过滤 | `feed` L340-342（**基于 `engagements`**） | 去重依据切到 `feed_impressions`（含"看过未互动"） | **需改造** | **P0** | AC-F-07b/09c |
| D9 | **ε-greedy 探索位** | `feed` L391-396 计算 `explore_slots`；**L419 硬编码 `is_exploration=False`；`explore_slots` 再未被引用** → **死代码** | **接线并真实注入**（FR-2.4.a~f）：1 条、索引 ≥ 3、低曝光分位选取、无合格候选则不注入、补 3 项行为测试 | **需改造** | **P1（优先于同层）** | **AC-F-08/08b/08c** |
| D10 | **N+1 查询** | `user_tag_profile` L120 对每条行为调 `db.get_video()`；`user_creator_affinity` L133 同；`item_similarity` 逐 id 发 SQL | 批量 `IN (...)`（NF-2/NF-3） | **需改造** | P1 | AC-P-02 |
| D11 | 推荐理由 `reason` | `_reason_for` L434-453 | 保持；**审查文案不泄露权重与风控**（FR-2.6.e） | **需改造** | P1 | AC-F-14 |
| D12 | feed item 字段 | `feed` L408-423（缺 `playback_url`/`width`/`height`/`created_at`/`visibility`/`moderation_status`） | 补全 | **需改造** | P0 | AC-F-14 |
| D13 | 游标分页与快照语义 | ❌ 不存在 | `cursor` 编解码 + `ts` 快照 + 120s TTL + 会话去重（FR-2.3） | **需新增** | **P0** | AC-F-09/09b/09c |
| D14 | R6 新视频保底路由 | ❌ 不存在 | §3.3.4（准入 5 条件 + 排序键 + 配额 + Gini 收敛） | **需新增** | **P0** | AC-F-16/17/18/19 |
| D15 | 冷启动首屏槽位配额 | ❌ 不存在（当前仅放大兜底 + 关探索） | `docs/03 §6.1` 的 3+3+2+2 槽位约束（FR-2.7.b） | **需新增** | P0 | AC-F-15 |
| D16 | `dislike` 过滤与创作者降权 | ❌ 不存在 | `user_video_suppression` 过滤 + 会话抑制 + `CREATOR_DISLIKE_PENALTY`（FR-2.5.a~d） | **需新增** | **P0** | AC-F-10 |
| D17 | 新品类扶持位与覆盖度联动 | ❌ 不存在（仅被动 MMR） | 每 20 槽位留 1 个给最低 20% 垂类；覆盖度 < 0.6 时 `ε` → 0.20（FR-2.7.e） | **需新增** | P1 | — |

### 10.6 模块 E：`server/app.py`（425 行）

| # | 能力项 | 现状（证据） | 本 PRD 要求 | 判定 | 优先级 | 验收 |
|---|---|---|---|---|---|---|
| E1 | 路由与 `Application` 解耦（可单测） | `Application` L36-157；`Handler` L176 | 保持 | **已实现** | P0 | AC-R-01 |
| E2 | 统一错误信封 + 具名错误码 | `ApiError` L160-165；`_send_error_json` L223-224 | 保持；**新增** §8.4 全量错误码与用户文案 | **需改造** | P0 | AC-U-04 |
| E3 | HTTP/1.1 keep-alive 与体排空 | `_drain_body` L182-209；`_body_consumed` | 保持 | **已实现** | P0 | AC-U-14 |
| E4 | `POST /api/users` | `create_user` L42-48 | 补 `token`/`interest_tags`/`source`/`auth_level` | **需改造** | P0 | AC-S-01 |
| E5 | `GET /api/users/{id}` | `get_user` L50-54 | **不返回 token 原文** | **需改造** | P0 | AC-S-04 |
| E6 | `POST /api/videos` | `upload_video` L57-95 | 补 `title`/`visibility`；审核分支（201/202）；`creator_id` 由 token 推导；限流前置；`Idempotency-Key` | **需改造** | P0 | AC-U-07/09/10 |
| E7 | `GET /api/videos/{id}` | `get_video` L97-101 | 补 `playback_url`/`author`/`viewer_state`；**移除 `storage_path`**；`sha256` 仅作者 | **需改造** | P0 | AC-S-06 |
| E8 | `POST /api/engagements` | `_KINDS` L104（7 类）；`add_engagement` L106-129 | kind 扩至 14 类；幂等返回 `already`；`dislike` 需 `session_id`；`user_id` 由 token 推导 | **需改造** | P0 | AC-S-08、AC-F-11 |
| E9 | `POST /api/follows` | `add_follow` L131-139 | 加鉴权（`follower_id` = token 身份） | **需改造** | P0 | AC-A-02 |
| E10 | `GET /api/feed` | `feed` L142-153 | 补 `cursor`/`session_id`；响应补 `has_more`/`request_id` | **需改造** | P0 | AC-F-09 |
| E11 | 媒体流 + Range | `_serve_media` L337-380 | **补访问控制**（§8.3.7 矩阵） | **需改造** | P0 | AC-U-09、AC-A-10 |
| E12 | 全站列表 | `GET /api/videos` L270-271（`list_all_videos` 全量） | 分页 + 过滤非公开 | **需改造** | P0 | AC-S-14 |
| E13 | `POST /api/admin/rebuild-cf` | L319-320（**无鉴权**） | 需 `SVP_ADMIN_TOKEN` | **需改造** | **P0** | **AC-S-07** |
| E14 | CORS 全域放开 | L216、L258、L368（`*` 硬编码） | `SVP_CORS_ORIGINS` 白名单 | **需改造** | **P0** | AC-A-06 |
| E15 | 演示首页 | `_serve_home` L383-412 | 保持（同步改为分页取数） | **已实现** | P2 | — |
| E16 | 无鉴权中间层 | ❌ 不存在（`grep auth|token` 无结果） | Bearer 解析 + `identity_mismatch` + 401/403 | **需新增** | **P0** | AC-A-01/02/03 |
| E17 | 无限流 | ❌ 不存在（`grep rate_limit` 无结果） | 令牌桶 + `429` + `X-RateLimit-*` + `Retry-After` | **需新增** | **P0** | AC-A-05/07 |
| E18 | 无并发上限 | `serve` L421-425（`ThreadingHTTPServer` 无界） | `MAX_CONCURRENT_CONNS` + `503 server_busy` | **需新增** | P0 | AC-A-08 |
| E19 | `POST /api/sessions`（+revoke） | ❌ 不存在 | §8.3.2 | **需新增** | P0 | AC-S-05 |
| E20 | `PATCH /api/videos/{id}` | ❌ 不存在 | §8.3.4（内容变更触发重审） | **需新增** | P0 | AC-U-11 |
| E21 | `DELETE /api/videos/{id}` | ❌ 不存在 | 软删除 → `status='removed'` | **需新增** | P1 | — |
| E22 | `GET /api/videos/{id}/exposure` | ❌ 不存在 | §8.3.13 的创作者反馈位（真实数字） | **需新增** | P1 | AC-U-12 |
| E23 | `POST /api/impressions` | ❌ 不存在 | §8.3.10（批量、单事务、幂等） | **需新增** | **P0** | AC-S-10/12 |
| E24 | `DELETE /api/engagements` | ❌ 不存在 | §8.3.9（`unlike`/`unfollow`） | **需新增** | P0 | AC-S-09 |
| E25 | `POST /api/internal/moderation/callback` | ❌ 不存在 | §8.3.12 | **需新增** | P0 | AC-U-10 |
| E26 | `POST /api/admin/recount` | ❌ 不存在 | 计数重算校对 | **需新增** | P0 | AC-S-13 |
| E27 | `GET /api/admin/metrics` | ❌ 不存在 | §8.3.13（8 项指标） | **需新增** | **P0** | AC-F-18 |
| E28 | 结构化日志与请求追踪 | `log_message` L250-252（默认静默，`SVP_HTTP_LOG` 开关） | JSON 结构化 + `X-Request-Id` 关联 + token 脱敏 | **需新增** | P1 | AC-A-09 |

### 10.7 补充块：`tests/` · `run.py` · `docs/` · `README.md`

| # | 能力项 | 现状（证据） | 本 PRD 要求 | 判定 | 优先级 | 验收 |
|---|---|---|---|---|---|---|
| F1 | 回归测试 86 项全绿 | `make test` → `Ran 86 tests … OK`（本次实测） | 提升至 **≥ 140 项**，且不削弱既有语义 | **需改造** | P0 | AC-R-01 |
| F2 | 探索位行为测试 | ❌ 不存在（无任何测试覆盖 `is_exploration`，是 G1 未被发现的原因） | 3 项行为断言（AC-F-08/08b/08c） | **需新增** | **P0** | AC-F-08* |
| F3 | 幂等与取消测试 | `test_engagement_updates_stats`（test_api.py:388）仅验证"计数增加" | 补幂等、取消、`recount` 一致性（AC-S-08/09/13） | **需新增** | P0 | AC-S-08/09/13 |
| F4 | 鉴权/限流测试 | ❌ 不存在 | AC-A-01~10 全套（含"拒绝先于读体"） | **需新增** | P0 | AC-A-* |
| F5 | 分页测试 | ❌ 不存在 | AC-F-09/09b/09c（跨页无重复 + 过期 + 曝光去重） | **需新增** | P0 | AC-F-09* |
| F6 | `run.py` 环境变量与前置校验 | L18-31（`SVP_HOST/SVP_PORT/--db/--media-root/--seed-demo`） | 补启动前置校验：`SVP_ENV=prod` 时 `ffprobe` 缺失即**拒绝启动**；`SVP_ADMIN_TOKEN` 缺失即拒绝 | **需改造** | P0 | AC-U-13 |
| F7 | `README.md` 现状描述 | L57-76 宣称「ε-greedy 探索 10%」已实现（**与代码不符**）；L130-133 列出 4 项已知限制 | **更正为与代码一致**（探索位标注"待接线"），并补入本文 §6.1 的 8 项上线阻塞项 | **需改造** | P0 | — |
| F8 | `docs/04-mvp-prd.md` | v1.0（206 行）缺数据模型/API 契约/GWT/Gap 表/任务拆分 | **本文 v2.0 就地覆盖**（零冗余，见 §0.1） | **需改造** | P0 | — |
| F9 | `docs/03-recommendation-design.md` §3.1 | L145-154「总候选约 500 / 150-80-120-100-50」绝对条数口径 | 修订为百分比 × 候选池基准深度（C1 裁定） | **需改造** | P0 | AC-F-03 |
| F10 | `docs/api.md` | 215 行，缺 11 个新增端点、缺鉴权章节、缺错误文案 | 以本文 §八 为准全面重写（或由本文取代其权威地位） | **需改造** | P0 | — |

### 10.8 Gap 表自检（对照本单验收标准）

| 本单验收标准 | 自检结果 |
|---|---|
| API 契约完整到工程可无歧义实现 | ✅ §八：22 个端点（12 个新增/改造）逐一给出方法/路径/鉴权/请求/响应示例/错误码；§8.4 全量 54 个错误码含用户文案；§8.5 兼容性策略 |
| 每条 FR 都有可测试验收条件 | ✅ §五：**69 条** Given/When/Then（AC-U 15 + AC-F 25 + AC-S 16 + AC-A 10 + AC-P/R 3），与 §三 每条 FR 双向映射，并在 §十 反查 |
| Gap 表覆盖 `server/` 现有 5 个模块 | ✅ §10.2–§10.6 逐模块覆盖 `config.py`/`db.py`/`media.py`/`recommend.py`/`app.py`，共 **102 条**逐条判定并附代码行号证据；§10.7 补充支撑文件 10 条 |

---

## 十一、口径冻结与决策记录

> 本章是**下游执行的强制约束**：凡与本章冲突的实现或文档，一律以本章为准。

### 11.1 口径裁定（冻结）

#### C1 · 召回配额口径终裁（解决 PRO-5 §7.2-5 点名的冲突）**P0 前置**

| 项 | 内容 |
|---|---|
| **冲突事实** | `docs/03-recommendation-design.md` L145-154 给出「单次请求总候选约 **500** 条」+ 绝对条数配额 `cf:150 / follow:80 / fresh:120 / tag:100 / fallback:50`；而 `server/config.py` L40-48 实现的是**百分比 × 候选池基准深度**：`{0.30,0.25,0.20,0.15,0.10} × RECALL_BASE_DEPTH(200)`，并带 `MIN_ROUTE_DEPTH(20)` 兜底 |
| **终裁** | **以百分比口径为唯一有效口径**（等同 `server/config.py` 现状）。`docs/03 §3.1` 的绝对条数口径**作废并须修订** |
| **公式** | `route_depth(r) = max(MIN_ROUTE_DEPTH, round(RECALL_QUOTAS[r] × RECALL_BASE_DEPTH))` |
| **裁定理由** | ① 代码与 2 项单测已固化百分比口径；② `config.py:36-39` 记录了「配额乘 `size` 会饿死候选池」的踩坑史，百分比 + 基准深度正是该踩坑的修正；③ 绝对条数在内容库 < 500 条时与「总候选 500」自相矛盾；④ 百分比口径随库规模增长自适应，零改配置 |
| **行动** | M0 内修订 `docs/03 §3.1` 与 §2.2 架构图；新增 `newcomer` 配额（M4 生效）：`RECALL_QUOTAS = {cf:0.25, follow:0.25, fresh:0.20, tag:0.15, fallback:0.05, newcomer:0.10}` |

#### C2 · 四个核心口径冻结（PRO-5 §6.4-5 要求）

| 口径 | 冻结定义 | 备注 |
|---|---|---|
| **`view`（播放）** | `kind='view'` 的**去重用户数**（`COUNT(DISTINCT user_id)`） | 与「开始播放即计」的 YouTube Shorts/Reels 口径**不同**，跨平台比较前须先对齐（PRO-3 已警告） |
| **`exposure`（曝光）** | `feed_impressions` 中 `is_visible=1 AND source='client'` 的**去重用户数**（`visible_ms ≥ 1000`） | **本 PRD 新增**；是 S1/S2/W2_CRR 的唯一基础 |
| **`完播`（complete）** | `kind='complete'` 的**事件数**（允许同人多条）；完播率 = `completes / views` | |
| **`有效播放`** | `watch_ms ≥ 3000` 的 `view` 事件数占比（参考值 ≥ 60%〔E1/待校准〕）。**不进入北极星**，仅作诊断 | 3000ms 为团队设定阈值，非行业基准 |
| **`served`（投放）** | 服务端返回 feed 时的 `source='server'` 记录（未确认可见）。**默认报表口径用 `exposure` 而非 `served`** | 防"投放即算曝光"的虚高 |

**口径版本**：以上定义冻结为 **`metric_caliber_v1`**。任何变更须：① 记录版本号；② 同步修订 PRO-5 §6.3 第 5/6 条验收条款；③ 在 `metrics` 端点的 `caliber_version` 字段中体现。

#### C3 · 互动实体命名：逻辑 `Interaction` ≡ 物理表 `engagements`

改表名为纯破坏性变更（86 项测试已固化），收益为零。**冻结为逻辑名与物理名分离**，本文档显式登记映射。迁移 PostgreSQL 时可一次性改名。

#### C4 · 曝光可见阈值 = 1000ms

`is_visible` 由**客户端**判定（元素在视口内 ≥ 1s）。服务端不做二次判定，但会裁剪 `visible_ms > 3600000`（防伪造超长时长）。理由：服务端无法感知真实可见性；把判定权交给客户端 + 上限裁剪，是 MVP 阶段成本与可信度的平衡点（IVT 级别的可见性校验属后续迭代）。

#### C5 · `duplicate_video` 的幂等语义（**客户端必须遵守**）

服务端返回 409 `duplicate_video` + 原 `video_id` 时，**客户端必须判定为上传成功**，直接采用该 `video_id` 进入发布流程。这是本 MVP **唯一的重试幂等机制**（sha256 去重）。若客户端把它当错误展示，一次 5xx 重试就会让创作者看到「视频已存在」的误导报错。

#### C6 · HTTP 状态码语义冻结

| 语义 | 状态码 | 说明 |
|---|---|---|
| 上传成功且已发布 | **201** | |
| 上传成功但待审核 | **202** | **不是错误**；客户端按成功处理并展示"审核中" |
| 幂等重放成功 | **200** | `Idempotency-Key` 命中 |
| 去重命中（已成功过） | **409** | 客户端按成功处理（C5） |
| 游标过期 | **409** | 客户端须自动刷新首屏 |
| 审核拒绝 | **422** | 语义错误（请求合法但内容被拒） |
| 超限 | **429** | 必须带 `Retry-After` |

#### C7 · 分发公平三常数（D2 的可核对数字，冻结）

| 常数 | 值 | 作用 |
|---|---|---|
| `CREATOR_CAP_PER_FEED` | **2** | 单创作者在单条 feed 内的最大条数（已实现） |
| `GINI_ALERT` | **0.6** | 创作者曝光 Gini 超此值触发告警（PRO-5 §4.4.2） |
| `GINI_FORCE_EXPLORE` | **0.7** | 超此值**强制**提升探索流量（`fairness_boost` 上限 2.0 → 3.0，`EPSILON_EXPLORE` 提升） |

> `RANK_WEIGHTS` 的变更必须与 C7 联动监控；护栏触发即回滚（PRO-5 §4.4.2 强制写法）。

#### C8 · 去重窗口与来源

| 机制 | 来源 | 窗口 | 现状 |
|---|---|---|---|
| 已看过滤 | `engagements` | 7 天 | ⚠️ 已实现但来源错误 → **须切到 `feed_impressions`（会话级 + 7 天）** |
| 会话内翻页去重 | `feed_impressions(session_id)` | 会话 | 需新增 |
| `dislike` 永久排除 | `user_video_suppression` | **永久** | 需新增 |

#### C9 · 北极星与代理口径

`exposure` 落地前，A1 与 W2_CRR 的「曝光」一律使用**代理口径** `[代理口径]`（`views ≥ 1`）并逐处标注；`exposure` 上线后切回（记录为 `caliber_v1 → v2`）。

#### C10 · 「新视频保护期」的诚实表述

`docs/03 §6.2` 的「不进淘汰池」在当前实现中**不适用**（系统**不存在**淘汰池）。因此：**不得**在对外口径中宣称"已实现新视频保护期"。正确表述：**「当前无淘汰机制；本 PRD 新增 R6 保底曝光路由（M4）作为该保护期的机制化实现」**。

### 11.2 本单（PRO-6）的执行决策

| # | 决策 | 依据 |
|---|---|---|
| **PD1** | PRD **就地覆盖** `docs/04-mvp-prd.md`（v2.0 取代 v1.0），**不新建 v2/v3 文件**，满足零冗余要求 | 用户方零冗余纪律；§0.1 |
| **PD2** | 保留上游 `[PRD-§x]` 全部引用锚点的语义，并给出映射表 | PRO-5 大量引用本文件；§0.2 |
| **PD3** | 召回配额采用**百分比口径**，废弃绝对条数 | C1 |
| **PD4** | 逻辑实体名用本单要求的 `Interaction`，物理表名保留 `engagements` | C3（避免破坏 86 项测试） |
| **PD5** | **分片/断点续传列为 Out of scope**，但强制量化上传失败率作为复查触发条件 | PRO-5 §6.2；NG11 |
| **PD6** | **`duplicate_video` 的 409 冻结为幂等成功语义**（新增顶层 `video_id` + 保留 message 兼容） | FR-1.3.c；C5 |
| **PD7** | **`dislike` 永久排除与「7 天已看」是两套独立机制**，不得合并；`skip`（弱信号）与 `dislike`（强信号）不得合并 | FR-2.5.b/h |
| **PD8** | 发现并登记 **G1 缺陷**：ε-greedy 探索位是**死代码**（`recommend.py:391-396` 计算、`L419` 恒为 `False`），使 README/PRD 的"10% 探索流量"声明**不成立**；要求接线 + 补 3 项行为测试 | 本次代码审查实测 |
| **PD9** | 发现并登记 **fail-open 缺陷**：`ffprobe` 缺失时 `validate_upload` 的时长/分辨率校验被整体跳过；生产环境必须 fail-closed | `media.py:320-328` + `:377` |
| **PD10** | **互动幂等性**（`like` 可被重复计数且无校对手段）列为 P0，并给出 `uq_eng_toggle` 部分唯一索引方案 | `db.py:230-262` 无唯一约束 |
| **PD11** | 管理端点（`/api/admin/rebuild-cf`）当前**无鉴权**，列为 P0；`SVP_ADMIN_TOKEN` 环境变量注入 | `app.py:319-320` |
| **PD12** | 明确 **`exposure` 未落地前 S1/S2 不可计算**，并把它写进 §6.1 上线阻塞项第 2 条（PRO-5 §4.4.1 纪律 4 的落地） | PRO-5 §6.4-6 |
| **PD13** | 数据模型新增列一律 `NOT NULL DEFAULT`；旧行 `moderation_status='approved'`（向后兼容），并显式标注「历史数据未经过审核」 | §7.5 |

### 11.3 待裁定 / 需上游或 board 确认的事项

| # | 事项 | 归属 | 说明 |
|---|---|---|---|
| 1 | 「创作者曝光反馈位」的呈现时机与文案 | PRO-8（GTM） | 本 PRD 只规定「X 必须为真实曝光数」；文案属 GTM |
| 2 | 对外保底数字口径（PRO-5 §7.3：GTM 的"500" vs A1 的"P10 ≥ 50"） | **PRO-8 先行裁定**（PRO-5 已裁定以 P10 ≥ 50 为准） | 本 PRD 已按 P10 ≥ 50 实现机制设计 |
| 3 | 「站外社交信号补充召回」的权重上限落地方式 | PRO-8 + 本 PRD 后续版本 | 本 PRD 仅冻结边界（≤ 1 路、冷启动期不作第一权重） |
| 4 | 真实身份认证（短信/OAuth）的引入时点 | board / 后续立项 | 本 PRD 明确 `auth_level:"dev"` 为**上线阻塞项** |
| 5 | 兴趣标签垂类白名单（`INTEREST_TAXONOMY`）的最终取值 | 产品 + 运营 | 需与 PRO-8 种子计划的垂类选择对齐（建议 6~10 个垂类） |

### 11.4 本单的诚实限定（不得省略）

1. **本 PRD 的机制设计成立 ≠ 成功判据成立。** S1/S2/S3/S4/S5 的成立前提是 PRO-4 的 Top 3 假设（A1/A2/A4）成立，而 A2/A4 为 **E1（无证据）**、A1 为 **E2**。本 PRD 交付的是**可验证的机制与测量基础设施**。
2. **Gap 表中的判定基于本次代码审查（含行号）**，可复核；但「需改造」项的具体工作量未经工程估算。
3. **所有阈值（P10 ≥ 50、Gini ≤ 0.6、限流速率、`EXPOSURE_FLOOR=50`、`QUAL_FLOOR=0.3`、`visible_ms ≥ 1000`、200MB、180s 等）均为团队设定值，非行业基准**，须在灰度后用真实分布校准。
4. **本 PRD 未做合规/法务审查**：内容审核钩子、举报处理、未成年人保护、个人信息（`interest_tags`/`source`/曝光行为）的收集均需另行通过 consent 与最小化收集审查。
5. **未新增外部检索**：所有竞品与用户事实均转引自 `docs/00`/`docs/01`/`docs/06`/`docs/07`；PRO-3 标注 D 级的条目未被引用（§0.3）。
6. **`docs/03 §3.1` 与 `README.md` 的现状表述与代码不符**（探索位、配额口径），本 PRD 已登记并要求在 M0 更正——**在此之前，`docs/03` 与 `README` 不得作为实现依据**。
7. **英文术语保留原因**：`kind`/`cursor`/`exposure` 等 API 字段名、状态枚举值保留英文，以便与代码、报文一致；这是**刻意的**，不属于"未中文化"。

### 11.5 交付物与落盘

| 项 | 位置 |
|---|---|
| 本 PRD（唯一有效版本） | `docs/04-mvp-prd.md`（分支 `PRO-1-pro-1`，就地覆盖 v1.0） |
| 本 PRD 全文 | PRO-6 issue 评论（PID `4e108dbe-281e-48fd-8c31-2d72de903c32`） |
| 基线验证 | `make test` → 86/86 通过（记录于 §0.5） |
| 后续实现 | 由 PRO-7 承接（§九 M0–M6；§11.3 待裁定项先行确认） |

---

*文档结束 · Product Compass Consulting · PRO-6 PRD：MVP「视频上传」+「推荐流」 · v2.0 · 取代 v1.0*

