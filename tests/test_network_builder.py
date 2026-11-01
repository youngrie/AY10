"""路网生成器单元测试（纯计算部分，不需要 netconvert / SUMO）。

只测"能离线验证"的逻辑：几何推导、连接表、相位字符串、需求文件。
真正调用 netconvert 的部分由 scripts/check_env.py 与集成测试覆盖。
"""

import xml.etree.ElementTree as ET

import pytest

from src.env import network_builder as nb


@pytest.fixture()
def config():
    return nb.load_network_config()


# --------------------------------------------------------------------------- #
# 几何：左转 / 右转 / 直行 的方向推导
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "approach, movement, expected",
    [
        # 从北驶入（向南）：右转去西，直行去南，左转去东
        ("n", "right", "w_out"),
        ("n", "through", "s_out"),
        ("n", "left", "e_out"),
        # 从东驶入（向西）：右转去北，直行去西，左转去南
        ("e", "right", "n_out"),
        ("e", "through", "w_out"),
        ("e", "left", "s_out"),
        # 从南驶入（向北）：右转去东，直行去北，左转去西
        ("s", "right", "e_out"),
        ("s", "through", "n_out"),
        ("s", "left", "w_out"),
        # 从西驶入（向东）：右转去南，直行去东，左转去北
        ("w", "right", "s_out"),
        ("w", "through", "e_out"),
        ("w", "left", "n_out"),
    ],
)
def test_outgoing_edge(approach, movement, expected):
    assert nb.outgoing_edge(approach, movement) == expected


def test_rotate_vector_right_angle():
    assert nb.rotate_vector((0, -1), -90) == (-1, 0)
    assert nb.rotate_vector((0, -1), 90) == (1, 0)
    assert nb.rotate_vector((1, 0), 90) == (0, 1)


def test_node_position_places_boundary_nodes(config):
    arm = float(config["geometry"]["arm_length"])
    assert nb.node_position("n", arm) == (0.0, arm)
    assert nb.node_position("e", arm) == (arm, 0.0)
    assert nb.node_position("s", arm) == (0.0, -arm)
    assert nb.node_position("w", arm) == (-arm, 0.0)


# --------------------------------------------------------------------------- #
# 车道 -> 转向 映射与连接
# --------------------------------------------------------------------------- #
def test_lane_movement_map_shape(config):
    movements = list(config["road"]["lane_movements"])
    table = nb.lane_movement_map(config)
    assert len(table) == 4 * len(movements)

    # SUMO 里 lane 0 是最右侧：配置第一项就是 lane 0
    for lane_index, movement in enumerate(movements):
        assert table[("n_in", lane_index)] == movement
        assert table[("s_in", lane_index)] == movement


def test_connections_cover_all_turn_directions(config):
    movements = list(config["road"]["lane_movements"])
    root = ET.fromstring(nb.build_connections_xml(config))
    connections = root.findall("connection")
    assert len(connections) == 4 * len(movements)

    by_from = {}
    for conn in connections:
        by_from.setdefault(conn.get("from"), []).append(conn)

    # 每个进口的连接数 = 车道数；出口种类数 = 该进口用到的不同转向数
    expected_targets = len({
        nb.outgoing_edge("n", movement) for movement in movements
    })
    for conns in by_from.values():
        assert len(conns) == len(movements)
        assert len({c.get("to") for c in conns}) == expected_targets


def test_edges_xml_uses_configured_lane_count(config):
    root = ET.fromstring(nb.build_edges_xml(config))
    edges = root.findall("edge")
    assert len(edges) == 8  # 4 进 + 4 出
    expected = str(len(config["road"]["lane_movements"]))
    assert all(edge.get("numLanes") == expected for edge in edges)


# --------------------------------------------------------------------------- #
# 相位设计
# --------------------------------------------------------------------------- #
def test_green_sets_has_four_phases(config):
    sets = nb.green_sets(config)
    assert [name for name, _, _ in sets] == [
        "NS_through",
        "NS_left",
        "EW_through",
        "EW_left",
    ]

    ns_through = sets[0][1]
    assert ("n", "through") in ns_through and ("s", "through") in ns_through
    assert ("n", "right") in ns_through       # 右转跟随直行
    assert ("n", "left") not in ns_through    # 左转不在这个相位

    assert sets[1][1] == {("n", "left"), ("s", "left")}

    ew_through = sets[2][1]
    assert ("e", "through") in ew_through and ("w", "through") in ew_through


def test_right_turn_option_adds_green_to_left_phase(config):
    cfg = dict(config)
    cfg["signal"] = dict(config["signal"], right_turns_green_in_both=True)
    sets = nb.green_sets(cfg)
    assert ("n", "right") in sets[1][1]


def _fake_link_map():
    """模拟 netconvert 的编号：每个进口 3 个 link，顺序 right/through/left。"""
    mapping = {}
    index = 0
    for approach in nb.APPROACHES:
        for movement in ("right", "through", "left"):
            mapping[index] = (approach, movement)
            index += 1
    return mapping


def test_phase_sequence_structure(config):
    link_map = _fake_link_map()
    phases = nb.build_phase_sequence(config, len(link_map), link_map)

    # 4 个绿灯 + 4 个黄灯（默认 all_red=0）
    assert len(phases) == 8
    green = [state for _, state, _ in phases if "G" in state]
    yellow = [state for _, state, _ in phases if "y" in state]
    assert len(green) == 4
    assert len(yellow) == 4

    for _, state, _ in phases:
        assert len(state) == len(link_map)
        assert set(state) <= set("Gyr")

    assert all("y" not in state for state in green)
    assert all("G" not in state for state in yellow)


