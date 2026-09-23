# 短视频平台 MVP · REST API 参考

Base URL：`http://127.0.0.1:8080`
所有请求/响应体为 UTF-8 JSON；上传接口为 `multipart/form-data`。

## 错误格式（统一）

任何非 2xx 响应都是同一信封结构：

```json
{ "error": { "code": "duration_too_long", "message": "视频时长 200.0s 超过短视频上限 180s" } }
```

| 错误码 | 状态 | 含义 |
|---|---|---|
| `invalid_handle` | 400 | handle 不符合 `[A-Za-z0-9_\-中文]{2,32}` |
| `handle_taken` | 409 | handle 已存在 |
| `user_not_found` | 404 | 用户不存在 |
| `video_not_found` | 404 | 视频不存在 |
| `media_missing` | 404 | 数据库中记录的视频文件在磁盘上缺失 |
| `missing_creator` | 400 | 上传时缺少 `creator_id` |
| `missing_file` | 400 | 上传时缺少文件字段 |
| `bad_file_field` | 400 | 文件字段名不是 `file`/`video` |
| `bad_content_type` | 400 | 上传接口 Content-Type 不是 multipart/form-data |
| `missing_boundary` | 400 | multipart 缺少 boundary |
| `unsupported_extension` | 400 | 扩展名不在白名单 |
| `unsupported_mime` | 400 | MIME 不在白名单 |
| `payload_too_large` | 413 | 请求体或文件超过 200MB |
| `empty_file` / `empty_body` | 400 | 文件或请求体为空 |
| `duration_too_long` / `duration_too_short` | 400 | 时长不在 1s~180s |
| `resolution_too_low` | 400 | 高度 < 240px |
| `unprobeable_media` | 400 | ffprobe 无法解析（非视频/损坏） |
| `duplicate_video` | 409 | sha256 重复，报文含原 `video_id` |
| `invalid_kind` | 400 | 互动类型非法 |
| `self_follow` | 400 | 不能关注自己 |
| `missing_user_id` | 400 | feed 缺少 `user_id` |
| `invalid_size` | 400 | `size` 不是整数 |
| `invalid_json` / `invalid_json_shape` | 400 | 请求体 JSON 非法 |
| `not_found` | 404 | 路由不存在 |
| `internal_error` | 500 | 服务内部错误 |

---

## 1. 健康检查

```
GET /api/health
```
```json
{ "ok": true, "ts": 1758624000.123 }
```

## 2. 用户

### 创建用户
```
POST /api/users
Content-Type: application/json

{ "handle": "foodie_lin", "display": "林小厨" }
```
→ `201`
```json
{ "id": "b3c1...", "handle": "foodie_lin", "display": "林小厨", "created_at": 1758624000.1 }
```

### 查询用户
```
GET /api/users/{user_id}
```
→ `200` 同结构。

## 3. 视频

### 上传视频
```
POST /api/videos
Content-Type: multipart/form-data; boundary=...

--boundary
Content-Disposition: form-data; name="creator_id"

b3c1...
--boundary
Content-Disposition: form-data; name="caption"

3分钟搞定深夜食堂 #美食 #家常菜
--boundary
Content-Disposition: form-data; name="file"; filename="clip.mp4"
Content-Type: video/mp4

<二进制>
--boundary--
```
→ `201`
```json
{
  "id": "9f2a...", "creator_id": "b3c1...",
  "caption": "3分钟搞定深夜食堂 #美食 #家常菜",
  "tags": ["美食", "家常菜"],
  "duration_ms": 6000, "width": 360, "height": 640,
  "size_bytes": 48210, "sha256": "a1b2...",
  "storage_path": "var/media/2026/09/9f2a....mp4",
  "status": "published", "created_at": 1758624000.5,
  "views": 0, "completes": 0, "likes": 0, "shares": 0
}
```

`duration_ms` / `width` / `height` 由服务端 ffprobe 探测，客户端无法影响。

### 视频列表
```
GET /api/videos
```
→ `200` `{ "videos": [ ... ] }`

### 视频详情
```
GET /api/videos/{video_id}
```

### 媒体流（支持 Range）
```
GET /api/videos/{video_id}/file
Range: bytes=0-99        # 可选
```
→ `200`（无 Range）或 `206`（有 Range，含 `Content-Range: bytes 0-99/48210`）

## 4. 互动

### 上报互动
```
POST /api/engagements
Content-Type: application/json

{ "user_id": "...", "video_id": "...", "kind": "complete", "watch_ms": 4200 }
```
`kind ∈ {view, complete, like, share, skip, comment, follow}`
→ `201`
```json
{ "ok": true, "video_id": "...", "kind": "complete",
  "stats": { "views": 12, "completes": 7, "likes": 3, "shares": 1 } }
```
`kind=follow` 时自动建立关注边（创作者 = 该视频作者）。

### 关注
```
POST /api/follows
Content-Type: application/json

{ "follower_id": "...", "followee_id": "..." }
```
→ `201`

## 5. 推荐流（核心）

```
GET /api/feed?user_id={uuid}&size=10&seed=42
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `user_id` | ✅ | 观众 UUID |
| `size` | ❌ | 返回条数，1~50，默认 10 |
| `seed` | ❌ | 随机种子；给定后结果可复现（用于测试与 A/B 复现） |

→ `200`
```json
{
  "user_id": "b3c1...",
  "cold_start": false,
  "size": 2,
  "weight_version": { "aff": 0.45, "pop": 0.2, "fresh": 0.15, "social": 0.1, "qual": 0.1 },
  "items": [
    {
      "video_id": "9f2a...",
      "creator_id": "77de...",
      "caption": "空气炸锅版脆皮五花肉 #美食 #懒人食谱",
      "tags": ["美食", "懒人食谱"],
      "duration_ms": 6000,
      "score": 0.482137,
      "features": { "aff": 0.7123, "pop": 0.331, "fresh": 0.8601, "social": 0.0, "qual": 0.4512 },
      "recall_routes": ["cf", "tag"],
      "reason": "标签兴趣匹配主导（召回路径：标签匹配/协同过滤）",
      "is_exploration": false
    }
  ]
}
```

**打分公式**（`weight_version` 与 `config.RANK_WEIGHTS` 一致，可在不改代码的情况下调参）：

```
score = 0.45·aff + 0.20·pop + 0.15·fresh + 0.10·social + 0.10·qual
```

`features` 与 `reason` 为可解释性字段，用于运营归因与线上问题排查。

## 6. 运维

### 重建协同过滤相似度
```
POST /api/admin/rebuild-cf
```
→ `200` `{ "ok": true, "item_sim_pairs": 128 }`

重建口径：item-item 共现余弦 `co_users / sqrt(pop_a × pop_b)`。
行为稀疏场景下该路由只做补充，主力是标签匹配与热门新鲜。

## 7. 演示页

```
GET /
```
返回一张服务端渲染的已发布视频列表页（暗色主题），无需前端构建，便于快速确认服务状态。
