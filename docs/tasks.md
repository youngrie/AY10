# 任务分工

三个人各管一块，**按文件划分**，这样各自 fork 的改动合并回来基本不会冲突。
做完一项就把 `[ ]` 改成 `[√]`。

## 总体节奏：两个阶段

| 阶段 | 时间 | 目标 | 主导 |
| --- | --- | --- | --- |
| **阶段一** | 第 1–3 周 | 4 相位路网 + **表格型 Q-learning** + 两个基线，跑出 S1–S4 完整结果 | A 路网、B 表格法、C 基线与评估 |
| **阶段二** | 第 4–5 周 | 扩展 **DQN**，与表格法对照 | B 主导，C 配合评估，A 保证路网稳定 |

> 阶段二在阶段一跑出完整结果之后再正式开工，避免两条线都停在半成品；
> 但阶段二的准备（装依赖、跑通管线）可以提前做。

## 进度总览

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| A 环境与路网 | **基本完成** | 路网/需求/相位映射/场景切换全部可用，仅剩可选的车道与配时微调 |
| B 智能体 | **未开始** | 代码骨架齐全并可运行，但调参与对比实验尚未做 |
| C 基线与评估 | **部分完成** | 评估流程已通，但**固定时长基线未校准**（见下方红字） |

---

## A：环境与路网（`nets/`、`src/env/`）· 阶段一

- [√] 建路网：4 个进口，每方向多车道（**当前：4 车道 = 右/直/直/左**）
- [√] 4 相位信号程序（南北直行 → 南北左转 → 东西直行 → 东西左转）+ 黄灯过渡
- [√] 实现 `scenarios.build_route_file`：生成 S1–S4 的泊松需求 `.rou.xml`
- [√] 做"相位 → 车道"映射（`src/env/phase_map.py`，LQF 已可用）
- [√] 实测并校准四个流量档位（1 小时实测插入车辆数）

  | 场景 | 设定 (veh/h) | 实测插入 | 偏差 |
  | --- | --- | --- | --- |
  | S1 | 600 | 592 | −1.3% |
  | S2 | 1200 | 1195 | −0.4% |
  | S3 | 2000 | 1953 | −2.4% |
  | S4 | 1200（3:1:1:1） | 1198 | −0.2% |

  全部在 ±3% 内，且所有车辆都能驶出网络（无阻塞）。
- [√] 场景切换：`build_env(scenario="S1")` 会用 `S1.rou.xml`；
  `train.py --scenario`、`evaluate.py --scenarios`、`demo_control.py --scenario` 均支持

> **路网怎么改**：只改 `nets/single-intersection/network.json`，然后
> `python nets/single-intersection/build_network.py`。当前 4 车道下
> `action_count = 4`、`observation_space` 37 维。
> **改了车道数后旧结果不可对比，基线要重跑。**
>
> 相位→车道映射可用 `python scripts/inspect_phase_map.py` 自检
> （当前：动作 0/2 各放行 6 条 = 右转+双直行，动作 1/3 各放行 2 条 = 左转）。

**阶段二**：A 无新增任务，只需保证路网与需求文件稳定，配合 B 复跑实验。

---

## B：智能体（`src/agents/`）

**阶段一：表格型 Q-learning**

- [ ] 调参（α、γ、ε、训练回合数），跑出学习曲线
- [ ] 状态设计对比（分箱粒度粗 / 细，看哪个收敛更好）
- [ ] 奖励函数对比（`diff-waiting-time` vs `queue`）
- [ ] 把训练好的 Q 表存下来（`--save`），供 C 评估时加载

**阶段二：DQN（阶段一完成后开工）**

- [ ] 装依赖：`requirements.txt` 里取消 `stable-baselines3==2.3.2` 的注释并安装
- [ ] 在 `src/train.py` 接入 `--controller dqn`（`src/agents/dqn_agent.py` 已有骨架）
- [ ] 训练并保存模型；在 `src/evaluate.py` 把 `dqn` 纳入可评估控制器
- [ ] 与表格法在**同场景、同种子**下对照：性能、收敛速度、泛化

> **现在就能做的准备**：DQN 不依赖新路网，可先用现有 4 相位路网
> 跑通"训练 → 保存 → 评估"管线，等阶段一结束再换成正式配置出结果。
>
> **重要背景**：表格法的难点在状态空间。观测含 16 条进口车道，
> 若每个车道分 5 档，状态数是天文数字——先做粗分箱（如每方向合并）
> 再谈收敛，这也正是引入 DQN 的动机。

