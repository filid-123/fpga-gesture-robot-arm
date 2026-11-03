# 工程进度与状态日志 (PROJECT_LOG.md)

> **更新时间:** 2026-08-26
> **当前阶段:** Phase 2-L1 v16/v3与既有Phase 2-L2功能RC保持封存；同帧128×128 ROI完成一稿封存
> **当前状态:** ✅ Phase 1 | ✅ Phase 2-L1 v16/v3 | 🟢 Phase 2-L2功能RC | 🟢 同帧ROI Functional RC Draft 1

> **恢复说明:** 2026-08-11 在清理旧文件末尾 NUL 字节时发生脚本异常，本文件曾被
> 意外截断；现已根据本次会话开始时读取的日志内容恢复、去除 NUL，并将重复/过期
> 状态收敛为下面的单一事实记录。RTL、模型与 Vivado 工程未受该异常影响。检查同时
> 发现 2026-07-31 至 2026-08-01 的旧 ZIP 均为 22-byte 空包；备份脚本现已修复并加入
> 文件清单、暂存数量、ZIP 条目数量和文件大小校验，新快照已验证可用。

---

## 1. 里程碑进度表 (Milestone Tracking)

| 编号 | 里程碑名称 | 关键交付物 | 状态 | 完成度 |
|---|---|---|:---:|:---:|
| **M0** | 架构与环境建基 | 规范文档、目录、AI Prompt、备份机制 | 🟢 完成 | 100% |
| **Phase 1A** | 测试图像与黄金向量 | 输入、权重、描述符、逐层 Golden | 🟢 完成 | 100% |
| **Phase 1B** | CNN RTL 与验证 | Conv/Pool/Dense、Requant、FSM、TB | 🟢 完成 | 100% |
| **Phase 1C** | AXI 与 PS 灌图 | 模型/图像加载、启动、状态、结果 | 🟢 板测成功 | 100% |
| **Phase 1.5** | 多图离线验证 | 历史 8 类测试与当前 4 类生产模型验证 | 🟢 完成 | 100% |
| **Phase 1S** | 稳定化收口 | ABI 1.0、active model package、全网回归 | 🟢 完成 | 100% |
| **Phase 1R** | V1.0 封存 | Bit/HWH、板测证据、实现报告、校验快照 | 🟢 完成 | 100% |
| **Phase 2-L1** | USB/PS 独立 Locator 闭环 | 128×128 输入、定位 IP、PS bbox、现有分类级联 | 🟡 ROI已冻结，时序新版板测/精度待签 | 85% |
| **Phase 2-L2** | OV5640/PL ROI 数据流 | next-SOF功能RC及同帧128×128 BRAM ROI一稿封存 | 🟢 Functional RC Draft 1（DVP实测例外） | 100% RC |

---

## 2. 当前硬件与模型事实

- **FPGA:** PYNQ-Z2 / XC7Z020-1CLG400C。
- **Vivado Board Part:** `tul.com.tw:pynq-z2:part0:1.0`（官方 Xilinx Board Store）。
- **当前已实现时钟:** FCLK0 50 MHz、FCLK1 100 MHz；Phase 2-L1 v16/v3布线后全局
  WNS/WHS `+0.124/+0.024 ns`。
- **当前 AXI 地址:** CNN `0x4000_0000/4 KiB`；LED GPIO `0x4120_0000/64 KiB`。
- **Phase 2-L1实现资源:** 13,392 LUT、10,443 FF、56 BRAM Tile、22 DSP、4 I/O；
  100 MHz Locator域已经实现及板测，不能用该报告外推后续L2模块。
- **当前 CNN 核:** 描述符调度的 `generic_conv3x3` / `generic_maxpool2x2` /
  `generic_dense`，不是旧的 `mac_array_32ch` 主通路。
- **当前L2 Locator卷积并行方式:** 8输出通道lane与PL Top-1已并入并封存为功能RC；
  同帧128×128 ROI候选继续复用该基线。
- **激活/权重:** UINT8 激活、INT8 权重、INT32 累加、INT32 Bias、定点 Requant。
- **active model:** `background / fist / mute / palm` 四类，输入 `1×32×32 UINT8`。
- **生产模型入口:** `model_package/active/`；权重 9838 个 32-bit word、描述符
  64 个 32-bit word，所有产物由 SHA-256 绑定。
- **当前封存摄像头入口:** USB摄像头接PS；独立L2 OV5640时序RC已完成精确哈希板测并功能封存。
- **OV5640:** 已确定OpenSOC OV5640_V1.2，3.3 V、8-bit DVP、20针2×10/2.54 mm并口版；
  XDC/BD与JA/JB映射已冻结，ID/PGM/camera→Locator前端板测通过。
- **Phase 2-L2功能RC:** 已完成YUV422抽Y、1024×29异步FIFO、固定VGA到128×128
  letterbox、独立32 KiB camera输入ping/pong、AXI4-Lite/SCCB、帧发布IRQ、新BD/XDC
  与8-lane Locator；ABI `0x00000402`新增PS描述符、next-SOF nearest ROI、分类器ROI BRAM/MUX
  和完整PS闭环；精确新哈希已完成implementation/bitstream及7/10 ROI→分类器板测并封存。
- **Phase 2-L1 定位架构:** USB 原始帧保留在 PS；PS 生成 128×128 UINT8 输入；
  独立 `locator_top` 输出 raw signed INT32 `5×16×16` CHW map；PS 解码 bbox 并
  对同一原始帧裁剪/缩放，再送入现有 `gesture_top_0`。
- **Phase 2 文档基线:** `docs/locator/PC_MODEL_FPGA_HANDOFF_CN.md` v2.1.2 与
  `docs/locator/LOCATOR_PHASE2_L1_INTERFACE_DRAFT_CN.md` v0.3.2。当前只冻结架构和
  静态接口；训练数值、最终寄存器规范和 MAC 档位仍待冻结。骨架绝对 AXI 地址已选定
  并写入 HWH，但在最终 RTL 规范签字前仍属于联调契约。
- **Phase 2-L1 骨架状态:** 独立 `locator_top` 已实现 AXI4-Lite 控制、模型/描述符
  BRAM、CRC-32/ISO-HDLC 提交、输入/输出 ping-pong 所有权、逐缓冲 Frame ID、
  sticky first-fault、IRQ 和确定性数据面 Stub；隔离 Block Design、HWH 地址、中断、
  50/100 MHz CDC、PS 批量 MMIO 驱动和 Stub Notebook 已完成。首版 Stub bitstream
  因 `PCW_FCLK_CLK1_BUF=FALSE` 作废；第二版虽启用 FCLK1，但两个 `proc_sys_reset` 的
  `aux_reset_in` 接常量 0 且被传播为 `C_AUX_RESET_HIGH=0`，使 GP0/Locator 永久复位，
  同样作废。第三版 reset-fix HWH 已冻结为两个复位域 `C_EXT_RESET_HIGH=0`、
  `C_AUX_RESET_HIGH=1`，并完成综合、实现、bitstream 静态签核和 Stub 上板回归。
  在同一接口内已接入v12五层真实定位CNN及PS bbox解码；候选bitstream完成静态HIL，
  USB实时工程闭环8次运行无硬件stall/drop。分类ROI策略已经冻结；Locator生产预处理、
  PS时序新版板测和受控精度仍待签。

---

## 3. 当前交付物与检查清单

### 架构与规范

- [x] `AI_INSTRUCTIONS.md`
- [x] `docs/architecture_plan_zh.md`
- [x] `docs/timing_and_cdc_spec.md`
- [x] `docs/register_map.md`（ABI 1.0）
- [x] `docs/layer_descriptor_spec.md`（8-word 线格式）
- [x] `docs/ov5640_purchase_and_integration.md`
- [x] `docs/camera/opensoc_ov5640_v1_2_hardware_baseline_cn.md`
- [x] `docs/camera/phase2_l2_frontend_design_cn.md`
- [x] `docs/locator/PC_MODEL_FPGA_HANDOFF_CN.md`（Phase 2 总体基线 v2.1.2）
- [x] `docs/locator/LOCATOR_PHASE2_L1_INTERFACE_DRAFT_CN.md`（接口草案 v0.3.2）
- [x] `docs/locator/locator_register_map_draft.md`（骨架相对地址与联调绝对地址）
- [x] `docs/locator/phase2_l1_vivado_platform.md`（隔离 BD、时钟、地址与综合报告）
- [x] `docs/locator/phase2_l1_board_bringup.md`（FCLK1 前置条件与分阶段安全板测）

### 模型与黄金向量

- [x] `model_package/active/package_manifest.json`
- [x] `model_package/active/weights_all.mem`
- [x] `model_package/active/layer_descriptors.mem`
- [x] `model_package/active/quantization_manifest.json`
- [x] `model_package/active/golden_vectors/`（8 个生产样本）
- [x] `scripts/verify_model_package.ps1`

### RTL 与总线

- [x] `rtl/top/gesture_top.v`
- [x] `rtl/axi/axi_lite_slave.v`（AW/W 独立握手、WSTRB、SLVERR）
- [x] `rtl/cnn/cnn_core.v`
- [x] `rtl/cnn/cnn_core_fsm.v`
- [x] `rtl/cnn/cnn_desc_mem.v`（PS 可写、CNN 同步读）
- [x] `rtl/cnn/generic_conv3x3.v`
- [x] `rtl/cnn/generic_maxpool2x2.v`
- [x] `rtl/cnn/generic_dense.v`
- [x] `rtl/cnn/weight_bram.v`
- [x] `rtl/cnn/cnn_act_bram.v`
- [x] `rtl/preproc/input_bram.v`
- [x] `rtl/locator/locator_top.v` 与 AXI4-Lite 控制面
- [x] Locator 参数/描述符 BRAM 与 CRC-32/ISO-HDLC `MODEL_COMMIT`
- [x] Locator 输入/输出 ping-pong、逐缓冲 Frame ID、release 与 sticky 错误语义
- [x] Locator 确定性 Stub 数据面（仅用于接口联调，不是定位 CNN）
- [x] Locator v16 5层INT8 CNN、Requant/Pool计算核与逐层黄金向量
- [x] Locator v16 8输出lane候选：保持外部CHW ABI，4组整网逐层bit-exact，
  prime/prefetch时序修复、Locator OOC及L2全顶层综合通过
- [x] Phase 2-L1 隔离 Block Design、骨架绝对地址、AXI INTC 与 HWH
- [x] PS 端批量 MMIO 驱动、模型 CRC 提交、输入/输出 ping-pong 与 Stub Notebook
- [x] Phase 2-L1 reset-fix 独立 bitstream 与 Stub 上板回归
- [x] PS 端可配置 128×128 letterbox、5×16×16 CHW int32 Top-1/bbox 解码、坐标
  反变换和显式同帧 bbox 裁剪接口（算法参数均为必填项，无生产默认值）
- [x] Phase 2-L2 camera前端RTL：YUV422抽Y、1024×29异步FIFO、VGA到128×128
  固定letterbox、独立camera输入ping/pong、SCCB、AXI控制/Frame ID/release/IRQ
- [x] Phase 2-L2 OpenSOC OV5640_V1.2 20针定义、3.3 V电气边界及PYNQ-Z2 JA/JB接线冻结
- [x] Phase 2-L2新XDC、XCLK/SCCB读ID/初始化表、Block Design集成和PL后续帧ROI
- [x] Phase 2-L2 implementation、新bitstream及旧候选ROI→分类器9/10闭环
- [x] Phase 2-L2新时序哈希10迭代短板测完成，闭环7/10
- [ ] 示波器可用后替换DVP临时输入窗口并作最终无例外时序签核
- [x] USB 实时帧到 Locator Stub 及现有中心裁剪分类器的有限板端回归
- [ ] 真实 Locator 输出 bbox 到同帧分类的端到端精度/延迟验收（等待模型、scale、阈值）
- [x] Locator激活bank与8输出lane并行MAC的100 MHz候选架构重构（仅分支OOC）
- [x] 将8-lane Locator接入Phase 2-L2全顶层并完成综合
- [x] 完成Phase 2-L2实现后时序签核、bitstream和精确新哈希ROI板测

### 验证

- [x] AXI AW-first / W-first 错拍握手检查
- [x] 非法地址/忙时写入 SLVERR 与 ERROR_STICKY 检查
- [x] START overlap、BRAM write overlap 检查
- [x] FSM watchdog 超时检测
- [x] Soft Reset 与 AXI 从机隔离检查
- [x] C1/P1/C2/P2/C3/P3/FC1 逐字节 Bit-Exact
- [x] FC2 `Class ID=1`、`max_logit=6024` Bit-Exact
- [x] Vivado 2026.1 OOC 综合：0 Error、0 Critical Warning；63 条普通 Warning 已分类
- [x] PYNQ-Z2 Board Part、BD、地址与 XDC 平台核对；完整顶层综合 0 Error、
  0 Critical Warning、IP 无锁定/过期、严重 DRC 为 0
- [x] Locator CRC 标准向量：`"123456789" -> 0xCBF43926`
- [x] Locator AXI/CRC/双缓冲/Frame ID 自检回归通过；含 AW-first、W-first、
  非法访问、START overlap、忙时模型写、双输出占满、原子 release、Soft Reset、
  bad CRC、bit-exact Stub 输出与全局 watchdog
- [x] Locator 骨架 Vivado 2026.1 OOC 综合：0 Error、0 Critical Warning；
  100 MHz WNS `+3.785 ns`、WHS `+0.252 ns`、TNS/THS `0`
- [x] Locator 骨架 OOC 资源：736 LUT、1018 Register、3 BRAM Tile、0 DSP；
  该数字不包含最终 5 层定位 CNN、BD 和 PS7
- [x] Phase 2-L1 HWH 六段地址与中断元数据自动核对通过；分类/GPIO 地址保持不变
- [x] Locator PS 驱动与前后处理共 16 项 PC 单元测试通过：little-endian/CRC、输入
  打包、双缓冲 Frame ID、bit-exact Stub、FCLK/HWH 门禁、CHW int32 解码、Top-1、
  letterbox 坐标反变换、显式 bbox 扩边/方形化/裁剪
- [x] Phase 2-L1 全顶层综合：0 Error、0 Critical Warning；50/100 MHz setup WNS
  `+2.558/+3.577 ns`，全局 hold slack `+0.041 ns`，未约束内部端点和无时钟寄存器为 0
- [x] Phase 2-L1 CDC：FCLK0↔FCLK1 活动时序路径 0；15 条 CDC 均为 `Info/ASYNC_REG`；
  AXI Clock Converter bus-skew 全部 MET，最小报告 slack `+29.303 ns`
- [x] Phase 2-L1 骨架全顶层综合资源：13,941 LUT、11,492 Register、40 BRAM Tile、
  18 DSP、4 I/O；包含现有分类器和高性能 SmartConnect，不包含真实 Locator CNN
- [x] reset-fix Phase 2-L1 Bitstream 上板回归：Locator 两帧 bit-exact、IRQ、分类
  HIL 8/8、GPIO 回读全部通过
- [x] Phase 2-L2 camera RTL 7项自检、Python 9项单元测试、Locator 4组黄金向量通过
- [x] Phase 2-L2全顶层综合：18,205 LUT、15,288 FF、79.5 BRAM、20 DSP；
  WNS/WHS `+0.019/+0.041 ns`；CDC 0 Critical，仅2条异步FIFO Gray指针Warning

### 摄像头与预处理

- [x] `rtl/camera/sccb_master.v`（100 kHz、16-bit寄存器地址、读写及ACK/NACK）
- [x] `rtl/camera/ov5640_capture.v`
- [x] `rtl/camera/cdc_async_fifo.v`
- [x] YUYV/UYVY参数化Y分量提取
- [x] 固定VGA 640×480到128×128 letterbox与camera输入ping/pong
- [x] PCLK/100 MHz异步FIFO CDC及camera子系统OOC时序/CDC报告
- [x] OpenSOC OV5640实物SCCB ID、PGM图像读回及camera→Locator正检测
- [x] 旧候选ROI→分类器9/10板测及新候选实现后整机时序签核
- [x] 精确新哈希短板测完成并封存功能RC
- [ ] DVP input delay实测后关闭临时时序例外

---

## 4. 历史变更摘要

### 2026-07-31：工程初始化与 Phase 1 原型

- 建立 `docs/`、`model/`、`rtl/`、`sim/`、`ps/`、`constraints/`、
  `scripts/`、`backups/` 目录和 AI 工作规范。
- 确立 CDC、流水线、BRAM Latency 和“RTL + 配套检测代码”双交付原则。
- 生成 32×32 测试图、层描述符、权重与八层中间黄金向量。
- 交付早期 `mac_lane`、`mac_array_32ch`、`requant_unit`、`line_buffer_3x3`、
  `cnn_ctrl_fsm`、AXI 从机和顶层封装。
- 修复多项早期问题：BRAM 读取对齐、权重寻址、1024 像素遍历、Argmax 首值、
  Requant valid 污染、多重驱动、仿真语法和综合 `$readmemh` 告警。
- 历史 PYNQ-Z2 板测完成：AXI 灌图/启动/结果读取闭环，曾完成 8 类离线样本验证。

### 2026-08-01 至 2026-08-03：描述符架构重建

- 识别旧 mock pipeline 的硬编码参数、测试旁路、权重映射和激活打包缺陷。
- 完成 C1 单层 3×3 Conv + Requant 的 RTL/Golden 100% Bit-Exact proof point。
- 重建 `cnn_core`、`cnn_core_fsm`、通用 Conv/Pool/Dense 与激活 Ping/Pong。
- 修复描述符解析和累加器读延迟问题，完成八层逻辑验证。
- 历史板级验证曾确认 Class ID 与当时黄金结果一致；该历史结果不替代 ABI 1.0
  新 Bitstream 的重新上板回归。

### 2026-08-11：Phase 1 稳定化与 ABI 1.0 收口

- [x] 建立 `model_package/active/` 单一生产模型入口，统一权重、描述符、量化
  manifest 与黄金向量，并增加 SHA-256/word-count 自动检查。
- [x] 将描述符绝对路径只读 ROM 替换为 `cnn_desc_mem.v` 可写双端口存储。
- [x] 重写 AXI4-Lite 写通道，支持 AW/W 独立握手、WSTRB、SLVERR、ABI 版本和
  忙状态 BRAM 写保护。
- [x] Soft Reset 仅复位 CNN 数据面和状态，不再复位 AXI 从机自身。
- [x] 收敛寄存器 ABI：移除旧 `0x18` 类别旁路；新增 `0x0C ABI_VERSION`、
  `0x28/0x2C` 描述符加载窗口；同步更新 Python/C 驱动和文档。
- [x] `sim/tb_gesture_top.v` 增加 AXI 错拍、忙时拒写、IRQ/DONE sticky、
  Soft Reset、watchdog、overlap 和全网 Bit-Exact 检查。
- [x] `fist_00`：C1/P1/C2/P2/C3/P3/FC1 全部逐字节一致；FC2
  `Class ID=1`、`max_logit=6024` 精确一致。
- [x] Vivado OOC 综合完成：0 Error、0 Critical Warning；active descriptor/weight
  初始化文件解析成功，旧绝对路径和 AXI 图像位宽警告消除。现存 63 条普通 Warning
  主要是未使用高位/保护位、池化临时寄存器优化和 BRAM 输出寄存器建议；后两类纳入
  下一阶段同步 BRAM 与 100 MHz 重构。
- [x] OV5640 采购评估：推荐 3.3 V、8-bit DVP 普通视角模块；USB/PS 调试入口保留。
- [x] 修复 Windows PowerShell 5.1 下的备份脚本编码/空包问题；新脚本排除可再生构建
  目录，并对实际 ZIP 条目数和大小执行强制校验。
- [ ] 下一阶段：同步 BRAM、100 MHz、8-output-channel MAC 和输入双缓冲。

### 2026-08-11：PYNQ-Z2 Vivado 平台基线修正

- [x] 工程 Part 确认为 `xc7z020clg400-1`，激活并写入官方 Board Part
  `tul.com.tw:pynq-z2:part0:1.0`。
- [x] 按官方板卡 preset 重建受 Board Part 影响的 PS7、复位和 AXI GPIO 单元，
  保留 Phase 1 的 50 MHz 实际时钟。
- [x] 核对并固化地址：CNN `0x4000_0000/4 KiB`，GPIO
  `0x4120_0000/64 KiB`；IRQ、AXI、时钟和复位连接完整。
- [x] LED 改用官方 `leds_4bits` Board Interface；综合后 IO 报告确认 M14、N16、
  P14、R14，均为 LVCMOS33。
- [x] 移除活动 XDC 中未经硬件接线确认的 OV5640 占位引脚；摄像头约束延期到
  具体 DVP 模块和排针转接确定后加入。
- [x] 刷新 stale 的 `gesture_top` RTL Module Reference；刷新后地址不变，全部 IP
  为 Up-to-date（AXI Interconnect 2.1 为 Vivado 标记的 discontinued/无需变更）。
- [x] `configure_vivado_platform.tcl` 和 `run_platform_synth_check.tcl` 固化上述检查；
  `create_project.tcl` 已通过临时目录从零重建冒烟测试。
- [x] 完整顶层综合通过：0 Error、0 Critical Warning、无锁定/过期 IP、严重 DRC
  为 0；50 MHz 综合后 WNS `+2.558 ns`、WHS `+0.045 ns`，约束满足。
- [x] 本步骤未运行 implementation/bitstream；现有旧 `.bit` 不代表本平台修正版，
  上板前仍需显式运行 `build.tcl` 生成新比特流。

### 2026-08-11：Phase 1 Baseline v1.0 板测与封存

- [x] Vivado implementation、route 和 bitstream 完成；0 Error、0 Critical Warning，
  8,920/8,920 条可布线网络全部完成。
- [x] 50 MHz 布线后时序收敛：WNS `+0.573 ns`、WHS `+0.036 ns`，TNS/THS 为 0，
  未约束内部端点和无时钟寄存器端点均为 0。
- [x] 布线后资源：6,321 LUT（11.88%）、2,670 Register（2.51%）、25 BRAM Tile
  （17.86%）、18 DSP（8.18%）。
- [x] PYNQ ABI/状态冒烟通过：ABI `0x00010000`，初始 STATUS `0x00000001`。
- [x] active model HIL 板测 8/8；单次 CNN 延迟 `7.805–7.815 ms`，平均
  `7.80975 ms`；完成状态 `0x00000005`。
- [x] USB 摄像头视频推理通过；四个用户 LED 在显式清零 AXI GPIO TRI 后通过。
- [x] 已知限制固化：PYNQ 未暴露当前直连 IRQ 元数据，V1.0 使用 DONE 轮询；GPIO
  使用前需初始化 TRI；仅证明 50 MHz；OV5640/定位/100 MHz 不进入本基线。
- [x] 建立 `releases/Gesture_Phase1_Baseline_v1.0/`，封存 bit/hwh、active model、
  可复跑 Notebook、板测记录、实现报告、源码快照及 SHA-256 清单。

### 2026-08-12：Phase 2-L1 Locator 工程骨架首轮实现

- [x] 导入并固化总体架构 v2.1.2、接口草案 v0.3.2；新增骨架相对寄存器映射，
  明确不占用或修改 Phase 1 的 CNN `0x4000_0000` 与 GPIO `0x4120_0000`。
- [x] 新建独立 `rtl/locator/`，实现 AXI4-Lite、参数/描述符存储、标准 CRC 提交、
  模型有效性、输入/输出双缓冲所有权、逐缓冲 Frame ID、IRQ、计数器和 Soft Reset。
- [x] 数据面先使用可复现的 Stub：读满 16 KiB 输入，写出 1280 个 INT32 Word；
  输出由输入校验值、frame ID 和 word index 唯一确定，用于验证接口和 BRAM 时序。
- [x] 新增 `sim/locator/` 自检 testbench 与一键脚本；CRC 标准向量和完整顶层回归
  均通过，包含 bit-exact 比对、FSM watchdog 与资源/事务 overlap 检查。
- [x] Vivado 2026.1 对 `xc7z020clg400-1` 完成 100 MHz OOC 综合：0 Error、
  0 Critical Warning；WNS `+3.785 ns`、WHS `+0.252 ns`；资源为 736 LUT、
  1018 Register、3 BRAM Tile、0 DSP。OOC 的 PS7 缺失/时钟源提示不等同于完整
  Block Design 的实现与时序签核。
- [x] 建立隔离 `vivado_phase2_l1/Gesture_Phase2_L1.xpr`：PS/分类 50 MHz、Locator
  100 MHz、AXI Clock Converter、输入 32 KiB/输出 16 KiB independent-clock TDP BRAM、
  AXI INTC 和六段固定联调地址；HWH 地址/中断元数据自动核对通过。
- [x] 新增 PS 批量 MMIO 驱动、PC Fake-MMIO 测试和 `locator_stub_board_test.ipynb`；
  Stub Notebook 明确要求未来的 Phase 2 bit/hwh，不能配合当前 Phase 1 bitstream 使用。
- [x] Locator IRQ 在源域寄存后经两级同步；RTL 回归新增 IRQ 置位/清除、BRAM
  Word-to-byte 地址适配和 CDC 同步器自检，四组 XSim 回归全部通过。
- [x] 最终全顶层综合为 0 Error/0 Critical Warning；WNS、CDC、bus-skew、DRC、IP
  状态和资源报告写入 `reports/phase2_l1/`。本批未运行 implementation/bitstream。
- [ ] 下一批：等待算法冻结预处理测试向量、逐层量化数值和描述符字段后，实现
  5 层 INT8 定位计算核及逐层 golden；随后完成 PS bbox 同帧闭环、implementation、
  新 Phase 2-L1 bitstream 和上板回归。Phase 1 V1.0 封存件保持不变。

### 2026-08-12：Phase 2-L1 Stub implementation 与首轮板端诊断

- [x] 首版 Stub 工程完成 implementation 与 bitstream：全局 WNS `+0.330 ns`、WHS
  `+0.020 ns`；FCLK0 WNS/WHS `+0.330/+0.020 ns`，FCLK1 WNS/WHS
  `+2.754/+0.022 ns`；路由错误、无时钟端点和未约束内部端点均为 0。
- [x] 成功登录 `192.168.2.99:9090`，只在板端新建
  `/home/xilinx/phase2_l1_stub_test_20260812_203200/`；未覆盖既有 Notebook、Overlay
  或 Phase 1 封存文件。
- [x] 修复 PYNQ 将 AXI BRAM Controller 放入 `mem_dict` 而非 `ip_dict` 时的元数据
  识别问题；板测脚本现合并两个字典并按基址/范围检查。
- [x] Locator MMIO 首次访问发生不可中断等待。静态回查 HWH 确认
  `PCW_EN_CLK1_PORT=1`、FCLK1 配置为 100 MHz，但 `PCW_FCLK_CLK1_BUF=FALSE`；
  这与跨 50→100 MHz AXI Clock Converter 后的目标时钟停止现象一致，首版 bit/hwh
  因此作废，不计为板测通过。
- [x] 构建脚本已强制 `PCW_FCLK_CLK1_BUF=TRUE`，PC 与板端 HWH 预检均将其列为
  Overlay 下载前的硬门槛；PS 驱动在创建任何 MMIO 前显式设置 FCLK0=50 MHz、
  FCLK1=100 MHz。Locator 驱动/HWH 契约回归 7/7、Phase 1 active 模型包校验均通过。
- [x] 新增 `docs/locator/phase2_l1_board_bringup.md`，冻结元数据→时钟→低风险 MMIO→
  Locator→双缓冲→Phase 1 回归的安全测试顺序。
- [x] 首版 bit/hwh、部署 ZIP 和派生 Notebook 已在
  `artifacts/PHASE2_L1_STUB_20260812_INVALID.md` 中统一标记为禁止复用，只保留追溯。
- [ ] 板卡执行软件 `reboot` 后未重新上线，需要物理断电重上电。
- [ ] 修正版工程暂未重建：本机 Vivado 用户 Tcl App manifest 要求加载
  `aldec::activehdl`，但用户缓存目录仅有 manifest/lock；Vivado 在执行工程 Tcl 前即
  报 `Failed to install all user apps` 并因 `load_features` 失败退出（安装目录内的
  Tcl Store 原始 App 仍存在）。需用户授权后备份并修复该用户级 App 缓存状态，再生成
  新 bit/hwh、执行 HWH 硬检查和完整板端回归。

### 2026-08-13：Phase 2-L1 Stub 复位根因与 reset-fix Bitstream

- [x] 通过 UART 确认板端 FPGA Manager、Jupyter、以太网和 USB UVC 摄像头均健康；
  PC 到 `192.168.2.99:9090` 的超时仍来自本机网络隔离，板内访问 Jupyter 返回 302。
- [x] 在 `/home/xilinx/phase2_l1_safe_bringup_20260813_002119/` 新建独立测试目录；
  未覆盖 `/home/xilinx/jupyter_notebooks`、Phase 1 Overlay 或既有测试文件。
- [x] 第二版 HWH 已满足 `PCW_FCLK_CLK1_BUF=TRUE` 且 FPGA Manager 下载成功，但
  首次 GP0 AXI 访问仍永久等待。静态回查证明两个 `proc_sys_reset` 均为
  `C_AUX_RESET_HIGH=0`，而 `aux_reset_in` 接常量 0，导致 50/100 MHz 数据面永久复位。
- [x] `create_phase2_l1_project.tcl` 显式冻结两套复位 IP 的
  `C_AUX_RESET_HIGH=1`；HWH 验证器和 PS 驱动同时要求 `EXT=0/AUX=1`，旧 HWH 会被
  自动拒绝。Locator 驱动测试扩充到 8/8，包含错误复位极性拒绝用例。
- [x] 在 `vivado_phase2_l1_resetfix_20260813_021135/` 从零重建独立工程；HWH 六段地址、
  FCLK1 和两个复位域门禁全部通过。Phase 1 工程及封存件未打开、未覆盖。
- [x] reset-fix 综合静态验收：WNS `+2.558 ns`，FCLK0/FCLK1 均存在，活动跨域路径 0，
  CDC、DRC、bus-skew 和约束覆盖检查通过。
- [x] reset-fix implementation/bitstream：WNS `+0.330 ns`、WHS `+0.020 ns`，路由、
  DRC、CDC、bus-skew 均通过。部署包位于
  `phase2_l1_resetfix_deploy_20260813_021135/`，压缩包 SHA-256 为
  `8D03721B072624C9BD56D0A3197C2C111D3A337552FA5A77EEAF805C7F2B8FA7`。
- [x] 板卡物理重上电后，在新目录
  `/home/xilinx/phase2_l1_resetfix_bringup_20260813_024300/deploy/` 完成 reset-fix 上板；
  未覆盖 `/home/xilinx/jupyter_notebooks`、Phase 1 Overlay 或既有测试目录。
- [x] 板端产物哈希与部署包一致：bit
  `52B87EEAC4724CF66963496B71E22A055FC259692CE976185A22DC55920516DE`，HWH
  `D2F5389B768248C699DB50C49DE38F258446A0DDA9FEF781FE03EA70E10412A`；FPGA Manager
  下载 `248.842 ms`，状态保持 `operating`，FCLK0/FCLK1 实测 `50/100 MHz`。
- [x] `board_test_result_lowlevel_v4.json` 最终状态 `PASS`，总用时 `1.476 s`：Locator
  ABI `0x00000302`、参数/描述符 CRC、ping-pong、Frame ID `0xFFFFFFFF -> 0x00000000`
  回绕、AXI INTC IRQ、原子 OUTPUT_RELEASE 和保留模型的 SOFT_RESET 全部通过；两帧
  128×128 Stub 推理分别 `6.507/6.233 ms`，每帧 1280 个输出 Word 均 bit-exact。
- [x] 保留分类器 ABI 与 active model 黄金向量 HIL `8/8` 通过，单次延迟
  `7.793–7.805 ms`；AXI GPIO/LED 寄存器回读 `0xA` 并恢复原状态；板内 Jupyter
  保持 `active` 且本机回环访问返回 302。
- [x] 摄像头随后接回 PYNQ；在新目录
  `/home/xilinx/phase2_l1_camera_validation_20260813_173445/` 重新加载 reset-fix 并复跑
  HIL，结果 `PASS`、总用时 `1.402 s`。Windows 到 Jupyter 已恢复，9090 TCP 可达且
  HTTP 返回 302；此前失败由 Windows 出站阻断规则和 USB 网卡 Phantom 状态叠加造成。

### 2026-08-13：Phase 2-L1 USB 实时链路与 PS 前后处理接口

- [x] 新增 `ps/locator/phase2_l1_pipeline.py`：显式 BGR 灰度、128×128 letterbox、
  little-endian signed CHW `5×16×16` 解析、confidence Top-1、五通道 scale 反量化、
  locator 到原图坐标反变换和同帧 bbox 裁剪。插值、取整、padding、阈值、scale、
  bbox 扩边/方形化/裁剪均无隐藏生产默认值，等待算法 manifest 后再冻结。
- [x] 新增 `test_phase2_l1_pipeline.py` 和有限板测 `phase2_l1_camera_smoke.py`；PC 端
  Locator 驱动/前后处理合计 16/16，PYNQ 端前后处理 8/8，并用真实帧验证 bbox 裁剪
  输出 `32×32 uint8`。
- [x] USB 摄像头 `/dev/video0` 在 reset-fix Overlay 下采集 `640×480` 共 30/30 帧，
  30 个帧哈希均不同；10 次实时帧→Locator Stub 均 bit-exact，延迟
  `5.987–6.815 ms`、平均 `6.300 ms`。
- [x] 同一批帧按现有 Phase 1 中心 ROI 送入真实分类器 10/10 次完成，延迟
  `7.945–8.295 ms`、平均 `8.159 ms`；画面均输出 background。该结果只证明实时链路
  稳定，不作为分类或定位精度评估。
- [x] 板测结束后 FPGA Manager 保持 `operating`，Jupyter 保持 `active`，板内访问
  返回 302；结果文件为板端 `camera_smoke_result_v2.json`，SHA-256
  `962B02C98B806B8D00EDAC7571BB0ACB3ADDEBA22602E54EEC12D75CA1691036`。
- [ ] 下一项只等待算法交付：预处理冻结向量、真实参数/描述符、五通道 scale、raw
  confidence 阈值、bbox 策略、逐层及整网黄金向量。到件前不实现/宣称真实 Locator CNN。

### 2026-08-13：汇报架构图数据底稿

- [x] 新增 `docs/overall_architecture_dataflow_report_cn.md`，统一整理 Phase 2-L1 当前骨架、
  Phase 1 分类 CNN、PS 前后处理和 Phase 2-L2 预留位置；文档用 Implemented、Measured、
  Contract、TBD、Future 五类标记隔离已实现事实与未冻结模块。
- [x] 文档补齐六段 AXI 地址、50/100 MHz 时钟与复位、CDC/IRQ、AXI4-Lite/AXI4/BRAM
  主要信号位宽、little-endian 数据格式、ping-pong 所有权、启动/完成/释放控制序列、
  分类器逐层周期、Stub 与板端链路延迟、顶层 post-route 资源/时序及主要 IP OOC 资源。
- [x] 真实 Locator CNN 的并行阵列、逐层周期、最终资源、量化数值和 bbox 闭环继续标记
  为 TBD；OV5640/DVP/PL letterbox/PL ROI 仅作为 Phase 2-L2 灰色占位。本批未修改 RTL、
  Block Design、模型、封存件或 bitstream。

### 2026-08-18：Phase 2-L1 v12 真实定位核、实现与候选部署包

- [x] 接收并机械校验 `quantized_locator_v12`：模型固定为 1,904 Word / 7,616 Byte，
  CRC-32/ISO-HDLC `0x63F19DDB`，模型 SHA-256
  `c7542efa941dca7e559ba4713ea362ebd4ea62ebe74f0e5ddb8a32a3e7c4bdbe`；输入为
  4,096 Word，Conv5 输出为 1,280 个 little-endian signed int32 CHW Word，confidence
  raw 阈值固定为 `-3336`。
- [x] 在既有 `locator_top` 控制、CRC、描述符、ping/pong、Frame ID、IRQ与AXI地址契约
  内启用 `USE_CNN_CORE=1`，实现真实五层标量定点 CNN；Phase 1 `gesture_top_0`、
  `model_package/active`、类别顺序和 ABI 均未修改。
- [x] 修复同步激活/模型存储读出到 byte-select/乘法器的 100 MHz 临界路径，在乘法前
  增加一级 pixel/weight 操作数寄存器；保持稳态每周期一个 MAC。四组正式样本的
  Conv1、Conv2、Conv3、Conv4 与 Conv5 均 bit-exact。
- [x] 周期精确回归：Conv1 `1,966,097`、Conv2 `3,833,880`、Conv3 `1,867,808`、
  Conv4 `921,648`、Conv5 `282,889` cycle；引擎合计 `8,872,324` cycle。完整AXI外壳
  START→DONE 为 `8,872,326 cycle = 88.72326 ms @100 MHz`，模型加载/CRC、两路
  output bank、逐缓冲 Frame ID、CHW输出及阈值判定同时通过。
- [x] `locator_top` OOC综合：1,188 LUT、1,131 FF、19 BRAM Tile、4 DSP，100 MHz
  WNS `+0.869 ns`。全顶层综合：14,389 LUT、11,604 FF、56 BRAM Tile、22 DSP、
  4 I/O，全局 WNS `+0.621 ns`。
- [x] 全顶层 implementation/bitstream 完成：post-route 13,395 LUT（25.18%）、
  10,415 FF（9.79%）、56 BRAM Tile（40.00%）、22 DSP（10.00%）、4 I/O（3.20%）；
  全局 WNS/WHS `+0.284/+0.024 ns`，FCLK0 `+0.921/+0.024 ns`，FCLK1
  `+0.284/+0.027 ns`。无时钟/未约束内部端点为0、路由错误0、CDC 15 Info且无
  Warning/Critical，bus-skew最小余量 `+28.733 ns`。
- [x] HWH六段地址、FCLK1 buffer/100 MHz与两套复位极性全部通过机械校验；PS驱动、
  pipeline和元数据单元测试 `18/18` 通过。bit SHA-256
  `533CBAD087D8E1DD21C623D5612A966206E7B772AA656DA1332F39536C7D6D6F`，HWH SHA-256
  `31927611FBD2DC0679EA70C09A745202DD5844F9AA797C567A0FD721BD1B8B93`。
- [x] 生成独立最小部署包
  `artifacts/phase2_l1_v12_candidate_20260818_005700.zip`，SHA-256
  `19F3F6D9D97794E2ADD6D797BF53B3D552AC700A291ECD2C10F74C0DA38D25AA`；板测脚本按
  “模型CRC→四组正式map/bbox→ping/pong/IRQ/Frame ID/reset→分类HIL 8/8→LED”执行。
- [ ] 板端回归暂未执行：Windows 当前没有枚举出先前的 ASIX/NX USB以太网适配器，
  因而不存在 `192.168.2.1/24` 物理接口，`192.168.2.99:22/9090` 均不可达。这不是
  bitstream或Jupyter服务结论；网卡恢复后只在 `/home/xilinx` 下新建测试目录部署。
- [ ] 静态板测通过后再进行 USB 实时阶段；原始BGR到冻结128×128输入的精确复现脚本、
  bbox扩边/方形化/失败回退策略及int32范围/回绕专项向量仍由算法/应用侧补齐。

### 2026-08-18：Phase 2-L1 v12 自助上板验收材料

- [x] 新增 `docs/locator/phase2_l1_v12_board_selftest_cn.md`，给出板卡/Windows网络检查、
  Jupyter上传与运行、正式PASS判据、LED目视检查、USB采集健康检查及按失败阶段停止的
  处理方法；明确不混用旧Stub bit/HWH，不覆盖板端既有文件。
- [x] 新增 `ps/locator/phase2_l1_v12_board_test_runner.ipynb`：先核对候选ZIP固定SHA-256，
  再在 `/home/xilinx` 新建带时间戳的隔离目录，复核部署manifest及bit/HWH哈希，最后以
  子进程流式运行正式 `phase2_l1_v12_board_test.py` 并汇总JSON结果。
- [x] Notebook提供两个默认关闭的显式可选步骤：正式HIL通过后可分别置位开关，显示
  LED `1010` 三秒并恢复原寄存器，或只读取 `/dev/video0` 的30帧USB摄像头；后者不
  宣称定位精度或生产闭环，`Run All`不会自动运行这两个步骤。
- [x] Notebook JSON解析及6个Python代码单元编译通过；候选ZIP与内部137项manifest
  将在备份前再次离线核对。没有运行板测，也没有修改RTL、bitstream、HWH、Phase 1
  封存件或现有候选部署ZIP。
- [x] 首次用户自助测试确认候选ZIP SHA-256正确并创建隔离目录，但PYNQ侧标准
  `ZipFile.extractall()`未实际生成至少一个嵌套黄金向量文件，manifest在Overlay下载前
  正确停止。PC端复核ZIP内目标文件、压缩CRC和全部137项manifest均完整；runner改为
  对每个ZIP条目显式创建父目录并复制内容，同时给出当前测试目录的原地补齐代码。
- [x] 首次文件准备失败发生在Overlay下载前，不计为板端HIL失败；改用全新目录逐项解压
  后，用户继续完成正式测试。

### 2026-08-18：Phase 2-L1 v12 真实定位核静态HIL通过

- [x] 用户在独立目录
  `/home/xilinx/phase2_l1_v12_selftest_clean_20250505_134009_373340/`运行正式板测；部署
  文件、HWH时钟/复位契约、候选Overlay下载、FCLK0/FCLK1 `50/100 MHz`、Locator ABI
  `0x00000302`全部通过。目录时间戳反映板端当前系统时间为2025-05-05，不是工程版本日期。
- [x] 板端上传1,904 Word模型并完成硬件CRC：模型`0x63F19DDB`、描述符`0x21A56B2B`；
  `MODEL_VALID`成立。Overlay加载`3785.693 ms`，模型/描述符加载`18.679 ms`。
- [x] 四组正式输入的完整1,280 Word Conv5 signed int32 CHW map均bit-exact，SHA-256分别为
  `96b09531e099f0f4c629bd50d70f592cb3fd5c3650fc02ba353952a1b3a46818`、
  `910cb1def2d299c23987845d7a1cb70204f3679333a8c9a369052eb3fb399dbd`、
  `55b5fe517dace0b0bddc01c23d10db337ffc7b0e2d17340044362ee01f187bcf`、
  `298abe9507326c34cc56b3f44fb7939ab6e782184cc64a1da1f3466f5f54494f`；
  Top-1、raw阈值`-3336`和bbox均与参考一致，hand样本检出、其余3组未检出。
- [x] 四次输入写+核计算+输出读事务延迟为`99.597/92.650/92.788/93.112 ms`，范围
  `92.650..99.597 ms`、平均`94.537 ms`；output bank前两帧为0/1，逐缓冲Frame ID、
  OUTPUT_RELEASE、AXI INTC pending `0x00000002`和保留模型的SOFT_RESET全部通过。
- [x] 候选bitstream内未修改的`gesture_top_0`完成HIL 8/8，延迟`8.277..8.375 ms`、
  平均`8.300 ms`；所有class ID/logits与封存黄金数据一致。GPIO数据回读`0xA`通过。
- [x] 正式脚本最终输出`BOARD TEST RESULT: PASS`和返回码0；结果文件为板端
  `phase2_l1_v12_board_test_result.json`。本记录依据用户提供的完整板端控制台输出；
  JSON已下载至工程根目录并解析确认`status=PASS`、11/11检查项PASS、脚本总用时
  `5.372 s`，SHA-256为
  `8E3ED9F9E28A497CF7CE0915530580D268419418BC8FE903094164A8DE241322`。
- [x] 候选bitstream下LED `1010`保持三秒并恢复，物理目视通过；USB摄像头采集
  `30/30`帧，shape固定为`480×640×3`，30个帧SHA均不同，平均亮度范围
  `3.00..35.45`。链路健康，但当前画面明显偏暗，准确率测试前需改善照明。
- [ ] 下一步进入USB实时Locator→PS bbox→现有分类器闭环与分段延迟/抖动测量。正式预处理、
  bbox扩边/方形化/失败回退和int32范围/回绕专项向量仍待算法/应用侧最终签核。

### 2026-08-18：Phase 2-L1 v12 USB实时闭环工程冒烟准备

- [x] 新增`ps/locator/phase2_l1_v12_realtime_smoke.py`，在不重新下载Overlay的前提下执行
  USB帧→灰度/128×128候选letterbox→真实Locator→raw阈值/bbox→同帧ROI→32×32分类→
  one-hot LED，并记录捕获、预处理、输入提交、等待/输出读取、bbox/分类和端到端各段时间。
- [x] 脚本每次重新加载封存分类参数；Locator仅在`MODEL_VALID=0`时重载v12包。每次结果
  记录硬件STALL/DROP增量、PS按`infer-every`主动跳过帧数、检测/bbox/分类计数、类别分布、
  亮度、全部逐帧数据和annotated preview；硬件`DROP_COUNT`增加会直接判失败。
- [x] 冒烟候选参数显式固定并写入JSON：OpenCV BGR2GRAY、nearest letterbox、half-up尺寸
  取整、top/left floor padding、每边10%扩框、方形化和linear 32×32分类resize；raw阈值
  `-3336`来自正式manifest。除raw阈值外均不宣称生产冻结或精度验收。
- [x] 新增`docs/locator/phase2_l1_v12_realtime_smoke_cn.md`，要求依次采无手和单手场景，
  稳定性只以帧数、无超时、无AXI错误、`DROP_COUNT=0`和结果文件生成判定；检测率、bbox
  跟随和分类分布作为观察量，避免在算法预处理/裁剪策略未签核前误报准确率。
- [x] 用户已运行无手、fist、mute、palm共8组场景并下载JSON及preview；板端实测结论见
  下一节和`docs/locator/phase2_l1_v12_realtime_results_20260818_cn.md`。

### 2026-08-18：Phase 2-L1 v12 USB实时闭环板测

- [x] 8/8个实时工程冒烟进程均为`PASS`：共采集480帧且480个帧哈希均不同，执行160次
  Locator推理；硬件`STALL_COUNT`与`DROP_COUNT`总增量均为0，无超时、无AXI异常。
- [x] 160次推理共88次超过raw阈值`-3336`，88/88均生成有效bbox并执行现有分类器，
  `crop_error=0`。无手场景0/20检出，raw范围`-8933..-4866`。
- [x] 三组fist标签现场运行分别检出0/20、20/20、8/20；已分类结果合计fist 11、
  palm 17。三组mute分别检出20/20、5/20、15/20；已分类结果合计mute 34、palm 2、
  background 4。palm运行20/20检出，分类palm 19、background 1。
- [x] 上述分布只作为未受控现场观察量：每组只保留最后一张preview，无法确认每个抽样帧
  的手部可见性和真值框，禁止据此宣称precision、recall或四类accuracy已经通过。
- [x] 160次均值：PS灰度/letterbox `6.074 ms`、16 KiB Locator输入提交`3.408 ms`、
  Locator等待+5 KiB输出读取`89.845 ms`；88个检出帧的分类输入上传`22.633 ms`、分类
  推理`8.239 ms`。未检出/已检出pipeline均值分别为`100.021/133.111 ms`。
- [x] Preview人工检查确认bbox在palm、偏左fist及部分mute画面能跟随手部；一组近距离
  fist定位成功但多次被分为palm，部分mute帧bbox包含较多面部或低于阈值。当前主要问题
  位于现场泛化、ROI策略和分类域适配，不是已经bit-exact的RTL数值链路。
- [x] 修正实时脚本nearest-rank P95索引；旧公式在20个样本时会把最大值写成P95。既有
  JSON的均值、最小值、最大值与本节结论不受影响。
- [ ] 下一轮只做必要的受控采样：保存每次推理的原始帧、128×128输入、bbox ROI和结果，
  按类别/距离/位置逐帧标注后再评估检测与分类；在此之前不调整`-3336`阈值，不改RTL
  定点路径。

### 2026-08-18：Phase 2-L1 v12 Jupyter实时视频查看器

- [x] 新增`ps/locator/phase2_l1_v12_live_view.py`：不重新下载Overlay，在PYNQ执行USB
  采集、v12 Locator、PS bbox/同帧ROI、封存分类CNN和LED输出，并通过Jupyter
  `display_id`把带标注JPEG持续刷新到电脑浏览器。
- [x] 实时画面同时显示绿色Locator bbox、青色实际分类ROI、raw值、固定阈值`-3336`、
  类别、pipeline时延和浏览器刷新FPS；默认120秒，也支持`--duration 0`运行到Notebook
  中断。正常/手动结束均释放摄像头并恢复原LED寄存器。
- [x] 每次会话生成独立JSON和最后一帧PNG，记录逐次Frame ID、ping/pong buffer、bbox、
  分类、分段时延与硬件stall/drop；硬件drop增加仍判失败。工具不修改RTL、bit/HWH、
  模型或正式验收目录。
- [x] 新增`test_phase2_l1_v12_live_view.py`及中文操作文档
  `docs/locator/phase2_l1_v12_live_view_cn.md`；本机帮助入口和AST语法检查通过，3个查看器
  纯函数测试及既有18个Locator驱动/前处理测试合计21/21通过。
- [x] 初版查看器已由用户在板端运行并生成多组JSON/最后帧；实测约4.5～5.1 FPS，硬件
  控制链路正常。18% A/B会话完成543次推理、373次raw检出且stall/drop为0，但当时仍为
  独立四边裁剪且未加时序滤波，只能作为旧版对照，不能替代下述冻结契约新版板测。

### 2026-08-18：Phase 2-L1 分类ROI与PS时序契约收口

- [x] 分类ROI冻结为：输入EMA后的原图float `xyxy`；每侧18%（边长系数1.36）；Python
  内建`round`；边长限制为源图短边；完整正方形整体平移回画面内；无padding；right/
  bottom为OpenCV开区间；`BGR2GRAY`后`INTER_LINEAR`缩放到32×32。
- [x] `phase2_l1_pipeline.py`加入契约版本
  `phase2_l1_roi_v1_18pct_square_shift_pyround`，修复边缘目标被独立clip成长方形的问题；
  底边实测几何回归由旧312×294矩形收敛为311×311正方形。
- [x] PS时序默认值实现为bbox EMA alpha `0.30`、漏检保持3个推理帧、分类5帧多数投票、
  新投票类别连续2次后切换。保持期继续对当前原始帧裁剪/分类，第4个连续漏检清空bbox、
  分类窗口和LED输出；JSON同时保留raw/stable/held bbox及raw/voted/output class。
- [x] 实时查看器显式加载与脚本同目录的冻结pipeline并校验契约版本，避免Jupyter模块缓存
  或验收目录旧10%实现混入；绿色显示raw bbox、黄色显示EMA/保持bbox、青色显示实际ROI。
  正式验收目录、RTL、BD、bit/HWH、模型、Locator ABI和`gesture_top_0`均未修改。
- [x] 新增ROI边界、短边限制、Python ties-to-even、EMA、3帧保持、5帧投票/2次切换回归；
  本机AST检查通过，Locator驱动/前处理/查看器合计26/26单元测试通过。
- [ ] 板端只需上传新版`phase2_l1_v12_live_view.py`和`phase2_l1_pipeline.py`到新的Jupyter
  工作目录，在已通过静态HIL的Overlay上运行；确认JSON契约版本、ROI严格正方形、hold/
  vote行为和stall/drop=0。之后再收集逐帧标注样本判断是否需要重训Locator或分类器。

### 2026-08-18：Phase 2-L1 失败样本自动采集与算法交接工具

- [x] 新增`ps/locator/phase2_l1_failure_capture.py`：每次运行只接受一个人工保证的
  `no_hand/fist/mute/palm`真值，在已验收v12 Overlay上自动筛选Locator假阳性、Locator
  漏检、分类误判及稀疏正确对照；不重新加载Overlay、不修改正式验收目录和LED。
- [x] 每个样本保存无损源灰度PNG、实际128×128 Locator输入、固定5120 Byte CHW小端
  signed int32 Conv5 map、实际32×32分类ROI（若运行）、禁止训练的标注preview及metadata。
  raw漏检即使被时序hold仍可作为Locator hard positive，但held旧ROI禁止进入分类训练。
- [x] 会话记录模型/脚本SHA、硬件ABI/模型CRC/描述符CRC、Frame ID、raw/EMA bbox、阈值、
  类别、buffer和stall/drop；结束或用户中断后生成逐文件SHA-256 manifest和CRC验证ZIP，
  方便从Jupyter或SCP拉回PC后向算法端交接。
- [x] 新增`test_phase2_l1_failure_capture.py`和
  `docs/locator/phase2_l1_failure_capture_cn.md`；错误类型选择、ASCII会话名、无损输入/ROI、
  5120 Byte raw map、小端恢复、manifest和ZIP CRC均有离线测试。与既有驱动/ROI/查看器
  回归合计30/30通过，AST和`--help`入口通过。
- [ ] 新采集器尚未在PYNQ真实摄像头上运行。首次板测先用`no_hand`、20秒、最多10个样本
  做小规模验证，下载ZIP并复核SHA/目录内容后，再开始3分钟正式批量采集。

### 2026-08-19：Locator v16 + 分类器 v3 第二轮候选准备

- [x] 接收并机械验收算法侧两套新包。Locator v16保持`1×128×128 uint8 ->
  5×16×16 signed int32 CHW`、1,904 Word和ABI不变，模型CRC为`0x21FC0351`、
  raw阈值为`-1901`；分类器v3保持9,838 Word、64个描述符Word及
  `background/fist/mute/palm`顺序不变，权重SHA-256为
  `BB22EB59EE4159DF5B08DCED2AB1813C8C73BED0A0C0D650D66B54B808BB1923`。
- [x] Locator v16的Conv4 requant乘数由`13102420`更新为`13500053`；定位核四组
  正式向量的Conv1～Conv5逐层bit-exact仿真、AXI/CRC/IRQ/ping-pong/Frame ID顶层仿真
  均通过。分类器v3八组输入的七个中间层、最终logits及class ID全部bit-exact通过。
  Locator核OOC综合为4 DSP48、19 RAMB36，100 MHz WNS `+0.869 ns`。
- [x] 首次默认实现布线后WNS为`-0.104 ns`，该bitstream明确拒绝部署。保持周期级行为不变，
  将Locator第一层外部输入BRAM使能条件独立寄存，并启用实现后物理优化；重新完成逐层与
  顶层仿真后，全工程实现WNS `+0.124 ns`、WHS `+0.024 ns`，TNS/THS均为0，
  21,001/21,001可布线网络全部完成，DRC为0 Error，CDC仅15项已同步Info，bus skew全MET。
- [x] 实现后全工程资源为LUT `13,392/53,200`（25.17%）、寄存器
  `10,443/106,400`（9.81%）、BRAM Tile `56/140`（40.00%）、DSP
  `22/220`（10.00%）、PL I/O `4/125`（3.20%）。候选bit SHA-256为
  `B02E4BE5B157BC5D372C379E63875C8B80AF91083FDE2D63BBD038B60FCE37AC`，HWH
  SHA-256为`31BF525B56D0081DCF151EE411727F7F9EEF4A5CDE558517A15B04DDF59A8A39`；
  HWH六段地址、100 MHz FCLK1、两套复位极性和AXI INTC元数据机械校验通过。
- [x] 新增独立静态板测`phase2_l1_v16_v3_board_test.py`及实时查看器
  `phase2_l1_v16_v3_live_view.py`。实时链路沿用已冻结的18%正方形平移ROI、bbox EMA
  0.30、漏检保持3帧、5帧投票和连续2次切换；提供无手、有人无手、fist、mute、palm、
  transition六类分场景操作说明。真人/人手部分只准备代码，未代替用户采集或执行。
- [x] 生成不可覆盖的部署包
  `deploy/phase2_l1_locator_v16_classifier_v3_20260819_014644.zip`，SHA-256为
  `88D017CA9AC9E70CDAC2986559826E00546DE10B81D02785FE5F8A5585A19455`；本地全新目录
  解压后55项manifest的长度与SHA全部通过，四个板端Python入口通过语法检查。
- [x] 用户重启板端Linux后在隔离目录完成静态板测，最终`BOARD TEST RESULT: PASS`，11/11
  检查项通过。板端确认bit/HWH SHA与上述候选一致，Locator模型/描述符CRC为
  `0x21FC0351/0x21A56B2B`，四组完整Conv5 map bit-exact，AXI INTC、ping/pong、Frame ID、
  SOFT_RESET、分类器v3 HIL 8/8及GPIO回读全部通过；结果JSON SHA-256为
  `785D77A07BE1552F672BDD082F4B500A485BD18AD94DF22BD10DD13C7ABAA4F3`。

### 2026-08-19：Locator v16 + 分类器 v3 USB实时结果与演示模式

- [x] 用户完成person_no_hand、fist、mute、palm四组约90秒会话，共1,604次推理；四组
  `STALL_COUNT`、`DROP_COUNT`增量均为0。完整统计见
  `docs/locator/phase2_l1_v16_v3_realtime_results_20260819_cn.md`。
- [x] person_no_hand为3/444次raw误检（0.68%），保持后产生12个有效框和9帧稳定mute输出；
  fist/mute/palm raw检出率分别为75.58%/74.87%/81.56%，EMA/保持有效框覆盖率分别为
  90.23%/91.45%/91.17%。当前主要现场问题为fist到palm混淆、raw漏检和短时人物误检。
- [x] 已实现`phase2_l1_v16_v3_demo.py`及实时查看器`--no-save`模式：保留Jupyter实时画面、
  bbox/类别、时序滤波和LED，停止时恢复摄像头/LED并检查DROP计数，但不创建JSON/PNG，
  也不累积逐帧记录，适合`--duration 0`长时间演示。新增输出路径回归后PS测试35/35通过。
- [x] 生成含演示入口的独立部署包
  `deploy/phase2_l1_locator_v16_classifier_v3_demo_20260819_031306.zip`，SHA-256为
  `5059DD7C5F10C3ABEF9DDC76D225816A1D7756DAC4A53617FF8AAD4E2E469DDC`；全新目录解压后
  56项manifest的文件长度和SHA全部通过。
- [ ] 演示脚本尚未在板上实跑；只需将新版live-view和demo两个Python文件上传到现有v16/v3
  目录，不需要重新生成或加载bit/HWH，不影响已经通过的静态HIL结论。

### 2026-08-20：Phase 2-L1 v16 + 分类器v3工程阶段封存与绘图文档更新

- [x] 在不连接板卡、不重跑Vivado/仿真/哈希校验的前提下，建立独立封存目录
  `releases/Gesture_Phase2_L1_v16_Classifier_v3_20260820/`，收录当前RTL、Tcl/XDC、
  Locator v16与分类器v3模型、仿真和PS测试软件、bit/HWH、签核报告及既有板测结果。
- [x] 更新`docs/overall_architecture_dataflow_report_cn.md`到v0.3.0：统一为Locator v16、
  分类器v3、raw阈值`-1901`、Conv4 requant乘数`13500053`、当前实现资源和
  `+0.124/+0.024 ns`全局WNS/WHS，并同步四组长时USB会话结论。
- [x] 更新`docs/locator/phase2_l1_vivado_platform.md`，并新增
  `docs/architecture_drawing_quick_reference_cn.md`，集中列出主数据链、六路AXI地址、
  信号位宽、双缓冲、逐层周期、资源时序和Phase 2-L2留白，供后续架构绘图使用。
- [x] 本轮没有修改Phase 1 V1.0封存件和`model_package/active`，也没有把未实现的OV5640、
  DVP、PL letterbox或PL ROI画成当前硬件事实。

### 2026-08-21：Phase 2-L1 v16/v3 无界面开机自启准备

- [x] 新增独立无界面入口`ps/locator/phase2_l1_v16_v3_headless.py`：自行加载当前v16/v3
  bit/HWH与两套模型，沿用冻结的128×128 letterbox、18%正方形ROI、EMA/保持/投票契约，
  不依赖IPython、不显示或保存视频，只输出journald状态并驱动物理LED。
- [x] 无界面入口支持等待稳定USB by-id节点、摄像头读失败后的释放与重开、SIGINT/SIGTERM
  安全停止以及Locator输出缓冲释放；当前摄像头稳定节点已由用户在板上确认指向`/dev/video0`。
- [x] 新增`gesture-demo.service`和中文安装说明，生成不覆盖既有部署包的
  `deploy/phase2_l1_locator_v16_classifier_v3_autostart_20260821.zip`。新脚本语法、CLI和ZIP
  必需条目离线检查通过；尚未在板上加载Overlay、运行实时推理或执行systemd重启验收。
- [x] 首次systemd启动定位到解释器环境差异：`/usr/bin/python3`不能导入`pynq`，板端实测
  `/usr/local/share/pynq-venv/bin/python3`可同时导入`pynq`与OpenCV 4.5.4；服务模板已改用
  该PYNQ虚拟环境。故障发生在Python导入阶段，未执行Overlay或模型加载，仍待重新上板运行。
- [x] 重启日志进一步定位到开机顺序竞争：服务启动时PYNQ尚未发现FPGA Manager，Overlay
  构造报`RuntimeError: No Devices Found`并重启。模板现等待udev settle及
  `/sys/class/fpga_manager/fpga0/state`，设备出现后再延迟2秒；该修正尚待重启板测。
- [x] FPGA Manager随后实测为`operating`但服务仍提示`is the XRT environment sourced?`，
  说明解释器路径正确但systemd未加载登录Shell的XRT环境。服务现通过`/bin/bash -lc`
  启动同一PYNQ虚拟环境，复现手工测试的`/etc/profile`初始化；尚待板端服务与重启验收。

### 2026-08-23：Phase 2-L1 v16/v3 开机自启恢复与重启验收

- [x] 首次错误配置在`bootpy`/XRT尚未就绪时启动，累计至少66次
  `RuntimeError: No Devices Found`重启，导致SSH、Jupyter和板端网络表现为失联；通过JTAG
  确认ARM/PL器件可见，以一次性内存bootargs屏蔽服务恢复Linux，再删除旧自启链接完成安全
  启动。该恢复过程没有修改SD卡bootargs、bitstream、模型或推理脚本。
- [x] 正常重启后确认`bootpy.service`以`status=0/SUCCESS`完成，`eth0`恢复
  `192.168.2.99/24`，登录Shell可枚举`pynq.pl_server.embedded_device.EmbeddedDevice`；手工
  服务运行674帧，Overlay、Locator v16、分类器v3、USB摄像头和LED链路通过，停止时
  `stall/drop`均为0。
- [x] `gesture-demo.service`新增`After=bootpy.service`，启动前最多60秒检查
  `pynq.Device.devices`，并将失败策略收敛为5分钟最多3次、重试间隔10秒，避免异常时无限
  重启拖垮系统。板端`systemd-analyze verify`通过，旧unit备份为
  `/etc/systemd/system/gesture-demo.service.pre_boot_order_20260823`。
- [x] 最终正常重启验收：`gesture-demo.service`为`enabled/active`、`NRestarts=0`，
  `bootpy`结果success，FPGA Manager为`operating`，日志确认`OVERLAY PROGRAMMED`、
  `MODELS READY`、`CAMERA OPENED`并连续运行超过986帧；Jupyter服务保持active，PC访问
  `192.168.2.99:9090`成功。镜像原有`haveged`及ISC DHCP v4/v6失败不影响当前静态直连和
  推理，本轮未扩大范围处理。

### 2026-08-23：Phase 2-L1 v16/v3 快捷演示入口与最终封存

- [x] 新增板端统一快捷命令`gesture-demo`，提供`status/start/stop/logs/recent/enable/disable/reboot`
  入口并直接复用已验收的`gesture-demo.service`。正常使用只需接好USB摄像头并上电等待约
  1～2分钟；若Jupyter曾加载其他Overlay、摄像头被占用或原地重启后PYNQ枚举异常，固定用
  `gesture-demo reboot`从干净启动恢复。LED映射仍为LED0 background、LED1 fist、LED2 mute、
  LED3 palm，无手时全灭。
- [x] 快捷脚本已安装到板端`/usr/local/bin/gesture-demo`，`sh -n`、帮助入口及文件SHA通过；
  安装后服务保持`enabled/active`且`NRestarts=0`。脚本SHA-256为
  `95773D58EE2A3788577BD36F358AE13886433304F48E169B69D7EEB056749104`，板端unit SHA-256仍为
  `5A51F53F802FAF2CE5AD80763662CB0DAFD569218CEF3A3DE7686D36A6B47404`。
- [x] 板端发现早期调试遗留的`override.conf`仅重复正式unit已有的udev/FPGA等待及ExecStart，
  不包含额外有效配置；已将其可恢复地改名为`override.conf.pre_seal_20260823`并执行
  `daemon-reload`。`systemd-analyze verify`通过，当前`DropInPaths`为空，服务未中断且仍为
  `active/running`、`NRestarts=0`，因此板端生效配置与封存unit完全一致。
- [x] 更新部署生成脚本，将headless入口、systemd unit、快捷命令及安装说明纳入标准负载；
  生成60项manifest的最终部署包
  `deploy/phase2_l1_locator_v16_classifier_v3_autostart_final_20260823.zip`，SHA-256为
  `35DBE31C8B28F32306A0944664F825300CB3481650E7F997F88E5AD034B5BF89`。
- [x] 建立只读演示封存
  `releases/Gesture_Phase2_L1_v16_Classifier_v3_Autostart_20260823/`及ZIP，封存ZIP SHA-256为
  `170D2C0F92BC207540344AAE720DFA6137195DC207860C6BDCE5BE424B733100`。全新目录解压后外层
  64项和内层部署60项长度/SHA全部通过。该封存不修改RTL、bit/HWH、Locator v16、分类器v3、
  AXI地址或ABI，后续OV5640/PL后处理开发以新工程版本推进，不覆盖本目录。

### 2026-08-23：Phase 2-L2 OV5640 前端合并开发

- [x] 新增`rtl/camera/`完整独立子系统：`ov5640_capture`在PCLK域参数化抽取
  YUYV/UYVY的Y分量；29-bit坐标token经1024深度Gray指针异步FIFO进入100 MHz；
  `pl_letterbox_640x480`固定执行5:1 nearest得到128×96并上下各补16行0。
- [x] 新增32 KiB camera专用Locator输入ping/pong BRAM、PS/camera输入数据MUX、
  100 kHz SCCB写主机及ABI `0x00000400`的AXI4-Lite控制面。逐缓冲Frame ID、valid/release、
  busy期间输入源保护、drop/format计数和帧发布sticky IRQ已经形成明确所有权语义。
- [x] 五组自检全部通过：异步FIFO顺序/满空、YUYV/UYVY字节相位、SCCB ACK/NACK、
  两帧完整DVP→CDC→letterbox→ping/pong逐Word比较，以及AXI AW/W独立到达、SLVERR和
  buffer release语义。按本轮要求未增加部署哈希验证。
- [x] 完整`camera_l2_top`在XC7Z020上的OOC综合为411 LUT、681 FF、9 BRAM Tile、0 DSP；
  PCLK 48 MHz WNS/WHS为`+16.002/+0.164 ns`，100 MHz为`+2.212/+0.164 ns`。原先
  `capture_enable`直跨PCLK和BRAM异步控制已修正；CDC仅剩异步FIFO Gray指针提示，DRC
  仅剩OOC未放置PS7的环境性`ZPS7-1`。
- [x] 新增`docs/camera/phase2_l2_frontend_design_cn.md`并更新总架构底稿。当前实现只覆盖
  OV5640全帧到Locator输入，不声称已经有camera分类闭环或可上板bitstream。
- [x] 实际模块、3.3 V电气边界和JA/JB逐针接线已于2026-08-24冻结，见下一条日志。
- [ ] 继续完成新XDC、XCLK、RESET/PWDN、SCCB读ID/初始化表、Y字节相位和VSYNC极性，
  再接入新Block Design并实现PS下发bbox的后续帧ROI crop/resize。

### 2026-08-24：OpenSOC OV5640_V1.2硬件与接线基线冻结

- [x] 实物模组确定为OpenSOC OV5640_V1.2：3.3 V、8-bit DVP、20针2×10/2.54 mm，
  非MIPI；20针方向和D0～D7、PCLK、HREF、VSYNC、XCLK、SCCB、RST/PWDN定义已记录。
- [x] 固定PYNQ-Z2双PMOD接线：D0～D6和PCLK使用JA，D7、同步、XCLK、SCCB、RST/PWDN
  使用JB。JA/JB到Y18/Y19/Y16/Y17/U18/U19/W18/W19/W14/Y14/T11/T10/V16/W16/
  V12/W13的映射及LVCMOS33已由Vivado 2026.1官方PYNQ-Z2 Board Part复核。
- [x] 新增`docs/camera/opensoc_ov5640_v1_2_hardware_baseline_cn.md`，统一记录逐针表、
  3.3 V/共地/上拉/去耦规则、新XDC计划、时钟与CDC策略、L2架构、已完成证据、待办和
  首次上板检查顺序；同步更新camera设计说明、采购说明和总架构底稿。
- [x] 明确`hardware_release/constraints/pynq_z2_timing_and_pins.xdc`中的OV5640管脚是与
  当前接线不一致的历史占位映射，不修改封存目录，也不允许新L2工程复制使用；活动XDC
  当前不含OV5640端口，保持原状。
- [x] 继承2026-08-23的验证结论：五组camera自检已通过；完整camera子系统OOC综合为
  411 LUT、681 FF、9 BRAM Tile、0 DSP，PCLK 48 MHz WNS/WHS `+16.002/+0.164 ns`，
  100 MHz WNS/WHS `+2.212/+0.164 ns`。本轮只更新文档，未重新运行RTL仿真或综合。
- [ ] 下一步只做必要L2集成：SCCB读芯片ID、AXI控制RST/PWDN、24 MHz XCLK、camera
  128×128 PS读回、新独立BD/XDC和第三路IRQ；芯片ID与图像链路通过后再接Locator，
  最后实现后续帧PL ROI，不覆盖Phase 2-L1封存版本。
- [ ] 上板冻结项：芯片ID预期`0x300A=0x56/0x300B=0x40`、RST/PWDN极性、VGA/YUV422
  初始化表、YUYV/UYVY字节相位、VSYNC极性、PCLK采样沿/实际频率和DVP输入delay。

### 2026-08-24：Phase 2-L2独立工程、控制面与综合候选完成

- [x] 在不覆盖Phase 1和Phase 2-L1封存件的前提下创建独立
  `vivado_phase2_l2_ov5640/Gesture_Phase2_L2.xpr`及`phase2_l2` Block Design。新增camera
  AXI段`0x43C10000/4 KiB`、第三路camera IRQ、PS/camera Locator输入MUX、独立camera
  PCLK复位域和100 MHz到24 MHz的MMCM+ODDR XCLK；BD validate与output products生成通过。
- [x] 新增OpenSOC OV5640_V1.2活动XDC，按已冻结JA/JB映射使用20个PL I/O并将U18/MRCC
  定义为保守48 MHz `ov5640_pclk`。PCLK与50/100 MHz时钟组异步；DVP输入delay故意留待
  首板量测后冻结。首次综合暴露XDC条件命令不受支持并漏建PCLK时钟，已改为直接约束且
  最终报告机械确认`clk_fpga_0/clk_fpga_1/ov5640_pclk`均存在。
- [x] camera ABI升级到`0x00000401`：安全复位默认保持RESET_N=0/PWDN=1，XCLK锁定前拒绝
  capture；SCCB支持16-bit寄存器读写、ACK/NACK和芯片ID读回；新增128×128双缓冲PS调试
  Word读回、camera→Locator预加载提交、busy期间输入源保护及缓冲所有权控制。
- [x] 增加Linux/ST官方OV5640寄存器定义来源整理的VGA/YUYV初始化表、板端安全上电/芯片ID/
  PGM读回/camera→Locator测试入口，以及`gesture-demo.service`活动状态拒绝保护。现有服务
  和板卡均未被本轮访问或停止，板测必须先由用户显式stop+disable服务。
- [x] 五组camera RTL自检全部通过；camera PS测试5/5、Locator驱动测试11/11通过。更新后的
  camera模块级综合为490 LUT、732 FF、9 BRAM、0 DSP。L2全顶层综合为15,655 LUT
  （29.43%）、13,478 FF（12.67%）、65 BRAM（46.43%）、22 DSP（10.00%）、20 PL I/O、
  1 MMCM；综合WNS/WHS为`+0.621/+0.041 ns`，无Error/Critical Warning。CDC仅两条异步FIFO
  Gray指针提示；DRC只含SCCB SCL未读回和既有CNN DSP流水建议。
- [x] 当前L2实现后资源预计14.4～15.2k LUT、12.0～13.0k FF、65 BRAM、22 DSP。后续流式
  nearest ROI预计再增加0.6～1.2k LUT、0.4～0.9k FF、2～3 BRAM、0～2 DSP；bilinear方案
  预计增加1.0～1.8k LUT、0.8～1.4k FF、3～5 BRAM、4～8 DSP。VGA整帧双缓冲BRAM不可行，
  后续维持流式ROI；主要工程风险为100 MHz布线余量而非容量。
- [ ] 按用户要求，本轮未运行implementation、write_bitstream或任何板端命令。待用户执行
  完整实现/bitstream后，依次确认芯片ID、RESET/PWDN极性、PCLK/VSYNC/Y字节相位、PGM图像、
  camera→Locator，并依据实测补齐DVP输入delay；实现后WNS/WHS、route、bus skew和DRC必须
  作为最终时序准入证据。

### 2026-08-24：PS控制加固与Locator 8输出lane并行分支

- [x] 原工作区最初没有Git元数据；先将Phase 2-L2现状提交为基线`0f2eeec`，建立
  `baseline/current-20260824`保护引用，再从该基线创建
  `feature/ps-hardening-locator-8lane`。现行Phase 2-L1封存件和未上板的L2候选均未被覆盖。
- [x] 保留原`locator_cnn_engine.v`作为标量回退，新建固定8输出通道lane引擎。每个tap
  广播一个激活值到8组权重/INT32累加器；模型存储提供8个镜像读口，层间激活按通道低3位
  分成8个4 KiB bank；尾组按实际输出通道屏蔽。Requant按lane串行，Conv5输出按lane串行
  写入单端口外部BRAM，因此不增加外部AXI/CHW数据契约。
- [x] 4组整网逐层bit-exact、计数和watchdog仿真全部通过；每组固定
  `1,641,748 cycle@100 MHz = 16.41748 ms`，相对标量核`8,872,324 cycle`为`5.40×`。
  4-lane机械估算约`2.56 M cycle = 25.6 ms`；考虑分类器约`7.8 ms`以及PS/camera开销，
  选择8-lane为当前候选。
- [x] 顶层真实CNN的双帧ping/pong、AXI模型写入/CRC、CHW输出阈值回归通过；Locator控制
  外壳、BRAM adapter、IRQ同步、CRC和双缓冲骨架回归保持通过。
- [x] 8-lane Locator OOC综合0 Error/0 Critical Warning：3,417 LUT、2,455 FF、
  33 BRAM Tile、2 DSP，100 MHz WNS/WHS`+0.138/+0.256 ns`。当前关键路径余量较紧；若L2
  全顶层不收敛，优先在激活bank地址请求路径增加一级寄存器，不盲目扩大lane数。
- [x] PS camera驱动新增启动前陈旧buffer释放、统一`release_all_buffers()`和安全
  `shutdown()`；bring-up用`try/finally`保证异常/成功均释放camera与Locator所有权并恢复
  RESET_N=0/PWDN=1。服务门禁同时拒绝`active`或`enabled`的`gesture-demo.service`，避免
  自动重启抢占板卡。使用工程bundled Python执行7项单元测试全部通过。
- [x] 当前证据只到RTL仿真、PS单元测试和Locator OOC综合；未重跑Phase 2-L2全顶层综合，
  未运行implementation、write_bitstream或任何板端命令，Phase 2-L2仍保持“未上板测试”。
- [ ] 后续顺序：先重建L2工程并跑全顶层综合；若setup不足则加bank地址流水；再运行
  implementation/bitstream并按芯片ID→极性/时序→PGM→camera→Locator顺序上板；链路稳定后
  优先开发PS下发下一帧ROI描述符的PL nearest crop/resize，bbox解码、EMA/hold和类别投票
  暂留PS，避免在定位精度未签核前过度硬化。

### 2026-08-24：OV5640同步极性根因修正

- [x] 根据本次上板反馈，图像链路根因定位为OV5640同步极性配置错误；当前OpenSOC
  OV5640_V1.2硬件与既有`VSYNC_ACTIVE_HIGH=1`采集RTL要求寄存器`0x4740=0x20`，原初始化表
  中的`0x22`不适配当前组合。
- [x] PS初始化表已改为`(0x4740, 0x20)`，并在Fake-MMIO VGA配置单元测试中加入精确断言，
  防止后续引用其它平台初始化表时回退到`0x22`；同步更新L2设计、总架构与上板排障说明。
- [ ] 本次只修正PS寄存器配置，不改变RTL、BD、XDC、资源或时序结论，未重跑Vivado或
  代替用户执行完整图像/camera→Locator上板验收。

### 2026-08-24：Phase 2-L2 next-SOF ROI与分类闭环候选收口

- [x] 接收并固化本轮实板证据：`0x4740=0x20`后SCCB ID为`0x5640`，128×128 PGM有效、
  padding为0，camera→Locator输出`5×16×16 int32` raw map；真实手势出现
  `DETECTED 1849`（阈值`-1901`）及有效bbox。该证据覆盖前端至Locator，不覆盖本轮新增ROI。
- [x] 新增PS描述符驱动的next-SOF流式ROI：`x0/y0/side/tag`在下一源帧SOF原子接受，
  采用`floor(dst*side/32)` nearest生成32×32 Gray8，4像素小端打包为256个Word；
  通过独立双时钟ROI BRAM送入现有分类器，分类器原ABI `0x00010000`保持不变。
- [x] camera ABI升级为`0x00000402`，增加ROI描述符、armed/busy/done/error、completed tag、
  source frame和classifier source/busy所有权保护；camera IRQ寄存器化后CDC同步器前无组合逻辑。
- [x] 新增`phase2_l2_closed_loop.py`：camera→8-lane Locator→Top-1/bbox→EMA/hold→18%正方形
  →next-SOF PL ROI→分类器v3→类别投票；有效检测不足`--min-classified`时明确失败，不伪报PASS。
- [x] 验证通过：camera RTL 7/7（含ROI逐Word bit-exact和双时钟BRAM）、camera Python 9/9、
  Locator 4组整网逐层bit-exact及顶层AXI/CRC/ping-pong/阈值回归。Python交付脚本`py_compile`通过。
- [x] 初次全顶层综合WNS为`-0.037 ns`；在8-lane激活bank地址前加入prime/prefetch请求寄存器后，
  每帧变为`1,669,396 cycle = 16.69396 ms`（增加1.68%，相对标量加速5.315×），
  Locator OOC为3,401 LUT、2,483 FF、33 BRAM、2 DSP，WNS/WHS`+0.267/+0.252 ns`。
- [x] 最终L2全顶层综合通过：18,205 LUT（34.22%）、15,288 FF（14.37%）、79.5 BRAM
  （56.79%）、20 DSP（9.09%）；WNS/WHS`+0.019/+0.041 ns`，CDC 0 Critical，只有两条
  异步FIFO Gray指针Warning。最差setup为Locator requant→pool比较链，ROI不是关键路径。
- [x] 预计实现后约16.8～18.2k LUT、13.7～15.3k FF、79.5 BRAM、20 DSP；后续ILA临时
  预留2～6 BRAM，bilinear预留4～8 DSP，多ROI/跟踪器预留0.5～1.5k LUT和1～3 BRAM。
- [ ] 按用户边界，本轮未访问板卡、未停止现有开机服务，也未运行implementation或生成
  bitstream。下一步由用户先执行实现后时序/route/DRC门禁，再停止并disable旧服务，完成
  ID→PGM→camera→Locator→PL ROI→分类器板测及DVP input delay量测。

### 2026-08-25：Phase 2-L2临时DVP输入约束、实现收束与功能RC封存

- [x] 接收并绑定旧功能候选实板证据：bit/HWH SHA-256分别为
  `04ac68534adf8d1d72a6d175a2f807eacf0c089046781e2d05ff83d689af2c07`和
  `5f4a73324bc1f9202be99e6dc3122212c057d98f7d2a8f1e908878d7b92a7b89`；
  `phase2_l2_closed_loop.py --iterations 10 --min-classified 1`完成9/10次ROI/分类运行，
  一次`NO DETECTION`按契约跳过，next-SOF源帧关系和`palm`输出正常。
- [x] 因暂时无示波器，按用户授权采用临时DVP工程窗口：PCLK最坏48 MHz（20.833 ns），
  `0x4740[5]=1`对应接收端上升沿采样，源端按下降沿发射，D[7:0]/HREF/VSYNC统一
  `set_input_delay -clock_fall -min 2.000 -max 8.000 ns`。OV5640公开资料未给出可直接签核的
  PCLK-to-data保证值，因此该窗口明确保留“待示波器替换”例外。
- [x] 修正Vivado 2026.1不接受XDC `unset`的问题后，全顶层综合通过：WNS/WHS
  `+0.019/+0.041 ns`，0 Error/0 Critical Warning。
- [x] 完整implementation/bitstream通过：全局WNS/WHS `+0.223/+0.012 ns`，DVP输入专项
  WNS/WHS `+3.414/+7.917 ns`；10/10个DVP捕获寄存器为`IOB=TRUE`并落入
  `ILOGICE2.IFF`；27,956个可路由网络全部完成，bus skew 10项全MET，DRC 0 Error/
  0 Critical Warning；CDC保持30条Info和2条已知异步FIFO Gray指针Warning。
- [x] post-route资源为17,138 LUT（32.21%）、14,171 FF（13.32%）、79.5 BRAM Tile
  （56.79%）、20 DSP（9.09%）。剩余67.79% LUT、86.68% FF、43.21% BRAM和90.91% DSP；
  后续ILA估计增加0.2～0.6k LUT/2～6 BRAM，bilinear估计增加0.4～0.9k LUT/
  0.4～0.8k FF/4～8 DSP，多ROI/跟踪估计增加0.5～1.5k LUT/FF和1～3 BRAM。
- [x] 新候选bit/HWH SHA-256为
  `1fc2a30c4fe3ed31f28468064cc33a737b626c537749156aa2b08cdd94fe2e76`和
  `6982b79cf5408cea04be80dd09a702c98f916642c0cdb05e7be7539bff4c1c8c`。生成独立部署目录
  `deploy/phase2_l2_ov5640_roi_timing_rc_20260825/`及ZIP，ZIP SHA-256为
  `dc9df6973cbbf41b888041e31cbd83be6cd4999bb6c3cf075770e2f60e52dda3`，清单含18项。
- [x] 精确新哈希板测完成：部署ZIP/bit/HWH SHA-256均与PC端清单一致；SCCB ID `0x5640`、
  有效PGM（min/max/mean `0/255/94.42`、padding `0/0`）、camera→Locator及10迭代闭环通过；
  闭环完成7/10 ROI/classifier，3次为正常`NO DETECTION`，源帧固定晚2帧且无timeout/error/
  tag mismatch/SLVERR/stall。已封存为“功能RC，DVP实测时序例外保留”；最终无例外时序版
  仍待示波器量测并回填输入延迟。
- [x] 建立只读封存目录`releases/Gesture_Phase2_L2_OV5640_ROI_Functional_RC_20260825/`及同名ZIP；
  `RELEASE_SHA256.json`以104项覆盖其余文件，目录/ZIP均为105个文件并逐项复算通过，清单
  SHA-256为`3877e46e5817308c13a553d34cd79f26f7386d739080b3cc9fe8c982b4e1ddb8`；最终封存ZIP
  SHA-256为`930dfe7f5cbef73e2300c41c163230633d9c7a053f44cc211c15bd172a80e3f3`。
### 2026-08-25：Phase 2-L2 8-lane Locator、PL Top-1与自启动候选完成

- [x] 在`feature/ps-hardening-locator-8lane`原位完成开发；未切换、覆盖或改写已封存的L1与
  `Gesture_Phase2_L2_OV5640_ROI_Functional_RC_20260825`。新候选保持camera ABI
  `0x00000402`、Locator ABI`0x00000302`和分类器ABI`0x00010000`。
- [x] 新增双缓冲`locator_top1_reducer`：在Conv5 CHW写流中以signed confidence选择首个Top-1，
  保存cell与confidence/dx/dy/width/height五个raw int32；`0x0060=0x54315231 (T1R1)`，
  缓冲0/1摘要位于`0x0064..0x0090`。完整5 KiB raw map保留，阈值、尺度、bbox、EMA/hold
  和类别投票继续由PS/manifest控制。
- [x] PS闭环改用`LocatorDriver.wait_top1()`与`decode_top1_raw_values()`；新增
  `phase2_l2_headless.py`、systemd unit、`gesture-demo`控制命令和幂等安装器。SIGTERM路径
  释放camera/Locator所有权、关闭OV5640并恢复LED；服务等待FPGA Manager/PYNQ Device后启动。
- [x] RTL回归通过：Locator外壳/AXI/CRC/double-buffer回归通过；真实CNN双帧仿真逐帧
  bit-exact，两个输出bank的PL摘要与完整黄金map Top-1一致。PS回归为Locator 36/36、
  camera/bring-up 9/9，交付Python `py_compile`通过。Windows环境未提供bash/sh，两个POSIX
  shell脚本按LF格式静态复核，实际systemd执行留给板端验收。
- [x] Locator OOC为3,692 LUT、2,986 FF、33 BRAM Tile、2 DSP，100 MHz WNS/WHS
  `+0.267/+0.252 ns`，0 Error/0 Critical Warning。整机综合为18,499 LUT、15,791 FF、
  79.5 BRAM、20 DSP，WNS/WHS`+0.019/+0.041 ns`。
- [x] 完整implementation/bitstream通过：post-route 17,427 LUT（32.76%）、14,674 FF
  （13.79%）、79.5 BRAM（56.79%）、20 DSP（9.09%）；全局WNS/WHS`+0.116/+0.050 ns`，
  DVP专项`+3.414/+7.917 ns`，10/10捕获寄存器位于IOB，28,722个网络全路由，bus skew MET，
  DRC 0 Error/0 Critical Warning，CDC仅30条Info与2条已知Gray指针Warning。
- [x] 相对已封存timing RC只增加289 LUT、503 FF，BRAM/DSP不变；PL摘要payload将每帧
  Locator输出读取从5,120 Byte降到24 Byte，减少99.53%。当前剩余67.24% LUT、86.21% FF、
  43.21% BRAM、90.91% DSP；后续ILA估计2～6 BRAM，bilinear估计4～8 DSP，多ROI/跟踪
  估计0.5～1.5k LUT/FF与1～3 BRAM，建议至少保留10 BRAM和8 DSP。
- [x] 新bit/HWH SHA-256分别为
  `87b0260b42e66f3659e07f9d7cdc199d4a9fd090eb7f2890c6914d174b8d13d1`和
  `ed5864d776cc194587a23e37754915f365efa878777e30b9bf469242c1def786`。独立部署目录/ZIP为
  `deploy/phase2_l2_ov5640_8lane_top1_autostart_20260825`，ZIP SHA-256为
  `a539c172f5fba88b6c8513fa82c151370b10924fd919970e5b16eeaf02813d64`；清单23项覆盖其余
  文件，目录/ZIP均24项，ZIP无反斜杠路径，并生成同名`.sha256`旁路文件。
- [x] 新版本已完成实板验收：systemd实际目录
  `/home/xilinx/gesture_demo_l2_8lane`中的bit/HWH SHA-256与候选精确一致；重启后服务为
  `enabled`、`active/running`、`NRestarts=0`、`ExecMainStatus=0`。journal证据至少覆盖
  2,531轮、372次分类，`background/fist/mute/palm`四类均出现，未见timeout、Traceback、
  tag mismatch、SLVERR或stall。DVP 2～8 ns仍是无示波器阶段的临时工程窗口，最终无例外
  时序签核待实测替换。

### 2026-08-25：Phase 2-L2 8-lane / PL Top-1 / autostart功能RC封存

- [x] 板端实际服务目录中的bit/HWH SHA-256分别为
  `87b0260b42e66f3659e07f9d7cdc199d4a9fd090eb7f2890c6914d174b8d13d1`和
  `ed5864d776cc194587a23e37754915f365efa878777e30b9bf469242c1def786`，与部署包清单一致；
  部署ZIP SHA-256保持
  `a539c172f5fba88b6c8513fa82c151370b10924fd919970e5b16eeaf02813d64`。
- [x] systemd开机自启与持续端到端运行通过：服务零重启、主进程状态0；观测末值为
  `runs=2531`、`classified=372`、`no_detection=2159`。最大瞬时`loop_ms=1443.4`后继续运行，
  未触发重启或错误，记录为非阻塞性能尖峰。
- [x] 建立独立只读封存目录
  `releases/Gesture_Phase2_L2_OV5640_8Lane_Top1_Autostart_Functional_RC_20260825/`及同名ZIP；
  清单覆盖其余143项，目录/ZIP共144项。封存ZIP SHA-256为
  `49e4b829819202cabed1b508f715baa0eef29a8a5ad4c815fdf7fb3a91375ce5`。
- [x] 状态标记为“Phase 2-L2 8-lane / PL Top-1 / systemd autostart功能RC已封存”。功能、
  实现时序、资源和自启门禁均已闭合；唯一保留项是DVP输入延迟需在示波器可用后，以实测
  PCLK-to-data及板级偏斜替换当前2～8 ns临时窗口，再形成最终无例外时序发布。

### 2026-08-25：封存后PS类别确认2/3/3调优候选

- [x] 定位到“配置2次但体感约4次”的根因：原`ClassVoteSwitch`先做5帧多数投票，再对
  voted结果做2次确认；从稳定旧类别切换时，通常需要约4个连续新原始分类结果。保留该旧类
  供L1工具使用，新增L2专用`ClassConfirmSwitch`，直接统计连续原始候选。
- [x] 新规则为`fist/palm/mute=2`次、`background=3`次、Locator `none=3`次；候选改变即
  从1重新计数。headless不再在首次none时reset或熄灯，前两次保持原输出，第3次才清空；
  none计数直接绑定Locator未检出帧，不与bbox hold叠加。
- [x] `phase2_l2_closed_loop.py`与`phase2_l2_headless.py`均已接入新滤波器，启动日志输出
  `confirm=gesture2/background3/none3`；自启及上板文档同步更新。该变化仅涉及PS Python，
  未修改RTL、BD、XDC、ABI、模型、bit或HWH，因此不需要重新综合/实现。
- [x] 聚焦回归通过：`test_phase2_l1_pipeline.py`共17项全部通过，覆盖手势2次、background
  3次、none 3次及不同候选重置计数；L2 closed-loop/headless与包内Python均通过
  `py_compile`。
- [x] 生成不覆盖封存件的新候选
  `deploy/phase2_l2_ov5640_8lane_top1_autostart_confirm2_3_20260825.zip`，SHA-256为
  `f29dd2190f59500d5f25dfc04a62011a0c256986425f49936d6614a2c7c420ac`；清单23项、ZIP
  24项且路径全为正斜杠。包内bit/HWH仍精确绑定已封存的`87b0...d13d1`/`ed58...786`。
  原Functional RC目录/ZIP保持只读且未修改。
- [x] 精确新目录`/home/xilinx/gesture_demo_l2_8lane`完成30轮闭环板测：连续2次`fist`在
  第2次切换为`fist`，连续2次`palm`在第2次切换为`palm`，从`fist`开始连续3次Locator
  未检出后输出才由`fist`切换为`none`；被其它类别或未检出打断的`mute/background`候选
  保持`pending`并重新计数，符合2/3/3契约。闭环完成20/30次ROI/classifier，其余为正常
  `NO DETECTION`。
- [x] 手动headless板测连续执行60 s、15 s和120 s，三次启动均明确打印
  `confirm=gesture2/background3/none3`；累计1,402轮、648次分类和754次未检出，输出覆盖
  `background/fist/mute/palm/none`，camera drop、Locator drop/stall增量均为0。两次长测的
  `camera_format_delta`分别为28和21，15 s复测为0；该计数不归因于本轮纯PS确认策略修改，
  但与既有DVP 2～8 ns临时时序例外一并保留并在示波器可用后复核。
- [ ] 当前状态升级为“PS调优手动板测通过”；最终独立封存仍需安装该目录的systemd unit、
  重启后确认`enabled`、`active/running`、`NRestarts=0`、`ExecMainStatus=0`，并从journal确认
  策略标记及无Traceback/timeout/SLVERR/stall。通过后再建立新的Confirm2/3功能RC，不能
  覆盖原8-lane / PL Top-1 / autostart功能RC。

### 2026-08-25：Confirm2/3自启冷启动SCCB重试加固候选

- [x] 首次Confirm2/3重启验收未通过最终门禁：服务虽为`enabled`、`active/running`且当前
  `ExecMainStatus=0`，但首次完整OV5640配置发生SCCB NACK并留下Traceback，systemd随后恢复，
  因此`NRestarts=1`。第二次进程成功读到`0x5640`并打印正确2/3/3策略；该结果证明自动恢复
  可用，但不能作为零重启封存证据。
- [x] `phase2_l2_headless.py`新增仅限启动期的3次有界初始化：每次SCCB `OSError`后执行
  camera安全shutdown，等待1秒，再从power-on、芯片ID和完整VGA/YUYV配置重新开始；持续
  3次失败仍抛出原异常。未修改底层Camera驱动、RTL、BD、XDC、ABI、模型、bit/HWH或
  2/3/3类别确认策略。
- [x] 聚焦回归通过：Camera/headless 8项单元测试覆盖单次NACK进程内恢复及持续NACK失败，
  交付Python `py_compile`通过；2/3/3 pipeline 17项回归保持通过。无需重新综合、实现或
  生成bitstream。
- [x] 生成独立候选
  `deploy/phase2_l2_ov5640_8lane_top1_autostart_confirm2_3_sccb_retry3_20260825.zip`，
  SHA-256为`dd15e4731185256dbe9e1b2a834e5b422769bb9df22bc38cb6faf094115ef4a3`；ZIP 24项、
  清单23项全部匹配且无反斜杠路径。bit/HWH继续绑定`87b0...d13d1`/`ed58...786`。
- [x] retry3精确部署完成重启验收：服务为`enabled`、`active/running`、`NRestarts=0`、
  `ExecMainStatus=0`，启动日志读到`0x5640`并打印`confirm=gesture2/background3/none3`；持续
  至少500轮、5次分类且进程未退出，未出现Traceback/timeout/SLVERR/stall。四类输出由同一
  retry3部署前的三段手动headless证据覆盖，2/3/3切换由30轮闭环证据覆盖。
- [x] 建立新的独立只读封存
  `releases/Gesture_Phase2_L2_OV5640_8Lane_Top1_Autostart_Confirm2_3_SCCB_Retry3_Functional_RC_20260825/`
  及同名ZIP；清单覆盖其余144项，目录/ZIP共145项，逐项SHA与ZIP内容复算均为0错误，
  所有目录文件只读。封存ZIP SHA-256为
  `9de0a2740b954161b26ed415e4d1fe801fa8b73cdc4b429934c6bc4d36b6e922`；原8-lane功能RC ZIP
  保持`49e4...75ce5`未变。
- [x] 状态标记为“Confirm2/3 + SCCB retry3 systemd autostart功能RC已封存”。该版本继续
  精确绑定部署ZIP`dd15...f4a3`及bit/HWH`87b0...d13d1`/`ed58...786`；DVP 2～8 ns临时
  时序例外继续保留，示波器实测前不升级为最终无例外时序版。

### 2026-08-26：Phase 2-L2同帧128×128 BRAM ROI候选完成PC门禁

- [x] 从现有工作树建立独立分支`codex/phase2-l2-sameframe128-roi`；旧release目录、ZIP、
  bit/HWH及板端旧部署路径未覆盖。新增版本索引`docs/PROJECT_STRUCTURE_AND_VERSIONS_CN.md`，
  以`source/docs/reports/deploy/releases`职责分类，不移动或重写历史封存件。
- [x] 新增`same_frame_roi_128x128`：Locator完成帧N后保持原camera buffer，复用其128×128
  BRAM读口产生32×32 nearest ROI，完成后再release。仲裁为Locator优先，裁剪失去grant时
  暂停；不新增BRAM/DSP，约2050 cycle@100 MHz，即20.5 µs。旧`next-sof-vga`路径保留为
  显式A/B回退。
- [x] Camera ABI升级为`0x00000403`；AXI新增同帧mode/buffer选择与busy状态。PS闭环和headless
  默认`same-frame-128`，每次分类前强制`ROI_SOURCE_FRAME_ID == locator Frame ID`；仍保留
  timeout、tag、所有权和必要几何门禁，不增加逐帧CRC或冗余模型校验。
- [x] camera RTL自检8/8、Python单元测试10/10及交付Python `py_compile`通过。同帧TB覆盖
  256 Word bit-exact、buffer身份、busy overlap、grant暂停、重复写、非法描述符和watchdog。
- [x] camera OOC为1,015 LUT、1,473 FF、9 BRAM、0 DSP，100 MHz WNS `+1.042 ns`；相对旧
  camera OOC增加183 LUT、290 FF，BRAM/DSP不变。全顶层综合为18,683 LUT、16,081 FF、
  79.5 BRAM、20 DSP，WNS/WHS `+0.019/+0.041 ns`。
- [x] 完整implementation/write_bitstream通过：post-route为17,632 LUT（33.14%）、14,992 FF
  （14.09%）、79.5 BRAM（56.79%）、20 DSP（9.09%）；全局WNS/WHS `+0.140/+0.014 ns`，
  DVP专项`+3.414/+7.917 ns`，29,167/29,167可路由网络完成，bus skew MET，DRC 0 Error，
  DVP捕获寄存器10/10位于IOB。
- [x] 新bit/HWH SHA-256分别为
  `e7487df16110d63c86ee313c2c34f70154a515c328a7475089045ef1f68528ad`和
  `035dd48cce4f594e71c37ea1eafe1100a3d0f8e2bfb9c51467665fdf780535fb`。
- [x] 生成独立候选
  `deploy/phase2_l2_ov5640_8lane_top1_sameframe128_confirm2_3_sccb_retry3_20260826.zip`，
  SHA-256为`a1f8318436e4959608ed255990969e2256303ce9fb0a238e86af8e8381c84e7f`；清单24项零错误，
  ZIP 25项且无反斜杠路径。板端目录和单元分别隔离为
  `/home/xilinx/gesture_demo_l2_sameframe128`与`gesture-demo-sameframe128.service`。
- [x] 同帧30轮闭环完成16次有效ROI/classifier运行，16条分类记录全部满足
  `locator_frame == roi_source_frame`；60秒headless完成704轮、448次分类，camera/Locator
  drop与Locator stall均为0。首次SCCB NACK由进程内retry3恢复。
- [x] 独立systemd重启后为enabled、active/running、`NRestarts=0`、`ExecMainStatus=0`，
  日志持续至少1,867轮。接受为Functional RC Draft 1；`camera_format_delta=1`和DVP 2～8 ns
  临时时序例外继续保留，本稿不重新声明分类器精度。
- [x] 建立独立只读封存目录
  `releases/Gesture_Phase2_L2_OV5640_8Lane_Top1_SameFrame128_Confirm2_3_SCCB_Retry3_Functional_RC_Draft1_20260826/`
  及同名ZIP。`RELEASE_SHA256.json`覆盖其余160项，目录/ZIP共161项；目录清单、ZIP逐条目
  哈希、正斜杠路径和161/161只读属性均通过独立复算。封存ZIP SHA-256为
  `558190d37a2b06b914c7a8337ba4b12c5ec994ffe7bce555a15ddb8b9ee5b833`。
- [x] 原8-lane功能RC、Confirm2/3+retry3功能RC和旧retry3部署ZIP哈希分别保持
  `49e4b829...75ce5`、`9de0a274...b6e922`和`dd15e473...ef4a3`，未被本稿覆盖。

### 2026-09-03：Phase 2-L2当前硬件实时画面与框图调试工具

- [x] 新增`ps/camera/phase2_l2_live_view.py`，严格绑定Camera ABI `0x00000403`、Locator ABI
  `0x00000302`、classifier ABI `0x00010000`、PL Top-1 capability `0x54315231`以及当前
  BIT/HWH完整SHA-256；启动前同时拒绝后台gesture服务占用硬件。
- [x] 左图显示PL实际保留的128x128 Locator Gray8输入并叠加绿色原始框、黄色EMA框和青色
  18%扩展正方形ROI；右图按RTL `floor(dst*side/32)`规则重建32x32分类输入。每次分类前仍由
  硬件寄存器强制校验`ROI_SOURCE_FRAME_ID == Locator frame_id`。
- [x] 记录有效区亮度、置信度/阈值、贴边状态、原始/确认类别、分项耗时和硬件计数，支持
  Notebook实时刷新、周期PNG及逐帧JSON；明确当前硬件不保存640x480全帧，预览通过4096次
  AXI-Lite诊断读回，帧率不能作为正常闭环吞吐率。
- [x] 新增中文手册`docs/camera/phase2_l2_live_view_cn.md`与专用打包器
  `scripts/prepare_phase2_l2_live_debug_bundle.ps1`。Tier 1聚焦回归共50项全部通过：实时工具
  9项、Camera 10项、OV5640 guard 3项、Locator 11项、pipeline 17项；包内脚本`py_compile`
  和`--help`通过。
- [x] 生成独立调试包`deploy/phase2_l2_sameframe128_live_debug_20260903.zip`，SHA-256为
  `6068c1592ab84b8e647b55cb17342c9477b511edfb132ba568938fce263a45dc`；清单26项全部复算
  一致，ZIP共27项且包含查看器和中文手册，包内BIT/HWH仍精确为`e748...28ad`/`035d...35fb`。
  本次只新增PS调试代码、文档与打包脚本，未修改RTL/BD/XDC，无需重综合。
- [ ] 仍需按`docs/camera/phase2_l2_live_view_cn.md`在PYNQ-Z2实机完成短时30帧及典型光线/距离/入框条件观测；
  本工具用于根因诊断，不重新声明模型准确率，也不替代正式闭环或HDMI性能验收。

### 2026-09-04：OV5640 DVP PCLK极性实机修正

- [x] 保持接线、BIT/HWH和测试方法不变，仅将`0x4740`由`0x20`改为`0x00`。20秒
  camera-only对照由49个有效帧、74次等待超时、189个格式错误改善为237个有效帧、
  0超时、0格式错误，确认主要问题来自DVP PCLK采样相位。
- [x] 实时画面复核确认棋盘纹和横向错位已经消失，识别表现大幅提高；当前仍有个别噪点。
  本次未进行带标签逐帧统计，因此只记录现场改善，不声明具体准确率。
- [x] 本地相机初始化表固定为`(0x4740, 0x00)`，对应Fake-MMIO单元测试同步更新。
  本轮仅更新PS配置与日志，不修改RTL、XDC、BIT/HWH或历史封存文件。

### 2026-09-05：算法交接阈值 -3383 最小部署更新

- [x] 按算法端 `PHASE2_L1_PL_THRESHOLD3383_HANDOFF_CN.md`，仅将全硬件化 Locator 的
  原始有符号 Top-1 置信度阈值由 `-1901` 改为 `-3383`；判定保持为
  `detected = (top1_confidence >= -3383)`。Locator/classifier 模型、EMA、18% 扩框、
  同帧 ROI 和现有 2/3/3 类别确认均未改动，也未加入五帧投票、失败采集、CRC 或哈希验证。
- [x] bbox 位精确自检补充阈值边界：`-3384` 不检出，`-3383` 与 `-3382` 检出；全套六组
  autonomous XSim 自检全部 PASS。
- [x] 重新综合、实现并生成 BIT/HWH。综合 WNS/WHS 为 `+0.019/+0.041 ns`；实现后
  WNS/WHS 为 `+0.232/+0.024 ns`，DVP 输入 WNS/WHS 为 `+3.414/+7.917 ns`，DVP
  捕获寄存器 10/10 位于 ILOGIC，路由、DRC、CDC Critical 均无错误。
- [x] 已更新 `deploy/phase2_l2_autonomous_final_20260904/` 中的 BIT、HWH 和上板说明；
  加载脚本不变，不生成哈希或 CRC 清单。实机识别率与误检率等待上板测试记录。

### 2026-09-05：全硬件化 HDMI 同帧调试版

- [x] 在阈值 `-3383` 的全硬件自治流水线旁新增纯 PL HDMI OUT 支路：固定
  `640x480@60 Hz`，把 Locator 实际使用的 128x128 Gray8 图像以 3 倍最近邻显示，并叠加
  绿色原始 bbox、黄色 EMA bbox、青色 18% 扩框 ROI、`RAW` 当前候选、`LED` 确认类别和
  Locator 检出状态。不加入 AXI/DDR/VDMA/USB、DDC/HPD、CRC、哈希或软件控制握手。
- [x] 显示端使用独立双 BRAM 缓冲被动镜像相机写流；图像与相同 frame_id 的结果配对后，
  通过稳定 payload + toggle/ack CDC 提交，只在 HDMI 帧起点切换读 bank，不反压也不改变
  推理流水线。TMDS 使用 25.2 MHz 像素时钟、126 MHz DDR 串行时钟和 7-series OSERDES。
- [x] 原六组自治 XSim 与新增视频时序、TMDS 编码、双缓冲所有权/CDC、渲染器四组自检，
  合计十组全部 PASS；bbox 仍覆盖 `-3384` 不检出、`-3383/-3382` 检出的边界。
- [x] 综合 WNS/WHS 为 `+0.019/+0.027 ns`；实现 WNS/WHS 为 `+0.038/+0.020 ns`，DVP
  专项为 `+3.414/+7.917 ns`，DVP 捕获寄存器 10/10 位于 ILOGIC，TMDS OSERDES 6/6
  位于 OLOGIC，路由失败网络 0，DRC 0 Error。
- [x] 实现资源为 12,385 LUT（23.28%）、6,544 FF（6.15%）、66.5 BRAM tile（47.50%）、
  28 DSP（12.73%）、2 MMCM（50%）；相对无 HDMI 最终版增加 720 LUT、1,061 FF、
  8 BRAM tile、0 DSP、1 MMCM。
- [x] 生成最小部署目录 `deploy/phase2_l2_autonomous_hdmi_debug_20260905/`，只含同名 BIT/HWH、
  最小加载脚本和中文上板说明，不生成校验清单。DVP 下降沿 2～8 ns 临时输入窗口继续保留，
  HDMI 画面、显示器兼容性与端到端延迟等待 PYNQ-Z2 实机测试。

### 2026-09-18：HDMI 黑屏、四灯常亮与残余噪点离线复核

- [x] 确认 0905 HDMI BIT 的生成时间晚于全部相关 RTL/XDC 和 0904 相机修正；相机初始化
  ROM 第 50 项为 `474000`，即 `0x4740=0x00`。部署 BIT/HWH 与实现工程产物逐字节一致，
  压缩包内 BIT/HWH 也与部署目录一致；因此当前工作区没有更新但漏编译的 HDMI 硬件源。
- [x] 由 RTL 确认“HDMI 黑底仍显示 `LED:NONE` + 四个物理 LED 持续全亮”表示显示链路已工作，
  但推理前端进入锁存 `fatal_error`。入口仅为相机初始化三次失败/XCLK 后续失锁、DVP
  异步 FIFO 溢出或非法调度状态；与 `-3383`、EMA、ROI、classifier 判定无关。
- [x] 残余噪点时多时少更符合 DVP/PCLK 信号完整性、供电/接地或未实测采样窗口问题；现有
  下降沿 2～8 ns 约束为假定板级包络，静态时序通过不能证明杜邦线上的真实眼图。
- [x] HDMI 加载脚本改为先设置并稳定 50/100 MHz FCLK，再下载 overlay，避免自治初始化
  启动后再次触碰 FCLK1。未修改 RTL、阈值、模型或 BIT。
- [x] 新增最小相机路径诊断脚本，可输出 XCLK、SCCB Chip ID、`0x4740` 读回、FIFO overflow、
  format/drop 计数及三帧 PGM；生成无哈希复测包
  `deploy/phase2_l2_hdmi_black_screen_retest_20260918.zip`。明日先排除所有自启服务抢占，
  再做 HDMI 三次重载，失败时切换无 HDMI 相机诊断 overlay；证据出来前不重跑 bitstream。
- [x] 首轮实机复测：确认 `gesture-demo.service`、`gesture-demo-sameframe128.service` 和自建
  `gesture-hdmi.service` 均为 disabled，且无对应 running unit/进程；新加载器三次重新下载
  HDMI overlay 均读回 FCLK0/FCLK1 `50.0/100.0 MHz`，3/3 正常显示视频，未复现黑屏或
  四灯常亮。20 秒观察脚本退出后 PL/HDMI 继续运行属于预期行为。
- [ ] 当前仍观察到数量随时间变化的噪点及单灯/类别闪烁。由于“禁用服务”和“FCLK 先于
  overlay”同时生效，本轮只能确认 BIT 有效，尚不能单独归因原黑屏是服务抢占还是启动顺序。
  下一步运行包内无 HDMI `camera_diag`，检查 Chip ID、`0x4740` 读回、FIFO/format 计数及
  三帧 PGM；随后做一次完全断电冷启动手动加载复核，在证据出来前不重跑 bitstream。
- [x] 首次 `camera_diag` 在首个 `CAMERA_STATUS` 输出处因 Python 形参重名退出：`emit()` 的
  位置形参和 JSON payload 均命名为 `label`，属于诊断脚本软件错误，不是相机或 FPGA 故障。
  最小修复仅将事件形参改名为 `event`；`py_compile` 和直接覆盖原失败路径的无硬件依赖
  `snapshot(..., "after_overlay")` 回归通过。生成无哈希 `fix1` 复测包，BIT/HWH、驱动、
  时钟、寄存器配置和 RTL 均未修改，仍需在板端重新采集三帧完成噪点隔离。
- [x] `fix1` camera-only 实机诊断完成并保存至
  `board_evidence/20260918_camera_diag_fix1/`：FCLK0/FCLK1 为 50/100 MHz，XCLK 锁定，
  SCCB ID=`0x5640`、`0x4740=0x00`，三帧均成功发布且 FIFO overflow 始终为 false。
  `format_error_count` 仅在启动后的首帧阶段由 0 增至 1、此后保持 1，结合 capture 任意时刻
  使能后等待下一 SOF 的实现，先按启动帧对齐瞬态处理；MMIO 慢速读回占用双缓冲期间
  `drop_count` 增至 5 属诊断读回预期，不解释画面散点。
- [x] 三张 128x128 PGM 在无 HDMI 条件下均可见大量随机亮点，因此已排除 HDMI 渲染、
  阈值 `-3383`、EMA、18% ROI 和分类器为像素噪点来源。离线空间中值残差 `>=96` 的强异常点
  分别为 47/105/129 个，三组跨帧掩码 Jaccard 仅 0.0066/0.0057/0.0218，且异常值常见
  `0x7F/0xFF/0xEF/0xFB/0xF7` 等多位高电平组合；更符合相机至 PL 的 DVP 数据采样/供电接地
  瞬态，而非固定坏点或单根 D7 恒定翻转。现有 2～8 ns 输入约束仍只是未实测假定窗口。
- [ ] 下一步保持 BIT、驱动和寄存器不变，先断电后缩短/重插 D[7:0]、PCLK、HREF、VSYNC，
  加强相机与 PYNQ 共地并在固定光照静态场景采集 10 帧；若噪点未明显下降，再制作降低 DVP
  PCLK 的最小 A/B 配置。证据前不加入图像滤波，也不重跑相同 RTL 的 bitstream。
- [ ] HDMI 临时自启首次尝试未通过，原始终端输出保存于
  `board_evidence/20260918_hdmi_autostart_attempt1/pynq_terminal.txt`。新建的
  `gesture-hdmi-0918.service` 已被 enable，两条等待 FPGA Manager/PYNQ Device 的
  `ExecStartPre` 均以 0 成功，但执行最新 clock-first HDMI 加载器的 `ExecStart` 约 20.7 秒后
  以状态 1 退出，unit 为 `failed (exit-code)`。本次粘贴内容未包含 Python traceback，且尚未
  完成重启/冷启动，因此不能归因，也不能接受为自启通过；取得完整 journal 和同路径手动运行
  对照前应保持该 unit 禁用。
- [x] 自启首次失败的 traceback 与手动恢复证据保存于
  `board_evidence/20260918_hdmi_autostart_attempt1_manual_recovery/pynq_terminal.txt`。根因为
  systemd 的直接 `ExecStart` 未加载 XRT/PYNQ 设备环境，`Clocks.fclk0_mhz` 访问
  `Device.active_device` 时抛出 `RuntimeError: No Devices Found`；FPGA Manager 本身仍为
  `operating`。禁用并 reset-failed 后，在同一部署目录由交互式 shell 手动运行加载器成功，
  FCLK0/FCLK1 为 50/100 MHz、退出码 0 且 HDMI 画面恢复，进一步确认 BIT/HWH 有效。
- [ ] 自启最小修正仅将 `ExecStart` 改为已在既有功能 RC unit 使用的
  `/bin/bash -lc 'exec ...'`，使其继承 XRT/PYNQ 登录环境；重新 enable 后先做当前启动测试，
  再完成至少两次完全断电冷启动。通过标准仍为 `active/exited`、`NRestarts=0`、
  `ExecMainStatus=0` 与实际 HDMI 正常，噪点问题继续独立处理。

### 2026-09-18：HDMI自启恢复与DVP接线雪花根因确认

- [x] 将 `gesture-hdmi-0918.service` 的 `ExecStart` 改为 `/bin/bash -lc 'exec ...'` 后，用户
  实机确认开机自启成功并正常显示画面，原 `No Devices Found` 由此确认属于 systemd 未进入
  PYNQ/XRT 登录环境，不是 BIT/HWH 故障。本次尚未收到两轮完整冷启动状态字段，因此只记录
  当前实机成功，不扩展声明长期冷启动稳定性。
- [x] 保持 HDMI BIT/HWH、相机寄存器、阈值和场景不变，将 OV5640 全部连线由面包板转接改为
  短线直连后，原随机雪花点消失；任一连接线轻微移动后雪花可再次出现。该可重复 A/B 已将
  根因定位为相机至 FPGA 的物理接触/板级信号完整性，不归因于 HDMI、`-3383` 阈值、EMA、
  18% ROI 或分类器。无需重新实现 bitstream，也不加入图像滤波或额外检测机制。
- [x] 新增固定接线与自启部署说明、已验证 `/bin/bash -lc` service 和最小安装脚本；生成独立
  无哈希/CRC部署包 `deploy/phase2_l2_autonomous_hdmi_wiring_verified_20260918.zip`。包内沿用
  当前实机通过的 BIT/HWH 和 clock-first 加载器，不覆盖历史部署包。
- [x] 部署包静态验收通过：ZIP 共6项且均为正斜杠路径，不含哈希/CRC/manifest；包内
  BIT、HWH、加载器与 `fix1` 实机版本逐字节一致，加载器Python语法、UTF-8文本和systemd
  关键字段检查通过。本轮无RTL/BD/XDC变更，因此未重新综合、实现或生成bitstream。

### 2026-09-21：Phase 3 Windows/CoppeliaSim机械臂控制基线启动

- [x] 在Windows 11下完成CoppeliaSim、外部Python ZMQ客户端和RoArm-M3 URDF导入；为规避
  simURDF对空 `world`/`hand_tcp` link的兼容问题，当前仿真场景保留7个有几何与惯性的link、
  6个运动关节，场景保存为 `D:\RobotSim\scenes\roarm_m3_imported.ttt`。
- [x] 新增隔离目录 `sim/phase3_robot/`，冻结首版仿真六通道关节顺序、弧度单位和URDF限位；
  实现按别名发现关节、位置读写、停止态保护和三次smoothstep多轴插值。该接口仅作为仿真与
  后续FPGA参考模型，真实机械臂零位、方向、范围和控制周期仍待实物标定。
- [x] FakeSim离线自检5项全部通过，覆盖乱序句柄归一化、缺失关节拒绝、长度/有限值/范围检查、
  运行态拒绝和插值精确到达。
- [x] CoppeliaSim现场验证发现6个预期关节，句柄依次为17/20/23/26/29/32，初始位置均为0；
  `link1_to_link2` 完成停止态 `+20 deg` smoothstep往返，恢复最大误差为
  `0.000000000 rad`。该结果属于仿真测量，不是实物机械臂精度证据。
- [x] 依据原URDF固定变换在 `link5_respondable` 下创建 `hand_tcp` Dummy：
  `xyz=(0,0,0.115428) m`、配置 `rpy=(1.5708,-1.5708,0) rad`。CoppeliaSim在俯仰角接近
  `-90 deg` 时返回等价欧拉表示 `(0,-1.570793,-1.5708)`，因此验收改为比较位姿矩阵而非
  欧拉角分量；离线4项测试和现场矩阵验证均通过。新场景另存为
  `D:\RobotSim\scenes\roarm_m3_phase3.ttt`，未覆盖原始导入基线。
- [x] `hand_tcp` 随动现场测试完成：肩/肘测试运动使TCP移动`0.198251481 m`，TCP相对
  `link5_respondable`的局部矩阵最大误差为`3.33e-16`；返回初始关节后，TCP世界矩阵与
  六关节最大恢复误差均为0。JSON证据保存为
  `sim/phase3_robot/results/tcp_motion_20260922.json`。
- [x] 新增隔离式位置IK验证：在临时`simIK`环境中按三轴位置约束求解，求解阶段不把结果
  同步回场景；仅显式`--execute`时才经既有smoothstep控制器执行，并在`finally`中回零。
  默认TCP目标为`(+30,0,-20) mm`，现场求解与执行实测误差均为`0.000090779 m`，低于
  `0.002 m`门限，TCP矩阵及六关节恢复误差均为0。离线完整回归19项全部通过，现场证据为
  `ik_solve_only_20260922.json`和`ik_execute_20260922.json`。
- [x] 依据RoArm-M3 SRDF冻结夹爪端点与手势语义：`0 rad=closed`、`1.5 rad=open`，
  `fist -> closed`、`palm -> open`。现场执行`palm`开夹至`1.5 rad`后恢复到`0 rad`，
  到位和恢复误差均为0；证据保存为
  `sim/phase3_robot/results/gripper_palm_restore_20260922.json`。
- [x] 新增无FPGA抓放状态机，串联开夹、预抓取、下探、fist合夹/挂接、抬升、搬运、
  下放、palm开夹/解除挂接、撤离和回零。首次预检拒绝了接近最高伸展奇异位的不可达航点，
  未放宽门限；将工作平面下移后六个航点全部通过。现场完整执行最大TCP误差为
  `0.000095836 m`，物块放置误差为`0.000009800 m`，释放后撤离时物块位移为0，最终TCP
  矩阵和六关节恢复误差均为0。全套离线回归27项通过；证据保存为
  `sim/phase3_robot/results/pick_place_fsm_20260922.json`。
- [ ] 当前物块抓取由挂接到`hand_tcp`模拟，不宣称接触动力学或夹持力验证；姿态约束、
  碰撞/避障、外部实时手势输入、黄金轨迹导出、FPGA联调和真实机械臂标定仍待后续完成。

### 2026-09-22：Phase 3轨迹参考合同与CoppeliaSim实时回放预演

- [x] 新增开发用`phase3_trajectory_q16_16_v1`合同：六通道有符号Q16.16弧度，phase/blend为
  UQ0.16且`1.0=65536`，每次重新量化采用最近值、恰好半值时远离零；tick 0/末tick强制
  逐位输出起点/终点。该合同只用于Python参考模型和后续PL轨迹核心，不冻结真实RoArm UART、
  物理控制周期、舵机零位/方向/安全限位或设备单位。
- [x] 从已通过的抓放FSM结果提取11个关键帧，以32逻辑tick/段生成10段、321个六轴样本；
  导出JSON合同清单、CSV和每行192位的MEM，MEM布局为ch5高位、ch0低32位，并记录CSV/MEM
  SHA-256。完整Phase 3 Python回归38项全部通过，覆盖舍入、固定四步smoothstep值、终点精确、
  192位打包/解包、符号恢复和manifest/MEM一致性。
- [x] 新增黄金轨迹回放桥作为未来FPGA显示链路的文件数据源替身。20 Hz现场回放321个样本，
  期望/实测时长为16.000/16.003 s，P95/最大派发晚到为29.431/44.218 ms，整周期超限0次，
  最终样本和回零误差均为0；证据为`trajectory_replay_20hz_20260922.json`。
- [ ] 相同逐轴ZMQ实现的50 Hz A/B出现130次整周期超限，P95/最大晚到为59.654/73.552 ms，
  虽然最终姿态与回零仍精确，但明确判定调度不通过；证据为`trajectory_replay_50hz_20260922.json`。
  后续用单次批量提交或场景端脚本优化，再接入FPGA实际数据流。AXI/FIFO、整机实现、
  板测和真实机械臂接口均尚未开始。

### 2026-09-22：Phase 3固定32 tick轨迹RTL叶模块

- [x] 新增隔离式`trajectory_smoothstep_q16_16`，六路同时接收起点/终点并按
  `phase3_trajectory_q16_16_v1`合同生成Q16.16 smoothstep；末tick强制精确目标，带busy、
  sample index/done、重复启动和算术溢出sticky状态。当前每样本7个100 MHz时钟，仅支持
  固定32 tick/段，不接AXI、UART或现有视觉顶层。
- [x] Vivado XSim自检通过：10段、320个RTL输出样本与黄金MEM逐位一致，并覆盖六通道原子
  提交、最终done、运行中重复启动拒绝和有限watchdog。Phase 3 Python回归38项继续全部通过。
- [x] 初次OOC综合WNS为`-0.205 ns`；在DSP乘法与舍入/加法间增加一级流水后，位精确XSim
  仍通过，PYNQ-Z2 OOC综合资源为1,461 LUT（2.75%）、934 FF（0.88%）、14 DSP（6.36%）、
  0 BRAM，100 MHz内部寄存器路径WNS为`+0.968 ns`，0个setup failing endpoint。
- [ ] 当前仅有synthesized OOC证据，没有place/route或bitstream。叶模块590个宽总线端口尚未
  接入顶层，故OOC DRC预期报告NSTD-1/UCIO-1，外部I/O路径也没有板级delay约束。物理tick
  调度已在下节完成；下一步加入AXI控制封装，再做整机实现与CoppeliaSim实时流联调。

### 2026-09-22：Phase 3可编程节拍与反压安全输出层

- [x] 新增`trajectory_stream_scheduler`：命令通过ready/valid提交六轴起点、终点和32位
  `period_cycles`；底层轨迹核先计算固定32点并写入32×192段缓冲，再以可编程最小间隔输出。
  当前最小周期为256个100 MHz时钟，仅是预计算安全下限，不是最终舵机周期。
- [x] 输出采用192-bit ready/valid；下游反压期间数据、索引和last保持，握手后重新开始周期
  计时，因而不会丢样本。低于最小周期的命令被拒绝并锁存错误；忙时`cmd_ready=0`，不会
  覆盖正在执行的段。接口合同记录于`docs/PHASE3_TRAJECTORY_STREAM_INTERFACE_DRAFT_CN.md`。
- [x] XSim通过10段、320个节拍化黄金样本逐位比对，并覆盖非法周期、忙时第二条命令、首段
  第5点持续7周期反压、payload稳定、最终done、复位清错和全局watchdog；Phase 3 Python
  38项回归继续全部通过。
- [x] 首次综合发现RAM写口位于异步复位过程，Vivado将6,144-bit段缓冲退化为6,144个FF；
  拆分为无复位同步写口后，明确推断`32×192` RAM并映射为3个RAMB36E1。OOC脚本新增
  `RAMB36E1_COUNT==3`硬门禁，最终综合为1,649 LUT（3.10%）、1,410 FF（1.33%）、
  3 BRAM Tile（2.14%）、14 DSP（6.36%），100 MHz内部WNS `+0.968 ns`，setup失败端点0。
- [ ] 当前仍是synthesized OOC结果；627个宽总线端口未接顶层，NSTD-1/UCIO-1和外部I/O
  未约束属于预期边界。尚无AXI寄存器、UART、取消/反馈超时、implementation或bitstream。

### 2026-09-22：Phase 3 AXI4-Lite shadow/COMMIT控制层

- [x] 新增独立`trajectory_axi_lite_top`，冻结开发ABI `0x0000_3001`。PS先写六轴起点、
  六轴终点与周期shadow，再由`CONTROL.COMMIT`原子提交；当前段执行期间允许预写下一段
  shadow，但忙时COMMIT返回`SLVERR`且不会覆盖活动命令。
- [x] 输出通过六个只读sample word和META窗暴露；VALID后数据/index/last保持到
  `CONTROL.SAMPLE_POP`，末点POP产生DONE_STICKY。加入DONE/ERROR两路IRQ enable，以及
  invalid period、fill、deadline、core、busy commit、empty pop、access和command conflict
  九类sticky错误；sticky错误仅由外部复位清除。
- [x] AXI写通道使用独立AW/W pending寄存器，覆盖AW-first、W-first和同周期到达；只允许
  32-bit对齐全字写。自检对B/R响应各施加两周期反压，验证响应保持；非法地址、部分WSTRB、
  只读写、多命令同写、空POP、非法周期和忙时COMMIT均返回`SLVERR`。
- [x] XSim通过两个完整段、64个AXI读出样本与冻结MEM逐位比对；同时验证活动段期间改写
  shadow不影响当前段、下一次COMMIT使用新shadow、样本在POP前稳定、DONE清除与IRQ语义，
  并带有限watchdog。底层scheduler的10段/320点覆盖保持不变。
- [x] PYNQ-Z2 OOC综合硬门禁确认`RAMB36E1_COUNT=3`；资源为1,894 LUT（3.56%）、
  1,919 FF（1.80%）、3 BRAM Tile（2.14%）、14 DSP（6.36%）。100 MHz内部WNS为
  `+0.968 ns`、setup failing endpoint为0。
- [ ] 当前是孤立synthesized OOC，101个AXI/IRQ顶层端口未分配IOSTANDARD/LOC，故
  NSTD-1/UCIO-1属于预期；没有place/route、BD地址、HWH、bitstream或板测。
- [x] 新增`ps/robot/trajectory_axi_driver.py`：显式接收未来BD基地址，支持ABI/min-period
  检查、六轴signed Q16.16 shadow写入、单次COMMIT、状态/错误解码、稳定样本读取与POP。
  FakeMMIO聚焦测试4项通过，覆盖原子提交、负数打包、输入拒绝、样本符号恢复和DONE清除。
- [ ] 下一步将该IP接入隔离的Phase 3 Block Design并分配地址；UART/舵机协议、
  反馈超时、取消/急停与真实物理周期仍待实物接口和安全需求冻结。

### 2026-09-22：Phase 3隔离Block Design、实现与板端Smoke包

- [x] 新增`trajectory_axi_bd_wrapper`与隔离`Gesture_Phase3_Trajectory`工程；连接Zynq PS
  GP0、100 MHz FCLK/reset、SmartConnect和IRQ，地址固定为`0x43C2_0000/4K`。BD验证通过，
  M_AXI_GP0接口实际频率`CONFIG.FREQ_HZ=100000000`通过门禁。
- [x] 完成综合、布局布线和bitstream：2,241 LUT（4.21%）、2,361 FF（2.22%）、
  3 BRAM Tile（2.14%）、14 DSP（6.36%），post-route WNS/WHS为`+0.677/+0.036 ns`，
  5,330个网络全部布通、路由错误0、DRC Error 0。BIT/HWH与XSA均已生成。
- [x] 新增不接物理输出的PYNQ smoke脚本与最小部署目录`deploy/phase3_trajectory_20260922/`；
  上板后加载独立overlay，提交冻结黄金轨迹第一段并逐点核对32个六轴Q16.16样本。
- [ ] 当前bitstream尚未上板执行smoke；UART/舵机协议、反馈超时、取消/急停与真实物理周期
  仍待实物接口和安全需求冻结，不能将本次PS-MMIO闭环称为机械臂闭环。

### 2026-09-23：Phase 3 S1双机械臂数据通路候选 v0.1.0（SOURCE_CANDIDATE）

- [x] 目标：统一六通道数据通路，从PL轨迹样本直接驱动RoArm-M3（JSON行/二进制桥v1发送）或
  SO-ARM101（Feetech半双工）后端；配置化协议、默认拒绝真实输出；反馈/到位/超时/急停统一模型。
- [x] 输入基线：`handoff_full_extract_20260923/source_baseline`（轨迹ABI `0x0000_3001`，
  隔离BD `0x43C2_0000`）。`releases/`与已有部署未改动。
- [x] 修改：`trajectory_axi_lite_top.v`增加`EXTERNAL_SAMPLE_SINK`（默认0不变；=1时ABI `0x3002`，
  POP返回SLVERR）；`trajectory_axi_bd_wrapper.v`接空新端口；`trajectory_axi_driver.py`支持`0x3002`。
  新增`rtl/robot/arm_*`与`phase3_s1_armpath_top.v`（机械臂后端ABI `0x0000_3101`，建议`0x43C3_0000`），
  `ps/robot/arm_*`等参考模型/驱动/工具，`config/`profile与协议文件，S1 Tcl/XDC/XSim脚本。
- [x] 实际测试：Python 127项PASS。补充开源层（不是XSim/Vivado）：pyslang静态16例0 error；
  Icarus Verilog 12/12自检TB打印`[PASS]`（含基线两个轨迹TB回归）；Yosys估计完整运动子系统
  4,910 LUT（校准上界6,761）/4,187 FF/3 RAMB36/15 DSP（Vivado预期14），逻辑深度10级（基线参照8级）。
- [ ] 未运行：XSim、Vivado OOC/BD/实现/时序/BIT、CoppeliaSim、PYNQ板测、实物
  （`NOT_RUN_ENV_UNAVAILABLE`/`BLOCKED_EXTERNAL_INPUT`）。
- [ ] 外部参数：RoArm官方JSON词汇与固件版本、Feetech官方表与帧结构核实、两臂标定/限位/超时、
  6个PYNQ引脚与收发器（`config/UNKNOWN_PARAMETERS.yaml`）。
- [ ] 已知问题：LUT预算需Vivado确认（估计4.9k–6.8k，预算6k）；JSON子集限制；桥RX/固件未做。
- [x] 回退：删除S1新增文件并恢复4个修改文件；现有Phase 3工程与BIT/HWH未动。
- [ ] 下一步：等待用户返回XSim/OOC/实现结果和B1–B6板测结果，以及官方协议与标定数据后再进入修订/S2。

### 2026-09-24：Phase 3 S1候选 v0.1.1（资源统计口径与预算门禁修订）

- [x] 目标：修正S1 Vivado脚本的LUT统计口径（v0.1.0以`REF_NAME =~ LUT*`计数，预算未可靠计入LUT as Memory），
  建立明确的`OVER_BUDGET`门禁；不改RTL，不进入S2。
- [x] 修改：新增`scripts/phase3_s1_resource_gate.tcl`（以`report_utilization`“Slice LUTs” = LUT as Logic + LUT as Memory
  为准，解析Design Timing Summary）；`run_phase3_s1_arm_ooc_synth.tcl`三构建全部输出`S1_OOC_RESULT/BUDGET/GATES`
  后判定，超限`RESULT: OVER_BUDGET`退出12（门禁11、两者13），无PASS；`build_phase3_s1_armpath.tcl`输出运动子系统
  `armpath_0`与整设计的总LUT/LUT as Logic/LUT as Memory与时序，删除`PHASE3_S1_IMPL_LUT_CELLS`，失败时不暂存BIT/HWH。
- [x] 实际测试：Python 141项PASS（新增14项：用基线真实Vivado 2026.1报告测解析，用桩化Vivado命令测两脚本控制流）；
  Tcl测试改在子进程执行，修复v0.1.0引脚检查测试在pytest默认输出捕获下的偶发失败（整套连续15次全部通过）。
  补充层pyslang/Icarus/Yosys重跑，RTL未变。
- [ ] 未运行：XSim、Vivado综合/实现/时序、板测、CoppeliaSim、实物。
- [x] 回退：恢复两个v0.1.0 Vivado脚本并删除`phase3_s1_resource_gate.tcl`。
- [ ] 下一步：等待用户返回Vivado（三构建与实现的全部`S1_OOC_*`/`PHASE3_S1_IMPL_*`行与退出码）和板测结果。

### 2026-09-24：Phase 3 S1 v0.1.1 本机 Vivado 验收（SOURCE+IMPLEMENTED_CANDIDATE）

- [x] 校验外部ZIP SHA-256为`c2aa489db57056c5dca45c2dc26b94f3f8f1625fc5ae0a06c815e4923cec158a`；解压及包内SHA256SUMS检查PASS。与v0.1.0对比未发现机械臂RTL、ABI、AXI地址或参考向量变化。合并前备份为`backups/snapshot_20260924_223904_Before_Phase3_S1_v0_1_1.zip`。
- [x] Vivado 2026.1 XSim 12/12 PASS。三种OOC构建全部通过预算、100 MHz时序和映射门禁，脚本退出码0：`both`为5010 LUT/3920 FF/3 BRAM/14 DSP、WNS/WHS `+0.265/+0.164 ns`；`roarm_only`为4753 LUT/3662 FF；`so101_only`为4461 LUT/3690 FF。
- [x] 隔离BD地址为轨迹`0x43C2_0000/4K`、机械臂`0x43C3_0000/4K`。候选Arduino D0-D5管脚完成双后端implementation与BIT/HWH/XSA。运动子系统为4903 LUT/3917 FF/3 BRAM/14 DSP，全设计5318 LUT/4408 FF；post-route WNS/WHS `+0.336/+0.033 ns`，失败端点0、routing error 0、DRC Error 0，脚本退出码0。
- [x] 验收证据为`reports/phase3_s1_v0.1.1_local_acceptance_20260924/`，隔离板测包为`deploy/phase3_s1_armpath_v0.1.1_20260924/`。
- [ ] 包内Python 141项本机未复跑：现有Python缺少pytest，记`NOT_RUN_MISSING_PYTEST`。PYNQ `192.168.2.99:9090`只读检查超时，B1-B6均`NOT_RUN_BOARD_UNREACHABLE`。
- [ ] 当前只能进入无机械臂B1-B6。候选管脚尚未物理核对，SO-ARM101需要外置3.3 V半双工收发器；官方协议、固件、标定/限位冻结前不得连接真实机械臂，也不进入S2。

### 2026-09-25：Phase 3 S1 v0.1.1 板测阶段性结果（用户提供控制台输出）

- [x] 板上BIT/HWH SHA-256与本机部署包一致，`yaml/numpy/pynq`导入通过；加载S1前已停止`gesture-hdmi-0918.service`。
- [x] B1只读PASS：两个后端能力为true，`errors=[]`；脚本在输出结果前完成轨迹与后端ABI断言。
- [x] B4 RoArm UART回环复测PASS：32帧发送、32次有效反馈、0反馈错误、0响应超时；最后六轴命令与反馈及Python参考值一致，`valid_mask=0x3F`，最长帧8.42495 ms（要求<20 ms）。第一次尝试因`motion_enable_in`未接高电平报`no permission`，接线后通过；这不是B6急停测试。
- [ ] B2/B3 DRY_RUN、B4b PC抓包、B5 SO-ARM101 PC仿真器、B6急停负向测试尚无结果；USB-TTL尚未到货，真实机械臂未连接。
- [x] 阶段性证据记录于`board_evidence/phase3_s1_v0.1.1_partial_20260925.json`；当前结论为`PARTIAL_BOARD_PASS`，不能写为S1板测全部PASS。
- [x] 随后用户提供B2/B3 DRY_RUN输出：RoArm与SO-ARM101的软件检查均PASS，均为32帧、0错误、0反馈超时，最后六轴设备值与Python模型一致；RoArm最长帧8.42495 ms，SO-ARM101为0.77428 ms。DRY_RUN的外部TX/DIR空闲电平尚无仪器观察，B4b/B5/B6仍未运行。
- [x] 用户随后提供B5 SO-ARM101仿真板端输出：脚本PASS，32命令帧、213有效反馈、0错误/超时、六轴反馈全有效且命令与参考模型一致。PC仿真器`replies`日志未提供。处理周期最后55.56751 ms、最大73.22813 ms，因此尚不能证明20 ms/样本的持续50 Hz输出。
- [ ] 以`--period-cycles 20000000`运行的RoArm回环结果为普通PASS：32帧全部完成、`errors=[]`，没有`ESTOP_EVENT`。用户随后确认未拔D5或不确定，因此这次未执行B6运行中撤销许可测试，不能据此判断急停故障或急停通过。
- [ ] 依总计划`阶段1：机械臂与接口验证`出口，尚缺实物安装/校准、离线轨迹与角度反馈、更新率/延迟/内部平滑实测、暂停取消夹爪归位，以及协议路线决定。当前仅为无实物S1数据通路阶段性通过，不可宣布Phase 3第一阶段结束。
- [x] B6后续有效运行达到负向逻辑判据：`ESTOP_EVENT`出现、仅发11/32帧、11次反馈、0反馈错误/响应超时；脚本`result=FAIL`是预期的主动中断结果，末六轴值未到目标亦属预期。启动前许可线未接的失败与先前普通200 ms回环均不计B6。外部TX停发波形尚未提供；整体仍为无实物板测阶段性通过。

### 2026-09-25：Phase 3 S2 v0.2.1 修复与本机实现候选

- [x] 在 S2 样本选择器中跟踪 S1 COMMIT 到最后一个样本交付，拒绝首样本出现前切到 S2 或 START；加入一级 ready/valid 缓冲，修复 S1 到后端的时序路径。S1 v0.1.1 RTL/驱动未修改。
- [x] XSim 四个自检 TB 4/4 PASS（S2 核心、S2 顶层、S1 双后端回归）；S2 顶层新增首样本切换和下游背压断言。
- [x] Vivado 2026.1 OOC 三构建预算与时序全通过：both 6329 LUT/5312 FF、WNS +0.951 ns；S2 增量 1300 LUT/1391 FF、0 BRAM/DSP。隔离 BD 地址为 0x43C2/0x43C3/0x43C4_0000，各 4K。
- [x] 实现通过：运动子系统 6198 LUT/5309 FF/3 BRAM/14 DSP，S2 增量 1292 LUT/1391 FF、0 BRAM/DSP，WNS/WHS +0.612/+0.030 ns，退出码 0；生成匹配的 BIT/HWH。
- [ ] 已制作无机械臂 Jupyter 上板包及 C1–C5 操作过程；板端、物理引脚和真实机械臂测试尚未运行。S3 未启动。

### 2026-09-25：S2 v0.2.2 板测脚本修补（BIT/HWH 不变）

- [x] 用户回传 v0.2.1 上板哈希全 OK；C1、C4、C5 退出码 0，C2/C3 均以 SIGBUS/退出码 135 中止。C2/C3 脚本中有一次故意触发非法切源的 AXI 写，RTL 会返回 SLVERR；这是当前最可能的 SIGBUS 触发点，尚待板端日志或 v0.2.2 复测确认。
- [x] v0.2.2 板测脚本不再执行该负向写，保留只读首样本窗口检查；非法切源拒绝继续由 XSim TB 覆盖。加入 faulthandler 以便若仍 SIGBUS 可记录栈。BIT/HWH SHA-256 与 v0.2.1 完全一致。
- [x] 上板 ZIP 的 SHA256SUMS 改为 LF 行尾，PYNQ 可直接执行 `sha256sum -c SHA256SUMS.txt`。
- [ ] v0.2.2 C2/C3 板测仍待用户执行，不能宣布 S2 板测通过。

### 2026-09-25：S2 v0.2.3 C2/C3 SIGBUS 定位与修复

- [x] 用户提供 v0.2.2 的 C2/C3 日志；两者堆栈均定位到 `phase3_s2_board_smoke.py` 行 157 调用 `arm.clear_counters()`，经 `arm_backend_axi_driver.py` 写 S1 后端 CONTROL 时 SIGBUS。S1 RTL 仅允许 MODE_OFF 且空闲时执行 COUNTER_CLEAR；该处仍为 DRY_RUN，导致 AXI SLVERR。此前归因于负向切源写入的推测未被日志支持。
- [x] v0.2.3 删除运行中的两次清计数，改用每段开始时的累计帧数作差；初始 MODE_OFF 清计数保留。对 PAUSE/RESUME/CLEAR/切源增加必要状态前置检查，异常时在 Python 层停止而不继续触发非法 AXI 写。
- [x] 重打包上板与源码 ZIP；BIT/HWH 与 v0.2.1、v0.2.2 字节相同。v0.2.3 的 C2/C3 尚待上板复测。

### 2026-09-25：S2 v0.2.3 无机械臂 DRY_RUN 板测退出码

- [x] 用户在 PYNQ-Z2 解压 v0.2.3 上板包；C2 RoArm DRY_RUN 与 C3 SO-ARM101 DRY_RUN 退出码均为 0。脚本仅在所有软件 `checks` 为真时返回 0，说明两后端软件判据通过。此前相同 BIT/HWH 的 C1、C4、C5 退出码也为 0。
- [ ] C2/C3 的 JSON 日志、`late_count` 与 D1/D2/D4 示波器空闲电平尚未收到；真实机械臂、引脚电气与 S1 剩余出口项仍未验收。

### 2026-09-25：S2 v0.2.3 无机械臂 DRY_RUN 日志验收

- [x] 用户提供 C2/C3 JSON 日志，均 `result=PASS`、19/19 checks=true、退出码 0、`late_count=0`、后端错误为空。RoArm 与 SO-ARM101 的累计 `frames_tx` 均为 152（S1 32 + 规划器 100 + 回程急停前 20）；暂停、DONE、急停、清错及最终设备命令检查均通过。
- [x] 证据保存于 `board_evidence/phase3_s2_v0.2.3_20260925/`。同一 BIT/HWH 的 C1/C4/C5 先前退出码均为 0。
- [ ] 用户暂无示波器，D1/D2/D4 空闲电平与脉冲波形未实测；真实机械臂未连接。结论限于无机械臂的软件 DRY_RUN 板测通过。

### 2026-09-26：S3 v0.1.1 / S4 v0.1.0 源码候选隔离核审

- [x] 两个 ZIP 的侧车 SHA-256 和包内 SHA256SUMS 全匹配：S3 `50e12ab5a7fb1b9bb9c969160ec3af7b81cac7eebcd02394eec7e270391e21eb`（112/112）；S4 `bd70208c68c47a30c937a07263017abd734e0771620830394ee6e2ff30e6b906`（74/74）。仅在 `reviews/s3s4_20260926/` 中集成复测，未合入主工程。
- [x] S3 v0.1.1 本机 Vivado 2026.1 XSim 9/9 PASS、退出码 0。七类真实数据、训练权重及可上板 BIT/HWH 仍缺，不具备真实七分类上板验收条件。
- [x] S4 依赖锁 39/39 与当前工程匹配；XSim 17/17 PASS，OOC 三配置通过。BD 地址保留 S1/S2，新增 0x43C5_0000，但四个 AXI 接口缺时钟关联元数据，BD 报 `BD 41-967` 与 SmartConnect 时钟域 CRITICAL WARNING。
- [ ] S4 完整实现布线后 WNS/WHS +0.227/+0.008 ns、DRC 0 error，但最终门禁退出码 13。脚本按 `*/task_0/u_motion` 寻找层级，实际层级是 `task_0/inst/u_motion`，导致 S1/S2 子树及增量资源为 MISSING；构建未交付门禁通过的 BIT/HWH。须修复时钟关联和层级查询并完整重跑后才可无机械臂上板 DRY_RUN；真实机械臂参数与反馈仍未确定。

### 2026-09-26：S4 v0.1.1 两处构建修复及无机械臂上板候选

- [x] 在独立 S4 副本修复 `phase3_s4_task_top.v` 的四个 AXI 总线时钟/复位关联元数据，BD 退出码 0，原 `BD 41-967` 与 SmartConnect M00-M03 时钟域严重警告消失；0x43C2/43C3/43C4/43C5_0000 地址不变。
- [x] 将实现门禁 `u_motion` 查询修正为 `task_0/inst/u_motion`。Vivado 2026.1 完整实现退出码 0、预算通过，S4 增量 4252 LUT/5030 FF/1.5 BRAM/0 DSP，WNS/WHS +0.227/+0.008 ns，DRC 0 error，生成同次 BIT/HWH/XSA。S4 功能逻辑未改；原版 XSim 17/17 和 OOC 3/3 未重复运行。
- [x] 交付 `deliverables/Gesture_Phase3_S4_PLMotionController_Candidate_v0.1.1.zip`（SHA-256 b379d947d9b9c6307204d4f306262bd517b5c9785e170ca90480395d75b27c9e）和 `deliverables/phase3_s4_task_v0.1.1_20260926.zip`（SHA-256 1afafc2f46490ff99fac08d0b8e4fa9c91d523ed041795ba385cfb4217895d4a）；源码 75/75、板包 33/33 哈希匹配。BIT/HWH SHA-256 分别为 c41d06805fbf6f6ab4e6239de02b6e8376609004fb6e881e28a6e5838db277a3 / 096bc357834c1aeba6a606bdae8cd30ef5bf45470a8f3acb02ce619447952c8c。
- [ ] PYNQ 板端、外部引脚、真实机械臂与 S3 七类视觉联合测试均未运行；仅可按 BOARD_TEST_CN.md 做无机械臂 VISION_SIM/DRY_RUN。

### 2026-09-26：S4 v0.1.1 C1–C5 板测与 v0.1.2 脚本修复

- [x] 用户回传五份 PYNQ 日志：C1/C2/C3 退出码 0 且 JSON PASS；C3 S2 RoArm DRY_RUN 19/19 checks=true、late_count=0、152 帧。C4 退出码 1，`ENABLE rejected: ESTOP`，S4 fault NONE；用户确认当时 D5/motion_enable_in 未接或低电平。S4 ENABLE 必须看到同步后的物理许可为高，故这不是 RTL 故障。
- [x] C5 退出码 1，唯一失败项 `source_is_s1=false`；C4 原脚本在切到 S2 后抛异常，仅 stop 后端而未恢复规划器数据源。这是板测脚本清理缺口。
- [x] 制作 `deliverables/phase3_s4_task_v0.1.2_20260926.zip`（SHA-256 d7570580b4b6a31972957a69080fd6978f389ae3d9d9702bcba9645a2898b24b）：DRY_RUN 在任何配置写入前检查初始状态和 D5 同步许可，低电平清楚报错且不切源；异常时仅在 S4 未持有、规划器排空条件下恢复 S1。低 D5 本地 Fake-MMIO 前置检查通过，Python 语法通过。BIT/HWH 与 v0.1.1 字节完全相同，未重复跑 Vivado。
- [ ] v0.1.2 板端尚未复测。用户接好 D5 的 3.3 V 许可后，重新加载 overlay 跑 C1，确认 `motion_enable_in_ok=true`，再跑 C4/C5；C2/C3 在同一 BIT/HWH 已通过，无须重复。

### 2026-09-26：Phase 3 S5–S8 源码先行交接

- [x] 为无 Vivado/CoppeliaSim/机械臂/RGB-D/AI PC 环境的外部开发者制作 `deliverables/Phase3_S5_S8_Source_Handoff_20260926.zip`，SHA-256 `3324242f63043dc45778b4795cea3c7ad014d0a75c4cb9303b3a24ebf9cf08ee`。包内含 S1 v0.1.1、S2 v0.2.3、S3 v0.1.1、S4 v0.1.1 冻结源 ZIP，S3 视觉基线、S4 v0.1.2 板测脚本、S4 Vivado 结果、总计划、状态说明和 S5–S8 总 Prompt。四个冻结源 ZIP 哈希与既有记录一致。
- [ ] 授权外部开发者先行完成各阶段源码候选、仿真和接口文档；真实七类模型、S4 板测复测、机械臂标定、RGB-D/ROCm 与 S5–S8 阶段出口均待后续实测，交接包不包含 BIT/HWH，也不代表整机闭环通过。

### 2026-09-26：S4 v0.1.2 C1–C5 板端复测

- [x] 用户提供五份日志，保存于 `board_evidence/phase3_s4_v0.1.2_20260926/`。C1/C2/C3 均退出码 0、JSON PASS；C3 S2 RoArm DRY_RUN 19/19 checks=true、late_count=0、frames_tx=152。
- [x] C4 退出码 1，停在写配置前的安全预检：`motion_enable_in_ok=false`、`estop_ok=false`；D5 未接或为低电平，S4 DRY_RUN 正确拒绝继续。C5 退出码 0、JSON PASS，确认 S4 OFF、控制源 S1、无错误。
- [ ] 连接经过确认的 D5 3.3 V 许可后，仅重跑 C1（确认 `motion_enable_in_ok=true`）、C4、C5。C4 的任务完成/取消/故障恢复测试尚未执行，S4 板测未完成。

### 2026-09-27：S4 C4 进入任务测试，急停帧数判据待复测

- [x] 用户回传 v0.1.2 C4 日志，D5 许可 `motion_enable_in_ok=true`，任务完成、回 HOME、取消、PS 写隔离、ABORT 故障/规划器 ESTOP、恢复、释放 S1 均为 true；唯一失败项 `abort_frames_stop=false`。退出码 1；随后 C5 退出码 0。日志保存于 `board_evidence/phase3_s4_v0.1.2_20260926/S4_C4_after_D5_high_20260927.log`。
- [x] 原板测脚本将“FAULT 时帧数已增加”与“FAULT 后增量 ≤2”合并，未报告原始计数；MOVE 已下发时后端可能尚未发帧，因此该失败不能区分零帧误判和真实超限。独立 v0.1.3 包改为 ABORT 命令前采样，0.5 秒后采样并报告计数，仍要求增量 ≤2；仅改 Python 脚本/说明，BIT/HWH 字节不变。
- [x] v0.1.3 脚本 Python 解析与 ABORT 前回调聚焦检查通过；ZIP 34 文件、33 项清单匹配。交付 `deliverables/phase3_s4_task_v0.1.3_20260927.zip`，SHA-256 `a5f9c3c00e34aec5848a9cacc1aa24208eda119115b37fcb68b2731c4b78f212`。
- [ ] 板上 C4 急停后帧数尚无数值，必须以 v0.1.3 C4 输出确认；此前 C4 不能算通过。复测仅需 C1/C4/C5，C2/C3 已通过。

### 2026-09-27：S4 v0.1.3 C1–C5 板端退出码

- [x] 用户回报 PYNQ 上 v0.1.3 包的 C1/C2/C3/C4/C5 退出码全部为 0；C1 后的 Ctrl-C 发生在 shell 提示符处。按 v0.1.3 自检脚本返回码语义，无机械臂 VISION_SIM/DRY_RUN 的五步检查通过。
- [ ] 本轮 JSON 日志尚未提供；`abort_frame_counts.delta` 的实际值及包内哈希未独立核对。结论限于用户回报的脚本退出码，不包括外部引脚波形或真实机械臂。
- [x] 用户补充 v0.1.3 C4 JSON：`abort_frame_counts.at_abort=40`、`after_wait=40`、`delta=0`（ABORT 后等待 0.5 秒）；结合 C4 退出码 0，急停后 DRY_RUN 帧停止判据通过。v0.1.2 的唯一失败项与旧判据要求“此前必须至少发过一帧”的误判相符，但旧日志缺计数，不能反推旧轮的实际帧数。

### 2026-09-27：S5–S8 源码交付包上板准入核审

- [x] 用户交付外层 ZIP SHA-256 `f93e44ef297af60042238b9936af00ebaadc083f9403614ebf933fc3ffd24c3c` 与侧车一致；外层 22/22、五个阶段解压清单分别 49/49、62/62、71/71、37/37、35/35 匹配。审查副本在 `reviews/s5s8_20260927/`；五个阶段包均无 BIT/HWH/XSA。
- [x] S5 是唯一新增联合 RTL 的阶段；包内 XSim/Vivado 均 NOT_RUN，集成 Icarus/XSim 测试中的 S3 为仿真替身。上板前须按依赖锁合并 S1–S4/S5，准备七类导出包（测试权重仅作资源/接口冒烟）、运行 XSim 和 Vivado BD/实现门禁，生成同次 BIT/HWH；当前未做该构建。
- [x] S6/S7 板测说明存在可执行性缺口：S6/S7 服务要求 S4 模式 B、IDLE、owner_s4；现有 S4 v0.1.3 板测脚本使用模式 A 并于末尾 RELEASE，无法充当模式 B 初始化器。S6 BENCH 配置周期 20,000 cycles 与 S4 板测的 20 ms（2,000,000 cycles）不一致。需专用模式 B 初始化/板端配置和网络实测后才可验收。
- [x] S4 托盘补丁未合入，S5 v0.1.0 顶层未透传 TRAY_EXIT；托盘归还无法用本包上板测试。S8 仅日志/指标工具，不需新 BIT。真实七类模型、窗口/机械臂/RGB-D/ROCm 标定和实测仍缺，不能验收真实任务。

### 2026-09-27：S5–S8 独立上板包与本地门禁

- [x] 在独立 `s5b/` 合并冻结 S1/S2/S3/S4 与 S5；S5 依赖锁 61/61，Python 29/29，XSim 4/4。S3 在联合 XSim 场景使用仿真替身；实构建使用七类随机测试权重（`RTL_TEST_RANDOM_WEIGHTS`），不代表真实识别。Vivado 2026.1 BD/实现/DRC/时序/预算通过，WNS +0.011 ns、WHS +0.017 ns，整体 23,061 LUT、63 BRAM tile、42 DSP；同次 BIT/HWH 均生成。
- [x] S6 修正方形检测框 yaw 在不同 OpenCV 版本下的非确定性，再生黄金路径；Python 76/76、S4/S2/S1 XSim 4/4。新增 20 ms 的 BENCH 模式 B 初始化、触发与合成 PC 客户端，部署包离线配置检查通过。S6 没有新 RTL，沿用 S5 BIT/HWH。
- [x] 在独立 `s7b/` 将 S4 托盘补丁接入 S5 联合顶层，显式 `TRAY_EXIT=1`、ABI 0x3402；S4 托盘 RTL XSim 6/6，原 S7 Python 26/26，与修正 S6 组合功能测试 24/24。Vivado 2026.1 BD/实现/DRC/时序/预算通过，WNS +0.064 ns、WHS +0.013 ns，整体 23,283 LUT、63 BRAM tile、42 DSP；同次 BIT/HWH 均生成。S8 Python 19/19，无新增 RTL，复用 S7 硬件。
- [x] 交付 `deliverables/phase3_s5_board_testweights_20260927.zip`（SHA-256 `192a14b33d7f76057bdfb2e651ec721defc3238bf20b5db3ad1e0ee4f7e9661e`）、`phase3_s6_board_bench_20260927.zip`（`dac588c265a891f95ef0d3aa6adf8f184bb9659ee5dd5c550671969322e0efea`）、`phase3_s7_tray_board_bench_20260927.zip`（`70505dc81e281dff0d32bbdca2eae4037ca5e45af9912d079f8e65db28c652a4`）、`phase3_s8_board_metrics_20260927.zip`（`1e64785382601e2eb4bb74e5e7bf480c3365258a698341bb6c565af61c278a2b`），各带 SHA256SUMS 和侧车，封包后逐项核对。每包有板测接线、命令、判据及本地验证摘要。
- [ ] 四阶段 PYNQ 上板、相机帧、PC↔PYNQ 网络及托盘真实动作未测；真实七类权重、RGB-D/IK/机械臂标定与实测缺失。当前包仅允许无机械臂的随机权重、合成视觉/IK、DRY_RUN 台架测试，不可用于真实机械臂任务验收。

### 2026-09-28：S5 测试权重 BIT 上板冒烟

- [x] 用户回传 S5 C1–C4 退出码均为 0，日志存于 `board_evidence/phase3_s5_testweights_20260928/`。C1 ABI、S4 OFF、SOURCE=S1、窗口关闭全通过；C2 相机约 23.4 fps、fresh/valid、无 S3 fatal、stale_events=0；C3 D5 许可为高，任务完成/取消、PS 写隔离、ABORT 后帧数增量 0、恢复与释放源全通过；C4 S4 OFF、SOURCE=S1、无错误。中间重新加载的第二次 C1 退出码 0，但同名日志已覆盖，仅保存最终 C1 内容。
- [ ] `stable_class=7` 来自随机测试权重，不能评价真实七分类；S5 的真实手势识别与机械臂测试仍未执行。S6 可沿用同一硬件设计进行无机械臂的模式 B 合成路径台架测试；其 PC↔PYNQ 网络及路径提交结果待回传。

### 2026-09-28：S6 模式 B 上板准备

- [x] 用户报告在 `pynq/` 内重新运行 S6 C1/C2/C3 后退出码均为 0；最终 C3 JSON 为 `mode_b=true`、`owner_s4=true`、`state=IDLE`、`s1_mode=DRY_RUN`、`period_cycles=2000000`、`tray_exit=false`。首次在包根目录执行 C1 因脚本路径错误退出 2；C3 成功后立即重复执行时因 S4 不再处于 OFF/无所有权状态而拒绝，重新加载 overlay 后 C3 通过。这两个中间退出码不表示硬件故障。
- [ ] S6 路径服务、PC 合成客户端、PATH_COMMIT、DONE/DUPLICATE 和断链场景尚未回传。完成当前模式 B 准备后勿再运行 C1/C3，否则会重置或重新配置 S4。
- [x] 首轮 S6 PC 正常客户端连接到 PYNQ 50555 后等待 HELLO 超时；用户板端 `ss` 显示 PID 5880 占用端口，`ps` 的 `STAT=T+` 确认原服务被终端挂起（仍监听但不处理请求）。第二份服务因端口占用退出 98，并覆盖了同名服务日志；此时没有发出 OBJECT 触发。需恢复/终止挂起进程，用新日志名后台重启服务后再测；不需重载 BIT 或重跑模式 B 初始化。
- [x] 后台服务 PID 9777 已监听 50555；PC HELLO 成功后等待 TARGET_REQUEST 超时。板端触发脚本在注入 OBJECT 前报 `this trigger is for S1 DRY_RUN only`。定位为脚本读取 S4 的 `T_S1_STATUS` 缓存：S4 在 IDLE 尚未做 OP_POLL，缓存可能仍为复位值 0；S4 RTL 于任务开始后的 PRECHECK 才刷新并检查 S1 模式。C3 旧 JSON 的 `s1_mode=DRY_RUN` 为硬编码文字，不能证明实时 S1 模式。
- [x] 修正 PS 脚本：触发前直接读 S1 0x43C3_0000 STATUS，要求实时 DRY_RUN、无 S1 fault、D5 许可高；C3 初始化 PASS 也读取并记录实测 S1 STATUS。新增缓存为 0 而实时模式为 DRY_RUN 的正例与实时 OFF 拒绝负例，S6 Python 78/78。BIT/HWH、RTL、地址、ABI 均未改变。提供双文件热修复 `deliverables/phase3_s6_ps_trigger_hotfix_v0.1.1_20260928.zip`（SHA-256 `7e5cc92ae01508ac698096aba11574fcbc173465ce18dc244ca7652efce1664b`），以及更新完整 S6/S7/S8 包：S6 `90ec02bab11f6494995b53b2e2ed4a52ec6ecd80071b5fe80b93b9051cb2933a`，S7 `1db5f4f490e95e3f0abaf5d3a00a7bcd1cb52745f5b31d71eaa47158f460caaa`，S8 `25218e4571954f9ee3c87ed19732c1c5943f088bce132fb6046e4d37e3615891`。上板复测未回传。
- [x] 用户在 S6 v0.1.1 完整包的 PYNQ 目录直接读取 S1 状态：`active_mode=1`（DRY_RUN）、`fault=0`、原始 STATUS `0x00001029`；因此上一轮触发失败确为 S4 空闲缓存误判，实时 S1 模式允许继续无机械臂合成路径测试。新触发脚本与 PC 的 COMMITTED/DONE 结果尚未回传。
# 2026-09-28 — Phase 3 S6 board bench (v0.1.1)

- S1 live status: `active_mode=1` (DRY_RUN), `fault=0`, raw `0x00001029`.
- S6 service listened on `0.0.0.0:50555`; physical arm disconnected; D5/motion_enable_in held at 3.3 V for the dry-run bench.
- Normal synthetic path: board exit 0, `IDLE`, `done=1`, `cancel=0`, `fault=0`, PALM sent; PC log reported `COMMITTED`, `DONE`, and duplicate `DUPLICATE`.
- Disconnect before PATH_SUBMIT (`drop_waiting`): PC exit 0; board exit 0, `IDLE`, `done=0`, `cancel=1`, `fault=0`, PALM not sent.
- Disconnect after COMMITTED (`drop_committed`): PC exit 0; board exit 0, `IDLE`, `done=1`, `cancel=0`, `fault=0`, PALM sent.
- Conclusion: S6 synthetic TCP/PS/S4/S2/S1 DRY_RUN bench scenarios pass. Real vision, physical link loss, IK, and physical arm motion remain untested. Next: S7 board validation.
- S7 test-plan correction: the packaged S7 tray scenario ends with `CANCELLED`; `board_s6_synthetic_client.py --mode normal` requires `DONE` and would report failure. For the no-arm tray bench use `--mode drop_committed` so the PC confirms COMMITTED and closes, then inject FIST from `board_mode_b_trigger.py --fist-at-move 4 --expect-tray`. Judge the final tray/cancel state from the board log.
- S7 no-arm tray bench, user-reported: `phase3_s7_board_readonly.py` C1/C2 both exit 0; C1 `s4_tray_abi/s4_off/source_is_s1/window_disabled=true`. C3 config check exit 0. C4 `--prepare --tray` exit 0 with mode B, S4 ownership, IDLE, S1 DRY_RUN, 2,000,000 period cycles, tray_exit true, physical_arm_connected false. PC synthetic `--mode drop_committed` exit 0. Board `--object 2 --fist-at-move 4 --expect-tray` exit 0, `IDLE`, `fist_sent=true`, `tray_seen=true`, counter deltas done 0/cancel 1/fault 0, PASS. C1-C4 and orchestrator were invoked from `phase3_s7_tray_board_bench_20260927/pynq`; PC and trigger from `phase3_s7_tray_board_bench_v0.1.1_20260928`. S7 v0.1.1 changed PS scripts only; hardware BIT/HWH are unchanged. The pasted service startup snapshot after two seconds showed only `config OK`, with no listener line yet; the later successful PC and board test demonstrates a service accepted the test connection. Preserve S7_PC.log, S7_TRAY.log, S7_SERVER.log, S7_PS.jsonl as evidence. Real tray/arm motion and true gesture recognition remain untested.
- S8 v0.1.1 metrics-tool smoke, user-reported: `collect_run.py` on the S7 PS JSONL plus S7 build results exited 0, copied 2 files/1 run, `simulation=False`, `schema problems 0`; `compute_metrics.py` exited 0 and wrote `metrics.json` with `MEASUREMENT` status; `render_report.py` exited 0 and wrote `REPORT.md`. The generated manifest/metrics/report contents have not yet been inspected in this session, so quantitative and NOT_MEASURED fields are pending review. This validates the tool flow on one synthetic S7 DRY_RUN tray-cancel run, not real gesture or arm performance.
- S8 report content audit: read `REPORT.md`, `metrics.json`, and `run_manifest.json`. The input bundle has one PYNQ PS event log (22 records, no schema problems) and one S7 Vivado gate text file. It reports one B_AI_PC `TRAY_RETURN` state, one FIST cancellation, log-state return 1/1, measured PS-clock intervals of 118.725 ms select-to-commit, 727.660 ms commit-to-end, and 846.385 ms select-to-end. All P90/P95/P99 are correctly `INSUFFICIENT_SAMPLES` for n=1. Gesture classification, false triggers, physical delivery/return, PC/network/PL/arm latency remain `NOT_MEASURED`. `MEASUREMENT` and `simulation=false` mean the event log came from a real PYNQ run; the request/IK and tray action were synthetic/DRY_RUN, so 1/1 is not physical success. Wording issues: report should label the 1/1 as log-state return and surface the bundle's synthetic/no-arm note; `latency.pl_internal.reason` names S4 v0.1.1 although the S7 tray overlay uses ABI 0x3402. No numeric discrepancy found in the provided report.

### 2026-10-02：AI 指令与 Git 协作流程整合

- [x] 经用户审核后，将仓库自动入口写入 `AGENTS.md`，项目约束写入 `AI_INSTRUCTIONS.md`，通用 FPGA 方法写入 `.agents/skills/fpga-development/SKILL.md`；个人 `gesture-fpga-dev` skill 收敛为指向仓库的入口（位于用户目录，不在 Git 中）；更新当前上下文与总体计划中的实际 Windows AI PC（约 64 GB）和 ROCm 待验证边界。
- [x] 固定个人分支的安全获取/提交/推送流程、合理阶段划分、逐版封装、精确测试和接线说明、证据级别、日志、资源与时序检查；保留既有未跟踪交付与板测资料。
- [ ] 本轮仅修改流程文档，没有改变 RTL、模型、BIT/HWH 或板卡接线；仿真、综合、实现和上板均 `NOT_RUN`。ROCm 7.14.0+ 在本机 Windows 原生环境的可用性以及真实七类/机械臂闭环仍待专项验证。


### 2026-10-03：Phase 3 PreDemo Frozen v0.1.0 封存与后续架构计划

- 用户要求暂时封存现有候选并讨论后续优化。读取仓库入口/AI 要求/当前上下文与 FPGA skill；确认个人分支 dev/filid、origin 为 filid-123/Gesture；跟踪文件初始干净，保留所有既有未跟踪资料。fetch 后个人分支 ahead/behind 0/0，ff-only pull 返回 Already up to date；未合并 main 或队友分支。
- 输入代码基线 e848dc198e1e383ac7c3a2f84a344f05306d5a3e。本机封存包 deliverables/Gesture_Phase3_PreDemo_Frozen_v0.1.0_20261003.zip，9,742,685 bytes，SHA-256 750d67e7a04e9ac3b9e16b84df4212a60d86c87cf83a0f7f2a49dede4cedd77c。包含输入 Git archive、选定 S7 集成源码/测试/初始化模型/报告、10 个明确的最新阶段与 AI PC 交付 ZIP、现存阶段证据及本轮说明/计划；未复制可再生输出/虚拟环境/历史备份/原始数据集，未覆盖既有资料。状态 FROZEN_CANDIDATE，ZIP 不加入 Git。
- 实际验证：10 个原交付 ZIP CRC 与 652 项内部 SHA-256 通过，有侧车的 ZIP 均匹配；外层清单 173 项 SHA-256 通过、174 个 ZIP 成员完整列入（含 SHA256SUMS 自身）；7 组原始 BIT/HWH 的唯一性/同名配对通过，S7/S8 板包与本机 S7 实现目录的 BIT/HWH 哈希分别一致。哈希和配对核验不等于本轮重新构建或实物验收。详细描述见 docs/PHASE3_PREDEMO_FROZEN_v0.1.0.json。
- 新增 docs/PHASE3_NEXT_DEVELOPMENT_PLAN_CN.md 与封存说明/描述，更新 CURRENT_PROJECT_CONTEXT.md。用户确认 RoArm-M3-Pro 仍为候选、首版保留双后端；手部水平微调延后到首版成功后再确定。计划顺序为真实固定点首版闭环、S2 统一运动入口、原生命令/状态接口与实测裁剪；保留或迁移 mux 缓冲/背压/LAST_DELIVERED、初始化/owner/ABI、window 的原子配置/快照/超时语义。5%～8% 资源收益只作假设。
- 本轮 RTL/模型/驱动/工程配置未修改；只进行文档与明确授权的版本封存，按 AI 要求不运行通用工程备份。XSim/Vivado/上板/真实机械臂测试 NOT_RUN。继承 S7 整机历史结果：23,283 LUT、17,034 FF、63 BRAM tile、42 DSP，WNS/WHS +0.064/+0.013 ns，失败 setup/hold 端点 0；不是本轮实现结果。
- 上板条件继续采用原板包说明；真实机械臂型号/固件/接口/单位/限位/许可/急停与可持续周期未冻结，当前无新的实物动作许可。回退先在隔离目录核验并解压封存包，保留旧 BIT/HWH/发布基线，不直接覆盖当前工程。
- 下一步：实物参数确认与最终视角七类模型/量化交付，在现有可观测结构上逐版完成首版模式 A 真实闭环；之后才进入架构收敛。此次仅提交上述明确的文档/清单到 dev/filid，并用 phase3-predemo-v0.1.0 标签定位封存说明；大包和未跟踪集成资料保留本机，远端不冒充已有完整包。

- 本轮额外核对既有 post-route 层级报告：SmartConnect 450 LUT/476 FF；旧 S1 轨迹链 1,966 LUT/1,909 FF/3 BRAM/14 DSP；S4 link 944 LUT/776 FF；formatter 503 LUT/211 FF。用于确定优化优先级，不能把现有占用当作未来净节省。

### 2026-10-03：Phase 3 CoppeliaSim Closed Loop v0.1.0

- 用户尚未购买机械臂，七分类由队友优化；明确要求先用 Python 和自行调度 CoppeliaSim 打通执行反馈闭环，之后由用户做 FPGA 上板闭环。遵守 Gesture/FPGA skill；开发前确认 dev/filid、跟踪文件干净、保留所有既有未跟踪资料；fetch/pull --ff-only 返回个人分支已最新。输入基线 6928cd7488da56b15b8c9ef9640cb336a6b7f89d；代码/输入备份 backups/phase3_coppelia_before_v0.1.0_20261003.zip，SHA-256 5915d73e2d4c78a50b7fdb7470c5cdb7014719be253abde8435c7f1c0ee1b043。
- 新增 sim/phase3_closed_loop：稳定类别注入、原 S4 FSM、S2 位精确采样、S1 原单位映射与 fixture 格式化/解析、TCP 虚拟 UART 字节流、实际 CoppeliaSim 六关节与物品、场景反馈、到位/通信监控、原 S8 指标。模式 B 经实际 HELLO/TARGET_REQUEST/PATH_SUBMIT/STATUS，完整提交与重复拒绝；不逐点 PC 控制板端。复制 20 项原 S8 依赖/模板，来源锁逐项 SHA-256 相同，源文件不改。新增独立事件适配器与仿真准入适配器。
- 实际环境：Windows 原生 Python 3.12.10、CoppeliaSim 4.10 rev0、Remote API 2.0.4、pyserial 3.5、PyYAML 6.0.3、pyzmq 27.2.0。自行启动 headless 原场景 roarm_m3_phase3.ttt（SHA-256 42980fe3985916a14243afc97dcb772c02e47dd1cb91e786f177470dfd26d201）；停止状态运动学、位置 IK、几何父子关系抓取。所有测试后关节恢复零位，临时物品/桥清除，关闭本轮启动的仿真进程，没有保存覆盖原场景。
- 验证：Python 10/10 单测，覆盖分帧、坏帧/限位/长行拒绝、测量反馈与目标分离、反馈消失、B 事件竞争、真实 LINE 门槛保留、虚拟准入与重复提交。11/11 实际场景通过：A/B 各三物品正常交付、A1 持物取消归位、B2 持物取消托盘、A1 PALM_TIMEOUT 归位、A1 反馈消失 COMM_TIMEOUT、A1 肩关节阻塞 ARRIVAL_TIMEOUT；故障停止且无释放。S8 全部 SIMULATION、schema_problems=0。六个正常任务物品落点误差最大 0.102995 mm；回零门槛 0.00035 rad（考虑固定点/小数映射量化）。按最小 20 ms 节拍另测 A1 通过，墙钟 41.7987 s、逻辑 19.84 s、虚拟 UART RTT 最大 82.6471 ms，不能宣称持续 50 Hz；独立 200 次场景 RPC 均值 0.6837 ms、P99 1.1307 ms、最大 76.3701 ms。prepare/cleanup 通过，A/B 板配置检查、Python 编译、依赖锁核对通过。独立交付目录 10/10 单测与配置检查通过，证明打包依赖闭包完整。
- 开发失败证据全部保留于 reports/phase3_coppelia_closed_loop_v0.1.0：伸展零位附近预交付点不可达，工作区下移 50 mm 后全部关键点逆解通过；表终点必须使用 HOME/PRE_DELIVERY 专用索引；S8 模板遗漏/data_kind 字段修正；50 ms 虚拟 UART 等待在 Windows 偶发无初始反馈，增至 250 ms；模式 B service.step 与 supervisor.take 第二次 drain 的竞态导致 SELECTED 仅进入 task=0，无 TARGET_REQUEST，改为服务单次 drain、监督器消费副本，晚到事件留至下次服务处理，回归与三个 B 场景复测通过。初次封包对含点版本目录误用 with_suffix，ZIP 名称截短；打包脚本已修正，最终包使用完整版本文件名。
- 提供 prepare_scene、executor.py --serial、board_load、board_loop、board_gesture、pc_submit：用户可以使实际 S7 PL UART 驱动同一 CoppeliaSim 执行器，场景读回经 UART 回到实际 S1；初始化在 DRY_RUN 种 HOME 后才进入 no-robot bench LINE，校验六通道反馈与场景 HOME。虚拟 service 仅在显式 simulation_only/fixture/no-robot + BENCH/无真实标定前提允许路径准入；原生产 service 的真实执行保护保留，S4/S1 实际 LINE 状态与监控不变。板端退出请求 ESTOP/OFF；强杀仍需 D5 去许可。
- 上板条件：PYNQ-Z2，原 S7 matched BIT/HWH；断电去原 UART 回环，无机器人/舵机总线。3.3 V TTL USB-UART：D1/U12 TX→适配器 RX，适配器 TX→D0/T14 RX，共 GND，D5/T15 接板端3.3 V许可，适配器 VCC不接板卡；D2–D4不接，PMOD相机口不改；115200 8N1。先只读加载→场景准备/executor READY→模式 A，后模式 B网络8765，PALM/FIST显式注入。命令、阈值、失败停止、恢复、回传资料见 sim/phase3_closed_loop/README_CN.md。
- 本机最终可测试包 deliverables/Gesture_Phase3_CoppeliaClosedLoop_v0.1.0_20261003.zip，3,942,746 bytes，SHA-256 39dadf5ab71bc402a73ad3ee82004418635d0bb358be5d80229e3378304c45bb；253成员，ZIP CRC和252项成员SHA-256通过（不含SHA256SUMS自身）。包含实际需要的源码/脚本/fixture配置/原场景/原BIT与HWH/约束/成功和失败证据。原BIT SHA-256 00adb89234b3acb8da7488af20175c759162a2c03442b344c839002b17e03f62；HWH ebe35405dafbdb98fd6855044ae79e22867ba54da08e465027b89f500a9416f1，与既有S8包同名配对。ZIP和原始报告不加入Git；本轮源码、来源锁、测试摘要、README和项目文档提交个人分支；局部gitattributes保留冻结输入的原始字节，避免Git换行转换破坏来源锁。
- RTL、AXI/ABI、约束、双后端、活动权重均未修改；Vivado/XSim/FPGA→UART→Coppelia板测/真实七类/RGB-D/碰撞接触动力学/实物机械臂 NOT_RUN。资源时序仅继承历史S7：23283 LUT、17034 FF、63 BRAM、42 DSP，WNS/WHS +0.064/+0.013 ns，不是本轮新实现。状态 SIMULATION_PASS_BOARD_NOT_RUN。下一步由用户按本包完成A/B实际PL执行反馈板测并回传JSONL/BOARD_RESULT/终端全文/接线照片；七类模型优化可继续独立推进。

### 2026-10-06：CoppeliaSim 板端模式切换热修复 v0.1.1

- 用户反馈：原 S7 board_load/现场配置 PASS；完整 board_loop 静默退出，PIPESTATUS=135/0，日志仅头部，无 FAILURE.json；内核 external abort 虚拟0xb6fbc004，映射页0x43c30000，偏移0x004（S1 MODE）。板端 RTC 显示2025-05-09，与用户当前日期不一致，保留单调时间诊断，不用其墙钟推断跨主机延迟。
- 板端后续用户实测：MODE读写OFF通过；完整S1配置/提交/清错/清计数及OFF→DRY_RUN→OFF通过，STATUS=0x1009，退出0。这些是用户板端证据，不是本机板测。
- 根因核对：原S7 arm_backend_axi_top.v REG_MODE拒绝不同非OFF模式直接切换；原board_loop在S2 HOME后直接DRY_RUN→LINE，返回SLVERR，在Zynq裸MMIO路径导致SIGBUS。修正为先OFF、等待实际OFF/idle、要求配置有效且无fault，再带原bench_loopback许可进入LINE；保留配置和LAST_DELIVERED/HOME。增加INIT进度和faulthandler使后续native abort可见。
- 当前dev/filid跟踪文件初始干净，fetch/pull为最新，保留既有未跟踪文件。修改前git源码备份backups/phase3_coppelia_before_v0.1.1_20261006.zip，输入提交c5c489282cdc81dfb4ee976fdff37eb2c4590e99。
- 实际软件验证15/15单测通过：新增5项覆盖原模式直切被拒绝、OFF/idle等待与许可传递、无效配置/fault/busy超时不进入LINE；既有10项回归通过。配置检查PASS。RTL/BIT/HWH/ABI/引脚/权重/Windows执行器未改，Vivado/XSim和v0.1.1实际板端闭环复测NOT_RUN，不复用Python场景通过冒充该补丁板测；无新资源时序结论，继承既有S7结果。
- 可覆盖旧板包的本机热修复deliverables/Gesture_Phase3_CoppeliaModeHotfix_v0.1.1_20261006.zip，7420 bytes，SHA-256 aadbff4ead14695962ea4c488d2c857b8c5ad91dad30803821f597c2d61e2581；5成员（4项内部SHA-256加SHA256SUMS），CRC及成员字节检查通过。包含board_loop.py、聚焦测试、说明、PATCH_INFO；ZIP不提交Git。源码、README/当前上下文/日志/热修复说明推送个人分支，不更新main。
- 上板复测：沿原3.3 V TTL UART交叉TX/RX、GND、D5许可、无机械臂；先去许可、停旧进程并备份原脚本，解压补丁至原板包根目录；重载原BIT、重新准备Windows场景和配置、executor READY、恢复许可，用新runs/board_A1_003且不接tee运行。观察INIT各阶段及OBJECT injected，WAIT_PALM时注入PALM；回传终端/BOARD_RESULT/PS与sim JSONL。异常去许可、停执行器、保留调用栈/dmesg，下一步由用户完成板端复测。

### 2026-10-06：CoppeliaSim 板端启动保护 v0.1.2 与 S2 START SIGBUS 诊断

- 用户 v0.1.1 A1_003 BOARD_RESULT：PASS/RETURNED_TO_SLOT/PALM_TIMEOUT，fault/refuse NONE，frames_tx1068/fb_ok3640/fb_err0/resp_timeouts0。实际 FPGA/UART/Coppelia 取消路径的板端判据通过；PC sim_events/物品末态/HOME 未回传，正常 DONE 尚未验收。
- A1_004 在 INIT: S2 HOME in DRY_RUN、planner_axi_driver.start 的 CONTROL 写入发生 native SIGBUS，exit135。用户明确回答该轮之前已重载 BIT 且旧 board_load PASS。故障后完整 S2 状态尚未取得，不能把本轮定性为漏载，也不能把防护测试当作实际重载故障修复完成。
- 阅读项目入口/AI/上下文/FPGA skill，确认 dev/filid 与 origin、跟踪文件初始干净，保留原未跟踪资料；fetch/pull --ff-only 为最新。同一 fetch 看到队友 dev/Giao 远端前进，仅获取，不合并。输入基线 a87fa8b19a9ab3dbb7d56445b3a67dd1ffa39406；源码备份 backups/phase3_coppelia_before_v0.1.2_20261006.zip，SHA-256 ce06873b9d8096e6c28e4e9ef7e05217766c610fe43ebadbeed263dd4e0a34a6。
- RTL 核对：S2 START 只接受 IDLE/DONE、S2 source、无 core/downstream/S1 活动待发，非法返回 SLVERR。board_loop 结束 ESTOP；旧 board_load 未检查 S2 IDLE，因此 S4 OFF 与 JSON PASS 不等于可重新 START。
- 新增 board_state.py，只读输出 S1/S2/S4 状态及 checks；加强 board_load 重载核对；board_loop --check-board、配置前门禁/PREFLIGHT 文件与 HOME START 二次检查。门禁失败保存 FAILURE、不配置/START、不 CLEAR、不在 finally 再停机写入覆盖现场。保留 v0.1.1 模式切换及原结束 ESTOP，每轮仍需重载/准备场景。未修改通用 planner 驱动/冻结 S8 依赖/RTL/BIT/HWH/ABI/引脚/模型/Windows执行器。
- 软件测试22/22 PASS（原15+新增7，覆盖残留 ESTOP、忙/待发/错误/源与控制权、读检查、START 合法性及 main 拒绝无写入）；JSON配置PASS。首次新增 main 测试的 Mock 禁止 assert_abi 方法，改为指定真实驱动 spec 后通过，这是测试替身修正。原v0.1.0 ZIP加补丁在隔离 runs/hotfix_v012_validation 独立运行22/22及配置PASS。没有新增场景动作、Vivado/XSim或v0.1.2实际板测，均NOT_RUN；资源时序沿用S7历史证据，未生成新数字。
- 本机补丁 deliverables/Gesture_Phase3_CoppeliaStartupGuard_v0.1.2_20261006.zip，12329 bytes、8成员、SHA-256 18752979fce9098db89e9994e5b2d26ff85f4be1587799d93a9e12da23de9e65；ZIP CRC、内部7项SHA256与成员字节核对通过。包含board_loop/load/state、两组聚焦测试、说明与PATCH_INFO/SHA256SUMS，原完整包依赖不重复打包；ZIP不加入Git。只选择源码/说明/README/上下文/日志提交个人分支。
- 本次板端步骤：去D5许可、停executor、备份并覆盖补丁，先 --check-board 保存崩溃后状态，再新版 board_load 与 --check-board 保存重载状态。无额外接线/实物机器人；3.3V TTL、TX/RX交叉、GND、适配器VCC不接。FAIL退出1是诊断保护，不自动CLEAR/START；回传两份BOARD_PREFLIGHT及加载输出。全部PASS后再新建停止场景、复制新配置、executor READY/恢复D5、新目录测PALM正常DONE。异常保留PS/sim JSONL、faulthandler/dmesg，去许可停止。

### 2026-10-06：v0.1.2 A1 正常 FPGA/UART/Coppelia 闭环验收

- 用户回传 A1_004 故障后完整 PREFLIGHT：S1 DRY_RUN/idle，S2 ESTOP/source1/last_valid/errors ESTOP+COMMAND_CONFLICT，S4 OFF/owner released；只读FAIL/exit1。随后实际重载 S7 BIT，S1 OFF/idle/no fault、S2 IDLE/source0/无历史/待发/错误，load及check-board均PASS/exit0。S2非法START解释得到一致状态证据，本次正常重载恢复确认；不改写用户此前已重载的陈述。
- 用户 board_A1_005 stdout：PREFLIGHT PASS，S1配置、S2 DRY_RUN HOME、OFF/idle→LINE、实时反馈、OBJECT1全部越过；监视显示OFF→IDLE→RUN OUT→holding→WAIT_PALM，用户注入PALM；BOARD_RESULT PASS、DONE、exit0、fault/refuse NONE、TX988/FB2870/fb_err0/resp_timeouts0。PS单机task start至end为38.800180041 s，包含人工等待，不当作硬实时延迟；原始板端PS/BOARD_RESULT文件尚未拷回，摘要明确来源为用户stdout。
- 直接读本机交付目录runs/board_scene_005的实际配置和完整sim_events；冻结两个输入至reports/phase3_coppelia_board_A1_005_20261006并计算SHA256，写验收JSON到docs/evidence/phase3_coppelia_A1_005_20261006.json，报告同时保留本机副本。验证7项判据全部PASS：一次抓物品1（frame338）、一次释放（frame790）、先抓后放、最终无附着、交付误差≤2mm、HOME≤0.00035rad、其他物品未移动。实测落点误差0.08748110729619mm，HOME误差0rad、物品2/3位移0；日志2891次观察、984 UART命令帧。板端TX数包含初始化，与场景物理命令数分别记录，不据此声称丢帧或持续频率。
- 末尾PC反馈为[0,0,0,0,0,1.5]，与本轮配置HOME一致；因此之前板端BOARD_RESULT中较早快照与最终命令不相同，并不代表最终未回HOME。本轮以执行器末态完成核对，没有调整控制代码或容差，没有向运行场景写入/重载/清理。
- 分支dev/filid跟踪文件初始干净，fetch/pull ff-only最新，保留既有未跟踪数据。此次仅新增/更新验收JSON、当前上下文、README及日志，按项目规则无工程备份、无额外镜像测试/新版本包。Git只提交上述四项文档/证据；完整PC快照保留本机，原BIT/HWH/RTL/ABI/接线/Windows和PS脚本均未修改，资源时序不新增。
- 结论：真实FPGA S4/S2/S1→3.3V UART→CoppeliaSim→UART反馈的A1正常交付单例PASS，手势仍明确注入、场景仍停止状态运动学/几何抓取。A1_003掌心超时归还只有板端判据，末态尚未核对；A2/A3和B板测、七类真实模型、物理机械臂/官方协议/标定、动力学/碰撞/接触、持续50Hz及完整S8配对原始日志指标未验收。下一步A2/A3、再B，每轮重载原BIT/准备新停止场景与配置，executor READY和D5许可后执行。

### 2026-10-06：v0.1.2 模式 A 三物品正常交付板测验收完成

- 用户新回传runs/board_A1_010实际object_id2和board_A1_011实际object_id3，均PASS/DONE、fault/refuse NONE、反馈错误/响应超时0；A2 TX1040/FB3115、A3 TX956/FB3004。本次JSON没有进程退出码，验收摘要标记NOT_PROVIDED，不沿用A1的exit0。此前board_A1_007/008均object_id1，保留为重复A1，不当作A2/A3。
- 实际读取并冻结本机board_scene_010/011配置与完整sim_events到reports/phase3_coppelia_board_A2_010_20261006和A3_011；两组7项末态判据均PASS。A2 grasp attached2/frame338、release/frame842、最终attached0，误差0.10299541269381984mm、HOME0rad、其他物品位移0；A3 grasp attached3/frame338、release/frame758，最终attached0，误差0.06715360964112974mm、HOME0rad、其他物品位移0。场景命令帧1036/952、观察3134/3039，分别记录，不推断硬实时频率。
- 新增docs/evidence/phase3_coppelia_A2_010_20261006.json与A3_011摘要，包含来源SHA256/字节数、对象身份、抓取释放事件、末态/阈值及用户板端报告来源；输入快照及report哈希/结果检查PASS。原始PYNQ PS日志/结果文件尚未拷回，不能基于派生摘要伪造S8日志。
- 加上已验收A1_005，模式A三个固定物品正常交付的实际FPGA/UART/Coppelia场景闭环判据通过，最大落点误差0.1029954mm。真实分类器/RGB-D/物理机器人、动力学/碰撞/接触、持续50Hz、端到端同步延迟和模式B板测仍未验收；A1_003掌心超时取消仍只有板端判据，无本轮追加场景末态结论。
- 新增docs/PHASE3_COPPELIA_MODE_B_BOARD_TEST_CN.md：沿原TTL接线/权限与新场景/配置/重新加载，先启动B2 board_loop监听TCP8765，再PC提交完整路径（从TARGET_REQUEST取得object，不额外指定），保留双PC进程（UARTexecutor与PCsubmit）；COMMITTED后WAIT_PALM手动PALM，期望B_AI_PC/object2/DONE及物品/HOME。随后新轮FIST期望TRAY_RETURN。网络IP须取用户实际板卡地址，60s会话等待，异常去许可/保留日志，禁止自动CLEAR/绕过网络。
- 读取AI/上下文/FPGA skill，确认dev/filid跟踪文件初始干净，fetch/pull ff-only最新，保留既有未跟踪数据。本轮仅证据和文档/上下文/日志变更，不改RTL/BIT/HWH/ABI/引脚/脚本，不做工程备份/镜像测试或新版本包；本机PC原日志保留，Git只选择两个JSON及模式B说明/README/上下文/日志推送个人分支。

### 2026-10-06：v0.1.2 B2 正常网络提交与实际执行闭环验收

- 用户 board_B2_015：PASS/B_AI_PC/object2/DONE，SELECTED、PATH_ACCEPTED、TASK_DONE，无fault/refuse，TX1040/FB3097/反馈错误0/响应超时0。板端摘要明确来源为用户粘贴BOARD_RESULT；原始PS文件与进程退出码未拷回。PS单机任务42.112532313秒、start到commit121.637385毫秒，含人工等待/软件提交，不是跨主机感知执行延迟。
- 前序B2尝试分别遇到D5断开导致ENABLE ESTOP、重复输出目录、60秒会话超时、缺少运行中的UART执行器；用户Test-NetConnection确认实际192.168.2.99:8765可连。本机核对COM16为CH340，启动场景013的独立执行器及临时PC等待启动器；后者只重试TCP连接，接通后仍使用原pc_submit HELLO、完整路径提交和STATUS，没有绕过原协议、修改PL或替代反馈。
- 读取本轮完整PC/执行器日志，确认BENCH会话、task1的5段路径、COMMITTED及最终STATUS DONE；stderr均空。场景3121次观察、1036命令帧，一次grasp物品2/frame338、release/frame842；最终attached0、交付误差0.10299541269381984mm、HOME0rad、其他物品位移0，7项场景判据及4项PC判据PASS。
- 冻结配置、descriptor、sim/PC JSONL、双方stdout/stderr与临时连接启动器共9份输入至reports/phase3_coppelia_board_B2_015_20261006，计算来源字节数/SHA256并新增docs/evidence/phase3_coppelia_B2_015_20261006.json。本轮PC启动器已自行退出；核对PID/命令行后仅停止本轮执行器，不关闭用户CoppeliaSim。快照保存后cleanup恢复初始姿态并删除013临时对象/descriptor，重新prepare_scene生成停止场景016。
- 当前dev/filid跟踪文件初始干净，fetch/pull ff-only最新；本轮只选择验收JSON、README、上下文和日志提交/推送，保留全部既有未跟踪文件。核心PS/PC脚本、RTL/BIT/HWH/ABI/引脚/模型不变，不新增工程备份/版本包/镜像测试；资源时序沿用既有S7，不生成新数字。
- 模式A三物品及B2正常完整路径/执行反馈闭环通过；结论限注入手势、停止状态运动学/几何抓取。B1/B3、B2 FIST托盘取消的实际板测、真实七类/RGB-D/物理机械臂/接触动力学/持续50Hz及S8配对原始日志指标待验收。下一轮场景016、COM16、原BIT/v0.1.2、新board_B2_cancel_016目录，在WAIT_PALM注入FIST，期望TRAY_RETURN且物品入托盘/最终HOME；异常保留日志、去许可停止，不自动CLEAR/START。

### 2026-10-06：B2 FIST 取消016会话失败记录与017复测准备

- 用户board_B2_cancel_016 stdout：PREFLIGHT PASS、DRY_RUN HOME/OFF→LINE/实时反馈成功、READY监听8765，随后60秒SESSION超时、exit1，无BOARD_RESULT。独立监视OFF→IDLE→OFF后180秒超时，未到WAIT_PALM、未注入FIST。没有开始任务路径，不能归因于FIST/托盘轨迹或计为取消成功。
- 本机pc_submit.stderr确认临时启动器在原socket.create_connection超时退出，stdout只有WAITING而无TCP_CONNECTED/COMMITTED；该启动器有600秒准备窗口，UART执行器仍运行且stderr空。不能仅凭板端READY推断PC客户端仍活着；异步人工上板不适合短暂准备窗口。
- 核对PID/命令行，仅停止scene016本轮执行器，冻结配置/descriptor/sim JSONL/双方stdout-stderr/临时启动器8份输入并计算SHA256至reports/phase3_coppelia_board_B2_cancel_016_failed_20261006。实际2872次场景观察均frame0、attached0、无action，最终HOME0rad；摘要docs/evidence/phase3_coppelia_B2_cancel_016_failed_20261006.json明确板端stdout来源与未取得PS原始文件。
- 快照后cleanup016、prepare_scene017均实际成功；017配置与016完整JSON相等。新临时PC启动器取消600秒准备截止，首次连接前持续重试OSError，连接后仍执行一次原HELLO/完整路径/STATUS，不自动重复任务或绕过协议。语法编译通过，实际017上板会话/FIST/TRAY_RETURN尚未运行；原PC/PS核心脚本、RTL/BIT/HWH/ABI/接线不变，仍是无物理机械臂的停止运动学/几何场景。
- 读取项目入口与FPGA skill，dev/filid跟踪文件初始干净，fetch/pull ff-only最新，保留全部既有未跟踪数据。仅选择失败证据/当前上下文/模式B说明/日志推送个人分支，不造版本包或工程备份、不复跑无关镜像测试，资源时序不新增。下一步保持COM16执行器READY和PC首次连接等待、PYNQ重载原BIT、新board_B2_cancel_017；先启动监视再启动board_loop，在WAIT_PALM一次FIST，验收TRAY_RETURN/tray_seen及实际入托盘和HOME。失败保留日志、去许可停止，不自动CLEAR/START。

### 2026-10-06：v0.1.2 B2 WAIT_PALM FIST 托盘归还实际闭环验收

- 用户board_B2_cancel_017经过只读门禁、S1配置、DRY_RUN HOME、OFF→LINE、实时反馈、网络会话和任务提交；用户监视OFF→IDLE→WAIT_PATH→RUN OUT→holding→WAIT_PALM后调用board_gesture.py FIST，打印S4Status(raw=19427973)。最终PASS/B_AI_PC/object2/TRAY_RETURN、held/tray_seen/moved=true、fault/refuse NONE，SELECTED/PATH_ACCEPTED/TASK_CANCELLED，exit0；TX1256/FB3107/反馈错误0/响应超时0。
- cancel_source原文VISION_FIST (inferred: no PS/PC/timeout cause recorded)保持其推断身份，不写成原始事件直接归因；用户FIST监视记录是另一来源，PS原始手势日志仍未拷回。板端原始文件未本机取回，摘要明确来自用户stdout/JSON。PS单机任务37.881847334秒、start到commit124.403489毫秒，不跨时钟域计算感知执行延迟。
- PC日志确认BENCH会话、task1的5段完整路径、COMMITTED及最终STATUS CANCELLED；双方stderr为空。完整场景3136次观察、frame1252，一次grasp物品2/frame338、一次release/frame1062，先抓后放且最终attached0。托盘落点误差0.059767345732776596mm（≤2mm），HOME最大误差0rad（≤0.00035rad），其他物品位移0；7项场景与4项PC判据全部PASS。
- 核对进程PID/命令行，仅停止本轮scene017执行器；PC提交程序已收到最终状态退出。冻结配置、descriptor、sim/PC JSONL、双方stdout/stderr和无准备截止的一次提交启动器9份输入至reports/phase3_coppelia_board_B2_cancel_017_20261006，写docs/evidence/phase3_coppelia_B2_cancel_017_20261006.json；9项字节数/SHA256和11项验收检查通过。保存后cleanup017/prepare_scene018实际成功，018配置与017完全JSON相等。
- 读取AI/上下文/FPGA skill，dev/filid跟踪文件初始干净，fetch/pull ff-only最新；保留既有未跟踪数据，仅证据/README/当前上下文/日志选择提交推送，不备份工程、不造新版本包、不复跑无关测试。核心PC/PS脚本、RTL/BIT/HWH/ABI/接线/模型不变，资源时序不新增。原600秒启动器失败轮016证据保留；017持续等待首次TCP的临时启动器实际连接与完整协议已验证。
- 当前模式A三物品正常、B2正常与B2持物FIST托盘归还实际FPGA/UART/Coppelia闭环已通过。下一步场景018/新board_B1_018、原BIT和v0.1.2、COM16/原3.3V TTL接线及D5，先正常B1 PALM再正常B3；仍只注入类别、停止状态运动学/几何抓取。真实七类/RGB-D/物理机器人/接触动力学/持续50Hz/端到端同步延迟/S8完整配对原始日志指标待验收。

### 2026-10-06：v0.1.2 B1 正常完整网络提交与实际交付验收

- 用户board_B1_018完成门禁、初始化、实时反馈、网络会话及物品1提交；监视OFF→IDLE→WAIT_PATH→RUN OUT→holding→WAIT_PALM，PALM返回S4Status。最终PASS/B_AI_PC/object1/DONE、exit0、fault/refuse NONE，SELECTED/PATH_ACCEPTED/TASK_DONE；TX988/FB2676/反馈错误0/响应超时0。原PS/BOARD_RESULT文件未本机拷回，摘要明确来自用户stdout/JSON，不重构成原始S8日志。
- Windows实际PC BENCH会话、task1完整5段路径、COMMITTED及最终STATUS DONE全部通过，双方stderr为空。场景2716次观察、frame984，一次grasp物品1/frame338、一次release/frame790，先抓后放、最终attached0。落点误差0.08748110729619mm（≤2mm）、HOME0rad（≤0.00035rad）、物品2/3位移0，7项场景及4项PC判据PASS。
- 核对PID/命令行，仅停止本轮scene018串口执行器，PC提交程序已DONE退出。冻结配置/descriptor/sim与PC JSONL/双方stdout-stderr/临时等待启动器9份输入到reports/phase3_coppelia_board_B1_018_20261006，新增docs/evidence/phase3_coppelia_B1_018_20261006.json；来源字节数/SHA256及11项判据校验PASS。归档后cleanup018、prepare_scene019实际成功，019配置与018完全JSON相等，准备B3一次完整提交/正常交付。
- 读取AI/上下文/FPGA skill，dev/filid跟踪文件初始干净，fetch/pull ff-only最新，保留既有未跟踪资料。仅验收JSON/README/上下文/日志选择提交推送，不造工程备份、版本包或镜像测试；核心PS/PC脚本、RTL/BIT/HWH/ABI/接线/权重不变，资源时序不新增。
- 模式A三物品正常、B1/B2正常、B2持物FIST托盘归还通过。下一步board_scene_019/COM16及192.168.2.99:8765首次连接持续等待；PYNQ重载原BIT、D5许可、新board_B3_019、object3，在WAIT_PALM注入PALM，检查DONE及场景末态。B3、真实七类/RGB-D/物理机器人/动力学/持续50Hz/同步端到端延迟及S8配对原始日志指标待验收；模拟手势、运动学几何抓取与物理执行明确区分。

### 2026-10-06：v0.1.2 B3 通过及七例 FPGA/Coppelia 执行闭环验收收尾

- 用户board_B3_019完成门禁/初始化/实时反馈/网络会话与object3提交，PALM监视到WAIT_PALM/holding并返回S4Status(raw=20476549)。最终PASS/B_AI_PC/object3/DONE、exit0、fault/refuse NONE，SELECTED/PATH_ACCEPTED/TASK_DONE；TX956/FB2541/反馈错误0/响应超时0。摘要来源用户stdout/BOARD_RESULT，原始PS文件仍待取回。
- PC实际BENCH会话、task1完整5段路径、COMMITTED和最终STATUS DONE，双方stderr空。场景2562次观察、frame952；一次grasp物品3/frame338、一次release/frame758，最终attached0、交付误差0.06715360964112974mm、HOME0rad、其他物品位移0，7项场景及4项PC判据PASS。仅停止本轮确认PID/命令行的scene019执行器，PC终态自行退出。
- 冻结本轮9份配置/descriptor/PC与sim日志/双方stdout-stderr/临时等待启动器到reports/phase3_coppelia_board_B3_019_20261006；新增docs/evidence/phase3_coppelia_B3_019_20261006.json。汇总原A1_005/A2_010/A3_011/B1_018/B2_015及B2_cancel_017，共6正常+1持物取消，65项判据、42份本机来源快照的字节数/SHA256及原BIT/HWH配对均核验PASS。历史A摘要缺mode/exit字段时按已记录A命令规范化，缺失退出码保持NOT_PROVIDED，不改原逐例证据。
- 新增docs/PHASE3_COPPELIA_BOARD_ACCEPTANCE_v0.1.2_CN.md及docs/evidence/phase3_coppelia_board_acceptance_summary_v0.1.2_20261006.json。正常落点最大0.1029954mm、托盘0.0597673mm，各例HOME0rad/其他物品位移0/反馈错误与响应超时0。列举收敛验收案例，不排除早期失败/重复轮次后宣称成功率100%；016会话失败与SIGBUS热修复历史保留。PS单机任务时长不当作同步端到端延迟，板端TX与场景命令帧分别记录。
- 归档后实际cleanup019成功，恢复初始姿态、移除临时桥接对象与live descriptor；专用Python执行器/PC等待程序均已退出，用户Coppelia应用保持打开。不再自动准备新轮次。板端由用户去D5许可，保留板包/日志；下一步先拷回七轮原ps_events/BOARD_RESULT/PREFLIGHT，配对本机PC/sim原始日志重算S8，不从派生JSON伪造日志，再安排实际故障注入/重复运行、七类真实视觉与实物验证。
- 读取项目规则及FPGA skill，dev/filid跟踪文件初始干净，fetch/pull ff-only最新，保留既有未跟踪文件。本轮只证据/报告/README/上下文/日志选择提交推送，无核心源码/RTL/BIT/HWH/ABI/接线/模型变更，不造工程备份/新版本包/镜像测试，无新资源时序结果。此次完成的是注入手势、实际PL及UART、停止运动学/几何Coppelia执行反馈阶段；真实七类/RGB-D/物理机器人/动力学/持续50Hz/同步延迟/S8配对原始日志指标未验收。

### 2026-10-06：七轮原始PYNQ日志回收、配对与原S8指标复核

- 用户提供C:/redacted_user/Downloads/phase3_board_evidence_20261006.tar.gz，4063字节，SHA256 f6a855816f1572a8a0510ef172af89209f31958effb7a2b13ceacfb03fe69242。只读检查28成员（7目录+21普通JSON/JSONL），限定runs/七个预期目录及三类文件，拒绝穿越/链接，逐字节保存到reports/phase3_coppelia_s8_board_logs_20261006。原上传文件不改，ARCHIVE_MANIFEST记录21项来源大小/哈希。
- 七轮BOARD_PREFLIGHT全PASS，BOARD_RESULT的模式/对象/结果/计数与前述验收记录相等；PS task_end的对象/模式/结果/holding/tray/cancel_source及三个任务时间戳与原RESULT逐项一致。七个独立PS clock_id、每轮task1，通过明确案例目录配对原本机PC快照（A无PC，B四轮PC），不靠跨主机墙钟或task_id全局合并。
- 原冻结S8 collect_run/compute_metrics/render_report实际均退出0，bundle 11日志/7轮，schema_problems0/data_kind SIMULATION，20份冻结依赖哈希通过。保留工具原REPORT/metrics/manifest不改，命令argv/配对信息在PAIRING_AUDIT；原metrics逐字节复制docs/evidence/phase3_coppelia_s8_metrics_v0.1.2_20261006.json。21项raw/4项输出哈希、7独立时钟及指标字节相等再次校验PASS。新增来源审计docs/evidence/phase3_coppelia_s8_raw_board_review_20261006.json，更新验收汇总为原PS已回收而不修改历史逐例缺文件记录。
- 原指标A DONE3、B DONE3/TRAY_RETURN1，无physical truth注释，物理成功/归还NOT_MEASURED；收敛案例包不是完整失败/重复总体，日志层3/3、3/3、1/1不作为100%整机成功率。A选择→提交0.533939～0.575286ms（n3）；B含取消105.708898～124.403489ms（n4）；B PS请求→路径收到42.176289～55.247095ms（n4）。同PS时钟日志差值不等于感知/PL硬实时延迟；总任务时长含人工PALM与仿真调度。
- PC缺target_request接收和pipeline事件，虽文件已配对，PC处理/纯network RTT/AI流水线仍NOT_MEASURED；未补造或从跨主机时间戳直接相减。P95/P99不足20/100样本，保持INSUFFICIENT_SAMPLES；七份单任务日志各longest_streak1，不能称连续7轮。板端墙钟2025-05-09/PC2026-10-06原样保留。无PL trace/到位时序/真实标签/新Vivado报告，不虚构实物、持续50Hz、PL内部或资源时序指标。
- 四轮B原PS在task_end后6.744/10.702/12.562/8.948ms出现IDLE状态PS_WRITE_BLOCKED，随后link_down；已完成DONE/TRAY_RETURN不变，无fault，但日志没有拒绝命令/地址，不能归因于某个写入。列入后续收尾控制权/连续运行验证；不筛掉事件。原取消原因仍为推断VISION_FIST，未取得显式FIST时刻。冻结renderer历史通用banner描述参考模型/合成RGBD/内存链路不适用于本轮全貌，原工具输出保留，新增主报告准确写真实FPGA/UART+Coppelia/注入手势范围。
- 新增docs/PHASE3_COPPELIA_S8_RAW_LOG_REVIEW_v0.1.2_CN.md并在Codex打开，CURRENT/README/验收总报告更新指向本轮原日志与指标。读取AI/上下文/FPGA skill，dev/filid初始跟踪干净，fetch/pull ff-only最新，保留既有未跟踪数据；仅选择文档/指标/来源审计提交推送，raw包/报告保留本机，不造工程备份/版本包或镜像测试。原源码/冻结工具/RTL/BIT/HWH/ABI/模型未改，无新板动作。下一步非冻结适配层补PC请求/STATUS/显式手势/拒绝命令诊断后重测，实际故障与连续运行、七类真实视觉与实物闭环继续独立验收。


## 2026-10-07 — NativeMotion RC v0.1.0：统一S2 / 内部原生接口 / 场景支撑面

范围经用户确认：仅最终版本上板，旧S1 cubic不兼容；新模型到来前冻结现有视觉，微调延后；当前仅Coppelia、未来RoArm-M3-S；16mm运动学抓取保留，资源5%～8%非门槛，不增加额外检测模块。个人分支dev/filid，Git基线4c7da78，开始fetch/pull后干净，原未跟踪资料全保留。修改前选定485份源/config/vector/docs备份backups/snapshot_20261007_before_native_motion.zip；中间统一S2源码native_motion_unified_source_v0.1.0_BOARD_NOT_RUN.zip无BIT且不要求上板。

新native_motion/独立继承本机S7；活动S1 trajectory退役，motion_sample_mux保留弹性缓冲、反压、最后后端接受目标、固定S2；旧0x43C20000仅零读/AXI事务排空。初始化、PS调试、S4/模式B均走S2。S4原生完整MOVE握手后单口LUTRAM完整写入再启动，POLL复用后端快照，pause/resume/clear/estop复用S2；旧内部AXI调度/不存在的切换等待退役。owner/排空fence/配置锁/PS隔离/快照和原故障处理保留，释放失败不清owner；SmartConnect管理与模式B路径提交保留。HAS_SO101=0，RoArm模板/反馈/许可最终门控保留，不声称官方协议或实物兼容。

新sim/phase3_native_closed_loop与旧版本隔离，ARM/S2/S4 ABI=0x3101/0x3202/0x3403、SOURCE复位1；repeat1..3同次初始化不同物品，auto-PALM明确可选测试注入。ARM.FB_SNAPSHOT是写操作，正常改到RELEASE/OFF后；故障持有owner时不发会被拒绝的PS收尾写。历史日志无拒绝地址，仅确认并修复代码的一个触发条件，收尾板测仍待验收。

Coppelia4.10/Windows现有RobotSim Python：底座网格下界z=0.0218391456604m取支撑面，16mm方块中心z=0.0298391456604m，底面齐平；原.ttt不覆盖。仿真可达HOME种子、位置IK/几何附着保留。11/11软件任务（A/B各3正常、A取消、B托盘、掌心超时、反馈丢失、锁定肩关节到位故障）PASS；一次离线2865不同实测姿态重放，正常/取消/掌心超时支撑面相交0，锁定关节故障注入189相交对；故障路径不推广实物。仍非动力学、板卡或真实感知成绩。

22/22现有RTL XSim任务回归PASS，复用位精确样本/golden并覆盖正常、PS隔离、取消、超时、limit/planner fault、恢复、tray；22/22现有Python单测PASS。日志native_motion/reports/native_xsim、native_motion/native_python_tests.log；场景原始runs/pc_native_all_001。

Vivado2026.1 / xc7z020clg400-1，100MHz system/motion、50MHz classifier，同视觉模型/约束/Performance_ExplorePostRoutePhysOpt；整机LUT20427 / FF14876 / BRAM tile60 / DSP28；WNS+0.138ns / WHS+0.021ns、TNS/THS0、DRC error0 / route error0 / CDC unsafe0、门禁PASS。原S7 LUT23283/FF17034/BRAM63/DSP42，净减LUT2856（旧已用12.266%，器件53200 LUT占用降5.368百分点）、FF2158、BRAM3、DSP14。83份视觉/模型/约束SHA256不变；Locator v16和七类随机classifier冻结，原活动四类、算法六类/v24结构实验未替换。BUILD_MANIFEST绑定源码/模型/约束和同次BIT/HWH。

最终本机deliverables/Gesture_Phase3_NativeMotion_RC_v0.1.0_20261007.zip含所需完整源、MEM/模型、约束、同次BIT/HWH、Windows/PYNQ依赖、场景、实现/仿真原始证据、README/SHA256SUMS与回退信息，不含Vivado/XSim缓存，大包不进Git。上板流程docs/PHASE3_NATIVE_MOTION_BOARD_GUIDE_v0.1.0_CN.md。新BIT的FPGA/UART、同次连续任务、收尾权限修复及实物均NOT_RUN，只最终BIT做A/B连续及B持物取消；断电接D1(U12)→USB-UART RX、D0(T14)←TX、GND、3.3V TTL，D5(T15)运行接3.3V许可、检查/停止/故障断开，无物理臂；回传PREFLIGHT/RESULT/PS/SIM/B-PC后验收。真实模型、RGB-D/AMD推理与M3-S官方协议/固件/标定另阶段。


## 2026-10-08 — NativeMotion RC v0.1.0 A/B同次连续三任务验收

用户回传board_native_A_001、board_native_B_003 stdout：每轮PREFLIGHT全11项通过，同次初始化task/object1→2→3全部DONE，fault/refuse NONE。A TX2940/FB6114、B TX2940/FB6291、fb_err/resp_timeouts0、valid/arrival mask0x3F、servo fault0；B三条SELECTED/PATH_ACCEPTED/TASK_DONE。当前按用户stdout提取保存，原板端PS/RESULT/PREFLIGHT文件、退出码和板端BIT哈希未取回。

只读取已有Windows执行日志：发布目录runs/board_native_scene_001(A)/002(B)，各连续1→2→3抓取释放一次，落点误差分别0.0212861/0.0346292/0.0394685mm，最终frame2936/attached0/HOME0rad。PC log实际在scene001/pc_events.jsonl，内容时间对应B003，BENCH会话和task1/2/3各五段提交；按内容配对。该日志未记录COMMITTED/终态STATUS且stdout未提供，由实际板端PATH_ACCEPTED/DONE确认接受/完成，不伪造PC事件。板端即时反馈快照略滞后于HOME，最终实测场景HOME0rad。

原Windows7份输入和用户JSON提取保存reports/native_motion_ab_repeat3_20261008，哈希/路径/字节数见docs/evidence/native_motion_ab_repeat3_acceptance_20261008.json；验收报告docs/PHASE3_NATIVE_MOTION_AB_REPEAT3_ACCEPTANCE_20261008_CN.md。A/B连续正常已通过，原20261007 ZIP/源/模型/约束/BIT/HWH不变，发布NOT_RUN保留历史。没有新增RTL、综合、软件测试或现场动作；资源时序仍原LUT20427/FF14876/BRAM tile60/DSP28、WNS/WHS+0.138/+0.021ns。纯验收文档更新，不做工程备份。

下一步只新版B持物FIST托盘归还（object2/repeat1/无auto-palm），重新准备scene/config及reload同一最终BIT，WAIT_PALM时FIST，期望TRAY_RETURN/tray_seen/托盘≤2mm/HOME/无附着/错误超时0。正常A/B不重跑。当前没有实物/真实视觉/RGB-D/接触动力学验证；原PS_WRITE_BLOCKED收尾完整事件审计、实际故障恢复仍未做，不从RESULT字段外推通过。结束/故障去D5许可，按原流程cleanup；保持用户现场状态，本轮不停止执行器或重载场景。


## 2026-10-08 — B持物FIST输出目录与直接运行流程重写

用户要求读取现状并给直接能用流程。读取当前包/配置/脚本/目录，近期取消尝试Windows日志（170854/172737/173957）均frame0无抓取释放，scene003 pc log只有头无SESSION，未把它们算托盘路径已测或失败。确认192.168.2.99 SSH在线；COM16沿用此前成功执行。保留所有旧目录/结果，不关闭现场程序、加载BIT或执行机械动作。

新增docs/PHASE3_NATIVE_B_FIST_RUNBOOK_20261008_CN.md：统一native_B_fist_20261008_01编号，Windows scene配置/descriptor、独立SIM和PC日志，PYNQ本次配置、板端board子目录、完整终端/退出码及FIST_INJECTION；不提前创建board子目录，root只对新输出根给xilinx上传权限。四终端明确角色，每个PC窗口使用完整路径，板端READY后60秒内建立PC会话。一次性文档脚本先等待WAIT_PALM/holding/object2/tray_ok/modeB/VISION_SIM，只发一次FIST；无PALM、无重复任务/自动清错，并保留注入前状态和板端时间证据。PC CANCELLED实际编码5明确写出；附退出、同名目录回收和失败/重试步骤。原流程第6节指向新流程，当前上下文更新。

本轮只整理文档与命令，嵌入Python语法核对通过，未访问MMIO/重跑测试/改RTL模型约束或板上脚本；不做工程备份，不重打包原发布物。B取消仍待实际执行，A/B正常连续成绩不变，资源时序沿用最终实现。以后新试验整套换编号02而非部分改变量或覆盖旧日志。


## 2026-10-08 — NativeMotion B持物FIST托盘归还通过，最终优化板测收尾

用户native_B_fist_20261008_01 stdout与回收原始PYNQ文件：PREFLIGHT PASS、B/object2/TRAY_RETURN、held/tray_seen/moved=true、fault/refuse NONE、exit0，SELECTED/PATH_ACCEPTED/TASK_CANCELLED；TX1152/FB2776、反馈错误/响应超时0、valid/arrival0x3F、servo fault0。PC原始终端COMMITTED后STATUS状态码5/CANCELLED，BENCH会话和task1五段路径提交完整。

FIST_INJECTION原始文件记录一次PS_TEST FIST，WAIT_PALM/object2/holding/tray_ok/modeB，t_ns=12930426668893，在task_start12916727030766和task_end12945121102182之间。BOARD_RESULT与PS task_end的原cancel_source仍为VISION_FIST推断标签，和显式PS注入证明分开记录，不声称真实摄像头推理。本次PS日志从启动到link_down未记录PS_WRITE_BLOCKED，范围限于捕获内容，不推广历史全量事件或故障恢复。板端墙钟2025-05-09、PC/SIM2026-10-08原样保留，不跨时钟计算延迟。

对应Coppelia2805条观察，唯一物品2抓取frame422、托盘释放frame894；最终frame1148/attached0、托盘误差0.024716167010189253mm、HOME最大关节误差0rad，其他物品位移0。13份原始输入逐字节归档reports/native_motion_B_fist_01_20261008，保存来源/字节数/SHA256；新增docs/evidence/native_motion_B_fist_acceptance_20261008.json、docs/PHASE3_NATIVE_MOTION_FINAL_BOARD_ACCEPTANCE_20261008_CN.md，更新当前状态/计划/上板指南/直接流程。live descriptor不在回收目录，本轮未操作或确认现场cleanup。

原定最终A连续3、B连续3、B持物FIST托盘归还全部通过，本轮统一S2与接口/资源优化的FPGA/UART+Coppelia验收完成，无需重测。正常A/B仍采用此前用户stdout与配对场景来源，缺失原板文件不补造。原ZIP/BIT/HWH/源/模型/约束与20261007发布NOT_RUN记录不变；资源时序沿用LUT20427/FF14876/BRAM tile60/DSP28，WNS/WHS+0.138/+0.021ns。纯已有证据归档/文档，不新增测试、现场动作、综合、版本包或工程备份。

已读AI/当前上下文/FPGA技能，dev/filid跟踪文件开始干净、fetch远端无新提交；保留所有原有未跟踪资料，选择本次验收文档/JSON提交推送个人分支，不触碰main/队友分支。后续等兼容模型包，核对拓扑/I/O/类别/量化/布局再确认开发；真实模型/Windows AMD感知/RGB-D/实物RoArm-M3-S/接触动力学/故障恢复板测另行推进，跟手微调仍延后。尚未收尾时按原流程断开D5、停止执行器并清理当前会话，已重载场景不得用旧descriptor。

## 2026-10-14 RoARM-M3-S Mode A 0.2.0 源码、仿真与整机实现

已读仓库入口、AI/当前上下文、gesture-fpga-dev与通用FPGA开发流程，按需读历史依据；硬件图采用可编辑SVG/DrawIO。用户确认固定掌心直接递送、三槽手动补物、取消/超时有实体验证回收路径则回收否则HOLD，保留A/B且默认A，视觉全部防抖，禁止训练，仅最终BIT上板。到货实例的固件、软限位、21个姿态、手掌高度及停止距离由现场实测填写；模板null/false拒绝运动。

根工作区dev/filid及其三个仅本地的图纸提交和全部未跟踪资料保留。新开发区runs/mode_a_roarm_20261014/dev从远端237314e154c9dfdf3d34728b4c7ca0a91550a3db建立codex/mode-a-roarm-20261014；Rain独立detached工作树冻结0f350087af8db4e69c4cbab724ca2ed6313eaf05。用户后续明确授权新源码/配置/操作手册推送独立codex分支；新旧图纸/绘图脚本、完整板包和实测标定数据只本地，不上传，不合main/队友分支，不强推。开发前备份SHA256 bf082e66d60c007d9074af41f257f7e0f460c2b7801d453edca54da5401a85d3。

真实模型包1093条SHA和12样本384项独立NumPy整数核对PASS；权重不改、不训练。适配七阶段locator含G1(d2)/G2(d5)/残差WRAP32、VGA Gray8→128×96加上下16行、源坐标时间EMA、同一VGA源帧的1.36方形ROI/PIL精确32×32、Conv8/16/32与FC512→64→6；bg/one/two/three/fist/palm映射S4 0/1/2/3/5/4。源缓存75 tile/两拍读与所有权；紧凑classifier ROM、残差复用、量化/点积/几何/地址分拍，视觉/AXI/任务/执行单100MHz，PCLK异步FIFO。保留S2唯一控制权、配置锁、反压、LAST_DELIVERED和故障处理及B路径/FIFO；裁剪旧cubic窗口和SO101外部通路。

加入不同帧时间去抖与新任务中性重新触发，初始选物100/PALM200/FIST80/中性250ms，至少2个不同FID，帧间断/陈旧250ms；固定PALM窗口3帧静止。S4持物取消/超时/失掌回收或HOLD；松爪前后复查资格，开爪MOVE已提交不能追回已下发目标。实物RoARM T102六关节原生弧度、T105→1051 b/s/e/t/r/g、115200 8N1、40PIN TTL方向及供电从官方手册/原理图核对；D5为本地许可，不能取消MCU已收到的目标。PS只初始化、示教/编表、只读日志；不代替PL实时手势/轨迹决策。失败重编表阻断旧实例；替代掌心可用without-tray验收HOLD，仍要求全部实测门槛。

实际验证：12样本locator全部7阶段/1280输出2356248周期（23.56248ms@100MHz），classifier全部层/logits/argmax/margin750170周期（7.50170ms）；16例PIL ROI最大2881316周期/28.81316ms（side479），两幅VGA全部307200字节、4096定位字、AXI快照反压/所有权、12几何/46EMA、滤波及五类完整DVP集成PASS。159次SCCB写入/636字节在100kHz逐字节对照，ACK/NACK三次重试/XCLK丢失/复位PASS；实体SCCB仍NOT_RUN。A定向安全测试使用FSM种子，完整DVP仿真绕过SCCB，均不替代实体整任务。22项原生RTL、23项后端Python、7项示教/协议/失败重编译/无回收门槛测试PASS。各原始失败与检查点保留，rc1/rc2源码包无BIT、BOARD_NOT_RUN。

v4/v6完整实现失败、v7/v8中止定位时序瓶颈；v9初次遗漏量化prep的失败日志归档后修复重跑。v9b完整时序通过但仅+0.043ns，并发现继承SCCB SDA缺同步，报告/BIT/HWH另存本地检查点不交付。补SDA两级ASYNC_REG与外部输入例外、将差值/绝对值/比较拆三拍；v10在源更新时中止，避免构建读入顺序不明。v11在工程创建/综合之前冻结142输入，实际包门槛逐项SHA无差异。

最终v11 Vivado2026.1、XC7Z020-1CLG400于13:52完整实现/输出PASS：LUT22440/53200、FF18062/106400、BRAM tile128.5/140（121 RAMB36+15 RAMB18）、DSP24/220，WNS/WHS+0.309/+0.017ns，TNS/THS0、内部未约束端点0、40160可路由net全部完成、DRC Error0。CDC12+12+4全Safe，Unsafe/Unknown/No ASYNC_REG0；两向11位Gray指针skew0.968/1.311ns均低于10ns，独立只读DCP审查不修改BIT。31项DRC警告为SCL未使用输入与DSP流水建议；18项methodology提示逐项复核为DVP单边launch与慢控制输出。继承PCLK48MHz/fall2..8ns仍是暂定板级预算，需示波器复核，任何硬件改动须重做整机门槛。

最终BIT SHA256 65dcf99c6179ad6330616fbc9ed6ca305149626f1084a97a4aacf69cd1b956dd；同次HWH ad4e3d8cbdd9bcdc222d5cf0d538ee57af1f0f18dcd9aa39fda94af0af20e95c。完整实现/CDC审查在native_motion/reports/roarm_closed_loop_implemented，公开小摘要docs/evidence/mode_a_roarm_source_validation_20261014.json。scripts/package_roarm_mode_a.py核对源码已提交、冻结输入、测试/路由/CDC/skew门槛、同次BIT/HWH，并生成完整本地源码/模型/报告/图纸/README/清单/哈希包，拒绝覆盖旧包；包SHA写同目录sha256文件，源码提交写BUILD_MANIFEST，不用此日志造成自引用哈希。

800×600mm黑垫名义布置、摄像头250–350mm、独立盘/前臂支撑、正常/回收路线及电气、Windows只读查询/示教/PYNQ命令在docs/MODE_A_ROARM_RUNBOOK_CN.md；复现导入/生成/仿真/全实现在docs/MODE_A_ROARM_BUILD_CN.md，详细失败/修复记录在docs/MODE_A_ROARM_DEVELOPMENT_20261014_CN.md；三份本地SVG/DrawIO/PNG已渲染检查。名义坐标不是机器人运动坐标，S2关节空间插值不能保证直线TCP。未上板、不操作机械臂；真实相机/SCCB/UART、限位/停止距离/实体抓取和固定真人掌心均NOT_RUN。下一步只加载最终同次BIT，先相机无执行器/只读UART，再空载→方块→回收→替代掌心与取消故障分支，最后真人固定掌心；原NativeMotion完整回退保留。


## 2026-10-14 Mode A RoARM 0.2.1 camera-release repair

- Trigger: user 0.2.0 logs show live results, ready snapshot and valid-size VGA PGM, then intermittent 5s snapshot timeout. Separate system-wide Python/ls/tail EIO recovered enough to run ls after reboot; still USB powered. Storage/power cause and actual image quality remain unconfirmed.
- Old source 427f076 reproducibly starts retained frame 11 twice at 235ns because registered release and old valid are observed on the same edge. Controller now masks releasing buffers. Snapshot holds an in-flight release; two-bit deferred release delivers it on exit without rescheduling the held frame.
- Read-only existing camera state/format/drop counters exposed as VIS ABI3503/CAM1. Matching scripts required. Snapshot preserves failure-time evidence before finally clearing the request; default timeout stays 5s, no automatic reset/retry and no motion permission bypass.
- PASS: release miss/ROI error/ROI+CLASS next-frame/dual-buffer regression; adapter/read latency/backpressure; retained full VGA; all five real-model pipeline vectors plus snapshot all-byte equality and deferred exit; SCCB159 writes/636 bytes/ACK/NACK; Python camera5 and commissioning7; native RTL22. Unchanged arithmetic/golden evidence retained, no training/weight changes.
- Pre-fix source archive SHA256 9d28968cacbd537ffad6f7b3d60d84d70a3c7eb0bdd6eb3b3eddb098ee22631c. Local failed reproductions and old v11 reports preserved. Frozen142 build inputs captured before v12 project creation at 2026-10-14T21:46:25+08:00; v12 full implementation completed22:03 with LUT22524/FF18132/BRAM128.5/DSP24, WNS/WHS+0.120/+0.020ns,40322 routed nets,DRC Error0,CDC28 Safe,Gray skew1.078/0.998ns below10ns. Source fingerprints unchanged; no intermediate BIT used on board.
- New revision board/live AI/arm/calibration/human delivery NOT_RUN. Diagrams and raw field data remain local. Root dev/filid and its three private commits remain untouched.

- Final v12 BIT SHA256: 66608046cfe965c4719f0f0369c55f2a3ccc9015f36ac71ca6b02caa5723b971; matched HWH: 263c64f5129ea46223753511644fd18821dad0ba09030cfd6f0137c295216c36. Local final package name RoarmModeA_v0_2_1_Final; source/config/manual published only to existing independent codex branch.

## 2026-10-15 Mode A v0.2.2 direct-FPGA board-test strategy

- User confirms original arm supply/base fixation and direct FPGA UART; Windows USB is not a prerequisite. Actual firmware, limits, poses and stopping distance remain field measurements. Latest pasted 0.2.1 log shows init_done and three 307200-byte snapshots; format_errors116→396 and result_events42→94 over32.803s reject continuity. No actual arm feedback or physical success evidence received.
- Added complete Chinese board-test strategy covering power/pins, isolated test03 deployment, read-only camera/UART gates, D5 electrical verification, physical power stop, original low-speed Web teaching with PL feedback capture, all21 poses, six empty routes, cube/tray/surrogate trials, real-vision A/abnormal exits, evidence and recovery.
- Added scripts/roarm_board_tools.py: rejects stale/frozen/error feedback and moving poses; measured pose imports retain session backups and do not set verification flags. Camera checker distinguishes owned drops, format errors, distinct frames and source age. Live box reader is read-only and refuses active motion; PALM-window output is a proposal, never automatic calibration. Offline evidence is explicitly supplied-log-only.
- Added empty-tray path to PS commissioning, forces every gripper target open and refuses mismatched closed HOME before hardware access. The former empty stage tested delivery only; both paths for all three objects must pass before declaring empty routes tested. No modified motion RTL, protocol, weights, constraints or BIT.
- PASS: board tools10, commissioning9, camera5 (24 software tests). Full package gate20 groups and142 frozen hardware inputs rechecked unchanged; prior22 native RTL regressions/full v12 implementation retained. Whole device LUT22524/FF18132/BRAM128.5/DSP24,100MHz,WNS/WHS+0.120/+0.020ns inherited from unchanged passing build; no new Vivado run required or claimed.
- Before-edit tracked source ZIP SHA2562669f8d14f8aeaebd3ca91d12291275f86a7d0d9ec0ebf0bf31c3b1cedce195b. Original0.2.1 package remains unchanged (ZIP SHA256aa5207246b980f723dd31e609c3e73a19452a5de02cfd30f4a47ea9e2806762d). New complete local package is RoarmModeA_v0_2_2_BoardTest_Final, same BIT/HWH hashes as above, manifests bind its committed software and frozen hardware. Diagrams, whole package and field calibration stay local; source/manual only to existing codex branch.
- Field work NOT_RUN: actual PL UART, D5/power-stop behavior, unit firmware/limits/21 poses, grasp/tray/surrogate/human delivery and live gesture quality. Next user test is D5-low10s UART plus60s camera continuity. Existing camera format errors and historical USB-powered system EIO are unresolved and must not be waived.

## 2026-10-15 v0.2.3 UART timeout diagnosis and MONITOR-counter correction

- User test03 logs match final hardware hashes. Clean precheckMODE0/STATUS0x20/ERROR0; 2sMONITOR has valid_mask/fb_seq/fb_ok/fb_err/ignored0, age1→1926ms, finalSTATUS0x51/ERROR0x800. Only feedback timeout confirmed; no evidence establishes wrong wiring, absent TX, or zero RX bytes. User reports oscilloscope unavailable.
- Found our v0.2.2 checker/documentation incorrectly required frames_tx growth in MONITOR. RTL counts only completed motion frames, excludes request frames. Valid synthetic MONITOR with advancing six-channel feedback and zero motion count reproduced old rejection. Corrected checker and pose-import dependency; nonzero motion-count delta now fails read-only monitoring. This software bug does not explain the user's actual absent feedback.
- Added bounded2s MONITOR diagnosis and D1-D0 isolated-loopback guide using existing BIT. No motion targets, ARM, firmware changes, timeout relaxation or automatic clear/retry. Hardware timeout after500ms stops future polls. Configuration register zero readback is not evidence of failed writes (most are write-only). Loopback echoes T105 and should increment lines_ignored, not fb_ok; physical arm must be disconnected/powered off, and the loop removed under power-off before restoring UART.
- Added simulation-only generator/bench/runner replaying434 real PS configuration writes to unchanged native S1 RTL; D5 low and no sample stream. Three XSim scenarios PASS: native query bytes/no reply timeout, query-only pin loopback with ignored lines, native T1051 six-channel acceptance; frames_tx stays0 in all. TB divisor/watchdog/poll clocks accelerated explicitly; no new BIT or physical success claimed.
- Python31 checks PASS (tools11/diagnosis6/commission9/camera5). Refactor first exposed an out-of-scope permit variable in regression; failure log retained as python_commission_refactor_failure.log, corrected via shared readonly_setup and rerun. Frozen142 hardware fingerprints remain unchanged, inheritedv12 resource/timing evidence retained.
- Before-edit source backup SHA2564318cbacbe6da50c1b13505e6f332f276e2d11b914f12c75f8e73faae799b46f; previous0.2.2 package preserved. New software full packageRoarmModeA_v0_2_3_UART_Final binds the same finalBIT/HWH and committed source. Raw user logs/whole package/diagrams/calibration local only; source/manual push existing codex branch. Next physical action is isolated PYNQ loopback, NOT_RUN here; actual arm communication remains failed/unresolved, no motion authorized by diagnostic result.

## 2026-10-17 Windows passive-header comparison tool v1.0.0

- User's pasted Python lost an open_port statement boundary and a string terminator; Read-Host prompt arguments were also mistaken for assignments. This invocation failed during Python compilation, before any serial open/write, and is not new hardware-failure evidence. Replace multiline terminal source pasting with saved scripts/roarm_uart_rx_compare.py and explicit CLI arguments.
- Existing local evidence: PYNQ pin loopback passed; CH340 and buffered Adapter(C) loops each returned five exact query echoes (50B). Same purchased arm on a teammate PC returned five complete T1051 lines, 319B/CRLF each, total1595B; raw/event consistency and byte-stream reference parsing five full masks pass. External UART retest still had zero received bytes. These are communication-only findings; no physical motion acceptance. Raw files and field joint values are not committed.
- Tool uses only onboard CP210x USB to send five literal T105 queries, CH340 receives only. COM syntax, distinct/available ports and VID roles checked before opening; check-only opens none. New output directories preserve all bytes/events/console/request/result; failures close both handles and retain partial capture. Guide documents physical10/9 RX/GND, disconnected external TX/VCC/Adapter, board USB and original12V power/init, verdict limits and recovery.
- PASS: eight hardware-free tests for copied malformed names, swapped/missing ports, no-open precheck, fragmented responses/raw integrity/USB-only writes, silent header diagnosis, second-port open cleanup, existing-output preservation and invalid numeric feedback rejection. CLI help and actual inventory check-only PASS for COM15=CH340,COM20=CP210x; no physical ports opened or queries sent by agent. Real dual-port capture NOT_RUN. No RTL/BIT/HWH/model/constraint change; unchanged v12 resource/timing reports retained, no new Vivado run. Existing v0.2.3 full board packages remain intact.
- Before-edit tracked-source ZIP SHA25609c2199798c89a7a62aed9a9b69210e5d5491c4ed7af50f21d6fa7a72bfb9e52. Sources/manual only on existing codex/mode-a-roarm-20261014; root private diagram commits and runtime/calibration files excluded. Next field test invokes the saved tool and compares onboard USB reference with passive external RX.

## 2026-10-18 Windows USB-only raw diagnostics v1.1.0

- User confirms the same ESP32 UART Type-C used in the teammate's successful test, all header/Adapter/FPGA/CH340/loopback wiring disconnected, original12V and main switch ON. Previous Windows121 open failure no longer occurs after USB isolation; old usb-query opens but discards raw/nonmatching feedback and reports no complete six-channel packet.
- Extend existing saved tool with --usb-only, requiring only MCU CP210x. Five literal T105 queries at least1s apart, full raw/event accumulation, automatic new directories and finally-close retained; dual-port receive-only behavior preserved. No motion, torque, firmware, reset, baud or FPGA operations. New guide covers identical-cable/host comparison before driver or board conclusions.
- Actual physical single-port run on COM20 at2026-10-17 23:58: five10B query writes, RX5B(FB7B7B7B7B), LF0, valid six-channel T1051=0, no serial exception. This is incomplete/abnormal byte reception, not zero reception, successful feedback, proven echo, or proof of FPGA timing failure. Raw logs retained locally under RobotSim/logs, excluded from Git. Same unit's earlier teammate USB5/5 remains historical evidence, not current host acceptance. Real dual-port comparison/motion/human handoff NOT_RUN.
- PASS: eleven hardware-free tests (original eight plus USB-only precheck without CH340, fragment/raw integrity with only one opened device, and silence/five-query evidence); actual USB-only inventory check opens none. CP210x11.2.0.167 observed read-only; no driver installation or replacement performed. RTL/BIT/HWH/model/constraints unchanged, existing v12 timing/resource evidence inherited; no Vivado rerun.
- Before-edit tracked-source snapshot SHA256e734b234f566c3f7fba52e8240ef52456c763970dad2acc58bde92234b35548b. Old v1.0.0 tool and v0.2.3 board packages retained. Source/manual pushed only to independent codex branch; diagrams/raw field/calibration data local. Next minimal test: teammate's known-good cable on current host directUSB, then same unit/cable/power on teammate host if needed; establish USB reference before header comparison.

## 2026-10-18 Local onboard USB query acceptance

- User ran v1.1.0 --usb-only on COM20 at00:08:44: five T105 writes, five complete six-channel T1051 responses,1620B total, zero invalid/incomplete JSON, LF5, USB_FEEDBACK_PASS/error=null. Offline raw audit confirms five324B CRLF records, literal10B query writes, and exact RX-event/raw equality. Raw SHA256c231acc4d5d43c9eacd1d5a2d22ff2a55e51f253cfe29f7eb6ba81499cfcb143; local actual joint/TCP/feedback files excluded from Git. Host-observed complete-line delay about47ms each, five samples, not FPGA or motion-loop timing acceptance.
- Earlier USB_ONLY_QUERY_FAILED is an old PowerShell status block, not this new capture's verdict. Windows121 and five-byte failures remain historical facts; the exact changed condition causing recovery is unrecorded, so neither driver nor cable nor arm fault is declared proven. Current computer's USB reference is now established; no need to repeat previously passing isolated loops.
- Next field test: power off/unplug USB before wiring; CH340 RXD to arm40PIN physical10(P_RX/U0TX), GND to9, externalTX/VCC/Adapter/FPGA disconnected. Board MCU USB alone sends five T105; both receiver streams compared with existing tool after main12V/ON/init. Both passing validates exposed feedback only; external input and standalone ground/power remain separate.
- This turn only reviews existing physical logs, reads port inventory and rechecks official schematic. No new serial open/query, code/RTL/BIT/HWH/model/constraint change, Vivado or physical motion. Documentation-only update on independent codex branch; existing packages unchanged. External UART, real motion/limits/stopping distance and human delivery remain unaccepted.

## 2026-10-18 Dual-receiver acceptance and explicit TTL query tool v1.2.0

- User v1.1.0 dual capture at00:14 uses onboardCOM20 for five literal T105 writes, passive CH340COM21. Each receives1565B/five313B CRLF six-channel T1051, no invalid/incomplete JSON, BOTH_FEEDBACK_PASS/error=null. Offline audit confirms raw files byte-identical and each matches RX-event reassembly; common SHA2563de0c90ab616e9c080c639ce495378f08ad8b0dd1f5ff13de3f2bb42041453e8. Raw joint/TCP/feedback files local only. This validates exposed feedback under onboardUSB grounding/power, not external command input or standalone operation.
- Tool v1.2.0 adds explicit --ttl-only --header-port for five T105 writes through selected CH340 with onboard armUSB physically unplugged. Default dual mode still writes only onboardUSB; USB-only preserved. TTL mode logs HEADER_TX/header_rx.bin, reports queries_via_usb=0/queries_via_header=5 and TTL_FEEDBACK_PASS only for five full responses. Echoing T105 is not feedback. Missing/ambiguous modes rejected before opening; calling header-only capture without explicit TTL intent rejected. No motion/torque/reset/firmware/FPGA commands.
- Guide docs/ROARM_UART_TTL_QUERY_v1_2_0_CN.md specifies power-off wiring, AdapterP2 TX/RX/GND/3V3 pins4/2/6/9, AdapterP1 pins4/2/6 to arm40PIN8/10/9, unused5V disconnected, original12V/ON/init, unplugged onboardUSB, exact CLI, pass/failure/recovery. Pin namespaces distinguished; no measured3V3 claim. A software check-only cannot prove physical unplugging/wiring.
- PASS:16 hardware-free tests including original11, TTL selected-port/five-literal-writes/raw integrity, echo rejection, VID/no-open preflight, accidental/ambiguous transmission guards. Actual COM21 check-only PASS, no serial open. Actual new TTL transmit/arm motion NOT_RUN; user must rewire before executing. No RTL/BIT/HWH/model/constraint changes or Vivado run; unchanged final v12 resource/timing evidence retained.
- Before-edit tracked-source ZIP SHA25602ca96e572649f8a30b2bb3d33ac35ade1acc300ea4a15bf2688016757056bce. Old v1.0.0/v1.1.0 tools and v0.2.3 board packages retained. Source/tests/manual only on independent codex branch; field data/calibration/diagrams local. Next is standalone CH340→Adapter→arm query, then FPGA readonly MONITOR if it passes; do not repeat established isolated loops.

## 2026-10-18 Standalone TTL silent; plan loaded input-node observation

- User capture003502_499701: COM15 CH340, five literal10B T105 API writes, rawRX0B, TTL_FEEDBACK_NOT_ESTABLISHED/error=null. Raw/event/request audit agrees. User confirms onboardUSB unplugged, original12V/ON still normal boot behavior, Adapter P2-9 connected to TTL3V3 and P2-6 toGND; voltage/waveform unmeasured. Prior USB-powered passive headerRX pass cannot establish this changed harness/standalone return path unconditionally. No FPGA is in current failed path.
- Reference official schematic has external P_TX/U0RX with onboardCP2102 TX throughR47 1k. This motivates observing the actual loaded node, not asserting contention/drive failure or modifying RTL. New docs/ROARM_UART_INPUT_TAP_20261018_CN.md keeps arm connected and moves only CH340RX from feedback to a high-impedance branch at arm physical8; keeps physical10 isolated from tap, power-off wiring, no8/10 short, existing115200/fiveT105 capture. Dedicated offline criterion is50 exact echoed query bytes/LF5; generic no-T1051 status is expected for this observation. Even a byte match does not measure analog thresholds/edges or prove MCU acceptance.
- Offline checker command executed against current0B raw file: bytes0/LF0/exact_query_echo=False as expected. Actual tap observation NOT_RUN pending physical rewiring. No new serial open/query/motion or code/RTL/BIT/HWH/model/constraint changes; documentation only, no backup/new tests/Vivado/package required. Prior16 software tests and packages retained. Next evidence decides whether to inspect loaded external path versus actual board routing/input electrical conditions; raw/calibration data remain local.

## 2026-10-18 Loaded input tap zero decode; paired load isolation plan

- User loaded observation005635_833 has five correct10B T105 writes and raw0B/LF0/exact_query_echo=False, no API errors. User explicitly confirms RX moved fromP2-2 to a three-way node with Adapter output and armphysical8, while arm remains connected. This is no decoded bytes, not a measured absence of all electrical transitions. No FPGA in this path; no timing/firmware/drive root cause established.
- Updated existing tap manual: A power-off/remove only arm8 branch while keeping same output harness/RX observation and supplies/grounds. If exact50B returns, focus on target loading/node/pins/electrical conditions and keep arm8 disconnected pending measurement. If still bad, B power-off/move only RX observation to TTLTX/AdapterP2-4 input with arm8 still disconnected. Bgood/Abad narrows to buffer/power/OE/output harness; bothbad narrows to source/input/observation/ground. This is a controlled comparison with current failing harness, not a request to redo all prior isolated acceptance tests.
- TI126 OE-high pass-through/OE-low high-impedance rechecked in primary datasheet; reference driver has CP2102TX throughR47 1k toU0RX. These facts motivate checking actual voltage/load, not declaring contention or damage. User lacks measured voltage/waveform evidence; further diagnosis after these comparisons may require borrowed meter/analyzer. No5V/drive/baud/timeout changes prescribed.
- This turn audits existing user files and updates documentation/context only; no new serial opens/queries/motion, software/RTL/BIT/HWH/model/constraint changes, new tests, Vivado or package. A/B follow-up NOT_RUN, v1.2.0 and original16 software tests retained. Runtime/calibration data remain local.

## 2026-10-18 Latest B input observation passes; Adapter loop proposed

- User corrects latest condition to A fail/B pass. Local audit: A010459_469 has0B; earlier B010647_543 also0B, both retained as history. New B010850_981 has50B/LF5, exactly five literal T105 queries and identical RX-event reassembly, no API error. Thus latest buffered input-node observation passes; generic no-T1051 status is expected for this tap, not a failure of the echo criterion.
- With Bgood/A bad, inspect buffer power/OE/output and output extension/tap contacts. User proposes an Adapter loop; appropriate current-harness isolation: power off, fully disconnect arm/FPGA, TTLTX/RX/GND/3V3 toP2-4/2/6/9, remove B input RX branch, sole loop jumper P1-4(P_TX) toP1-2(P_RX). Restoring RX toP2-2 matters: leaving it onTX input would bypass buffer and falsely pass. Exact50B is loop criterion, not T1051.
- If loop passes, focus on output extension/branch/contact differences versus A; if not, separate buffer supply/OE/output and receive-return path before declaring damage. Historical20261017 Adapter loop50B retained; current repeat is diagnostic under new failing conditions. Current repeat NOT_RUN. No new serial open/query/motion, code/RTL/BIT/HWH/model/constraint change/tests/Vivado/package; documentation/evidence only, raw field data excluded from Git.

## 2026-10-18 Adapter local loop accepted; isolate extension harness

- User011721_909 Adapter local P1-4↔P1-2 loop:50B/LF5/five exact T105 echoes, raw matches RX events, five literal writes, no API error. SHA256ab138db008554306faadf96aa10e314e096b13d4ace8403bb83bf191df06bdf8. Generic no-T1051 status is expected, echo check passes. Combined with latestB50B andA0B, prioritize output extension/return harness/end contacts and A observation wiring; no claim of real-load analog acceptance or defective arm.
- Next plan changes only jumper location: power off and fully isolate arm/FPGA, retain TTL-P2 four wires and RX onP2-2, remove all taps/local jumper, attach original arm8/10 wires toP1-4/2 and short only their detached far ends. Never short actual arm8/10. Exact50B is extended-loop criterion. If failed, replace one harness leg at a time; if passed, restore the same pair plus reliable arm ground and perform normal five-T1051 query. Persisting real-load failure requires voltage/waveform/board checks rather than software retuning.
- Only existing field files audited and docs/context updated; no serial open/query/motion, code/RTL/BIT/HWH/model/constraint change, tests/Vivado/new package. Extended harness loop and restored normal query NOT_RUN. v1.2.0/original16 tests/packages retained, raw field/calibration data local.

## 2026-10-18 Far-end original harness loop accepted

- User012400_786 far-end loop:five literal T105 writes, raw50B/LF5/exact query echo, identical RX-event reassembly, noAPI error. SHA256ab138db008554306faadf96aa10e314e096b13d4ace8403bb83bf191df06bdf8. Current adapter plus original signal pair works in this loop; real arm ground/input load and analog margin are not included. Earlier A0 remains a different observation, not proof of a defective cable after this result.
- Next normal restore: power off/unplug USB, remove every board/far-end loop and observation branch; RX onP2-2, tested pairP1-4/2 toarm8/10, reliable short groundP1-6 toarm9, TTL3V3/P2-9 andGND/P2-6 retained. Onboard armUSB disconnected, original12V/ON/init, then existingv1.2.0 --ttl-only COM15 in a new auto output directory. Criterion is five actual six-channelT1051/TTL_FEEDBACK_PASS, not50 echoed T105 bytes.
- If zero persists, move to physical ground/pin/input-voltage-waveform evidence; repeated established loops/software changes will not determine cause. Normal restored query NOT_RUN. This turn only reviews existing files/port inventory and records evidence; no new serial open/query/motion, code/hardware/model/constraint/tests/Vivado/package changes. Raw/calibration data local.

## 2026-10-18 Nominal normal-query invocation returns only request echoes

- User012842_689320 runs v1.2.0 --ttl-only COM15. Raw audit:50B/LF5, exactly five T105 requests, matches RX events, zeroT1051/error=null. Same data as far-end loop; not valid arm feedback. Actual physical removal of loops and reconnection ofarm8/10/9 is not established by CLI output, so an explicit wiring clarification is pending. No new physical port opened or query sent by agent.
- Avoid overclaiming origin: prioritize residual bypass/observation branch, but echo alone does not establish short circuit versus firmware/other source. Current M3 official JSON page has no echo/143 entry; UGV143 search results are not applied to M3. No echo-mode/configuration/motion commands sent. If actual restored wiring is confirmed, isolate feedback source by disconnecting return under power-off before further inference; that test NOT_RUN.
- Documentation/evidence only, no code/RTL/BIT/HWH/model/constraint/test/Vivado/package changes. Tightened prior context wording equating pure echo directly to a remaining loop. Existing passing loops retained, true externalTTL feedback remains unaccepted; raw field/calibration data local.

## 2026-10-18 External TTL actual arm feedback accepted, five queries

- User's adapter_loop_new_20261018_031930_563 uses v1.2.0 ttl_only on COM15 CH340 at115200/8N1: five literal10B T105 writes, queries_via_usb=0/queries_via_header=5. Raw1599B/LF5 contains five complete six-channel T1051 records, finite values, no invalid/incomplete JSON or API error; TTL_FEEDBACK_PASS. Offline audit confirms RX-event/raw equality, SHA25676beb8e3d96ecbc03d7c3a5579b04d6cec4b52722bc7dbb4f88a9894d4d7da58. This is real request/feedback communication, despite the loop-named folder, not a50B query echo. Raw joint/TCP data remain local.
- Host event delays are15ms to firstRX and47ms to complete line for each of five queries; not PL/motion latency or a long-run reliability statistic. All six torque-switch feedback fields are0. No motion/holding/limits/handoff acceptance, torque command or automatic home operation follows from this pass.
- User clarified012842_689320 echo was arm-off; powered013132_496249 remained0B. Before this pass, user reported only AdapterGND floating with3V3 connected and a remembered sub-ohm reading across isolated power rails, without exact bidirectional readings. Actual changes, successful supply/ground topology and physical removal of onboardUSB are pending clarification. Preserve the new communication pass without asserting electrical health or a proven earlier root cause.
- Prepared next stage: existing finalBIT, D5low, PL readonlyUART after successful wiring/power is recorded; do not attach a suspect supply network toPYNQ or repeat established loops/retuneFPGA. This turn only reads existing files and official references and updates docs/context. No new serial open/query, code/RTL/BIT/HWH/model/constraint/test/Vivado/package changes; prior16 software tests and releases retained. PL viaAdapter, real motion/calibration/stopping behavior, camera continuity and ModeA task remain unaccepted. Sources/manual only on independent codex branch; drawings and field/calibration data excluded.

## 2026-10-18 Adapter physical-wiring correction reported by user

- User reports the successful PC arrangement uses5V supply, Adapter P_RX/P_TX side toward TTL and A2/A4 toward arm. Retain the accepted five actual T1051 replies. Withdraw the previous assumed P2-host/P1-arm and prescribed3.3V physical table as current operating instructions; add a correction page and front notices in five affected field guides. Old records/packages remain historical, not a second active wiring recipe.
- Original user schematic instead labels SN74LVC1G126 supply/OE3V3 and A4→buffer→P_TX. Exact physical mapping, TX/RX crossings,5V supply origin/input point, grounds, old3V3 node, actual chipVCC/output level and physical onboardUSB removal are not yet recorded; do not silently replace the old table with a guessed reversed/5V one. Asked for the actual successful wire-by-wire arrangement. Direction and supply changed together, so no single-factor root cause is established.
- TI permits chipVCC1.65..5.5V, but at actual5V VIH=0.7VCC=3.5V and outputHIGH derives from that supply. External5V before a regulator would be a different circuit. PYNQ D0/D1 areLVCMOS33: do not transfer an unverified5V path or power node to them. PC query success does not certify electrical compatibility. No claim of proven board damage from remembered low resistance, or healthy rails from communication alone.
- Documentation correction only: no serial open/query/motion, code/RTL/BIT/HWH/model/constraint/software-version change, new tests/Vivado or package overwrite. Prior16 hardware-free checks retained; PL viaAdapter and physical motion remain unaccepted. New source/manual work stays on independent codex branch; diagrams/raw field/calibration data remain local.


2026-10-22曝光标定v0.2.0：实测源码e58b433，20XSim+完整实现/IOB/CDC通过；984行/5x作为静态调试档，10张原始小图/4147实时样本/format0->0/maxage191ms，75.156秒末尾选定档通过。冻结参考7张张掌仍全部background，画面改善但识别未恢复，完整A未测。正常恢复传感器原值/PS/CPU并关闭调试服务。原ROM未改、下次需重放配置，原VGA路线继续暂停。证据位于主目录board_evidence/mode_a_phase2_exposure_20261022_v0_2_0/，原4a82b6d Phase2分支保留；本次独立曝光分支，不自动合并主目录历史源码，不推送。


## 2026-10-24 black-scene vision v2 hardware source checkpoint

Imported only the frozen model candidate at Rain e4c43d44199762516e62da31672021cc73176a4c. New classifier weights/descriptors, actual signed gate -11748, and VIS model tag E4C43D44. Phase2 frontend/exposure/XDC/robot control unchanged. CPU 26 sample/832 layer checks and portable package checks passed. RTL checks and full implementation in progress; hardware NOT_RUN. All local only, no push. See docs/MODE_A_BLACK_SCENE_V2_20261024_CN.md and main evidence directory.


## 2026-10-24 v2 full implementation and candidate complete

2026-10-24黑背景v2硬件v0.3.0离线完成：构建源码744e834，37XSim/26CPU逐层/完整实现/独立网表通过，21108LUT/17378FF/53BRAM/26DSP，WNS/WHS+.045/+.033ns；新MODEL E4C43D44/raw>=−11748。相机/曝光/XDC/运动不变，板测NOT_RUN。完整本地Candidate及最终结果见主目录board_evidence/mode_a_black_scene_v2_20261024_v0_3_0/REPORT_CN.md。不推送。以下是此前源码检查点记录。

## 2026-10-27 Mode A v0.4.0 offline candidate

独立工作树/分支codex/mode-a-closed-loop-20261027，基线fd397f9。开发前快照snapshot_20261027_022327_Before_ModeA_ClosedLoop_V3_20261027.zip（3328文件/42.29MB）；原dev/filid修改、未跟踪资料、队友分支和其他工作树未改。集成Rain 022267a939c892d73ae278ceddee1a3e856a8dee targeted600 v3的Locator/Classifier及5个换算系数，MODEL_ID 022267A9，gate -11748不变。Giao最新9504e60e844063c712b3345877139a7d30d561cc仅原红位置45段，黄/蓝为空，不冒充新三槽标定。

生产S4启用库存ABI3404：复位空，人工RESTOCK，选定后预留，交付保持空，成功取消归还恢复；B自动继续PRE，PALM_CONTINUITY保留。50Hz候选每3运动帧查询，PRIME/闲时/看门狗不变。只读实时终端显示模型/事件、S4状态、阶段、库存、拒绝/故障、六轴已发目标和反馈；启动失败回收自己进程，Ctrl+C不停止PL。新模型相机独立入口及文档完成。

实际验证：26整数样本/832逐层及oracle检查，2316模型校验；26ROI/46EMA事件；44次XSim（38视觉/单元/最终顶层/真实115200节拍+6 S4独立golden/库存/故障）；68项相机PC预检；13项终端PC检查。完整实现20991 LUT/17382 FF/53 BRAM/26 DSP，相较v2 LUT -117/FF +4，WNS/WHS +0.041/+0.024ns、TNS/THS0。CDC28端点均safe、独立网表/IOB/输入时序/共享存储/库存及查询FF通过；DVP 2..8ns仍为待实测预算。同次BIT/HWH/XSA内外SHA一致，源码字节绑定清单SHA daebb08c8e4b59776015809e4e4e2bde32b46fe8adc6e27224ef19fa7e812485。早期G1换算不符/缺MEM与目录/UART bench竞争的失败保留，修复后重跑才计入通过。

三槽名义完整姿态IK独立规划：红(530,250,15)、黄(650,250,15)、蓝(590,320,15)mm；OV5640镜头候选(410,160,450)mm、朝-Z、长边+X。原远B/PRE/H不可达，近处候选为(450,215,140)/(430,175,150)/(410,140,115)。20ms样本12228个/66路径段、共享41关键点50段栈18；最大定点样本速度7.125253deg/s、二阶差分17.485284deg/s2、竖直弦偏差0.332300mm。真实CoppeliaSim停止运动学92295采样碰撞0、12臂网格与附着载荷，恢复原关节/移除临时对象。不是动力学、人手/线缆/完整支架、自碰撞或跟随精度保证。

本机包：D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_ClosedLoop_v0.4.0_20261027_ReviewCandidate，含同次硬件、完整模型/源码/证据/场景/流程。新模型实板识别、持续实体50Hz、肩/肘/夹爪到位、新三槽空夹/抓放/取消/人手交付NOT_RUN。本轮无实体JTAG/串口/动作访问。既有D/P工具映射独立留出误差49–69mm，最新Giao并未补齐三槽映射，已询问有无后来通过的配对依据；离线交付继续，实物表及启动器待该依据。详见docs/mode_a_closed_loop_v0_4_0/REPORT_CN.md和CALIBRATION_NEXT_CN.md，不能将SIM_ONLY表装入原生后端。旧active/模型/硬件包与故障阈值保留。


## 2026-10-27 A-anchor residual native trial v0.5.0

用户更新范围：不等待示教映射，已有A作为残差参照，推导B/C仿真后交付操作者测试；半小时无人时段开发，不访问实物。保留v0.4.0封装及fdc86aa源码检查点，新增前git archive源码快照CRC通过。历史成功高位A Q=(540,205,137)关联实际六轴反馈，假设名义工具向下/yaw0，取前五轴常量关节残差delta=(-1.380204,22.023232,-24.167829,6.538918,76.578780)deg；最后一项包含工具朝向约定，非测得roll零偏，单点不能识别真实五轴零位。夹爪采用原生open1.587670115/hold指令2.6/HOME3.083301384，2.543340146仅历史反馈。

已完成：三槽正常/悬停/原槽抓放9条原生路径，45489个20ms S2定点样本、参考限位通过；共享40关键点52段栈17，所有正常段保留回撤标志但初始持物取消hold_policy保持。蓝高位100mm超腕参考限位，选80mm升降；共同内点(585,225,90)，BUFFER_B(450,215,100)，PRE(430,175,110)，H(410,140,115)，退爪(410,140,135)。最大样本速度7.125253deg/s、二阶差分17.485284deg/s2、升降弦偏差0.167468mm。Coppelia4.10在显式q_scene=q_native-delta及独立夹爪映射下，12臂网格、桌面/三木块/相机，9正向与采样回程279066采样碰撞0、FK误差<=6.14e-13mm、恢复原关节/清临时对象。此几何证据检验残差假设，非真实手掌/接触/线缆/完整支架/跟随保证。

Windows原生串口候选单项入口支持显式--run --port --object --trial hover/pick-return；hover在目标上方等待操作者观察后返回；HOME不符不发动作，20ms T102 spd11/acc1、每3帧T105，三次不同新反馈/.02rad前五轴/.04rad夹爪、3秒等待不放宽，500ms反馈超时和>40ms调度迟到停止，不突发补帧，不自动松爪/回程，带载异常保留目标夹持角。10项纯PC协议/四舍五入/版本绑定/到位/故障行为通过。早期全路径笛卡尔细分超容量已改为升降细分与侧向关节扫掠验证；首次测试将Q16夹持角与未量化float直接比较的断言失败保留，修正为逐位和发包验证，不改生产阈值。

硬件完全沿用v0.4.0同次BIT/HWH/XSA/Rain022267a9；20991LUT/17382FF/53BRAM/26DSP、WNS/WHS+.041/+.024ns为该原版证据，无新RTL/模型/固件/PID变更，不重跑已过模块。本轮未开实体JTAG/串口/机械臂网络，新实体试验全部NOT_RUN。交付新增原生CSV/S4候选/规划与模拟源码/完整base_v04；PC入口是运动单项调试，正式模式A实时决策仍由PL。候选非physical_validated；用户无需先补完整示教映射，可按手册先悬停后原槽抓放回传残差观察。详见docs/mode_a_residual_v0_5_0/README_CN.md。

v0.5.0封包完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_v0.5.0_20261027_ResidualTrial.zip，51194768B，SHA256 36296467852f1207850870945bf4fc06fdc6d961e0a6b5fb6cd7c2daee58038d；3102文件，全部SHA/ZIP CRC/成员SHA/原v0.4硬件绑定通过。交付包内10项PC检查和6组dry-run通过，从交付根目录独立复现PLAN/S4/CSV/SCENE四文件与开发产物逐字节SHA一致。新源码检查点89e7ec61已推送个人codex分支，原包/原分支/未跟踪证据保留。


## 2026-10-27 v0.5.1 native-unit correction and complete motion flow

用户指令：先不管肩轴问题，先完成完整流程。实际读了yellow_hover_02.jsonl：80行/19.056919s，反馈序号1→231，最大年龄125ms，只在HOME_OPEN失败；手爪平均0.802489deg/s，原始文件SHA256 6281b4fde3f40a6a17df37080bbbd2a6a90bb0b7d4a98c65dac3843a6b9b944e。原始物理日志保持原处，不上传；开发前git archive快照CRC通过。官方T102参数本次已查证：spd单位步/s、4096步/圈，acc单位100步/s2。v0.5.0脚本将11/1配给8deg/s规划是软件适配错误，本版改100/3并记录实际单位换算8.7890625deg/s/26.3671875deg/s2，覆盖8deg/s与约17.5deg/s2的采样上限，20ms输出不变。

按用户授权暂将肩轴精确到位作为观察项：默认observe掩码0x3D，.02rad作为日志告警、>.15rad明显异常仍停；其他四臂轴.02rad与夹爪.04rad/三不同反馈/3秒等待不变。第一段从三稳定新反馈重新生成有界S2，手爪允许部分张开，前五轴仍需在原HOME邻域。每个成功串口写入T102记录原生spd/acc/完整JSON，终端约200ms显示，异常保持命令也独立记录。

新增handover完整运动入口：抓取、抬升、转运、PRE等待操作者确认木块夹稳/掌心就位，Enter后交付、释放、退爪、HOME，成功标记所选槽EMPTY。等待仍持续查询与日志；Esc/Ctrl+C/120秒超时停止保持，不自动释放。人工就位明确OPERATOR_PALM_READY，非伪造CNN/FPGA事件；这是PC串口联调，正式模式A的PL决策不在本轮冒称已验收。

实际验证：20项PC协议/单位/新起点/到位掩码/故障和取消顺序检查通过；单位限速手爪+静态肩偏差0.029145rad的纯软件plant，三槽悬停/原槽抓放/交付共9路线全完成，不能当PID/接触/实体结果。新启动几何：32个HOME邻域角点加本次停止反馈33场景，真实停止Coppelia4.10、12臂网格/桌/物块/相机，33066采样碰撞0、FK差<=6.14e-13mm、恢复关节/删自建对象。原v0.5.0全路线279066几何证据与v0.4.0同次BIT/HWH/XSA/Rain022267A9原样保留，硬件未改，不重跑44模块回归；资源20991LUT/17382FF/53BRAM/26DSP、WNS/WHS+.041/+.024ns仍仅指该原硬件实现。

新版实体运动NOT_RUN，本轮无实体串口/JTAG/机械臂网络访问。保留一次回归断言过严的失败：恢复起点已部分张开，旧速率模型剩余误差0.971rad而原断言>1rad；修为>0.9rad且到位失败，未改生产容差。交付与操作手册见docs/mode_a_fullflow_v0_5_1/README_CN.md；新包隔离保存，原v0.5.0及yellow_hover_02不修改。

v0.5.1已封包并核验：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_v0.5.1_20261027_FullFlow.zip，51678059B/3114文件，SHA256 7003c0f643d1e21e6e58c3c7801ad1d4b0d1f33f7e8560dd7832bccd9ce52c50。20项包内PC检查、9组dry-run、9条包内限速软件流程、全部文件SHA/ZIP CRC与成员SHA/基础硬件绑定均通过。原yellow_hover_02 SHA复核不变，原v0.5.0包不改；控制器源码检查点10f5d46c。新实体流程仍NOT_RUN。


## 2026-10-27 v0.5.2 observe-all timed walkthrough

用户明确：先不设置到位门槛，速度再快一点，需要先完整走完，随后按现场位置微调。旧v0.5.1第二段INNER因肘误差0.028622rad>.02停止；本版新增专用run_mode_a_walkthrough.py，所有六轴位置误差只告警记录，不再作为阶段门禁。无三次精确到位、3秒到位超时、HOME邻域或肩轴.15rad误差拦截。按插补时序和固定短停留前进，GRASP/RELEASE .8s、普通完整点.35s、细分点间0s；保留串口/反馈丢失/无效数据/人工停止，PRE等待掌心人工Enter，非CNN事件。编程全程不访问实体串口/JTAG/机械臂网络。

从新反馈接首段；--resume-log可解析上次INNER中断，跳过已完成开爪，接当前实际姿态再继续。原始停止日志、旧包不改。20ms跨段最小发送周期，Windows调度延迟只拉长时序，不突发补帧或跳样本。普通规划12deg/s/24deg/s2，近手HANDOVER/RELEASE/HAND_CLEAR保留8/16；T102及异常保持统一160步/s、acc5(500步/s2)，等价14.0625deg/s、43.9453125deg/s2，非0最大档。目标D坐标在段结束显示，六轴目标/反馈/误差持续写JSONL；TRIAL_DONE只说明指令序列完成，physical_task_pass为null。

实际验证：重定时9路径31959样本，S2生成/原生参考限位通过，关键点不变，40KP/52段/栈17；最大样本速度10.666023deg/s、二阶差分24.042266deg/s2、升降弦偏差0.169367mm。红/黄/蓝纯插补87.94/88.18/94.14s，非实体耗时。13项PC语义/大误差仍走完/远HOME启动/续跑/新起点/时序拉长/失联与取消检查通过；9路线加1续跑共10合成流程，在持续肩/肘/夹爪误差下完成，非实际PID/抓取验收。真实停止Coppelia4.10全9路线193041采样、实际停止姿态续跑/完整重接两路线44064采样均碰撞0；恢复关节/清临时对象。几何仍属A单点残差假设，不是手掌接触/完整支架/线缆或实体跟随保证。

保留一次报告单位错误尝试：首报告将rad/s、rad/s2数值误标deg单位，a2已修正，轨迹原生参数及实际160/5未受影响。git archive开发前源码快照CRC通过。FPGA/Rain v3保持v0.4.0，资源/时序引用原20991LUT/17382FF/53BRAM/26DSP、WNS/WHS+.041/+.024ns，无新硬件构建/模块回归。新控制实物NOT_RUN。当前手册docs/mode_a_walkthrough_v0_5_2/README_CN.md；此PC走位模式不代表PL到位FSM已改写，也不伪称自主A实体闭环已验收。

v0.5.2最终封包完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_v0.5.2_20261027_Walkthrough.zip，51334637B/3117文件，SHA256 2deb81e7c931438759297b81cdf51fadbb1690fb6d687dc71e6e7f6bb2b4be84。13项包内PC检查、9组完整预演及1组INNER续跑预演、10条包内持续误差软件流程、全部SHA/ZIP CRC和成员SHA/基础硬件绑定通过。原始yellow_handover_01仅只读，保留SHA b63b9652f786e786bfcc5835a71076428955f03068cc259e064be463b5319711；控制器源码40a371a6。新版实体运动仍NOT_RUN。

## 2026-10-27 v0.6.0 new-camera delivery layout and three-color suite

用户给出OV5640=(19.5,19.5,33.3)cm、视域(0,0)～(31,31)cm，并确认沿用原桌面原点，轴心与三块保持，交付点平移；继续以完整走完为主，不设置位置到位门槛。本轮不再索取示教/实物全局映射。开发前确认个人codex分支、fetch和未跟踪资料，git archive快照CRC通过。已有v0.5.2黄块日志仅只读：推进至PRE，原120s掌心就位超时停止，无位置误差拦截；原始物理日志不上传。

相机用于手势识别，三块无需入其视域。保留基座(585,25)mm和三槽(530,250,15)/(650,250,15)/(590,320,15)，每色抓取升降前缀12个原生目标与v0.5.2逐项相同。按原A单锚点残差外推，新交付侧B=(360,200,110)、PRE=(270,175,130)、H=(240,155,125)、H_CLEAR=(240,155,145)，掌面参考Z100。原全竖直姿态在新视域的主要区域受限，增加径向向外倾角B15°、PRE/H/退爪30°，抓取保持竖直；H比旧版高10mm以容纳倾斜木块。不是把相机位移直接加关节角。路径、原生CSV、最新说明和图由实际S2数据生成。

v0.6.0运行保持observe_all/arrival_mask0，无各轴精度、三帧到位、到位等待或HOME邻域拦截，普通12deg/s/24deg/s2、近手8/16、T102160步/s与acc5、20ms保持。PRE人工Enter无120s截止，持续反馈查询；Ctrl+C/等待中Esc、串口/反馈丢失/无效数据仍停。新增同一串口三色完整执行、逐色JSONL和整轮结果；失败不继续后续颜色，TRIAL_DONE只是指令流程完成，physical_task_pass保持null。布局ID绑定，旧布局日志不直接续跑新交付段。开始空爪/三块放回，新目录不覆盖。

实际开发端验证：9条三槽悬停/原槽抓放/交付路线32628个20ms S2样本，41关键点/53段/栈17；最大采样速度10.666023deg/s、二阶差分24.042266deg/s2、升降/递送/退爪弦偏差0.197154mm；量化后目标模型位置差<=0.003667mm，非实体精度。红黄蓝纯插补92.40/92.64/98.60s，含固定停留约98.55/98.79/104.75s，另加启动姿态差异、调度和人工等待。18项PC检查、10个持续误差单项合成流程、连续三色/每色PALM等待超过150s流程通过。

Coppelia4.10实际停止运动学：精确S2与实际T102四位小数各32628采样、碰撞0；12个实际机械臂网格，30mm木块随工具旋转附着、新相机盒体(195,195,333)、修正方向后的800x600桌面边界及80x80x20mm掌面代理，原关节恢复误差0、临时对象清理。首次附着脚本错误查询world对象导致API失败，已保留失败记录，改用payload相对TCP位姿后通过；几何轨迹未受影响。几何依然基于单A残差假设，不证明真实手形、接触动力学、未建模支架/线缆或实际舵机跟随。

本轮未打开实体串口/JTAG/机械臂网络，实体三色和新相机实际CNN均NOT_RUN。Rain022267A9和v0.4.0同次BIT/HWH/XSA保留，不改模型/RTL、不重跑已过模块；20991LUT/17382FF/53BRAM/26DSP、WNS/WHS+.041/+.024ns仅引用原硬件实现。导出新S4候选数据，但旧BIT未包含它或PC的observe_all运行策略；用户三色实体确认后再集成板端与掌面像素窗口。本机完整包与图纸/绘图脚本不上传，源码、配置、手册和合成/仿真汇总推送个人分支。操作手册docs/mode_a_delivery_layout_v0_6_0/README_CN.md。

v0.6.0最终封包：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_v0.6.0_20261027_NewCamera_ThreeColor.zip，50468076B、3130文件（3129条SHA），SHA256 ca40a16f43612bb5319633602f9d35e765c4b2d3ef5572a5ffe7184e9ecf6145。18项包内PC检查、9个单色预演加1个三色预演、10个单项合成流程和1个连续三色流程通过；包内规划源码独立重生成PLAN_NATIVE与开发产物逐字节一致，SHA dfd1cc3ca9ee14b4e1a603586bcba1cbe080c294d4d5e20503d8f9ca15c6eee8。全部文件SHA、原v0.4硬件/XSA绑定、ZIP CRC与每个成员SHA通过。源代码检查点e6569c4；图与路径说明已视觉核对，自建隐藏Coppelia进程34660已核对路径后关闭，无实体访问。新版实物仍NOT_RUN，旧包和真实日志原地保留。

## 2026-10-27 v0.7.0 raised-delivery FPGA board package

用户确认夹取/放下成型，授权上板验证，要求不设到位门槛、略加速、等待/交付提高约50mm，不允许先到点再抬升，其余复用。只读现有v0.6.0日志：三色各有完整结束记录（共6个TRIAL_DONE），用户报告真实抓放成型；不把指令结束单独算作任务成功率。原始日志留本机不上传。开发前读取AI/上下文/FPGA skill、确认codex个人分支和改动、fetch，git archive源码快照CRC通过。当前PC/CH340或PYNQ控制端及PYNQ侧3.3V逻辑尚未获现场确认；已异步询问，继续独立完成开发/封包，不访问实体JTAG/串口/机械臂网络。

复用原桌面/基座/三块/OV5640位置和A残差假设，三色抓取升降前缀每色12个目标逐项保持。新B(360,200,160)、PRE(270,175,180)、H(240,155,175)、退爪(240,155,195)mm，掌面Z150；交付侧倾角B20°/PRE-H40°使整条高位路线可解，抓取仍竖直。INNER后转运途中上升，不先去旧PRE/H再加50mm。9路径28569个S2定点样本、41KP/53段/栈17；最大采样速度12.458265deg/s、二阶差分28.413587deg/s2、弦偏差.177082mm。红黄蓝纯插补81.58/81.82/86.66s，加352/800ms固定停留后约87.756/87.996/92.836s，另加PALM和启动差异。

新S4编译参数TIMED_WALKTHROUGH，默认0保留旧行为，板项目显式1并报告ABI3405；flags低位抓取/回撤保持，bits7:2为16ms固定停留单位，22=352ms、50=800ms，细分0。忽略所有位置到位比较，配置arrival_mask0，无精度/三帧到位/到位等待/实际HOME邻域门禁；内部LAST_DELIVERED一致性和命令有效性保留。PALM等待0为无限，计数饱和防回绕；真实PALM资格、窗口/连续性、FIST普通取消/持物HOLD、反馈通信及D5仍保留。普通14deg/s/28deg/s2，近手9/18，T102原生200步/s与acc6，对应17.578125deg/s和52.734375deg/s2。20ms输出、每3运动帧T105；初始/闲时100ms查询。

新增Windows原生JTAG整会话入口：复用已验证的PS/FCLK100MHz/CPU保存恢复路径、不改PLL/MIO/DDR；同次BIT/XSA及五ID核对、曝光984/gain80、一次载入后端/路径、MONITOR真实反馈、D5低等待现场许可、从新反馈由PL接HOME、随后真实1/2/3/PALM全自主任务。PC只初始化/观察及人工r/y/b补料、停止，不逐周期插补/转发，不注入假手势。终端含模型/事件、FPGA状态/阶段/库存/命令/反馈、PALM窗口、当前规划点/D坐标和完成计数。Ctrl+C信号先置停止请求，再释放S4控制权/后端OFF、恢复传感器/PS/CPU并关自己隐藏服务；失败不自动清错重试。首次PALM固定有效内容区x0..128/y16..112、稳定框3帧/边界移动3px，未称为Z150实测像素标定。

实际验证：10新PC检查和13终端回归通过；新FSM定向XSim从复位完整三色（实际arrival0/配置3f也推进）、352/800ms固定停留、PALM超过70k tick、库存空、反馈丢失、FIST保持、D5即时故障通过。4次全S4/S2集成：DRY_RUN和LINE动作/S2样本逐位golden、库存、COMM故障/计数/故障后输出截断、D5；去除到位等待使COMM截止前可能多发一MOVE，旧arrival相关时序oracle不再适用，该场景改检最终故障/计数/故障后样本不增，正常两场景仍精确golden。1次实际115200串口XSim：新200/6模板、9条T102、每3运动帧查询、324B T1051、50Hz无查询重叠/丢帧/解析错误。合计6次XSim。保留FIST测试激励未跨采样沿、mapper三返回值解包错误、旧COMM oracle及退出条件两次失败，均在测试端修复；生产RTL构建后未再改。

Coppelia4.10精确S2及T102四位小数各28569采样，12实际臂网格/旋转附着30mm块/新镜头/桌面/掌面顶面Z150代理，碰撞0；6个已完成PC真实反馈结束姿态到HOME另265采样碰撞0，原始姿态候选LOCAL不上传，结束恢复关节并清自建对象。几何仍是残差假设下的停止运动学，不是新实体精度/接触/线缆/支架验证。

新完整XC7Z020实现：21166 LUT、17448 FF、53 BRAM、26 DSP，100MHz WNS+.173/WHS+.005ns、TNS/THS0，28CDC全safe。独立路由网表检查10正沿IOB、8 RAMB36/共享32KiB、单原MMCM、无IDELAY/冗余前端、Gray双向10ns偏斜、库存3FF和查询相位2FF；同次BIT/HWH/XSA内部绑定、HWH TIMED_WALKTHROUGH1与70项冻结输入哈希通过。构建依既有流程复核模型2316文件、26整数样本/832项，Rain022267A9权重/视觉RTL不改，未重训或重跑38个未改CNN RTL回归。硬件hash及计数见board_evidence/mode_a_board_v070_a1/IMPLEMENTATION_SUMMARY.json。

新BIT/加速/高位实板闭环均NOT_RUN。Adapter历史5V供电与信号电平未等同确认，不自动将未知电平接PYNQ；现场流程明确D1/U12 TX、D0/T14 RX、共地、D5/T15 3.3V许可，Adapter到机械臂侧原已工作线束保持，无新增供电接法。仅最终板包供用户现场启动，说明docs/mode_a_board_v0_7_0/README_CN.md；旧包、原始实测数据、未跟踪资料均保留。完整包/图纸/绘图脚本不上传，源码/配置/手册及非原始数据汇总推送个人分支。

v0.7.0封包前收到现场答复：目前尚未连接，用户要求给包后自行测试；届时PYNQ→机械臂，3.3V问题已经验证可行。按用户报告接受连接可行性，不重复电平试验，不由开发端打开JTAG/发机械臂命令。README据此更新，前文待确认状态只作过程记录。

v0.7.0第一次封包依赖检查发现少带mode_a_terminal_readonly.tcl，包内13终端回归因此1项报缺文件；已补齐清单，未改硬件/路径/控制器。未完成目录保留为RaisedDelivery_incomplete_a1，最终目录重新生成，不将此失败尝试当成已交付。

v0.7.0最终封包完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.7.0_20261027_RaisedDelivery.zip，44322605B、2655文件（2654条SHA），SHA256 c67f5e3bf92afc3f14cfafdb2b199a706bdee30995236bd3e63006d5faee490f。包内10新PC检查+13终端回归通过，规划及ABI3405 S4表从包内源码独立重生成与开发产物逐字节一致；全部文件/70项构建输入/模型/路径/同次XSA内外绑定、ZIP CRC及每个成员SHA通过。控制/打包源码检查点44bc75f；新BIT hash5c8527ab0c9b01df2cce299ae71549d73e9cce3b2ecea3deb6215cfb1bbcdfe5，HWH d7a83b5c2fc8b2f52a37c129a2e5fba5bdf8bd449dae23817d89505c664bb944，XSA0aa04bafe317967f639af637372c4a7e559b7c9621350365246cdf6a4c199400。自建隐藏Coppelia进程28176核对可执行路径后关闭。按用户要求只交付，由用户接线/现场测试，本轮未开JTAG/实体串口或机械臂网络，新实板NOT_RUN；旧完整包、失败封包目录和真实日志保持。


## 2026-10-27 A闭环初稿尝试：完整上板包及历版规划上传归档

用户本轮明确要求将本版本交付包及此前规划文件先上传Git，标注“A闭环初稿尝试”；本次授权覆盖旧约定中这些完整包/图纸仅本机保存的范围。开始确认当前codex/mode-a-closed-loop-20261027个人分支、无已有受跟踪修改，fetch后与远端4417cae4一致；保护其他未跟踪资料。新增deliverables/mode_a_closed_loop_draft_20261027/：v0.7.0完整ZIP及v0.4.0/0.5.0/0.5.1/0.5.2/0.6.0/0.7.0规划快照，含历史原手册/输入、原生或SIM_ONLY关节表、S4表、仿真场景/路径/结果和已生成图纸，来源由MANIFEST逐文件记录，README区分最新候选与历史参数。新标签mode-a-closed-loop-draft-20261027，注释“A闭环初稿尝试”。

最新ZIP保持44322605字节、2655文件，SHA256 c67f5e3bf92afc3f14cfafdb2b199a706bdee30995236bd3e63006d5faee490f；实际复核ZIP CRC、全部2654成员SHA以及六版本每项规划文件与原包SHA一致。归档SHA256SUMS覆盖除自身外所有新增归档文件，专用gitattributes保持封存字节。仅归档/文档变更，源码、RTL、模型、路径和BIT/HWH/XSA均未改变，不重复原模块测试或Vivado构建；既有资源时序仍见v0.7.0实现证据，新实板NOT_RUN。原始现场日志、LOCAL姿态、失败封包和EDA缓存不加入本次提交。


## 2026-10-27 v0.7.1：启动模式切换修复与D5前后两步测试

用户询问是否已修正并要求拆分插D5前后的测试。本轮明确上一轮仅定位，现完成实际软件修复。只读用户board_04：MONITOR下有效反馈包1→13；D5状态0x2021→0x2029被正确识别；JTAG请求185向ARM MODE 0x43C30004写259，RTL拒绝MONITOR→LINE直接非OFF切换，产生SLVERR/External abort，尚未启动HOME。终端fb_seq/六轴零为未刷新快照，不据此判定通信无回包。原始日志/实际姿态留本机，不推送。

开发前读取AI/上下文/FPGA skill，确认codex个人分支和现有受跟踪修改，fetch与远端b5581595一致。按备份规则生成选定源码/配置/文档Git归档D:/FPGA_Projects/Gesture/backups/snapshot_20261027_193620_before_mode_a_v071_startup.zip，277条目，771156B，CRC PASS，SHA c1abefabe56ee03df4578b54ef687c670129c0504f345aa5bb704bd9c46cb743；不纳入可再生EDA/既有大交付归档。

启动改为MONITOR查询且D5低，确认3个更新序号/六轴有效反馈；停在STEP2_WAIT_D5_AND_ENTER，无人工等待截止。必须D5高后按Enter才启动，提前Enter不保留，Enter只确认启动不代替PALM。支持--monitor-only执行第一步后恢复退出。正式启动先写OFF并等待active_mode=OFF且空闲，再LINE未ARM查询/确认反馈，最后LINE|ARM并启动S2从新反馈接HOME；没有恢复位置到位门槛。Tcl遥测在无S4 owner时主动FB_SNAPSHOT，S4拥有控制权时不写ARM窗口，只读取PL原快照；显示backend/fb_packets/fb_mask/fb_valid/捕获来源/会话阶段。保留D5、有效反馈、故障及旧有序停止恢复策略。

验证：19项PC回归（状态化MODE/OFF确认，D5单独不启动，提前Enter不保留，monitor-only不启用LINE/S2/S4，通信异常、D5早高/撤销、OFF超时不运动，Tcl快照刷新遵守PL独占等）及13项终端回归通过。1次实际后端RTL XSim使用当前完整配置和115200：D5低查询/六轴快照序号更新且T102为0；复现原直接切换SLVERR/CONTROL错误；OFF确认后未ARM LINE预取再ARM通过；原九条T102200/6、50Hz、三次查询、324B反馈无重叠/丢帧/解析错误通过，RX=6。原先纯Fake未限制非OFF切换，已用状态化Fake与真实RTL覆盖该缺口。证据board_evidence/mode_a_startup_v071_xsim_a1/RESULT.json，生成物/缓存保留本机。

硬件/RTL/约束/Rain CNN/全部路径/速度/布局均未修改，复用v070同次BIT/HWH/XSA和实现/模型/Coppelia依据，不重新综合/实现/碰撞仿真。既有21166 LUT/17448 FF/53BRAM/26DSP、100MHz WNS+.173/WHS+.005ns属于被复用的原实现，不是新硬件测试。新版完整包从固定SHA的v070 ZIP逐项校验/复制，更新软件、Tcl、手册、清单及修复证据；不带原包现场runs。v071新实板/新流程为NOT_RUN，由用户使用PYNQ→机械臂原已确认3.3V接线测试。上一轮总线异常后先撤D5并完整重启PYNQ，新手册给出两步命令/提示/观察点/停止恢复和整目录日志回传。旧v070初稿归档/标签及各版原始数据保持，完整补丁包本机交付，修复源码/手册/非原始汇总推送当前个人分支。


v0.7.1封包完成：源码检查点d51f50f8，D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.7.1_20261027_TwoStepStartup.zip，44334267B、2660文件、SHA256 2a9ccad3b922a314fe546436f2957a3d75ec687243c5925053848bc6d4cb4efe。包内19项PC和13终端回归通过，全部2659条SHA/源码输入/70项原构建输入/模型/路径/XSA内外绑定与ZIP CRC/成员SHA通过；2394项硬件/模型/RTL/约束/规划文件与原封存v070逐项相同。没有复制现场runs或LOCAL姿态，新包首次启动会创建自己的runs目录。补丁整包本机交付，Git仅新增修复源码/手册和汇总，旧A闭环初稿标签/ZIP不变。开发端未开JTAG或实体串口，v071新实板NOT_RUN。


## 2026-10-27 v0.7.2：D5预接、连续LINE接收与自动启动

用户提供v071 STOPPED_ERROR并明确不再运行中插D5，要求先接好再运行。只读现场board_03底层日志：62个有效反馈/D5高，请求196写MODE0成功、状态0x49，198错误0；199写LINE3成功、200状态0x3049、201错误0x40=UART_FRAMING；尚未发HOME。上次有序关闭后端、原传感器、PS/CPU及服务恢复均CONFIRMED。0x40不是到位/速度错误；OFF关闭RX并丢弃帧，重开可能从回复中途开始。原始现场关节姿态/日志保留本机。

开发前读取项目入口/上下文/FPGA skill，确认codex/mode-a-closed-loop-20261027受跟踪区干净、fetch与远端ae300e55一致。修改前选定源码/配置/文档Git归档D:/FPGA_Projects/Gesture/backups/snapshot_20261027_200623_before_mode_a_v072_prewired.zip，277条目/777135B，CRC PASS，SHA caee58ffa38f5a7c2dbf8b3ff54093c11560ae209328ff5dd3027a1d0cf5fd2f。

新v072软件在下载前接受D5已高，启动检查后端OFF/未ARM/空闲、无S4 owner；D5低则退出提示下次运行前接好，不在会话中等待插线。配置后直接LINE3(ARM=0)查询，连续三份新有效反馈确认后自动开始，取消运行中D5插接及Enter确认。保持LINE模式不变，读新快照/准备S2参数后只将ARM从0置1，启动PL从当前反馈接HOME；后续真实手势1/2/3/PALM任务保持。--monitor-only同样D5预接，LINE/ARM0查询后正常退出。保留通信/D5及故障停止、不清除错误强行继续，终端和异常加入原始错误码/名称/状态；状态结果记录D5_PRECONNECTED_AUTO。

验证：21项PC回归及13终端回归通过，覆盖D5高启动、初始OFF/未ARM/空闲/无owner检查、D5低无写操作、查询ARM0、自动开始无需键盘、不重切MODE、中途撤许可/通信问题停止、UART_FRAMING名称保留不清错、PL独占时不写快照。真实115200后端RTL XSim首先在324B回包中途OFF/重开复现0x40；新场景D5在复位前已高，LINE/ARM0阻断已排队运动样本、六轴快照有效，回包中置ARM且全程RX不掉；九条T102200/6、50Hz、每3帧查询及324B反馈无重叠/丢帧/解析错误通过。实际两次XSim：a1前三项通过，但首运动激励立即发送而缺少真实S2首样本20ms间隔，严格无查询重叠检查失败；a2按planner_p2p_core既有首周期合同修正激励，保留全部严格断言通过(RX=5)。两尝试保留，未修改生产RTL来迁就测试。通过证据board_evidence/mode_a_prewired_v072_xsim_a2/RESULT.json。

RTL/约束/模型/路径/速度均不变，旧BIT/HWH/XSA和2394项原硬件/模型/规划输入继续复用，没有重新实现或碰撞仿真；既有21166 LUT/17448 FF/53BRAM/26DSP、100MHz WNS+.173/WHS+.005ns只是同一原实现。新整包从冻结v070 ZIP复制，不取现场runs，再更新启动软件/Tcl/手册/清单及证据。用户按新完整目录先接D5再执行--run，查询后自动接HOME；新实板NOT_RUN，开发端未开JTAG/实体串口。旧v070/v071整包、初稿标签及原始数据均保留，完整v072包本机交付，修复源码/手册/非原始汇总推送个人分支。


v0.7.2封包完成，源码检查点2c38ac2d：D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.7.2_20261027_D5Preconnected.zip，44338190B、2662文件，SHA256 be07540d149f533ec7865b23f3d16d36742242b2f9db611d402631d3c9df0c2c。包内21PC/13终端通过；2661条SHA、源码输入、原70项构建输入、模型、路径、同次XSA内外绑定及ZIP CRC/成员SHA通过；2394项冻结输入与v070相同。新包无现场runs/LOCAL资料，实际使用的启动Python/Tcl无旧接D5/Enter提示或D5低启动门禁。实际仿真两次/修正测试激励后一次通过，前次失败记录保留。新实板NOT_RUN，完整包本机交付，旧初稿标签保持b5581595不变。


## 2026-10-27 v0.8.0：连续FIST、PRE一次PALM盲交付与加速

用户要求读取最新实测，修复短FIST误取消、等待不明显、PALM后仍持物和速度慢，并解释FIST。现场board_03为v072，1768遥测，完成0；红块短FIST触发未持物回退，黄块12:38:59.057426 UTC进入PRE，12:39:00.464332递送，实际等待1.406906s。12:39:02.577712开始失掌/THREE，12:39:03.125608在HANDOVER_2新增事件0x500=BLIND+HALTED且holding1/released0，后续341份PALM未恢复；arm_errors0，planner128是暂停/清理痕迹。根因是旧失掌策略转永久持物取消而未到释放，不是本次开爪到位失败。原始姿态/日志仍本机，只提交FIELD_REVIEW_SUMMARY。

开发前读取入口/上下文/FPGA skill，分支codex/mode-a-closed-loop-20261027，fetch与远端a397201d一致，保护原未跟踪资料。选定源码Git归档备份snapshot_20261027_205508_before_mode_a_v080_interaction.zip，396条/997814B，CRC PASS，SHA256 0f32b1beb08a590ff2e15528da1426160e906314a55d55904b6b41e70698d87d。先询问途中失掌行为；用户最终明确PALM只作为停在PRE后的盲交付一次触发，之前/之后不判断。此前开发的失掌可恢复暂停方案已全部撤回，不把旧策略塞入最终包。

新HANDOVER_V2编译参数默认0保持旧行为，本包置1，S4 ABI3406。PL新FIST_HOLD124=1000、PRE_WAIT128=2000，既有PALM_HOLD02C=500，1ms tick；新260/264只读交互状态/连续计数。FIST任何无效或其他类别归零，1s才形成单次普通取消；未夹取沿栈回退/恢复槽位，已持物未释放HALT并保持夹紧，PALM不恢复，释放提交后忽略普通取消；D5/通信故障仍保留。PRE固定停留后至少再等2s再累计窗口有效PALM0.5s，无掌心等待超时。确认后编译策略跳过所有PALM连续性/失掌/释放再确认，盲交付全程。六轴误差observe_all/arrival_mask0，非位置门槛不擅自移除。D5预接自动查询/同LINE ARM/PL接HOME流程保持，终端增加FIST/PRE/PALM计时与BLIND_DELIVERY_PALM_NOT_REQUIRED等明确判断。

所有三色9路159段起止原生关节关键点及D系位置/姿态、布局/残差逐项保持v070提高后的几何。普通22deg/s/44deg/s2，纯夹爪HOME_OPEN/GRASP30/60，近手12/24，释放开爪20/40；T102 spd400步/s、acc12对应35.15625deg/s和105.46875deg/s2，覆盖计划，20ms50Hz。41KP/53表段/栈17，17286S2采样；最大速度26.4902057deg/s、二阶差分41.5275502deg/s2、弦偏差.177403mm。三色纯插补49.4/49.6/52s，加原固定停留55.576/55.776/58.176s，另加PRE2s/PALM至少.5s和人工/启动时间；HOME_OPEN9.04→4.30s、GRASP6.24→2.92s均计划值。

最终FSM a3六类断言、新完整集成a7四例(真实外部视觉输入，PRE后立即撤掌仍保持正常DRY_RUN/LINE动作和全部S2样本严格golden，库存/通信/D5)、实际115200 UART a1九条400/12@50Hz/三次查询/324B反馈/无重叠，以及默认旧ABI3405回归一次通过，选定7次最终通过运行。开发早期FSM a1/a2是被用户新规则替代的恢复暂停策略；完整集成a1/a2为旧激励/策略，a3/a4错误使用PS视觉注入被物理模式正确拒绝，a5/a6改用外部视觉后通过，最终a7再撤掌并核对新计时寄存器。保留全部失败尝试，不放宽生产物理视觉防护。继承COMM故障trace与位置等待耦合，定时策略仅排除其动作时刻oracle，保留最终fault/counter/故障后样本截断；正常链路仍精确比对。

自建隐藏Coppelia40956，4.10版本、原冻结roarm场景，12臂网格/旋转30mm附着块/桌面/相机/掌面代理Z150，精确S2和四位小数实际命令各17286采样0碰撞，恢复关节和清理自建对象；无接触动力学。另以现场最新停止姿态假设空夹爪接HOME227采样0碰撞，实际姿态只留LOCAL，仅提交无姿态汇总。新包仍实物NOT_RUN。初次启动未能Resolve repo场景，自己的空场景随后通过API显式加载封存v072场景，metadata记录SceneLoaded=true，未操作用户场景。

新完整Vivado2026.1实现并独立网表复核：21013LUT/17430FF/53BRAM/26DSP；100MHz WNS+.017ns/WHS+.052ns，TNS/THS0；DRC Error0、43条输入空载/流水/BUFG既有类型警告留报告。CDC28端点均safe/unsafe0/unknown0；CDC-6两组11bit Gray两级ASYNC_REG和10ns skew已定向审核，实际偏斜0.974/1.085ns，余量9.026/8.915ns；相机10输入IOB/正边沿/单MMCM/无IDELAY/32KiB8RAMB36及库存/查询相位网表检查通过。70项构建输入哈希不变，BIT/HWH/XSA内外一致，硬件SHA见IMPLEMENTATION_SUMMARY；Rain022267A9完整模型未改未训练，构建26整数样本832检查通过，CNN RTL沿用未改模块既有回归。新源ABI和新硬件需整包使用，旧BIT不能执行新策略。

本阶段先提交源检查点再封包：从固定SHA v072 ZIP只取冻结依赖，复制同次新硬件/新规划/新脚本/证据，禁止带现场runs和LOCAL；包内23PC/13终端、独立重规划逐字节、模型/源输入/XSA和CRC/每成员SHA按实际封包结果追加。完整包本机交付，源码/文档/非原始结果推当前个人分支，旧A闭环初稿大ZIP/标签不改。未打开JTAG/实体UART/机械臂网络，待用户自行上板；新三色夹取/盲交付实板NOT_RUN。


v0.8.0最终封包完成：源码检查点3580435d5fc1a073cba5bf9cbd9e9aaa931634cc，D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.8.0_20261027_BlindHandover.zip，44067946B、2703文件（2702条SHA），SHA256 d59164f96edbf4603e415c85fd14d43a0f6326f087b726d9fe3ec4689dcbd09c。包内23PC/13终端全部通过，包内新规划及ABI3406 S4表独立重生成与开发产物逐字节相同；完整成员/70项构建输入/2317项冻结模型目录文件（含原SHA清单，模型审计内容2316项）/新硬件/同次XSA内外绑定及ZIP CRC/每成员SHA通过。BIT 1df4891dadbb0a60e6efe31ea8a50def37b6693a7647ca21a2d29653feb3c81d，HWH 19ec5992987ed0fddc1fee993397e1c3dc3745a725e33890407c8b725f1b6585，XSA 23d339847688e06e0e52b00bc694238e83aef3343d95b05d45c7c5aad70378ed。自建隐藏Coppelia40956核对可执行路径与元数据后关闭。完整包无现场runs和LOCAL资料；最终PACKAGE_RESULT/VERIFIED_SUMMARY纳入个人分支，完整新ZIP本机交付。旧A闭环初稿标签仍b5581595/旧ZIP不变。开发端未开JTAG/实体UART/机械臂网络，新实板NOT_RUN，交由用户D5运行前接好后测试。


## 2026-10-27 v0.8.1：通过基线再提速1.5倍

用户报告v080测试通过，授权运动速度再乘1.5。只读最新v080 board_01：2852遥测，完成计数最大2，结束2026-10-27 14:16:30.813029 UTC，最后STOPPED_ERROR为PL fault D5_PERMISSION，原传感器和PS/CPU恢复CONFIRMED。将用户报告与日志实际字段分别记录，不把末尾撤许可状态等同整条任务未完成，也不推断三色成功率/每次实物成功。原始角度与日志留本机，提交不含姿态的BASELINE_FIELD_SUMMARY。

开发前重读项目入口/上下文/FPGA skill及gesture入口skill，当前codex/mode-a-closed-loop-20261027无原受跟踪改动，fetch与远端7e6b0464一致。选定源码备份snapshot_20261027_222257_before_mode_a_v081_speed15.zip，406条/1028018B，CRC PASS，SHA f99f7728c4689e1dcddb162b3ec82adce1d213fac20bfcc912edc5c75d776dd5。原未跟踪资料/旧包/初稿标签保留；不由开发端打开JTAG/实体串口或机械臂网络。

新v081独立profile/config/规划/bridge/runner/checker保留v080源行为作为回退。所有9路159段起止原生关节、D坐标/姿态、布局、限位和残差逐项相同，只按N=ceil(v080_N/1.5)、Na=max(1,N//4)重采样，连短段最低20点也缩为14点，采样仍20ms50Hz。速度普通33/夹爪45/近手18/释放30deg/s，加速度对应99/135/54/90deg/s2，匹配时间缩放需要加速度乘2.25；原生spd600步/s/acc27对应52.734375deg/s及237.3046875deg/s2。启动实际反馈接HOME也用同一缩放与新S2约束。固定352/800ms、PRE2s/PALM500ms/FIST1s、库存、仅PRE触发盲交付、D5预接自动查询和无精度门槛完全不变。

规划41KP/53表段/栈17，11595采样，最大速度39.6915953deg/s、二阶差分91.7977424deg/s2、量化末端误差.003667mm、弦偏差.176094mm。红黄蓝纯插补33.14/33.26/34.86s，加原固定停留39.316/39.436/41.036s，再加PRE/PALM/人工与启动；固定等待不缩，所以全周期不是严格2/3。

25项新PC和13终端通过，含每段相对v080时间量化及启动VMAX/AMAX匹配。新增实际S2 core XSim检查9路159段11595个六轴样本，N/Na/profile/VMAX/AMAX取生产配置、Q16按原独立参考逐项比对及端点精确；TB只将周期改512cycles加快仿真，物理20ms另由生产数据和真实115200后端验证。UART XSim九条精确T102600/27@50Hz、三次查询/324B反馈无重叠/解析错误，RX5。两次新增RTL运行通过，FSM/全S4逻辑未改，继承v080对应通过依据而不重跑全部模块。

自建隐藏Coppelia41912，封存v080场景4.10，12臂网格/旋转30mm块/桌面相机掌面代理；精确/四位小数各11595采样0碰撞，恢复关节并清自建对象，无接触动力学。第一次CLI误传文件而非candidate目录，在连接模拟器前即报缺文件，改传目录后两种通过；保留过程说明。初次绘图选到未装matplotlib的仿真/捆绑Python，改用既有Python312的matplotlib3.11.2生成五幅新图并目视检查，未安装依赖、未改几何。

RTL/模型/接口/约束均不变，全部70项构建输入与v080同次BIT/HWH/XSA、模型校验绑定一致，复用已验证硬件，不重复Vivado综合/实现。继承资源21013LUT/17430FF/53BRAM/26DSP、100MHz WNS/WHS+.017/+.052ns、28CDC safe均属v080硬件，不当作本次新构建数据。完整包从固定SHA的v080 ZIP复制，只更新软件/参数/轨迹/手册；继承证据归入evidence/v080，新速度S2/UART/Coppelia/汇总单列。先源码检查点后封包，包内25PC/13终端、独立重规划逐字节、全部冻结输入及ZIP CRC/成员SHA按最终结果追加。新速度实板NOT_RUN，用户D5运行前接好即可按新脚本试三色；无需接线变动或重复旧模块测试。


v0.8.1封包完成：源码检查点0f9ad9f8301c38246ec7b1a93ece0c0c54de4e8c，D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.8.1_20261027_Speed1p5.zip，44002580B、2741文件（2740条SHA），SHA256 8d2f39507732bb96a031bbc989e10203b7b9f5a49696dfc3566fc28f6d987f03。包内25PC/13终端全部通过，包内新规划及S4表独立重生成逐字节一致；2385项硬件/模型/RTL/约束/规划冻结文件、70项构建输入、BIT/HWH/XSA内外绑定和ZIP CRC/每成员SHA通过，硬件仍为原v080同次产物。H/VERIFIED_SUMMARY和PACKAGE_RESULT记录准确范围；新增2次RTL通过、Coppelia23190采样，继承测试单独放v080。自建模拟器41912按可执行身份核对后关闭，未开JTAG/实体串口/机械臂网络。新包无现场runs/LOCAL姿态，旧v080及初稿标签不改；新速度实物NOT_RUN，由用户按新入口测试。完整ZIP本机交付，修复源码/手册/非原始汇总推个人分支。


## 2026-10-28 v0.8.2：FIST原槽归还与PRE右移50mm

用户报告v081测试通过，要求FIST返回原位及缓冲位置右移5cm，其余保持。已查v081 board_01：三色依次done1/2/3，OPERATOR_SESSION_ENDED、error null，结束2026-10-27 14:57:11.889558 UTC（22:57本地），传感器/PS/CPU恢复CONFIRMED。第四次红块在B→PRE时持续FIST，遥测计时24/157/305/453/596/737/885ms，下一帧进入HALT并将计时归零，holding1/released0/cancel_pending1、arm_errors0/fault NONE，事件新增0x400=HALTED。旧CFG HOLD_POLICY为1导致持物取消停住。原始记录只读/角度仍本机，FIELD_REVIEW_SUMMARY不含实物姿态。

按仓库规则先问清两个含义，用户明确：归还原槽后回HOME；只移PRE到(320,175,180)mm。B=(360,200,160)、H=(240,155,175)、H_CLEAR=(240,155,195)及其余布局/三槽/相机保持。前一轮澄清时已确认个人分支干净并fetch与远端dadc1a03一致；修改前快照snapshot_20261027_230525_before_mode_a_cancel_shift_v082.zip，416条/1055638B、CRC PASS、SHA fdad40289acaee7226bd5a28c78e59765f564ad366675c411e63c69cf9a4062a。备份和原未跟踪资料留本机。

新v082独立profile/config/bridge/入口/检查器/规划，保留v081回退。CFG从000e8106清bit2为000e8102，A_TRAY_EXIT=0保持，S4表hold_policy=false。生产RTL已具备回退栈：普通FIST暂停当前段，回到该段起点，再倒序每段起点，在原槽反向GRASP开爪、抬升、HOME；完成后cancelled事件/计数且恢复库存，持物正常取消不再HALT。未持物同样回退；释放已提交后FIST仍忽略；D5/通信故障仍停止且不虚构恢复库存。终端新增CANCEL_BRAKING_BEFORE_RETURN/CANCEL_RETURN_TO_SLOT_THEN_HOME、RETURN_目标/栈深度、cancelled_counter及FPGA_TASK_CANCELLED_RETURNED，会话结果也记录cancelled_tasks；避免继续显示正向递送目标。

新layout_v082仅PRE x+50，抬高/掌面/末端方向保持。ShiftedPreModel保留B20°和PRE/H40°，从B到新PRE、再到固定H整段反解/直线细分，未到位后再移点。三色前14段（42段）原生起止/时间逐项不变，悬停与原槽抓放全部运动数据、H终点及释放/退爪/HOME原生目标和时间相同，笛卡尔注释仅一个2.8e-14mm浮点差异按1e-9mm检查。新43KP/55表段/栈19，9路165运动段11925采样，最大速度39.6915953deg/s/二阶差分91.7977424deg/s2，弦偏差.303766mm、量化末端.004118mm。速度仍33/45/18/30deg/s及99/135/54/90deg/s2，T102600/27、20ms50Hz；固定352/800ms、PRE2s/PALM0.5s/FIST1s、一次PALM后盲交付和误差只观察保持。新距离使三色纯插补35.34/35.46/37.06s，加原固定停留41.516/41.636/43.236s，另加PRE/掌心/人工启动，不把距离变化说成降速。

新增实际S4 FSM使用完整原生表、生产1000/2000/500计数（TB tick32cycles缩时）和mock运动link。独立scoreboard根据前向已发起点序列逐个检查反向MOVE目标顺序，开爪必须在各色原槽、最后HOME/库存恢复/取消计数正确；三色正常盲交付、三色PRE取消、三色递送中途部分段取消、未持物/夹取中取消、释放提交后忽略FIST，以及回退中D5/通信故障共七组断言通过。a1只生成初始fixture保留，a2 testbench km_home声明顺序编译失败，a3修复bench后全通过，生产RTL无改。另新profile起初未转出SPEED/ACC，引入失败发生在S2执行前，修复后通过。28项PC包括配置/新PRE方向/返回终端覆盖，13终端保留按包复验。

实际S2 RTL对正常9路165段11925个六轴采样及从FSM实际MOVE导出的12场景304段20132采样逐项比对通过，使用生产N/Na/VMAX/AMAX，TB只将周期缩512cycles。导出包含8个成功归还场景；mock PAUSE反馈为关节中点，5个停止前向前缀按原N保守重放以连续进入返回，所有实际反向目标与N/Na不改，不宣称复现真实制动动力学。自建隐藏Coppelia35328，4.10封存v081场景、12臂网格/旋转30mm块/桌面/相机/掌面代理；普通新路径精确和四位命令各11925、归还场景各20132，总64114采样0碰撞并恢复关节/清对象，无接触动力学。新图按新PRE生成并目视检查。

未修改生产RTL/CNN/约束/接口，70构建输入hash不变，复用v080同次BIT/HWH/XSA、v081已验证600/27真实115200命令/查询频率，不重复模型/模块RTL或Vivado实现；资源21013LUT/17430FF/53BRAM/26DSP、100MHz WNS/WHS+.017/+.052ns和28CDC safe属于复用旧硬件，不算新构建。新包基于固定SHA v081 ZIP，继承证据单列v081；新layout/规划/配置/归还bench与回放/手册/汇总整包，禁止带现场runs/LOCAL。源码检查点后再封包，最终包内28PC/13终端、重规划逐字节、冻结硬件/模型/构建输入、ZIP校验按结果追加。新实体归还与新PRE为NOT_RUN，不自动上板；开发端未开JTAG/实体串口/机械臂网络。


v0.8.2封包完成：源码检查点570d004ba1b5fa8a13ced46457fd4c5d8b50c037，D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.8.2_20261028_CancelReturn_PRE320.zip，45160843B、2798文件（2797条SHA），SHA256 682bf4468e6b3fc2f5332716640cc1a0d592ec68b60814e66368391d71b7a5e9。包内28PC/13终端均通过；独立重生成新规划/S4表与开发产物逐字节相同；2385项冻结硬件/模型/旧RTL/约束/规划、70构建输入、BIT/HWH/XSA内外绑定及ZIP CRC/逐成员SHA通过。新layout与cancel_replay单列绑定，继承证据归v081，新增3次RTL通过及Coppelia64114采样结果单列。自建隐藏Coppelia35328按PID与可执行文件核对后关闭，无JTAG/实体UART/机械臂网络访问。旧初稿标签仍b5581595，新PRE/新归还实物NOT_RUN，使用新入口、D5运行前接好后由用户实测；完整包本机交付，源码/手册/非原始证据推个人分支。fetch期间发现队友dev/Giao推进8a116771，仅更新远端引用，按本轮其余保持不合入。现场原始日志/LOCAL与所有旧包保留。


## 2026-10-28 v0.8.2最终板测结果及尾部选物拒绝复核（无开发）

用户报告测试通过，要求查尾部ONE/TWO/THREE不响应原因，并询问独立硬件优化/跟手分支是否能适配；明确本轮只回答或改上一轮测试结果，不继续开发。已按项目入口/FPGA skill只读审记录/分支；个人分支开始无受跟踪改动，保留现场文件，不打开JTAG/实体串口/机械臂网络。只更新测试结果文档/JSON/上下文，不建快照、不改代码/配置/模型/RTL/旧板包，不重跑仿真/实现。

最终v082 board_04本地01:07:57至01:14:12，2375遥测、OPERATOR_SESSION_ENDED/error null、done3/cancel4，黄/蓝/红在01:10:05.776、01:10:53.418、01:13:02.134完成，库存依次101/001/000。4次取消在01:08:16.978、01:08:24.156、01:09:19.449、01:12:09.053回IDLE，库存111/111/111/001；其中后两次持物归还，由用户报告实物通过。结束原传感器/PS/CPU及自建服务恢复正常。末段ONE/TWO/THREE分别22/93/47份模型与任务类别一致且有效确认采样，均IDLE/stock000/EMPTY_SLOT；末尾拒绝计数7，无S4 fault或arm_errors，反馈错误/超时0。此处拒绝是成功交付后空槽、未人工RESTOCK；摆回物块不会自动改库存，脚本同会话前台r/y/b→OPERATOR_RESTOCK→背景重使能后再1/2/3。原库存约定保留，不通过去掉空槽检查掩盖。前次D5低/ARM_FAULT/UART_FRAMING及重启后查询framing失败也保留，最终正常不能证明这些间歇故障根因消除。FIELD_BOARD04_RESULT不含实际姿态，原始日志原样留本机。

只读定位独立codex/fpga-hw-opt-20261026，当前与远端均88de55d2、工作树无受跟踪改动。v0.2.0报告63次XSim/完整实现19640LUT/17879FF/54BRAM/26DSP、WNS/WHS+.417/+.022ns，离线未上板。HandAlign为最多16像素区域查表/稳定候选/接受/PALM锁定组件，未入生产源列表/未接S4动作，不是已可运行的连续XY跟手。它用旧E4C43D44、S4 ABI3403/A_TRAY_EXIT1和每命令查询策略，而当前为022267A9/3406/库存/原槽归还/盲交付/ROARM_FEEDBACK_EVERY3，因此可在后续独立适配中移植优化核心，但不能直接替换现BIT；现43KP/55段表也需考虑多区域路径容量。下一轮才确认局部对齐范围/标定/路径及接入，必须保持本轮已过行为并同次重建/验证。本轮未合并或编写新功能。


## 2026-10-28 第一稿A模式闭环封存、第二版开发授权

用户要求先封存实物通过的v082为第一稿，并在README末尾原样附现场注释。注释按原文字标点保存，未将物块左下角/“底座左直延”擅自解释为运动中心/轴心，不改几何或模型。用户进一步确认第二版：有限区域对齐，交接H左右各20mm三位置，PALM后锁定盲交付，保持1.5倍速度/高度/原槽归还；测量注释仅记录，仍沿用已通过坐标。先封存及Git标签，再以新工作树整合优化分支，保护第一稿和既有实验分支。新增打包器从固定SHA原v082 ZIP复制，所有运行文件/模型/RTL/轨迹/硬件逐字节保持，仅更新第一稿标签、已过实测结果、README和完整SHA清单，原ZIP不改。备份见board_evidence/mode_a_first_draft_20261028/BACKUP.json；源码检查点后生成封包结果，不打开硬件。

第一稿正式封包完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_ClosedLoop_FirstDraft_20261028.zip，45109685B/2801文件，SHA256 2d8c2f11f1fa4450f4c6b5e64af005fb10246432e0d03c5a75803880cf37b5c2。所有运行文件逐字节复用v082，README原文注释已核对，封包CRC/成员SHA和旧入口check-only通过；旧v082 ZIP不改。标签mode-a-closed-loop-v1-20261028指向含封存结果的源码状态，第二版另建工作树。


## 2026-10-28 第二版v0.9.0源码检查点：硬件优化与三位置跟手

- 用户确认有限区域→PALM锁定→盲交付；H±20mm三位置，速度/高度/FIST原槽归还保持；测量备注仅记录。第一稿已独立封存并推送mode-a-closed-loop-v1-20261028，不覆盖。
- 从88de55d2选择性导入classifier累加BRAM、locator requant流水、locator/classifier帧重叠、双ROI与时间去抖；保留Rainv3(022267A9)、50Hz T102600/27/每3帧反馈和原取消语义。S4新ABI3407：三组47KP共用59段，bank RAM1536words，map提交/修订号/配置锁；局部对齐不累积回退栈，最大23。
- 三组反解和共享时长最终规划a3；正常3组与6场景真实FSM发出的对齐/取消目标，实际S2精确49330采样；Coppelia精确/原生命令舍入总98660采样0碰撞，停止运动学/旋转附着，不是接触动力学或实体结果。新FSM a11和AXI a2、旧归还a8、30PC/13终端和真实115200UART检查已跑/结果以最终VERIFIED_SUMMARY封包核对。
- 已保留开发失败：移植常数G1/G2误用实验旧模型由locator第5层检出，终止a1构建；修复为原Rainv3常数，新locator26样本逐层整数精确通过，1647640cycles。旧流水线TB在bbox_done读取已改为结果帧的debug端口造成元数据比较失败，更新TB采样位置，不改生产RTL来迁就旧测试。
- 新运行入口run_mode_a_v2.py，D5预接不需Enter；--monitor-only采集三组静止PALM框中心生成一次性手区域图，再--hand-map上板。PALM只PRE触发，锁定后盲交付，三槽交付后人工r/y/b补库。新实板NOT_RUN。整机a2实现/完整流水线还在运行，本条为源码检查点，最终资源与硬件哈希后补。


### v0.9.0最终离线实现与验证（2026-10-28，实体NOT_RUN）

- a2最终74输入不再变动，20657LUT/19077FF/55.5BRAM/26DSP；相对v080硬件+v082软件第一稿LUT净减356(1.69%)，FF+1647、BRAM+2.5、DSP不变。100MHz WNS+.232/WHS+.019ns，TNS/THS0，内部未约束端点0；28CDC safe、0unsafe/unknown，双向11-bit Gray ASYNC_REG/10ns skew余量8.987/8.762ns；同次BIT/HWH/XSA哈希绑定，DRC0错误/35警告(4规则类型)。
- 模型保留Rain022267A9不训练/不换权重；26样本832项Python整数审计与classifier/locator实际RTL逐层精确，全26 DVP-ROI-分类也逐阶段精确。locator1647640cycles vs2356248，减少30.07%；12帧连续流输出12(4拒绝/8分类)，发生7次loc/classify重叠，数值/帧ID/采集时间一一对应。
- 顶层原6帧仅221ms，确实不满足新PALM300ms，因此失败保留；新a97使用10真实VGA帧无缩短生产时窗，frame9 qualified/event有效、D5低UART idle通过。新S4 a11覆盖三色对应三bank、十次全有向换位、原槽开爪/HOME库存和两种途中FIST；AXI a2完整三bank/mask/revision/index/锁；旧归还a8与真115200/50Hz600-27三查询通过。
- S2三bank及FSM回放49330个六轴Q16样本精确，Coppelia精确/4小数命令共98660样本0碰撞，两个mock PAUSE前缀按原N保守重放；不是实体动力学证据。32PC/13终端通过，独立新包封包与包内重规划后再记录最终ZIP哈希。未操作实体连接。


### v0.9.0最终封包（2026-10-28）

完整包Gesture_ModeA_FPGA_v0.9.0_20261028_HandAlign3_Final，46197925B/2974文件，SHA256 `0b70598458457ab38f929c88fcf339b10ee8789848dd7db2f72f05234fca6745`；包内32PC/13终端、独立--check-only、19个bank导出逐字节重现、74输入/模型/同次BIT-HWH-XSA及ZIP逐成员SHA/CRC通过。固件与运行源码检查点096a24f7；封包脚本随后补齐原封包与当前Git nominal xacro的字节绑定。首个封包只在xacro来源哈希上出现差异（关节/采样/几何数据无差异），未完成目录已标INCOMPLETE，Final包复制实际仿真使用的nominal输入后重现通过。原第一稿ZIP、标签、README测量注释不改；完整新包与图纸仅本机，源码/手册/非原始摘要推独立codex分支，实体NOT_RUN。开发端Coppelia仅关闭本次owned PID并已还原场景，没有开启实体接口。


## 2026-10-28 v0.9.1画面Y三分区与桌面前后规划

- 用户明确上中下指相机画面分区，对应桌面Y±20mm，交付高度保持。PRE320/155,175,195/180，H240/135,155,175/175，H_CLEAR同Hxy/z195；物块、相机、B、HOME、各色前14段目标、抓取、1.5倍速度600/27、50Hz、PRE2s/PALM500ms、FIST1s原槽归还与库存保持。
- 现有PL用二维矩形LUT，硬件/模型/74构建输入完全一致；不改RTL、不重建，复用v090同次BIT/HWH/XSA/ABI3407/时序资源证据(20657LUT/19077FF/55.5BRAM/26DSP，WNS+.232/WHS+.019ns，28CDC safe)。新软件/规划/区域配置版本v0.9.1，第一稿与旧X版本封存不变。
- 新Y采样工具按三次前/中/后PALM的框中心Y中位数确定区域，支持相机纵向反向；图像X全宽0..127，拒绝旧左右映射。新入口D5预接，不需运行中插线/Enter，六轴误差只观察。三组47KP/59段/最大栈23，align44/11；H/PRE等高度未变。
- 实际S4/LUT覆盖三色/三bank、十次全方向换档、单独改变图像X不换档、PALM锁定后失掌/换区盲交付、对齐/递送途中取消原槽开爪/HOME/库存、陈旧帧/D5/COMM。实际AXI寄存器加载Y区域，含X0和127边缘查找、完整性/修订号/锁。实际S2三组正常531段36585样本，加FSM发出回放197段12177样本，六轴48762采样精确。Coppelia停止运动学精确/4小数串口舍入总97524样本0碰撞，两个mock PAUSE前缀保守重放，不是接触动力学或实机动作证据。
- 34PC/13终端通过。初次新增全X约束先于轴标签检查，旧映射拒绝测试的错误文本预期不匹配；调整错误优先级后通过，功能从未接受旧映射。新方向实板NOT_RUN。开发前源文件备份BACKUP_LOCAL.json仅本地；完整包和19规划导出复现/冻结输入/ZIP校验稍后封包记录。


### v0.9.1最终封包核对

完整包Gesture_ModeA_FPGA_v0.9.1_20261028_ImageY_DeskY，46807974B/3042文件，ZIP SHA256 `e60a8403181b0282d508ef9602695bf36e6dd3d881066c196064e66fa9b41fcd`。包内34PC/13终端、新入口独立check-only、19项JSON/CSV/采样/表导出逐字节重现、全部冻结硬件/模型/RTL/约束和74构建输入及ZIP CRC/逐成员SHA通过；运行源码检查点d2a39b8e。v090及第一稿包不改，最终新包/图纸仅本机，源码/手册/非原始验证摘要推当前个人codex分支。已恢复场景并只关闭本轮创建的Coppelia进程，无实体接口操作，新方向板测NOT_RUN。


## 2026-10-28 v0.10.0 四区固定阈值跟手最终候选

2026-10-28 v0.10.0四区最终候选开发完成、封包待核对：用户确认约390×390mm视域、画面上方→桌面+Y；取消实体采样，固定框中心Y40/64/88分界，原128图内容16～111。H=(285,115/170/220/275,175)，PRE=(350,135/190/240/295,180)，H_CLEAR z195；扩大至160mm跨度，X因可达性收回。最上区H倾角35°，随已有退爪175→195mm恢复40°，消除a2约.07mm掌面相交；失败证据保留。四bank/16配对NNa、运动中最新候选邮箱、120ms/3帧与局部160ms；PALM/FIST/库存/600-27/50Hz/无精度门槛/预接D5保持。新ABI3408整机20999LUT/19728FF/55.5BRAM/26DSP，WNS/WHS+.202/+.022ns；74输入绑定。S4全3色×4bank及十二方向切换/途中归还、寄存器/接收确认竞态/旧默认/真实UART通过；实际S2五组82600精确采样，Coppelia正常四bank和FSM回放精确/舍入165200采样0碰撞；10真实VGA PALM帧生产去抖final-top通过。Rain模型和部署视觉2400文件与v091逐字节同一，既有26样本模型/定位/流水证据复用；本轮四区实板NOT_RUN。第一稿和v091包保持；源码在codex/mode-a-four-zone-20261028，完整包在交付区封包后更新记录。

- 用户明确无需实体采样，按镜头333mm与视域390mm作名义针孔推算，掌面150mm处约214.32mm，四中心114.64/168.21/221.79/275.36取整。该近似不冒充实物标定；图像X全宽不选档，画面上→桌面+Y由用户确认。
- 从3641928b在新managed工作树codex/mode-a-four-zone-20261028开发，修改前464个源文件字节备份在本机backups，保留其他工作树与旧封存ZIP。未连接实物、未发运动命令；自行启动的隐藏Coppelia实例回放完成且恢复场景后已关闭。
- 原参数HAND_ALIGN_REGIONS默认3，旧默认归还回归通过；新生产参数4、ABI3408。4×512关键点RAM、四cell和16配对时长，实际接受cell/revision显式确认避免运动中候选改写产生确认竞态。局部移动不增长归还栈。
- a1规划出现各bank退爪自适应步数不同，统一2步；a2出现最上区payload/palm_proxy交叉，保留失败证据；a3调整持物姿态，在保持TCP高度/坐标的情况下通过。没有降低碰撞判定或改小掌面代理。
- 新板需整套BIT/HWH/XSA，D5运行前预接，不需运行中插线/Enter。启动LINE/ARM0三个新反馈→同LINE ARM1→当前姿态接HOME保持。完整流程、终端字段及回传记录见docs/mode_a_four_v0_10_0/README_CN.md。
- 完整包和绘图/大规划/现场原始记录仅本机，源码/文档/非原始证据提交个人codex分支。封包、网表及完整ZIP核对后追加结果。


### v0.10.0最终封包和独立网表复核

2026-10-28 v0.10.0完整四区包已完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.10.0_20261028_FourZone_FixedThreshold，49551520B/3185文件，ZIP SHA256 0fd038d9ff8ba730ff0979cb48f1b5eb5701217ee69bb6bc4e21916e48d61892。源检查点adfd9fefd602a88ffae1aa54867f197f229b8976；包内33PC/13终端、25项规划导出逐字节重现、74输入与同次BIT/HWH/XSA绑定、独立check-only、全成员SHA/ZIP CRC通过。新整机20999LUT/19728FF/55.5BRAM/26DSP，WNS/WHS+.202/+.022ns，内部未约束0，28CDC安全，Gray skew余量8.981/9.151ns，DRC0错误/35警告(4类)。不需掌位采样或hand-map文件，D5运行前预接。四区实体NOT_RUN，第一稿/v091保留。

- 完整包包括新生产4区ABI3408硬件、四组三色轨迹/原生角度CSV、固定区间图/路径图、实际FSM归还回放、源代码/模型/约束/操作手册及实际证据。包内重新生成25个规划/表/采样/CSV文件与交付版本逐字节一致。新入口check-only不访问硬件通过。
- 精确S2 82600采样与Coppelia精确/串口舍入165200采样、12次三色四区正常任务和4种归还情景通过；生产120/2000/500/1000ms计时、运动中候选更新和显式接受竞态有专门验证。10真实VGA帧未缩短生产300ms视觉去抖，最后确认PALM qualified/event有效。
- LUT较v090增加342、FF增加651，BRAM55.5和DSP26保持。布局布线中间曾有相机IOB setup负余量，既有postroute物理优化后最终+.202ns，没有放宽任何时序/输入约束。独立网表复核确认10路正沿IOB、共享相机RAM8块/单MMCM及Gray约束保持。
- 全部新源码和非原始证据在个人codex/mode-a-four-zone-20261028推送；完整板包ZIP、绘图脚本、路径图和大体积规划保留本机，不声称ZIP已上传GitHub。旧封存ZIP和标签不变。


## 2026-10-28 v0.11.0 Locator独立三档跟手修复

2026-10-28 v0.11.0 Locator独立三档修复开发中：用户采用独立新鲜定位去抖、收窄选区并要求明显运动、缩短局部段与少量整体提速，ESP32先不处理。新codex/mode-a-locator-follow-20261028基于ac4daec6；三档Y54/74分界，H=(285,135/195/255,175)、PRE=(350,155/215/275,180)，跨度120mm，bank3同bank2备用不启用。新HAND_ALIGN_LOCATOR参数/ABI3409，原始同帧Locator中心和检测有效性独立80ms/2帧/250ms新鲜度，PALM/FIST语义仍按原确认。对齐中新目标PAUSE→等pending0→CLEAR→LAST_DELIVERED实际角差重定时；局部48ms停稳，整体规划上限+10%、660/33/50Hz，无到位精度门槛。JTAG每个mrd/mwr绑定唯一Cortex-A9#0 target-id，无自动运动写重试。40PC、实际S4三色三档/六方向/改向/排空/原槽归还/故障、独立定位/竞态/旧默认、真实115200新速度通过；S2共57285精确采样、Coppelia114570采样0碰撞。a1角差组合链时序不足主动终止保留，已拆流水并在a2重实现；最终硬件/包仍待核对，实板NOT_RUN。

- 最新v010 four_board_01：用户报告动作通过；只读1277快照约191秒，实际bank1/2十次切换，最上/下无有效已确认手势位置候选。记录累计done1/cancel1，蓝RELEASE时JTAG PA地址空间错误，恢复未确认；不写成三色正常退出。旧光学视域等分与可识别范围不一致，分类确认串入位置通路。旧日志EMA位置按新54/74分界在定位有效快照中覆盖三档，仅作选区依据，不冒充新raw跟随实测。
- 修改前1270源文件备份在本机backups。新模式默认参数0保证旧构建；生产4存储bank/3有效区，原三槽/B/相机/高度/原槽归还/库存/预接D5/冻结权重保持。最上H35度在退爪中恢复40度。
- 独立定位单测覆盖class7/6未确认分类仍跟随、invalid/stale重置、非PALM不锁定及匹配PALM锁定；S4 mock故意保留1024cycle pending，CLEAR/MOVE前排空断言通过。a3/a4实际发出目标trace逐字节相同，流水只增加内部时钟，不改N/Na/目标；对应S2/Coppelia绑定复用。mock暂停前缀保守重放，不作实体制动/速度连续声明。
- a1单周期角差选择/减法/绝对值/最大值链在布局布线后负余量，主动终止自建进程树，文件保留ABORTED，不供上板；a2拆为三拍流水重新综合实现。首次旧默认编译暴露hstep声明顺序、首次bench嵌套case语法均已修复并保留失败记录。
- XSDB2026.1本地源码确认mrd/mwr支持target-id，原PA解析依赖当前target。新脚本缓存唯一CPU target-id并在CPU选择时刷新；stub验证外部当前target变化不影响内存命令，真实写失败仅调用一次、保留bus_fault停止。现场PA错误根因及新修复效果NOT_RUN。ESP32固件未改、未访问实体接口。
- 完整板包、图纸/绘图脚本、原始实测及大规划保留本地，只提交源码/手册/非原始证据；旧封存包不覆盖。最终资源时序/完整包结果待实际完成后追加。


### v0.11.0最终整机与完整包验收

2026-10-28 v0.11.0三档修复完整包已完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.11.0_20261028_LocatorFollow3_Fast_Final，50008801B/3315文件，ZIP SHA256 d43c4b669cf3da663218e8006ad8f18124b2d37cec60ed45b59e782d15963c49，源码检查点681b185975b4745a3753c9ec84ec7886b0fc1439。新ABI3409整机21539LUT/19842FF/55.5BRAM/26DSP，100MHz WNS/WHS+.414/+.018ns，TNS/THS0、内部未约束0、28CDC安全、Gray skew余量9.168/8.902ns、DRC0错误/35警告(4类)。包内40PC/13终端、25项规划逐字节重现、74构建输入与同次BIT/HWH/XSA绑定、独立入口check-only、逐成员SHA/ZIP CRC通过。S2精确57285采样、Coppelia精确/舍入114570采样0碰撞，10真实VGA帧及原始Locator中心不受分类去抖/EMA阻塞的整机断言通过。独立定位80ms/2帧、Y54/74三档/120mm跨度、途中PAUSE排空接续与48ms局部停稳、660/33整体约+10%、预接D5和无精度门槛；ESP32未改。新实板/实际延迟/PA现场复测NOT_RUN。只用Final后缀完整包，旧版及失败记录保留。

- 21539LUT较v010增加540，FF增加114，BRAM/DSP保持；a2流水角差链消除内部负余量，未改变任何约束。独立网表保留正沿10路IOB、共享相机RAM8块/单MMCM、11bit双同步Gray总线及10ns skew约束。
- a4状态机与a3目标trace逐字节一致，覆盖pending保留1024mock周期后排空再CLEAR/MOVE；a503整机10真实VGA PALM帧生产300ms确认与新raw中心线路检查通过，未缩短语义计时。2400部署视觉/冻结模型文件与v010逐字节相同，复用旧26样本逐层CNN/Locator/流水证据；不声称本轮重新训练或重跑这些未变模块。
- 首次封包残留文档路径、第二次缺少新follow脚本筛选被包内检查检出；两未完成目录标INCOMPLETE并保留，不供部署。第二个在验证绝对源/目标均位于指定deliverables根后，原生PowerShell移动到INCOMPLETE_a2；无删除。最终Final包从父ZIP重组并重跑40软件/13终端、25项重规划一致性、入口与全部哈希/CRC，全部通过。
- 完整包及绘图脚本/图纸/大规划保留本机，源码/文档/非原始证据推送codex/mode-a-locator-follow-20261028；旧第一稿/v091/v010 ZIP及现场原始日志不改、不上传。新四区来源版本仍可回退，实机跟随延迟改善与显式CPU目标绑定的PA故障复测由本轮用户测试确认。


## 2026-10-28 v0.11.1 PALM中心区域回归修复

2026-10-28 v0.11.1 PALM中心区域修订：已查v0.11.0 follow_board_02，1242快照约202.10秒正常退出，done0/cancel2，通信/规划错误0；最后PALM分类已确认，同区PRE等待超过2秒，但raw框下缘126～128超过旧整框Y16～112，window始终0、PALM计时0。v011切raw后保留旧整框/角点限制是回归。新codex/mode-a-palm-window-fix-20261028基于ac151d7d，仅数据/软件改适配器X/Y0～128、角点128，保留3帧PALM；实际空间由S4新鲜已接受中心cell控制，PRE2秒/PALM500ms/80ms2帧定位/250ms新鲜度保持。三个档位各完整盲交付/释放/HOME及中心越界/陈旧拒绝、旧配置复现共6项实际适配器+core+S4 XSim通过（运动mock）；45PC通过。硬件ABI3409、模型、路径/速度/归还均冻结复用v011，待完整封包核对；新补丁实板NOT_RUN。手册docs/mode_a_palmfix_v0_11_1/README_CN.md。

- 原始实测日志仅本机，诊断脚本提取非原始汇总及日志SHA256；首次follow_board_01为独立JTAG Invalid context失败，不混入02正常退出结论，也不声称本补丁解决该问题。
- 本轮修改前源备份已保存在本机backups，新分支保留所有旧包/现场日志和未跟踪资料。未连接实物或发送运动命令，不修改ESP32。
- XSim a1声明顺序、a2接口端口、a3仿真背景不足一帧未重武装的问题均在测试台修正并保留失败记录；a4使用实际50ms帧间隔、背景至少3帧后重选，6项通过。生产RTL未改。
- 适配器不再把原始框延伸进上下填充区或角点尺寸变化视作交付位置判断；中心有效区16～111、同区停稳和PALM连续语义保持。新的45项PC包含实际新入口装载、仅两寄存器差异、运动/任务写完全一致、原桥权限和40项父基线测试。
- 完整板包将从冻结v011 ZIP重组，重跑45PC/13终端和独立入口/逐成员SHA/CRC；74构建输入和全部硬件/模型/规划逐字节复核后追加最终结果。只推源码/手册/非原始证据，完整包与图纸/大规划保留本机。


### v0.11.1最终包验收

2026-10-28 v0.11.1最终完整包已核对：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.11.1_20261028_PalmCenterGate_Final，50155203B/3344文件，ZIP SHA256 a9307055f98a21e3469434a2ac9c7b7a8d7f934260a20e996b77098fc5f0bc0b，源码检查点5a47d6dc4a61524684ea476c23b1f34479432453。包内45PC/13终端、独立新入口check-only、全部成员SHA/ZIP CRC通过，2486冻结文件及74构建输入与v011逐字节一致；复用原BIT/HWH/XSA、模型、全部三色轨迹/速度和S2/Coppelia证据。新适配器+core+S4共6项离线回归通过（mock运动链），新实板NOT_RUN。D5运行前预接，入口scripts/run_mode_a_palmfix.py，使用手册docs/mode_a_palmfix_v0_11_1/README_CN.md。完整ZIP与原始日志保留本地，源码/文档/非原始证据推codex/mode-a-palm-window-fix-20261028。

- 本次封包直接读取已冻结v011 ZIP，校验全部父成员后抽取；不复制父目录里的原始runs。父MANIFEST/README/验证摘要保留为evidence/V0110_*，新证据与新清单分版本。
- 只改变视觉配置中的Y整框范围和角点上限两项；实际loader测试确认其他后端/任务/运动写序列完全一致。保持原始框和3帧PALM，中心有效区/同区/PRE最少2秒/PALM500ms及陈旧阻断不变。没有修改可综合RTL，无新资源或时序变化；复用100MHz +.414/+.018ns构建。
- 完整包50155203B、3344文件，SHA a9307055f98a21e3469434a2ac9c7b7a8d7f934260a20e996b77098fc5f0bc0b。新实物PALM触发和实际交付效果需用户现场确认，不用离线mock的done代替实物通过。


## 2026-10-28 v0.12.0 HDMI简洁显示

2026-10-28 v0.12.0 HDMI简洁显示版开发中：用户要求参照Phase2，只有一个最终框，显示手势/无手势、机械臂命令和执行状态，注重简洁美观。独立codex/mode-a-hdmi-20261028基于12010faa；新增PL灰度384×288画面与中文三卡片、反馈在线标志，640×480/60Hz HDMI OUT。保留v0111模型、三档路径/速度、PALM中心条件/FIST归还/无精度门槛/预接D5；控制源逐项一致，S4顶层只新增只读tap。实际a3新整机22332LUT/20430FF/72.5BRAM/26DSP，100MHz WNS/WHS+.409/+.035ns，TNS/THS0、内部未约束0、87CDC全部safe、Gray skew9.077/9.029ns、DRC0错误35警告(4类)，85构建输入与BIT/HWH/XSA同次绑定通过，新增HDMI MMCM/6 OSERDES/16显示RAMB36及25.2/126MHz独立检查通过。48PC、5显示单项和实际UNISIM串行器通过；整机十帧回放及最终匹配图像/确认PALM快照在a8通过（长回放串行器sink，生产原语独立UNISIM通过）。硬件/显示器实测NOT_RUN，最终包待封。

- 修改前源快照在本机backups，保留旧板包/原始runs和其他未跟踪目录。未访问板卡、JTAG或机械臂。只交付最终完整包，不要求测试中间检查点。
- 复用Phase2四个原始模块：视频时序、TMDS编码、7系列串行输出、双口RAM；新建独立四显示bank适配双帧推理。只发布完整且frame_id匹配图像/框，在视频帧边界换bank，不阻塞摄像头，不加入PS实时显示决策。仅画raw Locator最终框，裁去上下填充恢复4:3；没有EMA/ROI额外框。
- 中文点阵ROM静态部署，深蓝底、青绿框，三卡片呈现确认手势、当前任务动作、执行阶段。无效/陈旧分类显示无手势；定位新鲜性独立于分类。当前任务命令并非ESP32逐条T102确认，反馈在线按原生反馈有效性/掩码/年龄及错误，手册明确界限。
- 新增ENABLE_HDMI构建参数默认0，开启才接25.2/126MHz独立时钟和HDMI OUT；不改任务ABI3409和AXI窗口。源保持+请求/应答+双级同步快照，帧边界更新；综合后状态16bit/图像框39bit，CDC6多bit总线人工核对握手和测试证据，原相机Gray11bit同步/skew保持。
- 单测随机变化源的快照无撕裂，51次只在帧边界更新；四bank保护、延迟结果/图像匹配和不匹配拒绝通过；640×480全部307200可见像素/消隐/中文语义/单框预览、TMDS逐bit编码、视频时序通过。真实UNISIM六串行器/三通道十bit周期与差分转发时钟通过。
- a1声明顺序在整机仿真发现后主动终止本轮构建，a2for循环声明Verilog兼容性被综合检出；均保留不供部署。a3使用相同逻辑兼容声明重建通过；综合0Critical/0Error。BD对TMDS输出自动推断clock接口的FREQ_HZ metadata提示经实际网表25.2/126MHz与完整约束核对，不代替时序检查。
- 整机回放早期编译补齐UNISIM/secureip/glbl和命令行引号，带加密串行器的长回放主动终止；生产串行器独立UNISIM测试，长视觉回放仅串行输出替换sink，实际像素缓存/渲染/编码/模型/控制均保持。a7十帧模型/ROI/图像配对通过，最后确认状态在20ms检查点尚未跨第二视频边界，按设计最坏33.34ms改为40ms后a8重跑。未据此改变产品RTL，也不声称sink验证了物理TMDS。
- 使用手册docs/mode_a_hdmi_v0_12_0/README_CN.md与INTERFACE_CN.md，新增HDMI OUT线，D5运行前预接；先monitor-only看屏且tx0，再run闭环。模型/控制原语与全部三色轨迹冻结，S2/Coppelia复用原哈希证据；完整包/预览图/原始记录本地，源码/文档/非原始证据推个人codex分支。

- 最终a8实际10帧全部模型/ROI/原始中心/adapter身份验证通过，最终frame_id9正确显示且确认PALM快照与adapter一致；未缩短生产300ms去抖。含40ms边界等待共409.06288ms仿真、实际8分51秒，无实体访问。a7失败条件修正后的a8已完成，本轮最终选定证据为HDMI单项a3、串行器a1、整机a8、硬件a3。


### v0.12.0最终完整包验收

2026-10-28 v0.12.0 HDMI完整包已封版：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.12.0_20261028_HDMI_Clean_Final，50649795B/3415文件，ZIP SHA256 c5285dcbe1b836672e0251287eed30ac9399c74568efea13bd09f4ee8c672708，源码检查点70c5875b741f3f775ca901ce18495506fdc27614。新BIT/HWH/XSA及85构建输入绑定，包内48PC/13终端、独立入口check-only、全部成员SHA/CRC通过；模型/全部路径和控制原语冻结，除S4顶层只读tap外同一。6项显示/真实UNISIM仿真、a8十真实VGA帧/最终匹配图像及PALM快照通过（长整机回放串行器sink、实际串行原语独立验证）。22332LUT/20430FF/72.5BRAM/26DSP，WNS/WHS+.409/+.035ns，87CDC全部安全。HDMI_OUT→显示器；D5启动前预接，run_mode_a_hdmi.py先monitor-only15秒再闭环。新显示器/实物闭环NOT_RUN，完整ZIP/预览图在本地，源码/文档/非原始证据推codex/mode-a-hdmi-20261028。

- 从封存v0111 ZIP按成员SHA/CRC抽取，不复制现场runs；替换同次新硬件和85构建输入，父硬件/验证说明以V0111前缀归档，模型/规划/控制原语2481文件保持，S2/Coppelia仅按原未变运动哈希复用。
- 包内48软件检查实际验证新入口的控制写序列与v0111一致，13终端检查通过，完整模型/源/硬件/路径/仿真绑定和独立check-only通过。3415成员和ZIP CRC逐一核对，旧v0111及第一稿不覆盖。
- 实物测试分两步：D5预接，先monitor-only15秒确认单框/中文/无手势/反馈，运动tx0；再run三色闭环，PALM锁定后盲交付，FIST按原策略归还。新显示器画面、原生串行物理信号和实物闭环尚未上板，均NOT_RUN；RTL预览是实际渲染器输出配真实训练样本和注入等待状态，不作实拍。


## 2026-10-28 Mode A v0.13.0 source checkpoint — five upgrades / under85%

用户采纳CNN内部流水/通道并行、256×192灰度HDMI、S曲线/jerk规划、有界连续Y跟手（无需实体采集）、片上分阶段时间戳与轨迹记录，开发前要求资源不超过85%。初步预算在board_evidence/mode_a_upgrade_a1/RESOURCE_BUDGET.json，原v012BRAM72.5，预计107.5～111.5；采用分类器双输出/共享双读ROM、Locator保留8lane、复用三锚点关节表，完整整机实际111.5/140=79.643%。备份保留本地，不上传完整包/图片/原始现场记录。

实现：新增无反压256×192相机采样和4显示bank、L/C/A页脚；五次10u³−15u⁴+6u⁵复用顺序乘法/除法，原生1320步/s与acc66、50Hz；64细分Y状态、有效图像中心Y16～111/44～84线性映射、PRE/H既有三锚点与毫米级中间FK偏差；PALM只在停稳PRE确认后锁定盲交付，FIST1秒归还原槽/HOME。片上256×256bit环形记录含事件/周期/六轴LAST_DELIVERED，冻结导出、覆盖及冲突显式计数。新ABI TASK340a/PLAN3203/VIS3506，ARM3101/模型022267a9不变。

验证：26冻结分类样本8阶段、logit和margin精确，周期750170→468486（4.68486ms）；两帧完整VGA/原128预处理与真实256预览采样、所有65位置/47KP原始预检和插值、96行坐标映射、256区间毫秒换算、环形覆盖/冻结/六轴记录通过。三色×五中间位置、PALM/FIST/改向/排空/归还/库存及旧D5/COMM条件通过（运动transport为mock，不能当实物）。65位置原生612495/精确与T102舍入Coppelia1224990采样0碰撞，XYZ关键点最大偏差约3.531/0.973/1.680mm；实际S4命令594段29658精确S2采样及59316 Coppelia改向/归还回放0碰撞（mock停止点中点，非制动力学）。三锚点28269实际S2、9423暂停/反压、N2～65535标量边界、45PC/13终端、新原生115200/1320/66/50Hz、12真实VGA/ML/HDMI集成通过；长集成串行器sink，实际UNISIM串行器另验。33规划文件重算逐字节一致。

a1激活RAM模板不支持、a2坐标除法时序失败、a3插值组合及后续常数除法长路径、a4发现共性长路径后主动停止，均保留并禁止发布。最终a5标准TDP、四级关节插值流水、等价坐标映射、顺序N²/6、显示分级换算与新鲜度一级寄存器后：整机26159LUT、23021FF、111.5BRAM、32DSP；100MHz WNS/WHS +.270/+.021ns、TNS/THS0、内部未约束0；111CDC全部safe，Gray10ns skew余量9.189/9.227ns；DRC0错误44建议，类型BUFC-1/DPIP-1/DPOP-1/DPOP-2，SCL输入无负载及DSP内部寄存器性能建议，已按实际时序审查。独立检查10正沿IOB、原共享相机8RAMB36、48HDMI RAMB36、4trace RAMB36、2MMCM/6串行器、HDMI25.2/126MHz及ACK快照CDC通过。89输入与同次BIT/HWH/XSA绑定，BIT03da9005/HWH079a35dc/XSA81009ea4。

手册docs/mode_a_upgrade_v0_13_0/README_CN.md，入口scripts/run_mode_a_upgrade.py。普通段速度上限2倍不是全流程时间减半；中心三色插补29.06/29.14/29.74秒，另加固定6.176秒、PRE/PALM和跟随等待。中断点不宣称全局jerk连续。D5启动前预接，PYNQ D1/TX、D0/RX及已验证3.3V沿用；先15秒monitor-only/ARM0，再现场三色、PRE移动/锁定与持物取消。新实板/显示器兼容性/实体成功率和实际跟随延迟NOT_RUN；本地完整包待封校验，ESP32与实体标定未改。


### v0.13.0 complete package seal

Final目录Gesture_ModeA_FPGA_v0.13.0_20261028_ParallelHD_ContinuousSmooth_Final；ZIP46770243B/3056文件，SHA2567bb4196160198f88aec54c3bf58fcd43029838c5b5bf76a2f397fed38ef8e267，source checkpoint eaf54597245fd587197e0469c52a101c97bdea46。包内45PC/13终端、独立新入口check-only、全部成员SHA和ZIP CRC通过，同次硬件89输入/模型/BIT-HWH-XSA与整机资源≤85%检查通过。完整包/渲染图/细节规划与仿真原始记录保留本地，源码、手册和非原始汇总推送独立codex/mode-a-v013-upgrade-20261028分支。新上板/显示器实测仍NOT_RUN，用户按README_CN.md先D5预接的15秒monitor-only，再红黄蓝/跟随PALM锁定/FIST归还测试，保留运行目录。


### v013 packaging follow-up: cold replan inputs

首次包独立check-only/45PC/13终端/SHA/CRC通过，进一步在包根目录执行prepare_mode_a_upgrade.py发现4份旧A残差基准（handoff/giao_427c805c与giao_9504e60e的既有JSON）未随过滤器复制，运行不受影响但离线重算不完整。已将首次包和ZIP移入PackagingAttempt_a1_NOT_FOR_DEPLOYMENT，不删除证据；修正封包过滤器包含父包原有4份handoff输入，硬件与规划均不变，重新封包后再做包根目录冷重算与33文件逐字节核对。原首次封包SHA7bb419...不再用作最终交付。


### v013 final package and standalone replan verified

最终仍用Final目录，已补齐父包4份handoff/A残差基准。包内独立重算33个文件逐字节一致、再次check-only通过；完整包46782973B/3060文件，ZIP SHA256 805fc1da0383e9c99c2b02d22931c7eb3f4b70b3bb3ad2e0682a5ffae8089173，source checkpoint 92ce4a5522fbdb47c469d821cd4d43636a37cb7a。第一次封包保留为PackagingAttempt_a1_NOT_FOR_DEPLOYMENT，其旧SHA不作交付。最终入口/45PC/13终端/所有成员SHA/ZIP CRC通过，BIT/HWH/XSA与89源码/模型/约束输入同次绑定；新实板与显示器仍NOT_RUN。完成后推独立codex分支；完整ZIP、图像与详细计算/原始记录不上传。


## 2026-10-29 v0.13.1 HDMI720p 显示兼容性补丁（离线通过，完整包待封）

用户照片呈现整幅UI/画面/页脚横向环绕。独立codex/mode-a-hdmi-alignment-20261029基于9077a543；修改前本地502文件备份保留。旧640整帧串行接收307200像素/同步正确，未复现照片故障；严格时钟/数据同字相位测试旧ODDR不通过，作为兼容性修正依据，唯一实板根因未确定。新增1280×720/60Hz、74.25/371.25MHz正同步、960×720居中画布（两侧160px），四路匹配串行器固定clock word。首次a1组合缩放31级/23.628ns、placed -11.309ns，仅停止本轮构建树并保留失败，不交付；a2用1.5BRAM同步坐标/源地址ROM，DE/HS/VS/frame_start同延迟一拍。保留单最终框/三卡片/LCA与原字体和布局。另修复终端RETRACE跨采样缺少planned_waypoint的KeyError，不改PL控制、PALM/FIST或JTAG处理。

实际验证：坐标2048X/1024Y穷举、6项显示单项、8个UNISIM串行原语、1237500串行字/921600像素与旧完整画布floor缩放精确一致；12真实VGA夹具经过生产采集/ML/适配器/HDMI集成15PASS（长集成serial sink，真实串行器独立整帧验证），46PC/13终端通过。62个非HDMI控制/视觉/运动RTL与v013逐字节相同，Rain模型、三色规划/速度/库存/PALM/FIST规则冻结复用，未重做实体映射。

a2整机26052LUT/23024FF/113BRAM/32DSP，最高80.714%<85%；WNS/WHS+.222/+.019ns，TNS/THS0、内部未约束0；111CDC全部safe，Gray skew9.008/9.035ns；物理DRC0错44建议4类。继承XDC if解析警告已记录，实际双向sys↔pixel异步分组独立核对，没有放宽约束。网表8OSERDES、坐标1RAMB36+1RAMB18、显示48RAMB36、相机8RAMB36、trace4、正沿IOB10，91构建输入/BIT/HWH/XSA绑定通过。BIT SHA9b59429c8f5b51b2a20e9724c617a12c65d34eae196e28c031cc8b35e8cd9b7e。新显示器/实物闭环NOT_RUN；D5启动前预接，先monitor-only30秒检查布局再进入闭环。最终包待封存SHA与冷入口检查；源码/手册/非原始证据推个人分支，完整包/图像/原始报告留本地。


## 2026-10-29 v0.13.1 最终完整包封存

本地目录/ZIP：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.13.1_20261029_HDMI720p_DisplayFix_Final，46992811B/3103文件；ZIP SHA256 5648c8978f7be9f3dd0961866af96081795d21da34eea7dbb4b9cc38c58fecf4，源码检查点f0fab40eb8888707756fc243afec216ebd348943。包内46PC/13终端、独立新入口check-only、所有成员SHA/ZIP CRC通过；4份最终显示回归共98项源码哈希与包内源码独立对照通过。91构建输入、同次BIT/HWH/XSA、完整原三色规划/模型/手动补料/取消规则绑定，CONTROL_MOTION_REUSE证明2476个冻结模型/候选/非HDMI RTL文件逐字节相同（实际数量以JSON为准）。新显示器/实物闭环NOT_RUN，最终布局为左图像/右三卡片，1280×720/60Hz，两侧160px深色留边正常；先D5预接、monitor-only30秒，再进入原三色流程。源码/手册/非原始证据提交并推独立codex/mode-a-hdmi-alignment-20261029；完整ZIP/图片/详细报告只保留本地。


## 2026-10-29 Mode A v0.14.0 空槽自动复原（离线通过，完整包待封）

- 用户确认v0.13.1显示已正常。本轮确认公共点为同桌面30mm木块中心D=(300,200,15)mm，三色均支持；IDLE时数字1/2/3对应有货则原交付、空槽则公共点取块→原槽→HOME，最终HOME完成后才恢复库存。复原不等PALM、不跟手，持续数字不连发，需背景重新武装。原人工r/y/b直接补回原槽确认保留。
- 复原FIST连续1秒：尚未夹取退出HOME，持物沿实际轨迹逆退放回公共点后HOME，目的槽仍空；原槽开爪放回一旦提交，按原released策略完成退出/HOME再置库存。通信/D5故障不补写库存。到位误差仍observe_all，1320/66/50Hz五次曲线、正常交付/连续Y跟手/模型/720p布局和串行器保留。
- 仅公共点新增反解，复用原A残差及B/INNER/三色槽位已通过的原生角度。新表46关键点/51段，共享前缀15段+每色尾段12段；复用闲置KP bank3、段RAM扩为256×32同一RAMB18。TASK ABI340B、status bit29、描述符374/378/37C/380、补料计数388，原正常文件340A格式逐字节保留，由新入口合并合同。初次实现a1的补料事件bit11与既有PS_WRITE_BLOCKED冲突，已保留NOT_FOR_DEPLOYMENT并修为独立bit14，新增实测仿真断言覆盖该冲突。
- 新S4真实寄存器RAM/读流水/FSM7组通过（运动链MOCK）；原连续交付/FIST回归7组通过；实际S4发出的7条正常/取消路线176段8776采样，实际生产S2六轴逐样本精确，修复事件位后MOVE日志逐字节相同。名义+中点返回Coppelia精确/四位小数各68155采样，实际S4/S2回放各8776采样，均0碰撞/关节恢复0；停止网格与几何附着，不等于动力学或实物抓放。
- 70项源码PC/终端测试、7项HDMI及12帧生产VGA/ML/显示集成15项断言通过。v0.13.1串行器/时序/画布/帧缓存/CDC8组件逐字节保留；新增字体/补料标签另有本轮显示回归。父包冻结4文件独立重规划逐字节一致。
- 最终a2整机实现26568 LUT/23188 FF/113 BRAM tile/32 DSP，最高80.714%<85%。WNS/WHS+0.302/+0.009ns，TNS/THS0、内部未约束0；114 CDC全safe，Gray skew余量8.864/8.782ns。DRC0错误、44条既有警告/4类，继承XDC解析诊断独立审查，未放宽约束。独立网表审查：原10个正沿IOB、无IDELAY冗余前端、8串行器、相机/显示/坐标RAM与新增单个共享段RAM均符合；91输入/BIT/HWH/XSA绑定。
- 个人分支codex/mode-a-auto-restock-20261029，基于e410dd08；备份snapshot_20261029_034953_before_auto_restock.zip保留本地。新入口scripts/run_mode_a_restock.py；D5启动前预接，先monitor-only再同进程交付→公共点补回→再次交付，不能重启假定库存持久化。本轮无板卡/JTAG/实体动作，physical_hardware_test=NOT_RUN。手册docs/mode_a_restock_v0_14_0/README_CN.md；完整包、CSV、原始规划与缓存在本地，源码/手册/精简证据按个人分支推送。
