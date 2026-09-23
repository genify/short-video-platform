# 短视频平台竞品深度调研报告

> 项目代号：short-video-platform  
> 编制单位：Product Compass Consulting  
> 报告版本：v1.0（立项调研阶段）  
> 数据截止：2026 年 5 月  
> 说明：本报告所有关键数字均标注可核实来源链接；无法从公开可信渠道核实的数字统一标注「未核实」。专有名词与产品名保留英文原文。

---

## 一、调研范围与方法论

本次调研聚焦全球与中国主流短视频/短内容平台，围绕「用户规模—分发机制—产品形态—变现结构」四条主线展开，覆盖以下 8 个对标对象：

1. 抖音（Douyin）
2. 快手（Kuaishou）
3. 微信视频号（Video Accounts）
4. 小红书（Xiaohongshu / RED）
5. 哔哩哔哩（Bilibili，以中视频延展短视频场景）
6. TikTok（海外）
7. YouTube Shorts（海外）
8. Instagram Reels（海外，数据有限，主要作为形态参照）

方法论上采用三层递进：

- **第一层（数据层）**：优先采用上市公司财报、平台官方公开文档、权威第三方监测机构（QuestMobile、eMarketer、DataReportal）数据。
- **第二层（机制层）**：采用平台官方算法公开披露（如抖音安全与信任中心、微信官方产品文档）与行业技术拆解，还原「召回—粗排—精排—重排」的工程链路。
- **第三层（推断层）**：对非公开的权重参数（如完播率具体阈值）标注为「行业观测值/推测值」，避免将运营经验当作官方事实。

---

## 二、核心竞品横向对比总表

下表为本次调研的核心交付物，覆盖月活、推荐机制、产品形态、上传上限、分成模式、冷启动、商业模式七个维度。

