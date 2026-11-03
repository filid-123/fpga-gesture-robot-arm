# 原创与第三方材料许可核对

核对日期：2026-11-01。范围：用户指定 p4.1 ZIP 的4,521项文件、文件头、模型元数据和包内来源说明。用户确认目前只有赛事使用授权，第三方再分发许可待确认；整体开源许可证尚未选择。本报告是材料来源/缺口清单，不是原创证明或完整法律意见。

## 已识别材料

| 材料 | 包内依据 | 已核对声明 / 当前处理 |
|---|---|---|
| 团队 RTL、PC/PS 软件、规划及本轮工具 | 原包来源哈希、Giao固定提交、原开发分支、本轮新增文件 | 作为团队项目源码收录；并未逐行证明原创或取得所有成员的权属签字。整体许可待团队决定，不自动附 MIT/Apache |
| B YOLOv8s 检测权重 | `project/model_package/mode_b/detector_background_v2/model.json` 明示 Ultralytics8.4.89，预训练/训练 SHA | 标注 AGPL-3.0 / Enterprise。用户未提供 Enterprise 授权；权重不随 Git 收录，保持外部资产。不能改写为团队独占或 MIT |
| MobileNetV3 编码器与分割权重 | surface 模型声明、`project/pc/multiobject/surface.py`、原公开来源说明 | torchvision 软件仓库是 BSD-3-Clause；预训练参数、训练数据和派生模型的来源要分别确认，不能仅凭库许可证认定权重全部可分发。checkpoint暂不收录 |
| PL 训练 checkpoint、图像、黄金数据 | `project/model_package/candidates/` 的导出与训练记录 | 硬件所需整数 ROM/MEM 和数值黄金数据按团队项目收录；训练 checkpoint/原始栅格图像暂不收录。训练图像完整权属链仍待成员确认 |
| Office-Home 训练来源 | `project/docs/phase3c/mode_b_six_objects_20261026/public_sources.md` | 原记录称非商业研究/教学用途。官方项目页当前可访问，但未取得能覆盖本次再分发的条款/授权证明，不能将研究训练用途等同原图再分发。原图库不收录 |
| LVIS / COCO 来源 | `source_attribution.json` 中原图URL、COCO license_id；原public_sources说明 | LVIS标注和COCO原图的条款不同，原图需逐项核对；不把标注许可套在全部图片上。图像不收录 |
| RoARM CAD/STL | `project/sim/models/mode_b_roarm_nominal/` | 源包未含足够的CAD再分发许可；网格暂不收录。需确认原厂/团队生成来源与许可 |
| Xilinx PS7 初始化文件 | `project/hardware/ps7_init.c/.h`、`ps7_init_gpl.c/.h` 文件头 | 前者标识MIT，后者明确GPL-2.0-or-later；原文件头保留，附相应许可文本，不将第三方声明替换为整体许可证 |
| Vivado生成 BIT/HWH/XSA 和报告 | `project/hardware/`、`project/evidence/implementation/` | 原始构建和IP来源保留；完整工具/IP使用与分发权以团队实际 AMD 授权为准，不能以赛事授权替代。重复产物/历史整包不收录 |
| Python/推理依赖 | `project/requirements_mode_ab_lock.txt` | 仅声明/安装，不把虚拟环境和wheel并入Git；不同包各自许可仍适用，未做完整依赖SBOM认证 |
| 赛事/其他 PDF | 源包中的PDF | 无需随源码发布且未确认再分发，暂列外部资产 |

源码包没有 LICENSE/NOTICE 文件，并不意味着其中每个文件都是团队原创。没有发现已识别的密钥/令牌模式，但这次静态扫描也不等于隐私或知识产权的全面认证。

## 官方核对来源

- [Ultralytics 官方 LICENSE](https://github.com/ultralytics/ultralytics/blob/main/LICENSE)：AGPLv3。这里只确认上游声明，未替团队选择许可路线。
- [torchvision 官方 LICENSE](https://github.com/pytorch/vision/blob/main/LICENSE)：BSD3软件许可。模型训练数据不因此获得统一许可。
- [Office-Home 作者项目页](https://www.hemanthdv.org/officeHomeDataset.html)，配合包内历史来源记录；许可覆盖范围仍待确认。
- [LVIS 官方项目](https://www.lvisdataset.org/) 与 [COCO 官方条款](https://cocodataset.org/#termsofuse)：应核对具体原图、标注与使用方式。
- PS7 MIT/GPL文字来自包内文件头。配套文本 [MIT](third_party/mit.txt)、[GPL-2.0-or-later](third_party/gpl-2.0-or-later.txt) 从 [SPDX license-list-data](https://github.com/spdx/license-list-data/tree/main/text) 获取；MIT文本采用PS7原文件的Xilinx版权声明；这不为团队其他文件选择MIT许可证。

以上网页核对不证明封存特定版本与所有上游材料都已完成追溯。特别是原数据记录提到的使用限制，需要保存原许可文本或单独授权后再关闭。

## 对外发布决策

本轮先发布源码组织、元数据、必要硬件导出和独立工具；模型权重、栅格图片、CAD、PDF、历史整包和可再生会话文件通过明确清单排除。每项保留原路径、字节数和SHA256，见 `report/provenance/excluded_assets.json`。本地恢复不更改这些文件的许可。

下一步需要团队确认：成员原创贡献及授权范围；YOLO采用AGPL路线还是能证明的Enterprise授权；训练/验证图像逐项许可及模型再分发覆盖；CAD来源；最终整体/分目录开源许可。确认后再提供合法模型获取方式、附实际适用许可并更新审查结果。本轮不生成整体 LICENSE，不把“许可待确认”写成已完成开源。
