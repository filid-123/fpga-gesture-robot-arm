# AB v0.1.0-p4：Giao 原生快速轨迹与全取物框

启动修复标识：`startup_route_map_p4_1`（CheckOnly 应显示此 hotfix_id）。

补丁标识：`native_giao_full_workspace_p4`；TASK ABI：`0x340E`；B 轨迹 RAM ABI：`0xB001`。
必须使用本版完整目录及同包 BIT/HWH/XSA。旧 p3/ABI340D 软件与位流保留，不混装。

## 输入与范围

- 已审查同步 Giao 新分支 `codex/mode-b-full-workspace-20261030` 的
  `3d66aeb8d33b42abf8d82da3c71b1e6276a9a32a`；`dev/Giao` 的快速转运数据仍为
  `1d3fa84de81d05b846d2b9f30998e16a84f4eee3`。更新的是规划/准入策略，冻结检测、顶面模型和普通 RGB 标定不变。
- 首版仍为红块、橡皮、小圆罐。取物框按**物体中心**约束：X=490～690、Y=215～355 mm。
  删除历史 25/150 mm 锚点半径门槛；物体轮廓可以跨过画框边线。RGB 预览投影绘出桌面方框。
- 按最新策略沿桌面坐标轴摆正；红块忽略小角度角点噪声，橡皮保留长轴 X/Y 选择，圆罐不跟随顶面 yaw。
  反解必要时允许最多 25° 附加倾角和最多 15 mm TCP 升高；这是工具姿态调整，不改变物体坐标或桌面高度。
- 红块源位采用新下探 12 mm；公共点补回仍保留独立的原红块额外 8 mm，不叠加源位下探。
  A 固定红槽使用已验证的 A 固定路径，共享红块库存继续联动。
- 关节限位、桌面/自身/载荷碰撞、持物倾角、视觉尺寸/形状和单实例要求继续执行。圆罐圆形残差阈值仍为 9%。
  “中心在框内”不代替这些检查，也不是连续全域实物成功率证明。

## 路径与速度

A 继续原 1320/66、20 ms、UQ32 五次 P2P 合同。B 抓取/交付不再拆为逐段重新起停的 A 五次曲线：
FPGA 接收完整 Q16 阶段样本，在 PL 内定时、插值、切换速度、执行夹爪事件和取消返回。

- 三类名义中心轨迹的 12 个运动阶段，六轴 Q16、阶段周期和 SPD/ACC 均逐项对照 Giao 原包。
- 抓取前三阶段保持 40 ms；转运/交付/退爪阶段保持 20 ms。四个快速阶段为 BUFFER、PREPLACE、RETREAT、RETURN_CLEAR。
  红块/圆罐快速 SPD=2640，橡皮快速 SPD=3960，ACC 上限 254；其他阶段保留各自发布值。
- 交付和退爪使用 Giao 的类别专属修正几何，避免把三类 PLACE 都改成同一个工具点。
  现场交付到手，不设置实体承托台。65 个手掌位置、PALM 500 ms 确认和 FIST 普通取消规则保留。
- 相机源位变化时，保留已检查的源位关节弦段及阶段时钟，重新生成连接到 INNER 的受限五次连接段；
  逐样本重新检查 Q16 和串口量化值。名义 Giao 输入保持原样，适配输入不冒充队友实测原始轨迹。
- 红块、橡皮、圆罐名义运动段分别为 22.62、15.00、23.10 秒。夹爪等待、PALM、规划、上传和通信另计。
  这些是轨迹时间，不是现场任务耗时或实物速度测量。
- T106 夹爪等待恢复 Giao `execution.json` 的行程公式：`abs(目标-起点)×4096/(2π)/spd+1` 秒。
  正向与取消逆退共享阶段计时，取两者较慢速度计算；不能用固定 0.3/0.8 秒代替。等待后仍保留实时反馈失联保护。
  因此实际总用时还包括较长的夹爪等待，不能把上述 15～23 秒当作完整抓放总时长。
- 公共点补回继续已检查的原位恢复策略及 A 的重计时合同；Giao 本次发布的四段快速策略针对抓取交付，
  不把它冒充为新的补回实测结果。

## FPGA 与写保护

- `0x43C20000` 为新的 B 配置窗口，经实际顶层 `s_axi_route` 和 S4 ownership window 连接；
  原 arm/plan/task/vision 窗口地址不变。AXI 仅上传配置，不能在此触发逐周期运动。
- 六个 2048×18 位真双口 BRAM 保存六轴 Q16 偏移，六个 32 位基准无损恢复原 Q16。
  192 字描述符保存三档、16 阶段的地址、样本数、周期和正/反向速度。
