# 模式B预训练权重与公开数据来源

2026-10-26已实际联网检索、下载并复核；原三色基线不替换。用户已批准六类路线，并要求优先利用成熟参数和公开数据。此文记录实际采用和未采用来源，不把“目录有类别”写成已能识别项目实物。

## 已采用的参数

| 来源 | 用法 | 条款/适用范围 |
| --- | --- | --- |
| [Ultralytics官方YOLOv8s权重](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt) | 本地已存在官方COCO预训练参数；剪刀对应COCO索引76，供新六类head初始化 | Ultralytics AGPL-3.0/Enterprise，随模型来源保留 |
| 本项目成功曝光版YOLOv8s | 复用已适配现场的骨干、检测特征和红黄蓝输出；训练报告绑定SHA | 已冻结成功方案仍独立可用，不覆盖旧权重 |
| 本项目MobileNetV3-small顶面分割 | 从成功权重微调扩展可见顶面形状；编码器源于torchvision ImageNet预训练 | 神经网络定位仍需新物品顶面标注；不是直接得到毫米坐标 |

两个YOLO头的隐藏通道布局匹配，新head保留红黄蓝行，并复制COCO剪刀行；橡皮和容器行重新初始化后训练。由于共享特征已适配现场，复制剪刀输出只是一种warm start，不能宣称未经训练就完整继承COCO剪刀精度。

## 实际采用的数据

| 数据集 | 实际覆盖/下载 | 标签怎样使用 | 局限 |
| --- | --- | --- | --- |
| [LVIS v1](https://www.lvisdataset.org/) / [官方train标注](https://dl.fbaipublicfiles.com/LVIS/lvis_v1_train.json.zip) / [val标注](https://dl.fbaipublicfiles.com/LVIS/lvis_v1_val.json.zip) | 下载官方350,264,821字节train和64,026,968字节val元数据，再下载选中图片；类别199 canister、425 eraser、923 scissors | 剪刀和经目视筛选的圆形储物罐检测框；完整实例掩膜仅用于训练侧抠图增强；另给少数清晰盖面绘顶面轮廓 | LVIS eraser大目标多是铅笔尾/揉捏橡皮，筛选后未用作本版橡皮训练；canister是相关外观，不保证是用户最终短圆柱容器 |
| [Office-Home官方页面](https://www.hemanthdv.org/officeHomeDataset.html) / [Voxel51公开镜像](https://huggingface.co/datasets/Voxel51/Office-Home) | 下载Eraser的41张Product、43张Real World，共84张供筛选 | 原数据只有图像类别，没有检测框或顶面；助手逐图复核后，补长方体橡皮框及可见顶面标签 | 商品图存在重复、包装、多件同框及铅笔尾橡皮；选11张Product及7张Real World训练，另14张Real World开发验证，同图的多件橡皮分别标框 |
| 本项目历史三色与曝光原图 | 复用原60训练/2开发验证条目 | 保留原数据来源、分组与标签；新head红黄蓝顺序不变 | 含历史弱标签和合成图，不是62个新独立实拍 |

LVIS官方说明：“LVIS annotations along with this website”是CC BY 4.0；图像来自COCO，须遵循COCO原图条款。官方页面JS与源图Flickr URL、license ID、COCO URL已留在本地研究/来源记录中；不能把标注许可套成所有图像统一许可。

Office-Home的官方/镜像数据说明采用非商业研究及教学用途声明；镜像标为license:other，不将其写成CC0/可任意商业分发。当前用于本项目研究训练，原图放在忽略Git的本地artifacts，交付时保留来源与论文引用，不把原图库整包推送Git。

引用：Agrim Gupta et al., *LVIS: A Dataset for Large Vocabulary Instance Segmentation*, CVPR 2019；Hemanth Venkateswara et al., *Deep Hashing Network for Unsupervised Domain Adaptation*, CVPR 2017。

## 检查后未纳入本版训练

- [Objects365](https://www.objects365.org/download.html)：确认存在Eraser、Scissors、Canned等类别，获取公开镜像validation标注并筛出174张含橡皮的图片记录，但镜像没有实际图片或原图URL，官方大图包需注册。未把只有标注的记录计为实际训练样本，也没有把Canned自动等同项目短圆柱容器。
- [Open Images v7](https://storage.googleapis.com/openimages/web/download_v7.html)：确认Eraser `/m/02fh7f` 与Scissors类；下载validation/test框标注，只有0/2张橡皮图，不比Office-Home更合适，未将test纳入训练。
- 若干GitHub/文具镜像没有明确数据许可或只给成品YOLOv5权重，未执行其代码或把未知许可权重用于本版。文本任务ERASER与橡皮图片无关，已排除。

## 数据统计和隔离

最新使用 `artifacts/multiobject/mode_b_public_20261026/dataset_v3`，264张编译图：226训练、38开发validation。其中96张是训练侧选定实例的合成抠图，不是96个独立场景。原图和衍生图绑定父来源分组，整个图像族保持原split；官方test没有用于训练。公开图之间仍可能有感知近重复或同商品族，开发validation参与模型选择，不能当成正式盲测。`dataset_v2`的257张及对应结果保留供比较；v3新增7张原先未采用的Real World橡皮图，没有把原验证图片移入训练。

本版标注数量（包含衍生图）：

| 类别 | train实例 | validation实例 |
| --- | ---: | ---: |
| 红木块 | 40 | 2 |
| 黄木块 | 22 | 1 |
| 蓝木块 | 32 | 2 |
| 橡皮 | 50 | 15 |
| 短圆柱容器相关外观 | 34 | 9 |
| 剪刀 | 97 | 19 |

多把剪刀同图的遗漏标签已补齐；初次不完整数据运行保留为`detector_v1`中止记录，随后从`dataset_v2`训练`detector_v2`，再以`dataset_v3`微调`detector_v3`。v3的抠图源增加，固定96次采样内类别占比随之改变，因此剪刀训练实例数略少；不能把这个差异解读为原剪刀标注被删除。训练未采用HSV识别/软件改色，没有新开相机或控制机械臂。

可见顶面原始标签尤其少：4张橡皮原图（2张Product、2张Real World）的可见大平面、同一张LVIS图中的3个圆罐盖面。公开图拍摄方向和重力未实测，这些只是可见面标签。带增强的训练顶面数不能冒充独立原图数。扩展分割仅是启动候选；橡皮有4个公开开发可见面标签，圆罐没有独立可用顶面真值，必须明确报告未验收。

逐条来源、URL/哈希和LVIS原图许可ID见 `source_attribution.json`；人工式视觉标注（由助手绘制，非独立人工真值）见 `public_annotations.json`；实际内容/分组审计见 `data_audit_v3.json`。
