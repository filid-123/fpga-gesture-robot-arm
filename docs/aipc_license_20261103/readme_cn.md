# AI PC端：模型参数与训练数据许可核对

日期2026-11-03；范围按用户明确要求，仅包含AI PC检测、顶面分割及相应数据/软件来源，不要求用户补齐FPGA端或队友资料。状态为**来源核对已完成本轮可执行部分，当前权重公开分发的授权覆盖尚未闭合**。不能把“审计脚本通过”写成“所有权重已获自由再分发授权”。

## 当前结论

| 材料 | 已确认 | 仍缺什么 |
|---|---|---|
| 团队原创AI PC代码 | 用户已选AGPL-3.0-only，根LICENSE/NOTICE已提供 | 维持对应源码、改动和运行说明；既有第三方声明不覆盖 |
| YOLOv8s实现及官方参数路线 | 上游Ultralytics AGPL-3.0/Enterprise，使用8.4.89；本项目选AGPL | AGPL路线已选定；本项目派生参数所用数据的权利问题仍单独核实，不声称购买Enterprise |
| 当前六类检测参数 | ONNX SHA及训练checkpoint、6阶段warm start记录可追踪 | Office-Home与逐图COCO来源的具体用途/公开分发覆盖，不能凭选AGPL一并关闭 |
| 当前顶面分割参数 | MobileNetV3-Small编码器+项目解码器；8阶段warm start记录；实际代码选择IMAGENET1K_V1 | TorchVision的BSD软件许可不能代替预训练参数条款；ImageNet网页本轮未成功取得，未核实精确初始化二进制SHA及可覆盖本用途的完整权重条款 |
| Office-Home来源 | 官方非商业研究/教学fair-use说明已保存，非标准开源数据许可 | 若超出说明范围，官方要求直接向原版权人取得许可；不能假定数据集作者拥有全部原图授权或能替所有权利人同意 |
| LVIS标注/COCO照片 | 标注CC-BY-4.0；74张实际照片的历史许可ID已匹配官方LVIS元数据 | 个别照片作者归属不完整，Flickr读取尝试超时；实际图片许可与训练/派生权重分发关系仍需按具体使用核实 |
| CPU审计环境依赖 | 保存已安装包的实际License/License-Expression及许可文件SHA | 不是AMD生产ROCm环境的完整SBOM，不替代AMD驱动/SDK各自条款；没有将整个Torch二进制简单称为单一BSD许可 |

当前检测ONNX SHA256：`5999c0e1e2d2631cf68b086b1b667ec87eabbb5268b1d6550421371520308cce`。当前顶面checkpoint SHA256：`9143a31f4ced63410d1bb3b3367139eb48dda68551e0aedce12eceda9b5f8f93`。本轮再次核验原freeze全部19项文件一致，没有训练、替换、转换或修改模型，也未改标定/动作参数。

## 数据使用事实与精确范围

当前检测数据清单459条（421训练、38验证），顶面数据清单483条（445训练、38验证）。两份清单都保留74张LVIS来源原图及32张Office-Home原图；这是清单覆盖，不等于所有图片都被两个网络同样采样，也不是两个互不重复数据集。

Office-Home：18张训练、14张开发验证，连同能沿source.parent直接追到的派生记录共60条。顶面训练器只采样训练split中有显式顶面多边形的对象，原Office-Home图片中只有4张满足该条件；LVIS原图中1张满足顶面训练条件（有多个容器盖面实例）。派生图另计，不能把清单32张说成32张都直接参与顶面训练；也不能因为本轮只采部分原图，就宣称warm start已经没有早期训练来源。

### 74张实际LVIS／COCO图片的历史许可

