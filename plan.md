# 基于强化学习的交通信号控制 — 项目方案 / 开题报告（plan.md）

> **文档定位**：本文件是小组作业 **AY10** 的**开题报告（proposal）**思路稿，覆盖作业要求的四个方面：**Environment / RL Agent / Baseline / Evaluate**。
> **当前状态**：已根据组内讨论**确定一条技术路线**（见 §0.1）；代码实现**暂不开始**，先定稿本 proposal。
> 状态标记：`[已定]` = 组内已确认；`[建议]` = AI 推荐；`[暂缓]` = 本期不做，留作扩展。

---

## 0. 作业要求回顾（来自 README.md / AY10.pdf）

| 方面 | 要求 |
| --- | --- |
| **Environment** | 搭建一个**简化单路口**仿真：车辆从不同方向到达、在队列中等待。可从**两个信号相位** + 简单到达模式起步。 |
| **RL Agent** | 训练**表格型 Q-learning** 智能体选择信号相位。状态可包含队列长度与当前相位；奖励可惩罚等待时间或过长队列。可选扩展到 **DQN** 并比较。 |
| **Baseline** | 与**固定时长控制器**（按固定时间表切换）与**基于队列的控制器**（优先放行等待车辆更多的方向）比较。 |
| **Evaluate** | 在不同交通条件下测试（轻度 / 重度 / 各方向不均匀）。**平均等待时间**与**队列长度**是有用指标。 |
| 评分导向 | 原文强调："manageable implementation, make clear comparisons, and analyse what works and why"——**可落地的实现 + 清晰对比 + 有解释力的分析**优先于堆砌花哨方法。 |

---

## 0.1 已确定的技术路线（Determined Route）`[已定]`

> 以下路线由组内讨论确定，是后续实现（及本 proposal）的**唯一主线**。

| 环节 | **确定的选择** | 依据 |
| --- | --- | --- |
| **仿真平台** | **SUMO**（不采用自研 Python 仿真） | 组内决定；SUMO 提供真实微观交通与标准信号控制接口 |
| **仿真接入方式** | **SUMO-RL**（`sumo_rl.SumoEnvironment`，Gymnasium 兼容） | 避免从零写 TraCI 循环；内置观测/动作/奖励与单路口网络 |
| **信号相位** | **4 相位，含保护式左转**（NS 直行 → NS 左转 → EW 直行 → EW 左转） | 组内决定需要左转相位 |
| **车道结构** | **每进口方向多车道，车道功能可配置**（当前：4 车道 = 右/直/直/左） | 组内决定 |
| **车辆到达模型** | **纯泊松**（稳态） | 组内决定先做最简单到达模式 |
| **RL 算法** | **阶段一：Tabular Q-learning；阶段二：DQN**（已确定要做，按顺序执行） | 组内决定 |
| **基线** | **固定时长 + 基于队列**（作业规定），**暂不加额外基线** | 组内决定 |
| **评估** | 场景**由易入难、循序渐进**；**暂不做显著性检验** | 组内决定 |

**一句话路线**：*用 SUMO-RL 搭建一个 4 相位（含左转）、每方向三车道的单路口环境；先用表格型 Q-learning、再扩展 DQN；与固定时长和基于队列两类基线，在由易到难的交通场景下比较平均等待时间与队列长度。*

> ⚠️ **注意的路线风险（不阻塞 proposal）**：SUMO-RL 默认动作空间是"**选择下一个绿灯相位**"（含黄灯过渡），其**观测是连续量**（密度/队列/one-hot 相位）。因此：
> 1. **表格型 Q-learning 需先做状态离散化**（§4.1），或使用 SUMO-RL 的 `states="state"` 离散占用网格观测；
> 2. 4 相位 + 左转会**增大动作空间**，对表格法收敛是挑战——这本身可作为报告的分析点。

**两阶段计划（已确定）**

| 阶段 | 时间 | 内容 | 交付物 |
| --- | --- | --- | --- |
| **阶段一** | 前 3 周 | SUMO 4 相位环境 + **表格型 Q-learning** + 固定时长 / 基于队列基线 + S1–S4 评估 | 完整对比结果（学习曲线 + 指标表） |
| **阶段二** | 第 4–5 周 | **DQN 扩展**：经验回放 + 目标网络，与表格法对照 | 表格法 vs DQN 的对比分析 + 结论 |

> 阶段二**在阶段一跑出完整结果之后启动**，避免两条线同时停在半成品；
> 但阶段二的准备工作（装依赖、跑通管线）可以提前做，见 `docs/tasks.md`。

**暂缓（本期不做）**：额外强基线（Max-Pressure）、时变需求、多路口路网、显著性检验。

---

## 1. 项目目标（proposal 建议表述）

