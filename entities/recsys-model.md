---
title: PhoenixModel(排序模型)
created: 2026-05-16
updated: 2026-05-16
type: entity
tags: [phoenix, ranking, transformer, embedding, jax, haiku]
sources: [phoenix/recsys_model.py]
---

# PhoenixModel(排序模型)

## 是什么

`PhoenixModel` 是 Phoenix 排序模型的代码构件 —— 一个基于 Haiku/JAX 的 `hk.Module`,定义于 `phoenix/recsys_model.py:395`。本页讲它的类结构与方法;排序的工作原理见 [[phoenix-ranking]]。

`recsys_model.py` 还定义了召回模型复用的公共件:`HashConfig`、`RecsysBatch`、`RecsysEmbeddings`、`block_user_reduce` / `block_history_reduce`(被 [[recsys-retrieval-model]] import)。

## 配置:PhoenixModelConfig

`@dataclass`,`recsys_model.py:335-392`:

```python
@dataclass
class PhoenixModelConfig:
    model: TransformerConfig          # Grok transformer 配置
    emb_size: int
    num_actions: int
    history_seq_len: int = 128
    candidate_seq_len: int = 32
    fprop_dtype: Any = jnp.bfloat16
    hash_config: HashConfig = None    # __post_init__ 兜底为 HashConfig()
    product_surface_vocab_size: int = 16
    post_age_granularity_mins: int = 60
    num_continuous_actions: int = 8
    continuous_action_hidden_dim: int = 64
    continuous_action_config: ContinuousActionConfig = None
    use_ip_address: bool = False
    right_anchored_rope: bool = False
    mask_neg_feedback_on_negatives: bool = True
```

- `post_age_vocab_size`(property)= `POST_AGE_MAX_MINUTES // post_age_granularity_mins + 2` = `4800/60 + 2 = 82`
- `initialize()` 置 `_initialized = True`;`make()` 构造 `PhoenixModel`(内部 `self.model.make()` 实例化 transformer)

### 辅助配置

| 类型 | 字段 | 说明 |
|------|------|------|
| `HashConfig` | `num_user_hashes=2`、`num_item_hashes=2`、`num_author_hashes=2`、`num_ip_hashes=0` | 各实体哈希函数数量 |
| `NormConfig` | `norm_scale=30.0`、`use_log=False` | 连续值归一化 |
| `ContinuousActionConfig` | `loss_weight`、`loss_type="mae"`、`tweedie_power=1.5`、`norm_config` | 连续动作损失配置 |

## 输入/输出类型

| 类型 | 种类 | 字段 |
|------|------|------|
| `RecsysBatch` | `NamedTuple` | `user_hashes`、`history_post_hashes`、`history_author_hashes`、`history_actions`、`history_product_surface`、`candidate_post_hashes`、`candidate_author_hashes`、`candidate_product_surface`,+ 可选 `history_continuous_actions`、`candidate_impr_ts`、`candidate_post_creation_ts`、`user_ip_hashes` |
| `RecsysEmbeddings` | `@dataclass` | `user_embeddings`、`history_post_embeddings`、`candidate_post_embeddings`、`history_author_embeddings`、`candidate_author_embeddings`,+ 可选 `user_ip_embeddings` |
| `RecsysModelOutput` | `NamedTuple` | `logits`、`continuous_preds` |

设计要点:`RecsysBatch` 只装**哈希值**(特征),`RecsysEmbeddings` 装**查表后的嵌入**。两者分离 —— 嵌入查表在模型外完成,模型内只做组合与 transformer。

## block_*_reduce 函数(模块级)

把"多个哈希嵌入 + 各类成分"压成 D 维序列,排序与召回共用:

