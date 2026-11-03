# 赛题 3.2.5.1 工程包索引

交付基线为 p4.1，TASK ABI 0x340E，B 路径 RAM ABI 0xB001。当前发布版是 publication.9。

| 赛题条目 | 材料与核对依据 |
|---|---|
| 系统架构、数据流、分工 | [总图与 FPGA 分图](../docs/architecture.md)。A 由 PL 处理手势、选槽、轨迹执行与反馈，B 由 AI PC 完成物体感知与规划、PL 播放并执行。PC 通过 JTAG 批量交付路径和配置，PL 保持周期性执行。 |
| 接口与时序 | [接口入口](../docs/interface.md)、[报文和寄存器](../project/docs/mode_ab/interface.md)、[B 原生路径合同](../project/docs/mode_ab/native_routes_p4.md)。覆盖 XSDB/JTAG、AXI MMIO、TTL、六轴 Q16 和回读提交。 |
| FPGA 源码与构建 | [RTL、约束和脚本](../project/native_motion/)、[Vivado Tcl](../project/native_motion/scripts/build_roarm_closed_loop.tcl)、[重建流程](../docs/reproduction.md)、[BIT/HWH/XSA](../project/hardware/)。 |
| 综合、实现、时钟和时序 | [a14 综合资源报告](validation/a14_utilization_synth.rpt)、[构建日志](../project/evidence/implementation/implement.log)、[实现资源报告](../project/evidence/implementation/implemented_reports/utilization_implemented.rpt)、[时序报告](../project/evidence/implementation/implemented_reports/timing_implemented.rpt)、[实现产物绑定](../project/evidence/implementation/implementation_summary.json)。封存主时钟 100 MHz，WNS +0.013 ns、WHS +0.011 ns，布线后 LUT/FF/BRAM Tile/DSP 为 30,657/25,196/117.5/56。综合报告仅脱敏主机字段，原构建日志记录了报告生成命令。 |
| FPGA 与实物验证 | [现场验收](../docs/field_acceptance.md)、[六次会话与操作者复核](acceptance/board_test_20261101.json)。已记录 A/B 任务和双向 HOME 切换，17 次执行中 16 次成功。 |
| AI PC 模型、后端与应用 | [模型声明](../docs/model.md)、[AI PC 源码](../project/pc/)、[依赖锁](../project/requirements_mode_ab_lock.txt)、[部署与启动](../docs/reproduction.md)、[九项固定资产渠道](../docs/runtime_assets.md)。公开版已通过下载、SHA256 和启动前输入检查。新机器完整 AMD/HIP 安装与实物复跑未执行。 |
| 硬件、外设与供电 | [实物图、BOM、接线和供电](../docs/hardware_setup.md)。已列 JA/JB 的 OV5640 针脚、TTL、JTAG、HDMI 和独立电源。 |

本次整理沿用封存构建和现场验收，没有重新综合、布线或运行机械臂。
