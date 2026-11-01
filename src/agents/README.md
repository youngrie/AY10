# `src/agents/` —— 智能体层

| 文件 | 职责 | 状态 |
| --- | --- | --- |
| `base.py` | 控制器统一接口 `BaseController` | 已用 |
| `discretizer.py` | 连续观测 → 离散状态（表格法用） | 已用 |
| `q_learning.py` | 表格型 Q-learning | 可用，可改 |
| `dqn_agent.py` | DQN（基于 stable-baselines3） | **骨架，训练未接入** |

## 接口

```python
class BaseController(ABC):
    name: str
    def select_action(self, obs) -> int: ...     # 必须实现
    def reset(self) -> None: ...                 # 回合开始
    def update(self, obs, action, reward, next_obs, terminated) -> None: ...  # 在线学习
    def on_episode_end(self) -> None: ...        # 回合结束（如 ε 衰减）
    def save(self, path) / load(self, path)      # 持久化
```

基线控制器（见 `../controllers/`）继承同一接口，所以能互换。

## ⚠️ 离散化的关键前提：观测已归一化

SUMO-RL 的 `observation_space` 是 `Box(0.0, 1.0, ...)`，即**观测已缩放到 [0,1]**。

```python
obs = [phase_one_hot, min_green, density(各车道), queue(各车道)]
```

所以分箱阈值必须落在 `[0,1]` 内，默认用 `DEFAULT_NORMALIZED_EDGES = (0.1, 0.3, 0.6, 0.9)`。

> 历史坑：早期用"车辆数"阈值 `(1,3,6,10)`，导致所有状态都落到第 0 档，
> Q-learning 等于在学一个常数。`factory.py` 现在会自动判断，
> 若配置里给了 `>1` 的阈值而观测已归一化，会**忽略配置并打印警告**。

`Discretizer.from_spaces(n_phases, obs_dim)` 会由观测维度反推车道数：
`obs_dim = n_phases + 1 + 2 * n_lanes`。所以**改车道数不需要改智能体代码**。

## 表格型 Q-learning

```python
agent = TabularQLearning(n_actions=4, discretize=discretizer,
                         alpha=0.1, gamma=0.95, epsilon=1.0,
                         epsilon_min=0.05, epsilon_decay=0.995, seed=0)
action = agent.select_action(obs)                 # ε-greedy
agent.update(obs, action, reward, next_obs, done) # Q(s,a) += α[r + γmaxQ − Q]
agent.on_episode_end()                            # ε 衰减
agent.save("results/q.pkl")
```

- Q 表用稀疏字典，未访问过的状态按全零初始化；
- `agent.n_states` 可用于观察状态空间覆盖程度；
- 超参数与分箱阈值都在 `src/config.py` 的 `agent` / `discretizer` 段。

## DQN（第二阶段）

- 动机：观测是高维连续量，表格法必须手工离散化且易状态爆炸；
- 依赖：`requirements.txt` 里取消 `# stable-baselines3==2.3.2` 注释后 `pip install -r requirements.txt`；
- 现状：`DQNAgent` 可构造，但 `train.py` 的 `--controller dqn` 仍直接打印"未接入"——
  需要补训练循环（`model.learn(...)`）与评估接线，见 `../../docs/tasks.md`。