---

## C：基线与评估（`src/controllers/`、`metrics.py`、`evaluate.py`、`report/`）

**阶段一**

- [√] **固定时长基线校准**（`[15,5,15,5]` 秒，周期 40s；见 `docs/baselines.md`）
- [√] 基线测量（3 种子 × 4 场景，平均等待 / 队列 / 最大队列 / 平均速度）
- [ ] 多种子评估扩展到 RL 控制器（Q-learning / DQN）
- [ ] 写 `scripts/plot_results.py`：从 `results/eval_*.csv` 出对比柱状图；
      学习曲线/时间序列需要原始 CSV，评估时加 `--keep-raw`
- [ ] 报告里的主表、图表、结论

**阶段二**

- [ ] 把 DQN 的结果并入同一张对比表和同一组图表
- [ ] 写"表格法 vs DQN"对比小节（性能 / 收敛速度 / 泛化）

> ✅ **基线已校准**（详见 [`baselines.md`](baselines.md)）。3 种子实测（平均等待，秒）：
>
> | 场景 | random | fixed_time | queue_based (LQF) |
> | --- | --- | --- | --- |
> | S1 (600) | 7.75 | 1.79 | **0.64** |
> | S2 (1200) | 8.29 | 1.68 | **1.26** |
> | S3 (2000) | 8.99 | 1.88 | **1.76** |
> | S4 (1200 不均衡) | 9.14 | 1.97 | **1.50** |
>
> 关键结论：
> 1. 校准前固定时长（12s）比随机还差；校准后降到 1.7–2.0s，是体面的基线。
> 2. **LQF 仍全面最优**，但优势随负荷收窄：轻载 2.8 倍 → 重载仅 1.07 倍。
> 3. RL 的对照基准应是 **LQF**；在 S3 只剩 7% 的提升空间，
>    报告里更应强调 S1/S2/S4 的提升与策略差异。
> 4. 教训：周期不能无限缩短——`10/5/10/5` 在 S3 下左转排队爆炸到 839s。

---

## 公共文件（改动前先在群里说一声）

`src/config.py`、`src/factory.py`、`src/agents/base.py`、`src/env/sumo_env.py`、
`src/env/network_builder.py`、`src/env/phase_map.py`、`tests/`

## 当前状态提醒

- 路网：4 进口 × 4 车道，4 个绿灯相位，`action_count=4`，观测 37 维。
- 场景：S1–S4 会真正切换车流（已实测，见 A 的表格）。
- 已验证可用的控制器：`random`、`fixed_time`（待校准）、`queue_based`；
  `qlearning` 可训练但尚未做对比实验；`dqn` 仅骨架。
- 所有命令都不需要手动改文件：`--scenario` / `--controller` / `--config` 即可。

## 下一步（按优先级）

| 优先级 | 待办 | 负责 | 说明 |
| --- | --- | --- | --- |
| **P0** | 表格法调参 + 存模型 | B | 基线已就绪，现在可以直接对比 |
| **P0** | `evaluate.py` 支持加载训练好的 Q 表 | B | 目前只能边训练边评估，没有 `--model` 参数 |
| ~~P0~~ | ~~固定时长基线校准~~ | C | **已完成**，见 [`baselines.md`](baselines.md) |
| P1 | `scripts/plot_results.py` | C | 从 `results/eval_*.csv` 一键出图 |
| P1 | RL 的多种子评估（≥5 种子） | C | 基线已用 3 种子，RL 用同样流程 |
| P2 | DQN 训练接入 | B | 阶段二主体 |
| P2 | 车道数/配时的补充实验 | A | 可选，作为鲁棒性分析 |

> 交接用的接口说明见 [`INTERFACE.md`](INTERFACE.md)。

## 常用命令速查

```bash
# 环境自检
python scripts/check_env.py

# 建/重建路网（改完 network.json 后）
python nets/single-intersection/build_network.py
python scripts/inspect_phase_map.py          # 检查相位→车道映射

# 训练 / 评估
python src/train.py --scenario S1 --controller qlearning --episodes 100 --save results/q_s1.pkl
python src/evaluate.py --scenarios S1 S2 S3 S4 --controllers random fixed_time queue_based --seeds 0 1 2

# 看动画
python scripts/demo_control.py --controller queue_based --scenario S3
```
