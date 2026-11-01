# `experiments/` —— 实验配置

```
experiments/
└── configs/
    └── sample.json      # 示例配置，可直接 --config sample.json 使用
```

## 用法

```bash
python src/train.py    --config sample.json --controller qlearning --episodes 50
python src/evaluate.py --config sample.json --controllers random fixed_time queue_based
```

`--config` 也接受完整路径；只写文件名时会自动到 `experiments/configs/` 下查找。

**优先级**：命令行显式参数 > 配置文件 > `src/config.py` 的 `DEFAULT_CONFIG`。

## `sample.json` 各段含义

| 段 | 作用 | 主要字段 |
| --- | --- | --- |
| 顶层 | 运行基本参数 | `controller`、`episodes`、`seed`、`reward_fn`（`diff-waiting-time` 或 `queue`） |
| `env` | SUMO 环境 | `num_seconds`（每回合仿真秒）、`delta_time`（决策间隔）、`yellow_time`、`min_green`、`max_green`、`use_gui` |
| `agent` | Q-learning 超参 | `alpha`、`gamma`、`epsilon`、`epsilon_min`、`epsilon_decay` |
| `discretizer` | 状态分箱阈值 | `queue_edges`、`density_edges`（**观测已归一化，阈值必须 ≤ 1**） |
| `fixed_time` | 固定时长基线 | `switch_every`（每多少次决策轮转一次） |
| `queue_based` | LQF 基线 | `hold_on_min_green` |

## 新增一份配置

复制 `sample.json` 改名（如 `heavy_traffic.json`），改你想变的字段即可，
**未写的字段会自动取默认值**（深度合并，不是整段替换）。

## ⚠️ 两点注意

1. **`scenario` 字段现在会生效**：`build_env` 会据此加载
   `nets/single-intersection/<SCENARIO>.rou.xml`。命令行也可以直接覆盖：
   ```bash
   python src/train.py --config sample.json --scenario S1
   ```
2. 改 `discretizer` 前先确认观测的量纲：SUMO-RL 输出在 `[0,1]`，
   用 `(1,3,6,10)` 这类车辆数阈值会让状态全部塌缩到同一档。
