# 项目结构 / Project Structure

本项目为小组作业 **AY10：基于强化学习的交通信号控制**。技术路线与实验设计见 `plan.md`，开题报告的方案部分见 `proposal/`。

**技术路线分两个阶段**：阶段一用**表格型 Q-learning** 跑通全流程并产出完整对比结果；阶段二在此基础上扩展 **DQN**，与表格法对照。

图例：✅ 已存在　🚧 计划中（尚未创建）

```
AY10/
├── README.md                       # 本文件：项目结构与环境配置说明            ✅
├── AY10.pdf                        # 课程作业原始要求                          ✅
├── plan.md                         # 方案与开题报告思路稿（已定技术路线）        ✅
├── proposal/                       # 开题报告（LaTeX 源文件与 PDF）             ✅
│   ├── proposal.tex                #   方案部分正文（XeLaTeX 编译）
│   └── proposal.pdf                #   编译产物
├── scripts/                        # 辅助脚本                                   ✅
│   ├── check_env.py                #   环境自检（SUMO / 依赖 / 仿真试跑）
│   └── demo_fixed_time.py          #   固定时长控制的 sumo-gui 动画演示
├── requirements.txt                # Python 依赖清单（已固定版本）               ✅
├── pytest.ini                      # pytest 配置（含 integration 标记）         ✅
├── CONTRIBUTING.md                 # 协作规范：分支 / 提交 / PR 流程             ✅
├── .gitignore                      # 排除虚拟环境 / 缓存 / 实验产物             ✅
├── nets/                           # SUMO 路网（由脚本生成，勿手改）               ✅
│   └── single-intersection/
│       ├── README.md                     # 路网说明与"如何改成自己的路网"        ✅
│       ├── network.json                  # 唯一需要改的配置（几何/车道/相位/流量）✅
│       ├── build_network.py              # 一键生成脚本                          ✅
│       ├── single-intersection.nod.xml   # 节点（路口 + 4 个边界）               ✅
│       ├── single-intersection.edg.xml   # 边（每方向一进一出，车道数由配置定）   ✅
│       ├── single-intersection.con.xml   # 连接（车道 -> 转向出口）              ✅
│       ├── single-intersection.tll.xml   # 信号配时（4 绿灯 + 4 黄灯）           ✅
│       ├── single-intersection.net.xml   # 最终路网（运行时使用）                ✅
│       ├── S1.rou.xml ~ S4.rou.xml       # 四场景需求（泊松到达）                ✅
│       ├── single-intersection.rou.xml   # 默认场景需求副本                      ✅
│       └── single-intersection.sumocfg   # 可直接 sumo-gui -c 打开               ✅
├── src/                            # 源代码                                   ✅
│   ├── config.py                   #   配置加载（默认值 + JSON 覆盖）
│   ├── factory.py                  #   控制器工厂（train/evaluate 共用）
│   ├── env/
│   │   ├── sumo_env.py             #   封装 SumoEnvironment、场景与随机种子
│   │   └── scenarios.py            #   场景 S1–S4（由易到难）
│   ├── agents/
│   │   ├── base.py                 #   控制器统一接口 select_action(obs)
│   │   ├── discretizer.py          #   观测 → 离散状态（供表格法使用）
│   │   ├── q_learning.py           #   表格型 Q-learning
│   │   └── dqn_agent.py            #   DQN（第二阶段，基于 stable-baselines3）
│   ├── controllers/
│   │   ├── fixed_time.py           #   基线一：固定时长控制
│   │   └── queue_based.py          #   基线二：基于队列控制（LQF）
│   ├── metrics.py                  #   等待时间、队列长度、吞吐量等指标
│   ├── train.py                    #   训练入口
│   └── evaluate.py                 #   评估入口（控制器 × 场景 × 种子）
├── experiments/                    # 实验配置                                   ✅
│   └── configs/                    # 场景与超参数配置（JSON）                   ✅
│       └── sample.json             #   示例配置（可直接 --config sample.json）
├── tests/                          # pytest 单元测试（不依赖 SUMO）              ✅
│   ├── conftest.py
│   ├── test_discretizer.py         #   观测离散化
│   ├── test_q_learning.py          #   表格 Q-learning
│   ├── test_controllers.py         #   固定时长 / LQF 基线
│   ├── test_metrics.py             #   指标汇总与 CSV 读取
│   ├── test_scenarios_config.py    #   场景与配置
│   ├── test_env_compat.py          #   环境接口兼容层
│   └── test_integration_sumo.py    #   集成测试（需 SUMO，默认跳过）
├── docs/                           # 文档                                       ✅
│   └── tasks.md                    # 任务分工（阶段一 / 阶段二）                 ✅
├── .github/                        # CI 配置                                    ✅
│   └── workflows/ci.yml            # GitHub Actions：提交即跑测试               ✅
├── results/                        # 实验输出 CSV（不入库）                     ✅
│   └── README.md                   #   目录用途说明
└── report/                         # 图表与最终报告（内容待填）                 🚧
    └── README.md                   #   目录用途说明
```

