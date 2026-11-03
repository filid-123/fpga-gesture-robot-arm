# 第三方来源与许可证

核对日期：2026-11-03。团队原创部分采用 [AGPL-3.0-only](LICENSE)，第三方材料依其原条款。版权声明和具体限制优先保留；本文不为训练图片或派生权重新增授权。

| 组成/来源 | 实际使用与依据 | 条款及当前处理 |
| --- | --- | --- |
| Ultralytics YOLOv8s，8.4.89 | B模式检测；官方COCO起点→三色模型→公开数据及现场适配→`detector_background_v2` | [固定版本AGPL全文](https://github.com/ultralytics/ultralytics/blob/v8.4.89/LICENSE)、[官方许可说明](https://www.ultralytics.com/license)。选择AGPL路线；公开对应源码、修改及构建/运行所需来源，不把ONNX导出、CPU/HIP执行当作解除条款的理由。未购买/声称Enterprise许可。 |
| TorchVision / MobileNetV3-Small | `IMAGENET1K_V1`预训练编码器；项目自建顶面解码器并微调 | [软件BSD-3-Clause全文](docs/open_source_audit_20261103/upstream/vision-license.txt)。[官方README](https://github.com/pytorch/vision#pre-trained-model-license)明确预训练模型可能受训练数据条款约束；不能仅凭软件BSD断定所有权重可自由再分发。本模型不是SWAG，不将SWAG条款误套。ImageNet起点权重授权范围仍待核实。 |
| Office-Home，Venkateswara等，CVPR 2017 | 当前检测及顶面训练链包含32张原图（18训练、14验证）；另有训练派生图。原图和直接派生合计60条记录 | [作者Fair Use Notice](https://www.hemanthdv.org/officeHomeDataset.html)声明非商业研究/教学用途，并提及未经原版权人特别授权的材料；这是用途说明，不是标准的可任意再分发开源许可。镜像下载或Hugging Face元数据不能扩大作者授权。原图/派生栅格不纳入本次提交；派生权重的公开再分发覆盖仍需确认。 |
| LVIS v1，Gupta / Dollár / Girshick，CVPR 2019 | 74张原图的目标标注来源（52训练、22验证）；使用scissors/canister，部分可见顶面由项目另行标注 | [LVIS官网](https://www.lvisdataset.org/dataset)：标注及网站CC-BY-4.0；[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)。官网前端原文与SHA记录在本次审计来源清单。说明项目筛选、类别映射与新增顶面标注；不把整物体实例掩膜当顶面真值。**API代码的BSD与标注CC-BY不同**。 |
| COCO / Flickr原图 | LVIS图像来自COCO，各图片有独立license id / Flickr来源 | [COCO条款入口](https://cocodataset.org/#termsofuse)。逐图记录出处、作者/归属、许可ID和URL；未补齐的原图不随源码打包。COCO API的[BSD文本](docs/open_source_audit_20261103/upstream/coco-license-data.txt)是代码许可，不能充当全体照片许可。 |
| 项目自采图及AI辅助标注 | 三色木块、橡皮、药瓶、剪刀；保留文件SHA及采集会话 | 使用团队有权提供的原图；保留拍摄主体、标签来源及训练/核对划分。近似AI标注不写成经人工精密标注的独立真值。 |
| RoARM CAD/URDF/STL，Waveshare | 机械臂离线几何模型 | [上游package.xml](https://github.com/waveshareteam/roarm_ws/blob/ros2-humble/src/roarm_main/roarm_description/package.xml)声明MIT；已取得该声明，但未取得与本地网格逐项匹配的上游提交及完整版权/授权文本。不能把一行MIT声明当成所有CAD权属核验完成。保留外部资产排除。 |
| Xilinx PS7支持文件 | 封存PS初始化代码 | `ps7_init.c/.h`的MIT、`ps7_init_gpl.c/.h`的GPL-2.0-or-later按原头保留；[MIT](docs/third_party/mit.txt)、[GPL文本](docs/third_party/gpl-2.0-or-later.txt)。不覆盖成团队版权。 |
| AMD/Vivado/IP/SDK、Python依赖 | 实现与运行环境；不随Git复制安装器/虚拟环境 | AMD工具/IP授权及各运行库许可分别适用。BIT/HWH/XSA不因仓库有AGPL就获得对第三方IP的额外授权；依赖清单不等于完整SBOM认证。 |

当前模型绑定：

- 检测ONNX：`5999c0e1e2d2631cf68b086b1b667ec87eabbb5268b1d6550421371520308cce`。
- 顶面checkpoint：`9143a31f4ced63410d1bb3b3367139eb48dda68551e0aedce12eceda9b5f8f93`。
- 原冻结清单：`cf2c959aa9aae7660015a3769ff1edcd6ed4ca8e32dee0f8e3a4fbbb9cbc5778`。

AI PC端逐图许可和训练链补充见[专门核对报告](docs/aipc_license_20261103/README_CN.md)：74张LVIS/COCO原图中58张标NC、18张标ND（含验证、计数重合）；这些图片条件不在本报告中自动套用为权重许可。Office-Home和ImageNet初始化覆盖仍待确认，未发送对外授权请求。

审计结论、来源与公开范围见 [docs/license_audit.md](docs/license_audit.md)。AGPL对应源码、网络交互源码提供义务和第三方材料权利是不同事项；不能用新增LICENSE宣称二者都已完成。
