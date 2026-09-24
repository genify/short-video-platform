# 短视频平台 MVP

面向垂直品类创作者的短视频平台最小可行产品：**视频上传 + 推荐流**。

零第三方依赖（纯 Python 标准库），开箱即跑。

---

## 快速开始

```bash
# 1) 启动服务（默认 127.0.0.1:8080）
python3 run.py

# 2) 或先注入演示数据再启动（需 ffmpeg）
python3 run.py --seed-demo
#    演示用户没有 token（数据是直接写库的）：用 POST /api/sessions 各自换一个
#    例：curl -s -X POST localhost:8080/api/sessions -H 'Content-Type: application/json' \
#          -d '{"handle":"viewer_amy"}'

# 3) 跑全部回归测试
make test

# 4) 端到端冒烟测试（真实 HTTP：注册 → 上传 → 互动 → 推荐流）
make smoke
```

### 前置条件

| 依赖 | 用途 | 缺失时行为 |
|---|---|---|
| Python 3.10+（开发于 3.12） | 运行时 | 无法启动 |
| **ffprobe**（ffmpeg 套件） | 上传时读取时长/分辨率**真值** | **拒绝上传**（`503 probe_unavailable`，fail-closed；不再静默放行） |
| ffmpeg | `--seed-demo` / `make smoke` 现场合成演示视频 | 演示与冒烟不可用（核心链路仍可跑） |

**无任何 Python 第三方依赖。**

### 三分钟走通完整链路（含鉴权）

> 鉴权上线后，**所有写接口必须带 `Authorization: Bearer <token>`**：上传、互动、
> 关注、以及推荐流（读自己的 feed）。注册响应里的 `token` **只返回一次**，服务端
> 只存 `sha256`。

```bash
BASE=http://127.0.0.1:8080

# 注册创作者与观众（各自拿到一次性 token）
read -r CREATOR CTOKEN <<<"$(curl -s -X POST $BASE/api/users -H 'Content-Type: application/json' \
  -d '{"handle":"foodie_lin","display":"林小厨","interest_tags":["美食","旅行","宠物"]}' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["id"],d["token"])')"
read -r VIEWER VTOKEN <<<"$(curl -s -X POST $BASE/api/users -H 'Content-Type: application/json' \
  -d '{"handle":"viewer_amy"}' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["id"],d["token"])')"

# 已有用户也可以换新 token（开发级身份：仅凭 handle，无密码）
curl -s -X POST $BASE/api/sessions -H 'Content-Type: application/json' -d '{"handle":"viewer_amy"}'

# 造一个真实 mp4 并上传（ffmpeg 现场合成；必须带创作者自己的 token）
ffmpeg -v error -y -f lavfi -i testsrc=size=360x640:rate=6:duration=6 \
  -c:v libx264 -pix_fmt yuv420p -preset ultrafast /tmp/clip.mp4

VIDEO=$(curl -s -X POST $BASE/api/videos \
  -H "Authorization: Bearer $CTOKEN" \
  -F "creator_id=$CREATOR" \
  -F "caption=3分钟搞定深夜食堂 #美食 #家常菜" \
  -F "file=@/tmp/clip.mp4;type=video/mp4" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 观众点赞（user_id 必须等于 token 身份，否则 403 identity_mismatch）
curl -s -X POST $BASE/api/engagements -H "Authorization: Bearer $VTOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$VIEWER\",\"video_id\":\"$VIDEO\",\"kind\":\"like\"}"

# 拉推荐流（含打分归因、召回路径、探索位标记）
curl -s "$BASE/api/feed?user_id=$VIEWER&size=5" -H "Authorization: Bearer $VTOKEN" | python3 -m json.tool
```

---

## 鉴权与限流（P0，上线阻塞项）

实现依据：`docs/04-mvp-prd.md` §3.4（FR-3）/ §3.5（FR-4），验收条件 §5.3–5.4。

