# 接口文档（交付给 B / C）

> 面向两位组员的对接说明：**环境怎么用、控制器怎么写、评估怎么跑、哪些不能动**。
> 以代码现状为准；带 ⚠️ 的是当前**缺口**，需要对应负责人补齐。

---

## 0. 三分钟上手

```bash
pip install -r requirements.txt      # 版本已固定，勿升级
python scripts/check_env.py          # 需要已安装 SUMO 并设置 SUMO_HOME
python -m pytest -q                  # 119 个用例，约 5 秒，不需要 SUMO
python src/train.py --dry-run --scenario S2
```

预期输出（关键两行）：

```
observation_space : Box(0.0, 1.0, (37,), float32)
action_count      : 4  (绿灯相位个数)
```

## 1. 目录与职责

| 路径 | 归属 | 说明 |
| --- | --- | --- |
| `nets/`、`src/env/` | **A（已完成）** | 路网生成、环境封装、相位映射 |
| `src/agents/` | **B** | 离散化、Q-learning、DQN |
| `src/controllers/`、`metrics.py`、`evaluate.py`、`report/` | **C** | 基线、评估、图表、报告 |
| `src/config.py`、`src/factory.py`、`tests/` | 公共 | **改动前先说一声** |

## 2. 环境接口（B / C 都只依赖这几个函数）

```python
from src.env import build_env, reset_env, step_env, action_count

env = build_env(
    scenario="S2",                    # 路网、车流量配置，可选配置S1、S2、S3、S4
    num_seconds=3600,                 # 回合时长（仿真秒）
    delta_time=5,                     # action决策间隔（秒）
    use_gui=False,                    # True 则开 sumo-gui（可视化）/ False 则启用libsumo加速（用于加速评测指标）
    reward_fn="diff-waiting-time",    # 或 "queue"
    out_csv_name="results/run",       # 给定时记录逐步指标
    sumo_seed=0,                      # ⚠️ 必须显式传，默认是 "random"
) #返回``sumo_rl.SumoEnvironment`` 实例

obs, info = reset_env(env)
obs, reward, terminated, truncated, info = step_env(env, action)
```

构建后环境带三个只读属性，便于排查：

```python
env.ay10_scenario    # "S2"
env.ay10_route_file  # ...\nets\single-intersection\S2.rou.xml
```

> **性能提示**：`use_gui=False` 时自动启用 `LIBSUMO_AS_TRACI`（进程内仿真），
> 比 TraCI 走 TCP 快约 **50 倍**（200ms/步 → 4ms/步）。一次 3600 秒回合约 3 秒。
> 要强制用 TraCI：设置环境变量 `AY10_NO_LIBSUMO=1`。

### 2.1 观测与动作

- **动作**：`Discrete(4)` = 选第几个绿灯相位
  （0=NS直行 / 1=NS左转 / 2=EW直行 / 3=EW左转）。
- **观测**：长度 37，已**归一化到 [0,1]**：

  | 位置 | 内容 | 长度 |
  | --- | --- | --- |
  | `0 : 4` | 当前相位 one-hot | 4 |
  | `4` | 最小绿灯是否已过（0/1） | 1 |
  | `5 : 21` | 16 条进口车道的车辆密度 | 16 |
  | `21 : 37` | 16 条进口车道的排队长度 | 16 |

  车道顺序由 `env.traffic_signals[tls].lanes` 决定（形如 `n_in_0 … n_in_3, e_in_0 …`）。
  **不要假设下标对应某个方向**，需要时读 `ts.lanes` 或用 `src/env/phase_map.py`。

- ⚠️ **归一化陷阱**：分箱阈值必须是 `(0.1, 0.3, 0.6, 0.9)` 这类；
  用"车辆数"阈值（1/3/6/10）会让所有状态塌缩到同一档。

### 2.2 其他工具

```python
from src.env import action_count, describe_env, available_scenarios
action_count(env)        # 4
available_scenarios()    # ['S1','S2','S3','S4']
```

## 3. 控制器接口（B 重点）

