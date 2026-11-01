"""指标计算与读取。

数据来源
--------
SUMO-RL 在 ``SumoEnvironment(..., out_csv_name="results/xxx")`` 时会写出
``results/xxx_conn0_ep0.csv``，每行一个决策步。经实测，其列名为::

    step, system_total_stopped, system_total_waiting_time,
    system_mean_waiting_time, system_mean_speed,
    t_stopped, t_accumulated_waiting_time, t_average_speed,
    agents_total_stopped, agents_total_accumulated_waiting_time

指标映射（与 plan.md §6.2 对应）
--------------------------------
* ``avg_wait``  ← ``system_mean_waiting_time`` 的均值（逐步平均等待时间）
* ``avg_queue`` ← ``system_total_stopped`` 的均值（**停车数作为排队长度代理**）
* ``max_queue`` ← ``system_total_stopped`` 的最大值
* ``p95_wait``  ← ``system_mean_waiting_time`` 的 95 分位
* ``total_wait``← ``t_accumulated_waiting_time`` 的最大值（累计等待时间）
* ``mean_speed``← ``t_average_speed`` 的均值
* ``duration``  ← ``step`` 的最大值（仿真时长，秒）
* ``n_samples`` ← 行数

.. note::
   ``system_total_stopped`` 是"速度低于阈值的车辆数"，是**排队长度**的近似；
   若后续需要精确排队数，应改为从 TraCI 直接读取各进口车道的
   ``getLastStepHaltingNumber`` 并在训练循环中记录。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional, Union

import numpy as np
import pandas as pd

#: 汇总结果的标准字段
METRIC_FIELDS = (
    "avg_wait",
    "avg_queue",
    "max_queue",
    "p95_wait",
    "total_wait",
    "mean_speed",
    "duration",
    "n_samples",
)

#: SUMO-RL CSV 中我们用到的列
_CSV_MEAN_WAIT = "system_mean_waiting_time"
_CSV_STOPPED = "system_total_stopped"
_CSV_ACC_WAIT = "t_accumulated_waiting_time"
_CSV_AVG_SPEED = "system_mean_speed"
_CSV_AVG_SPEED_FALLBACK = "t_average_speed"
_CSV_STEP = "step"


# --------------------------------------------------------------------------- #
# 定位与读取
# --------------------------------------------------------------------------- #
def episode_csv_path(out_csv_name: Union[str, Path], episode: int = 0, conn: int = 0) -> Path:
    """按 SUMO-RL 的命名规则构造 CSV 路径。"""
    return Path(f"{out_csv_name}_conn{conn}_ep{episode}.csv")


def find_episode_csv(out_csv_name: Union[str, Path], episode: int = 0) -> Path:
    """在磁盘上查找某个 episode 的 CSV（容忍 conn 编号不同）。

    Raises:
        FileNotFoundError: 未找到匹配文件。
    """
    base = Path(out_csv_name)
    pattern = f"{base.name}_conn*_ep{episode}.csv"
    matches = sorted(base.parent.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"未找到 {base.parent / pattern}；"
            "请确认构建环境时设置了 out_csv_name 并已调用 save_csv()。"
        )
    # 取最新的一个：SUMO-RL 的文件名包含 TraCI 连接标签（conn0/conn1/...），
    # 同一次实验可能产生多个文件，排序第一个不一定是最新那次。
    return max(matches, key=lambda path: path.stat().st_mtime)


def load_episode_csv(path: Union[str, Path]) -> pd.DataFrame:
    """读取一个 episode 的 CSV。"""
    return pd.read_csv(path)


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def _series(df: pd.DataFrame, column: str) -> Optional[pd.Series]:
    if column not in df.columns:
        return None
    return pd.to_numeric(df[column], errors="coerce").dropna()


def summarize_dataframe(df: pd.DataFrame) -> Dict[str, float]:
    """把单个 episode 的逐步 CSV 汇总成指标字典。"""
    waits = _series(df, _CSV_MEAN_WAIT)
    stopped = _series(df, _CSV_STOPPED)
    acc_wait = _series(df, _CSV_ACC_WAIT)
    # system_mean_speed 是整个路网的平均车速，通常都有值；
    # t_average_speed 在没有车辆时可能是 NaN，作为回落。
    speed = _series(df, _CSV_AVG_SPEED)
    if speed is None:
        speed = _series(df, _CSV_AVG_SPEED_FALLBACK)
    step = _series(df, _CSV_STEP)

    def _mean(s: Optional[pd.Series]) -> float:
        return float(s.mean()) if s is not None and len(s) else float("nan")

    return {
        "avg_wait": _mean(waits),
        "avg_queue": _mean(stopped),
        "max_queue": float(stopped.max()) if stopped is not None and len(stopped) else float("nan"),
        "p95_wait": float(np.percentile(waits, 95)) if waits is not None and len(waits) else float("nan"),
        "total_wait": float(acc_wait.max()) if acc_wait is not None and len(acc_wait) else float("nan"),
        "mean_speed": _mean(speed),
        "duration": float(step.max()) if step is not None and len(step) else float("nan"),
        "n_samples": float(len(df)),
    }


def summarize_episode(
    waiting_times: Iterable[float],
    queue_lengths: Iterable[float],
) -> Dict[str, float]:
    """把逐车等待时间与逐步队列长度汇总成指标字典（不经 CSV 时使用）。"""
    waits = np.asarray(list(waiting_times), dtype=float)
    queues = np.asarray(list(queue_lengths), dtype=float)

    return {
        "avg_wait": float(waits.mean()) if waits.size else float("nan"),
        "avg_queue": float(queues.mean()) if queues.size else float("nan"),
        "max_queue": float(queues.max()) if queues.size else float("nan"),
        "p95_wait": float(np.percentile(waits, 95)) if waits.size else float("nan"),
        "total_wait": float(waits.sum()) if waits.size else float("nan"),
        "mean_speed": float("nan"),
        "duration": float("nan"),
        "n_samples": float(waits.size),
    }


def load_and_summarize(path: Union[str, Path]) -> Dict[str, float]:
    """读取 CSV 并直接返回指标字典（最常用的一步到位接口）。"""
    return summarize_dataframe(load_episode_csv(path))


# --------------------------------------------------------------------------- #
# 跨种子汇总
# --------------------------------------------------------------------------- #
def aggregate_seeds(
    runs: Iterable[Dict[str, float]],
    fields: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """跨随机种子汇总：返回每个字段的 ``mean`` / ``std`` / ``n``。"""
    runs = list(runs)
    keys = tuple(fields) if fields is not None else METRIC_FIELDS
    result: Dict[str, Dict[str, float]] = {}

    for key in keys:
        values = np.asarray([r.get(key, np.nan) for r in runs], dtype=float)
        valid = values[~np.isnan(values)]
        if valid.size == 0:
            result[key] = {"mean": float("nan"), "std": float("nan"), "n": 0}
        else:
            result[key] = {
                "mean": float(valid.mean()),
                "std": float(valid.std(ddof=1)) if valid.size > 1 else 0.0,
                "n": int(valid.size),
            }
    return result


__all__ = [
    "METRIC_FIELDS",
    "episode_csv_path",
    "find_episode_csv",
    "load_episode_csv",
    "load_and_summarize",
    "summarize_dataframe",
    "summarize_episode",
    "aggregate_seeds",
]
