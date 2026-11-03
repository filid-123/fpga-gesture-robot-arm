# 接口和联测顺序

## 分工与模式边界

模式A保持filid固定物槽和1红/2黄/3蓝任务映射。模式B采用独立profile：1红方块、2橡皮、3圆柱，HOME完成后视觉给动态取物坐标。两模式可共用缓冲/交付逻辑，不共用固定取物坐标、类别编码或旧关节残差。

PC负责NPU视觉结果绑定、目标选择、局部实物补偿、完整路径/反解、全段碰撞与限速检查、任务阶段和归还源点。FPGA/PS负责接收已审核任务、周期轨迹执行、事件与反馈、确认/取消/超时/断链。新模式B整任务报文需队友确认并实现，当前JSON是交接表示，不能直接冒充已有PATH_SUBMIT协议。

正式目标仍为PC交稀疏关键点/段参数、PL插补，PC密集样本作黄金参考。当前实体PC执行的是PCHIP/五次时间律的原生T102采样流；旧PL梯形插补不能直接等价复现。队友应先选定兼容的段表示/插补与定点舍入，用本包逐点比对；若改变插补，需重新仿真并实体回归。旧32段限制应按新版适配器分块，块边界保持速度、任务ID和事件，不能截断完整任务。

## 数据输入

`DYNAMIC_INPUT_EXAMPLE.json`是接口草案和已成功坐标例子；不是在线已有二进制报文。必须绑定模式profile、task_id、帧ID/时间、标定哈希、物体尺寸/朝向、源中心与承托面中心。相机改变后旧标定/残差不能沿用；NPU实际运行证据单独记录。算法入口见快照`scripts/prepare_mode_b_empirical_transfer.py:prepare(capture_path,request_path,speed_multiplier)`，经`prepare_mode_b_ttl_full_trial.py`分派。原始hash链含本机路径，需要重新部署解析与绑定，不能只改路径字符串而保留旧hash。

归还目标使用任务开始时冻结的原始动态源点，不能用补偿后的指令位置，也不能用取消时新识别到的其他物体。每条反馈要关联task_id、段号、样本号、时间戳，区分发送成功/设备接收/实际完成。`Workflow.event('DONE')`只是意图模型，调用方需先核验对应动作的完成证据；CLOSE的DONE不能仅靠串口写成功就当作已夹稳。

## 坐标、执行参数

五个运动轴+独立夹爪六通道，不是六自由度末端任意位姿解。T102字段`base,shoulder,elbow,wrist,roll,hand`全部rad；T106夹爪`cmd`为rad；T122 HOME参考为deg；只读T105查询不是运动。PowerShell大小写不敏感，`T`和`t`不能当普通同名属性读入，参考`roarm_state_json.ps1`处理。

TTL：COM5为本机例子，115200/8N1，无流控，DTR/RTS=false；每条JSON后LF。PC不自动重发运动。入口/下降/抬升40ms，后半程20ms，具体每段样本以phase_map为准。3倍拾取spd480/acc180；3倍后半程spd1980/acc254（原297被254封顶并同步重计时），不能自行发送acc297。T102 spd单位为舵机steps/s，acc为100steps/s²，不是rad/s或轨迹倍率。

张开1.586rad/spd300/acc20，收纳闭合3.10rad/spd100/acc20，物体闭合见README。当前监督试验残差仅记录；通信失败/设备故障仍阻止后续请求，不重发，不承诺软件退出等同物理急停。夹爪停留按`abs(目标rad-当前rad)*4096/(2*pi)/spd+1s`估算并读反馈，不能删除后直接抬升。

名义运动时间只统计采样段，实际还含夹爪停留、状态查询与阶段等待；最新橡皮29.02s名义、119.575s实际，不能把后者写成29秒任务。实发时间戳保存在RESULT.json；首条与末反馈时间不等同每条采样周期精确达标。

## 状态映射

| 包内动作/事件 | 正式意图 | 后续条件 |
|---|---|---|
| 已知路径进入低HOME | HOME→WAIT_VISION | 空夹、已知状态、任务未持物 |
| DIRECT_PREGRASP + OPEN_HIGH | APPROACH_CORRECTED | 动态目标有效、张开后反馈 |
| DESCEND + CLOSE_SOURCE | DESCEND→CLOSE | 源点不变、闭合与夹持证据 |
| LIFT | VERTICAL_LIFT | 持物确认，禁止仅用写成功代替 |
| INNER_HOLD→BUFFER→PREPLACE | INNER_HOLD→BUFFER→PRE→PRE_WAIT | 到位/净空；缓冲为持物停留，不放下 |
| PLACE | DELIVER | PRE至少2s且PALM连续500ms |
| RELEASE | RELEASE | 支撑/交付许可、提交释放后禁止自动撤销取回 |
| RELEASE_CLEARANCE→RETREAT | RELEASE_CLEARANCE→HAND_CLEAR | 松开、向外8mm退爪与上撤 |
| RETURN_CLEAR→INNER_RETURN→RETURN_LOW_HOME + PARK_CLOSE | RETURN_CLEAR→INNER_RETURN→RETURN_HOME | 空夹、清空当前任务后等待下一帧 |

filid基准commit85b4bcaf000a8b69c50ca6d65bbd88b07afe4735：INNER=(585,225,90)，B=(360,200,160)，中档PRE=(350,215,180)，H=(285,195,175)，H_CLEAR=(285,195,195)。这些是link5局部(0,0,115.428)的工具参考点，H的175不是承托150，也不是各物块中心。导出计划已按各物体附着和尺寸重求PLACE；禁止直接把H写成物块中心目标。

## 建议队友按此顺序验收

1. PC离线verify三类数据，读HOME/参数/阶段，确认独立模式Bprofile。
2. 无机械臂，板端输出三类完整样本/事件，导出接受握手的向量并比对。另测40/20ms节拍、背压、不重复及跨块边界。
3. 按BRANCH_TEST先软件事件注入，再板端空载，再实体受控验收；已知静止节点才接续归还轨迹，运动中先建立停稳状态并重规划。
4. 接入NPU真实帧与任务绑定，明确视觉过期/目标切换处理；最后用已验证类速度实体联测，新速度另验。

本包没有实现新RTL/PS协议，不改变现有ModeA。待交接审核项是新版段表示、事件ID/帧格式、完成与夹持/支撑判定信号、取消路径生成及实际板端时序。