1. 在 **SUMO** 中搭建一个**单路口**交通仿真场景（4 相位含左转、每方向多车道，车道功能可配置）。
2. 使用 **SUMO-RL** 将仿真封装为 Gymnasium 环境，作为所有控制器的统一实验平台。
3. 实现并训练一个**表格型 Q-learning** 信号控制智能体；扩展实现 **DQN** 并与表格法对比。
4. 实现两类规定基线：**固定时长控制器**与**基于队列的控制器**，与 RL 智能体公平对比。
5. 在**由易到难**的交通场景下，用**平均等待时间 / 平均队列长度**等指标对比所有策略，给出"什么有效、为什么有效"的分析。

**非目标（本期不做）**：多路口协同控制、真实路网的完整标定、混合交通（行人/非机动车）、额外强基线与显著性检验（见 §0.1 的「暂缓」）。

---

## 2. 技术栈

| 类别 | 选型 | 说明 |
| --- | --- | --- |
| 语言 | Python 3.11（当前环境 3.11.5） | — |
| 交通仿真 | **SUMO**（`sumo` / `sumo-gui`）+ 环境变量 `SUMO_HOME` | 微观仿真、真实信号控制 |
| RL 环境封装 | **SUMO-RL**（`pip install sumo-rl`） | 提供 `SumoEnvironment`（Gymnasium 兼容）+ 单路口网络 |
| 智能体 | 自研 **表格型 Q-learning**（离散化状态）；扩展 **DQN**（`stable-baselines3`） | 对应组内两阶段路线 |
| 基线 | 自研 **固定时长**（static `tlLogic`）与 **基于队列** 控制器 | 作业规定 |
| 数值/数据 | `numpy`, `pandas` | 指标统计、结果表 |
| 可视化 | `matplotlib` | 学习曲线、对比柱状图、队列时间序列 |
| 配置管理 | `argparse`（+ `PyYAML` 可选） | 场景与超参数参数化、可复现 |
| 测试 | `pytest`（可选） | 保证控制器与指标代码正确 |

**环境搭建要点（SUMO 侧，记入 proposal 附录）**
- 安装 SUMO 后设置 `SUMO_HOME`（Linux 默认 `/usr/share/sumo`）。
- 接入方式二选一：
  - `pip install traci`（或把 `$SUMO_HOME/tools` 加入 `sys.path`），手动控制仿真步与信号灯；
  - 直接用 `sumo-rl`（推荐）——其 `TrafficSignal` 内部已封装 TraCI 的信号灯读写。
- 性能提示：`export LIBSUMO_AS_TRACI=1` 可获约 8× 加速（但**不能**同时用 `sumo-gui` 或并行多仿真）——训练用 libsumo、演示/调试用 `use_gui=True`。

---

## 3. Environment（仿真环境）`[已定：SUMO]`

### 3.0 概念澄清：什么是"相位"、"左转相位"（术语说明）

**相位（Phase）= 一个「允许哪些方向通行」的信号状态组合。**
路口有 4 个进口方向 `{N, S, E, W}`，不能让所有方向同时绿灯（会冲突），因此把互不冲突的方向**编成一组、轮流放行**；每一组"同时绿灯的方向集合"就是一个相位。

**本项目采用的 4 相位方案（含保护式左转）`[已定]`：**

| 相位 | 绿灯方向 | 说明 |
| --- | --- | --- |
| `Phase 0` | 南北**直行** | N/S 直行（+ 右转） |
| `Phase 1` | 南北**左转** | N/S 保护式左转（对向全红） |
| `Phase 2` | 东西**直行** | E/W 直行（+ 右转） |
| `Phase 3` | 东西**左转** | E/W 保护式左转（对向全红） |

```
 Phase 0: 南北直行      Phase 1: 南北左转      Phase 2: 东西直行      Phase 3: 东西左转
     │  ↑                   │ ↰                   ── → ──                (东西左转)
     │  ↓                   │ ↳                   ── → ──
  (东西全红)             (东西全红)              (南北全红)            (南北全红)
```

**在 SUMO 中如何表示相位**：SUMO 用 **`<tlLogic>` 定义信号程序**，每个 `<phase duration="..." state="..."/>` 用一个**状态字符串**描述各受控连接（link）的灯色，字符含义：

| 字符 | 含义 |
| --- | --- |
| `G` | 绿灯，**有优先通行权**（保护） |
| `g` | 绿灯，**需让行**（permissive，左转须让对向直行） |
| `r` | 红灯 |
| `y` / `Y` | 黄灯（`y` 让行、`Y` 有优先） |
| `o` / `O` | 灯灭 / 闪烁 |

> 左转保护相位的本质：在该相位的 `state` 里，让**左转连接**取 `G`，同时**对向直行连接**取 `r`，从而"左转独占"。

**与 SUMO-RL 的关系**：`SumoEnvironment` 会自动从 tls 程序解析出**所有"绿灯相位"**；其**动作空间 = 选择下一个绿灯相位**（`Discrete(n_green_phases)`），切换时自动插入黄灯过渡。所以"4 相位含左转"≈ 动作空间 4 个。

**相关术语速查**

