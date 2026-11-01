#!/usr/bin/env python
"""查看「绿灯相位 → 进口车道」的映射（LQF 依赖它）。

用法（在项目根目录执行）::

    python scripts/inspect_phase_map.py
    python scripts/inspect_phase_map.py --net nets/single-intersection/single-intersection.net.xml

输出示例::

    信号灯 'C'：4 个绿灯相位，16 条进口车道
      [0] 动作0  放行  6 条: n_in_0, n_in_1, n_in_2, s_in_0, s_in_1, s_in_2
      [1] 动作1  放行  2 条: n_in_3, s_in_3
      ...

改了车道数或信号相位之后，跑一次这个脚本能确认映射是否正确。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.env.phase_map import build_phase_lane_map, validate_phase_lane_map  # noqa: E402
from src.env.sumo_env import action_count, build_env  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查看相位 → 车道映射")
    parser.add_argument("--net", default=None, help="路网文件（默认用环境解析出的那份）")
    parser.add_argument("--num-seconds", type=int, default=30, help="仅用于建环境，默认 30")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # 映射需要 TrafficSignal（车道顺序 + 绿灯相位），所以要先建一个很短的仿真。
    env = build_env(num_seconds=args.num_seconds, use_gui=False, out_csv_name=None)
    try:
        mapping = build_phase_lane_map(env, net_file=args.net)
        print(mapping.describe())

        n_actions = action_count(env)
        print()
        print(f"动作空间大小 : {n_actions}")
        print(f"映射相位数   : {mapping.n_phases}")
        print(f"进口车道数   : {mapping.n_lanes}")
        print(f"每相位车道数 : {[len(x) for x in mapping.phase_lanes]}")

        covered = sorted({i for lanes in mapping.phase_lanes for i in lanes})
        print(f"覆盖车道下标 : {covered}")
        print(f"是否覆盖全部 : {covered == list(range(mapping.n_lanes))}")

        validate_phase_lane_map(mapping, n_actions)
        print("\n校验通过：可以直接用 --controller queue_based 运行。")
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
