# 当前 p4.1 已实测通过

2026-11-01，用户确认p4.1 已通过现场任务验收。当前 `0.1.0-p4.1` 登记为 **USABLE_USER_ACCEPTED / PASS_USER_CONFIRMED**，是已验收的可用与回退基线。此前 `project/` 封存材料中的实物 NOT_RUN 是封包时记录，不能再当作当前状态。

版本身份保持：patch `native_giao_full_workspace_p4`、hotfix `startup_route_map_p4_1`、TASK ABI340E、route ABI B001、a14 同次 BIT/HWH/XSA。原 p4_1 ZIP 和 SHA256 `c29a4f659c341646d2354006435401aa5458eb135630601a7b1077b9ba7b8adf` 不变。

精简证据为 [board_test_20261101.json](../report/acceptance/board_test_20261101.json)，源自开发分支提交 `633a4e1441ce9b54e95a25ea93b46b8fbc6329e0`；[来源记录](../report/acceptance/provenance.json) 记录原始哈希与脱敏副本哈希。原始现场遥测、图像和 session_result 没有上传或改写。

六次既有会话共24,446条遥测，FPGA fault均NONE，反馈错误/超时、native_route_error最大值均0。PL完成计数沿记录：

| 已记录的程序完成 | 次数 |
|---|---:|
| A交付 | 5：红块2、蓝块3 |
| A补回 | 蓝块3 |
| B交付 | 6：红块2、圆罐4 |
| B补回 | 圆罐3 |

日志包含A→B和B→A固定HOME过渡。用户随后逐组确认：A交付5/5、A补回3/3、B交付5/6（失败1次在这6次之中）、B补回3/3；这组17次执行物理成功16次，成功率94.117647%。[任务复核单](../report/acceptance/task_outcomes_review_20261101.json)记录操作者复核结论；没有补造失败对应的会话或物品标签。最新 `ab_20261031_233419` 会话记录交付5、补回4，其后发生JTAG异常，不应将整场退出改为正常。

验收范围保留以下事实：所核对六次会话未记录橡皮完成交付，不扩大为三类逐项全部验收或连续全工作域验证；取消计数含选物拒绝，不当作实物归还成功次数；本组回溯任务成功率及通信RTT已补齐，见[指标复算](metrics_recovery_20261101.md)；用户随后从另一角度重新查看实物视频，人工计时手势已进入摄像头视野至机械臂首次可见运动为0.62秒（620ms），撤回此前2.4秒读数，见[视频计时复核](../report/acceptance/video_response_review_20261101.json)。逐次响应计时序列及夹持/防滑、停止距离专项仍待补充。

两次任务完成后出现XSDB/JTAG Invalid context，PS/PL恢复未确认及原断电复位要求继续保留；JTAG问题OPEN，历史UART间歇问题也未因此宣布修复。NPU编译仍未通过，实际运行保持Windows原生ROCm GPU感知与CPU定位/规划。

本次只同步既有验收事实和发布措辞，没有重新访问相机/JTAG/串口/机械臂，也没有改动代码执行行为、RTL、模型、轨迹或速度。软件归档中的历史证明和本次新增验收记录分别保留。
