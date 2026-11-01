"""固定时长控制器（基线一）。

两种可行做法
------------
1. **推荐**：直接使用 SUMO 网络里的 ``static tlLogic``（固定 ``duration`` 的相位序列），
   不需要任何外部控制——用 ``sumo -c xxx.sumocfg`` 直接跑即可。
   此时本文件仅用于在统一实验框架中占位（返回固定的相位轮转）。
2. 本文件实现的**简化版**：每 ``switch_every`` 次决策轮转到下一个绿灯相位，
   用于在同一套 Python 实验循环中与 RL 智能体并列比较。

.. note:.
   简化版按"决策步数"而非"仿真时间"计时，故其周期 = ``switch_every × delta_time`` 秒。
   如需严格的固定配时（如周期 60 s、绿信比 50:50），应改用做法 1。
"""

from __future__ import annotations

from typing import Any, Sequence

from ..agents.base import BaseController


class FixedTimeController(BaseController):
    """按固定步数轮转相位的固定时长控制器。

    Args:
        n_actions: 绿灯相位个数。
        switch_every: 每多少次决策切换一次相位（等长配时；``durations`` 给定时不使用）。
        start_action: 初始相位索引。
        durations: **按相位的绿灯时长（秒）**，长度须等于 ``n_actions``。
            这是"真正的固定配时"：直行相位可以长、左转相位可以短。
            例如 ``[34, 9, 34, 9]`` = 直行 34s、左转 9s 交替。
        delta_time: 一个决策步对应的仿真秒数（默认 5，与 ``env.delta_time`` 一致），
            用于把 ``durations``（秒）换算成"决策步数"。

    Examples:
        >>> c = FixedTimeController(2, durations=[30, 10], delta_time=5)
        >>> [c.select_action(None) for _ in range(9)]
        [0, 0, 0, 0, 0, 0, 1, 1, 0]
    """

    name = "fixed_time"

    def __init__(
        self,
        n_actions: int,
        switch_every: int = 6,
        start_action: int = 0,
        durations: Sequence[float] | None = None,
        delta_time: float = 5.0,
    ) -> None:
        if n_actions <= 0:
            raise ValueError("n_actions 必须为正整数")

        self.n_actions = int(n_actions)
        self.delta_time = float(delta_time) if delta_time > 0 else 5.0

        if durations is not None:
            if len(durations) != self.n_actions:
                raise ValueError(
                    f"durations 长度应为 {self.n_actions}（每个相位一个），"
                    f"实际 {len(durations)}"
                )
            if any(float(d) <= 0 for d in durations):
                raise ValueError("durations 中每项必须为正数（秒）")
            # 秒 -> 决策步数；至少 1 步，避免四舍五入成 0
            self.steps_per_phase = [
                max(1, int(round(float(d) / self.delta_time))) for d in durations
            ]
        else:
            if switch_every <= 0:
                raise ValueError("switch_every 必须为正整数")
            self.steps_per_phase = [int(switch_every)] * self.n_actions

        self.switch_every = int(switch_every)
        self.start_action = int(start_action) % self.n_actions
        self._reset_state()

    # ------------------------------------------------------------------ #
    # 内部状态
    # ------------------------------------------------------------------ #
    def _reset_state(self) -> None:
        self._index = self.start_action
        self._elapsed = 0          # 当前相位已持续的决策步数

    def reset(self) -> None:
        self._reset_state()

    # ------------------------------------------------------------------ #
    # BaseController 接口
    # ------------------------------------------------------------------ #
    def select_action(self, obs: Any) -> int:
        # 当前相位放够了它分配的时长就轮转到下一个相位
        if self._elapsed >= self.steps_per_phase[self._index]:
            self._index = (self._index + 1) % self.n_actions
            self._elapsed = 0
        self._elapsed += 1
        return self._index

    # ------------------------------------------------------------------ #
    # 便于核对配时
    # ------------------------------------------------------------------ #
    @property
    def cycle_steps(self) -> int:
        """一个完整周期包含多少个决策步。"""
        return sum(self.steps_per_phase)

    @property
    def cycle_seconds(self) -> float:
        """一个完整周期的时长（秒，不含黄灯）。"""
        return self.cycle_steps * self.delta_time

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<FixedTimeController n_actions={self.n_actions}, "
            f"durations_s={[round(s * self.delta_time, 1) for s in self.steps_per_phase]}, "
            f"cycle={self.cycle_seconds:.0f}s>"
        )


__all__ = ["FixedTimeController"]
