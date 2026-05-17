---
title: 新增白话导览（2026-05-17）
created: 2026-05-17
updated: 2026-05-17
type: changelog
tags: [changelog]
---

# 新增白话导览

应反馈 —— 原 21 页技术性、代码性偏强,缺一层"快速理解"的通俗内容。本次新增 4 页**白话导览**(`guide/`)。

## 动机

技术页(`concepts/` + `entities/`)适合深读源码,但不适合快速建立整体认知。白话导览作为**通俗入口层**:零代码、零公式、多类比,关键处链接回技术页供深入。

## 新增页面

| 页面 | 内容 |
|------|------|
| `guide/how-it-works` | 端到端白话总览:一条帖子怎么一步步走进你的 For You |
| `guide/the-five-components` | 五大组件速览:各组件是干嘛的、为什么需要它 |
| `guide/glossary` | 术语速查表:~30 个术语的一句话通俗解释 |
| `guide/faq` | 常见疑问:读者真实疑问 14 条 |

## 配套改动

- `SCHEMA.md`:新增 `guide` 页面类型与「Guide Pages」章(含"核心结论须可追溯"规定);标签体系 Meta 增加 `guide`/`overview`/`glossary`/`faq`
- `index.md`:顶部新增「白话导览(Guide)」分类
- `README.md`:目录新增「白话导览 · 先读这个」;徽章与统计更新为 25 页
- `concepts/system-architecture.md`:相关页面增加到 `[[how-it-works]]` 的链接

## 可追溯性(出处)

白话页虽不放代码,核心结论仍须可追溯:

- 每页 `sources` frontmatter 列出主要依据的源码文件(不再只写 `README.md`)
- 每页正文末尾设「出处」一节:`how-it-works` / `the-five-components` 用表格把每条核心结论对应到技术页 + 关键源码文件;`glossary` / `faq` 借每行「详见」链到带源码锚点的技术页
- 精确 `文件:行号` 统一收敛在技术页的「源码锚点」一节,白话页指向技术页、不重复行号

## 规模变化

| 指标 | 变化 |
|------|------|
| 总页数 | 21 → 25(+4 白话导览) |
| 页面类型 | concept / entity / changelog → 增加 guide |

## 相关页面

- [[how-it-works]] —— 新增的白话总览入口
- [[2026-05-16-initial-creation]] —— 上一次:基于源码初始创建 21 页
