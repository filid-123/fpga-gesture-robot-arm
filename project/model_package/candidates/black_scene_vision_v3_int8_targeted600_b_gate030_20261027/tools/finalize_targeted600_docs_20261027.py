"""Complete v3 hardware instructions and numerical evidence before isolated verification."""
from __future__ import annotations
import json,shutil
import targeted600_release_common_20261027 as c
from build_targeted600_package_20261027 import refresh


def main():
    validation=c.read(c.PARAM/'validation.json');q=c.read(c.PARAM/'manifest.json');rows=c.read(c.PARAM/'validation_rows.json')
    comparisons={}
    for role,items in rows.items():
        hands=[row for row in items if row['GT_source'] is not None and row['detected']]
        corrected=[row['image_id'] for row in hands if row['approved_PC_class']!=row['truth'] and row['full_integer_class']==row['truth']]
        regressed=[row['image_id'] for row in hands if row['approved_PC_class']==row['truth'] and row['full_integer_class']!=row['truth']]
        comparisons[role]={'hand_float_correct_integer_wrong':len(regressed),'hand_integer_correct_float_wrong':len(corrected),
                          'corrected_ids':corrected,'regressed_ids':regressed,
                          'same_ROI':sum(row['PC_ROI']==row['integer_ROI'] for row in items),'records':len(items)}
    c.write(c.OUT/'evidence/precision_comparison.json',comparisons)
    table='\n'.join('| '+role+' | '+' | '.join(str(item[name]['correct_hand'])+'/'+str(item[name]['hand_total']) for name in
        ('approved_PC_baseline','approved_PC_ROI_integer_classifier','new_integer_ROI_float_classifier','full_integer'))+' |'
        for role,item in validation['metrics'].items())
    sat=[]
    for kind,key in (('Locator','locator_ranges_TRAIN_and_DEV'),('Classifier','classifier_ranges_TRAIN_and_DEV')):
        for layer,item in validation[key].items():
            if item.get('high_saturation_count',0):sat.append(f"- {kind} {layer}: {item['high_saturation_count']}/{item['activation_elements']}个激活高端饱和。")
    saturation='\n'.join(sat)
    (c.OUT/'README_CN.md').write_text(f'''# 黑背景视觉v3：targeted600 INT8候选

2026-10-27，`{c.ID}`。本包为独立硬件接入候选，不替换active、旧候选或RTL。首先阅读[硬件交接](docs/HARDWARE_HANDOFF_CN.md)。

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
{table}

常数只由TRAIN确定并在读开发推理前冻结，没有用DEV/TEST挑量化参数。主干gate/Top1保持，故旧238/240、首批100/100、定向150/150接纳不变，三组无手实际gate误接纳均0。整数旧集相对PC少3张，另外两组总数相同不代表逐图完全相同，详见evidence/precision_comparison.json及quantization_validation_rows.json。

累计检查Locator 970 TRAIN＋550 DEV、Classifier 959 TRAIN＋550 DEV，未观察到int32累加/融合溢出，但有少量uint8高端饱和：
{saturation}

它们按既定clamp语义处理并如实保留，未用开发数据回调尺度。原主干参数不能为消除新样本饱和而擅自重新量化，否则confidence/门槛也会变化。

26组TRAIN golden已由独立tap卷积/标量Dense及VGA坐标oracle验证。隔离验证状态见evidence/portable_verification.json。开发静态数据不等于独立TEST或新板测；没有新RTL/BIT、Vivado资源/时序/周期结论。左下角three、左上fist、左倾two仍须新现场检查；已有定向DEV three30/30不能单独验收角落难点。

Git目标：`filid-123/Gesture`，`dev/Rain`，`model_package/candidates/{c.ID}`。只提交本候选及PROJECT_LOG，不上传重复ZIP、原始全集、现场录像、环境或校准工作缓存。源浮点模型保持原字节，原active与RTL不改。
''',encoding='utf-8')
    (c.OUT/'docs/HARDWARE_HANDOFF_CN.md').write_text(f'''# 硬件接入说明：v3 targeted600

## 先核对版本

候选`{c.ID}`；Locator PT SHA `{c.LOC_SHA}`；Classifier PT SHA `{c.CLS_SHA}`。Classifier39110参数、Locator8717参数（base7265＋G1452）及接口形状不变。600是本轮定向阶段累计更新，三个200段新数据比例50%/25%/60%，不是全部600步均60%。

## 必须一起更新

1. 新Locator16KiB ROM：原conv1–5权重/bias、M/shift前缀保持，但G1/G2权重/bias、G1 requant和G2残差换域更新，整个ROM SHA已变化。加载本包整个ROM，不仅复制旧v2基础段。
2. Classifier39488字节参数与256字节层描述符同版更新。fc2输出六个raw signed32 logits，无ReLU/requant，公共正尺度，可直接argmax；平分取先出现类别。
3. gate仍signed int32 `raw>=-11748`，拒绝边界−11749、接纳边界−11748。概率说明0.30，confidence尺度保持v2；gate不在Locator权重ROM内，检查实际RTL寄存器或PS比较位置。

## Locator固定ROM地址（字节地址）

| 层 | weight | bias |
|---|---:|---:|
| conv1 | 0x0000 | 0x0048 |
| conv2 | 0x0080 | 0x03E0 |
| conv3 | 0x0440 | 0x0B00 |
| conv4 | 0x0B40 | 0x18C0 |
| conv5 | 0x1940 | 0x1D78 |
| G1 | 0x1DC0 | 0x2240 |
| G2 | 0x2260 | 0x2380 |

conv1/2/3/4/G1各M与shift依次在0x2400＋8i；残差4通道M/shift在0x2440＋8i；有效末尾0x2460，整个16384字节保留。word地址=byte/4，小端，每MEM行一个32位word。G1 dilation2/pad2，G2 dilation5/pad5，输入F3为16×16×16，G1 hidden8，G2输出4（dx,dy,w,h），只融合conv5几何通道，confidence通道不混入残差。

本次residual_M={q['residual_M']}，residual_shift={q['residual_shift']}。所有层的精确scale、M、shift在NPZ/quantized manifest，不从本说明手抄其他版本。conv1–4原M/shift31保持；G1和残差采用各自字段。

## B取样／后处理

VGA实际640×480 BGR按既有灰度转8位；128内容为`gray[0:480:5,0:640:5]`得到96×128，置入small[16:112]，上下16行零。硬件Y灰度和USB BGR2GRAY的相机输入差异仍需板端实测；不要另加直方图均衡或逐帧归一化。

同一128小图用于Locator与Classifier。source几何按本包decode/clip/round到偶数及18%方形ROI，`sx=x0//5;sy=16+y0//5;ss=(side+4)//5`，32取样索引`i*ss//32`。非法ROI不能用GT框或旧PIL缩放替代。source解码/ROI与EMA为明确PC数值语义；完整CNN整数不代表这些PS/RTL后处理已位级对齐。

原时间几何稳定器参数保持，包内提供7条合成时序例。拒绝时即使显示暂留框也不能送Classifier；Classifier background同样不触发目标动作。六类顺序background/one/two/three/fist/palm，动作码要显式映射，不能使用采集脚本历史数字ID。

## 对齐顺序

从sample_01开始比small128字节→conv1–3/Pools→G1/G2和残差换域→conv4/5及fused1280输出→raw峰/gate→source ROI→同帧B32→Classifier逐层→六logits。所有样例先用静态模式；时序对齐另用连续实例、采集单调秒时间戳。

输出流文件为44位{{addr12,data32}}、cell-major/channel0..4共1280行；地址=channel*256+cell，负数数据按补码。golden每组layout描述NPZ/MEM形状和字宽；uint8按小端4字节/word打包，int32一值一word、int64一值一64bit行。

F3/G1/F4为8bank，bank=channel%8、page=channel//8、每页256byte；G2四通道32位拆字节按现有act0映射保存。banks文件为4096byte/bank快照，未写区零只用于夹具padding，不要求硬件每帧全RAM清零。

## 验证与限制

26 TRAIN逐层golden与独立tap/标量Dense/VGA取样oracle一致；MEM/BIN/NPZ/descriptor/ROM地址读回和gate、溢出边界、合成EMA可由verify_delivery自查。校准Locator970/Classifier959合法TRAIN，参数固定后才读DEV，不读封存TEST或把两版现场S图入训/选模。

完整整数旧210/240、首USB97/100、定向136/150；认可PC213/97/136。少量隐藏高端饱和和旧集损失已披露于README/evidence，不等于硬件准确率。旧、首批、定向都是已使用开发集；没有新的均匀光照/角落独立测试或真实OV板测。硬件端仍需RTL仿真、同次BIT/HWH资源/时序/周期和实际场测，不能直接宣布上板通过。候选不覆盖active、旧v2或当前RTL。
''',encoding='utf-8')
    (c.OUT/'docs/REBUILD_AND_VERIFY_CN.md').write_text('''# 复现和源码快照边界

日常接入只使用包内reference、models、quantized、golden与contract，按README三条python -I -B命令在独立目录验证，CPU可运行，不需要生产者D盘、原TRAIN全集或CUDA。

tools中的export/build/common及旧版helper是构建源码快照，ROOT/DATA路径按原训练工作区组织，不能在当前包里直接执行它们重建参数。完整重建需恢复原工作区布局、已审核970个Locator TRAIN与959个Classifier父图及原SHA、冻结v2核心参数和600/old400两PT。先export（只读TRAIN，核心保持、新G和Classifier max-range PTQ），参数冻结后--validate（三个DEV，只比较不挑常数），再build/docs/hash/隔离验证。原训练全集、校准大缓存和工作区绝对来源映射未上传；公开calibration.json保留父图ID/输入SHA和统计，黄金只含26个TRAIN夹具，不含DEV/TEST或现场S图。

新G1范围取实际整数F3按原尺度反量化后通过浮点新G1的全TRAIN ReLU最大值；G2逐输出通道量化并换至原conv5几何尺度。Classifier按新整数几何得到的959个生产B32（背景为已批准peakROI）执行严格100%浮点激活最大值PTQ。权重/bias半数远离零，运行时正M右移半数向正无穷，累加及融合按signed32 modulo wrap，隐藏uint8 clip，FC2无ReLU。没有开发百分位/seed搜索或量化感知训练。

本版参数与模型冻结后不可原位重标量化“改善”验证数；下一次实验另建版本。golden向量用于数值对齐，不是准确率样本。portable_verification.json为构建时隔离运行记录；最终包所有文件和CHECKSUMS可再次哈希核对。
''',encoding='utf-8')
    (c.OUT/'docs/GIT_UPLOAD_CN.md').write_text(f'''# Git范围与获取

原仓库https://github.com/filid-123/Gesture.git，分支dev/Rain，本版只新增`model_package/candidates/{c.ID}`及PROJECT_LOG。旧v1/v2、active、RTL不改；不上传训练原图全集、开发数据、S快照/录像、.venv、校准cache或重复ZIP。26个小TRAIN源图仅用于golden复现。

包内.gitattributes禁止autocrlf/clean过滤改变参数和向量字节，.gitignore明确放行本包.bin。提交前核对每个candidate Git index blob SHA与本地manifest一致，路径清单只允许本candidate和PROJECT_LOG，不用git add -A或强推。原克隆需干净并fetch后保持dev/Rain fast-forward；若失败保留文件检查，不reset覆盖。

硬件同事在自己的干净工程先fetch该分支，通过既有流程取得这个candidate目录；不把整个算法工作树覆盖硬件开发分支。实际提交SHA和远端确认由发布完成记录提供，本说明不伪造尚未产生的commit。
''',encoding='utf-8')
    for source in (c.TOOLS/'finalize_targeted600_docs_20261027.py',):shutil.copy2(source,c.OUT/'tools'/source.name)
    refresh('DOCS_COMPLETE_READY_FOR_PORTABLE_VERIFICATION')
    print({'stage':'V3_DOCS_READY','precision_comparison':{role:{k:v for k,v in item.items() if not k.endswith('_ids')} for role,item in comparisons.items()}},flush=True)


if __name__=='__main__':main()
