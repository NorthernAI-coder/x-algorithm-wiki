---
title: PostStore
created: 2026-05-16
updated: 2026-05-16
type: entity
tags: [thunder, post-store, in-memory, in-network, retention]
sources: [thunder/posts/post_store.rs]
---

# PostStore

## 是什么

`PostStore` 是 Thunder 的核心内存数据结构 —— 一个按用户分组的线程安全帖子存储,为站内(关注的人发的)帖子提供亚毫秒级查询。定义于 `thunder/posts/post_store.rs:39`。

## 结构体定义

```rust
// thunder/posts/post_store.rs:38-53
#[derive(Clone)]
pub struct PostStore {
    /// 按 post_id 索引的完整帖子数据
    posts: Arc<DashMap<i64, LightPost>>,
    /// user_id → 原创帖(非回复非转发)的 TinyPost 队列
    original_posts_by_user: Arc<DashMap<i64, VecDeque<TinyPost>>>,
    /// user_id → 回复与转发的 TinyPost 队列
    secondary_posts_by_user: Arc<DashMap<i64, VecDeque<TinyPost>>>,
    /// user_id → 视频帖的 TinyPost 队列
    video_posts_by_user: Arc<DashMap<i64, VecDeque<TinyPost>>>,
    /// 删除墓碑表
    deleted_posts: Arc<DashMap<i64, bool>>,
    /// 保留期(秒)
    retention_seconds: u64,
    /// get_posts_by_users 迭代的请求超时(0 = 不超时)
    request_timeout: Duration,
}
```

所有字段用 `Arc<DashMap>` 包裹 —— `DashMap` 提供分片锁的并发哈希表,`Arc` 让 `PostStore` 可廉价 `Clone` 并跨线程共享(摄入线程写、请求线程读)。

## 三层数据布局

```mermaid
flowchart TB
    subgraph 时间线索引
        OP["original_posts_by_user<br/>user_id → VecDeque&lt;TinyPost&gt;"]
        SP["secondary_posts_by_user<br/>回复 + 转发"]
        VP["video_posts_by_user<br/>视频帖"]
    end
    subgraph 主数据
        P["posts<br/>post_id → LightPost"]
    end
    OP -.TinyPost.post_id 查.-> P
    SP -.-> P
    VP -.-> P
```

**为什么分两层**:per-user 队列只存 `TinyPost`(16 字节:`post_id` + `created_at`),按时间排序;完整 `LightPost` 单独存一份。查询时先在用户队列里按时间筛出候选 ID,再回 `posts` 表取完整数据 —— 时间线遍历轻量,完整数据不重复。

### TinyPost

```rust
// thunder/posts/post_store.rs:20-24
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TinyPost {
    pub post_id: i64,
    pub created_at: i64,
}
```

`LightPost` 在 protobuf schema(`in-network.proto`)中定义,含 `post_id`、`author_id`、`created_at`、`in_reply_to_post_id`、`in_reply_to_user_id`、`is_retweet`、`is_reply`、`source_post_id`、`source_user_id`、`has_video`、`conversation_id`。

## 构造

| 方法 | 说明 |
|------|------|
| `new(retention_seconds: u64, request_timeout_ms: u64)` | 指定保留期与请求超时 |
| `Default` | 保留期 2 天(`2*24*60*60`),无超时(`post_store.rs:521-526`) |

## 写入方法

### `insert_posts(&self, posts: Vec<LightPost>)`

`post_store.rs:86-101`。两步预处理后写入:

1. **过滤**:只保留 `created_at` 在过去 `retention_seconds` 内、且不在未来的帖
2. **排序**:按 `created_at` 升序
3. 调 `insert_posts_internal`

`insert_posts_internal`(`post_store.rs:115-168`)对每条帖:

- 若 `post_id` 在 `deleted_posts` 墓碑表 → 跳过(化解删除早于创建的竞态)
- 写入 `posts` 主表;若已存在则跳过(不重复加时间线)
- 按 `is_original = !is_reply && !is_retweet` 推入 `original_posts_by_user` 或 `secondary_posts_by_user`
- **视频资格**:`has_video` 为真,或"转发了一条有视频的非回复帖";回复一律不算视频帖 → 推入 `video_posts_by_user`

