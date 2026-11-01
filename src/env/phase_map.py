"""推导「绿灯相位 → 进口车道」的映射，供 LQF 等基于队列的控制器使用。

为什么需要这个映射
------------------
SUMO-RL 把各进口车道的排队长度放在观测末尾：

    obs = [phase_one_hot, min_green, density(lanes...), queue(lanes...)]

顺序由 ``TrafficSignal.lanes`` 决定（例如 ``['n_in_0', ..., 'w_in_3']``），
而动作是"第几个绿灯相位"。要把"某相位该看哪些车道的排队"对上，
就必须知道：**每个绿灯相位放行了哪几条车道**。

推导方法（纯静态，不依赖 TraCI 连接）
--------------------------------------
1. 从 ``.net.xml`` 读 ``<connection tl="C" linkIndex="i" from="n_in" fromLane="2">``，
   得到 ``linkIndex i -> 车道 n_in_2``；
2. 每个绿灯相位的 ``state`` 字符串按 linkIndex 排列，
   第 i 位是 ``G``/``g`` 即表示该 link 放行；
3. 于是"放行的 linkIndex" → "车道 id" → "在 ``ts.lanes`` 中的下标"。

注意：状态字符串的下标就是 linkIndex，这是 SUMO 的约定，
也与 ``network_builder`` 生成 ``tll.xml`` 的方式一致。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

#: 表示"绿灯"的字符（G=有优先权，g=需让行）
GREEN_CHARS = "Gg"


@dataclass(frozen=True)
class PhaseLaneMap:
    """一个信号灯的「相位 → 车道」映射。

    Attributes:
        tls_id: 信号灯 id（如 ``"C"``）。
        lanes: 观测中车道的顺序（车道 id 列表）。
        phase_lanes: 长度 = 绿灯相位个数；``phase_lanes[a]`` 是动作 a 放行的
            车道在 ``lanes`` 中的下标列表。
        phase_names: 可选，相位名称（如 ``NS_through``）。
    """

    tls_id: str
    lanes: List[str]
    phase_lanes: List[List[int]]
    phase_names: List[str] = field(default_factory=list)

    @property
    def n_phases(self) -> int:
        return len(self.phase_lanes)

    @property
    def n_lanes(self) -> int:
        return len(self.lanes)

    def describe(self) -> str:
        """生成人类可读的映射表（便于人工核对）。"""
        lines = [
            f"信号灯 {self.tls_id!r}：{self.n_phases} 个绿灯相位，"
            f"{self.n_lanes} 条进口车道"
        ]
        for action, lane_indices in enumerate(self.phase_lanes):
            name = (
                self.phase_names[action]
                if action < len(self.phase_names)
                else f"动作{action}"
            )
            served = [self.lanes[i] for i in lane_indices]
            lines.append(f"  [{action}] {name:<10} 放行 {len(served):2d} 条: {', '.join(served)}")
        return "\n".join(lines)


def parse_net_link_lanes(
    net_file: Union[str, Path],
    tls_id: str,
) -> Dict[int, List[str]]:
    """从 ``.net.xml`` 解析 ``linkIndex -> [车道 id, ...]``。

    Args:
        net_file: 路网文件路径。
        tls_id: 信号灯 id。

    Returns:
        形如 ``{0: ["n_in_0"], 1: ["n_in_1"]}`` 的字典；
        文件里没有该信号灯时返回空字典。
    """
    root = ET.parse(str(net_file)).getroot()
    table: Dict[int, List[str]] = {}

    for connection in root.iter("connection"):
        if connection.get("tl") != tls_id:
            continue
        link_index = connection.get("linkIndex")
        from_edge = connection.get("from")
        from_lane = connection.get("fromLane")
        if link_index is None or from_edge is None or from_lane is None:
            continue
        table.setdefault(int(link_index), []).append(f"{from_edge}_{from_lane}")

    return table


def green_link_indices(state: str) -> List[int]:
    """返回状态字符串中"绿灯"的位置（即放行的 linkIndex）。

    >>> green_link_indices("GGrrrrGGrrrr")
    [0, 1, 6, 7]
    """
    return [index for index, char in enumerate(state) if char in GREEN_CHARS]


def _get_traffic_signal(env: Any, tls_id: Optional[str]) -> Any:
    """取出环境里的 TrafficSignal 对象（兼容 sumo-rl 的包装层级）。"""
    inner = getattr(env, "unwrapped", env)
    signals = getattr(inner, "traffic_signals", None)
    if signals is None:  # 有些版本放在 env.env 里
        signals = getattr(getattr(inner, "env", None), "traffic_signals", None)
    if not signals:
        raise RuntimeError(
            "环境里找不到 traffic_signals，无法推导相位→车道映射。"
            "请确认使用的是 SUMO-RL 的单智能体环境。"
        )

    if tls_id is None:
        tls_id = next(iter(signals))
    if tls_id not in signals:
        raise KeyError(f"信号灯 {tls_id!r} 不存在，可选: {', '.join(signals)}")
    return signals[tls_id]


def build_phase_lane_map(
    env: Any,
    tls_id: Optional[str] = None,
    net_file: Union[str, Path, None] = None,
) -> PhaseLaneMap:
    """根据运行中的环境，推导「动作索引 → 车道下标列表」。

    Args:
        env: :func:`src.env.sumo_env.build_env` 返回的环境。
        tls_id: 信号灯 id；``None`` 时取环境里第一个。
        net_file: 路网文件；``None`` 时优先用环境记录的 ``ay10_net_file``，
            否则回退到 :func:`src.env.sumo_env.resolve_net_files`。

    Returns:
        :class:`PhaseLaneMap` 实例。
    """
    traffic_signal = _get_traffic_signal(env, tls_id)
    lanes = list(traffic_signal.lanes)
    lane_index = {lane: position for position, lane in enumerate(lanes)}

    resolved_tls = getattr(traffic_signal, "id", tls_id or "?")
    path = net_file or getattr(env, "ay10_net_file", None)
    if path is None:
        from .sumo_env import resolve_net_files

        path, _ = resolve_net_files()

    link_lanes = parse_net_link_lanes(path, resolved_tls)
    if not link_lanes:
        raise RuntimeError(
            f"路网 {path} 里没有信号灯 {resolved_tls!r} 的连接信息，"
            "无法建立 linkIndex → 车道 的对应关系。"
        )

    phase_lanes: List[List[int]] = []
    for phase in traffic_signal.green_phases:
        served: List[int] = []
        for link_index in green_link_indices(phase.state):
            for lane in link_lanes.get(link_index, []):
                position = lane_index.get(lane)
                if position is not None and position not in served:
                    served.append(position)
        phase_lanes.append(sorted(served))

    return PhaseLaneMap(
        tls_id=str(resolved_tls),
        lanes=lanes,
        phase_lanes=phase_lanes,
    )


def validate_phase_lane_map(mapping: PhaseLaneMap, n_actions: int) -> None:
    """校验映射与动作空间是否一致；不一致时给出可读报错。

    Raises:
        ValueError: 相位数量不匹配，或存在没有任何车道的相位。
    """
    if mapping.n_phases != n_actions:
        raise ValueError(
            f"相位数量不一致：映射得到 {mapping.n_phases} 个，"
            f"动作空间是 {n_actions} 个。请检查路网的绿灯相位定义。"
        )
    empty = [action for action, lanes in enumerate(mapping.phase_lanes) if not lanes]
    if empty:
        raise ValueError(
            f"动作 {empty} 没有对应的进口车道，LQF 无法计算这些相位的排队，"
            "请检查路网连接与信号相位是否匹配。"
        )


__all__ = [
    "GREEN_CHARS",
    "PhaseLaneMap",
    "parse_net_link_lanes",
    "green_link_indices",
    "build_phase_lane_map",
    "validate_phase_lane_map",
]

