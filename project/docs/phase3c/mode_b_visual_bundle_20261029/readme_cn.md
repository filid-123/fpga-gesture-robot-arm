# B模式完整视觉包与当前标定

2026-10-29。队友反馈正确：远端`dev/Giao`已发布网页和运动交接，但网页引用的本机六类视觉依赖尚未随之发布。10-28的AMD包是部署预验证，未包含网页原路径冻结链和后来实抓采用的相机外参。本补包补齐这些文件。

## 可以传给队友的文件

本机工程根目录：`C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab`。

- 完整补包：`artifacts\multiobject\MODE_B_FULL_VISUAL_20261029_v1.zip`，旁边有`.json`和`.sha256`。
- 展开目录：`artifacts\multiobject\mode_b_full_visual_20261029_v1\stage`。
- 该包保留工程相对目录。可以独立解压运行网页/视觉，也可向已有Giao检出目录补齐缺失文件。不要再只复制`web/project-console`或只发昨日AMD包。

包内含实际ONNX、顶面权重、完整`pc/multiobject/*.py`、`pc/mode_b`视觉运行模块（含`tiled_detector.py`、`surface_ensemble.py`）、原冻结清单及其19个SHA依赖、网页与启动脚本、历史样例、当前相机外参/内参/工作区、实抓时三物品的图像和原定位结果、毫米回放入口、AMD校准图与双环境验证工具。不包含虚拟环境、完整训练数据图片、机器人执行器或整套历史运动证据；原训练manifest保留用于冻结校验。

## 当前应加载的标定

先读统一入口`config/ai_pc/mode_b_visual_current_20261029.json`，不要凭文件日期猜外参。

| 项目 | 工程相对路径 |
| --- | --- |
| 原冻结清单 | `artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json` |
| 六类检测 | `model_package/mode_b/detector_background_v2/model.json`及`model.onnx` |
| 顶面分割 | `model_package/mode_b/surface_eraser_repair_v1/model.json`及`weights.pt` |
| 当前工作区 | `artifacts/phase3c/mode_b_ttl_20261028/coordinate_retake_v2/pose_candidate_v2_E2/WORKSPACE_CANDIDATE.json` |
| 当前相机外参 | 同目录`RGB_DESKTOP_TRANSFORM_CANDIDATE.json` |
| 当前方向检查原记录 | 同目录`DIRECTION_CHECK.json` |
| 相机内参 | `docs/phase3b/calibration/RGB_INTRINSICS_CANDIDATE_20261014.json` |
| 实抓局部参考 | `artifacts/phase3c/mode_b_ttl_20261028/today_native_anchor/ACCEPTED_NATIVE_SOURCE_ANCHOR.json` |

当前外参SHA256：`7bc4444cbffa6fb84c3b4d0526b7105789d46e714cd1f932b3163e5d8748a77f`。
内参SHA256：`15fd11a87bb39aec230a2bb5aa0bf2e7846390d76dd48fe5955becde3f634200`。
检测模型SHA256：`5999c0e1e2d2631cf68b086b1b667ec87eabbb5268b1d6550421371520308cce`。
顶面权重SHA256：`9143a31f4ced63410d1bb3b3367139eb48dda68551e0aedce12eceda9b5f8f93`。

10-27外参`9566d29e...`仅为历史参考，**不要用于当前实抓机位**。原始标定文件保持字节及失败/待验收标志；当前选择依据是10-28成功实抓计划/三物品原定位输出共同绑定`7bc4444...`。它是同机位的局部试验参考，绝对相机→基座/TCP全域标定仍未通过。相机、焦距、桌面、底座移动后不能因复制了文件就沿用实抓局部补偿。

坐标系为`desk_global_mm`，原点桌面前左角，X向右、Y向后、Z向上；200×140 mm取物区X490..690、Y215..355。顶面投影高度红30/橡皮15/瓶46 mm；交给运动的物体中心Z分别15/7.5/23 mm，不要把顶面高度当中心Z，也不要把固件端点当物体中心。

## 解压后先验证

在全新解压目录使用Python3.10+标准库即可检查所有文件和当前标定链：

```powershell
python -B scripts/verify_mode_b_visual_bundle.py
```

再使用带numpy、OpenCV、ONNX Runtime、Torch、torchvision的CPU环境运行真实模型和毫米回放。环境不随包复制，不需要Ultralytics或训练依赖来推理；AMD环境按原SDK支持矩阵隔离。

```powershell
& '<视觉Python绝对路径>' -B -X utf8 scripts/replay_mode_b_visual_bundle.py --out target_results/visual_metric_01
& '<视觉Python绝对路径>' -B -X utf8 web/project-console/server.py --port 8765
```

打开`http://127.0.0.1:8765/#/mode-b`，点击“查看识别样例”应真实检出六类。毫米回放默认使用10-28成功红块的保存图；输出`observation.json`、`metric.json`、`detected.png`。要换输入图，需1920×1080、同相机机位，显式传`--image <图.png> --same-camera-pose`。旧10-27六类样例只用于类别/像素预览，不能套当前外参得毫米真值。

CPU预览不代表NPU运行。包内`docs/phase3c/mode_b_amd_handoff_20261028/TEAMMATE_START_CN.md`及`verify_mode_b_amd.ps1`继续用于目标机转换/NPU/ROCm同图核对。曝光−4只适用于原本那只相机与驱动，换机先查设备身份/曝光读回；浏览器预览不控制原曝光采集工具。

## 合入Giao与尚缺的桥接

推荐队友先独立解压确认能识别和定位，再把缺失目录按原相对路径合入Giao。已有同名文件必须先比较SHA；一致则保留，冲突由队友处理，不覆盖新的网页/运动版本。`MODE_B_VISUAL_BUNDLE_MANIFEST.json`可作为拷贝清单；冻结依赖应保持原字节，不通过修改冻结清单规避缺文件。

本次提供完整本机包与路径，尚未提交/推送Giao，也没有代发消息。可直接转发[队友短说明](FORWARD_TO_TEAMMATE_CN.md)。

**文件齐全后能独立运行识别、顶面定位和桌面毫米候选；从网页一路触发抓放还需桥接。** 已发布网页的`vision.py`仅CPU检测预览，`API_CN.md`规定的FPGA配置确认服务、同帧定位与动态任务冻结还未联合实现。具体接法及职责见[INTEGRATION_CN.md](INTEGRATION_CN.md)。不要把旧照片或网页显示框自动当作运动许可。
