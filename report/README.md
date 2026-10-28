# 报告目录

存放最终报告的图表与正文产物。

## 计划产出

| 内容 | 来源 |
| --- | --- |
| 对比柱状图（各控制器 × S1–S4） | `results/eval_*.csv` |
| 学习曲线（Q-learning 收敛过程） | `results/*_conn0_ep*.csv` |
| 队列/相位时间序列 | 同上 |
| 主表（等待时间、队列长度、均值±标准差） | 待实现 `scripts/plot_results.py` |

> 图表应由脚本从 `results/` 的 CSV 一键生成，避免手工整理。
> 生成脚本目前**尚未实现**（见 `docs/tasks.md` 中 C 的任务）。

