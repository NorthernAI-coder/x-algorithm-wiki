---
title: x-algorithm-wiki 初始创建（2026-05-16）
created: 2026-05-16
updated: 2026-05-16
type: changelog
tags: [changelog]
---

# x-algorithm-wiki 初始创建

基于 `xai-org/x-algorithm` 开源仓库(commit `0bfc279`,2026-05-15 release)源码深度分析,创建本 wiki。

## 范围

X "For You" 信息流推荐系统的五大组件:

- **home-mixer**(Rust)—— 编排层
- **candidate-pipeline**(Rust)—— 可复用流水线框架
- **thunder**(Rust)—— 站内帖子内存库
- **phoenix**(Python/JAX)—— ML 召回与排序
- **grox**(Python)—— 内容理解服务

## 产出

| 指标 | 数值 |
|------|------|
| 总页数 | 21(16 概念 + 5 实体) |
| 总行数 | 4900+ |
| 源码版本 | `xai-org/x-algorithm` @ `0bfc279` |

### 概念页(16)

总览 1:`system-architecture`。
在线服务 5:`candidate-pipeline-framework`、`home-mixer-orchestration`、`scoring-and-ranking`、`filtering-pipeline`、`ads-blending`。
Thunder 2:`thunder-in-network-store`、`thunder-kafka-ingestion`。
Phoenix 5:`phoenix-retrieval`、`phoenix-ranking`、`candidate-isolation-masking`、`grok-transformer`、`hash-based-embeddings`。
Grox 3:`grox-architecture`、`grox-classifiers`、`multimodal-embedders`。

### 实体页(5)

`candidate-pipeline`、`recsys-model`、`recsys-retrieval-model`、`post-store`、`run-pipeline`。

## 方法

- 每页结论均追溯到 x-algorithm 源码,附 `文件:行号` 锚点
- 全部页面与组件级源码逐一核对验证
- 所有 `[[wiki-link]]` 交叉链接经检查均有效

## 核对中发现并记录的源码与文档出入

- **mini 模型尺寸**:顶层 `README.md` 写 "256-dim / 2-layer",`phoenix/README.md` 写 "128-dim / 4-layer"。代码默认值与 `phoenix/README.md` 一致,相关页面以后者为准并标注。见 [[phoenix-ranking]]。
- **打分器数量**:`README.md` 描述 Weighted / Author Diversity / OON 三个独立 Scorer;实际 `scorers/mod.rs` 只声明 `phoenix_scorer`/`ranking_scorer`/`vm_ranker` 三个,加权/多样性/OON 逻辑合并在 `RankingScorer` 内。见 [[scoring-and-ranking]]。
- **候选隔离掩码**:`phoenix/README.md` 图示称用户+历史段"双向注意力",代码 `make_recsys_attn_mask` 用 `jnp.tril`(因果)。以代码为准。见 [[candidate-isolation-masking]]。

## 相关页面

- [[system-architecture]] —— wiki 入口页
