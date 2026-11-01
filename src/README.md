# `src/` —— 源代码总览

按"环境 / 智能体 / 控制器 / 评估"分层，各层通过统一接口解耦，
所以**换控制器不用动环境，换车道数不用动智能体**。

## 目录地图

| 路径 | 职责 | 详细说明 |
| --- | --- | --- |
| `config.py` | 实验配置（`DEFAULT_CONFIG` + JSON 深合并） | 见下方"配置优先级" |
| `env/` | SUMO 环境封装、场景定义、路网生成、相位映射 | [`env/README.md`](env/README.md) |
| `agents/` | 观测离散化、表格型 Q-learning、DQN 骨架 | [`agents/README.md`](agents/README.md) |
| `controllers/` | 基线控制器（固定时长、LQF） | [`controllers/README.md`](controllers/README.md) |
| `factory.py` | 控制器工厂（train / evaluate 共用） | 见下方"新增控制器" |
| `metrics.py` | 指标汇总（读 SUMO-RL 的 CSV） | 字段见 `METRIC_FIELDS` |
| `train.py` | 训练入口 | `python src/train.py --help` |
| `evaluate.py` | 批量评估入口（控制器 × 场景 × 种子） | `python src/evaluate.py --help` |

## 数据流

```
network.json ──build_network.py──> net.xml + rou.xml
                                        │
                           env/sumo_env.build_env()
                                        ↓
                     SumoEnvironment（Gymnasium 接口）
                                        │  obs / action
                       factory.build_controller(name, env)
                                        ↓
                   BaseController.select_action(obs) -> int
                                        ↓
                          env.step(action) -> reward
                                        ↓
                    metrics（读 CSV）+ results/*.csv
```

## 统一约定（改动前请确认没人依赖）

1. **控制器接口**（`agents/base.py`）：`select_action(obs) -> int`，
   可选 `reset()` / `update(...)` / `on_episode_end()` / `save()` / `load()`。
2. **环境返回值**：`reset_env(env) -> (obs, info)`；
   `step_env(env, action) -> (obs, reward, terminated, truncated, info)`。
   （`sumo-rl` 不同版本签名不同，这两个包装函数负责抹平差异。）
3. **动作**：`Discrete(n_green_phases)`，即"选第几个绿灯相位"。
4. **观测**：`[phase_one_hot, min_green, density(各车道), queue(各车道)]`，
   已被 SUMO-RL **归一化到 [0,1]**。

## 配置优先级

```
命令行显式参数  >  --config 指定的 JSON  >  src/config.py 的 DEFAULT_CONFIG
```

配置项集中在 `DEFAULT_CONFIG`，不要在代码里散落魔法数字。

## 新增控制器

1. 在 `agents/` 或 `controllers/` 实现 `BaseController` 子类；
2. 在 `factory.py` 的 `CONTROLLER_NAMES` 与 `build_controller()` 注册；
3. 在 `tests/` 加用例 —— 有个测试会检查 `train.py` 的 `--controller`
   是否覆盖了 `CONTROLLER_NAMES` 全部项（防止再次"加了控制器但命令行不认"）。

## 运行

```bash
python src/train.py --dry-run                    # 只建环境、打印空间信息
python src/train.py --controller qlearning --episodes 50 --out-csv results/q
python src/evaluate.py --controllers random fixed_time queue_based --seeds 0 1 2
```
