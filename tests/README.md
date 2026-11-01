# `tests/` —— 单元测试与集成测试

```bash
python -m pytest                     # 全部（119 个用例，约 5 秒，不需要 SUMO）
python -m pytest -m "not integration" # 只跑单元测试（CI 用这条）
python -m pytest -m integration       # 只跑需要 SUMO 的用例
python -m pytest tests/test_metrics.py -v
```

## 文件分工

| 文件 | 覆盖内容 | 需要 SUMO？ |
| --- | --- | --- |
| `conftest.py` | 把项目根目录加入 `sys.path`（**删掉它所有测试都会 `ModuleNotFoundError`**） | 否 |
| `test_discretizer.py` | 观测离散化、归一化阈值、维度推导 | 否 |
| `test_q_learning.py` | Q 更新公式、ε 衰减、保存/加载 | 否 |
| `test_controllers.py` | 固定时长轮转、LQF 决策规则与参数校验 | 否 |
| `test_metrics.py` | CSV 汇总、跨种子统计、文件定位 | 否 |
| `test_scenarios_config.py` | 场景定义、配置深合并、需求文件生成 | 否 |
| `test_env_compat.py` | `reset_env`/`step_env` 新旧签名兼容、参数过滤 | 否 |
| `test_network_builder.py` | 转向推导、连接表、相位字符串、需求流量、CLI 与工厂一致性 | 否 |
| `test_phase_map.py` | 相位→车道映射（假环境 + 合成 net.xml） | 否 |
| `test_integration_sumo.py` | 真实建环境、步进、映射校验 | **是**（`SUMO_HOME` 未设置时自动 skip） |

## 约定

- **优先写不依赖 SUMO 的用例**：快、CI 能跑。用假对象（`types.SimpleNamespace`）
  和合成 XML 就能覆盖大部分逻辑，`test_phase_map.py` 是最好的例子。
- 依赖真实仿真的用例放进 `test_integration_sumo.py`，并加
  `@requires_sumo`（`pytest.ini` 里注册了 `integration` 标记）。
- **新增公共函数/控制器时同步加用例**；改动接口后先跑一遍全量测试再提交。

## 两个"回归测试"值得保留

| 用例 | 防的是什么 |
| --- | --- |
| `test_normalized_values_are_separated_into_distinct_bins` | 曾用"车辆数"阈值给归一化观测分箱，导致状态塌缩 |
| `test_train_cli_accepts_every_factory_controller` | 曾出现"工厂加了 `queue_based`、但 `train.py` 的 choices 没同步"，命令行报 invalid choice |
