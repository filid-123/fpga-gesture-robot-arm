# 六类模式B：AMD目标机部署预验证

2026-10-28。本包可交队友验证当前候选的NPU检测和ROCm顶面网络，无须接相机或机械臂。先跑包内保存图，成功后再安排实体联调。

## 固定任务与模型

| 手势任务 | 抓取目标 | 尺寸/摆放 |
| --- | --- | --- |
| 1 | 红木块 red_cube | 名义30 mm立方体，当前尺寸登记仍未确认 |
| 2 | 橡皮 eraser | 65×15×15 mm，65×15大面向上 |
| 3 | 药瓶 small_canister | 盖/身均直径25 mm，高46 mm，直立闭盖 |

黄木块、蓝木块、剪刀只识别。检测头索引依次为red_cube、yellow_cube、blue_cube、eraser、small_canister、scissors，不能将索引直接当手势ID。

- 检测：YOLOv8s，512×512，FP32 ONNX SHA256 `5999c0e1e2d2631cf68b086b1b667ec87eabbb5268b1d6550421371520308cce`。
- 顶面：MobileNetV3-small编码器及学习解码器，256×256，权重SHA256 `9143a31f4ced63410d1bb3b3367139eb48dda68551e0aedce12eceda9b5f8f93`。
- 固定原图BGR→RGB/0..1及各网络原有归一化，不加软件gamma补色。检测按整图加重叠方形视图推理；顶面按同一帧5个固定偏移裁剪的概率平均。阈值保留检测0.4、分割0.7、形状IoU0.85。
- 旧成功三色方案及其回退包独立保留；本包不改变它的手势绑定。

## 已有证据及适用范围

包内`handoff/replay`为一个六物品摆放的20相关帧和一个旧空场的5相关帧，均排除训练和量化校准。已存CPU参考是本轮重新推理结果，便于同图比较；它不是独立真值或新增现场成绩。旧六物品核对中六类均20/20检出、三顶面20/20可用，但橡皮像素中心仍有变化。

`handoff/calibration`只选当前检测器原训练集里的全分辨率项目实拍，包含来源清单与哈希；转换时复用检测的整图/方形视图预处理。不得加入`replay`作为校准或训练数据。相关公开来源与许可见`docs/phase3c/mode_b_six_objects_20261026/public_sources.md`。

毫米定位沿用“学习顶面+已知高度+标定几何”路线。当前整桌原点为前左桌角，X向右、Y向桌后、Z向上；取物区X=490..690、Y=215..355 mm。硬件预验证只比较像素，不把旧图估计坐标传给运动模块。相机/基座配准、TCP及三个物品实抓另行续接；允许不影响夹取的小误差，详见本目录`GRASP_TOLERANCE_CN.md`。

## 队友准备

1. 记录实际APU/NPU/Radeon型号、操作系统和驱动。按目标设备官方支持矩阵建立Ryzen AI SDK/Quark环境与PyTorch ROCm环境，可以是两台机器/两个操作系统；两个Python不用装在一起。不要在SDK环境安装本机CPU依赖锁去覆盖厂商包。
2. NPU环境需要其SDK兼容的onnxruntime/VitisAI EP、Quark、onnx、numpy、opencv。ROCm环境需要匹配的PyTorch、torchvision、numpy、opencv；阶段间仅传JSON与原图。程序不会自动安装依赖。
3. 从当前SDK官方示例建立`provider_options.json`，填写设备支持的配置和独立缓存目录。不要照抄别人的设备路径或假定所有SDK都支持同一种BF16转换。项目既有ROCm版本要求须对照正式赛题、官方发行版本和设备支持逐项确认，不能用Torch版本号替代ROCm发行版本。
4. 解压到新目录。先用任意Python运行`python -B scripts/verify_deployment_archive.py .`，应输出全部文件校验通过；此步骤只需要Python标准库。

## Windows一键采集证据

在解压目录打开PowerShell，替换三个绝对路径：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_mode_b_amd.ps1 `
  -NpuPython 'D:\RyzenAI\python.exe' `
  -RocmPython 'D:\ROCmEnv\python.exe' `
  -ProviderOptions 'D:\SDKConfig\provider_options.json' `
  -Precision BF16 -Runs 30
```

脚本将转换一个六类检测模型→NPU分块检测→ROCm三目标顶面→CPU同图比较，全部使用新输出目录。默认BF16是待目标SDK验证的转换选项；若官方组合不支持，请保留错误日志，按官方示例确认能用的BF16/XINT8路径。程序缺EP、缺HIP设备或转换不兼容即报错，不回退CPU。`-NpuPackage`可指定先前用本包inputs清单转换并带来源哈希的模型，不能指定旧三色或另一清单的量化包。

provider选项常见结构如下，但具体键值必须按安装SDK填写：

```json
{"config_file":"D:/SDKConfig/vaiml_config.json","cache_dir":"D:/SDKCache/mode_b_v1","cache_key":"mode_b_v1"}
```

## 分环境或Linux运行

每步都从解压根目录执行，`target_results/run01`需为本次新结果位置。若在不同机器跑，先传相同完整包，再将前一步的输出目录复制过去。provider配置需对应实际NPU机器。

```text
<NPU Python> -B scripts/quantize_mode_b_deployment.py --precision BF16 --out target_results/run01/quantized
<NPU Python> -B scripts/check_mode_b_deployment.py detect --backend npu --package target_results/run01/quantized/model.json --provider-options provider_options.json --runs 30 --out target_results/run01/npu_detector
<ROCm Python> -B scripts/check_mode_b_deployment.py surface --backend rocm --detections target_results/run01/npu_detector/detector.json --out target_results/run01/rocm_surface
<ROCm Python> -B scripts/check_mode_b_deployment.py compare --candidate target_results/run01/rocm_surface/surface.json --out target_results/run01/comparison.json
```

请将stdout/stderr、SDK编译缓存中的算子分配和实际运行日志一起保留。NPU计时是预热后的整图+方形视图检测；顶面计时是缓存检测框后的5裁剪分割/几何处理，不包括检测时间、相机或文件读写，不能直接称端到端延迟。20相关帧不当20个独立场景。

## 回传与验收

回传整个`target_results`本轮目录，并填写本目录`RETURN_TEMPLATE_CN.md`。重点看`comparison.json`里的新增/丢失检测、框IoU、顶面可用性、轮廓IoU和像素中心变化。CPU参考不是GT，像素差不是毫米误差；药瓶只比较盖面轮廓，实体圆心必须在标定顶面平面求。

VitisAI EP已注册、运行时无CPU回退，仍不足以证明核心确在NPU执行；需要SDK算子/子图分配、实际运行与设备负载证据。ROCm需真实HIP设备和运行证据。预验证工具保留待审阅状态，不自动声称NPU/ROCm、定位精度或实体夹取通过。
