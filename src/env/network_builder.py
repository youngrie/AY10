"""按配置生成 SUMO 单路口路网（节点 / 边 / 连接 / 信号配时 / 需求）。

为什么写成"生成器"而不是手写 XML
--------------------------------
手写 ``.net.xml`` 几乎不可维护：车道数、路口长度、相位时长任何一项变了，
都要重算坐标和 linkIndex。这里把**所有可变参数**放进 ``network.json``。

生成流程（两遍 netconvert）
---------------------------
1. 先由 ``nod`` + ``edg`` + ``con`` 生成一版路网；
2. 读回这版路网里的 ``<connection ... tl="C" linkIndex="i">``，
   得到"哪个 linkIndex 对应哪个进口的哪种转向"；
3. 用这个映射拼出 4 相位的状态字符串（``G``/``y``/``r``），写出 ``tll.add.xml``；
4. 再把 ``tll.add.xml`` 交给 netconvert，得到**内嵌信号配时**的最终路网。

之所以要先跑一遍，是因为 linkIndex 由 netconvert 按车道顺序自动编号，
不写死才能保证改了车道数/路口形状后信号仍然对得上。

坐标系约定
----------
SUMO 用平面直角坐标：**+x 向东，+y 向北**。四个进口的"驶入方向"向量：

====  ==========  ==================
进口  驶入向量    含义
====  ==========  ==================
n     (0, -1)     从北边界驶向中心（向南）
e     (-1, 0)     从东边界驶向中心（向西）
s     (0, 1)      从南边界驶向中心（向北）
w     (1, 0)      从西边界驶向中心（向东）
====  ==========  ==================

对驶入向量做 ±90° 旋转即得左转 / 右转的出口方向，从而自动推出
"这条车道连到哪条出口边"，无需手工写死。
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH: Path = PROJECT_ROOT / "nets" / "single-intersection" / "network.json"

#: 进口顺序，同时也是需求 ratio 的顺序（与 src/env/scenarios.py 的 DIRECTIONS 一致）
APPROACHES: Tuple[str, ...] = ("n", "e", "s", "w")

#: 每个进口的"驶入方向"单位向量（+x 东，+y 北）
APPROACH_VECTORS: Dict[str, Tuple[int, int]] = {
    "n": (0, -1),
    "e": (-1, 0),
    "s": (0, 1),
    "w": (1, 0),
}

#: 出口方向向量 -> 出口边 id
OUT_EDGE_BY_VECTOR: Dict[Tuple[int, int], str] = {
    (0, 1): "n_out",
    (1, 0): "e_out",
    (0, -1): "s_out",
    (-1, 0): "w_out",
}

#: 转向对应的旋转角度（逆时针为正）
TURN_ANGLE: Dict[str, int] = {"right": -90, "through": 0, "left": 90}

#: 支持的转向名称
MOVEMENTS: Tuple[str, ...] = ("right", "through", "left")


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
def load_network_config(path: str | Path | None = None) -> Dict[str, Any]:
    """读取并校验 ``network.json``。

    Returns:
        配置字典，额外带两个内部键：``_path``（配置文件路径）与
        ``_dir``（输出目录的绝对路径）。
    """
    cfg_path = Path(path).resolve() if path else DEFAULT_CONFIG_PATH
    if not cfg_path.is_file():
        raise FileNotFoundError(f"找不到配置文件: {cfg_path}")

    config: Dict[str, Any] = json.loads(cfg_path.read_text(encoding="utf-8"))
    config["_path"] = str(cfg_path)

    output = config.setdefault("output", {})
    config["_dir"] = (cfg_path.parent / output.get("dir", ".")).resolve()

    validate_config(config)
    return config


def validate_config(config: Mapping[str, Any]) -> None:
    """校验关键字段，提前给出可读报错（而不是让 netconvert 报天书）。"""
    geometry = config.get("geometry", {})
    if float(geometry.get("arm_length", 0)) <= 0:
        raise ValueError("geometry.arm_length 必须为正数")

    road = config.get("road", {})
    movements: Sequence[str] = road.get("lane_movements", [])
    if not movements:
        raise ValueError("road.lane_movements 不能为空（至少 1 条车道）")
    unknown = [m for m in movements if m not in MOVEMENTS]
    if unknown:
        raise ValueError(f"road.lane_movements 出现未知转向 {unknown}，只能是 {MOVEMENTS}")

    # 注意：允许多条车道使用同一转向（例如 2 条直行车道）。
    # 每条车道是独立的一条，会各自连到不同车道的同一出口边，
    # SUMO 能正常处理（实测 4 车道 right/through/through/left 可生成 16 个 link）。
    # 因此这里**不限制重复**，车道组合完全由你决定。

    signal = config.get("signal", {})
    for key in ("green_through", "green_left", "yellow"):
        if float(signal.get(key, 0)) <= 0:
            raise ValueError(f"signal.{key} 必须为正数")
    if float(signal.get("all_red", 0)) < 0:
        raise ValueError("signal.all_red 不能为负数")

    ratios = config.get("turn_ratio", {})
    total = sum(float(ratios.get(m, 0.0)) for m in MOVEMENTS)
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"turn_ratio 三项之和应为 1.0，当前为 {total:.3f}")
    for movement in MOVEMENTS:
        if float(ratios.get(movement, 0.0)) < 0:
            raise ValueError(f"turn_ratio.{movement} 不能为负数")

    demand = config.get("demand", {})
    scenarios = demand.get("scenarios", {})
    if not scenarios:
        raise ValueError("demand.scenarios 不能为空")
    for name, spec in scenarios.items():
        ratio = spec.get("ratio")
        if not ratio or len(ratio) != len(APPROACHES):
            raise ValueError(
                f"demand.scenarios.{name}.ratio 必须是 {len(APPROACHES)} 个数（N,E,S,W）"
            )
        if float(spec.get("total", -1)) < 0:
            raise ValueError(f"demand.scenarios.{name}.total 不能为负数")


# --------------------------------------------------------------------------- #
# 几何推导
# --------------------------------------------------------------------------- #
def rotate_vector(vector: Tuple[int, int], degrees: int) -> Tuple[int, int]:
    """把方向向量旋转指定角度（逆时针为正，取 90 的整数倍）。

    >>> rotate_vector((0, -1), -90)   # 向南行驶，右转 -> 向西
    (-1, 0)
    >>> rotate_vector((0, -1), 90)    # 向南行驶，左转 -> 向东
    (1, 0)
    """
    radians = math.radians(degrees)
    cos_v, sin_v = round(math.cos(radians)), round(math.sin(radians))
    x, y = vector
    return (x * cos_v - y * sin_v, x * sin_v + y * cos_v)


def in_edge(approach: str) -> str:
    """进口边 id（从边界节点驶向路口中心）。"""
    return f"{approach}_in"


def outgoing_edge(approach: str, movement: str) -> str:
    """给定进口与转向，返回该转向驶出的出口边 id。

    >>> outgoing_edge("n", "through")
    's_out'
    >>> outgoing_edge("n", "left")
    'e_out'
    """
    vector = rotate_vector(APPROACH_VECTORS[approach], TURN_ANGLE[movement])
    try:
        return OUT_EDGE_BY_VECTOR[vector]
    except KeyError as exc:  # pragma: no cover - 由常量保证不会发生
        raise ValueError(f"无法为进口 {approach} 的 {movement} 找到出口边") from exc


def node_position(approach: str, arm_length: float) -> Tuple[float, float]:
    """边界节点坐标（路口中心固定在 (0,0)）。"""
    vector = APPROACH_VECTORS[approach]
    return (-vector[0] * arm_length, -vector[1] * arm_length)


# --------------------------------------------------------------------------- #
# XML 片段生成
# --------------------------------------------------------------------------- #
def build_nodes_xml(config: Mapping[str, Any]) -> str:
    """生成 ``.nod.xml``：1 个信号灯路口中心 + 4 个边界节点。"""
    arm = float(config["geometry"]["arm_length"])
    tls_id = str(config["signal"].get("tls_id", "C"))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<nodes>"]
    lines.append(
        f'    <node id="{tls_id}" x="0.00" y="0.00" type="traffic_light" tl="{tls_id}"/>'
    )
    for approach in APPROACHES:
        x, y = node_position(approach, arm)
        lines.append(
            f'    <node id="{approach.upper()}" x="{x:.2f}" y="{y:.2f}" type="priority"/>'
        )
    lines.append("</nodes>")
    return "\n".join(lines) + "\n"


def build_edges_xml(config: Mapping[str, Any]) -> str:
    """生成 ``.edg.xml``：每个方向一进一出，车道数取自 ``road.lane_movements``。"""
    road = config["road"]
    num_lanes = len(road["lane_movements"])
    speed = float(road["speed_limit"])
    tls_id = str(config["signal"].get("tls_id", "C"))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<edges>"]
    for approach in APPROACHES:
        # 进口边：边界节点 -> 路口中心
        lines.append(
            f'    <edge id="{in_edge(approach)}" from="{approach.upper()}" to="{tls_id}" '
            f'numLanes="{num_lanes}" speed="{speed}" priority="1"/>'
        )
        # 出口边：路口中心 -> 边界节点
        lines.append(
            f'    <edge id="{approach}_out" from="{tls_id}" to="{approach.upper()}" '
            f'numLanes="{num_lanes}" speed="{speed}" priority="1"/>'
        )
    lines.append("</edges>")
    return "\n".join(lines) + "\n"


def lane_movement_map(config: Mapping[str, Any]) -> Dict[Tuple[str, int], str]:
    """把配置里的车道转向展开成 ``{(进口边, 车道号): 转向}``。

    SUMO 中 lane 0 是**最右侧**车道，所以配置里的列表顺序就是"从右往左"。
    """
    movements = list(config["road"]["lane_movements"])
    table: Dict[Tuple[str, int], str] = {}
    for approach in APPROACHES:
        for lane_index, movement in enumerate(movements):
            table[(in_edge(approach), lane_index)] = movement
    return table


def build_connections_xml(config: Mapping[str, Any]) -> str:
    """生成 ``.con.xml``：每条进口车道连到对应转向的出口车道。

    要点：
    * ``toLane`` 取与 ``fromLane`` 相同的序号 —— 因为进出口边的车道排列规则一致，
      这样左转车道对左转车道、直行对直行，几何最自然；
    * ``dir`` 显式写出转向（l/s/r），便于 netconvert 与后续调试。
    """
    direction_tag = {"left": "l", "through": "s", "right": "r"}
    num_lanes = len(config["road"]["lane_movements"])

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<connections>"]
    for (edge, lane_index), movement in sorted(lane_movement_map(config).items()):
        approach = edge.split("_")[0]
        target = outgoing_edge(approach, movement)
        to_lane = min(lane_index, num_lanes - 1)
        lines.append(
            f'    <connection from="{edge}" to="{target}" '
            f'fromLane="{lane_index}" toLane="{to_lane}" dir="{direction_tag[movement]}"/>'
        )
    lines.append("</connections>")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# 外部程序
# --------------------------------------------------------------------------- #
def find_binary(name: str) -> str | None:
    """在 PATH 或 ``SUMO_HOME/bin`` 中查找 SUMO 工具（netconvert 等）。"""
    found = shutil.which(name)
    if found:
        return found
    home = os.environ.get("SUMO_HOME")
    if home:
        suffix = ".exe" if os.name == "nt" else ""
        candidate = Path(home) / "bin" / f"{name}{suffix}"
        if candidate.is_file():
            return str(candidate)
    return None


def run_netconvert(arguments: Sequence[str], cwd: Path) -> str:
    """调用 netconvert；失败时抛出带完整输出的异常，便于定位问题。"""
    binary = find_binary("netconvert")
    if binary is None:
        raise RuntimeError(
            "未找到 netconvert。请确认已安装 SUMO，并把 SUMO_HOME/bin 加入 PATH。"
        )
    proc = subprocess.run(
        [binary, *arguments], cwd=str(cwd), capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "netconvert 执行失败（exit=%d）\n命令: %s\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (proc.returncode, " ".join([binary, *arguments]), proc.stdout, proc.stderr)
        )
    return proc.stdout


# --------------------------------------------------------------------------- #
# 从生成的路网里反查 linkIndex
# --------------------------------------------------------------------------- #
def parse_link_indices(
    net_file: str | Path,
    movement_of: Mapping[Tuple[str, int], str],
) -> Tuple[Dict[Tuple[str, str], List[int]], Dict[int, Tuple[str, str]]]:
    """解析 ``.net.xml`` 的 ``<connection>``，建立 linkIndex 与"进口+转向"的双向映射。

    SUMO 的信号状态字符串按 linkIndex 顺序排列，而 linkIndex 由 netconvert
    依据车道顺序自动编号，因此必须在生成后读回来，不能写死。

    Returns:
        ``(by_key, by_index)``：
        ``by_key[(approach, movement)] = [linkIndex, ...]``，
        ``by_index[linkIndex] = (approach, movement)``。
    """
    root = ET.parse(str(net_file)).getroot()
    by_key: Dict[Tuple[str, str], List[int]] = {}
    by_index: Dict[int, Tuple[str, str]] = {}

    for connection in root.iter("connection"):
        if "tl" not in connection.attrib:
            continue
        edge = connection.get("from")
        lane = connection.get("fromLane")
        link_index = connection.get("linkIndex")
        if edge is None or lane is None or link_index is None:
            continue
        movement = movement_of.get((edge, int(lane)))
        if movement is None:
            continue
        approach = edge.split("_")[0]
        by_key.setdefault((approach, movement), []).append(int(link_index))
        by_index[int(link_index)] = (approach, movement)

    return by_key, by_index


# --------------------------------------------------------------------------- #
# 相位设计（4 个绿灯 + 黄灯 + 可选全红）
# --------------------------------------------------------------------------- #
def green_sets(config: Mapping[str, Any]) -> List[Tuple[str, set, float]]:
    """设计 4 个绿灯相位（顺序即 SUMO 程序里的相位顺序）。

    ==========  ==============================  ==================
    相位        绿灯的 (进口, 转向)               时长
    ==========  ==============================  ==================
    NS_through  n/s 的 through（以及 right）      green_through
    NS_left     n/s 的 left                      green_left
    EW_through  e/w 的 through（以及 right）      green_through
    EW_left     e/w 的 left                      green_left
    ==========  ==============================  ==================

    右转默认跟随同方向直行放行；把 ``signal.right_turns_green_in_both`` 设为 true，
    右转就会在直行与左转两个相位都放行。

    .. note::
       若某个进口没有 right 车道，把 ("n", "right") 放进绿灯集合也不会出错——
       因为路网里本来就没有对应的 link。
    """
    signal = config["signal"]
    both = bool(signal.get("right_turns_green_in_both", False))
    green_through = float(signal["green_through"])
    green_left = float(signal["green_left"])

    def build(approaches: Sequence[str], kind: str) -> set:
        result = set()
        for approach in approaches:
            result.add((approach, kind))
            if kind == "through" or both:
                result.add((approach, "right"))
        return result

    return [
        ("NS_through", build(("n", "s"), "through"), green_through),
        ("NS_left", build(("n", "s"), "left"), green_left),
        ("EW_through", build(("e", "w"), "through"), green_through),
        ("EW_left", build(("e", "w"), "left"), green_left),
    ]


def build_phase_sequence(
    config: Mapping[str, Any],
    n_links: int,
    link_movement: Mapping[int, Tuple[str, str]],
) -> List[Tuple[str, str, float]]:
    """生成完整相位序列：绿灯 → 黄灯 →（可选）全红，4 个绿灯各来一遍。

    Returns:
        ``[(相位名, 状态字符串, 时长), ...]``，状态字符串长度等于 ``n_links``。
    """
    signal = config["signal"]
    yellow = float(signal["yellow"])
    all_red = float(signal.get("all_red", 0))
    red_state = "r" * n_links

    sequence: List[Tuple[str, str, float]] = []
    for name, greens, duration in green_sets(config):
        green_state = "".join(
            "G" if link_movement.get(i) in greens else "r" for i in range(n_links)
        )
        yellow_state = "".join(
            "y" if link_movement.get(i) in greens else "r" for i in range(n_links)
        )
        sequence.append((name, green_state, duration))
        sequence.append((name + "_yellow", yellow_state, yellow))
        if all_red > 0:
            sequence.append((name + "_allred", red_state, all_red))
    return sequence


def build_tll_xml(
    phases: Sequence[Tuple[str, str, float]],
    tls_id: str,
    program_id: str,
) -> str:
    """生成信号配时文件（``additional`` 格式），交给 ``netconvert -t`` 内嵌进路网。

    把配时写进 ``.net.xml`` 而不是运行时 ``-a`` 附加，好处是
    SUMO-RL 打开路网时就能直接读到 4 个绿灯相位（动作空间 = 4）。
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<additional>"]
    lines.append(
        f'    <tlLogic id="{tls_id}" type="static" programID="{program_id}" offset="0">'
    )
    for name, state, duration in phases:
        lines.append(f'        <!-- {name} -->')
        lines.append(f'        <phase duration="{duration:g}" state="{state}"/>')
    lines.append("    </tlLogic>")
    lines.append("</additional>")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# 构建路网（两遍 netconvert）
