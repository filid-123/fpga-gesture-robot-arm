# 模型与软件栈声明

| 模型 | 来源/版本 | 精度与入口 |
|---|---|---|
| PL Locator/Classifier | `black_scene_vision_v3_int8_targeted600_b_gate030_20261027`，训练/整数导出声明随目录保存 | INT8，描述符、MEM/ROM、逐层黄金向量在 `project/model_package/candidates/` |
| B 检测 | YOLOv8s；声明的 Ultralytics 版本8.4.89；队友 Giao 固定来源版本见原包 manifest | FP32 ONNX，输入512×512，RGB 0～1/letterbox114，原六类输出；当前任务使用红块/橡皮/小圆罐 |
| B 顶面分割 | `mobilenetv3_small_top_unet_v1`，torchvision ImageNet 编码器起点加项目微调 | 256×256 RGB，FP32 PyTorch checkpoint；可见面不是独立重力真值 |

B 检测 ONNX SHA256 `5999c0e1e2d2631cf68b086b1b667ec87eabbb5268b1d6550421371520308cce`；分割 checkpoint SHA256 `9143a31f4ced63410d1bb3b3367139eb48dda68551e0aedce12eceda9b5f8f93`。完整模型元数据保留在各目录 `model.json`。权重再分发待确认，Git 不含这些外部权重。

当前推理通过 ONNX→onnx2torch 转换和显式 HIP 设备执行，分类/标定/IK 仍有 CPU 工作；不能把整个系统称为全 GPU。无 CPU 推理静默回退，NPU 编译未通过，不能宣称 NPU 部署成功。

封存环境的完整版本锁位于 `project/requirements_mode_ab_lock.txt`：ROCm SDK10.0.0、torch2.13.0+rocm10.0.0、torchvision0.28.0+rocm10.0.0 等。原保存帧设备记录实际HIP版本为7.15.26333；SDK包版本和实际HIP版本分开记录。它是原包记录，不代表任意机器当前可安装或运行。赛题要求 ROCm7.14.0及以上，最终提交须写出实际驱动、运行时与设备探测结果。原 AMD whl-next 源有变化的可能；环境重建失败应保留失败结果并重新评估版本组合，不能悄悄换 CPU 包。

原包保存9张实测来源帧的 HIP/CPU 数值对照和毫秒定位结果。开发验证参与过模型选择；正式独立检测 mAP、分割 mIoU、现场连续性能仍 NOT_RUN。训练使用的公开来源与限制见 [许可审查](license_audit.md) 及 [原始来源记录](../project/docs/phase3c/mode_b_six_objects_20261026/public_sources.md)。

当前PL INT8模型可直接从封存预测复算质量：old_dev270、usb_dev120、targeted_dev160，共550张；六类有效动作正确503张，Accuracy91.454545%，Macro-F1为0.9230474275302606（92.304743%）。手势准确率443/490=90.408163%，检测召回488/490=99.591837%。未通过检测门控的输出计为background/无有效手势，不能只看未门控分类top1。DEV参与模型选择，这些数值不宣称独立TEST或新增板测；B检测mAP与分割mIoU仍无对应独立真值结果。[复算报告](metrics_recovery_20261101.md)给出分组、混淆矩阵来源和重算入口。

## 2026-11-03冻结模型离线质量复算

当前同SHA的检测/顶面模型已在CPU离线运行，结果与数据说明见[视觉评测](report_metrics_20261103/README_CN.md)。38张DEV检测mAP@0.5/0.5:0.95=87.51%/65.52%；一个新摆放20张连续帧=100%/83.28%，GT框条件下二分类可见顶面mIoU=95.45%。20帧只算一个布局，标签为AI近似标注且尚未人工复核。此处补的是开发/历史核对结果，不改变上文“独立TEST仍NOT_RUN”，也不证明HIP/NPU新部署或毫米坐标精度。模型/生产代码/冻结清单未改；现有HIP实测证据独立保留。

当前原创源码许可证已选择AGPL-3.0-only。模型权重再分发仍按第三方来源单独核实，见[许可更新](open_source_audit_20261103/README_CN.md)。
