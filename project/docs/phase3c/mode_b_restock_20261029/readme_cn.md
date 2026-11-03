# 模式B：公共点取回，放回本次原抓取位置

**当前成功版本：红块v2完整补回130.644秒，用户确认全程正常。** 队友先读[成功版本联测入口](accepted_red_v2/README_CN.md)，或下载[完整成功资料包](MODE_B_RED_RESTOCK_ACCEPTED_20261029.zip)。进入解压目录运行`python verify.py`即可离线核验，不连接硬件。它包括原始成功证据、3835请求、9状态映射、执行参数及192位Q16参考。

用户已确认公共点桌面XY=(300,200)mm。参考filid的`codex/mode-a-auto-restock-20261029`，固定来源提交`480f3e600bc9465d9a1fec361e6781c2b2eb59a0`。只复用补回行为、阶段和取消规则；模式B保留三类物体、动态源点、原抓取修正及低位HOME。

首轮红块公共点实测后的下降8mm修正版另见[PUBLIC_RED_DEPTH8_CN.md](PUBLIC_RED_DEPTH8_CN.md)。原三类审阅ZIP和`review/`保持修正前归档；新修正版重新绑定接触深度并保持原释放中心，其源放回关节指令随之调整，不能与下文原版的“精确复原原抓取指令”混用。

下降8mm修正版已获实物全程接受，随后用户要求运动再快2倍；新版及其独立接受边界见[RED_SPEED2_CN.md](RED_SPEED2_CN.md)。

## 行为

1. 原模式B完成识别、抓取、交付并回空夹HOME。执行器在闭合后记录原物体坐标、抓取目标及新鲜反馈，完成整程时导出`GRASP_ORIGIN.json`，绑定原计划、实发结果和抓取采集的SHA256。
2. 同一运行会话里，该选择项标为“原位空”。再次做对应数字手势时，从公共点抓取该物体，返回记录中的原抓取位置，松夹、退爪、回HOME。补回不用PALM、不跟手，不在忙碌时插入第二个任务。
3. 放回和空夹HOME全部执行完成后，软件库存才恢复。持续保持同一数字不会立即重复，需背景/无手势重新武装。软件库存不是物体存在的实测证明；实物首轮仍需观察。
4. 补回过程中、提交放回开爪前握拳取消：持物则在已知停稳节点沿实际路径退回公共点并放下、退爪、HOME，原位继续为空。尚未夹取则空夹退出。放回开爪提交之后忽略普通取消，完成退爪归位。通信/设备故障停止后续请求，不自动恢复或重发。

`pc/mode_b/restock_workflow.py`提供无通信状态适配器，输入带task_id与completed_phase；旧任务、重复阶段完成、忙碌选择和未重新武装均拒绝。原正常交付不变。此适配器尚未接入FPGA/网页桥接，不能把本机状态测试当作新板端ABI实现；filid的0x340B固定三色补料表不能直接承载模式B动态返回坐标。

## 原坐标与实体残差

返回记录分开保存：原始相机物体中心XYZ/yaw、成功抓取的固件六通道目标rad、闭合后实际反馈rad与原生端点XYZ。固件端点XYZ与桌面物体中心不是同一坐标点，不能混用。

本次返回到原始物体坐标对应的成功抓取指令，按原示教/相对规划曲线逆向返回；不重新用未经全域标定的绝对XYZ反解，也不再叠加X/Y残差或向外2mm。红块、圆柱、橡皮各自沿用原类修正，橡皮25mm局部范围不扩大。新公共点取物段另做反解。原三类审阅包是修正前离线候选；红块下降8mm及后续节拍v2已独立实物接受，橡皮/圆柱补回及取消分支仍不据此宣称实体成功。

源记录在每次抓取闭合后冻结，之后相机识别更新或物体选择映射变化不覆盖该记录。实际归还前必须确认原位置空闲。同一逻辑选择项未补回前，不能被新源点替换。退出/重启后不推测前次库存或夹持状态，需要从保存的源记录和现场重新核对。

## 公共点布置

公共点Z按物体中心计算：红块15mm，橡皮7.5mm，圆柱23mm，均放在桌面；不是承托物顶部。公共点抓取朝向由各条新轨迹给定，见`review/路线/PROFILE.json`；橡皮须按长轴方向摆放，圆柱直立。当前未接入公共点视觉识别，执行前需确认物体与轨迹的朝向相符。