# --------------------------------------------------------------------------- #
def build_network(
    config: Mapping[str, Any],
    keep_intermediate: bool | None = None,
) -> Dict[str, Any]:
    """生成最终 ``.net.xml``（内嵌 4 相位信号配时）。

    Args:
        config: :func:`load_network_config` 的返回值。
        keep_intermediate: 是否保留 ``.nod/.edg/.con/.tll`` 中间文件；
            ``None`` 时取配置里的 ``output.keep_intermediate``。

    Returns:
        摘要字典：``net_file`` / ``n_links`` / ``n_phases`` /
        ``n_green_phases`` / ``cycle_seconds`` 等。
    """
    out_dir: Path = config["_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    output = config["output"]
    keep = (
        bool(output.get("keep_intermediate", True))
        if keep_intermediate is None
        else keep_intermediate
    )

    net_name = str(output.get("net_file", "single-intersection.net.xml"))
    # 注意：Path("x.net.xml").stem 得到的是 "x.net"，这里要显式去掉 ".net.xml"
    stem = net_name[: -len(".net.xml")] if net_name.endswith(".net.xml") else Path(net_name).stem
    nodes_path = out_dir / f"{stem}.nod.xml"
    edges_path = out_dir / f"{stem}.edg.xml"
    conns_path = out_dir / f"{stem}.con.xml"
    tll_path = out_dir / f"{stem}.tll.xml"
    net_path = out_dir / net_name
    tmp_net = out_dir / f"_{stem}.pass1.net.xml"

    # --- 第 1 步：写节点 / 边 / 连接 ---
    nodes_path.write_text(build_nodes_xml(config), encoding="utf-8")
    edges_path.write_text(build_edges_xml(config), encoding="utf-8")
    conns_path.write_text(build_connections_xml(config), encoding="utf-8")

    common = [
        "--node-files", nodes_path.name,
        "--edge-files", edges_path.name,
        "--connection-files", conns_path.name,
        # 不加 --no-turnarounds 时 netconvert 会自动补掉头连接，
        # 车道数与 linkIndex 都会变，信号相位就对不上了
        "--no-turnarounds", "true",
        "--tls.default-type", "static",
        "--no-warnings", "true",
    ]

    # --- 第 2 步：先出一版路网，读回 linkIndex ---
    run_netconvert([*common, "--output-file", tmp_net.name], cwd=out_dir)
    movement_of = lane_movement_map(config)
    _, link_movement = parse_link_indices(tmp_net, movement_of)
    if not link_movement:
        raise RuntimeError(
            "路网里没有任何受信号灯控制的 link，请检查节点类型是否为 traffic_light。"
        )

    # --- 第 3 步：按真实 linkIndex 生成相位，写出配时文件 ---
    phases = build_phase_sequence(config, len(link_movement), link_movement)
    tls_id = str(config["signal"].get("tls_id", "C"))
    program_id = str(config["signal"].get("program_id", "0"))
    tll_path.write_text(build_tll_xml(phases, tls_id, program_id), encoding="utf-8")

    # --- 第 4 步：带着配时再生成一次，得到最终路网 ---
    run_netconvert(
        [*common, "--tllogic-files", tll_path.name, "--output-file", net_path.name],
        cwd=out_dir,
    )

    if not keep:
        for path in (nodes_path, edges_path, conns_path, tll_path):
            path.unlink(missing_ok=True)
    tmp_net.unlink(missing_ok=True)

    green_phases = [name for name, state, _ in phases if "G" in state]
    return {
        "net_file": net_path,
        "tll_file": tll_path if keep else None,
        "n_links": len(link_movement),
        "n_phases": len(phases),
        "n_green_phases": len(green_phases),
        "green_phase_names": green_phases,
        "cycle_seconds": sum(duration for _, _, duration in phases),
    }


# --------------------------------------------------------------------------- #
# 需求文件
# --------------------------------------------------------------------------- #
def write_route_file(
    config: Mapping[str, Any],
    scenario: str,
    out_path: str | Path | None = None,
) -> Path:
    """按场景生成 ``.rou.xml``：每个 (进口, 转向) 一条 ``<flow>``。

    流量拆分::

        某进口总流量 = total × 该方向权重 / 权重之和
        某转向流量   = 该进口总流量 × turn_ratio[转向]

    ``arrival = poisson`` 时用 ``period="exp(平均车头时距)"``（指数分布 ≈ 泊松到达）；
    否则用 ``vehsPerHour``（均匀到达）。
    """
    demand = config["demand"]
    scenarios = demand["scenarios"]
    key = str(scenario).upper()
    if key not in scenarios:
        raise KeyError(f"未知场景 {scenario!r}，可选: {', '.join(scenarios)}")

    spec = scenarios[key]
    total = float(spec["total"])
    ratio = [float(value) for value in spec["ratio"]]
    ratio_sum = sum(ratio) or 1.0
    turn_ratio = config["turn_ratio"]
    vtype = demand.get("vtype", {})
    end = int(demand.get("simulation_seconds", 3600))
    poisson = str(demand.get("arrival", "poisson")).lower() == "poisson"

    if out_path is None:
        pattern = config["output"].get("scenario_route_pattern", "{scenario}.rou.xml")
        out_path = config["_dir"] / pattern.format(scenario=key)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<routes>"]
    lines.append(
        '    <vType id="%s" length="%s" minGap="%s" maxSpeed="%s"'
        ' accel="%s" decel="%s" sigma="%s"/>'
        % (
            vtype.get("id", "car"),
            vtype.get("length", 5.0),
            vtype.get("minGap", 2.5),
            vtype.get("maxSpeed", config["road"]["speed_limit"]),
            vtype.get("accel", 2.6),
            vtype.get("decel", 4.5),
            vtype.get("sigma", 0.5),
        )
    )

    # 先声明所有可能用到的路线（进口边 -> 出口边）
    for approach in APPROACHES:
        for movement in MOVEMENTS:
            if float(turn_ratio.get(movement, 0)) <= 0:
                continue
            lines.append(
                f'    <route id="{approach}_{movement}" '
                f'edges="{in_edge(approach)} {outgoing_edge(approach, movement)}"/>'
            )

    # 再按流量生成 flow
    for approach, share in zip(APPROACHES, ratio):
        approach_rate = total * share / ratio_sum
        for movement in MOVEMENTS:
            rate = approach_rate * float(turn_ratio.get(movement, 0))
            if rate <= 0:
                continue
            if poisson:
                # 注意 SUMO 的坑：period="exp(x)" 里的 x 是**速率 λ**（辆/秒），
                # 不是平均车头时距。平均时距 H 秒 ⇒ λ = 1/H = rate/3600。
                # 写成 exp(3600/rate) 会让 x 变成 120 这种大数，被当成 λ=120，
                # 结果所有进口都挤到饱和（实测 600 秒插入 117 辆而非 5 辆）。
                timing = f'period="exp({rate / 3600.0:.6f})"'
            else:
                timing = f'vehsPerHour="{rate:.2f}"'
            lines.append(
                f'    <flow id="flow_{approach}_{movement}" route="{approach}_{movement}" '
                f'begin="0" end="{end}" {timing} departLane="best" departSpeed="max"/>'
            )

    lines.append("</routes>")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def write_sumocfg(
    config: Mapping[str, Any],
    route_file: str | Path,
    out_path: str | Path | None = None,
) -> Path:
    """生成 ``.sumocfg``，便于直接 ``sumo-gui -c xxx.sumocfg`` 查看。"""
    output = config["output"]
    target = Path(out_path) if out_path else config["_dir"] / output.get(
        "sumocfg", "single-intersection.sumocfg"
    )
    net_name = output.get("net_file", "single-intersection.net.xml")
    end = int(config["demand"].get("simulation_seconds", 3600))

    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<configuration>\n"
        "    <input>\n"
        f'        <net-file value="{net_name}"/>\n'
        f'        <route-files value="{Path(route_file).name}"/>\n'
        "    </input>\n"
        "    <time>\n"
        '        <begin value="0"/>\n'
        f'        <end value="{end}"/>\n'
        "    </time>\n"
        "</configuration>\n"
    )
    target.write_text(content, encoding="utf-8")
    return target