| 术语 | 含义 |
| --- | --- |
| 相位（Phase） | 一组同时绿灯的通行方向 |
| 黄灯 / 全红（Yellow / All-red） | 切换过渡清空时间，期间不放行 |
| 最小绿灯（`min_green`） | 相位至少亮多久才允许切换，防抖动 |
| 最大绿灯（`max_green`） | 一个绿灯相位的最长时长 |
| 周期（Cycle）/ 绿信比（Split） | 所有相位走一遍的总时间 / 各相位占比 |
| `delta_time` | SUMO-RL 中 RL 的**决策间隔**（每多少仿真秒决策一次） |

### 3.1 路口与信号模型 `[已定]`

- **路口结构**：单十字路口，4 个进口方向 `{N, S, E, W}`。
- **车道结构**：**每进口方向多车道，车道功能由配置决定**（当前 4 车道：右 / 直 / 直 / 左，共 16 条进口车道；`nets/single-intersection/network.json` 可改）。
- **相位**：**4 相位，含保护式左转**（见 §3.0 表）。
- **信号参数（初值 `[建议]`，后续可调）**：
  - `yellow_time = 3 s`；`min_green = 5 s`；`max_green = 50 s`；`delta_time = 5 s`（RL 决策间隔）。
- **SUMO 侧实现方式**：
  1. 用 `netconvert` / `netedit` 建单路口网络（或先用 SUMO-RL 自带单路口 net），确保**每个方向含左转连接**；
  2. 用 `<tlLogic type="static" programID="...">` 定义 4 个绿灯相位 + 对应黄灯相位（`tls.add.xml`）；
  3. 通过 SUMO-RL 载入，RL 智能体在绿灯相位间做选择。

### 3.2 车辆与到达模型 `[已定：纯泊松]`

- **到达过程**：每个进口方向独立 **泊松过程**，`λ_i`（veh/h）；转向比例由路由文件决定左/直/右的分配。
- **SUMO 实现**：在 `.rou.xml` 中用 `<flow>`（`vehsPerHour` / `period="exp(...)"`）定义各方向需求；SUMO 原生即**微观车辆动力学 + 真实排队**。
- **episode / 仿真时长**：`num_seconds = 3600 s`（1 仿真小时）。
- **排队与等待时间（指标来源）**：从 SUMO 直接读取——`lane.getLastStepHaltingNumber`、每车 `waitingTime` / `timeLoss`（§6.2）。

### 3.3 与 RL 的接口（基于 SUMO-RL）`[已定]`

```python
# src/env/sumo_env.py  （接口示意，非最终实现；实现暂缓）
from sumo_rl import SumoEnvironment

env = SumoEnvironment(
    net_file="nets/single-intersection/single-intersection.net.xml",
    route_file="nets/single-intersection/single-intersection.rou.xml",
    out_csv_name="results/qlearning_single",
    single_agent=True,            # 单智能体 -> 普通 Gymnasium Env
    use_gui=False,                # 训练关 GUI；演示可开
    num_seconds=3600,             # 每个 episode 的仿真时长
    delta_time=5,                 # 决策间隔（秒）
    yellow_time=3,                # 黄灯时长
    min_green=5,                  # 最小绿灯
    max_green=50,                 # 最大绿灯
    reward_fn="diff-waiting-time",# 奖励设计，见 §4.2
    sumo_seed=42,                 # 随机种子（可复现）
)
# env.observation_space / env.action_space 由网络相位决定（动作 = 绿灯相位索引）
```

**SUMO-RL 的默认观测（连续量，需为表格法离散化）**：
```python
obs = [phase_one_hot, min_green, lane_1_density,...,lane_n_density, lane_1_queue,...,lane_n_queue]
```
- `phase_one_hot`：当前绿灯相位的 one-hot（4 相位 → 4 维）；
- `min_green`：min_green 是否已过的 0/1；
- `lane_i_density`：第 i 条进口车道的车辆数；
- `lane_i_queue`：第 i 条进口车道的**排队车辆数**。

> **公平性约定**：所有控制器使用"**同网络 + 同路由 + 同 `sumo_seed` + 同信号参数**"；指标统一从 SUMO 输出读取。

### 3.4 环境模块文件划分 `[建议]`

| 文件 | 职责 |
| --- | --- |
| `nets/single-intersection/*.net.xml` | SUMO 单路口路网（4 相位、每方向多车道含左转，由脚本生成） |
| `nets/single-intersection/*.rou.xml` | 车辆需求（纯泊松 `flow`，含转向比例） |
| `nets/single-intersection/tls.add.xml` | 4 相位信号程序定义（`tlLogic`） |
| `src/env/sumo_env.py` | 封装 `SumoEnvironment`、场景配置与种子管理 |
| `src/env/scenarios.py` | 交通场景定义（由易到难，见 §6.1） |

### 3.5 环境侧技术选择小结 `[已定]`

| 问题 | 确定选择 |
| --- | --- |
| 仿真平台 | **SUMO** |
| RL 环境封装 | **SUMO-RL `SumoEnvironment`** |
| 相位数量 | **4 相位（NS 直行 / NS 左转 / EW 直行 / EW 左转）** |
| 车道结构 | **每方向多车道（车道功能可配置；当前 4 车道 = 右/直/直/左）** |
| 到达模型 | **纯泊松** |
| 决策间隔 `delta_time` | 5 s `[建议]`（可调） |
| 训练/演示 | 训练 `use_gui=False`（可用 libsumo 加速）；演示 `use_gui=True` |

