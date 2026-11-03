# 冻结B模式视觉模型：数据说明、评测入口与实际结果

评测日期2026-11-03。本轮不训练、不改运行阈值、不操作硬件；按原freeze的19项文件SHA核对当前比赛基线模型，再使用CPU离线推理。检测ONNX SHA256 `5999c0e1e2d2631cf68b086b1b667ec87eabbb5268b1d6550421371520308cce`；顶面checkpoint SHA256 `9143a31f4ced63410d1bb3b3367139eb48dda68551e0aedce12eceda9b5f8f93`；冻结清单SHA256 `cf2c959aa9aae7660015a3769ff1edcd6ed4ca8e32dee0f8e3a4fbbb9cbc5778`。这些与p4.1元数据的模型SHA一致；生产HIP路线并非本次评测执行后端。

## 可引用结果

| 数据范围 | 图像/检测真值 | mAP@0.5 | mAP@0.5:0.95 | 二分类顶面mIoU | 端到端顶面mask IoU（拒绝计0） |
|---|---|---:|---:|---:|---:|
| 开发验证（参与模型选择） | 38张/48实例 | 87.50798270% | 65.51540947% | 82.81037422% | 36.93369569% |
| 历史新摆放核对（仅1布局） | 20张/120实例 | 100.00000000% | 83.28236022% | 95.44795375% | 94.01692926% |

这两组均是**开发/历史核对质量，非正式独立测试成绩**。标签来自AI视觉近似框和可见顶面多边形，`human_ground_truth_reviewed=false`；模型表现没有跨多布局、多光照盲测保障。单布局100%的AP50不能写成整个系统100%识别率；顶面mIoU也不是六类语义分割mIoU、毫米坐标精度或抓取成功率。

| 类别 | DEV实例 | DEV AP50 | DEV AP50:95 | 单布局实例 | 单布局 AP50:95 |
|---|---:|---:|---:|---:|---:|
| red_cube | 2 | 100.00% | 95.05% | 20 | 99.28% |
| yellow_cube | 1 | 100.00% | 90.00% | 20 | 89.12% |
| blue_cube | 2 | 100.00% | 92.52% | 20 | 93.10% |
| eraser | 15 | 85.28% | 41.32% | 20 | 69.15% |
| small_canister | 9 | 78.23% | 41.00% | 20 | 80.00% |
| scissors | 19 | 61.54% | 33.19% | 20 | 69.04% |

较严格框定位下，DEV橡皮/药瓶/剪刀AP50:95较低，是需要补充验证的薄弱项；不能仅展示三色块和单摆放优值。DEV分割仅有4个橡皮顶面真值，二分类mIoU82.81%不代表其他物类。单布局顶面真值为红块/橡皮/药瓶各20，共60个；20帧对应同一布局，不能当作20个独立场景。流水线顶面在DEV为2/4可用，单布局60/60可用。

## 数据清单与防泄漏范围

- `development_validation.json`逐图记录38张选择验证图的图像/像素SHA、尺寸、类别框和可用顶面多边形。检测真值48个；原训练/验证manifest来源SHA也随清单保存。该验证集已参与模型选择，不因这次重新评测变成TEST。
- `one_layout_check.json`记录2026-10-27冻结后核对的20张连续帧、120个检测真值及60个顶面真值。原`fresh_check_exclusion_lock.json`和当时的标注文件路径/SHA保留；此组此前已被观察，不称新的盲测。
- 评测对检测与顶面训练manifest检查精确图像/像素/嵌套父来源SHA和采集session。DEV按预期出现验证集重合，单布局未发现这些精确重合。此审计不证明不存在近重复，也不穷尽预训练或隐含来源。
- 原图含公开来源和团队自采。图片、权重不随这次提交再分发，只有标签/数值/来源。Office-Home等权利限制见[许可审计](../open_source_audit_20261103/README_CN.md)；完整图像重跑需合法恢复原始资产。不能以重新生成标签抹除原图来源。

## 指标定义

