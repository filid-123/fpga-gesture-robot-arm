# 红块补回：参考filid的节拍实现优化

持久TTL版本v1已完整实测，用户确认“全程正常”：首请求到末反馈174.782秒，较之前204.040秒缩短14.34%。公共点抓取、持稳转运、原位放回和退爪/低HOME均接受。v2修正串口写入阻塞与调度基准后已整程实测130.644秒，并获用户“全程正常”接受。

## Git核查结论

只读GitHub API核对后，filid补回分支`codex/mode-a-auto-restock-20261029`仍指向`480f3e600bc9465d9a1fec361e6781c2b2eb59a0`。最小源码与SHA清单保存在`artifacts/phase3c/mode_b_return_20261029/filid_timing_480f3e6/`，未合并分支或执行队友硬件脚本。

`scripts/mode_a_upgrade_profile.py`使用五次标量时间律：

`s(u)=10u³−15u⁴+6u⁵, u=t/T`。

其20ms周期、UQ32标量、Q16关节关键点由PL执行，段时长同时满足速度、加速度及jerk约束；`steps`按`max(2Δ/v, sqrt(6Δ/a), cbrt(60Δ/j))`向上取整。普通段配置72.6°/s、239.58°/s²、2000°/s³，交付和夹爪另设较缓/较快配置。`prepare_mode_a_restock.py`对连续下降/抬升的同组子段不额外停留，其他运动边界22tick=0.44秒、夹爪边界50tick=1秒。后端使用持续接收和原生T102输出。

我方原轨迹的`Builder.append`已经使用同一个五次时间律。只替换多项式不能解决当前耗时，且直接复制模式A的固定原槽、关节残差、Q16表或速度上限会改变已接受的模式B动态抓取语义。本候选沿用现有浮点原生轨迹，不声称与队友PL逐位等价。

## 已定位并修正的执行开销

- 旧执行器热循环每秒序列化全部历史请求，逐帧通过PowerShell日志操作；每段重新开关串口、采集5条反馈。
- 新`RestockSerialSession.cs`整程只开一次115200/8N1 TTL，持续读取反馈；请求意图先写顺序日志，完整结果只在阶段边界保存。
- Windows真实时钟、模拟串口的100帧测试复现：名义2000ms拖到3119ms，间隔约31ms。运行期间请求1ms计时精度并在finally恢复后，同一测试2165ms，最大帧间隔约22.7ms。这个比例与旧整程名义76.62秒、实际运动发送120.59秒接近；物理TTL还需实测。
- 调度使用单调时钟，迟到就延后，不压缩20ms间隔、不丢帧、不集中追赶。串口输出积压、通信过期或固件/扭矩故障会阻止后续提交，运动请求不重试。
- 运动边界保留0.44秒等待，抓取/放回低点0.8秒，并记录3条间隔100ms的新鲜反馈。原4个T106事件的cmd/spd/acc及“按行程/速度估算+1秒”的等待保持。接触残差只记录，不以到位误差中断后续。

## 保持的实物基线与验证

3835条动作JSON、13段轨迹、4夹爪事件、公共点(300,200)、公共点向下8mm、原位(651.879,257.801,15)mm与附件关系均逐条保持。顺序wire+LF SHA256仍为`1935e7c4d5f13893bdf362d431d79ef18feb7c41976e927bdab9a6598b0da9a2`。

28项Python检查及当前53项C#模拟串口/时钟检查通过，覆盖整段顺序、迟到不追赶、残差只观察、失联、写入失败、设备故障、扭矩关闭、积压、初始姿态不符、软件停止与Windows真实计时；v2新增14ms阻塞写入回归。执行包在硬件访问前重新确定性编译并核对SHA，19项冻结视觉SHA保持。

执行轨迹没有改变，绑定原同SHA计划的Coppelia3873原生样本网格无碰撞证据；本轮未重新打开仿真器，也没有将模拟串口结果当作实体结果。该网格验证不包含摩擦或伺服动力学。此前130–145秒预测未在v1达成；v2真实TTL整程130.644秒，已获实物接受。

当前已验证的红块补回包：`artifacts/phase3c/mode_b_return_20261029/red_session_v2/SESSION_V2.json`。同目录`SOFTWARE_VERIFICATION.json`记录阻塞写入回归与精确轨迹绑定。旧v1历史包保留，绑定旧执行器SHA，当前源码更新后旧包会拒绝直接执行；精确已执行源码在下述实测目录`executed_source/`，亦有已校验v1 ZIP可恢复。

## v1实测与v2修正

v1结果在`session_runs/20261029_085616_8698521/`，独立`ACCEPTED_SESSION_V1.json`绑定计划、执行器会话、结果与核验SHA。3835条指令完全匹配、18组56条边界状态完整、无固件/扭矩故障、串口已关闭。实际运动发送合计126.466秒，帧间隔均值33.05ms，证明无延迟模拟串口测试不足以预测真实TTL。

随后仅发送6条只读T105，另有填充至230字节的合法查询，测得长查询WriteLine阻塞约17.2ms，短查询约0.3–1.6ms，诊断没有运动。v1以WriteLine返回时刻为基准再等20ms，约14ms的写入因此会导致约34ms帧间隔。新增14ms写入模拟回归在修正前失败，修正后通过；当前以实际WriteLine开始时刻计周期，将写入耗时包含在20ms内。若写入超过周期，顺序同步执行自然延长间隔，不做追赶。每次结果另记`wire_started_ms`和`write_duration_ms`，供下一轮实机核查。

## 下一轮整程入口

红块上一轮已补回原位，因此下一轮需重新放到公共点(300,200)，仍按原朝向摆放；原位腾空、机械臂空夹低HOME、手离开，150mm承托物继续移开公共点路线。准备好后只运行一次整段，最后统一反馈。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\scripts\run_mode_b_restock_session.ps1" -Session "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\phase3c\mode_b_return_20261029\red_session_v2\SESSION_V2.json" -SerialPort COM5 -Move -EmptyGripperConfirmed -PublicAreaClearConfirmed -OriginalSourceVacantConfirmed -PublicObjectPlacementConfirmed
```

去掉`-Move`完全离线。入口会重新校验计划/实体接受/仿真/执行器SHA及确定性执行包，之后才访问串口。它是独立候选入口，旧成功执行器保留。

运行目录会输出`RESTOCK_RESULT.json`、逐条意图`REQUESTS.jsonl`和接收`SERIAL_RX.jsonl`，结果为程序序列完成而非实体放置证明。需要软件停止后续提交时，可在该运行目录创建空文件`STOP_REQUESTED`；这不保证物理急停。取消后的回放仍需要从已知停稳姿态另行规划，不自动重跑动作或盲目归位。未接入FPGA/NPU/网页触发。


## v2实体接受（2026-10-29）

用户确认“全程正常”。结果及独立接受证据在`artifacts/phase3c/mode_b_return_20261029/session_runs/20261029_094927_5503514/`；3835条原指令完全一致，释放、退爪与低HOME反馈完整，串口已关闭。首请求至末反馈130.643542秒，比v1缩短25.25%、比旧204.040416秒缩短35.97%；真实帧间隔均值21.495ms，写入阻塞均值11.439ms，运动发送合计82.346682秒。当前成功仅对应本次红块公共点补回与冻结原位，不作为另两类或任意原位的实体接受。计划、执行前软件/执行核验中的待反馈字段保留历史时序，由`ACCEPTED_SESSION_V2.json`记录最终实物接受，不回写旧证据。
