"""实验配置的集中管理。

配置以 **JSON** 文件给出（见 ``experiments/configs/sample.json``），
本模块负责"默认值 + 文件覆盖"的深度合并，避免参数散落在各脚本里。

命令行参数优先级：**CLI 显式指定 > 配置文件 > DEFAULT_CONFIG**。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

CONFIG_DIR = Path(__file__).resolve().parents[1] / "experiments" / "configs"

#: 默认配置（与 README / plan.md 中的取值一致）
DEFAULT_CONFIG: Dict[str, Any] = {
    "scenario": "S1",
    "controller": "qlearning",
    "episodes": 100,
    "seed": 0,
    "reward_fn": "diff-waiting-time",
    "env": {
        "num_seconds": 3600,
        "delta_time": 5,
        "yellow_time": 3,
        "min_green": 5,
        "max_green": 50,
        "use_gui": False,
        "single_agent": True,
    },
    "agent": {
        "alpha": 0.1,
        "gamma": 0.95,
        "epsilon": 1.0,
        "epsilon_min": 0.05,
        "epsilon_decay": 0.995,
    },
    "discretizer": {
        "queue_edges": [0.1, 0.3, 0.6, 0.9],
        "density_edges": [0.1, 0.3, 0.6, 0.9],
    },
    "fixed_time": {
        # 等长配时用（每多少次决策轮转一次）；给了 durations 时忽略
        "switch_every": 6,
        # 按相位的绿灯时长（秒）。null = 用 switch_every 等长配时。
        # 4 相位顺序：NS直行 / NS左转 / EW直行 / EW左转
        #
        # 下面的取值是**校准结果**（scripts/calibrate_baselines.py 扫描得出）：
        #   [15, 5, 15, 5] -> 周期 40 秒，直行 15s、左转 5s
        # 在 S1–S4 上的平均等待 1.82~1.92s；原来的 30/30/30/30（周期 120s）约 11.9s。
        # 注意左转不宜再短（试过 10/5 组合，重载场景下排队会爆炸到 800s+）。
        "durations": [15, 5, 15, 5],
    },
    "queue_based": {
        # 最小绿灯未满足时是否强制保持当前相位（True = 更接近真实信号机）
        "hold_on_min_green": True,
    },
}


def deep_update(base: Dict[str, Any], extra: Mapping[str, Any]) -> Dict[str, Any]:
    """递归合并 ``extra`` 到 ``base``（就地修改并返回 base）。"""
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def load_config(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """读取配置；``path`` 为 ``None`` 时只返回默认值的深拷贝。

    Raises:
        FileNotFoundError: 配置文件不存在。
        json.JSONDecodeError: 文件不是合法 JSON。
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path is None:
        return config

    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {file_path}")

    with file_path.open(encoding="utf-8") as handle:
        override = json.load(handle)
    if not isinstance(override, dict):
        raise ValueError(f"配置文件顶层必须是 JSON 对象: {file_path}")
    return deep_update(config, override)


def resolve_config_path(name: Union[str, Path]) -> Path:
    """把配置名解析成路径：既接受完整路径，也接受 ``configs/`` 下的文件名。"""
    candidate = Path(name)
    if candidate.is_file():
        return candidate

    from_dir = CONFIG_DIR / candidate.name
    if from_dir.is_file():
        return from_dir
    raise FileNotFoundError(f"找不到配置文件 {name!r}（已尝试 {candidate} 与 {from_dir}）")


def env_kwargs(config: Mapping[str, Any], **overrides: Any) -> Dict[str, Any]:
    """从配置中取出可直接传给 :func:`src.env.sumo_env.build_env` 的参数。

    注意 ``scenario`` 取自配置**顶层**（`"scenario": "S3"`），
    它决定用哪份 ``<SCENARIO>.rou.xml``。
    """
    kwargs: Dict[str, Any] = dict(config.get("env", {}))
    kwargs["reward_fn"] = config.get("reward_fn", "diff-waiting-time")
    kwargs["scenario"] = config.get("scenario")
    kwargs.update(overrides)
    return {k: v for k, v in kwargs.items() if v is not None}


__all__ = [
    "CONFIG_DIR",
    "DEFAULT_CONFIG",
    "deep_update",
    "load_config",
    "resolve_config_path",
    "env_kwargs",
]
