"""训练入口。

用法（在项目根目录执行）::

    python src/train.py --dry-run                     # 只建环境并打印空间信息
    python src/train.py --controller qlearning --episodes 50
    python src/train.py --config sample.json --controller qlearning
    python src/train.py --controller random --episodes 1 --gui     # 看动画

参数优先级：**CLI 显式指定 > 配置文件 > src/config.py 的 DEFAULT_CONFIG**。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.q_learning import TabularQLearning  # noqa: E402
from src.config import env_kwargs, load_config, resolve_config_path  # noqa: E402
from src.env import build_env, describe_env, reset_env, step_env  # noqa: E402
from src.env.scenarios import summary_table  # noqa: E402
from src.factory import CONTROLLER_NAMES, build_controller  # noqa: E402
from src.metrics import find_episode_csv, load_and_summarize  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="训练交通信号控制智能体")
    parser.add_argument("--config", default=None, help="配置文件（JSON，如 sample.json）")
    parser.add_argument("--scenario", default=None,
                        help="场景名（S1–S4），决定使用哪份 <SCENARIO>.rou.xml")
    parser.add_argument("--controller", default=None, choices=list(CONTROLLER_NAMES),
                        help="控制器类型（默认取配置）：" + " / ".join(CONTROLLER_NAMES))
    parser.add_argument("--episodes", type=int, default=None, help="训练回合数")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--reward", default=None, help="SUMO-RL 奖励函数名")
    parser.add_argument("--num-seconds", type=int, default=None, help="每回合仿真时长（秒）")
    parser.add_argument("--delta-time", type=int, default=None, help="决策间隔（秒）")
    parser.add_argument("--gui", action="store_true", help="开启 sumo-gui")
    parser.add_argument("--out-csv", default=None,
                        help="CSV 输出前缀（如 results/run_s1）；给定时每回合统计指标")
    parser.add_argument("--max-steps", type=int, default=100_000, help="单回合最大步数（保护）")
    parser.add_argument("--save", default=None, help="训练结束后保存模型路径（qlearning）")
    parser.add_argument("--dry-run", action="store_true", help="只建环境并打印信息")
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> dict:
    """加载配置并应用命令行覆盖。"""
    config = load_config(resolve_config_path(args.config)) if args.config else load_config()

    if args.controller is not None:
        config["controller"] = args.controller
    if args.scenario is not None:
        config["scenario"] = args.scenario
    if args.episodes is not None:
        config["episodes"] = args.episodes
    if args.seed is not None:
        config["seed"] = args.seed
    if args.reward is not None:
        config["reward_fn"] = args.reward
    if args.num_seconds is not None:
        config["env"]["num_seconds"] = args.num_seconds
    if args.delta_time is not None:
        config["env"]["delta_time"] = args.delta_time
    if args.gui:
        config["env"]["use_gui"] = True
    if args.out_csv:
        config["env"]["out_csv_name"] = args.out_csv
    return config


def main(argv=None) -> int:
    args = parse_args(argv)
    config = build_config(args)

    controller_name = config["controller"]
    if controller_name == "dqn":
        print("[train] DQN 训练流程尚未接入（见 docs/tasks.md 中 B 的阶段二任务）。"
              "请先用 --controller qlearning 或 random。")
        return 2

    print("[train] 场景一览：")
    print(summary_table())

    env = build_env(**env_kwargs(config, sumo_seed=int(config["seed"])))
    try:
        print("\n[train] 运行配置：")
        print(f"  场景        : {env.ay10_scenario or '默认需求（未指定场景）'}")
        print(f"  需求文件    : {Path(env.ay10_route_file).name}")
        print("\n[train] 环境信息：")
        print(describe_env(env))
        if args.dry_run:
            print("\n[train] --dry-run：环境构建成功，跳过训练。")
            return 0

        controller = build_controller(controller_name, env, config, seed=int(config["seed"]))
        print(f"\n[train] 控制器: {controller}")

        out_csv = config["env"].get("out_csv_name")
        for episode in range(1, int(config["episodes"]) + 1):
            obs, _ = reset_env(env)
            controller.reset()

            total_reward, steps = 0.0, 0
            for _ in range(args.max_steps):
                action = controller.select_action(obs)
                next_obs, reward, terminated, truncated, _ = step_env(env, action)
                controller.update(obs, action, reward, next_obs, terminated)

                obs = next_obs
                total_reward += reward
                steps += 1
                if terminated or truncated:
                    break

            controller.on_episode_end()

            message = f"[episode {episode:4d}] return={total_reward:12.2f} steps={steps:5d}"
            if isinstance(controller, TabularQLearning):
                message += f" epsilon={controller.epsilon:.3f} states={controller.n_states}"

            if out_csv and hasattr(env, "save_csv"):
                try:
                    env.save_csv(out_csv, episode)
                    metrics = load_and_summarize(find_episode_csv(out_csv, episode))
                    message += (f" | avg_wait={metrics['avg_wait']:.2f}s"
                                f" avg_queue={metrics['avg_queue']:.2f}")
                except Exception as exc:  # noqa: BLE001
                    message += f" | 指标读取失败: {type(exc).__name__}"

            print(message)

        if args.save and hasattr(controller, "save"):
            controller.save(args.save)
            print(f"\n[train] 模型已保存到 {args.save}")
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
