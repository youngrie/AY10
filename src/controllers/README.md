# `src/controllers/` —— 基线控制器

两个基线都实现 `BaseController`，可直接与 RL 智能体在同一循环里对比。

| 文件 | 控制器 | 说明 |
| --- | --- | --- |
| `fixed_time.py` | `FixedTimeController` | 每 `switch_every` 次决策轮转到下一个绿灯相位 |
| `queue_based.py` | `QueueBasedController` | LQF：选排队总和最大的相位 |

## 固定时长控制（两种含义，别混淆）

1. **SUMO 静态配时**（路网自带，`nets/.../*.tll.xml` → 内嵌进 `net.xml`）：
   纯 SUMO 运行时就按这个循环，与 Python 无关，可用
   `python scripts/demo_control.py --controller fixed_time` 观看。改它要动 `network.json` 的 `signal.*`。
2. **Python 侧 `FixedTimeController`**：为了能和 RL 放在同一个实验循环里比较，
   按 `durations`（每相位绿灯秒数）或 `switch_every`（等长轮转）切换相位。
   当前默认 `durations = [15, 5, 15, 5]`（**已校准**，周期 40s，见 `docs/baselines.md`）。

> 严格意义上第 1 种才是"固定配时基线"。当前 `evaluate.py` 里的 `fixed_time`
> 用的是第 2 种，且 `switch_every` 尚未针对路网校准（这是 C 的任务）。

## LQF（最长排队优先）

```python
QueueBasedController(n_phases=4, n_lanes=16, phase_lanes=[[...], ...],
                     hold_on_min_green=True)
```

- `phase_lanes`：每个相位放行的车道在**观测排队向量**中的下标；
  现在由 `src/env/phase_map.py` **自动推导**，不用手填：
  ```python
  controller = build_controller("queue_based", env, config)  # factory 内部自动推导
  ```
- 决策规则：
  1. 最小绿灯未满足（`min_green` 标志为 0）→ **保持**当前相位；
  2. 否则选"该相位放行车道排队总和"最大的相位。

## 实测表现（S3 默认需求，单种子，仅作参考）

| 控制器 | 平均等待时间 |
| --- | --- |
| `random` | 8.78 s |
| `fixed_time` | 12.00 s |
| **`queue_based`（LQF）** | **1.94 s** |

> LQF 是很强的基线，**RL 要超过它并不容易**，这是报告里值得重点分析的结论。
> 另外 LQF 换相位很频繁（约 10 秒一次），实际路口会避免这种抖动——
> 可作为"加入切换惩罚"的动机。

## 配置项

```json
"fixed_time": { "switch_every": 6 },
"queue_based": { "hold_on_min_green": true }
```

## 新增基线

实现 `BaseController` 子类 → 在 `src/factory.py` 的 `CONTROLLER_NAMES` 与
`build_controller()` 注册 → 在 `tests/test_controllers.py` 加用例。
