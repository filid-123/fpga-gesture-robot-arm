# 系统架构与数据流

## AI PC 与硬件分工

Windows 原生 AI PC 提供网页配置、B 模式普通 RGB 检测/顶面分割、标定定位、逆解和路径规划。B 视觉对象为红块、橡皮和小圆罐；三类物体中心工作区 X=490～690、Y=215～355mm，物体边界、姿态、碰撞和路径检查仍独立生效。

PYNQ-Z2 的 PL 负责 OV5640 DVP 采集、Locator、同帧 ROI、分类/手势事件、任务与控制权状态机、A 五次轨迹、B 原生轨迹 RAM 播放、实时插值和 TTL 输出/反馈。B 采样周期按阶段为 20/40ms；100MHz 内部逻辑处理不是声称 100MHz 舵机控制。PC 上传有限路径及配置，PL 定时执行；PC 不逐周期下发关节目标。

当前两端实际传输是本地 XSDB/JTAG 的 AXI MMIO，PS 提供 Zynq 硬件/初始化支持。网页的 localhost HTTP 是 AI PC 内部配置接口，不应写成已验证的 PC↔板卡 Ethernet 链路。

## 两种模式

- A：OV5640 像素→PL 定位/分类→数字选择固定红黄蓝槽→任务 FSM→轨迹→TTL 执行；PALM 确认交付，FIST 普通取消，公共点补回。
- B：RGB 帧→PC 本地检测/分割→标定桌面坐标→受限 IK/碰撞检查→路径与描述符上传/回读/COMMIT；数字事件启动，PL 播放、夹爪事件和交付/取消。两种模式共享红块库存，各自保留 HOME。

配置仅在真实静止状态及控制权允许时提交。模式切换使用固定空夹爪 HOME 过渡；运行中禁止改映射。异常回读/传输作废 RAM 镜像复用凭据。复位清除有效状态，必须重新配置、回读和 COMMIT。

## 原始图纸与说明

- [PL 总图 SVG](../project/docs/pl_architecture/01_pl_top.svg) / [可编辑 DrawIO](../project/docs/pl_architecture/01_pl_top.drawio)
- [视觉链](../project/docs/pl_architecture/02_vision.svg)、[任务链](../project/docs/pl_architecture/03_task.svg)、[运动链](../project/docs/pl_architecture/04_motion.svg)、[HDMI](../project/docs/pl_architecture/05_hdmi.svg)
- [p4 原生轨迹设计与限制](../project/docs/mode_ab/native_routes_p4.md)、[wrapper 层级对应](../project/docs/mode_ab/pl_wrappers.md)

图纸与数字均来自指定基线，本次整理不改变拓扑。当前 p4.1 已用户实测验收通过，具体任务覆盖、仍未形成的量化统计及问题边界见 `docs/field_acceptance.md` 与 `report/submission_status.md`。