- 上传只在静止 B WAIT_PATH 中进行；每个字回读比对后 COMMIT。开始、提交、运行、暂停均受硬件写锁。
  同一 owner 已确认且仍 committed 的相同镜像可复用；异常回读或传输会丢弃复用凭据。
- 原生格式同时要求 `flags[7]=1` 和 `profile=0`，避免误认共享 A 红块原有的等待标记。
  六轴软限位、最后门控、D5、500 ms 反馈保护和 500 ms 下游阻塞保护保留。
- T102 的 B SPD/ACC 与 T106 类型在 MAP 前锁存，发送期间不会被后继阶段更改。A 的原模板与查询模板保留原地址。
- 原生 Q16 恢复、左右乘积和舍入求和分级寄存，避免两次乘法与求和挤在一个 100 MHz 周期内。
  首样本内部准备增加两个时钟（20 ns），生产样本的 20/40 ms 周期及数值保持不变。

## 操作

```powershell
Set-Location D:\FPGA_Projects\Gesture\deliverables\gesture_mode_ab_v0_1_0_20261030_p4
powershell -ExecutionPolicy Bypass -File .\start_mode_ab.ps1 -CheckOnly
```

确认输出 `native_giao_full_workspace_p4`。人员在场，按 `hardware_setup.md` 检查实际姿态、物品、D5 与现场停止条件，先查询：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_mode_ab.ps1 -MonitorOnly -Seconds 15
```

查询通过后按同一入口启动正常会话。网页锁定 A/B 与 RGB 判定独立；只有任务启动才要求所选物品的新鲜视觉和路径通过。
模式仅在空夹爪 HOME 切换，并包含已确认的固定过渡。任务仍由 FPGA 数字手势启动；网页没有直接运动按钮。

网页显示配置禁用条件、规划进度、视觉测量/坐标、错误阶段与原因，以及原生轨迹硬件错误的中文说明。
规划输入在开始求解时即写入 `plans/<id>/frame.json`、`source_request.json`；失败也保留输入，便于定位。

本机 `.venv-ab-rocm` 复用原 p1 的已验证环境，不删除原目录。ZIP 不含 Python 环境和现场 runs；异机先运行
`setup_mode_ab.ps1 -VerifyModels`。Windows 原生 ROCm GPU 检测和分割、CPU 标定定位规划；没有 CPU 推理静默回退。
NPU 仍是未通过的实验后端，不声称已在 NPU 执行。

## 证据与恢复

`evidence/validation_summary.json` 列出实际通过项；`evidence/implementation` 绑定同次构建、资源、时序和 BIT/HWH/XSA。
`board_evidence/mode_ab_p4` 保存选定 PC、真实 RTL、全框与 Giao 对照证据。
物理成功率、连续全域抓取、真实总耗时、夹持/防滑和停止距离均为 **NOT_RUN**。
原有 UART 间歇问题仍 OPEN，没有通过加大超时掩盖。

回退使用完整原 p3 目录或原 A v0.14.0 包，连同其匹配的软件和位流；本包 `rollback/p3_a8` 保存旧硬件与绑定摘要。
不要用本版 Python 控制旧 ABI340D BIT，也不要用 p3 旧 Python 控制 ABI340E。

原生批量写的列表语义依据 [AMD XSDB mwr 文档](https://docs.amd.com/r/2024.2-English/ug1725-xsdb-reference-guide/mwr)。


最终 a14：30657 LUT、25196 FF、117.5 BRAM tile、56 DSP；WNS/WHS +0.013/+0.011 ns，TNS/THS=0；115 CDC 全 safe。
DRC 0 errors；新增 REQP-1839 仅限六路易失路径 RAM 的写许可，已核对 COMMIT 写锁及真实根模块异步复位测试。
复位会清除路径/后端配置与有效标记；不续跑旧任务，不跨复位复用 RAM 镜像。重新启动完整入口，完整装载、回读和 COMMIT 后才能执行。

## p4.1 启动修复

四次现场启动在首次遥测读取 0x43C20008 被 XSDB 拒绝。原 loadhw 只注册四个旧 PL 页，漏了新路径页；
现补齐 0x43C20000～0x43C20FFF，并在 JTAG_READY 前核验路径 ABI B001。原访问保护、BIT/HWH/XSA、模型、路径和速度均不变。
上次错误日志注明未完成 PS/PL 恢复，首次重试前按原现场流程断电复位板卡。继续使用本 p4 目录；
修正版完整压缩包为 gesture_mode_ab_v0_1_0_20261030_p4_1.zip，原 p4 ZIP 保留。仅运行3项启动映射校验和封包入口检查，实物启动修复复测为NOT_RUN。
