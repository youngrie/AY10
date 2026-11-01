# `scripts/` —— 辅助脚本

四个脚本各管一件事，都不是实验主流程（主流程是 `src/train.py` / `src/evaluate.py`）。

| 脚本 | 用途 |
| --- | --- |
| `check_env.py` | **环境自检**：SUMO / `SUMO_HOME` / 依赖 / 路网 / 一次短仿真 |
| `demo_control.py` | 用 sumo-gui 看**某个控制器**（固定配时 / LQF / Q-learning）的决策动画 |
| `calibrate_baselines.py` | **基线校准**：扫描固定时长的「周期 × 绿信比」组合 |
| `inspect_phase_map.py` | 打印"相位 → 车道"映射（改车道/相位后自检） |

## 常见用法

```bash
# 装完环境先跑这个
python scripts/check_env.py
python scripts/check_env.py --no-sim      # 只做静态检查

# 看固定配时动画（600 仿真秒 ≈ 30 秒）
python scripts/demo_control.py

# 看 LQF 决策动画（默认就是 queue_based）
python scripts/demo_control.py
python scripts/demo_control.py --controller qlearning --duration 300
python scripts/demo_control.py --delay 100           # 慢放

# 改完车道后确认映射仍然正确
python scripts/inspect_phase_map.py

# 重新校准固定时长基线（扫描周期 × 绿信比）
python scripts/calibrate_baselines.py --scenarios S2 --cycles 30 40 60
```

## 关于动画速度

`--delay` 单位是**毫秒/仿真步**（步长默认 1 秒）：

```
墙钟秒数 ≈ 仿真秒数 × delay / 1000
```

| 参数 | 墙钟 |
| --- | --- |
| `--duration 60 --delay 20` | ≈ 1.2 s |
| `--duration 600 --delay 50` | ≈ 30 s（默认） |
| `--duration 600 --delay 100` | ≈ 60 s |

## ⚠️ 踩过的坑

1. **SUMO 1.28 没有 `--start` 参数**（只有 `--startup-wait-threshold`）。
   误传会让 `sumo-gui` 立即退出，报 `traci.exceptions.FatalTraCIError: Could not connect.`。
2. **`LIBSUMO_AS_TRACI=1` 时无法开 GUI**。`demo_*` 脚本会在本进程内自动移除该变量。
3. **`--no-gui` 时 `--delay` 无意义**——没有画面可播放，仿真会瞬间跑完。
