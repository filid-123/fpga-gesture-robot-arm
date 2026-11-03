# B模式完整视觉文件：Git交付入口

2026-10-29。交付分支：`origin/dev/Giao`。本次把完整视觉包按工程原相对路径纳入Git，包含实际权重和当前标定；无需另找未入库的本机文件。

完整ZIP为113,669,801字节，超过GitHub普通Git单文件100 MiB限制，因此上传其展开文件；最大单个模型约44.7 MB，权重为实际文件，不是LFS占位符。原包内README与START_HERE中的“尚未推送”描述是生成包时的历史快照；Git交付状态以本文件及当前提交为准，原清单绑定内容保持不变。

## 队友先做这两步

在已有`dev/Giao`检出目录、保存好自己的改动后拉取：

```powershell
git pull --ff-only origin dev/Giao
```

在工程根目录，用Python 3.10+核对全部237个清单文件、19个冻结依赖和当前标定SHA链；这一步只需标准库：

```powershell
py -3 -B scripts/verify_mode_b_visual_bundle.py
```

应输出`COMPLETE_VISUAL_FILES_AND_CURRENT_POSE_HASHES_PASS`、`files: 237`、`frozen_files: 19`。若`py`不可用，用本机Python的绝对路径运行同一脚本。SHA失败时先查文件或行尾变更，保留冻结清单，不能修改清单来消除错误。

## 现在可从Git获取的关键文件

| 用途 | 工程相对路径 |
| --- | --- |
| 全包文件与SHA清单 | `MODE_B_VISUAL_BUNDLE_MANIFEST.json` |
| 六类检测器实际ONNX与配置 | `model_package/mode_b/detector_background_v2/` |
| 顶面模型实际权重与配置 | `model_package/mode_b/surface_eraser_repair_v1/` |
| 冻结清单及19个原路径依赖 | `artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json` |
| 识别/分割运行代码 | `pc/multiobject/` |
| 分块检测与顶面集成 | `pc/mode_b/tiled_detector.py`、`pc/mode_b/surface_ensemble.py`及同目录视觉模块 |
| 当前视觉与标定统一入口 | `config/ai_pc/mode_b_visual_current_20261029.json` |
| 当前实抓机位工作区与外参 | `artifacts/phase3c/mode_b_ttl_20261028/coordinate_retake_v2/pose_candidate_v2_E2/` |
| 原相机内参 | `docs/phase3b/calibration/RGB_INTRINSICS_CANDIDATE_20261014.json` |
| 实抓源图、像素定位、毫米参考及验证证据 | `artifacts/phase3c/mode_b_ttl_20261028/`、`handoff/` |
| AMD目标机NPU/ROCm交接 | `docs/phase3c/mode_b_amd_handoff_20261028/TEAMMATE_START_CN.md` |

当前外参SHA256为`7bc4444cbffa6fb84c3b4d0526b7105789d46e714cd1f932b3163e5d8748a77f`，通过统一入口加载，不选旧10-27外参。桌面坐标X向右、Y向后、Z向上；相机姿态改变后需重新核对。成功实抓局部参考不代表全域标定已接受。

## 运行真实识别与毫米回放

使用已有的视觉CPU环境（numpy、OpenCV、ONNX Runtime、Torch、torchvision；环境本身不提交Git）：

```powershell
& '<视觉Python绝对路径>' -B -X utf8 scripts/replay_mode_b_visual_bundle.py --out target_results/visual_metric_01
& '<视觉Python绝对路径>' -B -X utf8 web/project-console/server.py --port 8765
```

回放输出`metric.json`、`observation.json`、`detected.png`，输出目录需未存在。网页地址`http://127.0.0.1:8765/#/mode-b`，点“查看识别样例”运行真实六类检测。默认毫米回放使用当前实抓机位的红块源图；网页六类旧样例仅用于类别/像素检查，不能套当前外参作为毫米真值。

六类为红块、橡皮、药瓶、剪刀、蓝块、黄块；现有实体抓取支持红块、橡皮、药瓶。网页动态选择顺序与原固定1/2/3视觉profile分开处理。

Git中的文件已能支撑识别、学习顶面定位和已知高度投影到桌面毫米候选。**网页选择→实时定位冻结→FPGA模式/映射确认→既有抓放的统一桥接仍需集成与联测；NPU/ROCm目标机尚未验收。** 接口和职责见[INTEGRATION_CN.md](INTEGRATION_CN.md)。本次上传不改已接受的运动轨迹或驱动实体设备。