### `mark_as_deleted(&self, posts: Vec<TweetDeleteEvent>)`

`post_store.rs:69-83`。从 `posts` 主表移除,写入 `deleted_posts` 墓碑表,并把删除记录挂到特殊 user `DELETE_EVENT_KEY` 的队列下(以便墓碑也能被裁剪)。

## 查询方法

### `get_all_posts_by_users(...) -> Vec<LightPost>`

`post_store.rs:193-225`。给定关注用户列表,聚合其 `original` + `secondary` 帖。

### `get_videos_by_users(...) -> Vec<LightPost>`

`post_store.rs:171-190`。只取 `video_posts_by_user`。

### `get_posts_from_map(...)`

`post_store.rs:228-328`,共享的查询核心。逐用户:

1. 超时检查 —— `request_timeout` 非零且已超时则中断并记 `POST_STORE_REQUEST_TIMEOUTS`
2. 从用户队列**逆序**(最新优先)迭代,过滤 `exclude_tweet_ids`,最多扫 `MAX_TINY_POSTS_PER_USER_SCAN` 条
3. 回 `posts` 表取 `LightPost`(立即拷贝出值以尽快释放读锁,避免嵌套锁死锁)
4. 过滤 `deleted_posts` 中的帖;过滤"请求者自己转发过的源帖"
5. 对 secondary(`following_users` 非空时):只保留回复了关注用户原创帖、或同会话中回复关注用户的回复
6. 每用户最多取 `max_per_user` 条

## 维护方法

| 方法 | 说明 |
|------|------|
| `finalize_init()` | 启动时:排序所有用户队列 + 裁剪 + 清理墓碑帖(`post_store.rs:103-113`) |
| `trim_old_posts()` | 在 `spawn_blocking` 中,从各队列队首弹出超期帖、同步删主表、收缩队列容量、移除空用户(`post_store.rs:409-476`) |
| `start_auto_trim(interval_minutes)` | 后台任务,每 `interval_minutes` 调一次 `trim_old_posts` |
| `start_stats_logger()` | 每 5 秒输出用户数/帖数/删除数到 Prometheus |
| `sort_all_user_posts()` | 按 `created_at` 排序每个用户队列 |
| `clear()` | 清空全部 |

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 两层存储 | `TinyPost` 时间线 + `LightPost` 主表 | 时间线遍历只碰 16 字节小结构,完整数据不在多个用户队列间重复 |
| 三个队列分类 | 原创 / 回复转发 / 视频 分开 | 不同请求(For You、视频流)直接命中对应队列,免运行时筛选 |
| `DashMap` | 分片锁并发表 | 摄入线程高频写、请求线程高频读,分片锁减少争用 |
| 墓碑表 | `deleted_posts` 记删除 | 化解删除事件早于创建事件到达的乱序 |
| 查询逐用户超时 | `request_timeout` 中断 | 关注数极多的用户不会让单个请求无限延迟 |
| 每用户扫描上限 | `MAX_TINY_POSTS_PER_USER_SCAN` | 不为不活跃用户回溯过深 |
| 取值即拷贝 | 取 `LightPost` 后立刻 `*r.value()` | 尽快释放 `DashMap` 读锁,避免与写者形成嵌套锁死锁 |

## 源码锚点

- `thunder/posts/post_store.rs:38-67` —— 结构体与构造
- `thunder/posts/post_store.rs:115-168` —— `insert_posts_internal` 写入与视频资格
- `thunder/posts/post_store.rs:228-328` —— `get_posts_from_map` 查询核心
- `thunder/posts/post_store.rs:409-476` —— `trim_old_posts` 裁剪

## 相关页面

- [[thunder-in-network-store]] —— `PostStore` 之上的站内候选服务
- [[thunder-kafka-ingestion]] —— 谁向 `PostStore` 写入(Kafka 摄入)
- [[home-mixer-orchestration]] —— `ThunderSource` 经 gRPC 消费 Thunder
- [[system-architecture]] —— Thunder 在系统中的位置
