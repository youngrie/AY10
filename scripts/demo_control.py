#!/usr/bin/env python
"""用 sumo-gui 演示任意控制器的运行过程（带动画）。

与 ``demo_fixed_time.py`` 的区别：
* ``demo_fixed_time.py`` 用 SUMO 路网里内嵌的**固定配时**，与 Python 无关；
* 本脚本跑的是 ``src/factory.py`` 里的**真实控制器**（含 LQF / Q-learning），
  因此看到的就是评估时用的那套决策逻辑。

用法（在项目根目录执行）::

    python scripts/demo_control.py                                   # 默认 LQF，600 仿真秒
    python scripts/demo_control.py --controller queue_based --delay 100
    python scripts/demo_control.py --controller fixed_time --duration 300
    python scripts/demo_control.py --controller random --no-gui      # 无窗口自检

动画速度换算：``墙钟秒数 ≈ 仿真秒数 × delay / 1000``。
``delay=50`` 时，600 仿真秒约 30 秒放完。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import env_kwargs, load_config, resolve_config_path  # noqa: E402
from src.env import build_env, describe_env, reset_env, step_env  # noqa: E402
from src.factory import CONTROLLER_NAMES, build_controller  # noqa: E402


def drop_libsumo_flag() -> None:
    """libsumo 无法启动 GUI，若存在该环境变量则在本进程内移除。"""
    if os.environ.pop("LIBSUMO_AS_TRACI", None) is not None:
        print("[demo] 检测到 LIBSUMO_AS_TRACI=1，已在本进程内移除（libsumo 不支持 GUI）。")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 sumo-gui 演示控制器决策过程")
    parser.add_argument("--controller", default="queue_based",
                        choices=list(CONTROLLER_NAMES),
                        help="要演示的控制器（默认 queue_based）")
    parser.add_argument("--duration", type=int, default=600, help="仿真时长（秒，默认 600）")
    parser.add_argument("--delay", type=int, default=50, help="每步停留毫秒数（默认 50）")
    parser.add_argument("--seed", type=int, default=0, help="随机种子")
    parser.add_argument("--scenario", default=None,
                        help="场景名（S1–S4），决定使用哪份 <SCENARIO>.rou.xml")
    parser.add_argument("--config", default=None, help="配置文件（JSON）")
    parser.add_argument("--report-every", type=int, default=20, help="每多少步打印一次状态")
    parser.add_argument("--no-gui", action="store_true", help="不开窗口（仅自检用，动画无意义）")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    drop_libsumo_flag()

    config = load_config(resolve_config_path(args.config)) if args.config else load_config()
    config["env"]["num_seconds"] = args.duration
    if args.scenario is not None:
        config["scenario"] = args.scenario
    if not args.no_gui:
        config["env"]["use_gui"] = True

    # sumo-rl 会把 additional_sumo_cmd 原样拼到 SUMO 命令行后面。
    # 只传 --delay（每步停留毫秒数）即可控制动画速度。
    # 注意：SUMO 1.28 **没有** --start 参数（只有 --startup-wait-threshold），
    # 传了会让 sumo-gui 直接退出并报 "Could not connect"。
    overrides = {"out_csv_name": None}
    if not args.no_gui:
        overrides["additional_sumo_cmd"] = f"--delay {args.delay}"

    env = build_env(**env_kwargs(config, **overrides))
    try:
        print("[demo] 环境信息：")
        print(describe_env(env))

        controller = build_controller(args.controller, env, config, seed=args.seed)
        print(f"\n[demo] 控制器: {controller}")
        mode = "sumo-gui" if not args.no_gui else "sumo（无界面）"
        print(f"[demo] 模式: {mode}，仿真时长 {args.duration}s，延迟 {args.delay}ms/步\n")

        obs, _ = reset_env(env)
        controller.reset()

        delta_time = int(config["env"].get("delta_time", 5))
        n_steps = max(1, args.duration // delta_time)   # 每个决策步 = delta_time 秒

        prev_action = None
        total_reward = 0.0
        for step in range(1, n_steps + 1):
            action = controller.select_action(obs)
            if action != prev_action:
                print(f"  t={step * delta_time:6.0f}s  切换到动作 {action}")
                prev_action = action

            obs, reward, terminated, truncated, _ = step_env(env, action)
            total_reward += reward

            if step % max(1, args.report_every) == 0:
                print(f"  t={step * delta_time:6.0f}s  累计回报={total_reward:9.2f}")

            if terminated or truncated:
                break

        print(f"\n[demo] 结束：累计回报 {total_reward:.2f}")
        return 0
    except KeyboardInterrupt:
        print("\n[demo] 已手动中断。")
        return 130
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
