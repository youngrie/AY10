# `proposal/` —— 开题报告

| 文件 | 说明 |
| --- | --- |
| `proposal.tex` | 方案部分正文（LaTeX 源码） |
| `proposal.pdf` | 编译产物，用于预览 |

## 编译

使用 **XeLaTeX**（因为用了 `ctex` 宏包，pdfLaTeX 会报错）：

```bash
cd proposal
xelatex proposal.tex
```

在 Overleaf 中：*Menu → Compiler → XeLaTeX*。

> ⚠️ 编译会生成 `.aux` / `.log` / `.fls` / `.fdb_latexmk` / `.synctex.gz`，
> 这些中间文件已由 `.gitignore` 排除，**不要提交**（需要时重新编译即可）。

## 内容范围

- 本项目负责的**方案部分**：项目目标、环境选择、算法设计、基线、评估。
- 研究背景与相关工作由另一位组员负责，**不在本文件内**。
- 全文限制 2 页，本文件约 1 页；改动篇幅请留意是否溢出。

## 与代码的关系

`proposal.tex` 描述的两阶段路线与当前实现一致：

- 阶段一：SUMO + 4 相位路网 + 表格型 Q-learning + 固定时长 / LQF 基线
- 阶段二：DQN 与表格法对照

若技术路线发生实质变化（例如相位数量、车道结构），需要同步更新
`proposal.tex` 与 `../plan.md`。
