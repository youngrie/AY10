# 实验输出目录

`src/train.py` 与 `src/evaluate.py` 的产出都写在这里。**全部 CSV 都不入库**
（`.gitignore` 已排除），属于可再生产物。

## 目录里通常只有两类文件

| 文件 | 来源 | 是否保留 |
| --- | --- | --- |
| `eval_<场景>.csv` | `evaluate.py` | ✅ **保留**，每行 = 一次运行（控制器 × 种子 × 回合）的汇总指标 |
| `S2_queue_based_s0_e1_conn6_ep0.csv` | SUMO-RL 直接写出 | ❌ **默认删除**，只有加 `--keep-raw` 才留 |

> 为什么默认删原始文件：SUMO-RL 的文件名带 TraCI 连接标签（`conn0`、`conn1`…），
> **每次评估编号都会递增**，旧文件不会被覆盖。36 次运行 ≈ 2 MB，
> 反复评估会无限膨胀。汇总指标已经写进 `eval_*.csv`，原始逐步数据只在
> **画时间序列/学习曲线**时才需要。

## 怎么生成

```bash
# 三个基线 × 四个场景 × 3 种子（约 2 分钟）
python src/evaluate.py --scenarios S1 S2 S3 S4 \
    --controllers random fixed_time queue_based --seeds 0 1 2

# 需要保留原始逐步 CSV（例如要画队列/相位时间序列）
python src/evaluate.py --scenarios S1 --controllers queue_based --seeds 0 --keep-raw

# 训练时逐回合记录（学习曲线用）
python src/train.py --scenario S2 --controller qlearning \
    --episodes 100 --out-csv results/q_s2 --save results/q_s2.pkl
```

## `eval_<场景>.csv` 的列

`scenario, controller, seed, episode, episode_return, steps, avg_wait, avg_queue,
max_queue, p95_wait, total_wait, mean_speed, duration, n_samples`

指标含义见 `docs/INTERFACE.md` 第 4 节。

## ⚠️ 是"合并写"不是"覆盖写"

`evaluate.py` 会把新结果**合并**进已有的 `eval_<场景>.csv`：
同一个 `(scenario, controller, seed, episode)` 的行被替换，其余保留。

所以可以分多次跑，例如先跑三个基线，之后单独补一个控制器：

```bash
python src/evaluate.py --scenarios S1 --controllers queue_based --seeds 0 1 2
# -> 已有 random / fixed_time 的行不会丢失，末尾提示"累计 N 行"
```

## 当前结果（3 种子，平均等待 s）

| 场景 | random | fixed_time | queue_based |
| --- | --- | --- | --- |
| S1 (600) | 7.75 | 1.79 | **0.64** |
| S2 (1200) | 8.29 | 1.68 | **1.26** |
| S3 (2000) | 8.99 | 1.88 | **1.76** |
| S4 (1200 不均衡) | 9.14 | 1.97 | **1.50** |

完整指标（队列长度、最大队列、平均速度）与校准过程见 `docs/baselines.md`。

## 清理

```bash
# 只留汇总表
Remove-Item results\S*_conn*_ep*.csv

# 全部重来
Remove-Item results\*.csv
```