### 3.1 `BaseController`（`src/agents/base.py`）

```python
class BaseController(ABC):
    name: str
    @abstractmethod
    def select_action(self, obs) -> int: ...
    def reset(self) -> None: ...
    def update(self, obs, action, reward, next_obs, terminated) -> None: ...
    def on_episode_end(self) -> None: ...
    def save(self, path) -> None: ...
    def load(self, path) -> None: ...
```

训练循环已在 `src/train.py` 写好，它只调用这几个方法，**不需要你改循环**。

### 3.2 工厂（`src/factory.py`）

```python
from src.factory import build_controller, CONTROLLER_NAMES
controller = build_controller("qlearning", env, config, seed=0)
```

当前支持：`random` / `fixed_time` / `queue_based` / `qlearning` / `dqn`。
新增控制器后同步 `CONTROLLER_NAMES`——有个测试会检查
`train.py --controller` 是否覆盖它（防止命令行不认新控制器）。

### 3.3 表格型 Q-learning（已可用）

```python
agent = TabularQLearning(
    n_actions=4,
    discretize=Discretizer.from_spaces(n_phases=4, obs_dim=37),
    alpha=0.1, gamma=0.95, epsilon=1.0, epsilon_decay=0.995, seed=0,
)
agent.save("results/q_s2.pkl")
agent.load("results/q_s2.pkl")
```

```bash
python src/train.py --scenario S2 --controller qlearning \
    --episodes 200 --out-csv results/q_s2 --save results/q_s2.pkl
```

`--out-csv` 会为每个回合生成 `results/q_s2_connX_epN.csv`，
用 `src/metrics.py` 可算出平均等待/队列（见第 4 节）。

### 3.4 ⚠️ 需要 B 补的缺口

| 缺口 | 现状 | 建议 |
| --- | --- | --- |
| **评估时加载 Q 表** | `evaluate.py` 无 `--model`，只能边训练边评估 | 加 `--model`：构造 `TabularQLearning` 后 `load()`，并把 `epsilon` 置 0（纯贪心） |
| **DQN 训练** | `train.py --controller dqn` 只打印"未接入" | 用 `model.learn(total_timesteps=...)`；`requirements.txt` 取消注释装 `stable-baselines3==2.3.2` |
| **状态空间过大** | 16 车道 × 5 档 = `5^16`，表格法无法收敛 | 先按方向聚合再分箱（见下） |

> **建议的起点状态设计**：`(相位, min_green, bin(q_NS), bin(q_EW), bin(q_left_NS), bin(q_left_EW))`
> ——把 16 条车道压成 4 个量，状态数从 `5^16` 降到约 `4×2×5^4 ≈ 5000`。

## 4. 指标与评估接口（C 重点）

### 4.1 从 CSV 算指标

```python
from src.metrics import find_episode_csv, load_and_summarize

path = find_episode_csv("results/q_s2", episode=1)   # 取最新那份
metrics = load_and_summarize(path)
```

| 字段 | 含义 | 来源列 |
| --- | --- | --- |
| `avg_wait` | 平均等待时间（s/车） | `system_mean_waiting_time` 逐步均值 |
| `avg_queue` | 平均队列长度（辆） | `system_total_stopped` 逐步均值 |
| `max_queue` | 最大队列长度 | 同上取最大 |
| `p95_wait` | 等待时间 95 分位 | `system_mean_waiting_time` |
| `mean_speed` | 全路网平均车速（m/s） | `system_mean_speed` |
| `duration` | 仿真时长（s） | `step` 最大值 |

### 4.2 批量评估

```bash
python src/evaluate.py --scenarios S1 S2 S3 S4 \
    --controllers random fixed_time queue_based --seeds 0 1 2
```

输出 `results/eval_<场景>.csv`（每行一个 控制器×种子×回合），终端打印 `均值 ± 标准差`。
`--seeds` 会传给 `sumo_seed`，同一种子可复现。

两个行为要知道：

- **合并写**：新结果按 `(scenario, controller, seed, episode)` 合并进已有文件，
  同一个 key 覆盖、其余保留。所以可以分多次只跑某个控制器，不会冲掉历史结果。
