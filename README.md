# FPGA_手势交互机械臂系统

以 Windows 原生 AMD Ryzen AI PC、PYNQ-Z2 / XC7Z020 和 RoARM-M3-S 实现手势交互、视觉定位与机械臂递送。模式 A 使用固定槽位和 PL 视觉/任务链；模式 B 使用 AI PC 普通 RGB 感知和规划，PL 完成实时轨迹、交互与执行。

本分支整理基线是 `gesture_mode_ab_v0_1_0_20261030_p4_1.zip`，发布整理版本为 `0.1.0-publication.9`。运行合同仍为 p4.1：`native_giao_full_workspace_p4`、`startup_route_map_p4_1`、TASK ABI `0x340E`、B 路径 RAM ABI `0xB001`。本轮没有更改生产 RTL、模型数值、路径或动作参数。

**当前 p4.1 已实测通过，登记为 `USABLE_USER_ACCEPTED`（用户验收通过的可用版本），可作为后续开发和回退基线。** 2026-11-01 用户现场确认“实测任务完成，可以作为可用的版本”；六次既有会话的日志摘要支持 A/B 任务完成及双向固定 HOME 过渡。详见 [当前实测验收](docs/field_acceptance.md)。经用户复核，既有17次任务执行中16次物理成功，成功率94.12%；通信、INT8开发集质量及FPGA周期时延已从原记录复算，见[指标复算](docs/metrics_recovery_20261101.md)。闭环延迟采用板端遥测中的视觉确认至TTL反馈观测时长。团队原创部分采用 AGPL-3.0-only。第三方资产按各自条款管理。

## 从这里开始

只核验源码，Python 3.12 标准库即可；不会打开相机、JTAG 或机械臂：

```powershell
py -3.12 tools/check_repository.py
py -3.12 -m unittest discover -s tests -v
```

缺失外部资产时，检查会明确显示 `full_runtime_ready: false`；源码子集通过不表示完整运行环境已就绪。先读 [复现步骤](docs/reproduction.md) 和 [许可核对](docs/license_audit.md)。已经合法持有指定 ZIP 的操作者可以在本地恢复资产，再执行原完整包门禁：

```powershell
py -3.12 tools/restore_assets.py --archive C:/path/to/gesture_mode_ab_v0_1_0_20261030_p4_1.zip
py -3.12 tools/check_repository.py --complete
```

恢复工具验证整包 SHA256、CRC 和逐文件哈希，拒绝覆盖不同内容。恢复的外部资产受 Git 忽略规则保护，不获得新的再分发许可。原 ZIP 不随 Git 提交，详见 [源包清单](report/provenance/source_archive_inventory.json)。

## 目录与赛题对照

按赛题 3.2.5.5 对照如下。FPGA 和上位机共享同一套 p4.1 工程，相对路径用于定位 RTL、模型、配置和封存证据，因此统一保留在 `project/` 下。文档、指标、Skill 和报告可直接从提交包根目录查阅。

| 赛题推荐路径 | 提交包中的对应位置 |
|---|---|
| `README.md` | 本页及 [从零复现步骤](docs/reproduction.md) |
| `docs/` | [系统架构与数据流](docs/architecture.md)、[接口定义](docs/interface.md)、[硬件与接线](docs/hardware_setup.md) |
| `fpga/src/` | [RTL](project/native_motion/rtl/)、[约束](project/native_motion/constraints/)、[BD 与构建 Tcl](project/native_motion/scripts/) |
| `fpga/build/` | [构建入口](tools/build_fpga.py)、[BIT、XSA、HWH 与 PS 初始化](project/hardware/) |
| `fpga/report/` | [a14 综合资源报告](report/validation/a14_utilization_synth.rpt)、[实现资源和时序报告](project/evidence/implementation/implemented_reports/) |
| `host/model/` | [模型说明](docs/model.md)、[模型目录](project/model_package/)、[外部资产安装器](tools/install_runtime_assets.py)及[固定版本渠道](docs/runtime_assets.md) |
| `host/app/` | [上位机与通信源码](project/pc/)、[WebUI](project/web/)、[桥接和运行脚本](project/scripts/) |
| `host/deploy/` | [环境安装](project/setup_mode_ab.ps1)、[启动入口](project/start_mode_ab.ps1)、[依赖锁](project/requirements_mode_ab_lock.txt) |
| `metrics/metrics.csv` | [指标汇总](metrics/metrics.csv) |
| `metrics/logs/` | [保存帧日志](metrics/logs/)、[封存板级记录](project/board_evidence/) |
| `metrics/scripts/` | [指标复算脚本](metrics/scripts/)、[视觉评测工具](tools/vision_metrics/) |
| `metrics/evidence/` | [指标证据](metrics/evidence/)、[封存工程证据](project/evidence/)、[实物验收](report/acceptance/) |
| `skill/` | [三项可复用 Skill 与工作流](skill/README.md) |
| `report/` | [技术报告 PDF](report/technical_report.pdf)、[工程设计说明](report/design_report.md)、[工程包索引](report/engineering_package.md)、[验收与交付状态](report/submission_status.md) |

