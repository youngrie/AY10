# `src/env/` —— 环境层

| 文件 | 职责 |
| --- | --- |
| `sumo_env.py` | 封装 SUMO-RL，提供统一的构建/步进接口 |
| `scenarios.py` | 场景 S1–S4 定义（流量档位） |
| `network_builder.py` | **配置化生成**路网 / 需求 / 信号配时 |
| `phase_map.py` | 推导"绿灯相位 → 进口车道"，供 LQF 使用 |
| `__init__.py` | 对外导出 `build_env` / `reset_env` / `step_env` 等 |

## `sumo_env.py` 要点

```python
env = build_env(num_seconds=600, use_gui=False, reward_fn="diff-waiting-time")
obs, info = reset_env(env)
obs, reward, terminated, truncated, info = step_env(env, action)
```

- **路网路径解析优先级**：`net_dir` 参数 > 环境变量 `AY10_NET_DIR` >
  `nets/single-intersection/` > `sumo-rl` 自带路网。
- 构建后会把实际路径记在 `env.ay10_net_file` / `env.ay10_route_file` 上，
  `phase_map` 等模块据此读取**同一个文件**。
- **参数过滤**：`filter_supported_kwargs()` 丢弃当前 SUMO-RL 版本不认识的参数。
- **奖励回退**：`reward_fn` 名称不被支持时，自动去掉该参数重试（打印提示）。

## `network_builder.py` 要点

**两遍 netconvert**：先由 `nod/edg/con` 出一版路网 → 读回 `linkIndex` →
拼出相位状态字符串 → 带配时再生成一次。这样改车道数/路口形状后信号仍对得上。

所有可变参数都在 `nets/single-intersection/network.json`，代码里只有逻辑。
详见 [`../../nets/single-intersection/README.md`](../../nets/single-intersection/README.md)。

## `phase_map.py` 要点

```python
from src.env.phase_map import build_phase_lane_map
mapping = build_phase_lane_map(env)      # PhaseLaneMap
mapping.phase_lanes                      # [[0,1,2,3,4,5], ...]
```

- 纯**静态解析** `.net.xml` 的 `<connection linkIndex=...>`，不依赖 TraCI 连接；
- 结果是"动作索引 → 观测中排队向量的下标"；
- 兼容性：`<connection tl=...>` 是 SUMO 标准格式，非本项目生成的路网同样适用。

## 场景切换（S1–S4）

`build_env(scenario="S3")` 会加载 `S3.rou.xml`；不传 `scenario` 时用默认需求文件
（`single-intersection.rou.xml`，即 `network.json` 中 `default_scenario` 的副本）。

```python
env = build_env(scenario="S1", num_seconds=600)
env.ay10_scenario      # 'S1'
env.ay10_route_file    # .../nets/single-intersection/S1.rou.xml
```

- 场景名大小写不敏感（`"s1"` 等价 `"S1"`）；
- 场景文件不存在时会抛 `FileNotFoundError`，并在报错里**列出该目录可用的场景**；
- `resolve_net_files()` / `available_scenarios()` 可用于查询。

命令行对应参数：

```bash
python src/train.py --scenario S1 --controller queue_based
python src/evaluate.py --scenarios S1 S3 --controllers random fixed_time queue_based
python scripts/demo_control.py --scenario S4
```

> 新增场景：在 `network.json` 的 `demand.scenarios` 里加一项，
> 重跑 `build_network.py` 生成 `<新场景>.rou.xml` 即可。