- **原始 CSV 默认删除**：SUMO-RL 的逐步 CSV 文件名带 TraCI 连接标签
  （`conn0/conn1/…`），每次运行都会新增、永不覆盖。汇总指标进 `eval_*.csv` 后，
  原始文件默认被删掉；**要画时间序列/学习曲线时加 `--keep-raw`**。

### 4.3 ⚠️ 需要 C 补的缺口

| 缺口 | 建议 |
| --- | --- |
| `scripts/plot_results.py` | 读 `results/eval_*.csv` → 带误差棒的对比柱状图；读 `*_conn*_ep*.csv` → 学习曲线（这些需要 `--keep-raw` 才有）；输出到 `report/*.png` |
| 报告主表 | 直接复用 `docs/baselines.md` 的表格格式 |
| 吞吐量 / 平均延误 | SUMO-RL 的 CSV **不含** `arrived`、`timeLoss`；需用 `--tripinfo-output` 额外解析 |

## 5. 配置接口

```python
from src.config import load_config, env_kwargs, resolve_config_path
config = load_config(resolve_config_path("sample.json"))
```

优先级：**命令行 > JSON 文件 > `DEFAULT_CONFIG`**。

```json
{
  "scenario": "S2",
  "controller": "qlearning",
  "episodes": 100,
  "seed": 0,
  "reward_fn": "diff-waiting-time",
  "env":         {"num_seconds": 3600, "delta_time": 5, "use_gui": false},
  "agent":       {"alpha": 0.1, "gamma": 0.95, "epsilon": 1.0, "epsilon_decay": 0.995},
  "discretizer": {"queue_edges": [0.1, 0.3, 0.6, 0.9], "density_edges": [0.1, 0.3, 0.6, 0.9]},
  "fixed_time":  {"durations": [15, 5, 15, 5]},
  "queue_based": {"hold_on_min_green": true}
}
```

`fixed_time.durations` 是**已校准的基线**（见 `docs/baselines.md`），
**不要改动**，否则与已记录结果不可比。

## 6. 一定要知道的坑

| 现象 | 原因 / 处理 |
| --- | --- |
| 一次回合跑 2 分钟 | 没用 libsumo；确认 `use_gui=False`（自动启用），或手动设 `LIBSUMO_AS_TRACI=1` |
| 结果每次都不一样 | 没传 `sumo_seed`；`evaluate.py` / `train.py` 已修，自己写脚本时注意 |
| 状态"没变化" | 观测已归一化，阈值要用 `(0.1,0.3,0.6,0.9)` |
| 改了 `network.json` 没生效 | 要跑 `python nets/single-intersection/build_network.py` |
| 改了车道数结果不可比 | `observation_space` 维度变了，基线要重跑 |
| GUI 开不出来 | 环境里有 `LIBSUMO_AS_TRACI`；`build_env(use_gui=True)` 会自动移除，但同进程已导入 traci 就无法切换 |

## 7. 提交前自检

```bash
python -m pytest -q                  # 必须全绿（当前 119 个）
python -m compileall -q src scripts  # 语法检查
```

新增功能请**同时加测试**，尤其是：
- 新的状态/动作设计 → 加单元测试（用假观测即可，不必起 SUMO）；
- 新的评估逻辑 → 加一个 CSV 汇总用例。

## 8. 当前基线（供对照，3 种子，平均等待 s）

| 场景 | random | fixed_time | queue_based |
| --- | --- | --- | --- |
| S1 (600) | 7.75 | 1.79 | **0.64** |
| S2 (1200) | 8.29 | 1.68 | **1.26** |
| S3 (2000) | 8.99 | 1.88 | **1.76** |
| S4 (1200 不均衡) | 9.14 | 1.97 | **1.50** |

> 目标：**接近或超过 `queue_based`**。S3 上只差 7%，想在该场景取胜需要更细的状态设计；
> S1/S2/S4 空间更大，也更能体现学习型控制的优势。

