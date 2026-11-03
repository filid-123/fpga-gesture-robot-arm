# 模式B最终提速联测包 · 2026-10-30

本包为三类抓取→抬升→缓冲→交付→退爪→低HOME的当前参考。红块放置后撤离速度已获用户“合适”确认；按用户要求，把同样四段提速应用到圆柱和橡皮，不追加实体试验。两类旧抓取已成功，新转运曲线需队友联测，不标为已实测。

| 类别 | 基础倍率 | 原名义纯运动s | 新名义纯运动s | 抓取补偿/闭合 |
|---|---:|---:|---:|---|
| 红块 red_cube | 2 | 44.20（优化前） | 22.62 | 本局部下降12mm；2.70rad / spd40 / acc5 |
| 圆柱 small_canister | 2 | 43.90 | 23.10 | 桌面X+10mm、原抓取高度；2.80rad / spd40 / acc5 |
| 橡皮 eraser | 3 | 29.02 | 15.00 | 桌面X+13/Y+10mm、下降8mm；2.95rad / spd60 / acc5 |

时间只统计采样运动，不含夹爪停留、查询和确认；不承诺整程耗时同比下降。基础倍率保持各类已成功的抓取速度。主锚向外2mm只加一次，补偿只改运动命令，不写回相机坐标。橡皮额外残差仍限参考点(631.6914,265.6341)的25mm内；红块depth12同样只限其局部25mm，不复制到其他类。源范围和哈希见各自PLAN/PROFILE。

先在仓库根目录运行（仅Python3.10+标准库，不连接硬件）：

```powershell
python -B docs/phase3c/mode_b_optimized_handoff_20261030/verify.py
```

每类 `objects/<类>/` 含完整PLAN、phase_map、sequence/commands、Q16.16参考和四段quintic_segments。`execution.json`给周期、串口参数、夹爪等待及任务状态映射。HOME来自已接受低位停放；承托中心仍(285,195,150)mm，缓冲沿filid设定。历史成功补回130.6秒保持原配置，见 ../mode_b_restock_20261029/README_CN.md；这次只优化正常交付的四段，不改变公共点补回算法。

四段BUFFER/PREPLACE/RETREAT/RETURN_CLEAR使用关节五次曲线q=q0+(q1-q0)(10u³−15u⁴+6u⁵)，额外速度因子2。T102 spd分别2640/2640/3960，acc均254封顶并按同一加速度上限重计时，周期20ms。其余几何/抓取/事件参数保持；放置后仍先横向退爪8mm再上撤。新关节曲线不保证末端直线，因此已经逐样本进行本地关节/包围盒约束检查；本次没有新增Coppelia网格或实体测试。

`quintic_segments`用归一化u的六项系数；曲线时长=(样本数−1)×周期，段发送占时=样本数×周期，两者分开。其他段沿原笛卡尔PCHIP/五次时间律采样；不要将它们误当同一条关节五次曲线。motion_q16是六通道固件弧度、最近偶数舍入、低32位b再s/e/t/r/g；不包含T106事件。PL定点插补尚未逐点验收。

板端先离线输出接受的样本/事件，与本包比对：

```powershell
python -B docs/phase3c/mode_b_optimized_handoff_20261030/verify.py --object-class eraser --observed board_requests.jsonl
python -B docs/phase3c/mode_b_optimized_handoff_20261030/verify.py --object-class eraser --pl-samples board_motion.mem
```

observed每行至少index/label/wire_json，PL每行48位hex。离线比对不证明真实周期、碰撞或夹持力。不得把commands无间隔灌入串口。PC试验的PREPLACE固定2.5秒等待不是正式手势确认；FPGA需实现PRE等待≥2秒、PALM连续500ms许可、FIST连续1秒取消及通信故障处理，原模式A不变。动态选择顺序不得被旧三类参考编号覆盖。

原始相机源点冻结在PROFILE/origin_for_restock，原位归还使用该点，不用补偿后的指令位置。参考点仅供离线向量联测；新位置由当前视觉包重新识别，不能直接复放样例抓取。当前视觉入口 ../mode_b_visual_bundle_20261029/GIT_DELIVERY_CN.md。

`source_snapshot/`和SOURCE_INDEX包含当前规划/执行源码及配置审阅快照；带开发机绝对路径和历史哈希的输入证据保持原样。它不是换机即用的实时部署包：动态规划需部署视觉/几何环境并重新绑定本机证据路径，不能只替换路径字符串后继续使用旧SHA。实体入口scripts/run_mode_b_ttl_{red,cylinder,eraser}_trial.ps1显式传当前共享speed profile；没有Move不会发送运动。新包核验与本次生成均无设备访问。

evidence保存历史基线/用户反馈，保留旧计划false/pending字段；独立红块OPERATOR_FEEDBACK只接受本轮撤离速度。NPU实际执行、FPGA整链、取消/故障分支和新速度动力学仍由队友联测，不由发送完成推断接受。
