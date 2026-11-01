"""控制器工厂。

``train.py`` 与 ``evaluate.py`` 都通过本模块构造控制器，
避免两个入口脚本互相 import（原先 evaluate 依赖 train，不利于并行开发）。
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import numpy as np

from .agents.base import BaseController
from .agents.discretizer import Discretizer
from .agents.q_learning import TabularQLearning
from .controllers.fixed_time import FixedTimeController
from .controllers.queue_based import QueueBasedController
from .env.sumo_env import action_count

#: 工厂支持的全部控制器名
CONTROLLER_NAMES = ("random", "fixed_time", "queue_based", "qlearning", "dqn")


class RandomController(BaseController):
    """随机选择相位的控制器（性能下界，也用于快速验证环境）。"""

    name = "random"

    def __init__(self, n_actions: int, seed: int = 0) -> None:
        self.n_actions = int(n_actions)
        self.rng = np.random.default_rng(seed)

    def select_action(self, obs: Any) -> int:
        return int(self.rng.integers(self.n_actions))


def _get(config: Optional[Mapping[str, Any]], section: str, key: str, default: Any) -> Any:
    if not config:
        return default
    return config.get(section, {}).get(key, default)


def _is_normalized_space(space: Any) -> bool:
    """判断观测空间是否已被缩放到 ``[0, 1]``（SUMO-RL 默认如此）。"""
    try:
        high = np.asarray(getattr(space, "high", None), dtype=float)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(high).all() and high.max() <= 1.0 + 1e-6)


def build_controller(
    name: str,
    env: Any,
    config: Optional[Mapping[str, Any]] = None,
    seed: int = 0,
) -> BaseController:
    """按名称构造控制器。

    Args:
        name: ``random`` / ``fixed_time`` / ``qlearning`` / ``dqn``。
        env: 已构建的环境（用于读取动作数与观测维度）。
        config: 由 :func:`src.config.load_config` 得到的配置字典。
        seed: 随机种子。

    Raises:
        ValueError: 未知控制器名。
        ImportError: 选择 ``dqn`` 但未安装 stable-baselines3。
    """
    name = str(name).strip().lower()
    n_actions = action_count(env)

    if name == "random":
        return RandomController(n_actions, seed=seed)

    if name == "fixed_time":
        return FixedTimeController(
            n_actions,
            switch_every=int(_get(config, "fixed_time", "switch_every", 6)),
            durations=_get(config, "fixed_time", "durations", None),
            delta_time=float(_get(config, "env", "delta_time", 5)),
        )

    if name == "queue_based":
        # LQF 需要知道"每个相位放行哪些车道"，这里从路网自动推导，
        # 不需要手工填 phase_lanes。
        from .env.phase_map import build_phase_lane_map, validate_phase_lane_map

        mapping = build_phase_lane_map(env)
        validate_phase_lane_map(mapping, n_actions)
        print(f"[factory] {mapping.describe()}")
        return QueueBasedController(
            n_phases=n_actions,
            n_lanes=mapping.n_lanes,
            phase_lanes=mapping.phase_lanes,
            hold_on_min_green=bool(
                _get(config, "queue_based", "hold_on_min_green", True)
            ),
        )

    if name == "qlearning":
        obs_dim = int(env.observation_space.shape[0])
        normalized = _is_normalized_space(env.observation_space)
        discretizer_cfg = (config or {}).get("discretizer", {})
        queue_edges = discretizer_cfg.get("queue_edges")
        density_edges = discretizer_cfg.get("density_edges")

        # 配置里若给的是"车辆数"阈值（>1）但观测已归一化，
        # 直接使用会让所有状态塌缩到同一档，因此忽略配置、改用归一化阈值。
        if normalized and queue_edges and max(queue_edges) > 1.0:
            print("[factory] 观测已归一化到 [0,1]，忽略配置中的车辆数阈值，"
                  "改用归一化阈值。")
            queue_edges = None
            density_edges = None

        discretizer = Discretizer.from_spaces(
            n_phases=n_actions,
            obs_dim=obs_dim,
            normalized=normalized,
            queue_edges=queue_edges,
            density_edges=density_edges,
        )
        return TabularQLearning(
            n_actions=n_actions,
            discretize=discretizer,
            alpha=float(_get(config, "agent", "alpha", 0.1)),
            gamma=float(_get(config, "agent", "gamma", 0.95)),
            epsilon=float(_get(config, "agent", "epsilon", 1.0)),
            epsilon_min=float(_get(config, "agent", "epsilon_min", 0.05)),
            epsilon_decay=float(_get(config, "agent", "epsilon_decay", 0.995)),
            seed=seed,
        )

    if name == "dqn":
        from .agents.dqn_agent import DQNAgent  # 延迟导入：需要 stable-baselines3

        return DQNAgent(env, seed=seed)

    raise ValueError(f"未知控制器 {name!r}；可选: {', '.join(CONTROLLER_NAMES)}")


__all__ = ["CONTROLLER_NAMES", "RandomController", "build_controller"]