| ID | 图片许可（2.0版） | 实际使用原图 | 训练 | 验证 |
|---|---|---:|---:|---:|
| 1 | [Attribution-NonCommercial-ShareAlike License](http://creativecommons.org/licenses/by-nc-sa/2.0/) | 27 | 20 | 7 |
| 2 | [Attribution-NonCommercial License](http://creativecommons.org/licenses/by-nc/2.0/) | 14 | 10 | 4 |
| 3 | [Attribution-NonCommercial-NoDerivs License](http://creativecommons.org/licenses/by-nc-nd/2.0/) | 17 | 12 | 5 |
| 4 | [Attribution License](http://creativecommons.org/licenses/by/2.0/) | 11 | 7 | 4 |
| 5 | [Attribution-ShareAlike License](http://creativecommons.org/licenses/by-sa/2.0/) | 4 | 2 | 2 |
| 6 | [Attribution-NoDerivs License](http://creativecommons.org/licenses/by-nd/2.0/) | 1 | 1 | 0 |

以上共74张，52训练、22验证。含NonCommercial条件58张，其中42训练、16验证；含NoDerivatives条件18张，其中13训练、5验证；两类计数有重合，不相加。许可映射直接抽自此前保存的LVIS官方val标注ZIP，源ZIP及JSON SHA在`lvis_official_image_license_mapping.json`；没有靠记忆假定许可ID含义。原图片SHA与来源记录逐条一致，重复物体标注没有重复计为新的图片。

这些条款直接涉及照片及其复制/改编的使用，尤其是发布原图、裁剪图或抠图增强图时必须核实；**本报告不单凭“曾训练过”就断言权重自动继承图片许可证，也不据此认定当前训练违法或权重必然禁止公开**。比赛是否落入允许用途、模型和输出公开方式是否被覆盖，需要具体条款或权利人答复。训练使用和把图片重新分发是不同事项。

团队保管逐图来源清单，106个公共原图来源=74 LVIS+32 Office-Home；未包含原始照片。历史抓取候选池`source_attribution.json`有205条记录，不能把未采用图片也计入当前训练图。当前顶面/检测的来源统计不能再相加为212张独立公共图。

## 参数训练链

检测参数按metadata的source checkpoint SHA与warm start SHA衔接：

`detector_public_v2 / detector_public_v2_384（同一训练checkpoint的不同导出）→ detector_public_v3 → detector_bottle_field_v1 → detector_six_field_v1 → detector_camera_adjusted_v1 → detector_background_v2`。

六类初始头复用项目三色模型特征及官方COCO剪刀输出，原训练程序记录两个起点SHA。当前实际warm-start分支不会每次重新初始化或抹去旧特征；不能把记录中每阶段出现的official_coco_checkpoint字段误写成每阶段都重新加载了COCO。

顶面参数链：

`surface_bootstrap_v1 → surface_exposure_field_v1 → surface_public_v3 → surface_bottle_field_v1 → surface_six_field_v1 → surface_camera_adjusted_v1 → surface_camera_angles_v2 → surface_eraser_repair_v1`。

原始构造代码选择TorchVision `MobileNet_V3_Small_Weights.IMAGENET1K_V1`，官方权重枚举URL为`https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth`；不是SWAG，不适用把SWAG非商业条款直接套过来的说法。此次没有重新下载或加载该初始化二进制，未把URL中的短摘要冒充已验证完整SHA。

`metadata_lineage.json`保存各候选metadata SHA/输出SHA/warm start来源；这证明可核验记录的衔接，不是通过张量倒推的训练来源证明，也不是第三方授权证书。删除manifest条目、只用自采图继续微调、重新导出ONNX都不能证明历史来源已经消失。

## 现在采取的方式与需要用户决策的边界

当前成功模型继续原样保留为回退，本轮不要求补拍、不要求重新训练，不联系FPGA队友。许可待核实的原图、派生栅格、权重保持外部资产排除。可以继续准备AGPL源码候选及训练/导出/推理说明，但不能承诺该源码候选已能从零合法取得全部训练素材或达到相同模型效果，也不因源码加许可证就更改整个私有仓库可见性。

优先保留现有成果并取得覆盖实际用途的明确说明。内部许可审查记录保存可审核的英文询问草稿，**尚未发送**，也没有虚构联系邮箱。若要对外联系，需要用户决定发送对象与实际用途表述；数据集作者没有原图授权时，还需联系原版权人。

若最终无法得到可覆盖预期公开方式的权利证明，再由用户审核是否开新候选版本：采用经核实的初始化路线及团队自采/明确许可数据重新训练，并重新评测。不能未经用户同意替换成功模型，也不能把“仅在旧权重上删数据继续微调”当成已清除旧来源。新训练模型不保证现有精度和抓取效果，必须保留旧版与标定回退。

公开当前整仓库仍涉及其他分支和历史，这项事实不因用户只负责AI PC而消失；但本轮不要求用户代办其他模块授权，也不把其他模块待办混进AI PC核对结论。需要对外发布时，可准备单独AI PC源码快照作为候选，最终发布内容仍需具体审阅。

## 公开复核

冻结权重哈希和许可计数见 `current_models_final/audit.json`。原始逐图清单、依赖取证和联系草稿由团队保管。
