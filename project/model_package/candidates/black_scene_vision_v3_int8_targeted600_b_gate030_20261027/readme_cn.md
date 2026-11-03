# 黑背景视觉v3：targeted600 INT8候选

2026-10-27，`black_scene_vision_v3_int8_targeted600_B_gate030_20261027`。本包为独立硬件接入候选，不替换active、旧候选或RTL。首先阅读[硬件交接](docs/HARDWARE_HANDOFF_CN.md)。

新Locator G1/G2来自仅旧数据总400步a09c85…，新Classifier来自定向微调总600步da50fec…；两CNN形状、参数量和六类顺序保持。原整数主干conv1–5、confidence尺度/Top1及raw>=−11748门槛完全保持；**G1/G2、残差M/shift及Classifier参数已更新，Locator整个16KiB ROM也已改变，不能只换分类器或照抄旧v2参数。**

## 直接交接文件

- `quantized/locator/model_rom_16k.mem/.bin`：4096个32位字/16384字节，含新G权重/bias/G1与残差换域M/shift。
- `quantized/classifier/weights_all.mem/.bin`：39488字节；`layer_descriptors.mem/.bin`：8×8字/256字节，须同版替换。
- `quantized/*/parameters.npz`及layout JSON：完整量化常数与地址，`manifest.json`和`CHECKSUMS.sha256`用于一致性。
- `reference/integer_vision_reference.py`：完整两CNN整数运算与B级联；`pc_reference.py`：复现用户当前PC路径（整数gate/Top1＋浮点old400几何＋浮点600分类器）。两路径精度不同。
- `golden_integer/index.json`与26个TRAIN样例：全部逐层NPZ/MEM、B128/B32、8bank缓存和带地址1280输出流，包含拒绝手与左倾two。

## 自包含验证

在本包根目录，使用已有NumPy/OpenCV环境；浮点PC参考还需PyTorch，CPU可运行：

```powershell
python -I -B reference/verify_delivery.py
python -I -B reference/integer_vision_reference.py --verify
python -I -B reference/pc_reference.py --verify
python -I -B reference/integer_vision_reference.py --small-npy golden_integer/sample_01/locator_input_u8.npy
```

640×480原图可用`--image 图片路径`；两个reference均支持`--small-npy` B128输入。无需训练工作区、相机、原始TRAIN全集或CUDA。实测版本见dependency_versions.json，构建/复现边界见docs/REBUILD_AND_VERIFY_CN.md。

## 冻结后开发验证

| 数据 | 原认可PC | 同PC ROI＋整数Classifier | 整数ROI＋浮点Classifier | 完整整数 |
|---|---:|---:|---:|---:|
| old_dev | 213/240 | 212/240 | 209/240 | 210/240 |
| usb_dev | 97/100 | 97/100 | 97/100 | 97/100 |
| targeted_dev | 136/150 | 136/150 | 137/150 | 136/150 |

常数只由TRAIN确定并在读开发推理前冻结，没有用DEV/TEST挑量化参数。主干gate/Top1保持，故旧238/240、首批100/100、定向150/150接纳不变，三组无手实际gate误接纳均0。整数旧集相对PC少3张，另外两组总数相同不代表逐图完全相同，详见evidence/precision_comparison.json及quantization_validation_rows.json。

累计检查Locator 970 TRAIN＋550 DEV、Classifier 959 TRAIN＋550 DEV，未观察到int32累加/融合溢出，但有少量uint8高端饱和：
- Locator conv2: 2/74711040个激活高端饱和。
- Locator conv3: 15/24903680个激活高端饱和。
- Locator conv4: 17/9338880个激活高端饱和。
- Classifier conv2: 5/6180864个激活高端饱和。
- Classifier conv3: 1/3090432个激活高端饱和。
- Classifier fc1: 1/96576个激活高端饱和。

它们按既定clamp语义处理并如实保留，未用开发数据回调尺度。原主干参数不能为消除新样本饱和而擅自重新量化，否则confidence/门槛也会变化。

26组TRAIN golden已由独立tap卷积/标量Dense及VGA坐标oracle验证。隔离验证状态见evidence/portable_verification.json。开发静态数据不等于独立TEST或新板测；没有新RTL/BIT、Vivado资源/时序/周期结论。左下角three、左上fist、左倾two仍须新现场检查；已有定向DEV three30/30不能单独验收角落难点。

Git目标：`filid-123/Gesture`，`dev/Rain`，`model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027`。只提交本候选及PROJECT_LOG，不上传重复ZIP、原始全集、现场录像、环境或校准工作缓存。源浮点模型保持原字节，原active与RTL不改。
