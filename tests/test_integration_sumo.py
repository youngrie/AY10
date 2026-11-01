"""集成测试：需要本机安装 SUMO（未设置 SUMO_HOME 时自动跳过）。

运行方式::

    pytest -m integration        # 只跑集成测试
    pytest -m "not integration"  # 只跑单元测试（CI 默认）
"""

import os

import pytest

pytestmark = pytest.mark.integration

SUMOHOME_AVAILABLE = bool(os.environ.get("SUMO_HOME"))
requires_sumo = pytest.mark.skipif(not SUMOHOME_AVAILABLE, reason="需要 SUMO（SUMO_HOME 未设置）")


@requires_sumo
def test_resolve_net_files_falls_back_to_bundled(tmp_path):
    """本地 nets/ 为空时应回退到 sumo-rl 内置路网。"""
    from src.env.sumo_env import resolve_net_files

    net_file, route_file = resolve_net_files(tmp_path)
    assert net_file.is_file()
    assert route_file.is_file()


@requires_sumo
def test_environment_can_step():
    """真正启动一次短仿真，确认环境可用且动作空间有效。"""
    from src.env.sumo_env import action_count, build_env, reset_env, step_env

    env = build_env(num_seconds=30, use_gui=False, out_csv_name=None)
    try:
        obs, _ = reset_env(env)
        assert len(obs) > 0

        n_actions = action_count(env)
        assert n_actions >= 1

        for _ in range(2):
            obs, reward, terminated, truncated, _ = step_env(env, int(env.action_space.sample()))
            if terminated or truncated:
                break
    finally:
        env.close()


@requires_sumo
def test_phase_lane_map_matches_action_space():
    """相位→车道映射应与动作空间一致，且覆盖所有进口车道。"""
    from src.env.phase_map import build_phase_lane_map, validate_phase_lane_map
    from src.env.sumo_env import action_count, build_env

    env = build_env(num_seconds=30, use_gui=False, out_csv_name=None)
    try:
        n_actions = action_count(env)
        mapping = build_phase_lane_map(env)

        assert mapping.n_phases == n_actions
        assert mapping.n_lanes > 0
        validate_phase_lane_map(mapping, n_actions)

        covered = sorted({i for lanes in mapping.phase_lanes for i in lanes})
        assert covered == list(range(mapping.n_lanes))
    finally:
        env.close()


@requires_sumo
def test_scenario_selects_different_route_file():
    """指定不同场景时，环境应加载不同的 .rou.xml。"""
    from src.env.sumo_env import build_env, available_scenarios

    names = available_scenarios()
    if len(names) < 2:
        pytest.skip(f"可用场景不足两个: {names}")

    first, second = names[0], names[1]
    env_a = build_env(scenario=first, num_seconds=30, use_gui=False, out_csv_name=None)
    try:
        route_a = env_a.ay10_route_file
        assert env_a.ay10_scenario == first
    finally:
        env_a.close()

    env_b = build_env(scenario=second, num_seconds=30, use_gui=False, out_csv_name=None)
    try:
        route_b = env_b.ay10_route_file
    finally:
        env_b.close()

    assert route_a != route_b
    assert route_a.endswith(f"{first}.rou.xml")
    assert route_b.endswith(f"{second}.rou.xml")