---

### 💬 我的想法 / 待交流（Environment）

> 请在下面填写你的看法，然后我们据此更新 §3.1–3.5。

- **我倾向的仿真平台 / 工具**：（自研 Python 环境？SUMO？CityFlow？其他？）
  - SUMO，不打算用自研的python类来模拟交通
- **路口与相位设计**：（是否要左转相位？是否需要多车道？）
  - 需要左转相位，暂时先按照同向三车道（左转/直行/右转）设计
- **车辆到达模型**：（纯泊松？还是加入峰值/时变？各方向到达率大概想设多少？）
  - 暂时先使用纯泊松
- **排队与时间粒度**：（Δt 选多少？是否需要有限容量？）
  - 我也不太懂，先按你的理解来
- **我想额外加入的环境特性**：
  -
- **我需要你（AI）帮我确认/补充的点**：
  -
- **【AI 待你确认】**：
  - 单路口网络：**用 SUMO-RL 自带的单路口 net**（快速起步，但需确认是否含左转专用道），还是**自己用 `netedit/netconvert` 定制"每方向 3 车道 + 左转"的 net**？（后者更贴合需求，但工作量更大）
  - `delta_time` 定 **5 s** 还是 **1 s**？

---

## 4. RL Agent（智能体）`[已定：Tabular Q-learning → DQN]`

### 4.1 MDP 形式化（贴合 SUMO-RL）`[建议]`

| 要素 | 设计 |
| --- | --- |
| **决策时刻** | 每隔 `delta_time` 秒决策一次（初值 5 s）；相位切换自动插入黄灯过渡 |
| **动作空间 A** | `Discrete(n_green_phases)`：**选择下一个绿灯相位**（4 相位含左转 → 约 4 个动作）；受 `min_green` / `max_green` 约束 |
| **状态空间 S** | 由 SUMO-RL 观测离散化：`(phase_one_hot, min_green_passed, bin(各车道 queue), bin(各车道 density))` |
| **奖励 R** | 见 §4.2（SUMO-RL 内置 `diff-waiting-time` / `queue` / `pressure` 等） |
| **折扣因子 γ** | 建议 `0.95` |
| **回合** | 一个 episode = `num_seconds = 3600 s` 的仿真 |

**状态离散化（表格法关键设计点）**：
- SUMO-RL 默认观测是**连续量**（每车道 density、queue），表格法需**分箱**：
  - 例：`queue = 0 → 0`，`1–2 → 1`，`3–5 → 2`，`6–10 → 3`，`>10 → 4`。
- 也可用 SUMO-RL 的 `states="state"`（离散占用网格观测），直接得到**有限离散状态**——`[建议]` 优先尝试该模式，并与分箱法对比。
- **注意**：12 条进口车道 × 多档位会使状态空间较大，这是"4 相位 + 三车道"路线下**表格法的核心挑战**，也是引入 DQN 的动机。

### 4.2 奖励函数 `[建议]`

SUMO-RL 提供若干内置奖励（通过 `reward_fn` 指定）：
1. **`diff-waiting-time`（推荐主用）**：`r = 上一步总等待时间 − 当前步总等待时间`（作业建议的"惩罚等待时间"）。
2. **`queue`**：`r = -Σ 各车道排队车辆数`（作业建议的"惩罚过长队列"）。
3. **`pressure`**：基于"上游排队 − 下游排队"的压力差。
4. **`average-speed`**：以平均车速为奖励。
5. `[扩展]` 自定义奖励：在 (1)/(2) 基础上加**切换惩罚**（抑制抖动）。

> `[建议]` 主实验用 **`diff-waiting-time`**，并与 **`queue`** 对比；奖励设计差异是报告的重要分析点。

### 4.3 Tabular Q-learning 实现（第一阶段）`[建议]`

```python
# src/agents/q_learning.py  （算法示意；实现暂缓）
import numpy as np

class TabularQLearning:
    """基于离散状态的表格型 Q-learning。"""

    def __init__(self, n_actions, alpha=0.1, gamma=0.95,
                 epsilon=1.0, epsilon_min=0.05, epsilon_decay=0.9995, seed=0):
        self.Q = {}            # 稀疏字典: state -> np.array(n_actions)
        self.n_actions = n_actions
        self.alpha, self.gamma = alpha, gamma
        self.epsilon = epsilon
        self.epsilon_min, self.epsilon_decay = epsilon_min, epsilon_decay
        self.rng = np.random.default_rng(seed)

    def _q(self, state):
        if state not in self.Q:
            self.Q[state] = np.zeros(self.n_actions)
        return self.Q[state]

    def select_action(self, state):          # ε-greedy
        if self.rng.random() < self.epsilon:
            return int(self.rng.integers(self.n_actions))
        return int(np.argmax(self._q(state)))   # 平局可随机打破

    def update(self, s, a, r, s_next, done):
        target = r if done else r + self.gamma * np.max(self._q(s_next))
        self._q(s)[a] += self.alpha * (target - self._q(s)[a])

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def save(self, path): ...
    def load(self, path): ...
```

