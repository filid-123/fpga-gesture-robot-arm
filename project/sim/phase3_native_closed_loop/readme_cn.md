# NativeMotion Coppelia 适配层

对应 S2/S4 ABI 0x3202/0x3403。最终包与准确板上命令见 ../../docs/PHASE3_NATIVE_MOTION_BOARD_GUIDE_v0.1.0_CN.md。原 sim/phase3_closed_loop 与冻结 S8 依赖不改动；本目录 adapters 的驱动和 tray ABI 识别优先于冻结版本。

物块仍为 16 mm，以 base_link_visual 的世界最低点为共同支撑平面。prepare_scene 临时添加桌面、物块和桥接脚本，cleanup 恢复初始状态；.ttt 不被覆盖。使用停止运动学、位置 IK、2 mm TCP 距离附着；不模拟接触动力学。11 个软件闭环任务通过，正常/取消/掌心超时路径未检出末端与支撑面相交，锁定关节的到位故障注入有相交，不能用故障路径指导实物。

board_loop --repeat 1..3 对不同物品执行同次 BIT 初始化后的连续任务；--auto-palm 为显式测试注入，默认不开启。board_loop 正常结果快照在 RELEASE/OFF 后读取，避免 S4 owner 下写 ARM.FB_SNAPSHOT；故障持有 owner 时只保留现场。上述脚本的新 BIT 板测 NOT_RUN。

已有 Python 环境可直接使用 requirements-pc.txt 的版本。Windows ZMQ/串口执行不保证 50 Hz；场景成绩与 FPGA 时序、真实感知和实物成绩分别记录。原 metrics_tools 继续将这些数据标记 SIMULATION。