| 能力 | 实现 | 说明 |
|---|---|---|
| 用户凭据 | `POST /api/users` 返回 `token`（32 字节 URL-safe base64，仅一次） | 服务端只存 `sha256(token)`；`user_tokens` 表含 `expires_at`（30 天）/`revoked`/`auth_level=dev` |
| 开发级会话 | `POST /api/sessions {handle}` → `{token, user_id, expires_at, auth_level:"dev"}` | **无密码/验证码**，响应显式标注 `dev`，不得当作生产身份 |
| 撤销 | `POST /api/sessions/revoke` | 撤销后原 token 立即失效 |
| Bearer 鉴权 | 写接口 + 推荐流 + 用户资料读 | 缺头 `401 unauthenticated`；无效/撤销 `401 token_invalid`；过期 `401 token_expired` |
| 身份一致性 | 请求体/查询里的 `user_id`/`creator_id` 必须等于 token 身份 | 否则 `403 identity_mismatch`（杜绝冒用他人身份上传/点赞） |
| 公开读 | `/api/health`、`GET /api/videos`、`GET /api/videos/{id}`、`GET /api/videos/{id}/file`、`/` | 免鉴权，**但不免限流** |
| 管理端点 | `/api/admin/*` 需 `SVP_ADMIN_TOKEN`（环境变量） | **未配置则一律 403**（fail-closed）；管理员凭据与用户 token 不共用签发路径 |
| 限流 | 令牌桶（`server/ratelimit.py`） | 用户级 + IP 级 + 全局兜底；超限 `429 rate_limited`，带 `Retry-After` 与 `X-RateLimit-Limit/Remaining/Reset` |
| 上传前置校验顺序 | 鉴权 → 限流 → 体积预检，**全部在读请求体之前** | 否则保护对象（磁盘/IO）已被消耗；读体前被拒的请求直接关连接（`Connection: close`），不做排空 |
| CORS | `SVP_CORS_ORIGINS` 白名单驱动，**默认不为 `*`** | 未命中白名单不下发 CORS 头 |
| 秘密卫生 | 令牌只经环境变量/一次性响应传递；错误与日志统一脱敏为 `***` | 纯 hex 的 `video_id`/`sha256` 不会被误伤 |

限流默认档（`server/config.py::RATE_LIMITS`，可用环境变量覆盖）：

| 端点 | 用户级 | IP 级 |
|---|---|---|
| `POST /api/videos` | 5/分钟 且 20/天 | 10/分钟 |
| `POST /api/engagements` | 120/分钟 | 300/分钟 |
| `GET /api/feed` | 60/分钟 | 120/分钟 |
| `POST /api/users` | — | 5/小时 |
| `POST /api/sessions` | — | 20/小时 |
| `POST /api/admin/*` | 10/分钟 | — |
| 全局兜底 | — | 600/分钟 |
| `/api/health` | 豁免 | 豁免 |

环境变量一览：

```bash
SVP_ADMIN_TOKEN=...            # 管理端点凭据（不设则管理端点全拒）
SVP_CORS_ORIGINS=https://a.example,https://b.example
SVP_TOKEN_TTL_DAYS=30
SVP_RATE_LIMIT=0               # 仅本地调试用：关闭限流（生产禁止）
SVP_RANK_WEIGHTS='{"aff":0.45,"pop":0.20,"fresh":0.15,"social":0.10,"qual":0.10}'
SVP_MAX_UPLOAD_MB=200
SVP_DB_PATH=var/svp.db
SVP_MEDIA_ROOT=var/media
```

---

## 推荐流算法

三段式流水线，与 `docs/03-recommendation-design.md` 的设计一一对应：

```
① 多路召回                     ② 线性加权排序                 ③ MMR 重排 + 探索位
  cf       item-item 协同 30%    S = 0.45·Aff                  MMR λ=0.7
  follow   关注创作者     25%      + 0.20·Pop                   创作者打散（≤2 条）
  fresh    热门新鲜(HN)   20%      + 0.15·Fresh                 ε-greedy 探索位 10%（已接线，见下）
  tag      标签内容匹配   15%      + 0.10·Social                7 天内已看过滤
  fallback 冷启动兜底     10%      + 0.10·Qual
```

| 特征 | 定义 | 范围 |
|---|---|---|
| `Aff` | 用户标签画像（行为价值加权）与视频标签向量的余弦相似度 | 0~1 |
| `Pop` | `log1p(互动量) / log1p(全站最大)`，对数压缩防头部垄断 | 0~1 |
| `Fresh` | `0.5 ^ (age_hours / 48)` | 0~1 |
| `Social` | 关注=1.0，二跳社交=0.5，否则 0 | {0,0.5,1} |
| `Qual` | `0.6·完播率归一 + 0.4·点赞率归一` | 0~1 |

### 探索位（ε-greedy）—— 已真实投放

历史缺陷（PRD §10.5 D9 / G1）：代码算了 `explore_slots` 却在构造响应时硬编码
`is_exploration=False`，**探索位从未投放**，而旧 README 与 v1.0 PRD 却宣称
"10% 探索流量已实现"（86 项回归测试无一项覆盖该行为）。

现已按 `docs/04-mvp-prd.md` §3.2.5 FR-2.4.a~f 接线：

* 非冷启动用户、按 `seed` 判定命中 ε（默认 0.10）时，**真实替换第 4 位**
  （索引 3，前 3 位保持纯相关性）为一条探索项，feed 长度不变；
* 探索项从"未进入 top-size 且曝光量 < 全站 P30"的候选中按 `score` 降序取 1 条；
  无合格候选则**不注入**（宁缺毋滥）；