**检测AP：** 当前冻结TiledDetector的全帧加方形切片；模型输入512×512。评测置信度下限0.01（原decoder支持下限），类别内NMS，图像最多100个检测；不改生产0.4阈值。按类别、图像贪心一对一IoU匹配，IoU阈值0.50到0.95间隔0.05，101点插值精度平均；无真值类别从均值排除，空场误检仍计FP。这里是针对完整标注场景的COCO式实现，无crowd/ignore及面积子组支持。相同保存预测另外用官方pycocotools 2.0.11的bbox/all/maxDets100交叉核对，两组mAP差均小于1e-12，详见`coco_reference.json`。参考时先采用相同图像级100框上限，与官方默认按类别上限的差别已明确处理。

**神经网络二分类顶面mIoU：** 在GT物体框外扩18%的ROI上运行原五裁剪对齐概率平均，阈值0.7。累计所有有效ROI的TP/FP/FN/TN，foreground IoU=TP/(TP+FP+FN)，background IoU=TN/(TN+FP+FN)，二者均值为binary mIoU。这是**给定真值框条件下**可见顶面质量；不同于全图语义分割或检测到顶面的端到端定位率。顶面类只有红块、橡皮、药瓶。AI多边形按最近整数像素栅格化，近似标注误差未做人工计量确认。

**端到端顶面mask IoU：** 另用原生产0.4/0.7阈值和几何拟合流程；需同类框IoU≥0.5且一个结果最多关联一个GT，再比较拟合顶面多边形与GT。未检出、歧义、拒绝均计0，分母不剔除失败。该指标是像素形状，不测毫米中心误差。正式毫米误差仍需独立实物测量。

## 无受限资产复算数值

在仓库根，Python3.12标准库即可：

```powershell
py -3.12 tools/vision_metrics/verify_saved_vision.py
py -3.12 -m unittest discover -s tools/vision_metrics -p test_metrics.py -v
```

保存证据在`metrics/evidence/vision_20261103/`，两个`final_*`子目录各含逐帧预测和report（逐ROI混淆计数、模型哈希、运行库/后端、重合审计、评测代码SHA）。`evidence_index.json`绑定结果文件SHA。数值重算不重新运行网络，不冒充一次新模型测试。

可选官方参考核对：在独立评测环境安装`pycocotools==2.0.11`及NumPy，然后运行：

```powershell
python tools/vision_metrics/compare_coco_reference.py --out local/coco_reference_repeat.json
```

## 合法持有原资产时重新运行网络

先按`docs/reproduction.md`恢复合法取得的p4.1原包；配置与本报告兼容的独立CPU评测环境（ONNX Runtime、Torch、TorchVision、OpenCV、NumPy等，实际运行版本见report的runtime）。不要覆盖生产HIP环境。根路径用占位变量，输出必须新目录：

```powershell
$visionProjectRoot = (Resolve-Path './project').Path
python tools/vision_metrics/evaluate_competition_vision.py --project-root $visionProjectRoot --manifest docs/report_metrics_20261103/development_validation.json --out local/vision_dev_repeat
python tools/vision_metrics/evaluate_competition_vision.py --project-root $visionProjectRoot --manifest docs/report_metrics_20261103/one_layout_check.json --out local/vision_check_repeat
```

可将`--project-root`换成保留全部原始冻结文件的开发根目录。缺图、模型哈希不匹配或非DEV集合命中训练/验证来源时应停止，不能改SHA通过。本次实际使用原开发目录，所有19个冻结文件一致。CPU推理完成不等于AMD HIP/NPU复验，不将原观测记录中的NOT_ACCEPTED改写成硬件失败或本轮硬件验收。

## 独立测试集的剩余工作

建议先锁定比赛模型/阈值/后处理，再采至少30次独立重新摆放（正常、较暗、较亮各10次），每次一张代表帧；六类完整入镜，三种抓取目标覆盖位置/角度，另加空场与干扰负例，所有可见目标标全。连续帧不跨训练/验证/测试分组；按采集会话与场景划分，保留原图SHA。先由人工核对六类框和三类可见顶面GT，再只运行锁定版本一次，报告每类AP、两种mAP、二分类mIoU、顶面拒绝率，并用独立尺量中心位置补毫米误差。

这是一项待用户安排的后续采集/审核任务，本轮未执行，不能补造独立TEST成绩或将旧图重新命名为新测试。评测后若继续训练/调参，该测试集应转为开发集，并重新采最终盲测集。
