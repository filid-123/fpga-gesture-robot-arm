# PL 层级重构与硬件图对应

新增 12 个真实结构 wrapper，移动 34 个原有实例。wrapper 不新增寄存器、时钟域、状态、运算或流水级；
原模型、叶模块和时序行为通过身份端口/参数绑定保留。纯重构检查点与 B 新功能分开。

| 父模块 | 新 wrapper | 内容 |
|---|---|---|
| gesture_autonomous_top_black | vision_acquisition_pipeline | 相机配置 FSM、SCCB、DVP/CDC 前端 |
| 同上 | vision_locator_compute | 模型 ROM、8 路 CNN、Top-1 归约 |
| 同上 | vision_roi_memory_pipeline | 帧 BRAM、同帧 ROI、分类输入 BRAM |
| 同上 | vision_classifier_compute | 描述符 ROM、权重 ROM、CNN 计算核 |
| 同上 | vision_schedule_qualifier | BBox、调度 FSM、稳定确认 |
| phase3_s4_task_top | motion_axil_ownership_fabric | AXI 窗口、所有权/写锁、超时 |
| 同上 | motion_hand_target_pipeline | 区域 LUT、目标确认 FSM |
| 同上 | motion_task_control | 表 RAM/寄存器、任务 FSM、原生操作链接 |
| phase3_s2_motion_top | motion_actuator_pipeline | 弹性采样 MUX、机械臂后端 |
| mode_a_hdmi_output | display_scan_pipeline | 扫描时序、坐标 ROM |
| 同上 | display_telemetry_bridge | 单位转换、保持数据 CDC |
| 同上 | hdmi_phy_pipeline | TMDS 编码器、串行器 |

图中区分 BRAM/ROM、运算数据通路、FSM、CDC、协议/PHY；名称必须取自实际实例，不能用图上的抽象功能名替代 RTL 模块。
`u_step_map` 仍直接位于 S4 父模块；HDMI 的 `frame`、`renderer` 仍是其父模块的直接子实例。
新 B 的 `b_route_player`、六个 `b_route_ram` 是明确新增的功能硬件，不计入“纯 wrapper 等价”声明。

`board_evidence/pl_wrappers_v1/before` 与 `pure_after` 保存纯重构前后源码。
`verify_pl_wrappers.py` 检查全部叶实例 AST、端口/参数身份绑定，并展开比较所有原声明、assign、always 和 generate。
端口位选信号已显式转接，聚合实例位于对应声明之后。当前最终 RTL 还包含 B 新功能，不能用纯重构证明代替新功能测试。

本地提供 5 页 `.drawio`、SVG、PNG、矢量 PDF、端口/实例映射，可供论文重新排版。图纸与绘图脚本按仓库约定仅本地交付；
真实 wrapper、映射说明和精简证明提交个人分支。原 BIT 保留；新 B 功能使用新 BIT，后续布局和综合命名可能变化。

纯结构证明的复现使用独立工具环境 `pyslang==12.1.0`，在源码工作树执行 `python scripts/verify_pl_wrappers.py`。
该工具依赖不加入联测运行环境；封包内的已绑定证据供查看，不在封包原地重写。

`hierarchy.csv` 是纯 wrapper 阶段的叶实例转接表。最终版本新增的 B 接口以 `rtl_hierarchy_live.csv/json` 为准，
其中保存当前 .v 的实际端口连接、条件生成范围、活动参数和源码 SHA256；两种映射不混作同一阶段证明。