**原150mm高承托物中心(285,195)，80×80mm模型占地覆盖公共点(300,200)。补回前必须移走该承托物并腾出公共点和路线。** 新规划明确记录`removed_delivery_fixture`，执行需显式`PublicAreaClearConfirmed`。这不是允许机械臂从承托物里面取物；正常交付流程仍需原承托布置。

## 离线使用

新代码不修改已发布成功联测包。原始来源、三类新路径、取消分支和仿真归档在`MODE_B_RESTOCK_REVIEW_20261029.zip`及`VERIFICATION.json`；解压后进入`review/`运行`python verify.py`。Git保留ZIP，避免重复提交整份展开的历史候选路径。

以下在项目根目录执行，每次输出使用新的目录：

```powershell
artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe -B -X utf8 scripts\prepare_mode_b_restock.py record --delivery-plan "原成功计划.json" --delivery-result "该计划实发结果.json" --selection 1 --output "新目录\GRASP_ORIGIN.json"
artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe -B -X utf8 scripts\prepare_mode_b_restock.py plan --record "新目录\GRASP_ORIGIN.json" --output "新目录\RESTOCK_PLAN.json"
artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe -B -X utf8 sim\phase3_robot\verify_mode_b_loaded_route.py --plan "新目录\RESTOCK_PLAN.json" --output "新目录\COPPELIA_VERIFICATION.json" --port 23020
```

仿真需要独占、停止中的CoppeliaSim4.10实例。复核包的Python标准库校验无需Coppelia和机器人：

```powershell
python -B docs\phase3c\mode_b_restock_20261029\review\verify.py
```

指定某个已停稳持物节点生成取消路径：

```powershell
artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe -B -X utf8 scripts\prepare_mode_b_restock.py cancel --plan "新目录\RESTOCK_PLAN.json" --at-phase RESTOCK_SOURCE_HIGH --output "新目录\CANCEL_PLAN.json"
```

取消路径需单独仿真。持物支持PUBLIC_LIFT、RETURN_BUFFER、RETURN_INNER、SOURCE_HIGH、SOURCE_DESCEND五个RESTOCK节点；空夹支持INNER_OPEN、BUFFER_OPEN、PUBLIC_HIGH、PUBLIC_DESCEND四个RESTOCK节点。只适用于相应节点确已停稳、未提交释放。运动中需停止新增提交、排空队列并取得新鲜实际姿态，再规划；不能直接倒播一个假定已完成的段。

## 后续实体入口

`scripts/run_mode_b_restock.ps1 -Plan ... -Verification ...`默认完全离线，只校验源/计划/仿真绑定，不访问串口。显式`-Move`才启用TTL，沿用COM5/115200、无自动重发、误差观察，通信/设备故障仍停止后续请求；夹爪事件有独立停留与反馈。

正常实测需同时提供`-EmptyGripperConfirmed -PublicAreaClearConfirmed -OriginalSourceVacantConfirmed -PublicObjectPlacementConfirmed`。持物取消接续则需`-HeldObjectConfirmed -StoppedPoseConfirmed -PublicAreaClearConfirmed`，空夹取消把HeldObjectConfirmed换为EmptyGripperConfirmed。启动状态不匹配会拒绝，当前不支持严格在线几何分支；不会从未知姿态自动回HOME。原版归档的实测前标志保持；当前红块v2已完成实体接受，入口和独立接受证据见成功资料包。

正式联测仍需队友将动态源记录/任务ID、选择项库存、手势重新武装、段/事件提交与完成、释放承诺点接入模式B执行器。先无机械臂核对样本和事件，再测公共点抓取残差与三类实物补回。


红块两倍补回已获实物接受；进一步参考filid并定位Windows20ms节拍开销的独立候选，见`CONTINUOUS_SESSION_CN.md`。当前v2已获实物全程正常接受，130.643542秒；旧计划/报告的待反馈字段保留原始时序，最终接受由独立ACCEPTANCE证明。


原生算法/本机执行脚本依赖numpy/scipy、CAD及开发机历史路径/fixture；Git中的源代码可审阅，但不能据此直接在新电脑操作机械臂。跨电脑先使用上述标准库离线资料包核对，再部署运行环境和新场景。FPGA/NPU/网页自动补回桥接仍待联测。