* 冷启动用户不注入（兜底池已承担探索职能）；
* 行为测试：`make test-exploration`（AC-F-08 / 08b / 08c，含 1000 seed 注入率 ≈ ε）。

> ⚠️ **曝光口径待升级**：真正的曝光量（`FeedImpression`）尚未实现（PRD M1），
> 探索候选的"低曝光"筛选用 `views` 作**代理**。M1 落地后该判据需改为真实曝光分位。
> 另外：多路召回的深度截断会自然淘汰低曝光长尾，因此探索候选会把库内低曝光项
> **显式补入**并用同一套特征/打分函数评分（否则探索位在稀疏库上永远选不出候选）。
>
> `EPSILON_EXPLORE` 的调参纪律：与 Gini 指标联动（Gini > 0.7 → 强制提升探索流量）。
> **当前无 Gini/曝光度量**，因此该纪律尚不可执行（见"已知未实现"）。

调参示例：

```python
from server.recommend import RecommendEngine
engine = RecommendEngine(db, weights={"aff":0.0,"pop":1.0,"fresh":0.0,"social":0.0,"qual":0.0})
```

### 推荐权重校准（本项目最大未验证假设）

权重 `0.45 / 0.20 / 0.15 / 0.10 / 0.10` 是**行业经验初值**，已提供可复现的离线
校准工具与结论报告：

```bash
make evaluate      # → docs/10-recommendation-weight-calibration.md
```

* 方法：留出法（把真值相关项**彻底移除**）+ NDCG@K 网格搜索 + 局部细化；
* 自检：评测器在默认权重下的排序必须与生产 `engine.feed` 逐项一致（否则结论无效）；
* 结论（合成评测集，12 用户 × 1033 个权重向量）：现状 **0.7661** → 搜索最优
  **0.8735**（+14.0%）；
* **但不要直接改默认值**：合成集只能验证方法（搜索最优 ≠ 生成真值，且最优解落在
  搜索空间边界 = 过拟合信号）。生产权重必须用真实日志（`--from-db`）+ 线上 A/B 定。

---

## 项目结构

```
.
├── run.py                      # 启动入口（--seed-demo 注入演示数据）
├── server/
│   ├── config.py               # 权重、配额、限额、鉴权/限流参数（唯一调参入口）
│   ├── db.py                   # SQLite 持久层（用户/令牌/视频/行为/关注/统计/相似度）
│   ├── auth.py                 # 令牌生成与脱敏原语（只存 sha256，常量时间比较）
│   ├── ratelimit.py            # 令牌桶限流器（用户级/IP 级/全局兜底）
│   ├── media.py                # 流式 multipart 解析 + ffprobe 校验（fail-closed）+ 分桶存储
│   ├── recommend.py            # 推荐引擎（召回/排序/MMR/探索位/冷启动）
│   └── app.py                  # HTTP 路由 + 鉴权层 + Application 业务层（可脱离 HTTP 单测）
├── scripts/
│   ├── seed_demo.py            # 演示数据播种（ffmpeg 现场合成 mp4，幂等）
│   ├── smoke.py                # 端到端冒烟测试（一条命令，真实 HTTP）
│   └── evaluate.py             # 推荐权重离线校准（NDCG@K 网格搜索）
├── tests/
│   ├── test_recommend.py       # 推荐引擎单测（特征/打分/MMR/冷启动/协同过滤）
│   ├── test_media.py           # multipart 字节级往返 / 五重校验 / ffprobe（含 fail-closed）
│   ├── test_api.py             # 端到端 HTTP 全链路（注册→上传→互动→推荐流）
│   ├── test_auth.py            # 鉴权与限流（AC-S-* / AC-A-*，严格限流档）
│   ├── test_exploration.py     # 探索位行为测试（AC-F-08/08b/08c）
│   └── test_evaluate.py        # 离线评测器一致性（harness == feed）
└── docs/
    ├── 00-intake-and-decomposition.md   # 立项评估 + 任务拆解 + 派发计划
    ├── 01-competitive-analysis.md       # 8 家竞品机制层分析
    ├── 02-user-research-personas.md     # 6 画像 + 旅程 + KANO + 假设
    ├── 03-recommendation-design.md      # 推荐算法完整设计（含手算演示）
    ├── 04-mvp-prd.md                    # MVP PRD v2.0（实现依据，v1.0 已就地覆盖）
    ├── 05-gtm-plan.md                   # GTM 与冷启动增长
    ├── 09-launch-integration-runbook.md # 上线整合手册
    ├── 10-recommendation-weight-calibration.md # 权重校准报告（脚本生成）
    ├── api.md                           # REST API 参考
    └── images/recsys-pipeline.svg       # 推荐流水线架构图
```