| 平台 | 月活（MAU） | 核心推荐机制 | 单列/双列 | 上传时长上限 | 创作者分成模式 | 冷启动特征 | 商业模式 |
|---|---|---|---|---|---|---|---|
| **抖音** | 10.01 亿（含极速版，2025 年 3 月，[新浪财经](https://finance.sina.com.cn/tech/roll/2025-05-01/doc-ineuzkhe9577029.shtml)）；2026 年 3 月主端 10.09 亿（[新浪财经](https://finance.sina.com.cn/tech/discovery/2026-04-29/doc-inhwckrh8029807.shtml)） | 召回—过滤—排序—重排；几乎不依赖标签，神经网络直接预估「用户行为概率 × 行为价值权重」定优先级（[财联社](https://www.cls.cn/detail/2005910)） | 单列沉浸式上下滑 | 普通用户默认约 3 分钟，认证/申请后可延长；历史上限约 15 分钟；短剧单集硬上限 3 分钟（[新浪财经](https://finance.sina.com.cn/wm/2026-05-31/doc-inhzwpyv2519666.shtml)） | 播放量分成（中视频伙伴计划）+ 评论区广告分成 + 直播/电商/星图 | 系统分配初始流量池，以陌生人为主；阶梯晋级赛马 | 广告（2025 年约 4200 亿元，占比 46.6%）、直播、电商、本地生活 |
| **快手** | 7.31 亿（2025 Q3，[人民网](http://finance.people.com.cn/n1/2025/1120/c1004-40608130.html)）；2025 全年 7.25 亿（[华尔街见闻](https://wallstreetcn.com/articles/3768354)） | 基尼系数调控的「流量普惠」；80% 流量向中长尾倾斜，同城 30km 优先，粉丝互动权重约为陌生人 5 倍（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)） | 默认「精选」单列沉浸式；关注页/部分场景保留双列 | 客户端约 15 分钟内；网页端最长 15 分钟、单文件 ≤4G（[快手官方](https://www.kuaishou.com/help/feedback/4000?categoryId=hot)） | 直播打赏（核心）+ 磁力聚星广告 + 电商带货 + 流量分成 | 普惠池 + 私域（关注页）；老铁关系链带初始曝光 | 直播打赏、电商、广告、可灵 AI 订阅（单月收入破 2000 万美元） |
| **微信视频号** | 日活突破 5 亿（2025，[QQ 新闻](https://news.qq.com/rain/a/20250516A08CUZ00)）；另有 6.2–8 亿口径（第三方，**部分未核实**） | 社交推荐为第一权重 + 个性化兴趣为辅；好友点赞/互动内容首页曝光概率可提升约 300%（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)；[亿邦动力](https://www.ebrun.com/20250403/576580.shtml)） | 以单列为主，混有「朋友都在看」社交标签 | 未公开统一上限（**未核实**） | 创作分成计划：原创视频评论区展示广告，创作者约分得广告收益 60%（[微信官方文档](https://support.weixin.qq.com/cgi-bin/mmsupportacctnodeweb-bin/pages/flrux77QlRxPwwhY)；分成比例为第三方整理，**待官方核实**） | 微信好友与关注者带初始曝光（私域冷启动），无好友互动则难进公域 | 广告（腾讯广告体系）、直播打赏、电商、私域转化 |
| **小红书** | 3 亿（官方通案，[千瓜数据](https://www.qian-gua.com/information/detail/3149)）；3.5 亿（[亿欧](https://www.iyiou.com/news/202607311136762)）；DAU 1.18 亿（2025 年 1–10 月，[网易](https://www.163.com/dy/article/KHNN4E130553G8MA.html)） | 标签匹配为主：首图清晰度约 30% 权重、标题关键词约 20% 权重（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)）；「推荐页 + 朋友页」双流 | 双列卡片流为主（搜索/发现），视频进入为单列沉浸 | 最长 15 分钟（[小多 AI](https://insight.xiaoduoai.com/e-commerce-information/xiaohongshu-information/xiaohongshu-can-upload-videos-up-to-15-minutes-or-30-minutes-where-is-the-upload-button-hidden-official-duration-limit-analysis-complete-guide-to-upload-entry-even-newbies-can-get-started-quickly.html)，**官方口径建议复核**） | 蒲公英商单 + 直播 + 电商（笔记挂链）+ 部分流量激励 | 标签冷启动 + 搜索流量；带地域标签内容搜索流量占比约 40%（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)） | 广告为主（2025 年约 320 亿元，占总营收 76%，[36 氪](https://m.36kr.com/p/3897635059402375)）、电商 |
| **哔哩哔哩** | 3.66 亿（2025 Q4，[证券时报](https://www.stcn.com/article/detail/3663807.html)）；2025 Q3 3.76 亿、DAU 1.17 亿、日均 112 分钟（[财联社](https://www.cls.cn/detail/2200027)） | 完播率优先 + 分区保护；前 30 秒留存决定是否进推荐流，垂直内容有首页保底展示（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)） | 双列卡片为主（首页），播放页单列 | 常规上限 8 小时（一般账号），**具体分级未核实** | 创作激励 + 充电 + 广告分成（花火）+ 直播 | 分区标签 + 社区推荐；关注关系权重高 | 增值服务（大会员/直播）、广告、游戏、IP 衍生；2025 首次全年盈利 |
| **TikTok** | 约 19 亿（2025 年 10 月，[Printful](https://www.printful.com/blog/tiktok-statistics)）；美国 DAU 8220 万（2025 年 1 月，[Search Engine Land](https://searchengineland.com/guide/tiktok-users)） | 与抖音同源：多路召回 + 深度模型精排，完播/互动/复播多信号融合（**内部细节未公开核实**） | 单列沉浸式（For You 页） | 常规约 10 分钟，部分账号可至 60 分钟；**具体分级未核实** | Creator Rewards Program：视频需 ≥1 分钟、原创，按合格观看与 RPM 结算（[TikTok 官方](https://www.tiktok.com/creator-academy/article/creator-rewards-program)） | 新账号获初始曝光池（For You 冷启动），以陌生流量为主 | 广告（美国 2025 年约 140.3 亿美元，[eMarketer](https://digiday.com/marketing/tiktoks-ongoing-u-s-uncertainty-causes-marketers-to-rethink-future-budgets/)）、TikTok Shop、直播 |
| **YouTube Shorts** | 超 20 亿（[DemandSage](https://www.demandsage.com/youtube-shorts-statistics/)） | 与主站统一推荐体系；Shorts Feed 独立投放，重「停留/循环播放」信号 | 单列上下滑 | 3 分钟（[Google 官方](https://support.google.com/youtube/answer/15424877?hl=zh-Hans)） | 广告池分成：创作者固定保留 45% 分配收入（[Google 官方](https://support.google.com/youtube/answer/12504220?hl=en)） | 依托 YouTube 主站账号与订阅关系冷启动 | 广告（Shorts 日均超 2000 亿次观看，[YouTube CEO 2025 年 6 月](https://www.teleprompter.com/blog/youtube-shorts-statistics)）|
| **Instagram Reels** | **未核实**（Meta 未单独披露 Reels 月活） | 多信号融合：完播、分享（分享权重被业界认为极高）、保存（**具体权重未核实**） | 单列上下滑 | 约 3 分钟（**未核实**） | 无直接播放量分成，主要靠品牌合作/Reels 广告分成计划（部分地区） | 依托 Instagram 社交关系图谱冷启动 | 广告（Meta 广告体系）、电商标签 |

> 注：表中「行业观测值/推测值」均来自第三方技术拆解文章，非平台官方披露，落地决策时应以官方文档为准。

---

## 三、机制层深度剖析

### 3.1 推荐系统的「召回—粗排—精排—重排」四段式

抖音在 2025 年 4 月开放日首次系统披露算法原理：其推荐与国内外主流内容推荐平台相似，包含**召回、过滤、排序**等环节，核心是学习用户行为，采用协同过滤、双塔召回、Wide&Deep 等技术模型（[第一财经](https://www.yicai.com/news/102572414.html)、[财联社](https://www.cls.cn/detail/2005910)）。工程上可进一步拆解为四段：

1. **召回（Recall）**：从亿级内容池中筛出数百至数千候选。多路并行：i2i（item-to-item）相似召回、u2i（用户兴趣）召回、热门/精品池召回、同城/地域召回。抖音官方特别提到「多样性打散、多兴趣召回、扶持小众长尾兴趣」以打破信息茧房（[半月谈](http://www.banyuetan.org/xyx/detail/20250415/1000200033135821744731201065065327_1.html)）。
2. **粗排（Coarse Ranking）**：对召回候选做轻量模型打分，降维至百量级，控制算力成本。
3. **精排（Fine Ranking）**：主力模型（如 Wide&Deep、双塔）逐一预估「用户对每个内容的目标行为概率」，并结合**不同行为的价值权重**得出推荐优先级。抖音官方表述：「当用户打开抖音时，算法会给候选视频打分，并把得分最高的视频推送出去」「核心逻辑是预测用户行为概率 × 用户不同行为的价值权重」（[财联社](https://www.cls.cn/detail/2005910)）。这意味着**推荐值 ≈ Σ(行为概率ᵢ × 权重ᵢ)**，而非单一完播率排序。
4. **重排（Re-ranking / 打散）**：做多样性打散、频控、去重、作者去重、商业内容插播等约束，保证信息流不出现连续同质内容。

**关键洞察**：抖音的下一代逻辑正在弱化「标签匹配」。抖音总裁韩尚佑明确表示，推荐系统「已几乎不依赖对内容或用户打标签，而是通过一系列神经网络计算，直接预估每一个用户对每一个内容的目标行为」（[财联社](https://www.cls.cn/detail/2005910)）。这与小红书「标签匹配为主」的路线形成根本分野。

### 3.2 行为信号权重设计：完播率的「降权」与「深互动 + 搜索」的「升权」

行为信号权重是竞品机制差异的胜负手：

- **抖音（2024–2026 演进）**：2024 年升级提升了「播放时长」与「搜索关联」权重，用户主动搜索过的内容曝光量约提升 3 倍（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)）。到 2026 年，行业技术拆解显示抖音**完播率退出核心指标**，深度互动（收藏、分享、复看）与搜索价值成为流量核心，算法进入「7 天长效赛马 + 多维度权重重构」阶段（[CSDN](https://blog.csdn.net/2601_95649986/article/details/160103685)）。抖音官方也解释了为何突出「收藏」按钮——收藏被视作强正反馈信号。
- **快手**：行为权重向「关系链 + 私域」倾斜。同城内容优先推送给 30km 内用户，**粉丝互动权重约为陌生人的 5 倍**（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)）。这是一种典型的「关系增强」设计，对应其「老铁经济」。
- **视频号**：**点赞（社交背书）权重极高**，好友互动过的内容出现在首页的概率可提升约 300%，且带货转化率约达抖音的 2 倍（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)）。微信官方也确认，对「较多朋友推荐」的内容会提升曝光排序，并增加「朋友今天都在看」提醒（[人人都是产品经理](https://www.woshipm.com/share/6207300.html)）。
- **B站**：完播率优先 + 分区保护，**前 30 秒留存决定内容能否进入推荐流**（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)），适配其中长视频生态。

**对新产品启示**：行为权重不是常数，而是随平台生命周期动态调整的「旋钮」。新平台早期应**优先权重完播率与分享**（快速识别优质内容、驱动社交裂变），成熟期再引入搜索价值、收藏、复看等长效信号。

### 3.3 流量池阶梯（赛马机制）

冷启动的核心是分层流量池的「晋级—淘汰」博弈：

- **抖音流量池分级（行业观测值）**：新视频先进入**冷启动池／基础曝光池（500–5000 次曝光）**，通过核心指标筛选后逐级进入 **5 万级、50 万级、10 万–100 万级**流量池（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)、[店托易](https://diantuoyi.com/article/40163.html)）。另有拆解给出更细的冷启动池为 **500–1000 曝光，完播率需 ≥40%** 才能晋级，且**「前 3 秒留存率」权重占比高达 40%**（[新浪财经](https://cj.sina.cn/articles/view/7879848900/1d5acf3c401902mu14)）。
- **阈值观测值**：短视频（15 秒内）完播率需 ≥40%；中长视频（1 分钟以上）稳定在 25%–30%；综合互动率高于 5% 通常具备晋级潜力（[店托易](https://diantuoyi.com/article/40163.html)、[新浪财经](https://cj.sina.cn/articles/view/7879848900/1d5acf3c401902mu14)）。**注意：以上阈值为第三方运营经验总结，非抖音官方公布，属「未核实」级别。**
- **快手**：与抖音的「赛马」不同，快手用**基尼系数**作为严格的量化约束指标，每个分发策略都有基尼系数的约束性考核，避免流量过度集中于头部，约 80% 流量向中长尾倾斜（[东方财富研报](https://pdf.dfcfw.com/pdf/H3_AP202102081460140015_1.pdf)、[华尔街见闻](https://wallstreetcn.com/articles/3607502)）。

**两种流量哲学的 Trade-off**：

| 维度 | 抖音式「效率赛马」 | 快手式「普惠均衡」 |
|---|---|---|
| 分配目标 | 全局消费效率最优 | 创作者生态公平/长尾繁荣 |
| 冷启动 | 陌生人流量池，数据达标即爆 | 私域+普惠池，粉丝权重高 |
| 创作者体感 | 爆款概率高但生命周期短 | 涨粉慢但私域沉淀强 |
| 副作用 | 头部集中、内容同质 | 头部带货爆发力偏弱 |

### 3.4 冷启动机制：公域 vs 私域 vs 社交

三种冷启动范式对应三种流量来源：

- **公域型（抖音、TikTok）**：系统分配初始流量池，以陌生人为主，新账号只要内容过赛马验证即可触达百万级用户（[蝉妈妈](https://www.chanmama.com/yunyingquan/question/4161.html)）。优点是「内容为王、起量快」，缺点是缺乏关系沉淀。
- **私域型（快手）**：关注页即私域，粉丝互动权重高，冷启动靠老铁关系链带动，沉淀强但破圈慢。
- **社交型（视频号）**：冷启动来源是**微信好友和关注者**，无好友互动则无法进入陌生人推荐。视频号系统通常在发布后 **3 小时、6 小时、18 小时**触发推荐，并在 **48 小时、72 小时**再次推荐；**发布后前 3 小时为「冷启动期」，是最关键的生死线**（[知乎](https://zhuanlan.zhihu.com/p/464551187)）。这要求创作者必须先在私域「手动冷启动」（[海螺社](https://www.hailuoshe.com/blog/shipinhao-increase-views)）。

### 3.5 单列 vs 双列的产品形态取舍

- **单列沉浸式**：一屏一内容，强制曝光，点击率趋近 100%，适合「内容分发、爆款制造、广告密集曝光」，但对创作者友好度集中于优质内容，涨粉快（[东方财富研报](https://pdf.dfcfw.com/pdf/H3_AP202010201422479434_1.pdf)）。
- **双列选择式**：一屏多封面，用户主动选择，强化「关注人」和创作者品牌，适合「关系沉淀、私域转化」，但单条曝光强度低。
- **演化事实**：快手已将默认入口从双列改为「精选」单列沉浸式（类似抖音「发现」），仅关注页/部分场景保留双列（[知乎](https://www.zhihu.com/question/470353455)）。这说明**行业最终向单列沉浸式收敛**，因为其单位时长消费效率更高；双列更多作为「关系/品牌」场景的补充。

---

## 四、变现模式与创作者经济对比

### 4.1 平台侧商业模式

- **抖音**：2025 年国内业务总营收约 9012 亿元，同比 +28.3%；广告收入约 4200 亿元，占比 46.6%（[新浪财经](https://finance.sina.cn/2026-04-20/detail-inhvehiv8447441.d.html)）。商业模式以「广告 + 电商 + 直播 + 本地生活」为主，广告仍是第一引擎。
- **快手**：直播打赏、电商、广告三驾马车，2025 年营收与净利润双双创新高，可灵 AI 单月收入突破 2000 万美元（[华尔街见闻](https://wallstreetcn.com/articles/3768354)）。
- **小红书**：2025 年营收约 420 亿元，同比 +40%，其中广告 320 亿元占 76%，电商与广告结构高度依赖广告（[36 氪](https://m.36kr.com/p/3897635059402375)）。
- **TikTok**：美国市场 2025 年广告收入约 140.3 亿美元，预计 2026 年增至 171.7 亿美元（[eMarketer](https://digiday.com/marketing/tiktoks-ongoing-u-s-uncertainty-causes-marketers-to-rethink-future-budgets/)）。

### 4.2 创作者分成模式对比

| 平台 | 分成机制 | 门槛/条件 | 创作者获得比例 |
|---|---|---|---|
| 抖音 | 中视频伙伴计划（抖音+西瓜+头条，按播放量分成）、广告分成计划 | 需完成申请任务并通过人工审核 | 未公开固定比例（**未核实**） |
| 快手 | 流量分成 + 直播打赏 + 磁力聚星 | — | 未公开固定比例（**未核实**） |
| 视频号 | 创作分成计划：原创视频评论区展示广告 | 有效关注 ≥100 人，需实名 | 创作者约 60%（第三方整理，**待官方核实**，[网易](https://www.163.com/dy/article/K988S1Q30556AGXW.html)） |
| 小红书 | 蒲公英商单 + 直播 + 电商 | — | 无固定播放量分成 |
| B站 | 创作激励 + 充电 + 花火 | — | 未公开固定比例（**未核实**） |
| TikTok | Creator Rewards Program | 视频 ≥1 分钟、原创、≥1000 合格观看 | 按 RPM 结算（比例未公开） |
| YouTube Shorts | 广告池分成 | 加入合作伙伴计划 | **固定 45%**（[Google 官方](https://support.google.com/youtube/answer/12504220?hl=en)） |

**关键洞察**：YouTube Shorts 是唯一公开「45% 固定分成」且规则透明的平台；视频号以「评论区广告分成」创造差异化路径；抖音/快手则以「播放量分成作为补充、直播电商为主收入」的结构，头部创作者主要靠广告与带货而非平台分成（[界面新闻](https://www.jiemian.com/article/7585138.html)）。

---

## 五、对新产品可借鉴的 5 条结论 / Trade-offs

### 结论 1：推荐架构直接采用「多路召回 + 深度精排 + 多样性重排」，但行为权重必须与平台阶段匹配
不要照搬抖音成体系的「去标签化神经预估」——那需要亿级数据与算力。**早期更务实的路径是「标签/协同过滤召回 + 双塔/Wide&Deep 精排 + 打散重排」**，行为权重优先押注「完播率 + 分享率」，待数据积累后再引入搜索价值、收藏、复看等长效信号。
- **Trade-off**：早期偏重完播率会诱导「标题党/短平快」内容，长期伤害内容调性；需用多样性打散和作者保底曝光对冲。

### 结论 2：冷启动必须选定「公域赛马 vs 私域普惠」其一为默认，不可既要又要
抖音的陌生人流量池「起量快、沉淀弱」，快手/视频号的私域/社交冷启动「沉淀强、破圈慢」。
- **建议**：冷启动期采用**混合冷启动**——新内容先投「小规模陌生人测试池（如 500–1000 曝光）」验证完播与互动，达标后自动晋级更大流量池；同时向创作者的粉丝/社群推送「关系增强曝光」。这是抖音效率与快手普惠的折中。
- **Trade-off**：混合冷启动会牺牲部分头部爆发速度，但换来更健康的长尾创作者留存。

### 结论 3：产品形态以单列沉浸式为主，双列仅作「关系/品牌」补充
行业已完成向单列沉浸式收敛（快手从双列转向「精选」单列即为例证）。单列的强制曝光带来更高的单位时长消费与广告效率。
- **Trade-off**：单列会削弱创作者品牌辨识度与用户主动选择权，需通过「关注页/合集/主页双列」补齐关系沉淀场景。

### 结论 4：创作者分成模型可采用「透明固定比例 + 评论区/信息流广告」组合，避免纯补贴
YouTube Shorts 的 45% 固定比例是最清晰的标杆；视频号「评论区广告分成」是低成本、低门槛的创新路径。纯烧钱补贴（如早期中视频计划）被证明性价比不足（[界面新闻](https://www.jiemian.com/article/7585138.html)）。
- **建议**：新产品采用**「广告收益固定比例分成（如 50%–55%）+ 电商佣金 + 直播打赏」**组合，公开计算规则以建立创作者信任。
- **Trade-off**：高固定比例压低平台毛利，需以电商/直播等高毛利业务反哺。

### 结论 5：早期不要与抖音正面争夺「全品类泛娱乐」，应选择差异化「流量哲学」切口
抖音（效率赛马）、快手（普惠）、视频号（社交）、小红书（种草/搜索）、B站（社区/中视频）已分别占据不同的生态位。新平台若以「又一个抖音」切入，几乎不可能在流量池规模上取胜。
- **建议**：选择尚未被充分占据的切口，例如「强搜索关联 + 垂直兴趣社区」「创作者收入透明化」「AI 原生内容生产/分发」（可参考字节在 AI 上的投入方向）。
- **Trade-off**：垂直切口天花板较低，需设计清晰的「从垂直走向泛化」的扩张路径。

---

## 六、关键数据来源汇总

| 数据点 | 数值 | 来源 |
|---|---|---|
| 抖音 MAU（含极速版，2025-03） | 10.01 亿，同比 +12.3% | https://finance.sina.com.cn/tech/roll/2025-05-01/doc-ineuzkhe9577029.shtml |
| 抖音主端 MAU（2026-03） | 10.09 亿 | https://finance.sina.com.cn/tech/discovery/2026-04-29/doc-inhwckrh8029807.shtml |
| 抖音月人均使用时长 | 46.54 小时（≈1.55 小时/天） | https://finance.sina.com.cn/tech/roll/2025-05-01/doc-ineuzkhe9577029.shtml |
| 抖音算法机制（官方） | 召回/过滤/排序，行为概率 × 权重 | https://www.cls.cn/detail/2005910 |
| 抖音 2025 国内营收/广告收入 | 9012 亿元 / 4200 亿元（46.6%） | https://finance.sina.cn/2026-04-20/detail-inhvehiv8447441.d.html |
| 抖音短剧单集时长上限 | 3 分钟 | https://finance.sina.com.cn/wm/2026-05-31/doc-inhzwpyv2519666.shtml |
| 快手 DAU/MAU（2025 Q3） | 4.162 亿 / 7.311 亿 | http://finance.people.com.cn/n1/2025/1120/c1004-40608130.html |
| 快手 2025 全年 DAU/MAU | 4.102 亿 / 7.246 亿 | https://wallstreetcn.com/articles/3768354 |
| 快手基尼系数普惠机制 | 80% 流量向中长尾 | https://pdf.dfcfw.com/pdf/H3_AP202102081460140015_1.pdf |
| 快手上传时长限制 | 最长 15 分钟，≤4G | https://www.kuaishou.com/help/feedback/4000?categoryId=hot |
| 视频号 DAU | 突破 5 亿 | https://news.qq.com/rain/a/20250516A08CUZ00 |
| 视频号社交推荐机制（官方） | 好友推荐提升曝光排序 | https://www.woshipm.com/share/6207300.html |
| 视频号创作分成计划（官方） | 评论区广告、关注 ≥100 | https://support.weixin.qq.com/cgi-bin/mmsupportacctnodeweb-bin/pages/flrux77QlRxPwwhY |
| 小红书 MAU / 营收 | 3 亿 / 420 亿元（广告 76%） | https://www.qian-gua.com/information/detail/3149 ; https://m.36kr.com/p/3897635059402375 |
| B站 MAU/DAU（2025 Q4） | 3.66 亿 / 1.13 亿 | https://www.stcn.com/article/detail/3663807.html |
| TikTok MAU / 美国广告收入 | 约 19 亿 / 140.3 亿美元 | https://www.printful.com/blog/tiktok-statistics ; https://digiday.com/marketing/tiktoks-ongoing-u-s-uncertainty-causes-marketers-to-rethink-future-budgets/ |
| TikTok Creator Rewards 规则 | ≥1 分钟、原创 | https://www.tiktok.com/creator-academy/article/creator-rewards-program |
| YouTube Shorts MAU / 日观看 | 20 亿+ / 2000 亿次 | https://www.demandsage.com/youtube-shorts-statistics/ |
| YouTube Shorts 上传时长 | 3 分钟 | https://support.google.com/youtube/answer/15424877?hl=zh-Hans |
| YouTube Shorts 分成 | 45% | https://support.google.com/youtube/answer/12504220?hl=en |

---

## 七、数据可信度与局限说明

1. **官方数据 vs 第三方数据**：财报类（快手、B站）与官方文档类（微信、Google、TikTok）可信度最高；QuestMobile/eMarketer 等第三方监测可信度次之；行业自媒体拆解的「流量池阈值、权重百分比」多为运营经验总结，本报告已逐条标注「未核实」或「待官方核实」。
2. **口径差异**：抖音 MAU 存在「主端」与「含极速版」两种口径（10.09 亿 vs 10.01 亿），视频号 DAU 存在 5 亿与 6.2–8 亿等不同来源，使用时须明确口径。
3. **时效性**：短视频行业数据变化快，本报告数据截止 2026 年 5 月，建议在立项定稿前复核最新财报与监测报告。
4. **Instagram Reels**：Meta 未单独披露 Reels 的月活与时长限制，相关单元格已标注「未核实」，后续可通过 Meta 财报电话会补充。
