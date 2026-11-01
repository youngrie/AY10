"""`evaluate.merge_rows` 的单元测试（不依赖 SUMO）。

背景：`eval_<场景>.csv` 曾经是整文件覆盖，单跑一个控制器会把其它控制器的
历史结果冲掉。现在改为"按 key 合并"：同 (场景, 控制器, 种子, 回合) 覆盖，
其余保留。
"""

import csv

from src.evaluate import merge_rows

KEYS = ("scenario", "controller", "seed", "episode")


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_merge_creates_file_when_missing(tmp_path):
    path = tmp_path / "eval_S1.csv"
    rows = [{"scenario": "S1", "controller": "random", "seed": 0, "episode": 1, "avg_wait": 7.0}]
    merged = merge_rows(path, rows)
    assert len(merged) == 1
    assert merged[0]["avg_wait"] == "7.0"


def test_merge_keeps_other_controllers(tmp_path):
    path = tmp_path / "eval_S1.csv"
    _write(path, [
        {"scenario": "S1", "controller": "random", "seed": 0, "episode": 1, "avg_wait": "7.0"},
        {"scenario": "S1", "controller": "fixed_time", "seed": 0, "episode": 1, "avg_wait": "1.8"},
    ])

    # 只新增 queue_based，另外两个控制器必须保留
    merged = merge_rows(path, [
        {"scenario": "S1", "controller": "queue_based", "seed": 0, "episode": 1, "avg_wait": "0.7"},
    ])
    controllers = [row["controller"] for row in merged]
    assert sorted(controllers) == ["fixed_time", "queue_based", "random"]


def test_merge_replaces_same_key(tmp_path):
    path = tmp_path / "eval_S1.csv"
    _write(path, [
        {"scenario": "S1", "controller": "random", "seed": 0, "episode": 1, "avg_wait": "99.0"},
    ])
    merged = merge_rows(path, [
        {"scenario": "S1", "controller": "random", "seed": 0, "episode": 1, "avg_wait": "7.5"},
    ])
    assert len(merged) == 1
    assert merged[0]["avg_wait"] == "7.5"


def test_merge_sorts_by_key(tmp_path):
    path = tmp_path / "eval_S1.csv"
    merged = merge_rows(path, [
        {"scenario": "S1", "controller": "random", "seed": 2, "episode": 1, "avg_wait": "1"},
        {"scenario": "S1", "controller": "fixed_time", "seed": 0, "episode": 1, "avg_wait": "2"},
        {"scenario": "S1", "controller": "random", "seed": 0, "episode": 1, "avg_wait": "3"},
    ])
    assert [(r["controller"], r["seed"]) for r in merged] == [
        ("fixed_time", "0"),
        ("random", "0"),
        ("random", "2"),
    ]
