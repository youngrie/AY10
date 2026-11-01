"""场景选择的单元测试（只验证文件解析逻辑，不需要 SUMO）。"""

import pytest

from src.config import env_kwargs, load_config
from src.env.sumo_env import (
    available_scenarios,
    resolve_net_files,
    scenario_route_name,
)


@pytest.fixture()
def net_dir(tmp_path):
    """构造一个假的"路网目录"：网络 + 默认需求 + 两个场景需求。"""
    (tmp_path / "single-intersection.net.xml").write_text("<net/>", encoding="utf-8")
    (tmp_path / "single-intersection.rou.xml").write_text("<routes/>", encoding="utf-8")
    (tmp_path / "S1.rou.xml").write_text("<routes/>", encoding="utf-8")
    (tmp_path / "S3.rou.xml").write_text("<routes/>", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("不是需求文件", encoding="utf-8")
    return tmp_path


def test_scenario_route_name_normalises_case():
    assert scenario_route_name("s1") == "S1.rou.xml"
    assert scenario_route_name(" S3 ") == "S3.rou.xml"


def test_available_scenarios_only_lists_scenario_files(net_dir):
    assert available_scenarios(net_dir) == ["S1", "S3"]


def test_available_scenarios_missing_dir(tmp_path):
    assert available_scenarios(tmp_path / "nope") == []


def test_resolve_uses_scenario_file(net_dir):
    net, route = resolve_net_files(net_dir, scenario="S3")
    assert net.name == "single-intersection.net.xml"
    assert route.name == "S3.rou.xml"


def test_resolve_scenario_is_case_insensitive(net_dir):
    _, route = resolve_net_files(net_dir, scenario="s1")
    assert route.name == "S1.rou.xml"


def test_resolve_falls_back_to_default_without_scenario(net_dir):
    _, route = resolve_net_files(net_dir)
    assert route.name == "single-intersection.rou.xml"


def test_resolve_unknown_scenario_reports_available(net_dir):
    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_net_files(net_dir, scenario="S9")
    message = str(excinfo.value)
    assert "S9" in message
    assert "S1" in message and "S3" in message   # 报错里列出可用场景


def test_env_kwargs_carries_scenario():
    config = load_config()
    config["scenario"] = "S4"
    kwargs = env_kwargs(config)
    assert kwargs["scenario"] == "S4"


def test_env_kwargs_allows_scenario_override():
    config = load_config()
    config["scenario"] = "S4"
    kwargs = env_kwargs(config, scenario="S1")
    assert kwargs["scenario"] == "S1"
