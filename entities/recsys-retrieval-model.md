---
title: PhoenixRetrievalModel(召回模型)
created: 2026-05-16
updated: 2026-05-16
type: entity
tags: [phoenix, retrieval, two-tower, user-tower, candidate-tower, jax, haiku]
sources: [phoenix/recsys_retrieval_model.py, phoenix/recsys_model.py]
---

# PhoenixRetrievalModel(召回模型)

## 是什么

`PhoenixRetrievalModel` 是 Phoenix 双塔召回模型的代码构件 —— 一个 Haiku/JAX 的 `hk.Module`,定义于 `phoenix/recsys_retrieval_model.py:159`。本页讲类结构与方法;双塔召回的工作原理见 [[phoenix-retrieval]]。

它**复用** [[recsys-model|recsys_model.py]] 的公共件:`HashConfig`、`RecsysBatch`、`RecsysEmbeddings`、`block_user_reduce`、`block_history_reduce`(`recsys_retrieval_model.py:24-30` import)。

## 配置:PhoenixRetrievalModelConfig

`@dataclass`,`recsys_retrieval_model.py:115-156`:

```python
@dataclass
class PhoenixRetrievalModelConfig:
    model: TransformerConfig          # 与排序模型同款 Grok transformer
    emb_size: int
    history_seq_len: int = 128
    candidate_seq_len: int = 32
    fprop_dtype: Any = jnp.bfloat16
    hash_config: HashConfig = None    # __post_init__ 兜底 HashConfig()
    product_surface_vocab_size: int = 16
    enable_linear_proj: bool = True   # 候选塔是否用 MLP 投影
```

文档注释明确:"This model uses the same transformer architecture as the Phoenix ranker for encoding user representations." `make()` 构造 `PhoenixRetrievalModel`。

## CandidateTower(候选塔)

`@dataclass` `hk.Module`,`recsys_retrieval_model.py:46-112`。把"帖嵌入 + 作者嵌入"投影到与用户表示共享的空间,两种模式:

| 模式 | `enable_linear_proj` | 行为 |
|------|---------------------|------|
| MLP 投影 | `True`(默认) | reshape → `proj_1 [in, 2D]` → `silu` → `proj_2 [2D, D]` → L2 归一化 |
| 均值池化 | `False` | 沿哈希维 `mean` → L2 归一化(更省参数,表达力弱) |

输入形状 `[B, C, num_hashes, D]` 或 `[B, num_hashes, D]`,输出 `[B, C, D]` 或 `[B, D]`,**始终 L2 归一化** —— 这样点积即余弦相似度。

## PhoenixRetrievalModel 方法

`@dataclass` `hk.Module`,`recsys_retrieval_model.py:159-388`。

| 方法 | 作用 |
|------|------|
| `_get_action_embeddings(actions)` | 多热动作 → 嵌入(与排序模型同款 `2*actions-1` 投影) |
| `_single_hot_to_embeddings(...)` | 类别索引 → one-hot @ 嵌入表 |
| `build_user_representation(batch, embeddings)` | **用户塔**:编码 user+history,返回 `(user_representation [B,D], user_norm [B,1])` |
| `build_candidate_representation(batch, embeddings)` | **候选塔**:经 `CandidateTower` 投影,返回 `(candidate_representation [B,C,D], padding_mask)` |
| `_retrieve_top_k(user_rep, corpus, top_k, mask)` | 点积相似度 + `jax.lax.top_k` |
| `__call__(batch, embeddings, corpus_embeddings, top_k, corpus_mask)` | 完整召回,返回 `RetrievalOutput` |

### build_user_representation

`recsys_retrieval_model.py:221-291`。用户塔流程:

```python
# block_user_reduce + block_history_reduce(复用 recsys_model)
embeddings = concat([user_embeddings, history_embeddings], axis=1)
model_output = self.model(embeddings, padding_mask, candidate_start_offset=None)  # 跑 transformer
# 对有效位置做掩码均值池化
user_representation = sum(user_outputs * mask) / max(sum(mask), 1.0)
# L2 归一化
user_representation = user_representation / user_norm
```

关键:`candidate_start_offset=None` —— 召回**不用候选隔离掩码**,因为序列里没有候选段;transformer 输出对所有有效位置做**均值池化**压成一个 `[B, D]` 向量。

### \_\_call\_\_ 与 _retrieve_top_k

`recsys_retrieval_model.py:330-388`:

```python
user_representation, _ = self.build_user_representation(batch, recsys_embeddings)
scores = jnp.matmul(user_representation, corpus_embeddings.T)   # [B, N]
if corpus_mask is not None:
    scores = jnp.where(corpus_mask[None, :], scores, -INF)      # 无效语料置 -1e12
top_k_scores, top_k_indices = jax.lax.top_k(scores, top_k)
```

把无效语料的分数压到 `-INF`,是为了保证它们在紧随其后的 `top_k` 里绝不会被选中(相当于从候选集里彻底剔除)。返回 `RetrievalOutput(user_representation, top_k_indices, top_k_scores)`。

## 输出类型

```python
class RetrievalOutput(NamedTuple):
    user_representation: jax.Array   # [B, D] 归一化用户向量
    top_k_indices: jax.Array         # [B, K] 命中的语料下标
    top_k_scores: jax.Array          # [B, K] 相似度分
```

常量:`EPS = 1e-12`(归一化下界)、`INF = 1e12`(掩码用)。

## 与排序模型的异同

| 维度 | 召回 `PhoenixRetrievalModel` | 排序 [[recsys-model\|PhoenixModel]] |
|------|------|------|
| 序列构成 | user + history | user + history + candidate |
| transformer 调用 | `candidate_start_offset=None` | 传 offset,启用候选隔离掩码 |
| 用户侧输出 | 全位置均值池化 → 一个向量 | 只取候选段位置 |
| 候选侧 | 独立 `CandidateTower` | 拼进序列,无独立塔 |
| 最终产物 | top-K 下标 + 相似度 | 每候选多行为 logits |

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 双塔 | 用户塔 + 候选塔分离 | 候选嵌入可离线预算成语料矩阵,在线只算用户塔 + 点积,百万级可检索 |
| 复用排序的 transformer | 用户塔用同款 Grok transformer | 用户编码能力与排序一致,减少架构分裂 |
| L2 归一化 | 两塔输出都归一化 | 点积 = 余弦相似度,可直接 `top_k` |
| 候选塔双模式 | `enable_linear_proj` 切换 | MLP 表达力强;均值池化省参数,按需取舍 |

## 源码锚点

- `phoenix/recsys_retrieval_model.py:46-112` —— `CandidateTower`
- `phoenix/recsys_retrieval_model.py:221-291` —— `build_user_representation`
- `phoenix/recsys_retrieval_model.py:330-388` —— `__call__` 与 `_retrieve_top_k`
- `phoenix/recsys_model.py:147-268` —— 复用的 `block_user_reduce` / `block_history_reduce`

## 相关页面

- [[phoenix-retrieval]] —— 双塔召回的工作原理
- [[recsys-model]] —— 提供公共件、共用 transformer 的排序模型
- [[grok-transformer]] —— 用户塔的 transformer 骨架
- [[hash-based-embeddings]] —— 两塔输入的哈希嵌入
- [[run-pipeline]] —— 端到端把召回结果喂给排序