**训练流程（`src/train.py`，基于 SUMO-RL 的 Gymnasium 循环）**：
```python
obs, info = env.reset()
done = False
while not done:
    action = agent.select_action(discretize(obs))       # 表格法：先离散化
    obs_next, reward, terminated, truncated, info = env.step(action)
    agent.update(discretize(obs), action, reward, discretize(obs_next), terminated)
    obs, done = obs_next, terminated or truncated
```

**超参数初值 `[建议]`**：`α=0.1`（可衰减）、`γ=0.95`、`ε: 1.0 → 0.05`；训练 `数百–数千` episodes。

### 4.4 DQN（第二阶段，已确定）`[已定]`

**启动条件**：表格法（§4.3）已在 S1–S4 跑出完整结果、写入报告之后，再开始本阶段。

- **动机**：SUMO-RL 观测为**连续/高维**（多车道 density+queue+相位，实测已被归一化到 `[0,1]`），表格法需手工分箱且易状态爆炸；**DQN 可直接吃原始观测**，无需离散化。
- **实现**：使用 `stable-baselines3==2.3.2` 的 `DQN`（与 `gymnasium==0.29.1` 兼容）；依赖已列在 `requirements.txt` 的第二阶段段落中，取消注释即可。
- **落地步骤**：
  1. 安装依赖（`stable-baselines3==2.3.2`）；
  2. 在 `src/train.py` 接入 DQN 训练分支（`--controller dqn`），`src/agents/dqn_agent.py` 已有骨架；
  3. 训练并保存模型，同时在 `src/evaluate.py` 把 `dqn` 纳入可评估控制器；
  4. 与表格法在**同一场景、同一组随机种子**下对照。
- **对比维度**：性能（平均等待时间 / 队列长度）、**收敛速度**（达到同等性能所需样本数）、训练稳定性、跨场景泛化。
- **验收标准**：`python src/train.py --controller dqn --episodes N` 能跑完并保存模型；S1–S4 上产出与表格法并列的结果行。
- **预期论点**："表格法可解释、易实现，但在高维观测下需离散化且收敛慢；DQN 泛化更好，但需要更多训练样本与算力。"

### 4.5 Agent 模块文件划分 `[建议]`

| 文件 | 职责 |
| --- | --- |
| `src/agents/base.py` | 控制器统一接口 `select_action(obs) -> action`，保证 RL 与基线可互换 |
| `src/agents/discretizer.py` | 观测→离散状态的映射（分箱） |
| `src/agents/q_learning.py` | 表格型 Q-learning |
| `src/agents/dqn_agent.py` | DQN（SB3 封装）——第二阶段 |

---

### 💬 我的想法 / 待交流（RL Agent）

> 请填写你的想法，然后我们据此更新 §4.1–4.5。

- **我倾向的智能体算法**：（表格 Q-learning？SARSA？要不要做 DQN？）
  - Tabular Q-learning -> DQN
- **状态设计**：（用哪些量？队列是否分箱？阈值怎么定？是否加入等待时间/相位计时？）
  - 先按照你的理解设计
- **动作设计**：（"保持/切换" vs "直接选相位"？决策频率多高？）
  - 先按照你的理解设计
- **奖励函数**：（你更倾向队列惩罚、等待时间惩罚，还是 pressure？要不要切换惩罚？）
  - 先按照你的理解设计
- **超参数 / 训练时长**：（α、γ、ε 衰减、训练多少个 episode？）
  - 先按照你的理解设计
- **我特别想做的扩展**：（Double Q？DQN？迁移泛化？）
  -
- **我需要你（AI）帮我确认/补充的点**：
  -
- **【AI 待你确认】**：
  - 按你"Tabular Q-learning → DQN"的路线 —— **已确认**：DQN 作为**阶段二**，阶段一（表格法）出结果后再启动。
  - 表格法的状态用 **SUMO-RL `states="state"` 离散占用网格**，还是**自己做队列分箱**？
  - 主奖励用 **`diff-waiting-time`** 还是 **`queue`**？

---

## 5. Baseline（对照策略）`[已定：固定时长 + 基于队列]`

> 所有控制器实现**统一接口** `select_action(obs) -> action`，与 RL agent **共用同一 SUMO 环境与指标代码**，确保对比公平。

### 5.1 固定时长控制器（Fixed-Time）`[必做]`

- **原理**：信号按**固定时间表**周期切换，**不考虑实时交通状况**（作业指定）。
- **SUMO 实现**：使用网络自带的 **static `tlLogic`**（固定 `duration` 的相位序列）即可，**无需外部控制**——直接 `sumo -c *.sumocfg` 运行。
- **参数**：周期 `C`（如 60–90 s）、绿信比（NS:EW，如 50:50）、黄灯 `y`。
- **作用**：作为**基准线/下界**，体现"实时自适应"的价值。
- **简化说明**：按你的决定，**本期只做 balanced（等绿信比）版本**，不做离线优化版本（`[暂缓]`）。