---

## 技术决策与 Trade-off

| 决策 | 选择 | 被否决 | 原因 |
|---|---|---|---|
| 技术栈 | Python 标准库 | Flask/FastAPI | 零依赖可运行性；目标环境无可用 pip 包 |
| multipart | 自研流式 boundary 扫描 | `email` 解析器整体读入 | 200MB 上传下内存驻留 ≤64KB |
| 元数据 | 服务端 ffprobe | 信任客户端上报 | 防时长/分辨率伪造 |
| 元数据依赖缺失 | **fail-closed**（503 拒收） | 降级放行（历史行为） | 环境问题不该变成绕过时长/分辨率限制的后门 |
| 排序 | 线性加权（可手算） | DNN 双塔 | 稀疏行为下可解释、零数据依赖 |
| 令牌存储 | 只存 `sha256` | 存明文/可逆加密 | 库泄露不等于令牌泄露 |
| 身份校验位置 | HTTP 层 + 业务层**双重** | 仅 HTTP 层 | 防止绕过 HTTP 直接调用业务层造成越权 |
| 限流实现 | 进程内令牌桶 | 固定窗口计数 | 固定窗口在边界可被"两倍突发"击穿；令牌桶能给有意义的 Retry-After |
| 存储 | SQLite + WAL | PostgreSQL | MVP 期零运维；已知单写锁是并发天花板 |
| 锁策略 | 读并发无锁 + 写串行 | 全局单锁 | WAL 下读写可并行，只有写需串行 |

---

## 已知未实现 / 未测试（诚实清单）

**未实现（PRD 剩余里程碑，均未在本轮范围内）**

- ❌ **曝光埋点与度量基础设施（M1）**：无 `FeedImpression`、无 `exposure` 事件，
  因此 **S1（首发 24h 曝光 P10 ≥ 50）/ S2（Gini ≤ 0.6）/ 北极星 W2_CRR 在数学上
  不可计算**；`exploration_slot_rate`、`feed_p99_ms` 等指标端点（`/api/admin/metrics`）
  亦不存在。探索位的"低曝光"判据目前用 `views` 代理。
- ❌ **互动幂等（M5）**：`like` 重复上报会重复计数（无唯一索引），无 `unlike`/`dislike`/
  `report`，无负反馈永久排除表。**这是反刷量的另一半**：限流已上，幂等尚未。
- ❌ **推荐流增强（M4）**：无游标分页（`cursor`/`has_more`）、无会话级曝光去重、
  无冷启动首屏槽位配额（3 热 + 3 垂类 + 2 长尾 + 2 探索）、无新视频保底曝光。
- ❌ **上传增强（M3）**：无审核回调、无重试白名单文档化实现、无断点续传。
- ❌ **权限矩阵（M6）**：视频无 `private`/`hidden` 语义（当前全为 `published`），
  因此 `GET /api/videos/{id}/file` 未做可见性 ACL（FR-4.1.g 未落地）；
  `GET /api/videos` 无分页（全量返回）。
- ❌ **身份真实性**：`auth_level=dev`（仅凭 handle 换 token），无密码/短信/OAuth。
- ❌ **单机限制**：限流为进程内实现（多实例不共享，需迁 Redis）；SQLite 单写锁；
  无 `MAX_CONCURRENT_CONNS` 上限与慢速攻击读超时。

**未测试 / 测试盲区**

- ⚠️ 未做并发/压测：无 `feed` P99 门禁测试（PRD NF-1），无多线程上传竞态测试。
- ⚠️ 限流的时间行为只测了"第 6 次被拒"，**未测**"窗口过后恢复"（依赖真实时钟等待）。
- ⚠️ CORS 只测了头是否下发，未在真实浏览器跨域场景验证。
- ⚠️ 权重校准的评测集为合成数据（真实日志回放路径 `--from-db` 已实现但**未在真实流量上跑过**）。
- ⚠️ 未覆盖：SQLite 磁盘写满、媒体文件被外部删除、`ffprobe` 超时（30s）边界。

**已知限制（设计取舍，不是缺陷）**

- 标签依赖文案 `#话题` 抽取，覆盖率有限（应引入视频理解模型）。
- 冷启动路径仅"放大兜底池"，与 `docs/03 §6.1` 的槽位配额设计不同（M4 待做）。
- `docs/03-recommendation-design.md §3.1` 的召回配额为**绝对条数**口径，已被裁定作废：
  以"百分比 × `RECALL_BASE_DEPTH`"为准（PRD §十一 C1），实现与文档不一致处以下者为准。

---

## 环境要求

- Python 3.10+（开发于 3.12）
- ffmpeg / ffprobe（**缺失时上传被拒**：`503 probe_unavailable`）
- 无任何 Python 第三方依赖
