# 硬件接入说明：v3 targeted600

## 先核对版本

候选`black_scene_vision_v3_int8_targeted600_B_gate030_20261027`；Locator PT SHA `a09c85d89469f7fc5ebf57990ac0f2740458a7df2ace8da24dc702709dd8e06d`；Classifier PT SHA `da50fec1e717b4fb4b94cd2bdca7fceb7fadd8383f0f4b8661b1d8ac4ca4e227`。Classifier39110参数、Locator8717参数（base7265＋G1452）及接口形状不变。600是本轮定向阶段累计更新，三个200段新数据比例50%/25%/60%，不是全部600步均60%。

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

本次residual_M=[126680881, 193904139, 233575886, 383048081]，residual_shift=[31, 31, 31, 31]。所有层的精确scale、M、shift在NPZ/quantized manifest，不从本说明手抄其他版本。conv1–4原M/shift31保持；G1和残差采用各自字段。

## B取样／后处理

VGA实际640×480 BGR按既有灰度转8位；128内容为`gray[0:480:5,0:640:5]`得到96×128，置入small[16:112]，上下16行零。硬件Y灰度和USB BGR2GRAY的相机输入差异仍需板端实测；不要另加直方图均衡或逐帧归一化。

同一128小图用于Locator与Classifier。source几何按本包decode/clip/round到偶数及18%方形ROI，`sx=x0//5;sy=16+y0//5;ss=(side+4)//5`，32取样索引`i*ss//32`。非法ROI不能用GT框或旧PIL缩放替代。source解码/ROI与EMA为明确PC数值语义；完整CNN整数不代表这些PS/RTL后处理已位级对齐。

原时间几何稳定器参数保持，包内提供7条合成时序例。拒绝时即使显示暂留框也不能送Classifier；Classifier background同样不触发目标动作。六类顺序background/one/two/three/fist/palm，动作码要显式映射，不能使用采集脚本历史数字ID。

## 对齐顺序

从sample_01开始比small128字节→conv1–3/Pools→G1/G2和残差换域→conv4/5及fused1280输出→raw峰/gate→source ROI→同帧B32→Classifier逐层→六logits。所有样例先用静态模式；时序对齐另用连续实例、采集单调秒时间戳。

输出流文件为44位{addr12,data32}、cell-major/channel0..4共1280行；地址=channel*256+cell，负数数据按补码。golden每组layout描述NPZ/MEM形状和字宽；uint8按小端4字节/word打包，int32一值一word、int64一值一64bit行。

F3/G1/F4为8bank，bank=channel%8、page=channel//8、每页256byte；G2四通道32位拆字节按现有act0映射保存。banks文件为4096byte/bank快照，未写区零只用于夹具padding，不要求硬件每帧全RAM清零。

## 验证与限制

26 TRAIN逐层golden与独立tap/标量Dense/VGA取样oracle一致；MEM/BIN/NPZ/descriptor/ROM地址读回和gate、溢出边界、合成EMA可由verify_delivery自查。校准Locator970/Classifier959合法TRAIN，参数固定后才读DEV，不读封存TEST或把两版现场S图入训/选模。

完整整数旧210/240、首USB97/100、定向136/150；认可PC213/97/136。少量隐藏高端饱和和旧集损失已披露于README/evidence，不等于硬件准确率。旧、首批、定向都是已使用开发集；没有新的均匀光照/角落独立测试或真实OV板测。硬件端仍需RTL仿真、同次BIT/HWH资源/时序/周期和实际场测，不能直接宣布上板通过。候选不覆盖active、旧v2或当前RTL。
