# nets/single-intersection —— SUMO 路网与需求

本目录是**单路口路网的唯一来源**。路网不是手写的，而是由
`build_network.py` 读取 `network.json` 自动生成，改参数后重新跑一次即可。

## 一键生成

```bash
python nets/single-intersection/build_network.py          # 生成全部文件
python nets/single-intersection/build_network.py --check  # 只校验配置
```

生成过程（脚本内部会调用 SUMO 的 `netconvert`）：

1. 写 `nod` / `edg` / `con` 三个描述文件；
2. 先出一版路网，读回 `linkIndex`（信号状态字符串的顺序由它决定，不能写死）；
3. 按配置拼出 4 个绿灯相位 + 黄灯，写 `tll` 文件；
4. 带着配时再生成一次，得到内嵌信号配时的 `single-intersection.net.xml`。

## 生成的文件

| 文件 | 说明 |
| --- | --- |
| `network.json` | **唯一需要改的配置**：几何、车道、转向比例、相位时长、流量 |
| `build_network.py` | 一键生成脚本 |
| `single-intersection.nod.xml` | 节点：1 个信号灯路口中心 `C` + 4 个边界节点 `N/E/S/W` |
| `single-intersection.edg.xml` | 边：每个方向一进一出，车道数由配置决定 |
| `single-intersection.con.xml` | 连接：每条进口车道连到对应转向的出口车道 |
| `single-intersection.tll.xml` | 信号配时：4 绿灯 + 4 黄灯（可选全红） |
| `single-intersection.net.xml` | **运行时使用的路网**（已内嵌信号配时） |
| `S1.rou.xml` ~ `S4.rou.xml` | 四个场景的需求（泊松到达） |
| `single-intersection.rou.xml` | 默认场景副本，供 `src/env/sumo_env.py` 直接使用 |
| `single-intersection.sumocfg` | 可直接 `sumo-gui -c` 打开 |

## 路网结构

```
              N
              │  n_in：4 车道（右/直/直/左，当前配置）
              │
   W ─────────┼───────── E      路口中心 C 是信号灯节点（tlLogic id = "C"）
              │
              │  s_in：4 车道（右/直/直/左）
              S
```

- **车道顺序**：SUMO 中 lane 0 是**最右侧**。当前配置
  `["right","through","through","left"]` 表示 lane0=右转、lane1/2=直行、lane3=左转；
- **转向推导**：脚本按"驶入方向 ± 90°"自动算出口边，不需要手工查表；
- **信号相位**（周期 96 s）：

| 相位 | 绿灯方向 | 时长 |
| --- | --- | --- |
| `NS_through` | 南北直行 + 右转 | 30 s |
| `NS_left` | 南北左转（保护式） | 12 s |
| `EW_through` | 东西直行 + 右转 | 30 s |
| `EW_left` | 东西左转（保护式） | 12 s |

每个绿灯后插入 3 s 黄灯。SUMO-RL 会把 4 个绿灯相位识别为 4 个动作
（`action_count == 4`）。

## 想改成自己的路网？

只改 `network.json`，不用动代码：

| 想改什么 | 改哪个字段 |
| --- | --- |
| 路口大小（臂长） | `geometry.arm_length` |
| 车道数与车道功能 | `road.lane_movements`，见下方示例 |
| 限速 | `road.speed_limit` |
| 左/直/右车流比例 | `turn_ratio`（三者之和必须为 1） |
| 绿灯/黄灯/全红时长 | `signal.*` |
| 右转是否跟随左转也放行 | `signal.right_turns_green_in_both` |
| 各场景流量 | `demand.scenarios.*.total` / `.ratio` |
| 到达方式（泊松/均匀） | `demand.arrival` |
| 车辆参数 | `demand.vtype` |

**`lane_movements` 示例**（顺序 = 从最右侧车道往左数）：

| 配置 | 含义 | 受控 link 数 |
| --- | --- | --- |
| `["through"]` | 1 车道，只能直行 | 4 |
| `["through", "left"]` | 2 车道：直行 + 左转（无右转） | 8 |
| `["right", "through", "left"]` | 3 车道：只有一条直行 | 12 |
| `["right", "through", "through", "left"]` | 4 车道：两条直行（**当前配置**） | 16 |
| `["right", "through", "left", "left"]` | 4 车道：双左转（大流量左转路口） | 16 |

> **允许重复**：多条车道可以用同一转向。它们会各自连到出口边的不同车道，
> 不会冲突。改完后 `action_count` 仍是 4（绿灯相位个数不变），
> 只有 `observation_space` 的维度会随车道数变化。

改完重新执行 `python nets/single-intersection/build_network.py` 即可。

> ⚠️ **一个 SUMO 的坑**：`<flow period="exp(x)">` 里的 `x` 是**速率 λ（辆/秒）**，
> 不是平均车头时距。平均 120 s 一辆 ⇒ 要写 `exp(0.00833)`，写成 `exp(120)`
> 会让流量直接挤到饱和。生成器已按正确方式计算。

## 与代码的对接

- `src/env/sumo_env.py` 会优先使用本目录的
  `single-intersection.net.xml` + `single-intersection.rou.xml`；
  找不到时才回退到 `sumo-rl` 自带路网。
- `src/env/scenarios.py::build_route_file` 与生成器共用同一份 `network.json`。
- 验证：`python src/train.py --dry-run` 应显示 `action_count : 4`。

## ⚠️ 看动画必须加 `--delay`

`sumo-gui` **默认以最快速度运行**（`--delay 0`），并不按真实时间播放。
这就是"3600 秒的仿真一两秒就跑完"的原因——**不是配置错了，也不是单位错了**：

```
$ sumo -c single-intersection.sumocfg
Simulation ended at time: 3600.00.
Duration: 1.50s                    ← 墙钟只用了 1.5 秒
Real time factor: 2398.4           ← 快放约 2400 倍
```

`--delay` 的单位是**每步停顿的毫秒数**（步长默认 1 仿真秒），换算：

```
墙钟秒数 ≈ 仿真秒数 × delay(ms) / 1000
```

| 想看什么 | 命令 | 墙钟 |
| --- | --- | --- |
| 一个完整信号周期（96 s） | `sumo-gui -c single-intersection.sumocfg --duration 96 --delay 50` | 约 5 s |
| 半小时仿真 | `sumo-gui -c single-intersection.sumocfg --duration 1800 --delay 20` | 约 36 s |
| 完整 1 小时 | `sumo-gui -c single-intersection.sumocfg --duration 3600 --delay 10` | 约 36 s |

> 也可在 GUI 右下角拖 **Delay** 滑块；`--no-gui` 时 delay 无意义（没有画面可播放）。
> 更省事的是直接用 `python scripts/demo_fixed_time.py`（默认已是 GUI + 50ms）。

## 参考

- 路网生成：<https://sumo.dlr.de/docs/netconvert.html>
- 信号程序 `<tlLogic>`：<https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html>
- 需求 `<flow>`：<https://sumo.dlr.de/docs/Demand/Flows.html>

