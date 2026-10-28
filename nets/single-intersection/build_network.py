#!/usr/bin/env python
"""一键生成单路口路网（4 进口 × 3 车道 + 4 相位信号 + 泊松需求）。

用法（在项目根目录执行）::

    python nets/single-intersection/build_network.py
    python nets/single-intersection/build_network.py --config 其它配置.json
    python nets/single-intersection/build_network.py --check     # 只校验配置

产物（默认写入本目录）::

    single-intersection.nod.xml   节点（1 个信号灯路口 + 4 个边界节点）
    single-intersection.edg.xml   边（每个方向一进一出，车道数由配置决定）
    single-intersection.con.xml   连接（每条车道连到对应转向的出口）
    single-intersection.tll.xml   信号配时（4 绿灯 + 4 黄灯，可含全红）
    single-intersection.net.xml   netconvert 生成的最终路网（**运行时用这个**）
    S1.rou.xml ~ S4.rou.xml       各场景需求
    single-intersection.rou.xml   默认场景需求副本（供 sumo_env.py 直接使用）
    single-intersection.sumocfg   可直接 sumo-gui -c 打开
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# nets/single-intersection/build_network.py -> parents[0]=本目录, [1]=nets, [2]=项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.env.network_builder import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    build_all,
    load_network_config,
)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 SUMO 单路口路网")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 network.json）")
    parser.add_argument("--check", action="store_true", help="只校验配置，不生成文件")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    config = load_network_config(args.config or DEFAULT_CONFIG_PATH)

    road = config["road"]
    signal = config["signal"]
    print("[build] 配置：")
    print(f"  配置文件      : {config['_path']}")
    print(f"  输出目录      : {config['_dir']}")
    print(f"  车道（右→左） : {road['lane_movements']}  共 {len(road['lane_movements'])} 条")
    print(f"  路口半长      : {config['geometry']['arm_length']} m")
    print(
        f"  信号          : 直行 {signal['green_through']}s / 左转 {signal['green_left']}s"
        f" / 黄灯 {signal['yellow']}s / 全红 {signal.get('all_red', 0)}s"
    )

    if args.check:
        print("\n[build] --check：配置校验通过，未生成文件。")
        return 0

    result = build_all(config)

    print("\n[build] 路网：")
    print(f"  文件          : {result['net_file']}")
    print(f"  受控 link 数  : {result['n_links']}")
    print(f"  相位总数      : {result['n_phases']}（其中绿灯相位 {result['n_green_phases']} 个）")
    print(f"  绿灯相位名    : {', '.join(result['green_phase_names'])}")
    print(f"  周期时长      : {result['cycle_seconds']:g} s")

    print("\n[build] 需求：")
    for name, path in result["route_files"].items():
        print(f"  {name}: {path.name}")
    print(f"  默认场景 {result['default_scenario']} -> {result['default_route'].name}")

    print("\n[build] 完成。下一步可以：")
    print(f"  sumo-gui -c \"{result['sumocfg']}\"            # 看路网与固定配时动画")
    print("  python src/train.py --dry-run                # 确认 action_count 变为 4")
    print("  python scripts/demo_fixed_time.py            # 用新路网演示固定时长控制")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