### 5.2 基于队列的控制器（Queue-based）`[必做]`

- **原理**：**优先放行等待车辆更多的方向**（作业指定）。
- **实现（Longest-Queue-First, LQF）**：每个决策点用 SUMO 车道排队数据（`getLastStepHaltingNumber`）计算各**相位**的排队总和，选择排队最大的绿灯相位；受 `min_green` 约束后才允许切换。
- **参数**：`min_green`（与 RL 保持一致）。
- **作用**：代表**无学习的自适应**控制，是 RL 最直接的"对手"。
- **简化说明**：按你的决定，**本期只做 LQF，省略"阈值感应"版本与参数网格调优**（`[暂缓]`）。

### 5.3 额外参考控制器 `[暂缓]`

> 按你的决定（"暂时先不用"），**本期不加入额外基线**。以下仅作为暂缓项，在报告中作为"未来工作"提及。

| 控制器 | 说明 | （若做）作用 |
| --- | --- | --- |
| `Random` | 随机选绿灯相位 | 性能下界，验证环境合理 |
| `Max-Pressure` | 选"上游排队 − 下游排队"最大的相位（Varaiya 2013） | 强基线，学术价值高 |
| `All-way / 常绿交替` | 极端简单对照 | 说明问题难度 |

**对比矩阵（本期）**：`{Fixed-time(balanced), Queue-based(LQF), Tabular Q-learning, (DQN)}`，在 §6.1 各场景下横向比较。

### 5.4 Baseline 模块文件划分 `[建议]`

| 文件 | 职责 |
| --- | --- |
| `src/controllers/base.py` | 控制器统一接口 `select_action(obs)` |
| `src/controllers/fixed_time.py` | 固定时长控制（或不干预、直接用 static `tlLogic`） |
| `src/controllers/queue_based.py` | LQF 控制器 |

### 5.5 公平性要点 `[重要]`

- 所有控制器使用**同一路网 + 同一路由 + 同一 `sumo_seed` + 同一信号参数（`min_green`/`yellow_time`/`delta_time`）**；
- 由于本期不做调参（`[暂缓]`），报告中需**如实说明各控制器均使用默认/统一参数**，并把它列为结论的局限性；
- 结果从 SUMO 统一收集（等待时间、队列、吞吐），保证可比。

---

### 💬 我的想法 / 待交流（Baseline）

> 请填写你的想法，然后我们据此更新 §5.1–5.5。

- **必做的两个基线我怎么看**：（固定时长的周期/绿信比怎么设？基于队列用 LQF 还是阈值感应？）
  - 先按照你的理解设计
- **是否加入额外基线**：（Random？Max-Pressure？All-way？）
  - 暂时先不用
- **参数调优策略**：（基线参数谁来调？是否用相同时间预算调参？）
  - 暂时不考虑调参
- **公平性方面我担心的问题**：
  -
- **我需要你（AI）帮我确认/补充的点**：
  -
- **【AI 待你确认】**：按你的决定，本期基线只做 **固定时长（等绿信比）+ 基于队列（LQF）**，**不加额外基线、不做调参**——我会在报告中把"未调参"写明为局限性。这样可以吗？

---

## 6. Evaluate（评估）`[已定：由易到难循序渐进]`

### 6.1 交通场景（由易到难，阶梯式设计）`[已定]`

> 按你的意见"**由易入难、循序渐进**"，把评估组织为 **4 个递进阶梯**：前一级验证正确性，后一级逐步加压。设总需求 `λ_total`（veh/h），方向比记为 `N:E:S:W`。

| 阶梯 | 场景 | 描述 | 示例需求（总流量 / 方向比） | 目的 |
| --- | --- | --- | --- | --- |
| **S1** | **Low & balanced（低流量均衡）** | 远低于饱和，各方向相同 | `600 veh/h`，`1:1:1:1` | 验证环境/指标/控制器基本正确，**先跑通** |
| **S2** | **Medium & balanced（中流量均衡）** | 中等需求 | `1200 veh/h`，`1:1:1:1` | 观察 RL 是否开始优于固定时长 |
| **S3** | **Heavy & balanced（高流量均衡）** | 接近/达到饱和 | `2000 veh/h`，`1:1:1:1` | 压力测试，看谁先崩溃 |
| **S4** | **Uneven（不均衡）** | 主次方向差异大 | `1200 veh/h`，`3:1:1:1` | 检验自适应/公平性 |
| `[暂缓]` S5 | Time-varying（时变/峰值） | 需求随时间变化 | 梯形/正弦需求 | 留作扩展（暂缓项） |

**实施原则**：
- **逐级推进**：先在 **S1 跑通全流程**（基线 → RL），确认指标合理，再进 S2/S3/S4；
- 每级只改变**一个变量**（流量或方向比），便于归因；
- 所有场景的 `λ`、方向比写入配置文件（`experiments/configs/*`），保证可复现。

### 6.2 评估指标 `[建议]`

