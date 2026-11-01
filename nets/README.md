# `nets/` —— SUMO 路网

| 子目录 | 内容 |
| --- | --- |
| `single-intersection/` | 单路口路网、需求、信号配时（**由脚本生成，勿手改**） |

详细说明见 [`single-intersection/README.md`](single-intersection/README.md)。

## 核心约定

1. 路网**不是手写的**：由 `single-intersection/build_network.py` 读取
   `single-intersection/network.json` 自动生成。
2. 想改路口大小、车道数、转向比例、相位时长、各场景流量 →
   **只改 `network.json`**，然后重新运行生成脚本：

   ```bash
   python nets/single-intersection/build_network.py
   python nets/single-intersection/build_network.py --check   # 只校验配置
   ```

3. `single-intersection/` 下除 `network.json`、`build_network.py`、`README.md`
   之外都是**生成产物**，重跑脚本会被覆盖。

## 运行时如何被找到

`src/env/sumo_env.py` 按以下优先级查找
`single-intersection.net.xml` + `single-intersection.rou.xml`：

```
build_env(net_dir=...)            # 1. 显式参数
环境变量 AY10_NET_DIR              # 2. 环境变量
nets/single-intersection/         # 3. 本目录（默认命中）
sumo_rl 包内置路网                 # 4. 兜底
```

因此只要本目录下有这两个文件，实验用的就是**我们自己的路网**
（4 进口 × 4 车道、4 个绿灯相位）。

## 注意

- 改了车道数后 `observation_space` 维度会变，**旧实验结果不可直接对比**，基线需重跑；
- 改完建议跑 `python scripts/inspect_phase_map.py` 确认"相位→车道"映射仍覆盖全部车道。
