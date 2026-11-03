# Git检索与本机识别接入记录（2026-10-29）

本轮已fetch远端，保留本地dev/Giao工作区，没有合并、切换分支或改写已成功的机械臂轨迹。

| 来源 | 固定版本 | 可复用内容与边界 |
|---|---|---|
| filid最新显示/模式一分支 | [e410dd08](https://github.com/filid-123/Gesture/tree/e410dd08d461c35d9f47f76b74701bb3ca11c532) | `docs/mode_a_displayfix_v0_13_1/INTERFACE_CN.md`、`docs/mode_a_upgrade_v0_13_0/INTERFACE_CN.md`和`scripts/mode_a_terminal.py`提供模式一ABI、只读状态解析与运行阶段；不是网页A/B切换接口 |
| Rain视觉候选 | [022267a9](https://github.com/filid-123/Gesture/tree/022267a939c892d73ae278ceddee1a3e856a8dee) | `model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/docs/HARDWARE_HANDOFF_CN.md`为手势Locator/Classifier；六类是background/one/two/three/fist/palm，不是六类待夹物体 |
| 我方已发布联测包 | [db97c8ab](https://github.com/filid-123/Gesture/tree/db97c8ab507a69618867af19c9717ba3bc130406) | `docs/phase3c/mode_b_teammate_handoff_20261028/README_CN.md`为三类已成功的实体轨迹、参数与状态映射；本网页未更改这些路线 |
| 本机冻结六类物体模型 | `candidate_freeze_v2.json`，19文件SHA绑定 | 本网页直接复用其中`detector_background_v2`与既有`TiledDetector`。物体类为红/黄/蓝木块、橡皮、圆柱、剪刀。当前远端dev/Giao的正常源文件位置不包含这套本机完整视觉环境，不能宣称单独clone即可运行识别 |

## 已完成的连接

`网页所选相机/照片 → PNG原尺寸像素 → 原冻结检测器 → 同帧图像与检测框 → 网页预览`。

`vision.py`只新增适配层，不修改冻结识别源码、模型、阈值、训练集、机位、桌面标定或物理残差。只运行六类检测，不加载抓取表面分割或原1红/2橡皮/3圆柱的固定task映射。网页编号来自当前选择顺序，仅代表预览绑定；实体仍要独立锁定并收到FPGA确认。

启动页面不打开相机、不加载模型；点击“查看识别样例”才对历史原始照片运行真实模型；点“识别照片”只处理该次文件；相机需先明确选择/连接，再点“开始识别”。每次完成一帧后才采下一帧，没有不断堆积的推理队列。离开B、暂停或断开后，迟到结果丢弃，不显示旧框。上传图像只用于内存推理，不自动保存。

历史样例绑定2026-10-27采集记录：文件SHA `a9ee74d9b6134ee0fac2ff0dffbbb8602b3768f6b229c5a35e35dbe90430c5e5`，BGR像素SHA `01f891358bc4493194012513a471cde8ffa4bea786aa466d22e85499ea6293b0`。本轮真实CPU推理识别出六类，属于历史照片回放，不是当前相机或新准确率评估。

本地冻结检测器ONNX SHA `5999c0e1e2d2631cf68b086b1b667ec87eabbb5268b1d6550421371520308cce`。启动优先`.venv-multiobject`，缺依赖或模型时网页仍可展示，识别返回明确错误。迁移到另一电脑需要另行交付冻结清单列出的文件、样例及`numpy/opencv/onnxruntime`环境，不能只复制网页目录。

## 后续板端接入需要完成的部分

1. 按`API_CN.md`实现统一任务A/B配置入口：确认当前空闲、原子更新模式和有序物体映射、返回设备确认与revision。现有`P3S6`没有这一消息；ARM_BACKEND的OFF/DRY_RUN/MONITOR/LINE也不是任务A/B。
2. 状态展示可复用filid的真实寄存器解析。当前最新ARM/PLAN/TASK/VIS/MODEL版本依次3101/3203/340A/3506/022267A9；应先核对实装版本，不能直接把旧ABI的固定偏移当成当前状态。
3. 正式AIPC采用用户要求的NPU时，将已验证的NPU识别服务接到同帧视频/API；本轮是明确的CPU网页预览，`npu_accepted=false`，不声称NPU或FPGA闭环验收。
4. 六类可识别与六类已完成实体抓取应分别验收。现有实体成功证据覆盖红块、圆柱、橡皮；黄/蓝块和剪刀不能因网页出现识别框就被当作已有抓取轨迹。

本轮不启动JTAG、TTL、Wi-Fi运动或任何设备配置写入。
