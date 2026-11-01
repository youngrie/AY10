"""评估入口：控制器 × 场景 × 种子的批量实验。

用法（在项目根目录执行）::

    python src/evaluate.py --dry-run
    python src/evaluate.py --controllers random fixed_time --seeds 0 1 --episodes 1
    python src/evaluate.py --config sample.json --controllers qlearning --seeds 0 1 2

输出
----
``results/eval_<scenario>.csv``，每个 (控制器, 种子, 回合) 一行，含
``avg_wait / avg_queue / max_queue / p95_wait / total_wait / mean_speed / duration``。

.. note::
   每个场景使用各自的 ``nets/single-intersection/<场景>.rou.xml``
   （由 ``build_env(scenario=...)`` 选择）。S1–S4 的车流强度不同，
   因此同一控制器在不同场景下的指标不可直接横向比较，应在**同一场景内**比较控制器。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import env_kwargs, load_config, resolve_config_path  # noqa: E402
from src.env import build_env, reset_env, step_env  # noqa: E402
from src.env.scenarios import SCENARIOS  # noqa: E402
from src.factory import build_controller  # noqa: E402
from src.metrics import (  # noqa: E402
    METRIC_FIELDS,
    aggregate_seeds,
    find_episode_csv,
    load_and_summarize,
)


def run_episode(env, controller, max_steps: int):
    """跑一个 episode，返回 ``(累计奖励, 步数)``。"""
    obs, _ = reset_env(env)
    controller.reset()

    total_reward, steps = 0.0, 0
    for _ in range(max_steps):
        action = controller.select_action(obs)
        next_obs, reward, terminated, truncated, _ = step_env(env, action)
        controller.update(obs, action, reward, next_obs, terminated)

        obs = next_obs
        total_reward += reward
        steps += 1
        if terminated or truncated:
            break
    return total_reward, steps


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量评估控制器")
    parser.add_argument("--config", default=None, help="配置文件（JSON）")
    parser.add_argument("--scenarios", nargs="+", default=list(SCENARIOS))
    parser.add_argument("--controllers", nargs="+", default=["random", "fixed_time"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--episodes", type=int, default=1, help="每个组合重复回合数")
    parser.add_argument("--max-steps", type=int, default=100_000)
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--keep-raw", action="store_true",
                        help="保留每个回合的原始逐步 CSV（默认删除，只留汇总 eval_*.csv）")
    parser.add_argument("--dry-run", action="store_true", help="只打印评估矩阵")
    return parser.parse_args(argv)


def merge_rows(path: Path, new_rows: List[dict], keys=("scenario", "controller", "seed", "episode")) -> List[dict]:
    """把新结果合并进已有 CSV：相同 key 的行被替换，其余保留。

    这样就能"一次只跑一个控制器"而不会冲掉之前的记录。
    """
    existing: List[dict] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = list(csv.DictReader(handle))

    new_keys = {tuple(str(row[k]) for k in keys) for row in new_rows}
    kept = [
        row for row in existing
        if tuple(str(row.get(k, "")) for k in keys) not in new_keys
    ]
    merged = kept + [{k: str(v) for k, v in row.items()} for row in new_rows]
    merged.sort(key=lambda row: tuple(str(row.get(k, "")) for k in keys))
    return merged


def main(argv=None) -> int:
    args = parse_args(argv)
    config = load_config(resolve_config_path(args.config)) if args.config else load_config()

    combos = len(args.scenarios) * len(args.controllers) * len(args.seeds) * args.episodes
    print("[evaluate] 评估矩阵：")
    print(f"  场景    : {args.scenarios}")
    print(f"  控制器  : {args.controllers}")
    print(f"  种子    : {args.seeds}")
    print(f"  每组合  : {args.episodes} 回合   合计 {combos} 次运行")
    print()
    if args.dry_run:
        return 0

    out_dir = PROJECT_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    episode_rows = []

    for scenario in args.scenarios:
        for controller_name in args.controllers:
            for seed in args.seeds:
                for episode in range(1, args.episodes + 1):
                    csv_prefix = out_dir / f"{scenario}_{controller_name}_s{seed}_e{episode}"
                    # scenario 决定实际用哪份 <SCENARIO>.rou.xml；
                    # sumo_seed 必须显式传，否则 SUMO 每次随机、结果不可复现
                    env = build_env(
                        **env_kwargs(
                            config,
                            out_csv_name=str(csv_prefix),
                            scenario=scenario,
                            sumo_seed=seed,
                        )
                    )
                    try:
                        controller = build_controller(controller_name, env, config, seed=seed)
                        total_reward, steps = run_episode(env, controller, args.max_steps)
                        if hasattr(env, "save_csv"):
                            env.save_csv(str(csv_prefix), 0)
                    finally:
                        env.close()

                    row = {
                        "scenario": scenario,
                        "controller": controller_name,
                        "seed": seed,
                        "episode": episode,
                        "episode_return": round(total_reward, 4),
                        "steps": steps,
                    }
                    try:
                        raw_csv = find_episode_csv(csv_prefix, 0)
                        row.update(load_and_summarize(raw_csv))
                        # SUMO-RL 的原始 CSV 文件名带 TraCI 连接标签（conn0/conn1/...），
                        # 每次评估都会新增一批、永不覆盖，很占地方。
                        # 汇总指标已经写入 eval_<场景>.csv，因此默认删除原始文件。
                        # 需要画时间序列时加 --keep-raw。
                        if not args.keep_raw:
                            raw_csv.unlink(missing_ok=True)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[evaluate] {csv_prefix.name} 指标缺失: {type(exc).__name__}")
                        row.update({field: float("nan") for field in METRIC_FIELDS})

                    episode_rows.append(row)
                    wait = row.get("avg_wait", float("nan"))
                    queue = row.get("avg_queue", float("nan"))
                    print(f"[{scenario}] {controller_name:<11} seed={seed} ep={episode} "
                          f"return={total_reward:10.2f} wait={wait:.2f}s queue={queue:.2f}")

    for scenario in args.scenarios:
        rows = [r for r in episode_rows if r["scenario"] == scenario]
        if not rows:
            continue
        path = out_dir / f"eval_{scenario}.csv"
        merged = merge_rows(path, rows)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(merged[0]))
            writer.writeheader()
            writer.writerows(merged)
        print(f"[evaluate] 已写入 {path}（累计 {len(merged)} 行）")

    print("\n[evaluate] 跨种子汇总（均值 ± 标准差）：")
    for scenario in args.scenarios:
        for controller_name in args.controllers:
            runs = [r for r in episode_rows
                    if r["scenario"] == scenario and r["controller"] == controller_name]
            if not runs:
                continue
            stats = aggregate_seeds(runs, fields=("avg_wait", "avg_queue", "max_queue"))
            print(f"  {scenario} / {controller_name:<11} "
                  f"avg_wait={stats['avg_wait']['mean']:.2f}±{stats['avg_wait']['std']:.2f}s  "
                  f"avg_queue={stats['avg_queue']['mean']:.2f}±{stats['avg_queue']['std']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

