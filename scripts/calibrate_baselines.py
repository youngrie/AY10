#!/usr/bin/env python
"""基线校准：为固定时长控制器搜索合适的配时方案。

为什么要校准
------------
"每 N 次决策轮转一次相位"对 4 相位并不合适：若每个相位都放 30 秒，
而左转只承担 20% 的车流，绿灯就浪费在没车的方向上了。必须**按相位分配
不同的绿灯时长**（直行长、左转短），固定时长基线才具有说服力。

搜索空间
--------
* 周期（4 个绿灯相位总时长，不含黄灯）：60 / 76 / 86 / 96 / 120 秒
* 绿信比：``equal``（均分）/ ``demand``（按各相位承担的车流比例）

评测方式
--------
每个候选方案在 S1–S4 各跑一次（默认单种子），以**四个场景平均等待时间的均值**
打分，取最优。结果写入 ``results/baseline_calibration.csv``。

用法::

    python scripts/calibrate_baselines.py
    python scripts/calibrate_baselines.py --seeds 0 1 2
    python scripts/calibrate_baselines.py --scenarios S2
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import env_kwargs, load_config  # noqa: E402
from src.controllers.fixed_time import FixedTimeController  # noqa: E402
from src.env import build_env, reset_env, step_env  # noqa: E402
from src.env.sumo_env import action_count  # noqa: E402
from src.metrics import find_episode_csv, load_and_summarize  # noqa: E402

#: 4 个相位承担的车流比例（NS直行 / NS左转 / EW直行 / EW左转）。
#: 每个进口 20% 左转、60% 直行、20% 右转，右转跟随直行相位放行，
#: 故直行相位承载 80%、左转相位承载 20%；南北东西对称 → 4:1:4:1。
PHASE_DEMAND_WEIGHTS = (0.4, 0.1, 0.4, 0.1)


def split_durations(cycle: float, mode: str, n_phases: int) -> List[float]:
    """按周期与绿信比模式，算出每个相位的绿灯时长（秒）。

    Args:
        cycle: 4 个绿灯相位的总时长（秒，不含黄灯）。
        mode: ``"equal"``（均分）或 ``"demand"``（按车流比例）。
        n_phases: 相位个数。

    Returns:
        长度等于 ``n_phases`` 的时长列表，每项至少 1 秒。
    """
    if mode == "equal":
        weights = [1.0 / n_phases] * n_phases
    elif mode == "demand":
        if n_phases != len(PHASE_DEMAND_WEIGHTS):
            raise ValueError(
                f"demand 模式只支持 {len(PHASE_DEMAND_WEIGHTS)} 个相位，当前 {n_phases}"
            )
        total = sum(PHASE_DEMAND_WEIGHTS)
        weights = [w / total for w in PHASE_DEMAND_WEIGHTS]
    else:
        raise ValueError(f"未知模式 {mode!r}，可选: equal / demand")

    return [max(1.0, cycle * w) for w in weights]


def evaluate_plan(
    config: dict,
    scenarios: Sequence[str],
    seeds: Sequence[int],
    durations: Sequence[float] | None,
    switch_every: int = 6,
    label: str = "",
) -> Dict[str, float]:
    """跑一个固定时长方案，返回各场景汇总后的指标。

    Args:
        durations: 每个相位的绿灯时长（秒）；``None`` 表示按 ``switch_every`` 等长配时。
        label: 打印进度时用的方案名。

    Returns:
        ``{"avg_wait", "avg_queue", "max_queue", "per_scenario"}``
    """
    delta_time = float(config["env"].get("delta_time", 5))
    n_steps = max(1, int(config["env"]["num_seconds"] // delta_time))

    wait_values: List[float] = []
    queue_values: List[float] = []
    max_queue_values: List[float] = []
    per_scenario: Dict[str, float] = {}

    total_runs = len(scenarios) * len(seeds)
    done = 0

    for scenario in scenarios:
        scenario_waits: List[float] = []
        for seed in seeds:
            started = time.perf_counter()
            # save_csv 的文件名含 TraCI 连接标签（conn0/conn1/...），
            # 每建一次环境标签就变，所以必须用**唯一前缀**，否则会读到上一次的文件。
            prefix = PROJECT_ROOT / "results" / f"_calib_{scenario}_{seed}"
            env = build_env(
                **env_kwargs(
                    config,
                    scenario=scenario,
                    out_csv_name=str(prefix),
                    sumo_seed=seed,
                    additional_sumo_cmd="--no-step-log true",
                )
            )
            try:
                controller = FixedTimeController(
                    action_count(env),
                    switch_every=switch_every,
                    durations=durations,
                    delta_time=delta_time,
                )
                obs, _ = reset_env(env)
                controller.reset()
                for _ in range(n_steps):
                    obs, reward, terminated, truncated, _ = step_env(
                        env, controller.select_action(obs)
                    )
                    if terminated or truncated:
                        break
                env.save_csv(str(prefix), 0)
            finally:
                env.close()

            csv_path = find_episode_csv(prefix, 0)
            metrics = load_and_summarize(csv_path)
            csv_path.unlink(missing_ok=True)

            done += 1
            elapsed = time.perf_counter() - started
            print(
                f"      [{done}/{total_runs}] {label} {scenario} seed={seed}"
                f" -> 等待 {metrics['avg_wait']:6.2f}s 队列 {metrics['avg_queue']:5.2f}"
                f"  ({elapsed:.1f}s)"
            )

            scenario_waits.append(metrics["avg_wait"])
            queue_values.append(metrics["avg_queue"])
            max_queue_values.append(metrics["max_queue"])

        wait_values.extend(scenario_waits)
        per_scenario[scenario] = sum(scenario_waits) / len(scenario_waits)

    n = len(wait_values)
    return {
        "avg_wait": sum(wait_values) / n,
        "avg_queue": sum(queue_values) / len(queue_values),
        "max_queue": max(max_queue_values),
        "per_scenario": per_scenario,
    }


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校准固定时长基线")
    parser.add_argument("--scenarios", nargs="+", default=["S1", "S2", "S3", "S4"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--cycles", nargs="+", type=float, default=[60, 76, 86, 96, 120])
    parser.add_argument("--out", default="results/baseline_calibration.csv")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    config = load_config()
    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"[calib] 场景: {args.scenarios} | 种子: {args.seeds}")
    print(f"[calib] 候选周期: {args.cycles}（每个周期 × equal/demand 两种绿信比）")
    print(f"[calib] 每次运行 = {config['env']['num_seconds']}s 仿真，"
        f"单个方案约需 {len(args.scenarios) * len(args.seeds) * 3} 秒\n")

    # 对照组：原先的等长配时（switch_every=6 -> 30s/相位）
    print("[calib] >>> 方案 1：旧等长配时 30/30/30/30s")
    baseline = evaluate_plan(
        config, args.scenarios, args.seeds, durations=None, label="旧等长"
    )
    rows.append({
        "plan": "equal_switch_every(旧)",
        "cycle_s": 120,
        "durations_s": "30/30/30/30",
        **{k: baseline[k] for k in ("avg_wait", "avg_queue", "max_queue")},
    })
    print(f"[calib] <<< 旧等长配时: 平均等待 {baseline['avg_wait']:.2f}s"
        f" 平均队列 {baseline['avg_queue']:.2f}\n")

    plan_index = 1
    for cycle in args.cycles:
        for mode in ("equal", "demand"):
            plan_index += 1
            durations = split_durations(cycle, mode, 4)
            label = "%s_%.0fs" % (mode, cycle)
            text = "/".join(f"{d:.0f}" for d in durations)
            print(f"[calib] >>> 方案 {plan_index}：{label}（{text}s）")
            result = evaluate_plan(
                config, args.scenarios, args.seeds,
                durations=durations, label=label,
            )
            rows.append({
                "plan": label,
                "cycle_s": cycle,
                "durations_s": text,
                **{k: result[k] for k in ("avg_wait", "avg_queue", "max_queue")},
            })
            print(f"[calib] <<< {label}: 平均等待 {result['avg_wait']:.2f}s"
                f" 平均队列 {result['avg_queue']:.2f}\n")

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    best = min(rows, key=lambda r: r["avg_wait"])
    print(f"\n[calib] 最优: {best['plan']}（{best['durations_s']}s）"
        f" 平均等待 {best['avg_wait']:.2f}s 平均队列 {best['avg_queue']:.2f}")
    print(f"[calib] 明细: {out_path}")

    for leftover in (PROJECT_ROOT / "results").glob("_calib_tmp*.csv"):
        leftover.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

