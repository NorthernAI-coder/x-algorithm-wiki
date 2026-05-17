---
title: 新增选帖过程页（2026-05-17）
created: 2026-05-17
updated: 2026-05-17
type: changelog
tags: [changelog]
---

# 新增选帖过程页

应反馈 —— wiki 缺一页专门讲"如何选择帖子、选帖过程"。打分之后怎么定下最终展示的几十条,原先散落在多页里,没有独立成页。本次新增 1 技术页 + 1 白话页。

## 动机

读者问:"如何选择帖子、选帖过程这个好像没有?"

确实没有专页。选择阶段(流水线第 ⑦ 步)及其之后的成型步骤,此前分散在:

- `candidate-pipeline-framework`:只讲 `Selector` trait 的抽象签名
- `candidate-pipeline`:`execute()` 十阶段里一笔带过选择
- `filtering-pipeline`:讲了选后过滤,但没讲它前面的"选择"
- `home-mixer-orchestration`:提到 `BlenderSelector` 但未展开

读者要把"打完分→最终信息流"这段连起来,得跨四页拼。故独立成页。

## 新增页面

| 页面 | 类型 | 内容 |
|------|------|------|
| `concepts/candidate-selection` | concept | 选择阶段技术细节:`Selector` trait「排序 + 截断」骨架、`TopKScoreSelector`(内层按分取 top-K)、选后水合→选后过滤→截断到 `RESULT_SIZE`、`BlenderSelector`(外层组装) |
| `guide/how-posts-are-picked` | guide | 白话版:用"选秀收尾"类比讲清排座次→圈入围→背景调查→终审淘汰→砍名额→编排上桌 |

## 核心结论

- **选择 = 排序 + 截断**:`Selector` trait 默认 `select()` 即"按分降序排 → 截断到 `size()`"
- **两个选择器**:内层 `TopKScoreSelector` 按 `score` 取 top-K;外层 `BlenderSelector` 把 `FeedItem` 组装成信息流(不按分排序)
- **两个数量上限**:内层先选 `TOP_K_CANDIDATES_TO_SELECT`(略多),经选后过滤删减后再截断到 `RESULT_SIZE` —— 留余量,避免过滤后不够数
- **昂贵水合后置**:可见性 / 品牌安全水合放选择之后,只对会展示的入选候选做
- **落选不丢弃**:进入 `non_selected`,供 side effect 与调试使用

## 配套改动

- `index.md`:白话导览增 `[[how-posts-are-picked]]`;在线服务增 `[[candidate-selection]]`;统计更新为 27 页
- `README.md`:徽章与统计更新为 27 页;白话导览(5 页)、在线服务(6 页)各增一行
- 6 个相关页补交叉链接:`system-architecture`、`scoring-and-ranking`、`candidate-pipeline-framework`、`candidate-pipeline`、`filtering-pipeline`、`home-mixer-orchestration` 增 `[[candidate-selection]]`;`how-it-works`、`the-five-components`、`faq` 增 `[[how-posts-are-picked]]`

## 可追溯性(出处)

- 技术页 `candidate-selection` 设「源码锚点」一节,精确到 `文件:行号`
- 白话页 `how-posts-are-picked` 设「出处」表,把每条核心结论对应到技术页 + 主要源码
- 主要依据源码:`candidate-pipeline/selector.rs`、`home-mixer/selectors/top_k_score_selector.rs`、`home-mixer/selectors/blender_selector.rs`、`candidate-pipeline/candidate_pipeline.rs`、`home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs`

## 规模变化

| 指标 | 变化 |
|------|------|
| 总页数 | 25 → 27(+1 concept +1 guide) |
| 概念页 | 16 → 17 |
| 白话导览 | 4 → 5 |

## 相关页面

- [[candidate-selection]] —— 新增的选择阶段技术页
- [[how-posts-are-picked]] —— 新增的选帖过程白话页
- [[2026-05-17-plain-language-guide]] —— 上一次:新增 4 页白话导览