提交 ZIP 省略仓库根目录的内部协作说明和开发助手配置。开发与版本记录见 [开发日志](docs/development_history.md) 和 [版本记录](docs/version_history.md)。

## 已有证据与限制

- 封存实现：30,657 LUT、25,196 FF、117.5 BRAM tile、56 DSP；WNS/WHS `+0.013/+0.011 ns`，TNS/THS 0，115 个 CDC 端点均 safe。来自 p4/a14 同次实现，本轮只重新核对绑定；未重新综合实现。
- 原包记录 78 项 PC 测试、10 项 UI 检查、3 项启动映射检查以及 RTL/模型验证。哪些在本次整理中实际重跑，以 `report/validation/` 为准。
- 原包 GPU 记录是 9 张保存帧，不能代替现场闭环成功率或传感到物理响应延迟。
- 当前 p4.1 已完成用户现场任务验收；六次会话共 24,446 条遥测，fault、反馈错误/超时及原生路径错误均为 0。用户补充复核得到A交付5/5、A补回3/3、B交付5/6、B补回3/3，总计16/17成功；分母为这组既有执行。
- 已记录 A 红/蓝交付与蓝块补回、B 红块/圆罐交付与圆罐补回，以及 A↔B HOME 过渡；所核对会话未记录橡皮完成交付，不扩大为全物品逐项或连续全工作域验收。
- 已复算：52,884次RPC、2次异常（0.003781862%）；550张INT8 DEV Accuracy 91.45%、Macro-F1 92.30%；FPGA Locator/Classifier服务时间16.4764/4.68486ms。详见[指标表](metrics/metrics.csv)和[口径报告](docs/metrics_recovery_20261101.md)。视觉确认至TTL反馈分位数见指标表；DEV不替代独立TEST。JTAG `Invalid context` / 恢复未确认、历史 UART 间歇问题继续 `OPEN`。封存 `project/` 中的实物 `NOT_RUN` 保留为历史记录。

团队开发历史由原私有仓库保管。此交付从当前发布提交导出。

## 许可状态

团队尚未选定仓库整体的开源许可证；本仓库不声明 MIT、Apache-2.0 或 AGPL 为整体许可证。已有第三方文件保留各自声明，见 [许可核对及来源](docs/license_audit.md)。涉及 Ultralytics、Office-Home、COCO/LVIS 和 CAD 的材料继续逐项确认；不能将本目录当作已经完成授权审查的自由再分发整包。

## 正式测试结果与公开审查

本交付采用既有 p4.1 实物测试作为正式参赛结果。闭环任务16/17成功。正式报告的闭环延迟采用既有板端遥测复算。合格手势观测至运动发送后新鲜 TTL 反馈观测，A 模式14条的 P50/P95/P99/max 为493/542.95/551.79/554 ms，B 模式18条为14985/22125.55/23007.51/23228 ms。该指标的端点是轮询观测到的电气反馈，物理位移起始仍缺同步事件记录。

B 模式开发评测已收录。模型和资产的合规获取方式、完整环境复现资料由团队补充。当前INT8成绩按DEV集原口径列示。

本工程包从发布提交导出。源提交与逐文件变更见 `report/provenance/public_review.json`。原始封存包用于完整原包复核，交付副本使用自己的发布校验清单。

开发过程与历史版本见 [开发日志](docs/development_history.md) 和 [版本记录](docs/version_history.md)。

Giao 的冻结 B 模式模型评测已收录。38 张开发验证图的 mAP@0.5:0.95 为 65.52%，GT 框内顶面二分类 mIoU 为 82.81%。历史单布局 20 帧分别为 83.28% 和 95.45%。两组均使用 CPU 离线评测和 AI 近似标注。原始图像由团队保管。两份冻结 B 模式权重由 Giao 的上游仓库提供。

## 赛题工程包

按 [3.2.5.1 工程包索引](report/engineering_package.md) 查阅四类提交材料。[技术报告 PDF](report/technical_report.pdf) 对应赛题 3.2.5.4，测试证据范围见 [提交核对](report/final_submission_review.md)。

## 公开 A/B 运行资产

见 [运行资产获取说明](docs/runtime_assets.md) 和 [固定版本渠道清单](docs/runtime_asset_channels.csv)。
