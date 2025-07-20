---
title: 泰迪杯2024数据挖掘比赛B题【解题方案】
tags:
  - 行动盒
  - 数据科学
categories:
  - 计算机科学
date: 2024-05-13
---

参考项目：[Chinese-CLIP](https://github.com/OFA-Sys/Chinese-CLIP)

项目作品：[2024泰迪杯数据挖掘中比赛的论文与代码等资源。 (github.com)](https://github.com/JayChou404/DataMning-Taidibei-B-2024)

## 简介

本次比赛，我们直接采用现有的多模态模型进行微调，这个模型就是 CLIP 了，但是我们并没有直接使用 CLIP 模型，而是寻找到了一个开源的中文项目。

> Chinese-CLIP 是一次极其朴素的开源，没错就是 CLIP 的汉化，旨在推动中文社区多模态发展。
>
> 相比于 CLIP 模型，Chinese-CLIP 更适合我们的应用和微调，因为原始的 CLIP 模型只支持英文，对于我们的中文应用来说不够友好。Chinese-CLIP 很好地弥补了这方面的不足，它使用了**大量的中文 - 文图对进行训练**，与 CLIP 模型架构完全一致。
>
> ## 关于 Chinese-CLIP
>
> **Chinese-CLIP 延续了 CLIP 的模型架构**，使用了不同的训练方式以及全新的中文数据集，即在双流架构和对比学习的支持下，能够有效地整合中文的图像和文本信息到一个共享的嵌入空间，并拥有处理多模态数据的能力。初始阶段以预训练的方式设定了两种编码器：**一种是 CLIP 的视觉编码器，另一种是中文版的 RoBERTa 文本编码器**。
> ![image.png](https://s2.loli.net/2024/05/13/HqsU1RPaWzXrl6m.png)
{: .prompt-info }

## 参考文献

- [多模态表征—CLIP及中文版Chinese-CLIP：理论讲解、代码微调与论文阅读 - 知乎 (zhihu.com)](https://zhuanlan.zhihu.com/p/690361706)
- [OFA-Sys/Chinese-CLIP: Chinese version of CLIP which achieves Chinese cross-modal retrieval and representation generation. (github.com)](https://github.com/OFA-Sys/Chinese-CLIP)
- [[2211.01335v2] Chinese CLIP: Contrastive Vision-Language Pretraining in Chinese (arxiv.org)](https://arxiv.org/abs/2211.01335v2)