> 说明：图中省略了各包的 `__init__.py`（`src/__init__.py`、`src/env/__init__.py`、
> `src/agents/__init__.py`、`src/controllers/__init__.py`）以及 `proposal/` 下的
> LaTeX 中间产物（`.aux`、`.log`、`.fls`、`.fdb_latexmk`、`.synctex.gz`，已由 `.gitignore` 排除）。

**数据流**：`nets/`（路网与需求）→ `src/env/`（封装为 Gymnasium 环境）→ `src/agents/`＋`src/controllers/`（各控制器）→ `src/train.py` / `src/evaluate.py` → `results/`（CSV）→ `report/`（图表与报告）。

---

# 环境配置 / Environment Setup

## 1. 前置要求

| 组件 | 要求 | 说明 |
| --- | --- | --- |
| Python | ≥ 3.9（本项目在 3.11 下开发） | `sumo-rl` 要求 |
| SUMO | ≥ 1.14（建议 1.20 及以上） | `sumo-rl` 依赖 `sumolib`/`traci` ≥ 1.14 |
| 操作系统 | Windows / Linux / macOS | 命令按平台分别给出 |

> 注意：`pip install` 只装 SUMO 的 **Python 接口**，`sumo` / `sumo-gui` **可执行程序必须单独安装**，并通过 `SUMO_HOME` 与 `PATH` 暴露给 Python。

## 2. 安装 SUMO

**Windows**：从 <https://sumo.dlr.de/docs/Downloads.php> 下载`.msi`安装包，默认安装到
`C:\Program Files (x86)\Eclipse\Sumo`。

安装时勾选前两项添加到`PATH`中


**验证**：

```bash
sumo --version
sumo-gui --version
```


## 3. 安装 Python 依赖

创建并激活虚拟环境：

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

> 若 PowerShell 报"禁止运行脚本"，先执行：
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

安装依赖（**务必在虚拟环境下执行**，提示符应带 `(.venv)`）：

```bash
pip install -r requirements.txt
```

`sumo-rl` 会自动带入 `gymnasium`、`pettingzoo`、`traci`、`sumolib`、`pillow`；
`pytest` 也已包含在内，装完即可运行测试。

**阶段二（DQN）开始前**再启用：

把 `requirements.txt` 末尾被注释的 `# stable-baselines3==2.3.2` 取消注释，然后重新执行
`pip install -r requirements.txt`。不要改用 `[extra]` 版本 —— 它会额外拉入 opencv、pygame、autorom 等本项目用不到的包。

## 4. 验证安装

```bash
python scripts/check_env.py          # 检查 SUMO / 依赖 / 仿真是否正常
python scripts/demo_fixed_time.py    # 打开 sumo-gui 看固定配时的交通动画
python -m pytest                     # 运行 tests/ 中的全部单元测试
```


若第二条报 `SUMO_HOME` 相关错误，请回到第 3 步检查环境变量，并确认已重开终端。

## 5. 开发与测试

平时只需要一条命令：

```bash
python -m pytest        # 运行 tests/ 中的所有测试文件，87 个用例（不需要 SUMO）
```

- 大家一起怎么干活（fork、提交、口头汇报）：见 `CONTRIBUTING.md`
- 谁负责哪块：见 `docs/tasks.md`