```python
# recsys_model.py:147 —— 用户段
block_user_reduce(user_hashes, user_embeddings, num_user_hashes, emb_size, ...)
    -> (user_embedding [B,1,D], user_padding_mask [B,1])

# recsys_model.py:200 —— 历史段
block_history_reduce(history_post_hashes, history_post_embeddings,
    history_author_embeddings, history_product_surface_embeddings,
    history_actions_embeddings, num_item_hashes, num_author_hashes, ...)
    -> (history_embedding [B,S,D], history_padding_mask [B,S])

# recsys_model.py:271 —— 候选段
block_candidate_reduce(candidate_post_hashes, candidate_post_embeddings,
    candidate_author_embeddings, candidate_product_surface_embeddings, ...)
    -> (candidate_embedding [B,C,D], candidate_padding_mask [B,C])
```

每个 reduce 把多哈希嵌入 reshape 成 `[..., num_hashes*D]`、与其它成分 `concatenate`,再经一个学习投影矩阵(`proj_mat_1`/`proj_mat_3`/`proj_mat_2`)压回 D 维。padding 掩码由"首个哈希值是否为 0"决定(哈希 0 保留给 padding)。

## PhoenixModel 方法

`@dataclass` `hk.Module`,`recsys_model.py:395-680`。

| 方法 | 作用 |
|------|------|
| `_get_action_embeddings(actions)` | 多热动作 → 嵌入;`2*actions-1` 映射到 ±1 后投影 |
| `_single_hot_to_embeddings(input, vocab, D, name)` | 类别索引 → one-hot @ 嵌入表 |
| `_get_unembedding()` | 取 `unembeddings` 参数 `[emb_size, num_actions]` |
| `_get_continuous_head()` | 取 `continuous_unembeddings` 参数 `[emb_size, num_continuous_actions]` |
| `_project_continuous_value_to_embedding(...)` | 连续值 → 归一化 → 2 层 MLP(gelu)→ 嵌入 |
| `build_inputs(batch, embeddings)` | 拼 `[用户\|历史\|候选]`,返回 `(embeddings, padding_mask, candidate_start_offset)` |
| `__call__(batch, embeddings)` | 完整前向,返回 `RecsysModelOutput` |

### build_inputs

`recsys_model.py:520-626`。产出 `[B, 1+history_len+num_candidates, D]` 的嵌入序列、对应 padding 掩码、以及 `candidate_start_offset = 1 + S`。历史段会注入 `dwell_time`(取 `history_continuous_actions[:, :, 1]`)的连续嵌入;候选段会注入帖龄桶嵌入。

### \_\_call\_\_

`recsys_model.py:628-680`。流程:`build_inputs` → (可选)`right_anchored_rope_positions` → `self.model(...)` 跑 transformer → `layer_norm` → 抽取 `out_embeddings[:, candidate_start_offset:, :]` → 离散头得 `logits [B,C,num_actions]`、连续头得 `continuous_preds [B,C,num_continuous]`(经 sigmoid)。

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 特征与嵌入分离 | `RecsysBatch`(哈希)+ `RecsysEmbeddings`(嵌入)两个容器 | 嵌入查表可在模型外/不同设备完成,模型只管组合与计算 |
| reduce 函数模块级 | `block_*_reduce` 不绑在类上 | 召回模型可直接 import 复用,排序/召回共享同一套压缩逻辑 |
| 配置自带 `make()` | `PhoenixModelConfig.make()` 造模型 | 配置即工厂,统一初始化 transformer 与模型 |
| `bfloat16` 前向 | `fprop_dtype = jnp.bfloat16` | 推理省显存、提吞吐;参数仍以 fp32 存 |

## 源码锚点

- `phoenix/recsys_model.py:335-392` —— `PhoenixModelConfig`
- `phoenix/recsys_model.py:147-332` —— `block_user_reduce` / `block_history_reduce` / `block_candidate_reduce`
- `phoenix/recsys_model.py:520-626` —— `build_inputs`
- `phoenix/recsys_model.py:628-680` —— `__call__`

## 相关页面

- [[phoenix-ranking]] —— 排序模型的工作原理
- [[recsys-retrieval-model]] —— 复用本文件公共件的召回模型
- [[grok-transformer]] —— `PhoenixModelConfig.model` 指向的 transformer
- [[hash-based-embeddings]] —— `block_*_reduce` 处理的哈希嵌入
- [[candidate-isolation-masking]] —— `candidate_start_offset` 的用途
