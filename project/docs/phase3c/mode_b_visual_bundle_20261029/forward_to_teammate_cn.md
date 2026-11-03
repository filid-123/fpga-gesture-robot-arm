完整视觉已另外补包。请取这个文件，而不是只clone网页或只用10-28 AMD预验证包：

`C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\multiobject\MODE_B_FULL_VISUAL_20261029_v1.zip`

展开目录为同工程`artifacts\multiobject\mode_b_full_visual_20261029_v1\stage`。包内保留工程相对路径，包含模型、19项冻结依赖、完整pc/multiobject、tiled_detector、顶面网络/5裁剪、网页及历史样例、当前标定和毫米回放工具。先解压到新目录运行`python -B scripts/verify_mode_b_visual_bundle.py`，再按START_HERE_CN.md运行真实识别/毫米回放；缺文件可按清单合入Giao，同名冲突先比较SHA。

当前统一入口是`config/ai_pc/mode_b_visual_current_20261029.json`。当前工作区和外参在`artifacts/phase3c/mode_b_ttl_20261028/coordinate_retake_v2/pose_candidate_v2_E2/`下，分别为`WORKSPACE_CANDIDATE.json`和`RGB_DESKTOP_TRANSFORM_CANDIDATE.json`；外参SHA以`7bc4444c...`开头。内参是`docs/phase3b/calibration/RGB_INTRINSICS_CANDIDATE_20261014.json`。不要再用10-27的`9566d29e...`代替当前实抓机位。

完整依赖可以独立跑识别、顶面和毫米候选。网页现有接口仍只是检测预览，网页有序选物/毫米定位→FPGA配置确认→模式B规划抓放的桥接尚需接通，不能因有包就当闭环已完成。接法见包内`docs/phase3c/mode_b_visual_bundle_20261029/INTEGRATION_CN.md`。三类成功运动及10-29补回保持Giao现有包，不在视觉补包里覆盖。
