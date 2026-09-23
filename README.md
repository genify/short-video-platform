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

# 3) 跑全部回归测试（86 项）
make test
```

打开 <http://127.0.0.1:8080> 可看到已发布视频列表页。

### 三分钟走通完整链路

```bash
BASE=http://127.0.0.1:8080

# 注册创作者与观众
CREATOR=$(curl -s -X POST $BASE/api/users -H 'Content-Type: application/json' \
  -d '{"handle":"foodie_lin","display":"林小厨"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
VIEWER=$(curl -s -X POST $BASE/api/users -H 'Content-Type: application/json' \
  -d '{"handle":"viewer_amy"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 造一个真实 mp4 并上传（ffmpeg 现场合成）
ffmpeg -v error -y -f lavfi -i testsrc=size=360x640:rate=6:duration=6 \
  -c:v libx264 -pix_fmt yuv420p -preset ultrafast /tmp/clip.mp4

VIDEO=$(curl -s -X POST $BASE/api/videos \
  -F "creator_id=$CREATOR" \
  -F "caption=3分钟搞定深夜食堂 #美食 #家常菜" \
  -F "file=@/tmp/clip.mp4;type=video/mp4" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 观众点赞
curl -s -X POST $BASE/api/engagements -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$VIEWER\",\"video_id\":\"$VIDEO\",\"kind\":\"like\"}"

# 拉推荐流（含打分归因）
curl -s "$BASE/api/feed?user_id=$VIEWER&size=5" | python3 -m json.tool
```

---

## 推荐流算法

三段式流水线，与 `docs/03-recommendation-design.md` 的设计一一对应：

```
① 多路召回                     ② 线性加权排序                 ③ MMR 重排
  cf       item-item 协同 30%    S = 0.45·Aff                  MMR λ=0.7
  follow   关注创作者     25%      + 0.20·Pop                   创作者打散（≤2 条）
  fresh    热门新鲜(HN)   20%      + 0.15·Fresh                 ε-greedy 探索 10%
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

**为什么不用 DNN 双塔**：新平台行为极稀疏，协同过滤天然失效，DNN 是负收益。因此本实现把**内容标签匹配**与**冷启动兜底**做成一等公民，而非补充模块。权重全部集中在 `server/config.py`，可直接做网格搜索与 A/B。

调参示例：

```python
from server.recommend import RecommendEngine
engine = RecommendEngine(db, weights={"aff":0.0,"pop":1.0,"fresh":0.0,"social":0.0,"qual":0.0})
```

---

## 项目结构

```
.
├── run.py                      # 启动入口（--seed-demo 注入演示数据）
├── server/
│   ├── config.py               # 权重、配额、限额（唯一调参入口）
│   ├── db.py                   # SQLite 持久层（用户/视频/行为/关注/统计/物品相似度）
│   ├── media.py                # 流式 multipart 解析 + ffprobe 校验 + 分桶存储
│   ├── recommend.py            # 推荐引擎（召回/排序/重排/冷启动）
│   └── app.py                  # HTTP 路由 + Application 业务层（可脱离 HTTP 单测）
├── scripts/
│   └── seed_demo.py            # 演示数据播种（ffmpeg 现场合成 mp4，幂等）
├── tests/
│   ├── test_recommend.py       # 31 项：特征/打分/MMR/冷启动/协同过滤
│   ├── test_media.py           # 27 项：multipart 字节级往返/校验/ffprobe
│   └── test_api.py             # 28 项：端到端 HTTP 全链路
└── docs/
    ├── 00-intake-and-decomposition.md   # 立项评估 + 任务拆解 + 派发计划
    ├── 01-competitive-analysis.md       # 8 家竞品机制层分析
    ├── 02-user-research-personas.md     # 6 画像 + 旅程 + KANO + 假设
    ├── 03-recommendation-design.md      # 推荐算法完整设计（含手算演示）
    ├── 04-mvp-prd.md                    # MVP PRD
    ├── 05-gtm-plan.md                   # GTM 与冷启动增长
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
| 排序 | 线性加权（可手算） | DNN 双塔 | 稀疏行为下可解释、零数据依赖 |
| 存储 | SQLite + WAL | PostgreSQL | MVP 期零运维；已知单写锁是并发天花板 |
| 锁策略 | 读并发无锁 + 写串行 | 全局单锁 | WAL 下读写可并行，只有写需串行 |

## 已知限制

- ⚠️ **无鉴权与限流**（MVP 假设内网部署，上线前必须补）
- ⚠️ **推荐权重未经真实数据校准**，当前为行业经验初值
- ⚠️ SQLite 单写锁不适合高并发写入场景
- ⚠️ 标签依赖文案 `#话题` 抽取，覆盖率有限（应引入视频理解模型）

详见 `docs/04-mvp-prd.md` 第六章。

---

## 环境要求

- Python 3.10+（开发于 3.12）
- ffmpeg / ffprobe（用于视频元数据探测；缺失时降级为 0 值但不阻断上传）
- 无任何 Python 第三方依赖
