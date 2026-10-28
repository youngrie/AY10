# 实验输出目录

`src/train.py` 与 `src/evaluate.py` 的产出都写在这里（CSV 已在 `.gitignore` 中排除）。

## 怎么生成

```bash
# 训练时逐回合记录指标
python src/train.py --controller qlearning --episodes 50 --out-csv results/q_s2

# 批量评估：控制器 × 场景 × 种子，并输出汇总
python src/evaluate.py --controllers random fixed_time qlearning --seeds 0 1 2
```

## 文件命名

| 文件 | 来源 | 内容 |
| --- | --- | --- |
| `q_s2_conn0_ep1.csv` | SUMO-RL 直接写出 | 每个决策步的 `system_mean_waiting_time`、`system_total_stopped` 等 |
| `eval_<场景>.csv` | `evaluate.py` | 每个 (控制器, 种子, 回合) 一行的汇总指标 |

`src/metrics.py` 会把 SUMO-RL 的 CSV 汇总成：
`avg_wait`、`avg_queue`、`max_queue`、`p95_wait`、`total_wait`、`mean_speed`、`duration`。

> 注意：CSV 是**可再生产物**，不入库。报告里的图表应从这些文件用脚本生成，
> 不要手工整理数字。