## 6. 常用补充

**训练加速（可选）**：使用 libsumo 替代 TraCI，约 8 倍加速，但此时**不能**使用 `sumo-gui`，也不能并行跑多个仿真。

```powershell
$env:LIBSUMO_AS_TRACI=1     # Windows，当前会话有效
```

```bash
export LIBSUMO_AS_TRACI=1   # Linux / macOS
```

建议：训练时开启，调参与演示时关闭。

**动画演示（固定时长控制）**：

```bash
python scripts/demo_fixed_time.py                 # sumo-gui，600 仿真秒 ≈ 30 秒动画
python scripts/demo_fixed_time.py --duration 300 --delay 100
python scripts/demo_fixed_time.py --no-gui        # 无窗口自检
```

> 现在用的是 `nets/single-intersection/` 下**自己生成的路网**：
> 4 进口 × 4 车道（右/直/直/左）、4 相位（南北直行 → 南北左转 → 东西直行 → 东西左转）+ 黄灯，
> 周期 96 s，`action_count = 4`、观测 37 维。
> 若想换车道数/配时，改 `network.json` 后重跑
> `python nets/single-intersection/build_network.py`。

**换车流场景（S1–S4）**：`sumocfg` 里的 `route-files` 指向默认场景的副本。
最省事的临时切换方式是命令行覆盖（不改文件）：

```bash
sumo-gui -c nets/single-intersection/single-intersection.sumocfg -r S3.rou.xml --delay 50
```

要改默认场景，就改 `network.json` 的 `demand.default_scenario` 后重新生成。
> 注意：`build_network.py` 每次都会重写所有生成文件，**手改会被覆盖**。
> 另：`src/train.py` / `src/evaluate.py` 目前**还不会按场景自动选 `.rou.xml`**
> （见 `docs/tasks.md` 的"下一步"）。

---

# Title
基于强化学习的交通信号控制
Traffic Signal Control with Reinforcement Learning

# Description
创建一个简化的单路口仿真，并训练一个表格型 Q-learning 智能体来选择红绿灯相位。将其与固定时长控制和基于排队的控制策略在不同交通流模式下进行比较，测量平均等待时间和队列长度。
Create a simplified simulation of a single intersection and train a tabular Q-learning agent to select traffic light phases. Compare it with fixed-time and queue-based control policies under different traffic patterns, measuring average waiting time and queue length.

# Environment
构建一个简化版的单个交叉口仿真，车辆从不同方向到达并在队列中等待。你可以先从两个交通信号相位和简单的车辆到达模式开始。
Build a simplified simulation of a single intersection,where vehicles arrive from different directions and wait in queues. You can begin with two traffic light phases and simple vehicle arrival patterns.

# RL Agent
训练一个表格型Q学习智能体来选择交通信号相位。状态可以包括队列长度和当前信号相位，而奖励可以惩罚等待时间或过长队列。表格型Q学习将动作价值存储在表中，不需要神经网络，因此它提供了一个相对容易上手的起点。如果你们小组对深度强化学习感兴趣，可以选择性地将项目扩展到深度Q网络（DQN），并比较这两种方法。
Train a tabular Q-learning agent to select traffic light phases. The state could include queue lengths and the current light phase, while the reward could penalise waiting time or long queues. Tabular Q-learning stores action values in a table and does not require a neural network, so itprovides a relatively accessible starting point. If your group is interested in deep reinforcement learning, you could optionally extend the project to a Deep Q-Network (DQN) and compare the two approaches.  

# Baseline
将你的智能体与固定时间控制器以及基于队列的控制器进行比较。固定时间控制器按固定时间表切换信号灯，基于队列的控制器则优先放行等待车辆更多的方向。
Compare your agent with a fixed-time controller that switches lights on a regular schedule and a queue-based controller that prioritises the direction with more waiting vehicles

# Evaluate
在不同交通条件下进行测试，例如轻度交通、重度交通或各方向车流不均衡。平均等待时间和队列长度是有用的指标。
Test under different traffic conditions, such as light traffic, heavy traffic, or uneven flows across directions. Average waiting time and queue length are useful metrics.