def build_all(config: Mapping[str, Any]) -> Dict[str, Any]:
    """一键构建：路网 + 全部场景需求 + 默认需求副本 + sumocfg。"""
    network = build_network(config)
    output = config["output"]

    route_files: Dict[str, Path] = {}
    for name in config["demand"]["scenarios"]:
        route_files[name] = write_route_file(config, name)

    default_scenario = str(config["demand"].get("default_scenario", "S2")).upper()
    if default_scenario not in route_files:
        raise KeyError(f"demand.default_scenario={default_scenario} 不在 scenarios 中")

    default_route = config["_dir"] / output.get(
        "default_route_file", "single-intersection.rou.xml"
    )
    shutil.copyfile(route_files[default_scenario], default_route)
    sumocfg = write_sumocfg(config, default_route)

    return {
        **network,
        "route_files": route_files,
        "default_route": default_route,
        "default_scenario": default_scenario,
        "sumocfg": sumocfg,
    }


__all__ = [
    "APPROACHES",
    "MOVEMENTS",
    "DEFAULT_CONFIG_PATH",
    "load_network_config",
    "validate_config",
    "rotate_vector",
    "in_edge",
    "outgoing_edge",
    "lane_movement_map",
    "build_nodes_xml",
    "build_edges_xml",
    "build_connections_xml",
    "parse_link_indices",
    "green_sets",
    "build_phase_sequence",
    "build_tll_xml",
    "build_network",
    "write_route_file",
    "write_sumocfg",
    "build_all",
    "find_binary",
]





