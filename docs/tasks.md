# 任务分工

三个人各管一块，**按文件划分**，这样各自 fork 的改动合并回来基本不会冲突。
做完一项就把 `[ ]` 改成 `[x]`。

## 总体节奏：两个阶段

| 阶段 | 时间 | 目标 | 主导 |
| --- | --- | --- | --- |
| **阶段一** | 第 1–3 周 | 4 相位路网 + **表格型 Q-learning** + 两个基线，跑出 S1–S4 完整结果 | A 做路网、B 做表格法、C 做基线与评估 |
| **阶段二** | 第 4–5 周 | 扩展 **DQN**，与表格法对照 | B 主导，C 配合评估，A 保证路网稳定 |

> **阶段二在阶段一跑出完整结果之后再正式开工**，避免两条线都停在半成品。
> 但阶段二的准备（装依赖、跑通管线）可以提前做。

---

## A：环境与路网（`nets/`、`src/env/`）· 阶段一

- [x] 建路网：4 个进口，每方向多车道（**当前配置：4 车道 = 右/直/直/左**）
- [x] 4 相位信号程序（南北直行 → 南北左转 → 东西直行 → 东西左转）+ 黄灯过渡
- [x] 实现 `scenarios.build_route_file`：生成 S1–S4 的泊松需求 `.rou.xml`
- [ ] 做"相位 → 车道"映射（LQF 基线要用，目前 `QueueBasedController` 还构建不出来）
- [ ] 实测并校准三个流量档位（3 车道时测：S1 592/600、S2 1195/1200、S3 1953/2000、S4 1198/1200）

> 路网由 `nets/single-intersection/build_network.py` + `network.json` 生成，
> 换参数不用改代码。当前 4 车道配置下 `python src/train.py --dry-run` 显示
> `action_count : 4`、`observation_space` 37 维。
> **改了车道数以后旧实验结果不能直接对比，需重跑基线。**

**阶段二**：A 无新增任务，只需保证路网与需求文件稳定，配合 B 复跑实验。

---

## B：智能体（`src/agents/`）

**阶段一：表格型 Q-learning**

- [ ] 调参（α、γ、ε、训练回合数），跑出学习曲线
- [ ] 状态设计对比（分箱粒度粗 / 细，看哪个收敛更好）
- [ ] 奖励函数对比（`diff-waiting-time` vs `queue`）

**阶段二：DQN（阶段一完成后再开工）**

- [ ] 装依赖：`requirements.txt` 里取消 `stable-baselines3==2.3.2` 的注释并安装
- [ ] 在 `src/train.py` 接入 `--controller dqn`（`src/agents/dqn_agent.py` 已有骨架）
- [ ] 训练并保存模型；在 `src/evaluate.py` 把 `dqn` 纳入可评估控制器
- [ ] 与表格法在**同场景、同种子**下对照：性能、收敛速度、泛化

> 阶段二可以提前"预演"：DQN 不依赖 4 相位路网，可先用现有路网把管线跑通，
> 等阶段一结束再换成正式配置出结果。

---

## C：基线与评估（`src/controllers/`、`metrics.py`、`evaluate.py`、`report/`）

**阶段一**

- [ ] 固定时长基线校准（现在只是"每 6 次决策轮转一次相位"，周期和绿信比都要调）
- [ ] 多种子评估（每个"控制器 × 场景"至少 5 个种子，报均值 ± 标准差）
- [ ] 写 `scripts/plot_results.py`：从 `results/*.csv` 生成对比柱状图、学习曲线
- [ ] 报告里的主表、图表、结论

**阶段二**

- [ ] 把 DQN 的结果并入同一张对比表和同一组图表
- [ ] 写"表格法 vs DQN"对比小节（性能 / 收敛速度 / 泛化）

> 阶段一现在就能做的部分：画图脚本、评估流程（当前路网已可跑通）。

---

## 公共文件（改动前先在群里说一声）

`src/config.py`、`src/factory.py`、`src/agents/base.py`、`src/env/sumo_env.py`、
`src/env/network_builder.py`、`tests/`

## 当前状态提醒

- 路网已由我们自己生成：4 进口 × 4 车道（右/直/直/左），4 个绿灯相位，
  `action_count=4`，观测 37 维。
- **S1–S4 的场景还不会自动生效**：`sumo_env.resolve_net_files()` 只认
  `single-intersection.rou.xml` 这一份副本。目前要换场景，需改
  `network.json` 的 `demand.default_scenario` 后重新生成，或用
  `sumo -r S3.rou.xml` 手动指定。**这是待补的缺口（见"下一步"）**。
- 单种子实测（旧 3 车道路网）：`random` 等待 2.04s vs `fixed_time` 4.62s，
  说明**固定时长基线还没校准**（C 的任务）。

## 下一步（接口待打通）

| 待办 | 说明 |
| --- | --- |
| 场景参数传入环境 | `build_env(scenario="S3")` 应能选到 `S3.rou.xml`，目前写死 |
| LQF 可用 | 自动推导"相位 → 车道"映射，`factory` 增加 `queue_based` 分支 |
| DQN 训练接入 | `src/train.py` 的 `--controller dqn` 目前只打印提示 |