def test_ns_through_phase_greens_only_ns_links(config):
    link_map = _fake_link_map()
    phases = nb.build_phase_sequence(config, len(link_map), link_map)
    state = phases[0][1]

    green_links = {i for i, char in enumerate(state) if char == "G"}
    # n_right, n_through, s_right, s_through
    assert green_links == {0, 1, 6, 7}
    # 东西方向（link 3..5）必须是红灯
    assert state[3:6] == "rrr"


def test_all_red_option_appends_red_phase(config):
    cfg = dict(config)
    cfg["signal"] = dict(config["signal"], all_red=2)
    link_map = _fake_link_map()
    phases = nb.build_phase_sequence(cfg, len(link_map), link_map)
    assert len(phases) == 12
    assert phases[2][1] == "r" * len(link_map)


def test_tll_xml_roundtrip(config):
    link_map = _fake_link_map()
    phases = nb.build_phase_sequence(config, len(link_map), link_map)
    xml = nb.build_tll_xml(phases, "C", "0")

    root = ET.fromstring(xml)
    logic = root.find("tlLogic")
    assert logic is not None
    assert logic.get("id") == "C"
    assert logic.get("type") == "static"
    assert len(logic.findall("phase")) == len(phases)


# --------------------------------------------------------------------------- #
# 需求文件
# --------------------------------------------------------------------------- #
def test_route_file_flow_rate_matches_config(config, tmp_path):
    path = nb.write_route_file(config, "S1", tmp_path / "S1.rou.xml")
    root = ET.parse(path).getroot()
    flows = {flow.get("id"): flow for flow in root.findall("flow")}
    assert len(flows) == 12

    # S1: 600 veh/h，4 方向均分 -> 每方向 150；直行 60% -> 90 veh/h
    # 泊松参数 λ = 90/3600 = 0.025
    assert flows["flow_n_through"].get("period") == "exp(0.025000)"
    # 右转 20% -> 30 veh/h -> λ = 30/3600
    assert flows["flow_n_right"].get("period") == "exp(0.008333)"


def test_route_file_unknown_scenario(config, tmp_path):
    with pytest.raises(KeyError):
        nb.write_route_file(config, "S99", tmp_path / "x.rou.xml")


def test_sumocfg_references_generated_files(config, tmp_path):
    route = nb.write_route_file(config, "S1", tmp_path / "S1.rou.xml")
    path = nb.write_sumocfg(config, route, tmp_path / "test.sumocfg")
    root = ET.parse(path).getroot()
    assert root.find("input/net-file").get("value") == config["output"]["net_file"]
    assert root.find("input/route-files").get("value") == "S1.rou.xml"


# --------------------------------------------------------------------------- #
# 配置校验
# --------------------------------------------------------------------------- #
def test_validate_allows_repeated_lane_movements(config):
    """允许多条车道使用同一转向（如 2 条直行车道），不应报错。"""
    cfg = dict(config)
    cfg["road"] = dict(
        config["road"], lane_movements=["right", "through", "through", "left"]
    )
    nb.validate_config(cfg)  # 不应抛异常


def test_multi_lane_same_movement_generates_distinct_connections(config):
    """两条直行车道应各自连到出口边的不同车道，不能合并成一条。"""
    cfg = dict(config)
    cfg["road"] = dict(
        config["road"], lane_movements=["right", "through", "through", "left"]
    )
    root = ET.fromstring(nb.build_connections_xml(cfg))

    north = [c for c in root.findall("connection") if c.get("from") == "n_in"]
    assert len(north) == 4  # 4 条车道各一条连接

    through = [c for c in north if c.get("to") == "s_out"]
    assert len(through) == 2
    # 两条直行车道分别连到出口的不同车道
    assert {c.get("toLane") for c in through} == {"1", "2"}


def test_validate_rejects_unknown_movement(config):
    cfg = dict(config)
    cfg["road"] = dict(config["road"], lane_movements=["right", "fly", "left"])
    with pytest.raises(ValueError, match="未知转向"):
        nb.validate_config(cfg)


def test_validate_rejects_bad_turn_ratio_sum(config):
    cfg = dict(config)
    cfg["turn_ratio"] = {"left": 0.5, "through": 0.5, "right": 0.5}
    with pytest.raises(ValueError, match="之和"):
        nb.validate_config(cfg)


# --------------------------------------------------------------------------- #
# 命令行入口与工厂保持一致
# --------------------------------------------------------------------------- #
def test_train_cli_accepts_every_factory_controller():
    """train.py 的 --controller 选项必须覆盖 factory 支持的全部控制器。

    这条是为了防止"工厂加了新控制器、但命令行 choices 忘了同步"的问题
    （之前 queue_based 就因此跑不起来）。
    """
    from src.factory import CONTROLLER_NAMES
    from src.train import parse_args

    for name in CONTROLLER_NAMES:
        args = parse_args(["--controller", name])
        assert args.controller == name


def test_evaluate_cli_accepts_queue_based():
    from src.evaluate import parse_args

    args = parse_args(["--controllers", "queue_based", "--scenarios", "S1"])
    assert args.controllers == ["queue_based"]


