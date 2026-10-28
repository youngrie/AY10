"""交通场景定义（S1–S4，由易到难）。

开题报告中的评估阶梯：

========  ==================  ===============  ==========  ============================
场景      交通条件             总需求(veh/h)    方向比      目的
========  ==================  ===============  ==========  ============================
S1        低流量、方向均衡        600          1:1:1:1     跑通全流程、验证指标正确性
S2        中流量、方向均衡       1200          1:1:1:1     观察 RL 是否开始优于固定时长
S3        高流量、方向均衡       2000          1:1:1:1     压力测试
S4        中流量、方向不均衡     1200          3:1:1:1     检验自适应与方向公平性
========  ==================  ===============  ==========  ============================

说明
----
* :data:`DIRECTIONS` 的顺序为 ``("N", "E", "S", "W")``，与 ``ratio`` 一一对应。
* 具体流量数值需在真实路网下校准（详见 plan.md §6.1）。
* :func:`build_route_file` 目前未实现——生成泊松需求的 ``.rou.xml``
  属于待实现的较复杂部分，先用路径文件占位（见 nets/ 目录说明）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

#: 进口方向（与 per_direction_demand / ratio 的顺序一致）
DIRECTIONS: Tuple[str, ...] = ("N", "E", "S", "W")

#: 场景配置表
SCENARIOS: Dict[str, Dict[str, object]] = {
    "S1": {
        "label": "低流量、方向均衡",
        "total_demand": 600,
        "ratio": (1, 1, 1, 1),
        "purpose": "跑通全流程、验证指标正确性",
    },
    "S2": {
        "label": "中流量、方向均衡",
        "total_demand": 1200,
        "ratio": (1, 1, 1, 1),
        "purpose": "观察 RL 是否开始优于固定时长",
    },
    "S3": {
        "label": "高流量、方向均衡",
        "total_demand": 2000,
        "ratio": (1, 1, 1, 1),
        "purpose": "压力测试，观察各策略在饱和附近的退化",
    },
    "S4": {
        "label": "中流量、方向不均衡",
        "total_demand": 1200,
        "ratio": (3, 1, 1, 1),
        "purpose": "检验自适应能力与方向公平性",
    },
}


def list_scenarios() -> Dict[str, Dict[str, object]]:
    """返回全部场景配置（只读用途）。"""
    return SCENARIOS


def get_scenario(name: str) -> Dict[str, object]:
    """按名称获取场景配置，如 ``get_scenario("S1")``。

    Raises:
        KeyError: 场景名不存在。
    """
    key = str(name).strip().upper()
    if key not in SCENARIOS:
        available = ", ".join(SCENARIOS)
        raise KeyError(f"未知场景 {name!r}；可选: {available}")
    return SCENARIOS[key]


def per_direction_demand(name: str) -> Dict[str, float]:
    """把总需求按方向比拆分成各方向的到达率（veh/h）。

    >>> per_direction_demand("S1")["N"]
    150.0
    """
    scenario = get_scenario(name)
    total = float(scenario["total_demand"])  # type: ignore[arg-type]
    ratio = tuple(scenario["ratio"])  # type: ignore[arg-type]
    weight_sum = float(sum(ratio))
    return {d: total * r / weight_sum for d, r in zip(DIRECTIONS, ratio)}


def summary_table() -> str:
    """生成场景摘要表（纯文本），便于在终端打印。"""
    header = f"{'场景':<6}{'交通条件':<22}{'需求(veh/h)':>12}{'方向比':>12}"
    lines = [header, "-" * 52]
    for key, cfg in SCENARIOS.items():
        ratio = ":".join(str(x) for x in cfg["ratio"])  # type: ignore[arg-type]
        lines.append(
            f"{key:<6}{str(cfg['label']):<22}{int(cfg['total_demand']):>12,}{ratio:>12}"
        )
    return "\n".join(lines)


def build_route_file(name: str, out_path: str | Path) -> Path:
    """根据场景生成 SUMO 需求文件（``.rou.xml``，泊松到达）。

    实现委托给 :mod:`src.env.network_builder`，与
    ``nets/single-intersection/build_network.py`` 使用**同一份配置**
    （``nets/single-intersection/network.json``），避免两处各写一套流量逻辑。

    流量拆分方式::

        某进口总流量 = total × 该方向权重 / 权重之和
        某转向流量   = 该进口总流量 × turn_ratio[转向]
        泊松到达     = period="exp(λ)"，λ = 转向流量 / 3600（辆/秒）

    Args:
        name: 场景名（如 ``"S1"``，大小写不敏感）。
        out_path: 目标文件路径。

    Returns:
        实际写出的文件路径。

    Raises:
        KeyError: 场景名不存在。
        FileNotFoundError: 找不到路网配置文件。
    """
    from .network_builder import load_network_config, write_route_file

    config = load_network_config()
    return write_route_file(config, name, out_path)


__all__ = [
    "DIRECTIONS",
    "SCENARIOS",
    "list_scenarios",
    "get_scenario",
    "per_direction_demand",
    "summary_table",
    "build_route_file",
]