**主要指标（作业指定，必须报告）**
1. **平均等待时间**（Average Waiting Time, s/veh）——SUMO 每车 `waitingTime` 的均值。
2. **平均队列长度**（Average Queue Length, veh）——各进口车道 `getLastStepHaltingNumber` 的均值。

**辅助指标（增强分析可信度）**
3. **最大队列长度**——反映极端拥堵。
4. **吞吐量**（Throughput, veh/h）——是否牺牲通行量换等待时间。
5. **平均延误**（`timeLoss`，s/veh）——与等待时间对照。
6. **（RL 专属）学习性能**：累计奖励/平均等待时间随 episode 的**收敛曲线**。
7. **（可选）相位切换次数**——评估是否"抖振"。

> `[暂缓]` 由于本期不做显著性检验，**公平性指标（Gini 等）与计算开销统计暂不纳入主表**，可在报告中简要讨论。

### 6.3 实验协议 `[建议]`

- **训练 / 测试分离**：RL 在训练场景上学习，在**同场景**与**其它阶梯场景**上测试（看泛化）。
- **多种子（建议）**：每个 (控制器, 场景) 组合跑 **5–10 个 `sumo_seed`**，报告 **均值 ± 标准差**（虽不做检验，但**必须**报波动，否则结论不可信）。
- **可视化**：
  - 柱状图（带误差棒）：各控制器在 S1–S4 的主指标对比；
  - 学习曲线：累计奖励 / 平均等待时间 vs 训练 episode（RL）；
  - 时间序列：队列长度与相位随时间变化（展示行为差异）。
- **对比重点**：**阶段一**比较奖励函数（`diff-waiting-time` vs `queue`）与状态离散粒度；**阶段二**比较表格法 vs DQN。

### 6.4 结果记录格式 `[建议]`

统一产出 CSV（SUMO-RL 的 `out_csv_name` 已可输出每步/每 episode 指标）+ 汇总表 `results/{scenario}_{controller}.csv`，字段：`scenario, controller, seed, avg_wait, avg_queue, max_queue, throughput, ...`；报告图表由脚本一键从 CSV 生成。

### 6.5 分析要回答的核心问题 `[建议]`

1. RL **是否优于**固定时长与基于队列两个基线？在 S1–S4 各阶梯上表现如何变化？
2. **4 相位含左转**的设定下，RL 能否学到合理策略（动作空间变大是否难学）？
3. **表格法 vs DQN**：性能、收敛速度、泛化能力差异（对应"为什么 DQN 更适合高维观测"）。
4. **奖励设计**如何影响学到的行为（`diff-waiting-time` vs `queue`）？
5. 在**由易到难**的过程中，各控制器的性能差距如何演变？

---

### 💬 我的想法 / 待交流（Evaluate）

> 请填写你的想法，然后我们据此更新 §6.1–6.5。

- **我想测试的交通场景**：（轻/中/重/不均衡之外，是否要时变需求、特殊比例？具体 λ 设多少？）
  - 我也不太清楚，我觉得应该由易入难，循序渐进
- **我关心的核心指标**：（除平均等待时间、队列长度外，是否看重吞吐/公平性/切换次数？）
  - 先按照你的理解设计
- **实验规模**：每个组合跑多少个种子？episode 多长？
  - 先按照你的理解设计
- **统计与图表偏好**：（需要做显著性检验吗？希望出哪些图？）
  - 暂时不用
- **我想额外的消融/分析**：
  -
- **我需要你（AI）帮我确认/补充的点**：
  -
- **【AI 待你确认】**：我把场景设计成 **S1 低流量均衡 → S2 中流量均衡 → S3 高流量均衡 → S4 不均衡** 的递进阶梯（先跑通 S1 再逐级加压），是否符合你"由易入难"的想法？具体 `λ` 数值（600/1200/2000）需要用 SUMO 实测后再微调。

---

## 7. 推荐仓库结构（SUMO 路线）

```
AY10/
├── README.md                       # 作业说明（已有）
├── AY10.pdf                        # 作业原文（已有）
├── plan.md                         # 本方案 / proposal 文件
├── requirements.txt                # sumo-rl, traci, numpy, pandas, matplotlib, (stable-baselines3)
├── nets/
│   └── single-intersection/        # SUMO 路网与需求
│       ├── *.net.xml               # 单路口网络（4 相位、多车道含左转，脚本生成）
│       ├── *.rou.xml               # 车辆需求（纯泊松 flow + 转向比例）
│       ├── tls.add.xml             # 4 相位信号程序（tlLogic）
│       └── *.sumocfg               # 仿真配置
├── src/
│   ├── env/
│   │   ├── sumo_env.py             # 封装 SumoEnvironment + 场景/种子管理
│   │   └── scenarios.py            # 场景定义 S1–S4（由易到难）
│   ├── agents/
│   │   ├── base.py                 # 控制器统一接口
│   │   ├── discretizer.py          # 观测→离散状态
│   │   ├── q_learning.py           # 表格型 Q-learning
│   │   └── dqn_agent.py            # DQN（第二阶段，SB3）
│   ├── controllers/                # 基线
│   │   ├── fixed_time.py
│   │   └── queue_based.py
│   ├── metrics.py                  # 指标收集（等待时间、队列、吞吐…）
│   ├── train.py                    # 训练入口
│   └── evaluate.py                 # 评估入口（控制器 × 场景 × 种子）
├── experiments/configs/            # 场景/超参数配置
├── results/                        # 原始结果 CSV
└── report/                         # 图表与最终报告
```

