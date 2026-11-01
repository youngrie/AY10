"""相位→车道映射的单元测试（不需要 SUMO，用假环境 + 合成 net.xml）。"""

from types import SimpleNamespace

import pytest

from src.env.phase_map import (
    PhaseLaneMap,
    build_phase_lane_map,
    green_link_indices,
    parse_net_link_lanes,
    validate_phase_lane_map,
)

# 4 条进口车道：0=右转 1/2=直行 3=左转；每个进口 4 个 link
SYNTHETIC_NET = """<?xml version="1.0" encoding="UTF-8"?>
<net>
    <connection from="n_in" to="w_out" fromLane="0" toLane="0" tl="C" linkIndex="0"/>
    <connection from="n_in" to="s_out" fromLane="1" toLane="1" tl="C" linkIndex="1"/>
    <connection from="n_in" to="s_out" fromLane="2" toLane="2" tl="C" linkIndex="2"/>
    <connection from="n_in" to="e_out" fromLane="3" toLane="3" tl="C" linkIndex="3"/>
    <connection from="s_in" to="e_out" fromLane="0" toLane="0" tl="C" linkIndex="4"/>
    <connection from="s_in" to="n_out" fromLane="1" toLane="1" tl="C" linkIndex="5"/>
    <connection from="s_in" to="n_out" fromLane="2" toLane="2" tl="C" linkIndex="6"/>
    <connection from="s_in" to="w_out" fromLane="3" toLane="3" tl="C" linkIndex="7"/>
    <connection from="other" to="x" fromLane="0" toLane="0"/>
</net>
"""


@pytest.fixture()
def synthetic_net(tmp_path):
    path = tmp_path / "test.net.xml"
    path.write_text(SYNTHETIC_NET, encoding="utf-8")
    return path


@pytest.fixture()
def fake_env(synthetic_net):
    """模拟 SUMO-RL 环境：只需 traffic_signals / lanes / green_phases。"""
    lanes = [
        "n_in_0", "n_in_1", "n_in_2", "n_in_3",
        "s_in_0", "s_in_1", "s_in_2", "s_in_3",
    ]
    green_phases = [
        SimpleNamespace(state="GGGrrrrr"),   # link0..2 绿（n 的右/直/直）
        SimpleNamespace(state="rrrGrrrr"),   # link3 绿（n 左转）
        SimpleNamespace(state="rrrrGGGr"),   # link4..6 绿（s 的右/直/直）
        SimpleNamespace(state="rrrrrrrG"),   # link7 绿（s 左转）
    ]
    traffic_signal = SimpleNamespace(
        id="C", lanes=lanes, green_phases=green_phases
    )
    return SimpleNamespace(
        traffic_signals={"C": traffic_signal},
        ay10_net_file=str(synthetic_net),
    )


# --------------------------------------------------------------------------- #
# 基础解析
# --------------------------------------------------------------------------- #
def test_parse_net_link_lanes(synthetic_net):
    table = parse_net_link_lanes(synthetic_net, "C")
    assert table[0] == ["n_in_0"]
    assert table[3] == ["n_in_3"]
    assert table[7] == ["s_in_3"]
    # 没有 tl 属性的 connection 不应被收录
    assert len(table) == 8


def test_parse_net_link_lanes_unknown_tls(synthetic_net):
    assert parse_net_link_lanes(synthetic_net, "NOPE") == {}


@pytest.mark.parametrize(
    "state, expected",
    [
        ("GGrrrrGGrrrr", [0, 1, 6, 7]),
        ("rrGrrrrrGrrr", [2, 8]),
        ("rrrrryrrrrry", []),      # 黄灯不算绿灯
        ("ggrr", [0, 1]),          # 小写 g 也算放行
        ("rrrr", []),
    ],
)
def test_green_link_indices(state, expected):
    assert green_link_indices(state) == expected


# --------------------------------------------------------------------------- #
# 映射构建
# --------------------------------------------------------------------------- #
def test_build_phase_lane_map(fake_env):
    mapping = build_phase_lane_map(fake_env)
    assert mapping.tls_id == "C"
    assert mapping.n_lanes == 8
    assert mapping.n_phases == 4

    # 动作 0：n_in_0/1/2 -> 车道下标 0,1,2
    assert mapping.phase_lanes[0] == [0, 1, 2]
    # 动作 1：n_in_3 -> 下标 3
    assert mapping.phase_lanes[1] == [3]
    # 动作 2：s_in_0/1/2 -> 下标 4,5,6
    assert mapping.phase_lanes[2] == [4, 5, 6]
    # 动作 3：s_in_3 -> 下标 7
    assert mapping.phase_lanes[3] == [7]


def test_mapping_covers_every_lane(fake_env):
    mapping = build_phase_lane_map(fake_env)
    covered = sorted({i for lanes in mapping.phase_lanes for i in lanes})
    assert covered == list(range(mapping.n_lanes))


def test_describe_is_readable(fake_env):
    text = build_phase_lane_map(fake_env).describe()
    assert "n_in_0" in text
    assert "4 个绿灯相位" in text


def test_build_raises_when_no_traffic_signals():
    env = SimpleNamespace(traffic_signals={}, ay10_net_file="x.net.xml")
    with pytest.raises(RuntimeError, match="traffic_signals"):
        build_phase_lane_map(env)


def test_build_raises_when_net_has_no_tls(tmp_path):
    net = tmp_path / "empty.net.xml"
    net.write_text("<net></net>", encoding="utf-8")
    ts = SimpleNamespace(
        id="C",
        lanes=["n_in_0"],
        green_phases=[SimpleNamespace(state="G")],
    )
    env = SimpleNamespace(traffic_signals={"C": ts})
    with pytest.raises(RuntimeError, match="连接信息"):
        build_phase_lane_map(env, net_file=net)


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def test_validate_passes_for_consistent_map(fake_env):
    mapping = build_phase_lane_map(fake_env)
    validate_phase_lane_map(mapping, mapping.n_phases)  # 不抛异常


def test_validate_rejects_phase_count_mismatch(fake_env):
    mapping = build_phase_lane_map(fake_env)
    with pytest.raises(ValueError, match="相位数量不一致"):
        validate_phase_lane_map(mapping, mapping.n_phases + 1)


def test_validate_rejects_empty_phase():
    mapping = PhaseLaneMap(tls_id="C", lanes=["a_0"], phase_lanes=[[0], []])
    with pytest.raises(ValueError, match="没有对应的进口车道"):
        validate_phase_lane_map(mapping, 2)