---

## 8. 时间线（示例，5 周，可按组内进度压缩）

| 周 | 里程碑 | 交付物 |
| --- | --- | --- |
| **W1** | SUMO 环境搭建 + 4 相位网络打通 | 能跑通单路口仿真（S1），读取队列/等待时间 |
| **W2** | 基线完成 + 场景阶梯 | 固定时长 / 基于队列（LQF）跑通，产出 S1–S4 初版对比 |
| **W3** | 表格型 Q-learning 训练 | 学习曲线收敛，S1–S4 上初步对比基线 |
| **W4** | **阶段一收尾**：完整实验 + 奖励/状态对比 | 主实验图表、`diff-waiting-time` vs `queue` 对比（阶段一交付） |
| **W5** | **阶段二**：DQN 扩展 + 报告 | 表格法 vs DQN 对比章、最终报告与代码整理 |

**建议分工维度**（按组员人数调整）：① SUMO 环境/网络；② RL 智能体（表格+DQN）；③ 基线控制器；④ 评估与可视化；⑤ 报告与整合。

---

## 9. 风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| SUMO/SUMO-RL 安装与 `SUMO_HOME` 配置 | 阻塞开发 | W1 先解决；用 `pip install sumo-rl`；记录安装文档；无 GUI 用 libsumo 加速 |
| **多相位 + 多车道 → 状态空间大** | 表格法收敛慢/次优 | 状态粗化（或 `states="state"` 网格）、降低决策频率、调 α/γ/ε；DQN 安排在阶段二，不提前切换 |
| 车道数变更后实验不可比 | 结论混乱 | `observation_space` 维度随车道数变化，改配置后**必须重跑基线** |
| 自建多车道含左转的路网工作量大 | 进度延迟 | **已完成**：改为配置驱动生成（`network.json` + `build_network.py`），改车道数不用手写 XML |
| 基线未调参导致结论偏乐观 | 结论可信度下降 | 报告中如实声明"统一默认参数"，并将其列为局限性（已按你的决定执行） |
| 场景需求 `λ` 不合理（过饱和/过空闲） | 区分度低 | 先用 S1 校准，再实测微调 S2–S4 的 `λ` |
| 仿真耗时长 | 训练/评估慢 | `use_gui=False` + `LIBSUMO_AS_TRACI=1`；多场景并行；控制种子数 |
| 跨机器结果不可复现 | 无法核验 | 固定 `sumo_seed`、写 requirements、结果落 CSV |

---

## 10. 待你确认的问题清单（Need your confirmation）

> 以下均为**细节确认**，不影响已定的技术路线（不阻塞 proposal）。

1. ~~**网络来源**~~：**已确定并实现**——用 `netconvert` 脚本生成（`network.json` + `build_network.py`），
   当前 4 车道 = 右/直/直/左，改车道数不用手写 XML。（§3.1）
2. **决策间隔** `delta_time`：定 **5 s** 还是 **1 s**？（§3.1）
3. **表格法状态**：用 SUMO-RL 的 `states="state"` 离散网格，还是自己做队列分箱？（§4.1）
4. **主奖励函数**：`diff-waiting-time` 还是 `queue`？（§4.2）
5. **场景 `λ` 数值**：S1–S4 的具体流量（600/1200/2000 是否合适）需 SUMO 实测后微调。（§6.1）
6. **组内分工与时间线**是否可行？（§8）

> **已确认项**：DQN 作为**阶段二**，在阶段一（表格法）完成并产出结果后启动，见 §0.1「两阶段计划」与 §4.4。

---

## 11. 参考（用于报告引用）

- Watkins & Dayan (1992), *Q-learning*.
- Sutton & Barto, *Reinforcement Learning: An Introduction*（Q-learning / DQN 章节）.
- Alegre (2019), *SUMO-RL: Reinforcement Learning environments for Traffic Signal Control with SUMO*（GitHub / Zenodo）.
- Ault & Sharon (2021), *Reinforcement Learning Benchmarks for Traffic Signal Control (RESCO)*.
- Wei et al. (2019), *A Survey on Traffic Signal Control Methods*（相关工作与指标惯例）.
- SUMO 文档：*Traffic Lights*、*Interfacing TraCI from Python*；`stable-baselines3` DQN 文档.

---

> **下一步**：路线已定（§0.1），本文档即为 **proposal 初稿**。请你在 §3 / §4 / §5 / §6 的 **【💬 我的想法】** 区块及 **§10** 中确认细节；确认后我会把本文档整理成正式的**开题报告**（或按老师要求的格式），**待你确认后**再开始写代码。

