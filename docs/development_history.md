# 开发日志归档

来源为截至 2026-11-03 已提交的团队开发日志。发布前已处理个人目录、设备标识、邮件和内网地址。历史测试与交付路径用于追溯。

# 工程进度与状态日志 (PROJECT_LOG.md)

## 2026-10-21 Phase2 还原图像通过、当前A格式失败及判据差异定位

用户完整断电后确认JTAG/USB上电、原OV5640/机械臂断开/D5低，授权Phase2对照通过后当前A前端，无场景。v0.1.2 loadhw原HWH因工具层后缀被当SDK工程名，未读相机；Tcl实际恢复通过，host将测试退出2误记恢复失败的缺陷在v0.1.3修复。v0.1.3用字节相同XML别名，真实XSDB set_memmap元数据链PC检查通过，实板ABI403/芯片5640/原表和关键寄存器通过，但PC守卫漏6/7被拒。v0.1.4修复真实相机控制位，原驱动670笔fake-MMIO写同时经过实际Tcl守卫、18流程故障案例通过，取回正常128x128 Gray8/16384B，fmt0/drop0/FIFO0/ACK0。主机误拒RTL从0开始的首帧，原结果保留；独立审计32块4096词与PGM/PNG、valid/身份/计数/收尾逐项通过，不为错误ID>0判据重复试板。

当前A原BIT单次五ID/CAM1/初始化与无运动权限通过，格式13→14（2相干样本间0.266s），立即停止，未取当前VGA图或60秒/手势/机械臂。初始源年龄238ms只单点；无FIFO/pipeline错误，主机PL写0。PS/CPU恢复和服务关闭均验证通过。随后Phase2同BIT仅改4740=20/00各60秒/703新身份，持续格式增量0/drop0/预览正常；00预览启动格式增量1和基线1保留，不把它写成零总错误。

新增PC定向XSim使用封存旧letterbox与当前retained源码，合法VGA均fmt0/发布且4096词独立黄金精确；在行94多(x640,y94)token时旧fmt0/仍发布2帧且图像精确，当前fmt1/拒异常帧并在下一合法帧恢复。证明旧缩略图计数不等于当前完整VGA坐标门禁，Phase2好图不能排除之前1281字节/641Y。原RTL/模型/初始化/XDC/BIT均保持；没有新资源时序成绩，物理根因/当前4740读回/真实边沿仍未关闭。

已提出具体21项SCCB只读快照＋另一PCLK相位旁路行长/身份/冻结CDC候选，保留原采集IOB/功能、初始化时点、模型/XDC、全局计数/250ms/停止与运动许可；用户新明确同意开发，离线仿真/完整综合实现/IOB/半周期路径/CDC/DRC门禁通过后本轮直接有限取证，不再重复申请该范围。硬件访问已停止，服务关闭；既有两个v0.7未跟踪模块保持，后继新副本审查复用。本轮资料各自封存，local-only不推送。

## 2026-10-21 Phase2 JTAG v0.1.1 实板未完成与 v0.1.2 离线修正

用户授权全链离线检测后直接Phase2封存相机对照，通过再测当前A相机前端，只看格式/大小/图片，无布置场景，机械臂未接。用户新确认JTAG/USB上电、原JA/JB、机械臂断开/D5低。离线审查资料以2da5a02本地提交封存。

v0.1.1修正旧脚本启动/收尾并完成17Tcl全流程/故障模拟、实际XSDB check-only、原驱动fake-MMIO和图像编码检查。18:02:24～18:02:39实板单次，原Phase2哈希匹配、BIT配置通过；首笔43C10008被调试器PL地址保护拦截，memmap未满足Zynq硬件映射要求。尚无相机寄存器/图像结论。保守停止所有后续访问，恢复未确认；自建服务关闭、3121无监听。已请求用户完整断电，未自动重试。

v0.1.2离线确认实际HSI可直接打开原始匹配HWH、相机页43C10000..43C10FFF，改为loadhw该HWH且仅此页，不用跨版本XSA/-force。补模拟PL保护层后18案例/原驱动/实际XSDB离线/实际HSI解析通过。未试板，待用户断电确认再通知上电。失败与后继脚本各自隔离保留。原RTL/模型/初始化/XDC/BIT/HWH无修改，无新资源时序结果。本轮资料仅本地提交，不推送。后续仍按Phase2→当前A前端→用户逐步接入机械臂推进。

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
- [x] 成功登录 `[local-ip]:9090`，只在板端新建
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
  PC 到 `[local-ip]:9090` 的超时仍来自本机网络隔离，板内访问 Jupyter 返回 302。
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
  因而不存在 `[local-ip]/24` 物理接口，`[local-ip]:22/9090` 均不可达。这不是
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
  `[local-ip]/24`，登录Shell可枚举`pynq.pl_server.embedded_device.EmbeddedDevice`；手工
  服务运行674帧，Overlay、Locator v16、分类器v3、USB摄像头和LED链路通过，停止时
  `stall/drop`均为0。
- [x] `gesture-demo.service`新增`After=bootpy.service`，启动前最多60秒检查
  `pynq.Device.devices`，并将失败策略收敛为5分钟最多3次、重试间隔10秒，避免异常时无限
  重启拖垮系统。板端`systemd-analyze verify`通过，旧unit备份为
  `/etc/systemd/system/gesture-demo.service.pre_boot_order_20260823`。
- [x] 最终正常重启验收：`gesture-demo.service`为`enabled/active`、`NRestarts=0`，
  `bootpy`结果success，FPGA Manager为`operating`，日志确认`OVERLAY PROGRAMMED`、
  `MODELS READY`、`CAMERA OPENED`并连续运行超过986帧；Jupyter服务保持active，PC访问
  `[local-ip]:9090`成功。镜像原有`haveged`及ISC DHCP v4/v6失败不影响当前静态直连和
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
- [ ] 包内Python 141项本机未复跑：现有Python缺少pytest，记`NOT_RUN_MISSING_PYTEST`。PYNQ `[local-ip]:9090`只读检查超时，B1-B6均`NOT_RUN_BOARD_UNREACHABLE`。
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

- 用户提供[local-user-directory]/Downloads/phase3_board_evidence_20261006.tar.gz，4063字节，SHA256 f6a855816f1572a8a0510ef172af89209f31958effb7a2b13ceacfb03fe69242。只读检查28成员（7目录+21普通JSON/JSONL），限定runs/七个预期目录及三类文件，拒绝穿越/链接，逐字节保存到reports/phase3_coppelia_s8_board_logs_20261006。原上传文件不改，ARCHIVE_MANIFEST记录21项来源大小/哈希。
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


## 2026-10-11 — NativeMotion 源码对应硬件架构图

用户要求调用image2.5并严格按.v画硬件层级、信号名和位宽，数据实线、地址/控制虚线，具体.v实线模块框、功能分组虚线框。读取当前入口/技能/实际RTL和同次生成BD，使用已板测NativeMotion RC v0.1.0而不混入旧根RTL/S7或实验模型。dev/filid开始跟踪文件干净，fetch确认个人远端无新提交；队友远端更新不合并，原未跟踪资料保留。

新增docs/diagrams/native_motion_hw_20261011：源码对应PNG/SVG、可编辑Draw.io、绘图脚本、逐信号作用域/位宽/驱动与接收端口表、完整顶层AXI端口表、实例端口绑定/被引用RTL哈希、README和图像生成提示词。顶层/视觉/任务运动局部展开，最多从S5向下三层实例；数据与地址/控制/状态线型分开，握手组保留每条实际方向。保留旧地址零读/排空说明、原生S4/S2、sample mux/LAST_DELIVERED，未把HDMI/S1旧轨迹/HAS_SO101=0画成活动路径；op_target/配置直接进入S2，不伪造u_link目标复制。

实际调用内置imagegen生成及修正图像；工具未开放模型选择，未冒称指定image2.5。生成稿仍有长标识符/额外连线或u_motion嵌套失真，正式交付采用源码对应的确定性PNG/SVG/Draw.io，草稿不作为严格信号图。检查源信号范围及实例端口方向、渲染PNG并视觉审阅，未运行额外RTL/软件功能测试、综合或板上动作。仅文档图形，没有源/模型/约束/BIT/HWH变化，不做工程备份/新板包；此前板测与资源时序结论不变。

架构图已本地提交e7173b3。git push origin dev/filid被自动审批拒绝，理由为本次图形/项目元数据外发GitHub授权和远端所有权未确认；随后用户明确答复“仅保留本地”。遵照答复保留本地图与提交，没有重试或绕过推送；本轮架构图不能随以后提交一并外发而忽略这次选择。

## 2026-10-11 — NativeMotion 架构图清晰排布修订（仅本地）

用户提供视觉参考，要求放大画布并解决旧图线路与模块重叠、标注混乱。读取项目入口、绘图/FPGA技能、既有源码合同和相关实际端口；参考图只用于间距/清晰度，不沿用其中u_motion作为u_task兄弟的错误层级。dev/filid开始跟踪文件干净，fetch个人分支无远端新增，本地此前两提交仍未推送；原未跟踪资料和原图保留。

新增docs/diagrams/native_motion_hw_clear_20261011：15600×14200完整PNG/SVG、完整大图及7个局部页的Draw.io、7张单独PNG/SVG、离线index.html查看页、复现脚本、原206条信号/95个AXI端口/源码合同及排布清单。保留原选定70组主要连接；数据/控制/地址/返回握手分离，方向按实例端口绑定，V1–V6续接标记消除跨区域长线，不代表新实例。S4原生控制目标/限速/快照独立通道；分类器ROM线路分开；S2 LAST_DELIVERED与反压返回单独绕行。PS/SmartConnect和UART fixture画在集成RTL边界外，S2在S4内。

实际执行Python文档生成、Node/sharp PNG渲染并逐页视觉审阅、迭代去除文字/连线交叠。没有新增功能测试、仿真、Vivado实现、板测或现场动作；源文件合同哈希不变，资源/时序/既有验收状态不变。仅图形文档，无工程备份、新板包或imagegen调用。遵照用户“仅保留本地”形成本地提交，不推送。

## 2026-10-18 — PYNQ-Z2 启动故障诊断 v0.1.0（仅本地）

用户原 REG 适配器、USB/网线、原 SD 卡，无其他外设；运行中突然停止，重启后仅电源灯亮、DONE 不亮、COM14 空白。按用户逐项确认完成断电/重上电、卡到电脑只读检查、原卡装回；用户批准管理员只读磁盘元数据检查及一次 CPU0 暂停读取后立即恢复。未下载程序、写内存、改寄存器/跳线、写卡/修复/重刷或执行机械动作。

COM14 115200/8N1 接收记录均 0 字节/发送 0 字节，末次重插卡录制约 240 s，其中枚举后约 182 s；早期枚举空窗仍存在。绑定物理以太网后 ARP 无板卡 MAC、SSH/HTTP 超时；初期受 Meta 虚拟网卡影响的 ping/TCP 不作为板卡在线依据。Vivado cs_server 失败不计板故障，XSDB2026.1 成功识别双核 A9/XC7Z020，BOOT_MODE=5/PLL_STATUS=0x3F。

原卡启动头/boot.scr CRC/image.ub kernel与DTB内置哈希通过；ext4 superblock 校验正确、错误计数0、空闲51.3GB，journal recovery置位不能单独认定坏卡，未全盘扫描。用户提供 E:/tools/pynq_z2_v3.1.1.zip，仅读 IMG 前32MiB解析 FAT 提取 BOOT.BIN，与原卡1165852字节逐字节一致、差异0，SHA256 3bf9c24025a489926fd76872754977c5954e2ab25c91957373386e1f20915af6；没有扫描完整ZIP或备份整卡。

CPU0 取样 PC=0x578/LR=0x1021C/SP=0xFFFF5FF0，暂停14ms后立即恢复并确认双核 Running。实际 BOOT.BIN 反汇编和板上指令读回对应 DDR 测试失败调用点0x10218→0x578自循环；FSBL要求在0x100000写0xAA55AA55读回比较，后续只读该处为0。未读到独立保存的错误码，也不声称第二测试地址一定被写。当前失败早于 U-Boot/Linux/PL overlay，优先检查 DDR 供电/参考/存储器通路，尚不能确定损坏元件；DDR控制器normal不等于存储器测试通过。

报告 docs/PYNQ_Z2_BOOT_DIAGNOSIS_20261018_CN.md；全部原始日志、只读脚本、少量卡文件/元数据、原镜像比对结果留本机 board_evidence/pynq_boot_diag_20261018_174053，不整体加入Git。REVISION本地副本中疑似凭据已脱敏，不写入Git或报告，原卡未改。下一步保留唯一原卡，优先售后/有经验人员测 DDR1.5V、参考约0.75V和相关PS供电；测量、独立DDR测试、备用卡/板交叉验证均NOT_RUN，后续改变现场先确认。

dev/filid开始跟踪文件干净，本地已有3提交未推送且含用户指定仅本地的提交。保留全部旧未跟踪文件；本轮只选择诊断报告/上下文/日志本地提交，不推送。无RTL/模型/约束/BIT/HWH改动，无综合、实现或新增资源时序结论，不做工程快照/版本板包；历史NativeMotion验收成绩保留，新增当前板卡启动阻塞。

### 2026-10-18：供电初筛反馈与JTAG小范围检查准备（历史阶段 BOARD_NOT_RUN，后续见下）

用户有万用表、无示波器/可借备用卡，确认REG与SD跳线原位并熟悉直流电压测量。适配器空载12.2V；用户报告J7 VIN/5V/3.3V与预期相同、DONE仍不亮，未提供这三路精确数值。DDR1.5V/参考电压因无明确丝印无法定位，未测；停止探针测量，先前基于照片的电感方位推断不作为已确认测点。

在本机原证据目录jtag_ddr_probe_pending准备候选ddr_probe_32_bytes.tcl及README：只在双核原本Running、CPU0保持已定位FSBL DDR失败及指令门禁通过时，暂停双核、保存/测试/尝试恢复0x100000和0x200000各16字节，经APU/AP0物理内存通路立即/50ms后读回，状态异常则不写。无复位、初始化、程序/PL下载、SD/Flash写入或接线变化；默认不访问硬件，需要用户新确认才执行。地址/长度写入白名单、原值恢复核对和CPU恢复均有错误报告，不保证故障RAM可恢复。

XSDB2026.1本机help确认命令选项。假的调试接口离线验证good/zero_reads/alias/bad_guard/write_error/restore_error六场景与地址/长度限制、非零原值恢复、异常收尾通过；offline_validation.log明确模拟，所有模拟寄存器/时间不当板测。实际板测仍NOT_RUN。只读检查现有XSA包含ps7_init.tcl/c，参数等价性未验证、未运行，后续重新初始化另行确认。本轮候选/日志仅本地，保留原未跟踪资料和禁止外发的提交，不推送；无RTL/BIT/模型/约束/资源时序变更，不做工程快照。

### 2026-10-18：已批准JTAG补充检测 v0.1.2（INCONCLUSIVE，仅本地）

用户约19:47确认REG/原SD/PROG-UART已连接上电，批准此前32字节检查，要求离开约一小时期间自主完成。按已说明范围执行，不自动复位、重新初始化或下载。先等待：COM14从19:49:19.712连续接收120.303秒，RX/TX均0、错误0，随后关闭；多次短暂停核后恢复，CPU0 PC=0x578/LR=0x1021C重现原FSBL DDR失败位置。CPU0/PA完整读回98320字节FSBL，11差异字节全位于6个正常运行时注册的异常函数入口，其余包括DDR表完全一致；削弱SD早期读入代码损坏解释，不等于整卡无损。

真实尝试保留：v0.1.0因XSDB整数格式解析错误写前停止，暂停110ms；v0.1.1修复解析后经AP0发出两个花样块及两个恢复块命令，请求范围仅0x100000/0x200000各16字节，暂停178ms后双核恢复。该通路随后在已知OCM/有效外设也读全零，故撤销其7处不匹配的硬件失败解释及恢复零读回证明，实际物理DDR写入/恢复均未验证。v0.1.2改CPU0显式PA并加BOOT/PLL/DDRC门禁，当前ctrl/mode0，写前DDR_EXIT3，暂停244ms、双核恢复，无内存写入。工具物理DDR访问提示controller held in reset，未force/关闭保护；初期normal与当前0的差异尚未解释，不认定损坏芯片。DAP事务属性临时请求后均恢复CSW0x00800042，未重设PS/DDR功能配置；一次连续只读遇工具保护停止，未当作全控制器快照。最后双核Running于原错误循环，未恢复开机。

修正脚本PC假接口7类场景及地址/长度门禁、非零原值恢复、异常收尾通过，SIMULATION_ONLY，不能充作有效DDR板测。PC仅提取原BOOT FSBL silicon1/2/3 DDR操作表；版本寄存器读0x30800000，3.0表80MASKWRITE+2POLL+EXIT，数据未执行。下一步可核对前置状态后另行批准DDR重新初始化/训练再小范围物理读写，不必覆盖唯一SD；电源1.5V/VREF、纹波、独立有效RAM/全容量/冷启动交叉验证均未完成，不让用户凭照片盲探细小器件。

新增docs/PYNQ_Z2_JTAG_FOLLOWUP_20261018_CN.md，旧报告加阶段链接，更新当前上下文和脚本README。原始证据与各执行版本冻结在board_evidence/pynq_boot_diag_20261018_174053/followup_20261018_194710，SHA256SUMS；只选小JSON摘要和文档/脚本入本地Git，不提交原始卡文件/二进制/大日志，不推送含用户指定仅本地的提交。保留原未跟踪文件，无RTL/模型/约束/BIT/HWH、综合/实现/资源时序变化，不制作工程快照或新板包。

### 2026-10-18：保守恢复 v0.2.0 未恢复启动，v0.2.1 禁用硬件入口

用户明确授权“在不损坏板子的基础上尝试恢复”。dev/filid开始跟踪文件干净、ahead6，fetch无远端新增，保留原未跟踪文件与禁止推送的本地提交。约21:17起新增隔离诊断脚本，按FPGA流程读原BOOT FSBL、核对硅版本/时钟/DDR IOB/复位/全部327字原表；精确原表silicon3.0的1308字节SHA256=4e26a443072992ffd2b2f6c573d2cb63c6a0a7e2cd81916271d56133febfdfbe，83操作（80MASKWRITE/2POLL/EXIT）。发现项目XSA有8项DDR初值与原表不同，未替换。无现有工程覆盖、RTL/模型/约束/BIT/HWH变化，无综合/实现/新资源时序结论；新增小诊断脚本保留执行版，不做大型工程快照。

假接口7类场景与寄存器/轮询地址白名单、首写读回/超时/异常收尾验证通过，SIMULATION_ONLY。初次真实请求仅写DDRC ctrl0x84，读回0，门禁停止，其余配置/RAM未执行，暂停624ms双核恢复。一次标准rst-dap未改善且后续双核显示Suspended，经后续脚本恢复；一次rst-system返回Cannot reset APU/无法暂停超时，不当作成功复位，后续仍可读取旧PC/LR。未改频率/电压/IOB/时序初值，无程序/PL下载、写SD/Flash或force/关闭保护。

用户第一次完整断电（REG和USB皆断）重上电后ctrl0x85/mode0xA1恢复normal，仍FSBL PC0x578/LR0x1021C，串口120.179s零收发。CPU0/PA32字节首轮7处非零花样读0，继发APB错误0xF0000021，原值恢复和双核运行状态未核实；后续仅DAP错误0x30000021。两次清理debug状态尝试在name过滤/不支持DPR地址空间阶段停止，未执行DP写入；没有强行底层访问。请求用户再次完整断电清除状态。

第二次完整断电上电后，原版DDR表80次写完整执行，首条ctrl0x84及末条0x85读回匹配，DCI0x2B0F与mode0x1E1低3位normal，INITIALIZATION_NORMAL；随后32字节花样仍7不匹配，恢复阶段原生debugger RPC阻塞，日志无RECOVERY_EXIT。2秒轮询限时不能抢占底层mrd/mwr调用，模拟未覆盖此限制；不冒充RAM/CPU已恢复或完整有效独立DDR测试。约21:49仅终止核实命令行属于本次的xsdb.exe PID49344，未停止其他程序/共享hw_server。用户确认主开关OFF、REG及USB断开、所有灯灭，最终保持断电，无新增上板动作。

实际恢复未成功，原版初始化可以完成不等于物理内存正常，访问故障伴随调试错误不能定位DDR/Zynq芯片；先前AP0全零仍作废。下一步应先可靠测DDR1.5V/VREF与相关PS电源/纹波，再考虑可信OCM裸机/工具路径及板级信号检测，不重刷唯一原卡/跳过自检/盲改时序。新报告docs/PYNQ_Z2_RECOVERY_ATTEMPT_20261018_CN.md、证据recovery_20261018_2117/；保留执行源executed_recover_original_ddr_v0_2_0.tcl，v0.2.1包装禁用硬件入口exit6，PC验证其不连接硬件。选择本次文档/源/小摘要及关键日志仅本地提交，不推送；全部原始证据本机SHA256SUMS校验。

### 2026-10-19：PYNQ简单复测 v0.1.0，仍停FSBL DDR检查失败

用户报告REG/USB连接、无网线、电源灯亮、中央Zynq持续发热，要求简单重测并判断项目可用性。dev/filid开始跟踪文件干净、ahead7，fetch无更新，保留原未跟踪资料及仅本地提交。Windows/XSDB2026.1识别COM14和arm_dap/xc7z020；只接收串口60.266s，RX/TX0、错误0，窗口不覆盖最初通电瞬间。

CPU0暂停19ms取PC0x578/SP0xffff5ff0/LR0x1021c/CPSR0x5f，CPU0/PA只读OCM两条指令与已确认原FSBL失败路径匹配；BOOT_MODE5、PLL_STATUS0x3f、DDRC ctrl0x85/mode0xa1。立即恢复CPU0，最终双核Running；串口关闭。未复位、访问DDR数据区、写内存/功能配置、重初始化、下载或写SD/Flash；旧恢复脚本未运行。本轮未恢复启动，最终没有要求/确认断电，不混用上轮断电状态。

仍是早期DDR检查失败，控制器normal与芯片发热不能证明内存正常或器件损坏。现有PYNQ/Linux项目不能按当前状态正常上板，修复可能性仍取决于供电/参考/DDR通路；没有独立裸机DDR/PL功能验收，不能声称绕过DDR可直接继续项目。后续优先可靠电源/瞬态及独立诊断；未改RTL/模型/约束/BIT/HWH，无综合/实现/新增资源时序结论，不做工程快照。证据board_evidence/pynq_recheck_20261019_123645/README_CN.md及限定源脚本/原始日志/SHA256SUMS，仅本地归档、不推送。

### 2026-10-20：USB供电/JTAG模式下普通Zynq开发路径 v0.1.0 通过

用户确认已接USB供电并选择JTAG，明确要求验证。dev/filid开始跟踪文件干净、ahead8，fetch无远端更新，保留所有原未跟踪资料和仅本地提交。使用FPGA skill流程，在board_evidence/pynq_jtag_path_20261020_v0_1_0隔离源码/证据，Vivado构建在builds/jtag_path_20261020；不覆盖现有工程，不做大型可再生工程快照，不推送。

BOOT_MODE实读0、PC0xffffff28、OCM_CFG0x18，DDRC ctrl0x200/mode0（未初始化）。自编译1006字节ARM裸机程序唯一LOAD位于OCM0x20000—0x203ed，结果0x21000，测试区1KiB@0x22000，栈低于0x2f000；无CRT/DDR/中断依赖。OCM两种互补地址花样共512次比对0错、和0xffffff00、完成0x444f4e45、PC到0x2000c，SCTLR0x08c50078。CPU0/PA读取结果，不依赖串口。

随后仅临时复用MIO14/15到UART0、配置UART；原PLL和分频不动，按50MHz/读回PLL及分频计算115278.89baud，PC115200。板发OCM_READY，PC经COM14发PYNQ2026八字节，板完整接收/回显并输出OCM_UART_PASS；PC收43字节/错误0，OCM状态0x600d0002、RX哈希0x535a0512。两阶段保存/逐字恢复9280字节OCM范围，恢复CPU0通用寄存器、UART/MIO；CPU1未改。最终快照CPU0回原BootROM PC/SP/LR/CPSR、双核Running、UART/MIO与初始值一致，串口关闭。

新建独立PL诊断：H16板载PHY时钟、32位计数器、R14/P14/N16/M14四用户LED、ILA；无PS7/DDR/外接执行器端口。Vivado2026.1完整综合/布局布线：1083LUT、1929FF、1BRAM tile、0DSP，125MHz约束WNS/WHS+1.878/+0.049ns、无未约束内部端点，bus skew另报通过，DRC0错误/5警告（PS7缺席及厂商debug hub详细记录，未降级告警）。JTAG仅下载该BIT，DONE内部及引脚1、CRC_ERROR0；ILA两次各1024样本，相邻值逐次+1零异常，起点差135890415，确认纯PL真实运行。未单独行为仿真，硬件采样不能冒充整机回归。SysMon当时44.0°C、VCCINT1.024/VCCAUX1.807/VCCPINT1.023/VCCPAUX1.806V，仅样本、不代替DDR/VREF/瞬态测量。

保留实际失败与修正：首个ILA构建PC综合阶段未纳入IP产物，改项目综合流程；ARM编译PowerShell逗号参数引用修正；OCM首门禁十六进制未归一化，写前停止并恢复CPU，修正后通过；首次PL已下载后redirect工具命令不支持，改属性输出并仅capture-only得到两次有效采样，无重复下载/复位。失败源和日志保留，不当硬件故障。analyze_results.py对真实OCM结果、UART双方结果、2048个ILA样本、DONE/CRC及文件哈希检查通过，verified_summary.json。

结论限定：不依赖DDR的OCM裸机、板载UART及独立PL路径PASS，可以继续有限普通Zynq开发；不是整板无损证明，也未恢复原PYNQ/Linux/完整项目。本轮没有系统复位、DDR初始化或数据访问、PLL/电压调整、SD/Flash写入，没有PS↔PL AXI/当前USB+SD启动/实物机械臂测试。供电和启动方式同时改变，不能归因于电源已修复或DDR正常。最终硬件调试连接关闭，板上保留易失PL小测试，无用户断电确认。交付本机deliverables/Gesture_PYNQ_JTAG_NoDDR_Diag_v0.1.0_20261020.zip含源码/脚本/本次ELF/BIN/BIT/LTX/证据/README/SHA256SUMS；选定源/报告/小证据本地Git，较大二进制/构建缓存不提交；未推送。


### 2026-10-20：原RoarmModeA项目JTAG接入 v0.1.0 未完成，离线定位初始化遗漏

用户授权隔离JTAG脚本，跳过DDR、保留原RTL/模型/BIT；明确相机未接、机械臂未接、D5断开/低。使用dev/filid，开始跟踪文件干净、ahead9，fetch无相关更新；不覆盖codex/mode-a-roarm-20261014原工程及原未跟踪资料。先生成114435B的本轮入口/上下文/日志轻量快照，避免再生构建目录。新增代码仅在board_evidence/original_project_jtag_20261020_v0_1_0，本轮仅本地、不推送。

绑定RoarmModeA软件0.2.3/硬件0.2.1：BIT SHA66608046cfe965c4719f0f0369c55f2a3ccc9015f36ac71ca6b02caa5723b971、HWH SHA263c64f5129ea46223753511644fd18821dad0ba09030cfd6f0137c295216c36；最终XSA内部BIT/HWH一致。没有修改或重新实现原RTL/模型/约束，沿用原实现资源时序，不新增成绩。新脚本仅白名单访问四PL页和明确PS时钟/复位寄存器，物理输出模式禁止；本地边界检查通过，不算板测。

实际过程：首次PC高地址被Tcl解析为负数，下载前门禁停止，CPU恢复；修正归一化。之后两次原BIT成功下载，XSDB先后因缺硬件地址映射和仅memmap不足而拒绝访问，均未真正发AXI读、PS/CPU恢复完成。最后复用原已下载BIT，加载同次XSA并限四PL页，0x43C30010实际读取Instruction Complete超时；后续APB AP/DAP0xF0000021，自动恢复失败、两核调试状态异常。立即停止，不清错重试、不改DDR参数/系统复位。没有ABI/模型ID读取成功、PL配置往返或S2 DRY_RUN，尚未验证PS↔PL AXI与整机。没有DDR初始化/数据区访问、PLL重配、OCM写程序、SD/Flash写入或机械臂命令。关闭本任务主机hw_server，不把关闭服务当板上恢复。

用户随后确认全部断电至灯灭并接回JTAG；之后仅离线分析，未再次连接硬件。原始失败源/日志/JSON均保留，Python和Tcl入口由HARDWARE_RETRY_BLOCKED.json锁定。离线提取同次XSA的生成初始化，确认新脚本只清FPGA_RST_CTRL低4位，保存值0x01F33F0F被保留为0x01F33F00；原ps7_post_config要求整字清零，C注释包含多组内部PS/PL AXI复位。这是本次调试脚本的确定遗漏及超时候选原因，不是已验证根因，不据此判断板卡或原RTL/DDR损坏。复位IP外部极性为低有效，时钟分频算术得到名义50/100MHz，没有依据改原RTL或PLL。

报告及下一轮待批准动作：board_evidence/original_project_jtag_20261020_v0_1_0/OFFLINE_ANALYSIS_CN.md及JSON。建议下一版本只按原生成序列完整释放PS/PL复位，先只读ABI/ID，第一笔异常立即停止；不执行整个ps7_init、不跑DRY_RUN/视觉或接线。用户明确试板前再次确认，当前未执行修正/下一次硬件动作。结果仅为原BIT下载通过、原项目验证未完成；先前OCM/UART/独立PL结论保留。本机证据ZIP为EvidenceOnly，不能当作可重跑的上板版本。


### 2026-10-20：原项目JTAG AXI/ABI/模型ID限定验证 v0.1.1 通过

用户明确授权“修正后只验证AXI和ID”，相机/机械臂断开、D5低。dev/filid开始跟踪文件干净，fetch无相关更新，保留前失败版本和全部未跟踪资料；新代码隔离board_evidence/original_project_jtag_20261020_v0_1_1，修改前轻量快照129447B。仅本地，不推送。

原RoarmModeA软件0.2.3/硬件0.2.1 BIT/HWH与最终XSA内两文件SHA一致。新调试脚本按同次XSA ps7_post_config将0xF8000240整字清0并读回，保留IO PLL，分频名义50/100MHz；只有五个PL只读地址，PL写、DDR/OCM/PLL/UART范围被门禁拒绝。输入哈希、原复位序列及本地地址边界检查PASS，不算硬件成绩。

实际仅一次下载/一次限定测试：ARM@43C30010=3101，S2@43C4000C=3202，S4@43C50010=3403，VIS@43C60008=3503，模型@43C60070=0F350087，五值全部匹配。无AXI/APB错误或重试。支持前次新脚本未完整释放内部PS/PL复位导致访问不通；不将其解释为SD/Linux或DDR故障根因已经修复。没有运行轨迹、任务、UART或相机推理，没有PL寄存器写入、DDR初始化/数据访问、PS系统复位、PLL/MIO/UART修改、SD/Flash写入。原RTL/模型/约束/BIT/HWH未改，不重做Vivado，不新增资源时序成绩。

收尾逐项核对PS分频/门控/电平转换/复位与初始保存值一致，复位恢复01F33F0F、转换使能0、SLCR锁定；CPU0 PCFFFFFF28/SPE5801000/LRFFFFFF20/CPSR200001DF与开始一致，随后恢复Running，CPU1最终Running。关闭XSDB及本任务hw_server。板上保留原易失BIT，但PS/PL接口回到原复位/隔离状态，不是原任务持续运行。

RESULT.json/actual.log及其逐字节actual_output.txt/VERIFIED_SUMMARY.json/SHA256SUMS绑定本次实测；独立日志核对五值、CPU前后和无错误标志PASS。交付deliverables/Gesture_OriginalProject_JTAG_v0.1.1_20261020_EvidenceOnly.zip，原完整板包继续保留。当前仅AXI ABI/ID范围PASS，不等于整机/视觉/实物/DDR/Linux通过；用户授权已完成，后续DRY_RUN或接相机另行明确范围。

### 2026-10-20：原项目无相机JTAG台架 v0.1.2失败保留 / 冷上电v0.1.3通过

用户要求继续验证至需OV5640接线；相机/机械臂断开、Arduino D5低。dev/filid开始跟踪文件干净、ahead11，fetch无相关更新，保留全部已有改动/未跟踪资料及仅本地提交。沿用gesture-fpga-dev/fpga-development流程，修改前轻量快照backups/original_project_jtag_20261020_pre_v0_1_2.zip；代码隔离在两个新证据目录，不改原工程。

v0.1.2从v0.1.1正确初始化代码扩展有地址/物理模式门禁的JTAG MMIO桥，计划使用原驱动和BENCH_ONLY合成配置验证S2→缓冲/后端DRY_RUN及暂停恢复；S4源码已确认低D5不允许ENABLE，即使DRY_RUN也不能绕过，因此仅计划核对显式拒绝。PC输入哈希/驱动导入/计划Move校验和Tcl门禁检查PASS。实际一次原BIT下载，完整复位0读回后首笔43C30010 Instruction Complete超时，立即停止；无PL寄存器写入、配置、轨迹或S4测试，未尝试故障后恢复或继续访问。调试主机服务关闭。离线analyze_offline.py确认初始化执行代码和CPU/PS/配置读回前缀与成功v0.1.1一致，排除本次又遗漏高位复位的说法；原因仍未定位。失败原始脚本、日志、RESULT及独立摘要保留、一次性入口锁定。

用户确认完整断电至灯灭、接回JTAG，并明确同意新一次冷上电“先ABI/模型ID，通过再DRY_RUN，异常即停”。新v0.1.3保持初始化/测试内容相同，只变证据目录/版本；一次运行通过ABI3101/3202/3403/3503及模型ID0F350087。S4 ENABLE在低D5返回ESTOP拒绝码4/CMD_REJECTED，OFF、未取得控制权、fault0。原ARM驱动完整加载台架合成配置并提交、进入DRY_RUN，D5/物理许可保持低；三段32梯形正向、32线性返回、128梯形暂停/恢复，共192样本全部被后端内部接受，六轴Q16.16终点及设备单位cmd_dev映射快照均逐整数正确。暂停在第三段第6样本，两次LAST_DELIVERED/索引/接受帧计数不变，位置[-38,29,-19,14,-10,38]与原位精确参考相同；恢复后精确到目标。三段ARM/规划器错误、late_count、反馈错误、响应超时均0；没有真实机械臂反馈，DRY_RUN计数不当作物理UART发送成功。

正常收尾ARM OFF、S2 IDLE、S4 OFF无控制权，六项PS时钟/门控/隔离/复位读回恢复，CPU0 PCFFFFFF28/SPE5801000/LRFFFFFF20/CPSR200001DF一致，恢复双核Running，退出本任务XSDB/hw_server。原BIT仍为易失配置，PS/PL回到初始隔离/复位状态。没有DDR初始化/数据区访问、PLL重配、MIO/UART更改、PS系统复位或SD/Flash写入；原RTL/模型/约束/BIT/HWH不变，不做Vivado重建或新资源时序声明。原整机22524LUT/18132FF/128.5BRAM/24DSP及WNS/WHS+0.120/+0.020ns仅沿用旧报告。

analyze_results.py独立离线核对真实日志、五ID、三段结果、映射、暂停参考和PS/CPU恢复PASS，VERIFIED_SUMMARY.json。原始jtag_actual.log保留并有逐字actual_output.txt，SHA256SUMS绑定；EvidenceOnly ZIP含失败/成功两版证据和脚本，依赖原完整RoarmModeA包，本次不造新硬件板包。选定路径本地提交，不推送。现到需断电接OV5640的阶段，下一步按原JA/JB线束和3.3V供电验证SCCB/初始化/帧流/Locator→同帧ROI→真实分类；机械臂仍不接、Arduino D5仍低。相机/真实推理、完整S4任务、真实UART/实物机械臂、Linux/DDR恢复均NOT_RUN；续测超时与冷上电成功的差异未定位，不声称无断电重配置稳定。

### 2026-10-20：原OV5640 JTAG板测 v0.2.0，采集部分通过、连续性未通过

用户确认OV5640已接好、JTAG已上电，机械臂仍未接、Arduino D5低。dev/filid开始跟踪文件干净、ahead12，fetch无相关更新，保留所有未跟踪资料和仅本地提交。读取入口/项目上下文及FPGA skill，修改前轻量Git归档backups/original_project_camera_jtag_20261020_pre_v0_2_0.zip；新增验证脚本在board_evidence/original_project_camera_jtag_20261020_v0_2_0。原RoarmModeA软件0.2.3/硬件0.2.1最终BIT/HWH/XSA哈希一致，未改原RTL/模型/约束/BIT，未综合/实现，无新资源时序成绩。

离线原驱动/输入哈希和Tcl边界检查通过。初始Python缺PIL仅在导入阶段失败、未触硬件；改用标准库封装原始PGM/PNG，不安装软件。沿用v0.1.3已通过的PS临时配置和整字复位释放，一次下载/一次实际会话，五ABI/模型ID全部正确，XCLK lock/init_done/capture_enabled为真、init_error/FIFO overflow始终假，无AXI/APB异常。原BIT无传感器芯片ID读接口，未冒称SCCB芯片ID已读回。

快照前10.172秒中result_events+10（约0.983处理事件/主机秒，不是传感器帧率），format_errors7→107。读出139号完整640×480 Gray8快照307200字节，65.266秒JTAG传输；所有权/帧号/地址尾值76800一致，原始JTAG流76800字、PGM及PNG解码像素逐字节相同，像素SHA01be7df04a8f69a88ce6d1b086b8a7ebcb6adeca2d87f4af972af702e271d74b。画面有可辨认场景及明显散点噪声，未处理图像。主动持帧期间新输入排空，owned drop增长符合设计，不计格式故障。释放后3.047秒结果120→139/+1事件、格式错误再增35，未见比139更新的已处理帧；不能称持续恢复，也不据短窗口断言永久卡死。观测model/candidate均7、detected0，无已标注手势，ROI/分类执行/正确性及真实手势识别NOT_VALIDATED。遥测99..100ms仅为本次采集到结果差，不当整机分类/动作延迟验收。

format计数在retained_gray_frame接收(x,y)与期望不一致时增加。现BIT无首错坐标/采样波形，不能区分DVP时序/线束/行条件、逻辑CDC；原最终包已记录同BIT的camera continuity NOT ACCEPTED及历史格式错误增长，不将其定位为本次脚本引入。测试结束即停止，未改工程或再试板，已向用户询问原相机/线束、线长、是否转接/面包板、3.3V来源；后续根据资料提出最小动作，按用户“有问题先问再开发”先确认。

全程只三次PL写（snapshot_enable1、word_addr0、enable0），ARM/S2/S4无写、物理UART与机械臂命令0。正常收尾后端/S4 OFF、无许可/控制权、快照释放、运动相关错误0，PS六项临时值和CPU0四寄存器逐项恢复、双核Running；关闭XSDB及本任务hw_server。没有DDR初始化/数据区访问、PLL/MIO/UART改动、PS系统复位或SD/Flash写入，原Linux/DDR问题不处理。独立analyze_results.py核对五ID、全部请求应答、像素及PS/CPU恢复通过，VERIFIED_SUMMARY明确PARTIAL_CAPTURE_VERIFIED_CONTINUITY_FAIL；原始日志/图像/结构化结果/SHA256SUMS及EvidenceOnly包仅本地，选定路径本地提交不推送。当前不能进入完整A模式/实物机械臂联测。

### 2026-10-20：原OV5640同BIT复测 v0.2.1，格式连续性恢复，完整A视觉门槛仍未通过

用户确认沿用原JA/JB、线长20cm、无面包板/转接，报告此前Phase2图像良好；完整断电后避开强光调角度、插紧连线并明确同意复测。dev/filid开始跟踪文件干净、ahead13，fetch无相关更新；按FPGA流程保留全部历史/未跟踪资料，先轻量归档入口/日志/v0.2.0至backups/original_project_camera_jtag_20261020_pre_v0_2_1.zip。新脚本/证据仅在v0.2.1隔离目录，沿用同一原BIT/HWH/XSA及已通过的PS初始化，仅增加首10秒无格式增长才扩展50秒的主机观察；离线哈希/门禁检查PASS，无原RTL/模型/约束或硬件配置改变。

实际一次会话五ID、初始化/XCLK/采集正常，无AXI/APB错误。首10秒处理事件+58、格式计数1→1（前次同长+10、格式+100）；扩展总60.015秒+352结果、格式计数始终1，init_error/FIFO overflow0。启动累计1个格式错误不写成累计零错误。完整快照359共307200字节，读取64.578秒，像素SHA06e09690f898c1ce35390965c758623b78718e6838749d6271f9222d6d6e0736，JTAG原始流/PGM/PNG逐像素相同；画面有可辨认场景及散点噪声，内容/角度变化不作为定量SNR对照。释放后3.016秒+18事件，结果到376、格式仍不增长，新帧恢复通过。检测帧出现模型代码0/2/5及NO_DETECTION7，支持真实Locator→ROI→分类执行，但无标注场景，不验收准确率/误触发/掌心窗口。

独立离线分析：60秒采样217次，源图像年龄81次>250ms、观测最大304ms；最差样本134ms采集到结果+170ms结果保持，采到的不同结果的采集到结果100..136ms、中位135ms。此为观测口径，轮询遗漏中间结果，不将其等同分类器耗时或连续最大值。原250ms初始门槛保持，未宣称完整A视觉通过。角度/接触/断电同时改变，不能单独定位此前故障原因。六项本机Phase2保留capture/FIFO/旧frontend/letterbox/初始化/XDC与当前对应文件文本相同；当前全VGA坐标检查与旧降采样计数语义不同，未核实用户旧BIT身份。

正常收尾只三次快照写、运动窗口零写，后端/S4 OFF、D5低、无控制权/错误，PS六项/CPU0四寄存器一致恢复、双核Running，退出XSDB及本任务hw_server。原RTL/模型/约束/BIT/HWH未改，无DDR初始化/数据访问、PLL/MIO/UART更改、PS系统复位或SD/Flash写入，原Linux/DDR未恢复；无新综合/实现/资源时序数字。analyze_results.py核对实测日志/像素/收尾通过，VERIFIED_SUMMARY区分采集PASS与完整A门槛未通过；SHA256SUMS和EvidenceOnly ZIP仅本地。提交选定路径、不推送；后续新开发/门槛调整/试板动作先与用户确认。

### 2026-10-20：黑背景/已知手势 JTAG v0.3.0 首笔 AXI 超时，断电后离线定位

用户选择先验证黑背景空场和已知手势，随后确认黑背景/相机固定、完整断电重上电，机械臂仍断开、Arduino D5低。dev/filid开始跟踪文件干净、ahead14，fetch无相关更新；修改前轻量归档backups/original_project_gestures_jtag_20261020_pre_v0_3_0.zip（985067字节）。新增脚本/证据仅在board_evidence/original_project_gestures_jtag_20261020_v0_3_0，保留所有既有资料及仅本地提交，不推送。

沿用原RoarmModeA软件0.2.3/硬件0.2.1最终BIT/HWH及同次XSA，哈希匹配、原工作树跟踪文件干净。JTAG初始化与v0.2.1执行代码相同；主机新增人工PHASE空场/手势确认、模型0/1/2/3/4/5至任务0/1/2/3/5/4映射、同一owned VGA抽样预览。只允许快照控制/地址写，运动页零写；不向FPGA注入类别，单次摆姿不当正式准确率。PC输入/驱动/映射/地址边界及Tcl门禁离线检查通过；这些新增视觉硬件路径全部NOT_RUN。

实际一次下载原BIT、PS配置及XSA四PL页映射后，首笔43C30010超时（Instruction Complete）；没有任何ABI/模型ID成功读回、RPC请求、空场/手势阶段或快照，PL写入0，SESSION_RESULT.phases为空。立即停止，无后续寄存器访问/重试或总线故障后恢复；Tcl日志VERIFY_EXIT2，Windows启动包装返回0不算PASS，主机记RESTORE_INCOMPLETE。只关闭本任务XSDB/hw_server。用户随后确认全部供电断开并保持断电，此后未访问硬件。

离线analyze_offline.py确认与成功v0.2.1连接至ID段代码完全一致，CPU/PS保存值逐字节相同，十次配置读回相同（HSI信息行仓库加载0秒/1秒不当根因）；FPGA_RST_CTRL整字0已读回，不能再归因旧低4位遗漏。用户报告冷上电后仍失败，因此不能宣称冷上电稳定。HWH确认GP0/SmartConnect/rst_100m均用FCLK1，复位锁定接常数1，不依赖相机PCLK/MMCM锁定；不能要求再次改线或凭此判断原RTL/板卡损坏。

离线发现可单独验证的顺序差异：当前BIT下载后才配置FCLK；本机Vivado2026.1 FSBL main.c先ps7_init（同XSA包含时钟初始化）再LoadBootImage。候选是在复位/隔离保持时，将同样50/100MHz分频和门控放在BIT下载前，后续按XSA完整释放复位，只验五ID并补有限状态记录。候选尚未开发/运行，AXI复位不依赖相机MMCM，不能将顺序差异当已证实根因。原整段ps7_init涉及DDR/PLL/MIO等，明确不执行；根因为UNRESOLVED。报告OFFLINE_ANALYSIS_CN.md、结构化XSA_CLOCK_RESET_REVIEW.json及原生成摘录（NOT_EXECUTED）可复核。

原RTL/模型/约束/BIT未变，无新综合/实现或资源时序成绩；没有DDR初始化/数据区访问、PLL/MIO/UART更改、PS系统复位、SD/Flash写入或机械臂命令。上一轮60秒相机连续性通过证据保留，源图像年龄最大304ms超过原250ms门槛仍未解决；空场/已知手势/误触发/准确率均NOT_RUN，完整A视觉和实物仍未验收。实际脚本、SESSION_RESULT、保存值、原始日志逐字actual_output.txt、独立审计、SHA256SUMS及EvidenceOnly ZIP仅本地封存/提交。当前保持断电；下一次隔离脚本修改与有限试板须按用户“有问题先问再开发”确认，不自动重连或重试。

### 2026-10-20：隔离 JTAG v0.3.1 时钟前置与五 ID 限定验证脚本就绪，板测 NOT_RUN

用户明确同意将相同FCLK50/100MHz分频设置移到BIT下载之前、补有限只读启动状态、再同一原BIT仅验四ABI和模型ID；机械臂断开/D5低，异常即停，并要求脚本就绪后再通知上电。沿用FPGA skill，dev/filid跟踪文件干净、ahead15，fetch无相关更新，保留全部原资料与仅本地提交。修改前轻量Git归档backups/original_project_jtag_20261020_pre_v0_3_1.zip（151401字节），新代码隔离在board_evidence/original_project_jtag_20261020_v0_3_1。

基于v0.1.1 ID-only台架，不复用v0.3.0手势RPC：PS写白名单/五ID集合保持相同，FCLK分频00200D00/00100D00及门控在复位/隔离保持时先配置，再下载原BIT，下载后按XSA使能LVL和整字复位0。添加三阶段只读IO PLL状态/FCLK控制和节流控制状态/复位隔离记录，及XSDB自带fpga -config-status/-state；未配置完成不读AXI。正常恢复前显式选CPU0以覆盖配置查询异常时仍停在FPGA目标的路径。总线故障后不再访问寄存器、不清错/恢复/重试。PL只五个ID可读、零写，无轨迹/任务/快照/相机遥测或物理UART动作。

原RoarmModeA软件0.2.3/硬件0.2.1 BIT/HWH/XSA及内嵌文件哈希全匹配，原工作树3a6facee跟踪文件干净。PC输入/复位序列检查、XSDB --check-only门禁通过。check_offline.py以本机Tcl8.6.15替代全部板卡命令，五种情形通过：正常五值+恢复、首笔超时后零寄存器访问/不恢复、启动未完成零AXI、配置状态查询失败恢复目标正确、首ID不匹配停止后续读并恢复。模拟脚本初次校验因Python/Tcl返回值类型转换失败，仅离线修正校验表达式后五项通过；未涉及硬件或更改启动逻辑。离线PASS只证明控制流/门禁，不证明物理时钟、AXI可达或根因已解决。

本版硬件尚未执行，正式目录无HARDWARE_RUN_STARTED/实际日志/RESULT。用户最近确认板卡全部断电；完成脚本后请求保持JTAG、原相机/黑背景原位、机械臂断开/D5低，接回既有JTAG USB/供电并告知，等待完成确认才连接。原RTL/模型/约束/BIT未改，没有DDR初始化/数据区访问、PLL/MIO/UART更改、系统复位或SD/Flash写入；沿用旧资源时序，无新实现成绩。v0.3.0首笔超时根因仍未定位，v0.2.1相机60秒连续性通过及304ms超过原250ms门槛继续保留；空场/已知手势/完整A/实物仍未验收。README/BASELINE_MANIFEST/OFFLINE_CHECKS/SHA256SUMS和PreparedScriptsOnly包仅本地，不推送；后续实测证据追加本版，不删除一次性标记复跑。

### 2026-10-20：隔离 JTAG v0.3.1 时钟前置后的五 ID 限定实测通过

用户在脚本就绪后明确确认“已上电，可以执行五个ID验证”。dev/filid在f63d623准备检查点，跟踪文件干净、ahead16，fetch无相关更新；原工作树无跟踪修改。先核对本版准备SHA/一次性标记及原BIT/HWH/XSA，再启动本任务独立隐藏hw_server，核对3121监听进程属于本次启动器，执行一次run_verify.py --run。没有重新开发原项目、运行额外离线模拟或追加板测范围。

实际日志确认FCLK0/1控制00200D00/00100D00及门控0在原BIT下载前读回；下载时复位01F33F0F/隔离0保持。下载后FPGA状态DONE/EOS/INIT_B均1、CRC错误0，配置完成；后配置整字复位0/转换F读回。ARM@43C30010=3101、S2@43C4000C=3202、S4@43C50010=3403、VIS@43C60008=3503、模型@43C60070=0F350087全部匹配，无AXI/APB异常、重试或PL写入。三阶段IO PLL控制1A008/状态3F及四个节流控制/状态不变，只记录寄存器原值，不当频率实测。

正常恢复PS分频/门控/隔离/复位六项与保存值一致，CPU0 PCFFFFFF28/SPE5801000/LRFFFFFF20/CPSR200001DF与开始一致并恢复Running，CPU1最终Running，VERIFY_EXIT0。退出XSDB后按保存启动PID只关闭本次hw_server及其启动shell，主机未残留调试服务。原易失BIT仍配置，接口回初始复位/隔离；最近用户确认已上电，未要求或推断额外断电。机械臂仍断开、D5低为用户确认条件，本次严格只读五ID，没有另读运动状态。

新增analyze_results.py仅离线核对原日志与RESULT、准备阶段冻结的实际Tcl哈希、五值、DONE/EOS/CRC、时钟前置/复位释放顺序、PS六项及CPU/双核收尾，PASS；初次解析因原CRLF行尾未规范化未匹配ID，修正分析文本换行后通过，原始日志字节不变，不涉及板上重跑。actual.log保留并有逐字节actual_output.txt，HARDWARE_RUN_STARTED一次性标记保留，SHA256SUMS和EvidenceOnly ZIP绑定实测；PreparedScriptsOnly ZIP和OFFLINE_CHECKS/BASELINE_MANIFEST保留准备阶段NOT_RUN历史。选定路径仅本地提交，不推送。

结果仅PASS_FOR_ORIGINAL_PROJECT_AXI_ABI_AND_MODEL_ID_ONLY，单次成功支持新顺序可用，不能证明此前故障根因或多次重配置稳定。原RTL/模型/约束/BIT不变，无新综合/实现/资源时序；无DDR初始化/数据区访问、PLL/MIO/UART修改、系统复位、SD/Flash写入或机械臂命令。按本轮限定未继续相机/空场/手势/DRY_RUN；v0.2.1采集连续性通过及源年龄最大304ms超过原250ms门槛继续保留，完整A视觉/实物仍未验收。下一阶段可将本版启动顺序用于隔离的原空场/手势脚本，明确下一阶段范围后再执行。

### 2026-10-20：黑背景/已知手势 v0.3.2 离线准备完成，按用户要求等待空场就绪

用户明确选择继续60秒黑背景空场及逐项1/2/3、握拳、张掌观测；在场景确认中回答“尚未准备好，先等我”。据此不启动服务或接入硬件，只完成独立的离线准备。dev/filid基于168b8c1跟踪文件干净、ahead17，fetch无相关更新，保留全部原资料与仅本地提交；修改前Git轻量归档backups/original_project_gestures_jtag_20261020_pre_v0_3_2.zip（177130字节）。

新目录board_evidence/original_project_gestures_jtag_20261020_v0_3_2复用v0.3.0隔离MMIO/人工标签/owned VGA预览，并将连接至五ID的启动执行段与v0.3.1已通过段保持文本一致（先同样FCLK配置、再原BIT下载、有限只读状态、完整释放复位）。保留同样PS写集合，PL仅快照所有权/字地址可写、运动配置全部禁止；原RTL/模型/约束/BIT不改。主机固定空场60s再五手势各8s，每段2s稳定并等待人工确认，不自动串行展示。

观测增加同一会话格式基线（不在手势间重置）、初始化/运行条件/格式增长检查，空场有效动作类误触发保存首样本即停；相干结果按帧去重，非相干行不计类别/年龄统计，需相干处理进展。记录源图像年龄最大/250ms超标次数，保留原门槛；单次摆姿仅观测不验收准确率。RPC任意错误/EOF/超时置失败标志，快照finally不再发出写；总线故障不恢复/清错/重试。预览仍从同一owned640×480帧96条源行取样，保留原行字节/帧号/哈希，不与旧推理框配对或当模型输入。

原BIT/HWH/XSA及内嵌文件哈希/原后配置序列通过；XSDB --check-only、Python类别/预览边界检查通过。PC本地Tcl五种入口（正常、首ID超时、未配置完成、状态查询错、ID不匹配）模拟通过；额外固定阶段顺序、观测异常和RPC失败标志检查通过，启动执行段与v0.3.1一致。检查全部不连接硬件，正式目录无HARDWARE_RUN_STARTED、实际日志、SESSION_RESULT或预览；板测/空场/手势/采集全部NOT_RUN。

原资源时序沿用旧实现，无新综合/实现；没有DDR初始化/数据区访问、PLL/MIO/UART改动、系统复位、SD/Flash写入或机械臂命令。README、BASELINE_MANIFEST、OFFLINE_CHECKS、SHA256SUMS与PreparedScriptsOnly包仅本地提交/保存，不推送。用户告知空场准备好前不开始，现有相机/黑背景/线束可保持原位，机械臂继续断开/D5低；此前v0.3.1一次ID通过、相机60秒连续性通过及源年龄304ms超过250ms的界限保留。

### 2026-10-20：黑背景/已知手势 v0.3.2 入口通过，空场开始前格式计数新增1次而停止

用户在准备阶段要求等待后明确“空场准备好了”。dev/filid基于4016cb9，跟踪文件干净、ahead18，fetch无相关更新；核对准备SHA/一次性标记及原工作树干净后，启动本任务独立隐藏hw_server并核对3121所属启动器，使用冻结脚本一次启动TTY会话。没有新增完整断电确认，不能推断用户未报告的操作；不自动改接线/相机参数或原工程。

沿用v0.3.1前置FCLK的同一初始化段，一次原BIT下载、四ABI3101/3202/3403/3503及模型ID0F350087全部正确，FPGA DONE/EOS/INIT_B1、CRC错误0，无AXI/APB异常。ARM status20/错误0、S2错误0、S4状态1000/fault0，后端/任务OFF、无物理许可和控制权，D5低。相机XCLK/init_done/capture_enabled真，init_error/FIFO overflow假，首个相干状态帧7/事件6、格式1，记录为会话格式基线。

发送PHASE BLANK60后，其初始状态检查发现帧67/事件65、格式2。两次相干状态FPGA now_ms1545→11678，相隔10133ms、事件+59，格式仅证实新增1次；没有逐时序列、首错坐标或新图像，无法定位发生时刻与原因，不能当持续增长证据。两个启动样本qualifiedfalse、模型分别4/0，源年龄266/246ms，不能当60秒空场误触发率/准确率或时延分布。脚本按既定新格式错误停止，未输出PHASE_START、无phase_BLANK文件、SESSION.phases为空，60秒空场/五手势/预览均NOT_RUN。

全部21个RPC仅R/CLOSE、应答匹配无错、PL写0/快照流0。普通视觉条件错误后正常CLOSE，PS六项临时配置恢复，CPU0 PCFFFFFF28/SPE5801000/LRFFFFFF20/CPSR200001DF与开始一致，双核最终Running，Tcl VERIFY_EXIT0是恢复成功而非视觉PASS，主机会话STOPPED_ERROR。关闭本任务XSDB/hw_server及启动shell，不再硬件访问、不自动重试；保留同一易失BIT但接口回初始复位/隔离，未要求额外断电。

实际bridge/host脚本与4016cb9准备提交逐字节相同，原BIT/HWH/XSA哈希匹配，原RTL/模型/约束不改；无DDR初始化/数据访问、PLL/MIO/UART修改、系统复位、SD/Flash写入或机械臂命令，无新综合/实现/资源时序。新增analyze_results.py仅离线从RPC日志解码两状态，独立核对五ID/格式1→2/无PL写/PS与CPU恢复，证据一致PASS，视觉前置条件FAIL。原jtag_actual.log保留并有逐字actual_output.txt，实际SESSION_RESULT和一次性标记封存，最终SHA256SUMS/EvidenceOnly ZIP及选定路径仅本地保存/提交，不推送；PreparedScriptsOnly包及准备阶段NOT_RUN文档字段保留历史。

本次没有新增冷上电确认，而v0.2.1的60秒连续性通过前有明确完整断电确认。这是可单独控制的候选条件，不能证明本次未断电或确定根因，也不能因此归因用户接线。按“有问题先问再开发”，当前停止，后续若安排同脚本内容的完整冷启动空场对照须用户确认；本轮不改计数基线策略或放宽格式/250ms源年龄门槛。原相机连续性通过证据保留，完整A视觉/实物仍未验收。

### 2026-10-20：v0.3.3 完整冷启动空场对照仍有格式新增，收尾复位读回超时；已断电

用户明确同意并确认已完整冷上电，保持相机线束/黑背景、机械臂断开/D5低。dev/filid起于f564e36，跟踪文件干净、ahead19，fetch无相关更新。先Git轻量归档backups/original_project_gestures_jtag_20261020_pre_v0_3_3.zip（156331字节），新增隔离目录board_evidence/original_project_gestures_jtag_20261020_v0_3_3；Tcl/主机/离线检查脚本从v0.3.2逐字节复制，仅替换版本标签，功能/阈值/基线/原BIT不变。复用父版5种PC模拟和保护检查，明确未重复执行这些测试；记录两版源hash及归一化逐字比较，原输入/类别/预览边界运行前核对通过。

启动独立隐藏hw_server、核对3121所属进程，一次原BIT下载、五ABI/模型ID通过，FPGA DONE/EOS/INIT_B1、CRC0，无进入时AXI错误。相机初始化/XCLK/采集状态通过，ARM/S4 OFF、D5低、故障0。人工PHASE BLANK60实际开始后，在8.359秒触发格式1→2，按原停止策略结束，没有更改基线忽略错误或自动重试。73条记录全部相干、49个不同结果帧（57..105）；原始模型bg41/PALM5/THREE3，有效任务输出全部0，qualified动作误触发观测0，但部分单次空场未满60秒，不能当正式误触发率/准确率通过。源年龄最大315ms、23/73条>250ms，最差119ms采集至结果+196ms结果保持；不同结果延迟118..121ms不等于分类器单独耗时。手势/预览NOT_RUN。

531个RPC仅R/CLOSE且全应答OK，无PL写/快照流。主机因格式错误普通CLOSE后，Tcl恢复先解锁SLCR并尝试把FPGA_RST_CTRL写回保存值01F33F0F，在第一笔F8000240读回处Instruction Complete超时。该写命令已返回但实际值未知，后续时钟/隔离恢复未完成，无PS_RESTORE_VERIFIED/CPU_FINAL/CPU0_RESUMED；最终targets查询显示CPU0 APB AP/DAP0xF0000021、CPU1 Running，VERIFY_EXIT3，主机RESTORE_INCOMPLETE。现有脚本恢复内部总线故障后仍进行了targets查询和disconnect，但没有进一步内存寄存器操作；不能写成完全没有调试访问。立即关闭本任务XSDB/hw_server及启动shell，没有再次接入、清错或重试。用户随后确认全部断电并保持断电，后续只有离线分析。

新增analyze_results.py离线独立核对73条与原RPC、五ID、无PL写、版本外源码一致和恢复失败，证据一致PASS不代表视觉/恢复PASS。SESSION.phases=[]是未完成阶段，实际部分记录保留phase_BLANK.jsonl；原会话JSON/脚本/原日志不改、逐字actual_output.txt加入Git/ZIP，HARDWARE_RETRY_BLOCKED与一次性标记锁定本版。生成最终SHA256SUMS和EvidenceOnly ZIP，仅本地提交/保存，不推送。

离线回读retained_gray_frame.v确认格式计数仅在ACTIVE有效token坐标不等于期望x/y时增加，像素亮度和类别不参与触发；前端SOF/x/y/Gray8经29位FIFO传入，overflow0不能排除IO控制/CDC/复位等问题。新错误首见于now_ms18203..18317相邻观测，同一结果帧105保持，但无首错坐标/波形或新图像，原因仍未定位。此次用户确认完整冷上电后仍发生，推翻冷上电足以保证不再报错的假设，不继续盲重复试板。

收尾离线参考AMD/Xilinx Zynq FPGA驱动在重配置隔离阶段用FPGA_RST_ALL_MASK0xF、完成后0，与当前结束时整字POR值不同。此为待批准候选而非根因证明，Linux/PCAP上下文不能整段复制到JTAG；下一步可仅在隔离脚本改低四位PL复位/隔离终态，其余值恢复，明确不承诺高位逐位回POR，并把恢复内部总线错统一立即停止/跳过targets查询。候选尚未开发/运行，原启动整字释放0保持。按用户“有问题先问再开发”，板卡继续断电，任何新脚本功能和试板先确认。原RTL/模型/约束/BIT未改，无新综合/实现/资源时序，无DDR初始化/数据区访问、PLL/MIO/UART修改、PS系统复位、SD/Flash写入或机械臂命令；原完整A/实物仍未验收。

### 2026-10-20：隔离 JTAG 收尾 v0.3.4 修正与六项 PC 离线验证通过，硬件入口锁定

用户明确接受新结束契约并同意“只修隔离脚本并离线验证”：结束采用低四位PL复位与隔离，不再强行恢复POR高位，其他临时值按保存恢复；恢复内部一旦总线出错立即停止并跳过后续目标查询。启动整字写0释放保持，原RTL/模型/BIT不改，板卡继续断电，本轮不试板。dev/filid基于5ac3425，跟踪文件干净、ahead20，阶段开始fetch无相关更新，保留所有既有资料和未跟踪文件。修改前Git轻量归档backups/original_project_jtag_cleanup_20261020_pre_v0_3_4.zip（170884字节）。新文件仅在board_evidence/original_project_jtag_cleanup_20261020_v0_3_4，父版实际执行脚本和失败证据保持冻结。

jtag_bridge.tcl结束时写并核对FPGA_RST_CTRL@F8000240=0x0000000F，恢复两路FCLK分频、两路门控、电平转换五项保存值，再核对CPU上下文并恢复原运行状态。新的PS_ISOLATED_SHUTDOWN_VERIFIED及PS_RESET_TERMINAL_CONTRACT明确复位高位未逐位回POR；主机成功字段改为ps_isolated_shutdown_cpu_resume，严格要求新标记，不能把旧整字恢复标记当通过。恢复dispatcher新增恢复失败状态：内部内存/总线或CPU查询异常后不再内存访问或targets查询，仅断开连接并保留失败；正常路径仍检查最终目标。Python与Tcl在连接前检查HARDWARE_RUN_BLOCKED.json，本版不提供直接上板入口。

check_cleanup.py仅使用Python标准库tkinter/Tcl8.6.15，mock_xsdb.tcl替代所有硬件命令；六种情形实际运行通过：正常收尾、复位写失败、复位首次读回失败、隔离读回失败、时钟恢复写失败、CPU寄存器查询失败。正常模拟终态复位0xF、其他五值恢复、CPU上下文及运行恢复；五个故障情形退出3，无RESTORE_COMPLETE/CPU0_RESUMED/TARGETS_FINAL，故障后内存访问/目标查询均0，仅DISCONNECT。首次测试因Python/Tcl模拟日志值的类型展开失败，仅修正测试序列化后重跑六项通过，待测收尾逻辑不因此改变。

同时验证正式目录Python/Tcl入口均在连接和一次性标记前阻止，主机接受新契约且拒绝旧标记；原BIT/HWH/XSA及内嵌输入哈希通过，原工作树3a6facee跟踪文件干净。连接到五ID的启动执行段文本和六个视觉观测函数语法树与v0.3.3相同，启动前置FCLK/下载同一原BIT/整字复位0、格式基线/250ms门槛/阶段顺序/快照方法/写白名单均保持。正式目录没有HARDWARE_RUN_STARTED、实际硬件日志或会话结果；没有启动XSDB/hw_server或访问板卡，硬件全部NOT_RUN。

此结果仅证明模拟控制流和门禁，不证明PL物理复位/隔离行为、收尾超时根因或修复有效。官方Linux/PCAP驱动0xF策略只作候选依据，不作为JTAG实测。原相机坐标格式错误、空场原始分类非背景输出和源年龄最大315ms/250ms超标仍未解决，60秒空场/已知手势/实物未验收。用户最新确认全部断电并保持断电，保持原相机/线束原位、机械臂断开/D5低，不要求新接线或上电；任何下一次板测须另行明确范围，宜先限定新收尾契约。

原RTL/模型/约束/BIT/HWH未改，无综合/实现或新资源时序；旧整机22524LUT/18132FF/128.5BRAM/24DSP、WNS/WHS+0.120/+0.020ns仅沿用。没有DDR初始化/数据区访问、PLL/MIO/UART修改、PS系统复位、SD/Flash写入或机械臂命令。README/BASELINE_MANIFEST/OFFLINE_CHECKS/源码/SHA256SUMS和Gesture_OriginalProject_JTAG_Cleanup_v0.3.4_20261020_OfflineOnly.zip仅本地保存/提交，不推送；包不重复包含原大体积BIT，离线复现依赖原包和父版源码对照。

### 2026-10-20：v0.3.5 原 BIT 五 ID 与新收尾限定板测准备完成，等待上电

用户在v0.3.4离线完成后明确“继续进行板测”，并确认机械臂断开、Arduino D5断开或低电平、相机/黑背景原位、板卡仍完整断电。按上一阶段约定，先限定验证同一原BIT五ID和新收尾契约，不开始相机遥测/空场/手势/DRY_RUN或实物。dev/filid起于fbfff57，跟踪文件干净、ahead21，开始fetch无相关更新；修改前轻量Git归档backups/original_project_jtag_cleanup_20261020_pre_v0_3_5.zip（178103字节）。保留所有其他资料及未跟踪文件，仅本地提交、不推送。

新增隔离目录board_evidence/original_project_jtag_cleanup_20261020_v0_3_5，五ID流程沿用v0.3.1，收尾与故障dispatcher逐字保持v0.3.4，后者离线版与HARDWARE_RUN_BLOCKED保持冻结。前置相同FCLK→原BIT→整字复位0释放不变，PL白名单仅四ABI和模型ID五个地址，只读、零写；结束写0xF/恢复其他五项临时值，明确POR高位不恢复，核对CPU0上下文和双核Running。主机严格要求新成功标记和实际读回，Windows包装0不当通过，保存实际源/日志/RESULT并独立审计；一次性标记禁止复跑。

本机PC Tcl8.6.15替代全部硬件命令，四项模拟通过：正常五值+新收尾、首ID超时、首ID不匹配、收尾首次复位读回失败；正常仅五PL读、零写，故障后内存/目标访问0。启动与v0.3.1、收尾及dispatcher与v0.3.4文本完全相同；继承原六种收尾模拟证据，不重复宣称物理行为。首次check-only因模拟exit只记录但未中断而落入参数检查，仅修正测试替身，重跑四项及门禁通过，实际Tcl未因此修改。输入BIT/HWH/XSA及内嵌哈希/原后配置序列通过，Python语法检查通过；原工作树3a6facee跟踪文件干净。

脚本就绪后通知用户接回既有JTAG/供电并确认，上电前不启动服务或访问硬件。本准备阶段硬件全部NOT_RUN，无HARDWARE_RUN_STARTED/actual.log/RESULT；若总线或恢复异常立即停止并通知完整断电，不清错/不重试。原RTL/模型/约束/BIT不改，无综合/实现或新资源时序；旧22524LUT/18132FF/128.5BRAM/24DSP、WNS/WHS+0.120/+0.020ns仅沿用。无DDR初始化/数据访问、PLL/MIO/UART修改、PS系统复位、SD/Flash写入或机械臂命令。原相机格式错误、315ms超过250ms和完整空场/手势/实物未验收状态保持。准备包与SHA仅本地封存；实际板测证据待确认后追加本目录，不删除旧标记复跑。

### 2026-10-21：v0.3.5 五 ID 和新隔离收尾一次实板通过

用户在脚本封存后明确确认“已上电，可以执行限定验证”。dev/filid基于315cc4f准备检查点、跟踪文件干净，ahead22，准备期间fetch无相关更新；准备包19292字节/SHA ec5cd4923d275e20745a84a809988c1a950bc3d2a4ced297ee6e4bc82ee46942保留。五ID/新收尾范围不扩展，不再次开发原项目；执行前核对准备SHA及Git保存字节、原工作树无跟踪修改、一次性标记不存在。版本目录20261020沿用，实际开始标记2026-10-21T00:02:14.682941+08:00、日志结束00:02:20.891926，SESSION_TIMING记录真实Asia/Shanghai时间；RESULT.date是执行脚本固定包日期，原结果不改。

启动本任务独立隐藏hw_server，launcher34644/server19876，3121监听所有者和父PID核对通过。一次run_verify.py --run下载同一原RoarmModeA软件0.2.3/硬件0.2.1 BIT，FCLK前置/完整复位0启动保持；FPGA DONE/EOS/INIT_B=1、CRC=0。ARM43C30010=3101、S2 43C4000C=3202、S4 43C50010=3403、VIS43C60008=3503、模型43C60070=0F350087全部匹配，无AXI/APB或其他异常。PL严格五个ID只读、零写，无相机遥测、空场、手势、快照、DRY_RUN、物理UART或机械臂动作；D5低来自本轮用户确认，无额外读取许可状态。

新收尾实板读回FPGA_RST_CTRL=0x0000000F，其他两路FCLK分频/两路门控/电平转换五项与保存值一致，隔离保存值0；不再写回01F33F0F或承诺POR高位恢复。CPU0 PCFFFFFF28/SPE5801000/LRFFFFFF20/CPSR200001DF前后一致且恢复Running，双核最终Running。PS_ISOLATED_SHUTDOWN_VERIFIED、PS_RESET_TERMINAL_CONTRACT、RESTORE_COMPLETE、VERIFY_EXIT0齐全，主机result=PASS_FIVE_IDS_AND_REVISED_ISOLATED_SHUTDOWN_ONLY。单次成功支持新策略本次可用，不证明旧超时根因或反复加载可靠性，未追加重试。

关闭本任务hw_server及启动shell，确认3121无监听/无本次子进程；DEBUG_SERVICE_RECORD保存归属与关闭状态，此后无硬件访问。最近用户确认上电，正常收尾后不要求额外断电/接线；同一易失BIT仍配置，PL低四位复位、隔离恢复保存值0、其他临时值/CPU恢复，高位不等于POR。机械臂断开/D5低保持。analyze_results.py独立核对原日志、五ID、十八次配置读回、新终态、CPU、配置状态、输入/实际源哈希通过；verify_ids.tcl/run_verify.py与315cc4f逐字相同。actual.log原字节保留，actual_output.txt逐字副本，RESULT/保存值/一次性标记/时间记录/独立审计/SHA及EvidenceOnly包只本地封存/提交，不推送。

原RTL/模型/约束/BIT/HWH未改，原工作树跟踪文件仍干净，无新综合/实现/资源时序。无DDR初始化/数据区访问、PLL/MIO/UART修改、PS系统复位、SD/Flash写入或机械臂命令。相机格式错误、源年龄315ms超过250ms、完整60秒空场/已知手势/实物未验收状态保持；本轮入口与收尾通过不能扩写为视觉或完整A通过。下一阶段需沿用此次新收尾，在明确视觉观测范围后继续，不删除本版一次性标记复跑。

### 2026-10-21：v0.3.6 黑背景与已知手势观测准备完成，沿用实板通过收尾

用户已选择继续60秒黑背景空场和逐项手势观测，又确认空场无手/物体、JTAG上电、机械臂断开/D5低、相机/线束不变。dev/filid起于610c7fc，跟踪文件干净、ahead23，开始fetch无相关更新。修改前轻量Git归档backups/original_project_gestures_jtag_20261021_pre_v0_3_6.zip（227846字节）。新隔离目录board_evidence/original_project_gestures_jtag_20261021_v0_3_6，保留全部旧实测资料、未跟踪文件，仅本地提交不推送。

运行Tcl/主机从v0.3.4复制，仅版本标签改为0.3.6，不复制原离线阻止标记，原离线目录保持冻结。启动、restore及故障dispatcher与v0.3.5一次实板通过代码相同；六个phase/preview/read_state/observation_guard/validate_phase_command/inert函数与v0.3.3语法树一致。会话格式基线不重置、新格式/初始化/AXI异常即停、快照写白名单/运动页禁写、源年龄250ms门槛、BLANK60及五手势8秒逐项人工确认均保持。未向FPGA注入分类或启用物理执行。

check_preflight.py实际核对原BIT/HWH/XSA及内嵌输入哈希、原工作树3a6facee跟踪文件干净、源码仅标签变化及与实板版本启动/收尾相同；本机Tcl8.6.15只加载本地命令替身运行地址门禁通过，无硬件命令。verify_gestures.py无--run的类别/预览边界检查通过。已有相同收尾六种PC模拟及原观测保护证据复用、不重复运行或冒充新板测。本准备阶段硬件NOT_RUN，无一次性标记/实际日志/会话结果。

用户已明确空场准备好，准备封存后可接入一次，桥接就绪即发送PHASE BLANK60，避免基线后再长时间等待开始；通过后每个手势仍提示并等待人工确认。新格式/初始化/AXI或空场有效动作异常立即停止，普通视觉错使用新收尾，总线或恢复内部错停止后续内存/目标查询，必要时通知用户断电，不自动重试。本版尚未修复格式错误或源年龄315ms超过250ms，不宣称完整A/实物通过。

原RTL/模型/约束/BIT/HWH不改，无新综合/实现/资源时序，旧22524LUT/18132FF/128.5BRAM/24DSP及WNS/WHS+0.120/+0.020ns沿用。无DDR初始化/数据访问、PLL/MIO/UART修改、PS系统复位、SD/Flash写入或机械臂命令。README/BASELINE_MANIFEST/OFFLINE_CHECKS/源码/SHA及准备包仅本地；后续实际结果追加本目录，原日志逐字副本入Git/证据包，保留失败部分阶段数据。

### 2026-10-21：v0.3.6 空场初始检查格式1→11停止，新收尾实际通过

用户确认空场就绪/JTAG上电、机械臂断开/D5低、原接线不变后，基于75f21a9准备检查点一次执行。dev/filid跟踪文件干净、ahead24，准备期fetch无相关更新；准备包19666字节/SHA 13a03cdcf936178294f4099bb389bc06a1f57cc634a24051061f843a51b83df0保留。执行前准备源/清单/Git字节核对通过，未重复已有模拟。启动独立隐藏hw_server launcher6184/server40452，3121监听归属核对，通过冻结verify_gestures.py --run一次接入。

原BIT下载、四ABI3101/3202/3403/3503和模型0F350087、DONE/EOS/INIT_B1/CRC0均通过，无AXI/APB错误。ARM状态20/错误0、S2错误0、S4状态1000/fault0，后端与任务OFF/D5低。相机初始化/XCLK/capture有效，首个相干状态now2032ms、帧10/事件9、格式1记为会话基线；桥接就绪后发送PHASE BLANK60，初始检查now11656ms、帧70/事件60、格式11，立即停止。两状态跨9624ms、格式+10/帧+60/事件+51，不能恢复每次错误时间；未进入2秒稳定、PHASE_START或正式循环，无phase JSONL/预览，60秒空场/所有手势NOT_RUN。

两个状态模型/任务代码均7（无检测），未观察到动作类1..5，不能验收空场误触发率或准确率。无init_error/FIFO overflow；两状态源年龄155/309ms，最后309=99ms采集到结果+210ms保持，原250ms门槛仍不通过，仅两状态不能形成分布。21RPC仅R/CLOSE且全OK，PL写0/快照流0，没有主机配置或快照操作。原格式计数唯一增长路径仍为ACTIVE token的实际坐标不等于期望坐标；原BIT没有首错x/y/SOF或波形，不据此归因光照、线束或模型。当前沿用v0.3.5正常收尾后上电状态、初始复位已为0xF；v0.3.3完整冷启动也报错，不能把反复冷启动当修复。

普通视觉条件错误后21 CLOSE正常，新收尾实板复位0xF读回、其他五值恢复、CPU0 PC/SP/LR/CPSR一致且恢复运行、双核最终Running，完整新标记/RESTORE_COMPLETE/VERIFY_EXIT0。主机STOPPED_ERROR，Windows TTY退出1反映视觉失败，Tcl0反映收尾通过，不混淆。只关闭本任务hw_server及启动shell，确认3121无监听/无所属子进程，此后没有硬件访问或重试。最近用户确认板卡仍上电，新终态PL低四位复位/隔离保存值0、CPU恢复，无需因恢复失败额外断电，机械臂断开/D5低、线束保持。

analyze_results.py离线独立核对原日志、两个状态、SESSION错误字典、五ID/21RPC无写/新收尾/CPU/服务关闭及75f21a9实际源字节，证据一致PASS不代表视觉PASS。保留原jtag_actual.log/SESSION/保存值/一次性标记，逐字actual_output.txt入Git/ZIP；追加HARDWARE_RUN_BLOCKED禁止本版两层硬件入口。README、离线分析、独立审计、时间/服务记录、SHA与EvidenceOnly包仅本地封存/提交、不推送，原RTL/模型/约束/BIT/HWH不改，无新综合/实现/资源时序。无DDR初始化/数据访问、PLL/MIO/UART修改、PS系统复位、SD/Flash写入或机械臂命令。

下一阶段候选为仅离线审查capture→FIFO/token→retained坐标/握手合同并用现有仿真寻找定向复现条件，缺首错证据时再申请必要的诊断镜像；目前尚未开发该阶段仿真、修改RTL或构建新BIT。按“有问题先问再开发”先封存并确认，不自动重复同条件板测或放宽格式/250ms门槛，完整A/手势/实物仍未验收。

### 2026-10-21：v0.4.0 相机坐标链离线审查与定向仿真完成，尚未确认实物根因

用户明确同意仅capture→FIFO/token→retained离线审查与定向仿真，原RTL/模型/BIT保持、不再试板；RTL修复或诊断BIT先给具体方案确认。dev/filid起于768e4bd，跟踪文件干净、ahead25，开始fetch无相关更新；轻量Git归档backups/original_project_camera_coordinate_offline_20261021_pre_v0_4_0.zip（169960字节）。新目录board_evidence/original_project_camera_coordinate_offline_20261021_v0_4_0，编译缓存隔离到runs/camera_coord_20261021_v0_4_0及_r1，保留所有旧证据及未跟踪资料，仅本地提交、不推送。

只读审查原四模块、采集使能控制/复位连线/AXI映射及既有TB：原retained TB直接输入token，capture TB只几个字节，缺完整VGA经四模块链的覆盖。本轮四RTL逐字复制到input_rtl，不改原或副本功能；新增tb_camera_coordinate_chain，以独立capture像素/坐标黄金对照、FIFO写侧到所有消费token逐个scoreboard、反压保持和格式错/发布恢复检查，刺激只从DVP引脚或capture_enable输入，不force内部信号。不加载CNN/运动或硬件库。

Vivado Simulator2026.1（1ps精度）实际编译/elaborate并运行7种情形：约48MHz PCLK/100MHz系统时钟，相位3.700/0.125/8.900ns，三组合法完整VGA各3帧，共9帧/2764800 token，格式/溢出均0，顺序/数据/坐标/反压检查通过，发布3/2/2帧；后两案分别主动保留并排空1帧。每案最大未消费token积压125，padding反压覆盖。四个明确注入对照各产生一次格式错、overflow0并在下一合法帧恢复发布：HREF缺口期望100/8实际0/9 SOF0；VSYNC脉冲期望100/8实际0/0 SOF1；长行期望0/9实际640/8 SOF0；行中途使能期望540/0实际0/1 SOF0。全7案累计5217181个消费token。另原tb_retained_frame两帧各307200源字节/4096letterbox字逐项对照及保留/丢弃/释放/身份/畸形/复位通过。

首次XSim启动因Windows .bat对未引号CASE=0拆分，在仿真开始前报参数错误；依照仓库工具包装规则对全部参数加引号并拒绝cmd元字符后，改用全新_r1目录完成全部运行，未改DUT/激励，原results/失败输出保留。实际TB的COORD_MISMATCH字段time_ns由%t按1ps精度输出，名称误标；保留实际源码/日志，audit_results归一化成simulation_time_ps/ns，不影响坐标/计数/判据，未因此重复仿真。命令/工具返回值/耗时/输出SHA、原输入/原TB哈希及实际TB/驱动哈希均可审计。独立audit_results.py核对日志、指标、原四源码一致及原工作树干净，PASS，不能当板测通过。

审查确认capture_enable=camera_init_done&&!fatal_error，正常分类/帧释放不周期关闭采集；中途使能可以复现启动不完整帧，是基线1的候选解释，不能凭它解释基线后10次增长。旧letterbox格式计数不等于当前连续VGA坐标合同，用户旧Phase2图像经验保留，未做新旧并行回放。当前合法数字输入未复现内部丢token，四种注入仅证明输入条件类别可以产生overflow0的格式错，不证明板上存在某种毛刺；没有实物首错坐标/波形或电气/亚稳态/门级模型，实物根因仍UNRESOLVED，不猜测性修改采样边沿/FIFO/丢弃策略。

DIAGNOSTIC_PROPOSAL_CN.md仅提出待批准最小方案：在隔离副本加可在相机就绪后重新布防的首错快照，含布防时计数、实际/期望坐标、SOF/Gray、错误计数/FPGA时间/采集尝试帧号，AXI扩展候选0x088..0x0A8已核对原映射空闲。只锁复位首错会卡在启动基线1，必须布防才能定位后续增长；不清原错误计数/不改接受发布或250ms门槛。先验证布防/同拍优先级/原子读和既有接口，再完整实现核对资源时序和同次BIT/HWH/XSA；诊断构建/板测均尚未授权或执行，构建后另行确认有限板测。

本轮没有XSDB/hw_server/板卡访问、原RTL/模型/BIT/HWH/XSA/约束/PLL/DDR/SD/UART改动或机械臂命令，原工作树3a6facee跟踪文件干净、原BIT/HWH哈希匹配，无新综合/实现/资源时序；旧22524LUT/18132FF/128.5BRAM/24DSP、WNS/WHS+0.120/+0.020ns只沿用。当前不要求用户接线/供电操作，上次v0.3.6正常收尾/服务关闭状态保留。源码/激励/实际输出/独立审计/说明/候选方案/SHA及OfflineOnly ZIP仅本地封存/提交，build缓存不打包。格式实物根因、源年龄超250ms、空场/手势/完整A/实物仍未验收。

### 2026-10-21：v0.5.0 可重布防首错诊断候选完成，不上板

用户明确批准在隔离副本增加相机就绪后可重布防的首错快照与AXI扩展，只仿真、完整综合实现并交付候选，不自动上板；原工程/原BIT/模型/原格式计数和停止门槛保留，所有资料和提交仅本地不推送。dev/filid起于f3c1525（ahead26），阶段开始/结束fetch没有当前分支新远端提交，保留无关未跟踪资料；backup backups/original_project_camera_diag_20261021_pre_v0_5_0.zip185116B。create_worktree创建并附着[local-user-directory]/.codex/worktrees/camera-coordinate-diag/Gesture，codex/camera-coordinate-diag-20261021，从原3a6facee25d6fa3ba8056abcd883742becf3e100创建；冻结Rain模型1094非pycache文件/60125733字节逐hash复制，不训练、不改权重。

仅retained/front-end/vision/top/adapter五个原RTL文件改变：同100MHz域独立首错快照，布防保存原format计数，首次ACTIVE有效token坐标失配原子锁存actual/expectedXY、SOF/Gray、触发后原计数、FPGA时间和采集尝试帧；同拍arm+错错误优先，后错不覆盖，重布防使旧payload无效，reset清诊断，32位回绕明确。原writer FSM/内存/打包/读口源码块文本相同，并逐周期对照冻结基线；原capture/FIFO和帧接受发布/全局格式计数/模型/约束/PS配置/UART/运动逻辑不变。DIA1@VIS+0x088=44494131，0x08C读armed/valid且唯一完整32位写1布防，0x090..0x0A8只读payload；旧3503/CAM1/模型身份保留，非法值/WSTRB/对齐/RO写SLVERR、参数默认关闭，不触碰运动配置。

Vivado Simulator2026.1四TB通过：新诊断单测（原writer逐周期控制/写口基线对照、未布防启动错/首错/冻结/重布防/同拍/回绕/reset）、真实retained+AXI集成（AW/W两顺序、非法写、R/B背压、arm唯一性/旧ABI/关闭扩展）、原snapshot和retained完整VGA。完整RoArm top static elaborate通过。7种capture→FIFO→retained全VGA链5217181消费token：合法三条件共9帧/2764800token，fmt/overflow0；四注入各一次fmt/overflow0/下一合法帧恢复，首错快照签名符合，原published/format/overflow/injected/tokens/drop指标与v0.4.0相同。仿真不是实物毛刺/光照根因证据。解码器只解码保存JSON，无硬件API；4单测、4实际XSim快照集成和JSON CLI通过；新便携重放助手只语法/CLI检查，未因此重复整套仿真。

冻结RTL提交c151b0ae35f0188433c3774c3c24523a835b1121，以原create/build脚本在runs/camera_diag_hw_20261021_v0_5_0完整构建：create54.781s、build987.625s，均exit0；模型1093清单文件/12样本/384逐层和独立整数参考检查PASS。最终整机22555LUT/18341FF/128.5BRAM/24DSP，相比原22524/18132/128.5/24为+31LUT/+209FF，无新BRAM/DSP。WNS/WHS+0.016/+0.007ns，TNS/THS0，余量薄，不放宽原约束。全部40633可路由网络完成/错误0；CDC原三行全部Safe，Unsafe/Unknown/NoASYNC_REG0，no_clock/内部未约束端点0。DRC0错误32警告，比原31多bbox/mul_result_reg的DPOP-1输出PREG=0建议，bbox源码未变且DSP总24，其他警告描述保留；最终methodology18项TIMING-18与原版相同。原DVP2..8ns临时外部预算/3输入与10输出I/O例外未实测，不声称物理相机时序已验证。

离线打开同次最终实现网表，179位诊断状态+1布防FF均保留且clk_fpga_1。宽泛diag名字匹配另含原bbox几何diag_sq64位，在审计据未变源码明确剔除；没有为此改RTL/重建。XSA包含顶层与SmartConnect子HWH，按顶层basename核对嵌入和外部BIT/HWH逐字相同。PS初始化非注释内容、HWH内存窗口、冻结模型/原约束与原版一致，原工作树跟踪干净/原BIT哈希保持。新BIT4045780B/SHA8ff65c07b007e36f8fc78342ba8ea65df3d923dc88a42eb72b5c76be7a27ddf9，HWH239817B/SHAF35887AD0CEB81C1D6151569406BAAEAB8EFA816C7840FEDE523CFC45E04DFD3，XSA2454331B/SHA76F4FCEBF79E8689C25AAFB16E6377465CED11345149B502E23E8CA2E071D3A3。交付源码27507790492db7b49e15443a8364e7abf6d20609只补文档/离线解码器，与构建RTL/约束无差异，跟踪工作区干净。

主证据board_evidence/original_project_camera_diag_20261021_v0_5_0含实际命令/退出值/输出hash、仿真源码hash、原始stdout、最终报告/模型审计、独立产物审计和未来有限板测草案。候选deliverables/Gesture_CameraCoordinateDiag_v0.5.0_20261021_Candidate.zip，30514759B/SHA1df43f5f84a47581ddb3841632410c6f2a59b657f692e6064699ad3f9e29418a，1241文件；包含完整必要RTL/原构建脚本/约束/初始化/冻结模型/测试/解码器、同次BIT/HWH/XSA、README和SHA256SUMS，ZIP CRC及所有文件SHA通过。首次封包Path.with_suffix把带点版本名截短且内部WORK_PLAN更新遇默认GBK解码，RTL/模型/构建产物不受影响；保留PreFinalizationCheck目录和ZIP，改为明确拼接完整ZIP名及UTF8后重新封包验证，不覆盖失败证据。庞大Vivado/XSim缓存及大交付包不入Git；原始.log/.jou本地保留，实际stdout.txt逐字入证据。

本轮无XSDB/hw_server/JTAG下载/硬件访问/DDR或PLL初始化/SD写入/机械臂命令，HARDWARE_NOT_RUN_NOT_AUTHORIZED。上次硬件正常收尾/服务关闭状态保留，不要求接线或供电操作。物理格式增长根因、304/309ms超过250ms源年龄、空场/已知手势/完整A实物仍未验收。候选只补取证，后续须另行明确确认后才按有限五ID/DIA1→相机就绪/原基线→布防→首错或有限超时→冻结快照→新收尾，不清原计数/不重设基线/不放宽停止门槛，不自动上板。

### 2026-10-21：v0.5.1 首次诊断候选实板取证成功，视觉格式失败后正常收尾

用户请求“是否可以进行上板验证”，随后明确确认原连接/空黑背景/机械臂断开/D5低、已完整冷启动并JTAG上电。按此次请求与确认执行一次有限诊断，不再重复确认相同条件。dev/filid起于ea6e37a，阶段开始fetch无相关更新，原跟踪工作区干净/无关未跟踪资料保留；备份backups/original_project_camera_diag_jtag_20261021_pre_v0_5_1.zip。新目录board_evidence/original_project_camera_diag_jtag_20261021_v0_5_1，执行源检查点070a810，仅脚本/板证据变化，不改v0.5.0RTL/模型/约束/BIT，仍22555LUT/18341FF/128.5BRAM/24DSP、WNS/WHS+0.016/+0.007ns，不重跑综合实现。

隔离Tcl复用v0.3.6实际启动配置（日志标签换候选）、已通过新收尾和总线故障dispatcher；主机复用原telemetry/inert和transport reader/wait/call/close AST。读权限收窄到ID/遥测/DIA1，唯一新PL写为0x43C6008C完整值1；Python/Tcl双层限一次布防，移除快照流和ownership/address/运动/任务写。新源PC模拟7Tcl场景（正常/首ID/诊断读/arm写/收尾读故障/第二arm拒绝/仅检查）及6host场景（立即/轮询捕获、布防前窗口增长、有限无错、AXI/相机错误）通过，故障后额外内存与target查询0。候选BIT/HWH/XSA及decoder hash绑定，输入/源哈希预检通过；无新硬件初始化方案。主机观测上限从arm请求计时，单笔在途JTAG访问按既有有限超时完成，外部180秒看门狗未触发。

Asia/Shanghai约01:44:41启动自有隐藏hw_server，核对3121监听PID12120为本次launcher6788后代；执行host45036，单次下载v0.5.0 BIT8ff65c07b007e36f8fc78342ba8ea65df3d923dc88a42eb72b5c76be7a27ddf9及同次XSA。FPGA配置DONE/EOS/INIT_B1、CRC0，FCLK预先50/100MHz、完整复位0释放；原五ID3101/3202/3403/3503/0F350087及CAM1/DIA1均匹配，无AXI错误。ARM状态0x20/S4状态0x1000、后端/任务OFF、D5低/无许可及错误；机械臂断开，无机械臂UART或运动命令。

相机就绪、XCLK/采集正常、init_error/FIFO overflow0，初始相干frame14/events11/model7/task7/qualified false，原format基线5、now2727ms；源acq2303ms/result2403ms，处理latency100ms、源年龄424ms>250ms，失败保留，只一个完整结果样本，不作最大值/分布或空场误触发统计。立即只写一次0x43C6008C=1，arm_count5与原基线相同，armed1/valid0。15条短遥测FPGA2753→4459ms，前14条format5、最后6，无init_error/overflow；布防后约1.734秒停止。首错快照armed0/valid1，actual0x01200280=(640,288)、expected0x01210000=(0,289)，metaAF/SOF0/Gray175，event_count6与arm5模差1、event_time4396ms、acquisition attempt27。事件位于最后两遥测4345/4459ms之间。基线之前五次没有坐标快照，采集尝试27不是结果frame14。增量样本后只做冻结payload读和CLOSE；没有继续观测、重新布防、图像快照、手势/60秒空场或动作。

45RPC全部OK，唯一PL写为一次DIA1 arm；主机CAPTURED_FIRST_COORD_ERROR_VISUAL_FAILED、退出0仅代表取证/收尾完成，不能当视觉通过。新收尾实板复位0xF、其他五值保存恢复、CPU0 pc/sp/lr/cpsr一致并恢复运行、双核最终Running、VERIFY_EXIT0；01:45:00本次hw_server/启动shell退出，3121无监听，此后无硬件访问。当前无需因恢复失败再次断电/重新接线。增加HARDWARE_RUN_BLOCKED，保留SERVICE/HARDWARE一次性标记、原.log/saved状态等，不自动重复本目录。

analyze_results.py独立核对原始日志/全部RPC/唯一写、输入/执行源hash、寄存器与解码、计数关系与15遥测/事件时间、首错后仅dump+CLOSE、PS/CPU/服务收尾和原工程跟踪干净，PASS。解析首次受CRLF锚点影响，改为只对解析视图分行归一化，未改原始日志或硬件驱动；actual_output.txt与原.log逐字一致。原工程3a6facee及原模型/BIT保持，新候选保持同次输入hash，无DDR/PLL/MIO/SD初始化或写入，资料/提交仅本地，不推送。

离线只读判读：retained在应换下一行x0时收到旧行x640，呈现行尾多Y token形态，与原长行注入同类；尚无PCLK/HREF有效字节长度或物理波形，不能断定相机实际输出641像素、光照/线缆/传感器或RTL边界为根因，也不静默裁掉越界token、重设格式基线或放宽250ms门槛。按“有问题先问再开发”，下步候选仅离线核对初始化/有效字节数/Y相位/HREF边界并比较行末+1/+2有效字节的本次同类签名；尚未开发或运行，待明确确认，不自动修RTL或试板。

本轮EvidenceOnly包Gesture_CameraCoordinateDiag_v0.5.1_20261021_EvidenceOnly.zip46552B，SHA256 7ad892143e4fba496f20f1a2afc9ab4c0f9dc145efe845469e27ecb5f4ac2795，31文件CRC及逐文件SHA通过。只含本次脚本/原始输出/寄存器/解码/审计/停止标记，硬件依赖原v0.5.0 Candidate包与其SHA，未覆盖候选。原始.log继续本地保留，actual_output.txt逐字相同；本次版本封存不自动再次启动。

Git封存前发现XSDB自动生成的.Xil/roarm_closed_loop.bda缓存进入预检查包，保留EvidenceOnly_PreIndexCheck目录/ZIP，明确从最终包/SHA/选择暂存中排除.Xil与pycache，缓存本地保留不删除；最终包46552B、31文件、SHA7ad892143e4fba496f20f1a2afc9ab4c0f9dc145efe845469e27ecb5f4ac2795，CRC/逐文件hash重新通过。没有改变任何已执行板测脚本/数据/候选硬件，不追加硬件访问。

### 2026-10-21：v0.5.2 行末多1/2有效字节离线复现完成，物理根因仍未确定

用户明确同意只做VGA/YUV422初始化、Y字节相位/HREF行尾核对及+1/+2有效字节两案复现，原RTL/模型/BIT/原门槛保持、不再试板。dev/filid起于7f75ffb，开始fetch无当前分支远端新增，跟踪文件干净/无关未跟踪资料保留；轻量归档backups/original_project_camera_rowbytes_20261021_pre_v0_5_2.zip（14786811B），新目录board_evidence/original_project_camera_rowbytes_offline_20261021_v0_5_2，可再生缓存仅runs/camera_rowbytes_20261021_v0_5_2，所有资料/提交仅本地、不推送。

从诊断源码工作树2750779逐字复制capture/cdc_fifo/retained/frontend四模块到input_rtl，源hash保持并与既有实板候选绑定。TB复用已通过完整链，只把两种刺激限定在首帧第288行末尾多1或2个有效字节，其他959行均1280；增加独立引脚字节长度oracle和全部Y数据/坐标oracle，复用所有FIFO消费token顺序/反压、首错冻结与下一帧恢复断言，无force/release或DUT编辑，不加载CNN/模型/任务/运动。Vivado Simulator2026.1实际compile/elaborate/two run均exit0，100MHz系统/约48MHz PCLK、相位3700ps；每案960输入行、614401token，共1228802token/1920行。两案active字节1281/1282均产生641Y、同一actual01200280=(640,288)、expected01210000=(0,289)、SOF0，fmt1/overflow0/pub1/drop0，padding反压1026周期/峰值积压125，下一合法帧恢复。额外GrayAF/175是按实物显式输入，不能把该匹配当独立根因证明；仿真计数0→1/7ms/尝试帧1，不重放实物5→6/4396ms/尝试帧27。两案共享首个越界Y发生时刻约7.803735ms，完整运行相差一个PCLK周期，不以相同快照确定真实行长。

静态核对ROM159条/24位、COMMAND_COUNT159/8位索引、SCCB地址3C、cmd_read固定0、ACK/三次重试；计划3808/09=0280/380A/B=01E0即640×480，4300=30/501F=00为YUV422/YUYV，top Y_BYTE_PHASE0/VSYNC_ACTIVE_HIGH1、capture按HREF高消费，控制器capture_enable由init_done&&!fatal_error经top注册传递。Y相位0在有效字节0/2/...发token，N字节产生ceil(N/2)个Y；1281的第1281字节已经是额外Y，1282仅再多一个非Y，故现有系统域首错对两者不可辨。capture HREF低时复位byte_phase/x并在下降边界加y；不裁掉x640，retained按原逻辑拒绝坏帧。

review_initialization.py仅ast解析历史Python驱动，不import PYNQ。现行Phase2常量表157条，configure外层300882/300802展开后159条与ROM全同；20260826封存版展开后仅第50条474020不同于当前474000，capture本体却逐字相同。早期把157常量直接比159或假设所有旧表都同会失败，最终按真实configure语义展开并记录差异，没有改配置来满足检查。定向查PROJECT_LOG的20260904记录：同BIT/接线4740由20改00后，旧20秒camera-only49有效帧/74超时/189fmt改善到237/0/0；20260918旧诊断还读回00。将相关旧项目记录摘录保存，明确旧前端统计不等同当前连续VGA验收，不能拿八月表/历史画质直接要求回退当前极性。

字段语义核对OmniVision v2.01规格书（Waveshare公开托管）及Linux上游OV5640并口极性代码；规格书表项与上游明确VSYNC文档/硬件解释不同等限制保留，0x4740低位命名不能单独证明OpenSOC物理有效窗口或要求翻转。参考URL/下载源码SHA在EXTERNAL_REFERENCES，完整PDF/上游C文件不入包，下载参考只留runs。HTS1896/VTS1080不当HREF有效字节数；模拟48MHz和原2..8ns约束不当实测。没有新的寄存器读回、PCLK/HREF波形、模拟亚稳态模型或真实逐行byte/Y计数，物理根因UNRESOLVED。

独立audit_results核对两案原始stdout/命令返回/输出和编译源hash、冻结副本/历史参考、实物快照坐标签名、初始化差异、原3a6facee和诊断2750779工作树干净、原候选BIT/HWH/XSA哈希及无硬件标记，PASS。README/两案TB/冻结必要RTL/静态初始化与历史输入/实际结果/审计/参考/未来提案/SHA归档Gesture_CameraRowBytes_v0.5.2_20261021_OfflineOnly.zip，73619B/SHA5e09e26b3596a2ac9f04fa9c0553ef35925bf2b4f9e625a71581404d111ec124，34文件CRC和逐文件SHA通过，不纳入Vivado/XSim/.Xil/pycache/下载缓存，不重复大模型/BIT。

本轮无XSDB/hw_server/任何板卡访问，无新RTL/模型/BIT/HWH/XSA/约束/初始化配置/计数基线/250ms门槛变化，无新综合实现或资源时序，继续沿用候选22555LUT/18341FF/128.5BRAM/24DSP、WNS/WHS+0.016/+0.007ns且余量薄。上次实板收尾/服务关闭状态保持，不申请接线/供电操作。已完成本次批准的离线阶段；下一候选只提出PCLK域旁路有效行byte/Y计数、行尾相位与身份、安全布防/稳定payload握手及只读AXI观察点，先仿真和完整实现交候选、不自动上板，尚未实现或授权，需按用户“有问题先问再开发”另行确认。424ms>250ms源年龄/空场/手势/完整A物理闭环仍未验收，不静默裁剪越界token、翻极性/采样沿或放宽计数门槛。


## 2026-10-21 PCLK行长诊断v0.6.0离线候选完成（未上板）

用户批准在隔离副本制作PCLK行长诊断候选、完整仿真与综合实现后交付，不上板。新托管分支codex/camera-pclk-line-diag-20261021由2750779建立；构建RTL检查点3d76c3bd46f06c8c0e8d21593fc2fa0c9b6aeb93，交付源码98e50cee6dd5dbff09d27265cdf573866cd859b8（之后只文档，RTL/构建脚本/约束一致）。新增LIN1旁路持续计数原IOB采样有效行字节及真实Y token、冻结首个结束超长行；两级布防请求/确认、XPM 4+4级控制同步与稳定payload四相握手；原DIA1布防/字段、capture顺序逻辑、FIFO/retained决策、模型、原约束/格式计数/250ms门槛保持。忙时布防拒绝标志及联合复位>=两域各32周期契约明确。

最终XSim a4实际21条工具命令/11项运行及整机top elaborate通过；三组时钟每组六份记录（共18），包括1280/1281/1282、最后Y、冻结/重布防/忙时拒绝/行中布防/复位排空/禁用/饱和及逐周期原capture对照。两份完整VGA异常链各614401 token，行288分别1281/1282字节、均641Y，原首错(640,288)->期望(0,289)保持、fmt1/overflow0，下一合法帧恢复；合法链921600 token/format0。合计2150402链token/3360行。原新AXI、背压及旧接口回归、独立stdout/SHA/解码审计通过。原模型整数门禁1093文件/12样本/384层通过；1101模型/约束文件与基线同哈希。

完整整机22794LUT/19386FF/128.5BRAM/24DSP，较v0.5.0净增239LUT/1045FF、BRAM/DSP不变；WNS/WHS+0.385/+0.014ns、TNS/THS0，41767net全部路由、错误0。CDC Safe14/14、14/14及输入4/4、unsafe/unknown/no-ASYNC_REG0。DRC0错31警告（比旧诊断少一项未改bbox的PREG建议，自动实现映射差异）；methodology原18TIMING-18+新增1TIMING-24。原异步clock groups覆盖XPM自动max-delay，未隐藏/未放宽原XDC；强制路由后逐位独立审计228变化位最大1.733ns<=同规则10ns、28唯一GND常量位，共256目的寄存器，4布防同步FF属性及1070诊断FF双域核对通过。该payload门禁每次重建必需，不声称自动约束生效。BIT/HWH/XSA同次内嵌匹配，PS初始化非注释内容及AXI窗口保持，原BIT/模型与旧工作树保留。

过程失败保留：a1声明顺序编译失败已修正；a2复位提前撤销send触发XPM S-2，即使主机0也独立拒绝，保存原源码/测试及日志，修正为复位排空后a3/a4通过；初次离线网表审计把常量保留位当作缺失跨域路径而拒绝，inspection_a1原文件/脚本保留，检查器增加唯一GND/VCC分类与全覆盖计数后PASS，未因此修改RTL/BIT。完整构建约56.015s创建+1017.157s实现，最终检查65.125s。无XSDB/hw_server/板卡访问/新接线/供电操作。

完整Candidate ZIP 30670230B，SHA256 b3fabf8b5ad52e157d30901a9ff17a9472e3931fcda9242ab1794b68e995a897，1313文件CRC及逐文件SHA通过；路径deliverables/Gesture_CameraPclkLineDiag_v0.6.0_20261021_Candidate.zip。阶段board_evidence/original_project_camera_pclk_diag_20261021_v0_6_0有完整源码引用、输入锁、原始实际输出、模型/资源/时序/CDC/DRC报告、独立审计与恢复/未来有限板测提纲；所有资料只本地提交不推送。原格式实物根因、源年龄424ms>250ms、60秒空场/手势/完整A实物仍未验收；PCLK域计数不是传感器/线束/供电根因证明，身份不能混同retained attempt/result。下一次硬件取证须另行确认，本阶段HARDWARE_NOT_RUN_NOT_AUTHORIZED。


## 2026-10-21 PCLK诊断单次JTAG取证v0.6.1准备

用户授权开始摄像机取证并确认USB/上电，沿用既有JTAG/相机/黑背景/机械臂断开/D5低，不伪记新冷启动。隔离目录original_project_camera_pclk_jtag_20261021_v0_6_1复用v0.5.1已通过启动/收尾/故障dispatcher，唯一扩展LIN1只读到0x0D8与PCLK确认/会话/两域冻结记录。原五ID/模型/同次v0.6.0 BIT,HWH,XSA输入SHA通过；原采集/模型/门槛不变。9Tcl+15host模拟、地址/一次写门禁、保留原telemetry/inert/transport AST通过，无硬件访问。mock最初十六进制解析/快照后valid状态修正，原失败stdout保留，final preflight_stdout_a3与OFFLINE_CHECKS PASS。原32位布防仅一笔VIS+08C=1，错误后不等PCLK行尾，只有限冻结读取和CLOSE；2秒确认/10秒观测/180秒host看门狗，服务只关闭归属本任务的进程。v0.6.0无需重建。当前将执行一次已授权板测，随后封存，不自动二次试板；备份backups/camera_pclk_jtag_20261021_pre_v0_6_1.zip。所有资料仅本地提交不推送。


## 2026-10-21 PCLK诊断v0.6.1单次实板完成

用户授权开始摄像机取证/USB连接上电，执行源码9d29113eff6a1d799734ea6e9269a9baa29eb38a；未新确认冷启动，元数据明确false，沿用既有JTAG/OV5640黑背景/机械臂断开/D5低。Asia/Shanghai2026-10-21约12:53:58～12:54:15，一次v0.6.0 BIT加载成功，CRC0/DONE/EOS/INIT_B1，五原ID/CAM1/DIA1/LIN1、D5低/后端与任务OFF/故障0；93RPC全OK/无AXI错误，唯一PL写VIS+08C=1。

原format基线1/布防计数1、LIN1 session0→1且ACK确认。约2.765秒/25次遥测：前24条format1、最后1→2。首错DIA1实际(640,94)、期望(0,95)、SOF0/Gray159、错误计数2/4707ms/retained采集尝试27。LIN1真实冻结1281有效字节/641Y、HREF行94/capture行94、PCLK帧54/session1、meta0xC24：next_phase1/last_phase0，未抑制/未饱和/非行中布防；接收4707ms与DIA1事件同系统ms。两域行/记时/会话关联有一致线索，但PCLK frame54不强行等同attempt27。该证据确认采样域已看到超长行，FIFO/retained单独重复不足以解释全部现象；实际传感器输出/采样边界/时钟或电气来源仍未确定，不直接归因光照/线束/模型，不自动剪掉额外字节或改门槛。无init_error/FIFO overflow。初始相干源年龄225ms<=250ms仅单点，未验收全程/分布，不撤销旧424ms失败。

发现新fmt后只剩RPC90 DIA1九字、91 LIN1十二字、92 LIN1状态/session核对、93 CLOSE，没有继续等行尾或轮询。新收尾复位0xF/其他五值恢复、CPU0上下文一致、双核运行/VERIFY_EXIT0；所属hw_server PID12068/launcher16688关闭，3121无监听。硬件访问已停止，不需要因恢复失败额外断电；一次性标记及HARDWARE_RUN_BLOCKED保留，不自动重跑。通用源码输入/93RPC/停止尾序列/寄存器解码/恢复/服务独立审计PASS，另独立原始字段/SOF/meta/25样本/CRC核对PASS。

结果分开：诊断取证/收尾PASS，视觉格式FAIL；60秒空场/手势/图像快照/UART机械臂动作/完整A未测。原工程/模型/RTL/约束/候选BIT不改，无重新综合实现，本轮沿用v0.6.0资源22794LUT/19386FF/128.5BRAM/24DSP、WNS/WHS+0.385/+0.014ns，这些是离线成绩，不当实物IO时序测量。阶段board_evidence/original_project_camera_pclk_jtag_20261021_v0_6_1及OFFLINE_ANALYSIS_CN.md封存；EvidenceOnly ZIP53274B/SHA2604cd5009aa8177b1c9103ed6ce68afd754c4bc30341bdc47745dc2b2c9de1f/35文件CRC及逐文件SHA通过，依赖完整v0.6.0候选包，不重复放硬件/模型。所有资料仅本地提交不推送。下一步建议基于本次1281/641做采样/HREF/PCLK边界与冻结初始化的离线核对并形成具体最小修复方案；未开发/未额外试板，RTL改动或新板测另行确认。


## 2026-10-21 采样边界原因定位v0.6.2（纯离线，根因尚未唯一确定）

用户要求定位格式增长原因，并明确当前初始化源码4740=00、运行时读回未知和真实DVP边沿未测。现场无示波器/逻辑分析仪，选择后续FPGA内部诊断方向。本阶段先完成离线机制与STA假设核对，不访问硬件/不新增候选RTL。基线97ad92f，代码前Git archive备份backups/camera_sampling_cause_20261021_pre_v0_6_2.zip；dev/filid仅本地不推送，保留所有未跟踪文件。

直接编译v0.6.0冻结capture与PCLK观察器及vendor XPM，未改DUT/force内部状态。Vivado2026.1 XSim两种假设周期20.834/41.668ns、每种15案共30案：16项1280T等宽HREF两端同移±1/100/2000/8000ps全1280/640；4项边界不等且跨采样沿1281/641、4项反向缩短1279/640、2项真1281T、2项行内额外理想PCLK边沿和2项仅数据变化。后三种长行机制均冻结meta0xC24，可解释实物1281/641，但不能从同签名选出物理原因；行内额外边沿也到最后才出现x640，所以不能把坐标错误位置当物理毛刺位置。逐针脚有效边沿计数、全部Y坐标/SOF、LIN1计数/相位与独立raw-output审计PASS。1ps边界是数字条件，不是测量采样余量或亚稳态。短行未触发长行观察器不当格式通过，无效XPM旧payload不当新记录。Gray9F为显式刺激。

最终同次postroute_physopt DCP离线核对10采样FF全部IOB/ILOGIC、posedge PCLK，未打开/保存原工程。原fall2..8ns假设HREF setup/hold+1.768/+11.096ns，十输入最小+1.710/+11.050；仅分析内rise2..8ns假设HREF+12.184/+0.680，十输入最小+12.126/+0.633。两未实测假设均正，原报告不能判断真实边沿或证明现场输入预算；set_input_delay发射沿与RTL采样沿分开。ROM159条且4740唯一474000，cmd_read恒0/read_data未用，当前VIS没有SCCB读回通路。源码漏带00不支持，实际传感器4740仍NOT_READ。

保留失败：a1 TB错误比较内部y累计与已补最终Y的record，修判据不动DUT；a3原始30案PASS但JSON漏负号字段，a4修解析后30案重跑PASS。a2错选中间routed DCP取得负setup并因不支持reset_input_delay退出，明确不是加载BIT最终时序；a5正确DCP但remove_input_delay也不受支持，最终a6用set_input_delay覆盖并导出命令历史/时序成功。独立审计核对覆盖命令顺序及20路径半周期差，不以write_xdc保留旧命令误判双沿生效。原始失败、拒绝TB与实际stdout保留。

原工程3a6facee/诊断2750779与98e50ce跟踪文件干净，候选ZIP/BIT/HWH/XSA/模型与既有证据哈希保持。没有新综合实现或资源成绩，沿用v0.6.0资源22794LUT/19386FF/128.5BRAM/24DSP、整机WNS/WHS+0.385/+0.014ns；不把它当物理IO签核。阶段original_project_camera_sampling_cause_offline_20261021_v0_6_2、独立审计PASS，物理根因UNRESOLVED。已准备最小下一内部诊断提案：初始化后固定SCCB只读快照含芯片ID/首尾4740/尺寸格式时钟，保留原采集时点；旁路另一采样相位HREF/VSYNC行长与短边界记录、身份检查、安全CDC，不能抢占原IOB或把fabric采样当校准波形。尚未开发/综合/试板，需按用户原要求确认具体范围；不自动翻4740/改XDC/裁剪x640/放宽门槛或再访问硬件。原格式、源年龄250ms/60秒空场/手势与机械臂闭环仍未验收。

OfflineOnly包 72922B / 46文件 / SHA256 d09e06d45aba0f37bbf693354c65cf3ec1a0a8085e942a0121c0eba33f9f8b72，CRC和逐文件SHA通过；依赖已交付完整v0.6.0候选及Vivado vendor XPM，不重复模型/BIT。

## 2026-10-21 全流程离线审查 v0.1.0（不上板，保留设计并报告问题）

用户明确当前不能上板，要求全面检查视觉输入到机械臂输出及架构冗余，未来先Phase2封存相机版验证现有硬件连接，再当前相机，再A闭环。本阶段只做Windows本地XSim/软件与已部署实现报告审查；无XSDB/hw_server/实物串口/板卡动作，无可综合RTL、初始化、模型、XDC或标定修改。dev/filid起点ad04e22；预备份backups/offline_fullchain_audit_20261021_pre_v0_1_0.zip，保留所有未跟踪资料。

实际部署基线为RoarmModeA软件0.2.3/硬件0.2.1，原工作树3a6facee。新runs/offline_fullchain_audit_20261021_v0_1_0冻结1771文件；53个启用RTL与部署包逐字节一致，原BIT66608046.../HWH263c64f5...实际哈希匹配。真实模型为六类background/one/two/three/fist/palm，映射S4 PALM4/FIST5，OTHER_INVALID不是第七个训练输出。原及PCLK诊断工作树跟踪文件保持干净，机器人RTL/模型/约束不变性通过。

68项实际XSim运行按各自判据通过（含旧兼容及缺done特征，不代表68项实体验收）：12视觉台架、16相机/两相位链案例、37运动/任务/协议台架、新最终顶层和原生模板2项、四缺done特征1项。模型1093文件/12样本/384检查通过；当前Python229项全部通过（初因旧目录布局跳过的两项PS/RTL合同已补跑通过），历史Locator辅助35通过/3缺旧v12/v16资产。最终top实际6帧VGA经全部ML/ROI/时间确认与adapter，OBJECT1第三帧起qualified/event_valid，帧/时间戳一致、理想源年龄72ms，未启用任务/D5低时UART空闲；仅绕过SCCB初始化，另台架核对159写/636B/ACK/NACK/XCLK/复位。原生T102/T105五案503B与独立整数格式化逐字节相同，含反压/int32边界。

真实发现：scheduler在Locator/BBox/ROI/classifier缺完成脉冲时分别停状态3/6/8/10，10000周期无候选/无本地fatal/capture_enable1；源码无更长超时条件。已有250ms图像失效和S4任务超时为另外保护，不能据此认定未授权运动；修复须定义引擎停止/帧归属/排空/重启，待用户确认，不自动改RTL。仍缺单次已使能最终top的真实pixels→完整任务→原生数字反馈plant长场景，现为真实视觉/最终接口+S4 fixture LINE+原生协议分段证据。实物1281字节行、4740实际读回/真实边沿、304或424ms年龄、现场识别、固件/限位/停止距离/实体A继续未验收。

保留并拒绝失败：首隔离副本漏config，补依赖新attempt后当前软件/monitor通过；旧台架[PASS]被初版汇总漏识别，最终独立raw日志分类修正。三项旧trajectory在readmemh缺文件时仍打印PASS，首轮全部拒绝，补原golden在新目录重跑通过；旧S2在130ns要求退役cubic ABI而读0，归为旧测试不适用。XSim fatal可能仍进程0，所以最终检查退出码+Fatal/FAIL+缺文件+完成标志，不覆盖原日志。

资源只复核绑定旧BIT的同次完整实现：22524LUT/18132FF/128.5BRAM/24DSP、WNS/WHS+.120/+.020ns，BRAM91.79%，非本轮新实现。75块完整VGA非重复快照，Locator四ROM副本用于8读口；旧三次轨迹执行器/SO101未进最终网表。u_win_traj54LUT/48FF是真小残留，u_mux103LUT/391FF中的elastic/LAST_DELIVERED数据不可直接删。建议优先验证合同/可用性，再ROI读词/流水优化；ROM分银行为需逐层/端口/实现验证候选；暂不改分辨率/模型/接口。当前DVP2..8ns仍未实测。直接最终methodology仅18TIMING-18，timing_summary缓存旧TIMING-16不当新setup失败。

用户前次要求的Phase2物理对照已锁定20260826 BIT/HWH历史哈希，但新增JTAG v0.1.0审查发现仍用旧POR整字恢复及BIT后分频，地址check-only不覆盖完整序列；在旧准备目录新增HARDWARE_RUN_BLOCKED并置HOLD，硬件从未运行，后续新补丁修传输层并完整离线故障验证后才能上板。阶段board_evidence/offline_fullchain_audit_20261021_v0_1_0含报告/输入锁/新TB/原输出/独立审计；仅本地交付和提交，不推送。下一步按用户可用条件推进Phase2→当前视觉→PL只读UART/DRY_RUN→完成commission的空载/替代物→真实A，不自动访问硬件或优化设计。

EvidenceOnly ZIP：deliverables/OfflineFullchainAudit_v0.1.0_20261021_EvidenceOnly.zip，277887B/186文件，SHA256 c4b6520cf25ae673a7dad7a7efa52a3b1db8a2cd582c9d1e8c32dc25bc313afc；ZIP CRC及逐文件SHA通过。模型/原RTL/BIT和仿真缓存未重复纳入包，依赖由提交、绝对来源和逐文件哈希锁定。两项初跳过PS/RTL合同已用当前RTL字节相同路径副本实际通过，当前软件总计229项通过。

## 2026-10-21 寄存器／双相位诊断v0.7.1及单次实板v0.7.2

用户明确同意新增诊断开发且离线门禁后直接一次有限取证。开发前备份backups/camera_phase_reg_20261021_pre_v0_7_1.zip；新托管工作树camera-phase-reg-v071、分支codex/camera-phase-reg-v071-20261021、基线98e50ce。原旧工作树两个未跟踪模块按哈希保留，原工程/初始化/模型/约束/BIT不覆盖。构建RTL检查点ea70e8f8170c905e03914559d61a3715f6dbea67，交付源2166beb5fb1e5833599f6b4004ec3be4ec50d93c只增加解码器。

新增原初始化DONE后21项固定SCCB读，保留原capture_enable时点；REG1 DC..140只读窗口，含首尾4740/芯片ID/尺寸格式时钟。新增fabric负沿HREF/VSYNC和原相位行身份／有效宽度配对冻结，PHA1 144..190只读；旧DIA1/LIN1/ABI3503及唯一08C一次布防保持，新窗口写全拒绝。原10IOB、像素/FIFO/retained/模型/计数/250ms/运动许可不变。

最终a5共17项实际XSim＋完整top展开通过：真实原100kHz master/159写21读/原初始化逐周期等价/NACK三次/XCLK丢失；寄存器8子案；双相位10子案×3时钟比，含短长/单侧多采样/身份/饱和/复位/重布防/忙拒绝/冻结/原capture等价；AXI扩展/背压/原诊断/真实VGA合法与长行回归。保护1166文件；1093模型内容＋校验清单一致、12样本384检查。保留并拒绝a2旧TB覆盖、a3Windows命令长度、a4模型资产缺失；修正文件列表和严格缺资产拒绝后a5通过。模型清单初次计数1094/误名问题有记录，非模型数值失败。

完整实现实际23750 LUT/22063 FF/128.5 BRAM/24 DSP，WNS/WHS+.280/+.050ns、TNS/THS0。原10采集IOB/ILOGIC保持；负→正半周期setup/hold+2.050/+10.376ns，旁路输入max/min非负。LIN1 228动态+28常量、PHA1 392动态+120常量全目的位核对，最大路由1.575/1.745ns<=10ns。CDC三组16/16、16/16、4/4安全，unsafe/unknown/noASYNC_REG0。31项原DRC及18TIMING-18保留；两路TIMING-24因为原clock groups覆盖自动max-delay，逐端点实际路由门禁独立放行。第一次网表检查器误读cell默认极性参数而退出，失败/探针原始证据保留，后改clock pin.IS_INVERTED真实bool后inspection_a2通过，无RTL/BIT/XDC修改。PS初始化非注释与HWH地址原样，同次XSA内嵌BIT/HWH哈希一致；2～8ns输入预算依旧未实测。

19:26:16～19:26:24（Asia/Shanghai）仅一次BIT取证，19:26:28自有服务关闭。沿用JTAG上电、原OV5640接线、机械臂断开/D5低、无场景，无新增冷启动确认。PC预检9Tcl+10host通过；28RPC全OK、五旧ID/模型及新诊断ID正确，BIT CRC0/DONE1。SCCB21读全valid/done、ACK/timeout0；芯片5640，首尾4740=00，640×480、4300=30/501F=00、HTS0768/VTS0438及读到时钟全匹配原表。运行时4740缺口关闭，无证据支持漏带00或错误尺寸配置。

原LIN1帧30/HREF行325/capture行325、1281字节/641Y、metaC24；PHA1同帧30/同行325/session1，正相位1281/负相位1280、flags3。两记录原相位结束周期63762287完全一致、接收2696ms、未抑制/饱和/行中布防，valid/session复核保持。独立raw RPC字解码与记录一致。确认有效窗口的相位敏感差异，优先DVP采样边界方向；未测模拟波形，fabric负沿不是校准相位，不能按两套绝对周期值换算引脚偏移或宣布负沿数据图像已正常，传感器/线缆/PCLK/输入余量根因仍未唯一确定。

初始格式28、最后唯一遥测仍28，LINE_VALID先触发即停，后仅固定冻结读取/CLOSE；DIA1仍valid0，不把本轮写28→29或新系统首错，原坏帧可能在布防前已判错。本轮没有有效结果时间戳，now-0=2657数值差不当源图像年龄；250ms/60秒/图像/手势/UART动作/机械臂未验收。唯一PL写08C=1、任务和后端OFF/故障0、无FIFOoverflow。PS低四位复位/隔离与其他临时值恢复、CPU0恢复、RESTORE_COMPLETE/VERIFY_EXIT0验证，自有服务关闭/3121无监听，无额外断电要求；单次目录封锁重跑。

完整候选Gesture_CameraPhaseRegDiag_v0.7.1_20261021_Candidate.zip为30950904B/1391文件，SHA acfdc203ea31b977cedc48c0b2de005729cf947652d49cce5bf97e30a559524f；实板EvidenceOnly v0.7.2为57951B/40文件，SHA3d375afa7f7c8a4720ea3c8dd07358ba54ec23ea5c4c2f82cee7fbf362882574，CRC及逐文件SHA通过。第一轮证据封装Path.with_suffix误截断版本命名，原包与PACKAGE_RESULT_a1保留；新规范名重封，不涉及硬件重试或改实测。全部资料仅本地提交/交付不推送。下一整组10IOB负沿采样功能性对照候选尚未开发/授权，具体初始化/模型/计数保护、完整离线实现门禁及有限图像/60秒验收方案已形成，按用户“有问题先问再开发”确认；机械臂继续断开/D5低。

## 2026-10-21 整组负沿候选v0.8.1：开发/实现完成，替代输入假设失败而不上板

用户明确同意开发整组10个DVP IOB负沿候选，全部仿真/实现/输入/半周期门禁后直接一次图像和最长60秒试板，随后再次要求继续完成。本阶段完成已授权开发和全部离线审查，发现真实门禁失败后停止，不将原XDC全局时序正值替代独立输入假设门禁。本轮从未启动hw_server/XSDB或访问板卡，无新图像/遥测/机械臂动作，无恢复失败/新断电要求。

预备份backups/camera_negedge_20261021_pre_v0_8_1.zip；新托管工作树camera-negedge-v081、分支codex/camera-negedge-v081-20261021、基线2166beb，源码142a154bcccbf06c6f37377fbe2df88aedb420f8。新增默认0的DVP_SAMPLE_NEGEDGE及完整正沿回退分支，通过frontend/autonomous/finaltop，候选BD设1。仅10IOB整体负沿，像素/坐标/Y/SOF、FIFO/retained/ROI/模型/原初始化4740=00/XDC/全局计数/250ms/运动许可保持，保护1226文件；原正式工程/BIT不覆盖。PHA1旧positive字段在此构建表示主负沿IOB样本由正沿逻辑计数，negative仍fabric负沿，不再是不同物理采样沿。

最终a2实际29XSim及正沿/负沿两种整机展开通过：原正沿逐周期对照、负沿7案×3时钟比/Y值坐标SOF黄金、同类边界1281正/1280负、真正短长行与外部额外PCLK不掩盖、复位/中途enable、7完整VGA合法/所有权/故障/恢复/背压场景、1281/1282字节链、原寄存器/双相位/AXI/冻结CDC/真实100kHz159写21读/初始化逐周期等价。模型1093内容＋校验清单、12样本384整数检查通过。a1在中途enable仍用540旧常数时Fatal被拒，即使XSim退出0；负沿和新驱动时刻使首源byte202、1078字节应539Y，按独立时序公式修判据并补首Y值/SOF断言，不改DUT，a2全重跑。

工程创建42.171秒、完整实现731.641秒；23764LUT/22058FF/128.5BRAM/24DSP，较前候选+14LUT/-5FF，原XDC WNS/WHS+.199/+.052ns、TNS/THS0，路由全完成/错误0。CDC16/16、16/16、4/4安全，无unsafe/unknown/noASYNC_REG。31DRC不变，TIMING-18由18降8，逐项为10DVP输入提示消失、原8LED/相机控制输出保持；2TIMING-24原clock groups覆盖XPM max-delay，逐端点独立约束审计仍必需。HWH DVP_SAMPLE_NEGEDGE实际1，BIT/HWH同次XSA匹配。

inspection_a1旧IOB glob漏generate名字退出；probe1看到真实首个IOB负沿，但误对名字含iob的OPT_INSERTED组合缓冲查C脚退出。二者原输出保留，正式检查器仍严格FD*/10IOB/ILOGIC/负沿/半周期，不放松门槛；inspection_a2真实确认10个负沿IOB、主IOB半周期setup/hold+1.182/+11.160ns（setup要求10.417）、原旁路时序、LIN1 228动态+28常量/最大1.603ns、PHA1 392+120/最大1.907ns，全payload<=10ns。然后另一输入发射沿假设setup负值导致真实拒绝，不能归检查器失败。

probe2仅离线打开同一次最终postRoute Physopt网表，导出10输入×setup/hold×两发射沿假设全部40路径和各自约束命令，无保存原XDC/项目/BIT。原fall2～8ns全部正，数据7setup/hold+9.253/+2.458；rise2～8ns全部10setup负，范围−1.163～−1.045ns，HREF−1.152/VSYNC−1.106，hold全正。最差数据7慢角IBUF1.600ns+自动ZHOLD7.317ns，输入最大8ns、数据到达16.917/允许15.754，差1.163；快角ZHOLD2.381ns，移除会消耗hold。原2～8ns/真实发射沿依旧未实测，不将这份候选失败直接等同原相机物理根因。查AMD原始UG471/UG912确认ZHOLD默认机制及IOBDELAY配置，官方链接保留EXTERNAL_REFERENCES，无全PDF入包。之前fabric负沿1280不能保证实际IOB负沿窗口，因为内部路径不同，RTL仿真本身不含这些实际延迟。

v0.8.2隔离主机脚本准备12Tcl+13host PC模拟通过，涵盖完整640×480/307200B与最终76800指针/身份、快照暂停后等新采集再测250ms、251拒绝、总线故障后不再MMIO、门禁停止和原成功收尾等；当前实际包预检/板测NOT_RUN，HARDWARE_RUN_BLOCKED有效且无服务/硬件启动标记。未用当前BIT试图“先看看”，条件性硬件授权尚不能执行。

完整ReviewBlocked包Gesture_CameraNegedge_v0.8.1_20261021_ReviewBlocked.zip为31000140B/1406文件，SHA1ad508509db56afa7937b23b98c15bfb3cda3fde6ac3b2434d8e402dea27c37f，CRC和逐文件SHA通过仅表示文件完整；含必要完整源码/脚本/模型/约束/同次BIT/HWH/XSA/全部失败与路径，明确非TestReady。BIT30030fced1109a303a90436febeb552631676192cf1d0ef7ae1e6e4f1b987855，HWH089358c4e0f17b24bbc28ec3c5d67552a9267d42e5908cddeadb32e968270b37，XSA12853bc62294c1c1be6275e050b17ab6e994e06ec7c20836279a5703c13bb8b7。仅本地提交/交付，不推送。

下一最小提案已具体写入NEXT_IOB_DELAY_PROPOSAL_CN：新隔离补丁对10个实际DVP IBUF显式IOBDELAY=NONE，新增候选实现XDC/构建引用，保留外部2～8预算/频率/初始化/模型/计数/250ms/许可，完整重建全部setup/hold/IOB/半周期/CDC/路由，任何失败即停。取消ZHOLD可能损伤hold，不能以减法估算或更改假设冒充通过。该新增真实输入路径配置尚未开发/授权，依用户“有任何问题请先问再开发”请求确认；可选择门禁后一次有限图像/60秒试板或仅离线。原相机/年龄/手势/实体A闭环仍未验收。

## 2026-10-22 — v0.8.3输入IOBDELAY=NONE真实实现hold失败，v0.8.4未试板

用户明确批准10实际DVP IBUF设置IOBDELAY=NONE，完整setup/hold/IOB/半周期及原实现门禁后才一次完整图像/最长60秒试板，机械臂断开/D5低。新托管工作树camera-iobdelay-v083，分支codex/camera-iobdelay-v083-20261022，基线142a154；预备份backups/camera_iobdelay_20261022_pre_v0_8_3.zip，最终源码f85ff79963a94496a83e4e5965b80461dfe65d44。新增implementation-only NORMAL顺序XDC及create引用，不改原XDC的2～8ns/引脚/频率，不加例外；RTL/模型/4740初始化/计数/250ms/许可等1230保护文件逐字节一致。

复用v0.8.1 a2已实际29项XSim和双参数整机展开：全部RTL/测试/vendor源、原命令日志SHA及Fatal/缺文件判据重核，冻结原输出，本补丁新增功能XSim实际次数0。模型1093文件12样本384整数检查、完整综合实现本轮实际重新运行。初次准备脚本误认为一处update_compile_order，断言停止后定位两处、只在第一处插约束引用。源码ccc3834的a1实际XDC读取器不支持if/foreach，发现critical后主动终止自己的构建进程，原日志和工程完整保留，没有把Tcl source属性测试当真实read_xdc通过；修为一条标准set_property、普通Tcl恰10对象读回，新源码f85ff79/新a2工程完整重建，实际read_xdc核对通过。

a2创建78.375秒，完整综合实现866.579秒，生成原始BIT但原全局门禁exit11拒绝：23764LUT/22058FF/128.5BRAM/24DSP；WNS+0.250ns、TNS0，WHS−2.500ns、THS−24.434ns/10失败端点。报告阶段在合格BIT/HWH复制和write_hw_platform前退出，没有合格交付BIT/HWH或XSA。实际最终DCP SHA0c76417fd301f727fc940690ec752c9e533fea4c3c0c1c4124192eeb40fa8792。

独立inspection_probe1逐项核10负沿ILOGIC/10IBUF属性NONE且直接到D，无ZHOLD，主IOB半周期setup/hold+1.241/+11.176ns，真实setup要求10.417。原fall2～8ns全10setup正，全10hold−2.500～−2.383ns；分析内rise2～8ns全10setup+3.414～+3.530ns、hold+7.917～+8.034ns，仅内存分析不写回源/工程。探针为已知失败只读取证，显式RESULT=DIAGNOSTIC_COLLECTION_ONLY_KNOWN_GLOBAL_HOLD_FAILURE_NOT_A_CANDIDATE_PASS，退出0只表完整取证。两路XPM payload逐端点228动态+28常量/392+120覆盖完整256/512，最大1.578/1.685ns≤10ns；CDC16/16、16/16、4/4安全、DRC保持31警告0错，方法学原8TIMING-18/2TIMING-24加10TIMING-15，与hold失败一一对应。

最差D6输入min2ns+IBUF1.416ns，数据13.833ns；PCLK经IBUF/BUFG/全局线至C16.106ns，加hold/uncertainty要求16.333ns，差−2.500ns。NONE确实生效，取消自动延迟后输入数据与内部时钟延迟失衡，不能只挑另一rise假设通过；也不能用旧快角ZHOLD2.381ns从旧slack相减，因为新最差角/完整路径已变。该证据解释本候选时序失败，不证明真实摄像头发射沿或实体故障根因；外部2～8ns仍预算。旧Phase2出图/旧计数宽松与当前全帧检查差异、运行时4740首尾00、1281/1280双相位现象、250ms/真实闭环缺口保留。

v0.8.4隔离软件准备有12Tcl/13host PC模拟记录，最终Candidate输入预检NOT_RUN（不存在合格Candidate包），HARDWARE_RUN_BLOCKED已写入，目录无SERVICE/HARDWARE启动标记、无jtag_actual.log或服务记录，本轮从未启动hw_server/XSDB或访问板卡，不需要因本轮操作断电恢复。原v0.8.1/0.8.2封锁不变，不偷偷下载新失败BIT。

完整ReviewBlocked包Gesture_CameraIOBDelay_v0.8.3_20261022_ReviewBlocked.zip，28450180B/1341文件/SHA818aa0e4b11b4192703c4ce74b3318a15af5f4d078ad87282c931e53961f105c，CRC和逐文件SHA通过；包含必要完整源码/模型/脚本/约束/测试和所有原始失败报告，以及hardware_REVIEW_BLOCKED_NOT_FOR_BOARD下的同次原始生成BIT/HWH，明确禁止下载，无XSA，不称TestReady。仅本地提交/交付，不推送。

额外只读最终DCP盘点确认全部10DVP/PCLK在Bank34，存在200个IDELAY站点/4控制器站点，现有50/100/48预算/24MHz时钟，无200MHz参考。a1误查package_pin SITE属性失败保留，a2用get_sites -of_objects成功；此盘点没有设计更改或路由可行性保证。AMD官方2023.2 UG953 IDELAYE2/IDELAYCTRL与本机2026.1原语库核对支持固定0..31tap及校准参考/复位/RDY；2026.1在线CTRL正文误写E3但模板E2，未混用E3规则。下一提案具体在NEXT_CALIBRATED_INPUT_PROPOSAL_CN：新隔离10IDELAYE2+1同组IDELAYCTRL+由现有100MHz经独立MMCM/BUFG产生200MHz+ready复位门控，保持现有相机24MHz MMCM/PS/原外部预算/模型/计数/250ms/权限，实际tap与两沿/全门禁择优，失败停止。尚未授权或开发；依用户有问题先问要求确认新增RTL/参考范围，可选择全门禁后有限试板或仅离线。当前A视觉格式/年龄/手势/实体闭环未通过。

## 2026-10-22 — v0.8.5校准输入时序通过但就绪CDC失败，继续v0.8.7范围内修复

用户明确选择“同意开发，全部门禁后有限试板”，批准具体10IDELAYE2/同组IDELAYCTRL/独立200MHz参考/ready门控，全部仿真/实现/两输入沿setuphold门禁后直接一次图像/最长60秒，机械臂断开/D5低、原线束/供电条件沿用。新托管camera-idelay-v085/分支codex/camera-idelay-v085-20261022，基线f85ff79，预备份camera_idelay_20261022_pre_v0_8_5.zip，源码7688844f8ab2ecf61c982cb278793ac8ccd717ce。默认旁路0/候选负沿1输入延迟1tap29，10IBUF NONE→IDELAYE2→原负沿IOB，仅主采集；raw HREF/VSYNC旁路保留，原24MHz相机wizard/PS时钟/初始化/模型/2～8ns/全局计数/250ms/权限不变，1228保护文件。

实际46XSim与三种整机展开通过独立审计：29旧回归、7校准VGA/所有权/错误恢复、2校准1281/1282行、8真实UNISIM tap/ready/LOCK和参考失效/停PCLK/联合复位恢复。a1实际39后tap8 xelab链接undefined reference失败；a2逐tap新目录/单线程补6但tap31再失败；a3误用-O 0在展开前被拒；按本机help的-O0在a4新目录补最后1。RTL/测试/判据始终不改，所有失败保留，46为本补丁实际执行，不是前版复用。编译使用同版工具预编译unisims_ver，对应IDELAY源SHA仅记录来源，未冒称直接编译该vendor源码。新100MHz就绪/故障XPM异步禁止支持停PCLK，故障不清原计数。

完整创建51.235秒、实现833.250秒，23727LUT/22066FF/128.5BRAM/24DSP，2MMCM/10IDELAY/1CTRL；原全局WNS/WHS+.124/+.050ns、TNS/THS0，生成并绑定同次BIT/HWH/XSA。独立inspection_a1确认10ILOGIC负沿/10IDELAY tap29 DATA/IDATAIN高性能模式、Bank34同组CTRL、实际200MHz来源100MHz、IBUF NONE无ZHOLD；主半周期setup/hold+1.397/+11.429ns，真实setup10.417ns；两输入沿40项setuphold全部非负，原fall hold最小约+.239ns、rise setup最小+.572ns；两路payload228+28/392+120全覆盖256/512，最大1.454/1.821ns≤10ns。

但CDC clk_fpga_1→ov5640_pclk 17端点16safe/1unsafe，CDC-10明确组合源在u_input_delay/g_calibrated.u_ready_pclk/arststages_ff_reg[0]/PRE前；源组合了100/PCLK复位、RDY/LOCK和fault。方法学新增4LUTAR-1异步复位LUT驱动提示。整体门禁FAIL：全局时序、XPM实例或独立输入检查进程exit0均不代表完整CDC通过。report_helpers从只匹配Warning/Info改为包括Critical所有行，并用本真实unsafe报告确认会拒绝；原历史报告无Critical的既有结论不受此解析缺口影响。没有新硬件访问、无新图像/60秒/机械臂证据，v0.8.6的12Tcl/19host PC模拟通过但最终包预检/实板NOT_RUN，HARDWARE_RUN_BLOCKED保留，无本轮恢复/断电要求。

完整Gesture_CameraCalibratedInput_v0.8.5_20261022_ReviewBlocked.zip，31039109B/1375文件/SHA15c2a8a2315baa14b22737f0a29e787c3310edba16c7381690dbcf76e4ef8b48，CRC/逐文件SHA通过只表完整性；含必要源/模型/约束/脚本/测试、同次BIT/HWH/XSA与完整失败证据，hardware_REVIEW_BLOCKED_NOT_FOR_BOARD禁止下载。本地封存/提交不推送。

在已批准的校准/ready/CDC实现范围内继续v0.8.7，不需重复批准同一范围。新托管camera-idelay-v087/分支codex/camera-idelay-v087-20261022、基线7688844，预备份camera_idelay_cdc_20261022_pre_v0_8_7.zip。只改控制源：100MHz注册reference_hold和capture_hold，前者同步至相关200MHz并注册CTRL RST、保持≥80ns；后者直接驱动PCLK XPM异步同步器，fault保持联合复位、停PCLK仍能禁止，原计数/FIFO不额外复位。1233保护文件不变；当前正在重新实际38+8项验证，未完成，新完整实现/硬件NOT_RUN。不得把v0.8.5已过的输入时序当成v0.8.7已验收。外部真实预算/相机物理根因/源年龄/手势/实体闭环缺口保留，后续全部门禁才原授权有限试板。


## 2026-10-22 — v0.8.7离线全门禁通过；v0.8.8目标发现失败，未到相机

当前最新（2026-10-22）：v0.8.7已完成全部离线门禁，构建源码0731eb650668fbf28e26487edf9186d9bf6d1d3b（托管camera-idelay-v087，基线7688844）；只改注册就绪控制，1233保护文件相同，48实际XSim/三种top展开/模型1093文件12样本384检查通过。完整实现23754LUT/22152FF/128.5BRAM/24DSP，WNS/WHS+.108/+.050ns、TNS/THS0，路由/DRC Error0。实际10IDELAYtap29/Bank34 CTRL/独立200MHz/10负沿IOB/IBUF NONE、禁止FF直驱异步同步器；原fall/rise两假设40项setuphold全过，主半周期+1.053/+11.581ns、payload逐端点≤10ns；CDC16/16、17/17、4/4及相关参考1/1safe，unsafe/unknown0，无新增LUTAR。DRC33警告比原31多2 bbox DPOP-1，实际旧/新DCP确认PREG1→0后输出到30/47个100MHz fabricFDRE，具体审查通过，无时序/CDC放宽。全源/模型/约束/脚本/测试/同次BIT/HWH/XSA Candidate包31034932B/1381文件/SHA f34d1eb2186c00b9177eace11c5ac2c0e122ef182cef7aa5d15d3758079d3feb，CRC/逐文件SHA通过。本轮原2～8ns/初始化/模型/计数/250ms/运动许可保持；真实引脚窗口仍未测。

v0.8.8最终PC预检实际12Tcl/22host通过后，按原授权直接一次试板：北京时间13:06:49～13:07:03，自有hw_server成功，但XSDB首次选择Cortex-A9#0即报available targets:none。停止在CPU停止/PS保存写入/BIT下载/AXI/RPC之前，RPC0，无新相机图像/寄存器/格式/年龄/60秒证据。原SESSION_RESULT=RESTORE_INCOMPLETE保留；独立审计TARGET_UNAVAILABLE_BEFORE_PROGRAMMING确认未到任何状态修改，不能伪称PS收尾验证成功。自有服务已关闭且3121无监听，没有重试，硬件尝试封锁。已要求用户完整断电保持断电，等待回复；只做离线封存。下一步先恢复JTAG目标发现，再新隔离目录复用同一候选继续相机，不因此改RTL。机械臂继续断开/D5低，A相机实时性/手势/实体闭环仍未验收。本轮本地提交/交付不推送。

资料board_evidence/original_project_camera_idelay_20261022_v0_8_7/REPORT_CN.md与original_project_camera_idelay_jtag_20261022_v0_8_8/ACTUAL_RESULT_CN.md。Candidate封存后说明勘误在后者PACKAGE_DOCUMENTATION_NOTE.md，不修改原归档。旧v0.8.1/0.8.3/0.8.5失败包和硬件封锁全部保留。以下为前次历史记录。


详细来源：v0.8.7 VERIFIED_SUMMARY/SIMULATION_AUDIT/DRC_REVIEW/NETLIST_INSPECTION与同次构建报告；v0.8.8 OFFLINE_CHECKS/jtag_actual.log/SESSION_RESULT/DEBUG_SERVICE_RECORD/VERIFIED_SUMMARY。初次严格DRC计数拒绝、具体两DSP审查及检查器_psdsp名称后缀修正均记录，未改RTL/约束或门槛；报告追加说明的PC默认GBK解码失败在证据补充说明，原ZIP不覆写。候选源码保持工作树提交0731eb6，仅本地主分支封存本轮证据，无推送。

后续用户确认“已完整断电，并保持断电”；USER_POWER_OFF_CONFIRMATION.json作为封包后的增量记录保留，不修改已封ZIP。v0.8.8 EvidenceOnly包51360B/35文件/SHA7456d3d2ecd019afaac151f943e6f0de5a40d538dee431ce5f371e03b92aab88，CRC与逐文件SHA通过；它只证明连接失败证据完整，图像/60秒/PS收尾/机械臂并未通过。板卡保持断电，任何新硬件访问仍未执行。


## 2026-10-22 — 暂停VGA路线；Mode A Phase2前端备选v0.1.0离线交付

用户要求把当前开发作为分支暂停，标记并保留回退，另做Phase2前端硬件备选、注意时序资源、不写冗余模块。已在codex/camera-idelay-v087-20261022提交ca80c215b50aaa5145452092b30baa6c16891750状态文档PAUSED_BY_USER，最后构建源码0731eb6及原包/失败实板证据不变；恢复须用户明确要求。独立托管camera-phase2-alt/分支codex/mode-a-phase2-frontend-20261022从原A的3a6facee建立，源/工程改动前备份backups/mode_a_phase2_frontend_20261022_pre_v0_1_0.zip，最终构建源码4a82b6d31756a9fe553fa0a357d944c1539d6d9d。

复用冻结Phase2原正沿capture/FIFO/nearest同帧ROI字节一致，letterbox决策逐周期等价，新增accepted-SOF时间戳；仅一块32KiB双bank图像RAM供Locator/ROI/快照共享。原源坐标几何EMA保留，小图ROI映射floor x/5、16+floor y/5、ceil side/5后NN32；初始化159项仅474000恢复474020。保留真实六类模型/量化/任务/轨迹/UART/权限/250ms，构建不含VGA源RAM/PIL/诊断/IDELAY/额外200MHz/并行旧新前端。VIS ABI3504、128x128 Gray8/16384B/4096word，快照冻结/延迟释放/退出不重新消费旧帧覆盖。

实际18XSim：3合法时钟/行尾异常与旧writer决策/双bank与时间戳、超规格71MHz FIFOoverflow负向、AXI边界与背压、ROI/调度释放/滤波/任务保护、实际100kHz159SCCB写/NACK/锁定、六类真实像素ML链、生产顶层6帧及检测帧快照跨LOC/ROI/CLASS。最终事件资格成立/仿真age44ms/D5低UART空闲；这是仿真而非实物任务。模型整数审计1093文件/12样本/384层PASS，1094模型文件SHA保护。12冻结TRAIN Locator字节同一，10有效ROI原新10/10正确，仅实现夹具观察。失败编译/TB关键字/超合同输入及提前误判中间时序等原始记录保留；最终RTL未实施另提移位加法/额外流水/IOBDELAY补丁。

Vivado2026.1完整创建69.062s/实现1324.719s；21127LUT/17322FF/53BRAM/26DSP/1MMCM，较暂停v087减少2627LUT/4830FF/75.5BRAM，DSP+2。最初DSP<=24比较目标未达：3精确常数映射减去1原PIL DSP，显式记录资源取舍，器件220上限/其他门禁不变。WNS/WHS+.009/+.022ns，TNS/THS0，36489全路由/DRC Error0；9ps/22ps余量薄，最差setup为原复位到后端baud_div。独立最终网表10正沿IOB/无IDELAY/无诊断/单共享RAM，20输入maxmin最小setup+1.710/hold+11.050；CDC12/12、12/12、4/4safe、unsafe/unknown0，Gray两组11位2级同步skew0.865/1.066ns<=10。原2..8ns外部预算未测，不以STA推断物理余量。DRC42Warning/方法学TIMING18x18保留；新增6PLBUFGOPT连接警告由Vivado实现FCLK1串接，追加只读逐节点确认同一10ns/0..5ns，BUF10/32；不是写入冗余RTL模块，也不宣称物理时钟树已最简。

用户随后提供队友反馈并明确批准直接B方案。输入ZIP35成员CRC/34清单SHA、单独3文件同字节、540CSV行与ROI映射复核通过，10有效TRAIN B输入与本地仿真逐字节同，模型SHA同。CSV复算部署整数193/240->188/240（80.42%->78.33%，-2.08pp），15退化/10改善，数字2/3混淆增加，空黑背景均0/30真实误报。全VAL推理由队友运行，本机没有重推理、没有独立核查未提供的VAL原图/标签，没有重训/开封TEST。未把附件建议当代理操作授权；采用权来自用户当次请求。far/小手/弱光/复杂背景/密集序列/硬件防抖误触发未验收。

完整本地候选deliverables/Gesture_ModeA_Phase2Frontend_v0.1.0_20261022_Candidate.zip，36251276B/1387文件/SHA fcbec2a7da18cdc0f523715c41aafefb33e0630cf72a4d7203f2bab29ff4ef28，CRC及全部SHA通过，同次BIT/HWH/XSA内部外部匹配。首包Path.with_suffix截断版本文件名，原完整目录/ZIP保留backups/mode_a_phase2_frontend_20261022_packaging_attempt1，修正为追加.zip后新包重封，未覆盖失败证据/改RTL。报告与全证据board_evidence/mode_a_phase2_frontend_20261022_v0_1_0；独立网表检查65.391s与追加时钟树只读42.203s。源/模型/约束/脚本/测试/实际原始报告与SHA完整；必要源码/模型进入交付包，原可再生缓存不入Git。

当前板卡最新用户确认完整断电、机械臂断开/D5低，本轮没有访问硬件/启动调试服务。相机图像/新ABI板测/连续250ms/真实手势/机械臂闭环NOT_RUN。旧Phase2会忽略部分额外行尾token，不称1281字节根因已修；原视觉scheduler缺局部done超时恢复保留。后续先新建/预检ABI3504隔离JTAG脚本及恢复目标发现，依次只读ID、无场景图像格式/尺寸/内容、最长60秒稳定性/年龄、空场及1/2/3/FIST/PALM，再由用户逐步接入机械臂。原VGA路线继续暂停；本轮只本地提交/交付，不推送。


## 2026-10-22 — Phase2备选首次实板：格式/60秒通过，三张实拍近黑

用户明确已连接，允许自主板测至结束并返回照片；再次确认JTAG上电、OV5640原JA/JB、机械臂未接、D5断开或低。仅在新隔离board_evidence/mode_a_phase2_frontend_jtag_20261022_v0_1_1运行host v0.1.1，同一Phase2硬件v0.1.0/源码4a82b6d/原BIT-HWH-XSA哈希；无RTL/模型/初始化/XDC改动，原VGA路线继续暂停。修改前保存复用host5文件ZIP backups/mode_a_phase2_jtag_20261022_pre_v0_1_1.zip。PS启动/收尾/失败分派与既有脚本比较相同，增加3504/4096word界限并拒绝不存在诊断页，只允许040/04C快照写。实际PC预检15Tcl/16host故障注入通过，包括frameID0、越界、运动写、总线故障停止、快照错误和age251拒绝。

北京时间17:59:28~18:00:58单次实板，18:01:04服务关闭：JTAG目标正常，四ABI3101/3202/3403/3504及0F350087匹配，不再出现上次无目标。三张完整128x128 Gray8/16384B快照fid43/400/757、SOF4095/41380/78238ms、上下16行填充零、完整4096word/身份稳定，实际JTAG_REPLY独立重拼与RAW逐字节相同，PGM/PNG CRC/解压匹配。每张约6.36~6.83秒冻结读取不当实时年龄；三次释放均确认新采集新结果。累计非冻结live60.218秒由两段30.109秒组成，中间取图，不声称不间断60秒；383采样/383不同结果ID，format基线0最终0，无新增FIFO/init/锁定错误，源年龄120/P50146/P95180/max182ms均<=250。owned-drop两段分别80->80/155->155，差值75发生在持帧期；未以丢帧累计变化冒充实时链路错误，也未说全程无丢帧。全部采样detected=false/model-task7，不将qualified年龄标志当有效手势。

三张PNG已实际查看：中央有效区灰度范围3~11、2~8、2~8，近乎全黑，有弱噪声纹理、无可核对物体。保留原始灰度未提亮/去噪/插值/合成。结论ACTUAL_PHASE2_CAMERA_DATA_FORMAT_SNAPSHOTS_AND_60S_LIVE_PASS_DARK_SCENE_VISUAL_LIMIT；只验数据格式/快照/本次年龄连续性，不能排除当前黑背景/遮挡、光照曝光或图像数据问题，不能宣布正常成像质量/物理连线全面正常/旧1281字节根因修复。原宽松行尾语义/2..8ns真实窗口未测、9ps/22ps薄时序和6BUFG告警限制保留。下一步正常照明下可见明暗物体对照，之后黑背景及1/2/3/FIST/PALM；图像/手势通过后由用户逐步接臂。本轮真实手势/物理UART/机械臂闭环NOT_RUN，无擅自RTL或曝光修改。

实际host写9次仅快照040=1/04C=0/040=0各3次，无任务/运动/配置/诊断写。初末后端OFF/D5无许可/任务OFF、故障0；XSDB exit0、PS_ISOLATED_SHUTDOWN_VERIFIED/复位0F契约/RESTORE_COMPLETE确认，其他临时PS/CPU按原规则恢复，PL保持复位隔离。自有host/launcher/server关闭，3121无监听；不自动重试，保留STARTED，后续新目录。证据包deliverables/Gesture_ModeA_Phase2Frontend_BoardEvidence_v0.1.1_20261022_DataPass_DarkScene_r2.zip，164322B/38文件/SHA4ff11d01db03b70a0181a7359c4ce5d6f009aa463364178320d82be000949439，CRC及全部SHA通过；只含本次脚本/实际日志/3组PNG-PGM-RAW/输入绑定，硬件原候选不复制不覆盖。仅本地提交，不推送。

封包收尾补充：首证据包包含一个自动.Xil地址映射缓存，保留原包/attempt1记录；canonical _r2包排除.Xil与bytecode，164322B/38文件/SHA4ff11d01db03b70a0181a7359c4ce5d6f009aa463364178320d82be000949439，完整CRC/逐文件SHA通过。实际执行脚本/图片/原始日志均未修改；jtag_bridge惰性空白行保留原字节以绑定实测SHA。原始jtag_actual.log虽全局忽略，仍明确单文件加入证据；不提交.Xil。


## 2026-10-22 — 合并可见性/手势v0.1.2，用户因相机方向暂停

用户直接要求合并前两步并上板，随后确认张掌就绪。仅新host分段观测脚本/控制文件/PC测试，硬件仍Phase2v0.1.0/4a82b6d，原RTL/模型/初始化/XDC/250ms/格式门槛未改；原VGA分支继续暂停，机械臂未接/D5低。旧脚本7文件备份backups/mode_a_phase2_gestures_20261022_pre_v0_1_2.zip。15Tcl/16host/7guided PC测试实际通过；首预检mock12Hz不能覆盖10Hz轮询重复帧断言，改mock4Hz后重跑，生产逻辑/门槛不变，尝试记录保留。

新目录board_evidence/mode_a_phase2_gestures_jtag_20261022_v0_1_2，实际同次四ABI/模型匹配。第一段PALM10.109秒/79不同结果帧，format0未增长、age117~190ms；完整128x128/16384B快照fid138/SOF12200ms、有效灰度14~255，图片实际可见手和物体、上下零填充/持帧身份正确。rawSHA50061625cf7ea01243392f2d39c12668cebdc350e5eb33be5627a9bf85483d7a，实际JTAG重拼相同。后2秒过渡以外65帧模型0类51/1类1/7类13，稳定任务0类59/7类6，无PALM模型5/任务4配对；原始统计保留，不套准确率。

用户随即纠正“摄像头方向反了，请重新检测这一项，准备好了我会通知你”。立即控制002 USER_STOP并停止后续阶段；标INVALID_PRESENTATION_WRONG_CAMERA_ORIENTATION_RETEST_REQUIRED，刚才记录不计正式张掌识别通过/失败，空场/1/2/3/FIST均NOT_RUN。未旋转/镜像图片或改RTL/模型/阈值，等用户就绪后新隔离尝试重测本项。用户暂停是当前任务状态，不自动继续。

host北京时间19:55:06~19:57:37，USER_STOP/return2表示用户终止而非硬件故障；XSDB VERIFY_EXIT0、PS隔离复位0F/其他临时值与CPU收尾确认，自有服务完全关闭/3121无监听。host写仅040=1/04C=0/040=0三次，无任务/运动/许可配置写，无硬件或恢复故障，无需因本次成功收尾请求断电。原图/原始数据、实际日志/控制/指令/状态/哈希封存UserPaused证据包130813B/37文件/SHA7b25fd142639efc2e63e4f174538bb7c9e86e87203a7eb7cb8675ce4674bbc79，CRC/全部SHA通过只表完整性；包deliverables/Gesture_ModeA_Phase2Gestures_BoardEvidence_v0.1.2_20261022_UserPaused.zip。所有资料仅本地提交/不推送，保留单次标记，不覆盖旧证据。


## 2026-10-22 — 方向纠正后v0.1.3完整手势观测，识别未通过

用户通知“准备好了”，恢复此前合并可见性/手势观察请求，新隔离目录board_evidence/mode_a_phase2_gestures_jtag_20261022_v0_1_3。硬件仍Phase2v0.1.0/4a82b6d，同次BIT/HWH/XSA哈希校验，无RTL/模型/量化/阈值/初始化/XDC/权限修改，原VGA路线仍暂停，机械臂未接/D5低/S4和后端OFF。脚本版本元数据/授权更新前备份backups/mode_a_phase2_gestures_20261022_pre_v0_1_3.zip；15Tcl/16host/7guided实际预检通过，然后一次配置/会话。逐段用户确认PALM、EMPTY、再次确认EMPTY、ONE、TWO、THREE、FIST，最后控制008完成收尾。

host北京时间20:02:45~20:14:23，7段各约10s，共70.376s非冻结live/527采样及不同结果ID，段间等待与取图不作连续观测。格式基线0未增长、FIFO/init/锁定异常0，age117/P50148/P95184/max190ms<=250。7张128x128 Gray8/16384B照片fid141/979/2936/4356/5692/7020/7678，完整4096word、持帧身份与上下零填充、退出新源结果正常；实际JTAG_REPLY重拼与全部RAW、PGM和PNG CRC/解码字节一致。原始未提亮/旋转/镜像；actual contact sheet仅nearest4x和图外文字，手形明确可见。初/末任务/运动故障0；仅21次host040/04C快照写，无任务/运动/许可/诊断配置写。

最终VISIBLE_CAMERA_DATA_PASS_GESTURE_ACCEPTANCE_FAIL。每段首2s过渡仍保留，之后PALM60帧fist22/bg32/palm1/no-det5，ONE60帧fist55/bg5，TWO62帧bg53/two6/palm3，THREE62全bg，FIST62帧no-det36/fist18/bg8。两段EMPTY60+58帧均no-det。模型/稳定任务/检测/资格联合预期匹配PALM0/60、EMPTY60/60和58/58、ONE0/60、TWO1/62、THREE0/62、FIST12/62；不当独立GT准确率/实际任务触发次数。输入识别不可靠，完整实物A不执行。

视觉勘误：初始错误把EMPTY1的128缩略图认作残留张掌，用户确认无手后做EMPTY2；nearest放大并排确认两张均无手，已明确向用户纠正，VISUAL_REVIEW_CORRECTION记录原图SHA和事实，SCENE_CONFIRMATION.issue只为当时错误假设。不把此次视觉误判写成快照残留或硬件bug，未改图像/门槛来隐藏。两段空场有效，原记录保留。

对本次7张实际small快照运行只读冻结整数Locator/Classifier与B公式，未读TRAIN/VAL/TEST、未训练调参；保存参数/参考源码SHA、PC ROI32/logits。结果PALM->palm、两EMPTY拒绝、ONE->fist、TWO->two、THREE->bg、FIST->fist，无整数溢出。ONE和THREE误判不依赖PL执行也能出现，提示真实输入/定位ROI/模型适配问题；但快照非对应同一live帧、参考浮点单图无EMA，与RTL固定点有状态几何有边界，不能唯一归因或宣称RTL全正确。缺完整原VGA不能冒称A/PIL与B对比准确率。下一步同帧ROI/整数路径离线复现，若需RTL/模型/预处理修复，按用户约定先具体提案确认，目前未改。

观测流程host0/XSDB0/PS隔离复位0F/其他临时PS与CPU现场收尾通过，自有server/host/launcher关闭，3121无监听，PL保持复位隔离，无后台访问；不是硬件恢复失败。旧时序薄余量/2..8ns未测/Phase2行尾宽松语义限制不因实测消失。所有照片/原始数据/分类与访问日志/用户阶段确认/勘误/复算封存Gesture_ModeA_Phase2Gestures_BoardEvidence_v0.1.3_20261022_GestureFail.zip，822824B/88文件/SHA17239521be0cfc610cb4f4cb51373c0b2a2d300f603c7862da0e4a40dc543b0c，CRC/逐文件SHA通过仅表失败证据完整。原方向错误v0.1.2与暗场v0.1.1、硬件候选全部保留。当前真实识别未通过，物理UART/机械臂A闭环NOT_RUN。本轮仅本地提交和交付，不推送。


2026-10-22曝光标定v0.2.0：实测源码e58b433，20XSim+完整实现/IOB/CDC通过；984行/5x作为静态调试档，10张原始小图/4147实时样本/format0->0/maxage191ms，75.156秒末尾选定档通过。冻结参考7张张掌仍全部background，画面改善但识别未恢复，完整A未测。正常恢复传感器原值/PS/CPU并关闭调试服务。原ROM未改、下次需重放配置，原VGA路线继续暂停。证据位于主目录board_evidence/mode_a_phase2_exposure_20261022_v0_2_0/，原4a82b6d Phase2分支保留；本次独立曝光分支，不自动合并主目录历史源码，不推送。


2026-10-22铺满垫子后PALM复测v0.2.2：同一e58b433/Phase2Exposure v0.2.0 BIT、984行/5x，不改RTL模型阈值。用户确认持续张掌/臂断开/D5低，实际22:35:10~22:36:31，10张新128x128/16384B快照与JTAG/RAW/PGM/PNG一致。冻结参考Locator和PALM分类10/10=100%；20.203秒去重实时169/169 PALM=100%，qualified+vis_valid为151/169=89.35%，另18个也是PALM、恰为9次快照释放后前两个结果帧重新确认，不删除分母。282健康样本，format0->0，无FIFO/init异常，age119/P50154/P95186/max191ms<=250。正常恢复相机原值/PS/CPU，host/XSDB0、自有服务关闭。v0.2.1中文UTF8/GBK读取在Bridge之前失败、未访问硬件，原尝试保留；v0.2.2显式UTF8和15/16/16预检通过。10图PNG ZIP92741B/SHA9085e74dc7700ff8565ed7ce98b39b9075a7105e4b45a98fe522ff0f4bc2ba79；Evidence r1 ZIP657006B/SHA57519879410f8de395975f46204c5f853049bf8d038eb798abdd641385805857，CRC/SHA通过。仅本轮单一PALM场景，不是六类总体准确率；新背景空场/1/2/3/FIST及实物A闭环未测。证据board_evidence/mode_a_phase2_palm_fullmat_20261022_v0_2_2，原VGA路线仍暂停，仅本地不推送。


## 2026-10-23 — Phase2曝光备选四类手势实板 v0.2.3/v0.2.4（数字类失败）

用户要求逐项FIST/ONE/TWO/THREE，全部通过才进入机械臂测试。同一e58b433/Phase2Exposure v0.2.0 BIT，固定984行/gain80，不改RTL/模型/ROI/阈值/XDC。预先声明每类10/10快照、最后约10秒连续模型及联合确认各>=95%、format无增长和age<=250ms；机械臂断开、D5低。FIST 2026-10-22 23:54:24~23:59:25会话完成10图后等待ONE180秒超时，保留原STOPPED_ERROR，传感器/PS/CPU正常恢复和服务关闭；新隔离v0.2.4于2026-10-23 00:01:06~00:06:47只续测ONE/TWO/THREE，等待600秒，总watchdog2500秒。15Tcl/16相机host/20曝光-PALM-四手势PC门禁通过，同一BIT及执行源哈希绑定，无重建硬件。

结果：FIST快照10/10、连续模型及联合81/81，通过；ONE快照0/10（6未定位、4背景）、连续0/81；TWO快照0/10（7背景、3 ONE）、连续模型4/78=5.13%、联合0/78；THREE快照0/10（5背景、5 PALM）、连续83/83错误并稳定qualified成PALM/task4。全段采图前+连续模型命中166/173、2/172、11/169、3/173，联合154/173、0/172、0/169、1/173，漏检错分均保留。冻结参考浮点几何/无EMA，与实时RTL帧/状态分开统计，不冒充逐帧位精确对照。全部40新图原像素可见对应手形，JTAG/RAW/PGM/PNG逐字节一致、128x128/16384B/16行零填充、新身份/固定档一致、整数溢出0；4421健康样本format0->0，无FIFO/init异常，最大age191ms。相机数据检查通过、数字手势验收失败，未连接臂、未启动实物闭环。

正常恢复原传感器值/自动模式、PL隔离复位0F/其他临时PS及CPU现场，自有调试服务关闭；v0.2.4 host/XSDB0。仅会话等待超时无硬件故障，不要求额外冷启动。整机资源时序复用原LUT21187/FF17410/BRAM53/DSP26、WNS+0.104/WHS+0.051ns，不声称重新实现；原外部2~8ns预算未实测及既有告警保留。旧VGA路线继续暂停。

定位结论：保存图像参考复现数字类失败，ONE多次Locator不足，TWO/THREE定位后仍背景/错类，当前不只任务确认问题；光照/掌面/ROI/模型适配具体贡献尚未隔离，未实施阈值放宽、重训或硬件修改。下一步先核对本次真实ROI和训练口径，修改方案按用户要求先确认；新场景空场和完整A物理测试NOT_RUN。证据为board_evidence/mode_a_phase2_fourgestures_fullmat_20261023_v0_2_4及相邻v0.2.3目录，含40原图/参考/两会话日志/逐图CSV/四类拼图和审计。仅本地个人分支提交，不推送。


## 2026-10-23 — 持续LED观测软件 v0.2.5（未自动试板）

用户要自行观察LED寻找识别环境。新增scripts/run_mode_a_led_monitor.py和独立模板board_evidence/mode_a_phase2_led_monitor_20261023_v0_2_5。每次显式--run创建新隔离会话，哈希及PC门禁通过后复用已实测启动/恢复和同一Phase2Exposure BIT，重放984行/gain80；持续观测到Ctrl+C或原AXI/初始化/FIFO/格式增长/age>250ms异常，无快照、无运动写、S4/后端OFF/D5低，每秒再核无运动状态。终端区分模型/稳定任务和由状态推算的灯码，实际灯无独立回读，不提供无GT的准确率。Ctrl+C处理函数只置停止事件，随后正常恢复原相机模式/参数、PL复位隔离/其他临时PS/CPU并关闭自有服务；总线故障后不继续MMIO或目标查询。直接强关终端恢复不承诺。

实际PC验证15Tcl注错+16相机host+13曝光SCCB+8LED映射/真实循环停止/异常清理/实际SIGINT处理=52项通过。PS启动/恢复/总线故障分派与v0.2.4逐段相同。--help和--check-only实际执行，未调用--run；新持续工具硬件验证NOT_RUN。原e58b433整机资源LUT21187/FF17410/BRAM53/DSP26、WNS+0.104/WHS+0.051ns复用，无RTL/BIT/模型/阈值/XDC改动，原2~8ns预算未测和数字手势失败结论保留。

LED说明按LD3..LD0：0000未检测/未确认/过期/复位，1000背景，1001 ONE，1010 TWO，1011 THREE，1100 PALM，1101 FIST，1110门控类，1111 fatal。任务PALM4/FIST5与模型PALM5/FIST4不同。建议保持目标姿态约10秒并检查移手后的空场，不能以瞬间亮灯当成通过。

软件补丁ZIP deliverables/Gesture_ModeA_LEDMonitor_Software_v0.2.5_20261023.zip，38978B，SHA256 af5327ba6a3e37a3bf50a56107eba5b275a7bb8816e20181a6d63e2290557a9d，CRC及逐文件SHA通过；依赖现有完整硬件目录，不重复包BIT/模型。README有启动/停止/离线命令、条件、故障恢复与NOT_RUN边界。原完整VGA路线仍暂停，只本地提交不推送。


## 2026-10-23 — 视觉问题交接、转入分级UART联测 v0.1.0

用户报告更换吸光更强的垫子后正确率明显改善，但每几十秒出现一次持续较久的识别不准，PC软件模型测试也有同样问题，交CNN队友修改。本轮不量化该主观正确率，不把用户判断升级为新的摄像头物理时序签核。按要求冻结并暂不处理CNN参数/网络及OV5640曝光、增益等配置，仅记录相关日志。未来队友更新模型与必要相机参数另阶段处理；旧完整VGA/IDELAY路线继续暂停。

用户指定顺序：先Windows TTL→机械臂，成功后PYNQ→机械臂UART。本轮计划仅状态查询，原未改装RoArm-M3-S/ESP32及用户自验Adapter线束沿用，不再要求错误商家图逐针重验，不重做已通过回环。找到并复制独立工作树的roarm_uart_rx_compare v1.2.0和16项无硬件测试，原脚本不改：115200/8N1、DTR/RTS false、约7.5秒内5次字面T105，真实完整六通道T1051为通信判据，50B查询自回显不算通过，原始字节与事件保留。脚本离线16测试实际通过；无端口打开。当前枚举仅PYNQ COM14及蓝牙，外置TTL尚未枚举，已异步请求用户连接/上电/关闭串口助手并提供实际COM，等待后执行Windows，未自动进入PYNQ。

用户自行运行的LED目录只读核对并保留：003008无完整结果、005913端口3121占用未启动硬件、010136源age超限但正常恢复、010241源age超限且sensor_restore失败需断电的原记录保留、最新010551为正常操作者停止，3219健康样本/maxage191ms/原相机和PSCPU恢复通过、自有服务关闭。未改写或自动归档这些原始会话，不按本次新观测忽略既往失败。本轮不继续定位这些相机现象。

本阶段新目录board_evidence/roarm_uart_staged_20261023_v0_1_0记录用户观察、源码哈希、用户会话索引和阶段状态；本轮Windows TTL/PYNQ UART/实物运动均NOT_RUN，尚未发实际串口字节，也未访问JTAG。无RTL/模型/约束/BIT变化和新Vivado构建，复用e58b433资源/时序。只本地提交，不推送。


## 2026-10-23 — Windows TTL实测通过，PYNQ只查询入口已就绪

用户确认COM15 TTL和机械臂接好正常上电，按历史成功115200/8N1。先check-only核对COM15为VID1A86/PID7523 CH340且不打开端口，随后一次实际7.5秒TTL-only采集，2026-10-23 02:26:23起：五次10B字面T105写入，收到1620B/5条完整六通道T1051/5LF，无无效JSON、缺字段或API错误，返回0并关闭COM15。原始header_rx.bin等于全部HEADER_RX事件重组，TX严格只有5次T105；RX SHA256 e7b803c8c23338584dec9e2dbccc5841bdca344b7d90264af744ab0bdc220516。Windows TTL通过；只查询、不发运动，原始关节/TCP数据不进Git。目录board_evidence/roarm_uart_staged_20261023_v0_1_0/windows_ttl_20261023_022623_715607，公开本地审计只含数量/哈希。

按用户Windows通过后转PYNQ的授权，准备独立软件候选board_evidence/roarm_pynq_jtag_query_20261023_v0_1_0。沿用e58b433/Phase2Exposure0.2.0 BIT和PS时钟-before-BIT/整字释放/0F隔离收尾序列，不用Linux或DDR；仅原S1 RoArm MONITOR(mode2/ARM0)、D5低/S4 OFF。复用原配置编译器/驱动/字节解析参考，使用只查询占位映射而非实测运动限位；两模板入口都改为字面T105+END，未加载T102字节。436笔配置值/顺序由Python/Tcl双层校验，运行后只允许快照和OFF、禁止LINE/ARM/S2/S4/相机写和停止后重入。约10秒反馈观测，至少5个不同完整反馈序号，错误计数0、frames_tx=0（此计数仅运动帧，不因查询增长）。

实际PC门禁20Tcl注错/地址与顺序限制及25host状态/判据/完整流程模拟通过；包含完整主机正常反馈、不完整反馈、异常运动计数、AXI故障跳过后续后端停止MMIO。5条本次真实PC原始反馈分块进入PL对应字节解析模型均全6通道，舍入后与逐行参考相同。最初门禁脚本Tkinter模拟事件int/tuple类型兼容已修正，仅PC问题，无硬件访问；最终源码/配置/输入哈希封存。PS启动/恢复/总线故障停止分派与已实测v0.2.4逐段相同。

已向用户申请先正常结束LED观测、断电拆开电脑TTL收发、切到PYNQ D1/D0/GND，Adapter供电由用户按可靠方案保持，D5低，恢复JTAG及机械臂原供电并等初始化，确认后只做一次有限查询。当前等待实物就绪，PYNQ实际NOT_RUN。RTL/模型/BIT/约束/相机参数不改，无新Vivado实现，资源时序复用原LUT21187/FF17410/BRAM53/DSP26、WNS+0.104/WHS+0.051ns；旧VGA路线继续暂停。


## 2026-10-23 — PYNQ PL UART v0.1.1实测通过，两级查询完成

用户确认PYNQ接线、JTAG与机械臂就绪/D5低后，v0.1.0首次实板五ID通过，但第3笔只读0x43c40008被Tcl大小写敏感列表误拒。实际host写0笔、未启动UART，正常恢复PS/CPU和关闭服务，无断电要求。离线重现小写/十进制拒绝、大写通过；另复核发现verify_uart循环误读PLAN ABI+0x0C作为错误，正确ERROR_STATUS+0x08。两处均为新增脚本缺陷；用户两次明确批准先规范化、再一并修正寄存器地址和回归后重测。v0.1.0原脚本、日志和ACTUAL_FAILURE_AUDIT保留。

新隔离v0.1.1只修上述软件问题，增加真实小写/大写/十进制请求、ABI3202与真实错误值、未知模拟寄存器拒绝的回归。21 Tcl+27主机检查及Windows真实5条反馈的字节解析参考对照通过，PS初始化/恢复/故障分派与已实测版本相同。用户保持同BIT/线束/D5低，授权后单次上板，03:01:35~03:01:53（北京时间），观测跨度10.125秒、44条状态含启动首个未收齐样本；累计fb_ok100，43个不同反馈序号的完整六通道快照，反馈年龄min1/P50 63/P95 97/max100ms，fb_err/resp_timeout/lines_ignored/servofault与运动frames_tx全0。读取温度/力矩不是本次判据；原始关节/TCP仅本地。

实际写入436笔冻结配置与计划严格一致，两个模板入口都只输出T105，之后44次S1反馈快照和1次OFF；无S2/S4/相机配置写，无LINE/ARM。后端OFF/idle、permission/estop均低、S4 OFF且无故障，PS复位0F隔离/其他临时寄存器和CPU现场确认，host/XSDB退出0、自有服务关闭。源/输入哈希一致，实际JTAG、telemetry、SESSION的SHA已记录在不含姿态值的VERIFIED_RESULT中；成功会话原始文件不加入Git。

Windows TTL和PYNQ PL UART查询均PASS。当前未进行机械臂运动、限位/停止测试或完整A闭环；只查询占位映射不作运动标定。RTL/BIT/模型/相机/约束不改，复用LUT21187/FF17410/BRAM53/DSP26、WNS+0.104/WHS+0.051ns，无新Vivado实现。视觉问题依用户交CNN队友/暂不调相机，原完整VGA分支继续暂停。证据board_evidence/roarm_uart_staged_20261023_v0_1_0/ACTUAL_RESULT_CN.md和roarm_pynq_jtag_query_20261023_v0_1_1/VERIFIED_RESULT.json，全部保留本地，不推送。


## 2026-10-23 — OV5640 B一致性与周期错误离线审查 v0.1.0

- 用户授权回到周期识别错误定位，确定实现缺陷可直接修复；当前无人无板不试板，机械臂低速空载延后。个人dev/filid初始01369e2，fetch origin；活动源分支codex/mode-a-phase2-exposure-20261022/71be083仅只读，实际构建RTL e58b433，旧VGA分支不恢复。
- 外来ZIP SHA0be521d7f0f238d2565281d131d9bb9eb6e81562e50529a973381955e0a52027；CRC/136项校验、NPY-MEM-BIN字节/数值通过，10输入SHA精确对应旧camera01..10 RAW。53RTL/部署MEM匹配同次交付，模型1093项+release manifest9758976d...一致。
- 新增隔离PC/XSim测试与证据，未加可综合模块。21实际XSim通过：10独立样例真实采集/异步FIFO/Phase2双缓冲/真实定位CNN/peak/固定点ROI/nearest/真实分类CNN，全部163840输入字节/12800signed32/7168分类字节/42logits精确匹配；PALM_LONG_GAIN5无差异阶段，peak8,9/conf41997/source110,0,480/small22,16,96，logits[9402,2864,-7070,-14076,3666,159]为BG。3空场不接纳，7PALM全BG，匹配不是分类验收通过。手工68框直接RTL分类[10428,-25499,-20497,-4061,9095,29579]全匹配为PALM，仅诊断，不改生产合同。
- 连续四帧无复位双bank及32位时间/帧号回绕、8192次控制观测（每组4096/150ms间隔，首末614250ms）恒定EMA无漂移、确认计数饱和255/驻留恢复/过期、46历史EMA/jump/loss/gap及4前端PCLK/尾字节/过速、SCCB共享/快照消费释放通过。加速时间戳不等于长时板测；保留编译前两次脚本准备错误及修正。原bbox_done trace后三个映射线尚未锁存不可当新描述符，TRACE_NOTES明示，源ROI及实际1024分类字节均有效，连续replay另在roi_start断言22/16/96。
- 历史LED正常收尾3219样本/726.039秒，只读审计健康、ID和qualified映射无异常，maxage191ms/延迟98..107ms；没有手势GT/连续输入/完整输出/ROI及ISP时间线，不推断周期准确率。最强线索是自动ROI尺度/上下文，周期触发仍不确定，不擅改采样沿/阈值/margin/模型。
- 本轮板测、串口/JTAG、综合实现、物理运动均NOT_RUN；实际源码/权重/曝光/约束/BIT未变，原LUT21187/FF17410/BRAM53/DSP26、WNS+0.104/WHS+0.051ns仅引用旧同次实现，2..8ns临时预算仍未测。两级UART查询通过保留，低速空载推迟，A实物闭环尚未通过。
- 证据board_evidence/ov5640_b_consistency_20261023_v0_1_0：REPORT_CN、TEAM_REPLY_CN（未自动发送）、BOARD_PLAN_CN、逐阶段COMPARISON、原始日志、source_snapshot与SHA256SUMS。交付ZIP Gesture_OV5640_B_Consistency_v0.1.0_20261023.zip，345文件/2967064B/SHA15bdbb51da6518fbc4fdf1173312231147bcc3b1f758d173cf490bb3bc67a29c，CRC/逐成员SHA通过。版本/source快照仅保留本地，不推送、不覆盖原BIT。下一阶段待用户返回按同帧证据排查周期；当前生产ABI未导出全部定位raw/ROI32/logits，普通快照不能与上一live帧强配。


## 2026-10-23 — 低速空载前UART复核 v0.1.0

用户将视觉算法交由CNN队友继续设计，仅记录；开始空载低速，先UART收发。用户确认当前JTAG/PYNQ D1-D0/Adapter/共地/PC TTL移开/D5低，以及空载固定无遮挡、在旁可断电、原厂零位限位已设。新一次性query_recheck目录复用已通过软件v0.1.1和同一BIT，配置436写逐项与历史成功版相同，21Tcl/27host/5真实PC反馈解析门禁通过。实际五ID/AXI正常，但MONITOR两状态采样fb_ok=0、fb_err/timeout计数/运动frames=0，约500ms后ERROR_STATUS0x800反馈看门狗超时。正常后端OFF/idle后保持sticky错误，最终inert()的通用Unexpected motion fault覆盖了主错误显示，原寄存器日志证实FEEDBACK_TIMEOUT；本轮未改软件。PS/CPU正常恢复、XSDB0、host2、自有服务关闭、无运动。当前不能进入低速，等待用户检查开机初始化/Adapter供电/线束并确认一次相同查询复测；未要求重做相机或更改RTL。两级历史UART成功保留，本次失败也保留。原始关节/JTAG仅本地不进Git，正式摘要VERIFIED_RESULT.json；当前阶段board_evidence/roarm_unloaded_bringup_20261023_v0_1_0/STAGE_STATUS.json。


## 2026-10-23 — 接线纠正后UART通过与有限底座首动候选 v0.1.0

用户说明前次插错、恢复并要求重测。新roarm_pynq_query_recheck_20261023_v0_1_1同BIT/同436写T105-only配置，21Tcl/27host/5实际PC字节解析预检通过后实际查询通过：39状态样本、38个不同反馈序号完整六通道快照、98有效反馈，fb_err/timeout/运动frames均0，反馈maxage100ms。后端OFF/idle，PS/CPU恢复、host0/XSDB0、自有服务关闭；旧失败不覆盖，用户接线纠正与成功复测支持前次无反馈和插错有关。原关节反馈只本地保留。

用户确认固件版本未查、到手原厂未刷写，字段保持null。依当前低速空载授权制成隔离有限首动候选roarm_base_low_speed_20261023_v0_1_0：T101固定joint1，只底座从稳定反馈参考+约2°并返回；每段32样本/100ms/3.2秒/Na8，规划速度≤1°/s、加速度≤2°/s²，原厂spd16步/s（约1.40625°/s）/acc1非最大档。原厂单位及opcode复核微雪官方JSON文档，未采用示例spd0或旧T102spd200。原查询profile占位限位不用于动作，局部临时窗口由实际反馈构造，其他五关节无命令字段。普通require_real_output(robot)仍拒绝，未伪造固件版本/设备序列号/完整六轴标定；本次有限单关节验证需额外明确scope确认，不能当成通用全臂许可。

实际离线验证：35PC门禁（双层写顺序/篡改/越界/ARM前D5与完整新鲜反馈/姿态/错误/S4、完整主机两段64帧及错误不返回/停止不重入、D5撤销/陈旧/额外帧/异常关节/反馈错误/到位超时/AXI故障无后续MMIO/KeyboardInterrupt/缺人工ready服务前拒绝）通过；一次同BIT真实S2 planner+S1 mapper+formatter XSim精确64样本/384通道/全部T101+T105字节、CHECK静默、EMIT反压、返回连续性通过，仿真周期4096、实际10000000时钟。原RTL/权重/约束/相机/BIT不变，无新实现，继承21187LUT/17410FF/53BRAM/26DSP/WNS+0.104/WHS+0.051ns。

实物运动NOT_RUN：D5仍低，已向用户提交具体2°往返/速度/异常停止方案，申请断电后用PYNQ板上3.3V（不是5V）经可断开许可线接D5并恢复JTAG；同时明确版本未查原厂固件仅本次有限验证，不启用通用全臂配置。未确认前不创建SCOPED_OPERATOR_READY.json、不启动硬件。PC验证包Gesture_RoArm_BaseFirstMotion_v0.1.0_20261023_OfflineCandidate.zip为47文件/101307B/SHA6964757b18c7a847a8c95e3a56d6734bfc60c8712b47269a9262475817a05edb，CRC和逐文件比对通过；含实际参考PRIVATE数据仅本地不进Git、不推送。源码/最终PC检查/仿真日志/公开PLAN及说明可本地提交，原始查询和PRIVATE计划/姿态/夹具/运动记录排除。视觉按用户决定交CNN队友继续，只记录。

候选收尾审查补充：通用plan.raise_for_fatal只检查fatal位，本次首动应在任意PLAN错误时停止，因此增加ERROR_STATUS全字非零检查及非fatal SOURCE_CONFLICT注入回归。最终36项PC门禁通过，新增用例确认停止且不执行返回；RTL数据通路未改，无需重复XSim。实物仍NOT_RUN，等待同一D5与有限scope确认。候选源/说明、最终检查报告与47文件本地候选包重新封存为r1，原包保留。


## 2026-10-23 — 有限底座首动启动拦截与纠正接线后复测 v0.1.0/v0.1.1

2026-10-23有限底座首动两次均在ARM前停止：用户接受原厂版本未查、约2°往返/≤1°每秒并准备D5。v0.1.0于16:04启动五ID通过，但D5高/ARM许可低联合条件失败；未打印状态原值，不能单凭该次断言引脚电压，UART配置/运动写0，PS/CPU恢复、自有服务关闭。用户说明连接错误已纠正并明确要求再测；新v0.1.1从候选r1逐字节复制47文件，源/私人计划/BIT哈希全相同，不改脚本/RTL/模型/相机/门槛。16:10复测D5去抖高通过，436笔配置精确匹配，T105收到2有效反馈、1份完整六通道快照、age28ms/错误超时运动frames0；相对冻结参考b/s/e差+15/-15/-31设备单位（e=-0.0031rad，约-0.177617°），超过每轴30单位参考门槛1单位，故停止未ARM。439总写=436配置+2快照+OFF，无ARM/S2写；最终后端OFF/idle/unarmed无fault、PS/CPU恢复、host2/XSDB0、自有服务关闭。单完整快照不能确认稳定或开机重复性根因。当前低速运动NOT_EXECUTED，不能称首动或A闭环通过；当前UART有反馈，历史98反馈通过仍保留。下一提案先10秒未ARM查询取得至少5稳定完整快照，再重新冻结同幅度/速度/门槛的当前参考，相关离线门禁后一次首动；尚未授权，不自动更新/放宽容差/重试。报告board_evidence/roarm_base_low_speed_20261023_v0_1_1/ACTUAL_RESULT_CN.md。原始姿态/PRIVATE/实际JTAG只本地不进Git，所有资料不推送。

实际配置/动作边界：同一e58b433 BIT/HWH/XSA，T101仅joint1底座约+2°并返回、两段32样本/100ms/3.2秒、规划速度≤1°/s/加速度≤2°/s²、原厂spd16/acc1，其他五关节无运动目标字段。本轮尚未提交任一段S2目标；未伪造固件版本，普通全臂profile继续禁用。两次原始日志和失败标记均保留，不能重用已消费目录。v0.1.1为实测尝试版本，软件源与候选r1完全相同；36PC门禁/一次64样本真实S2+mapper+formatter XSim是既有证据，本轮只核对源/输入哈希和实际请求，不冒充重新运行。无新实现，继承LUT21187/FF17410/BRAM53/DSP26，WNS/WHS+0.104/+0.051ns；旧VGA分支继续暂停，CNN算法改善交队友。阶段STAGE_STATUS及两份公开VERIFIED_RESULT已更新，原始反馈/READY/私人夹具/计划/实际会话不加入Git；仅本地提交封存、不推送。

Local two-attempt evidence archive: Gesture_RoArm_BaseFirstMotion_v0.1.1_20261023_TwoAttemptsEvidence.zip; 79 files, 134899 bytes, SHA256 257a102e7d5aa4b6e2c7a2bcc476092b8555c1d551e74de1388f696fe491fe6f. CRC and every member SHA256 PASS. Contains private raw data, local only, excluded from Git.


## 2026-10-23 — 新稳定参考与底座2°/5°实物首动

2026-10-23稳定参考刷新与实物首动v0.1.2/v0.2.0完成：用户批准10秒未ARM稳定查询→新参考→原范围首动，随后因2°不易看见明确允许转大一点，开发端选择5°一次可见性对照。两次reference_query_v0.1.0/v0.1.1各101有效反馈/41份不同序号完整快照/错误超时运动0，D5去抖高，第一轮各轴跨度[0,0,15,0,0,0]单位，第二轮全0，均≤30；逐轴中位值冻结，未放宽0.003rad参考门槛。新查询21Tcl/31host/5实际PC解析门禁通过，第二查询逐字节相同复用门禁，PS/CPU恢复、自有服务关闭。2°v0.1.2运行时算法与旧版相同，新36PC/真实64样本384映射XSim通过；实物32帧第一段发完，S2约3.281秒DONE，38次六通道LAST_DELIVERED匹配终点，但反馈只+1.317803°、残差0.681820°，DONE后5.766秒不变，9秒到位超时，未返回。用户未看到明显小转动。按最新明确放大授权制作5°v0.2.0：80/Na20/100ms/8秒每段，规划速度≤1°/s、加速度≤2°/s²、原厂spd16/acc1不变；主机按N计帧、到位有限观察14秒，原0.004rad到位门槛和全部故障/软窗口/D5门槛保持。新36PC/真实160样本960映射XSim通过后一次实板80帧第一段发完，S2约8.110秒DONE、42次终点全向量相同；反馈+4.131026°、残差0.870896°、DONE后5.953秒平台，14秒到位超时，未返回。用户确认能看见平稳转动、无异常声音。两轮其他五通道变化0，反馈解析错误/响应超时/舵机故障0，maxage104/101ms，后端OFF/idle/unarmed、PS/CPU恢复、host2/XSDB0、自有服务关闭。已真实运动但两轮往返均未通过；当前最后反馈相对5°轮起点+4.13°，不能说已归位或完整A闭环通过。PL终点交付及电气通信/实物底座响应证据明确，不能由无T101逐条ACK断言每条ESP都执行。原厂公开ZIP仅按HTTP Range取得64KiB尾部并解压六个源文件、逐项CRC/SHA通过，非完整ZIP下载/非实物固件一致性证明；T101传至底座WritePosEx/T105来自位置读回、4096步，启动P16/I0；实物固件仍未查，PID/死区未读。优先区分舵机保持/低速连续目标与终点接收，唯一根因未定。未修改PID/力矩/固件/容差、未自动补偿/返回或继续扩大；下一仅提出同一终点单目标保持对照，需用户确认再开发和试板。原BIT/RTL/模型/相机/XDC不变、无新增硬件/实现，资源时序继承21187LUT/17410FF/53BRAM/26DSP/WNS+.104/WHS+.051ns。视觉继续交CNN队友、旧VGA分支暂停。原始姿态/PRIVATE/会话只本地不进Git，不推送。

当前报告：board_evidence/roarm_base_low_speed_20261023_v0_2_0/ACTUAL_RESULT_CN.md，前2°报告在v0_1_2，两个reference_query报告分别封存。作用域源备份snapshot_20261023_ReferenceRefresh_ScopedSources.zip和snapshot_20261023_Base5Deg_ScopedSources.zip均CRC/逐文件比对通过，排除庞大再生目录。公开结果只保留相对变化/计数/哈希，原始反馈/PRIVATE向量和完整来源包不进Git。

Final local EvidenceOnly r1: Gesture_RoArm_LowSpeed_v0.2.0_20261023_EvidenceOnly_r1.zip; 219 files/820827 bytes/SHA256 b9f24ca6cae2a9734d40f5a1ce94081c49c9db65578a9084174db83bec04b753; CRC and every member SHA256 PASS. Raw actual joint data/private vectors are local only, ZIP excluded from Git. NEXT_TEST_PROPOSAL_CN.md remains NOT_RUN and awaits explicit authorization.


## 2026-10-23 — 同一终点单目标保持 v0.3.0/v0.3.1

2026-10-23同一终点单目标对照v0.3.0/v0.3.1完成：用户明确授权门禁后一次固定原5°终点T101 joint1/spd11（0.9668°/s）/acc1、保留0.004rad/最多10秒/不返回。v0.3.0已有40PC、单样本S2/mapper/formatter和真实S1空闲轮询仿真通过，但实板ARM前历史参考底座差31单位（门槛30）停止，运动0，恢复和服务关闭。明确告知后沿用此前已授权的稳定参考刷新流程，原单命令尚未发出；新reference_query_v0.1.2为未ARM T105-only原源逐字节复制，复用21Tcl/31host/5实际PC解析门禁，实测10.079秒/43样本/42不同序号完整快照/100反馈、六轴跨度0、maxage99ms、错误运动0，恢复/服务关闭。v0.3.1新参考立即冻结，其他五通道仅保留原逻辑规划坐标（实测差≤0.003rad、它们无T101目标字段），原全六通道绝对终点、软窗口、所有安全/到位门槛不变。新40PC/单样本精确字节和真实S1 UART空闲查询XSim通过，S1仿真缩放tick最大85、不冒充实物。v0.3.0早期poll a1源列表含已裁剪未启用SO101，编译前停止，a2纠正源列表后通过，生产RTL未改。v0.3.1实际prime6/hold68，ARM一次START一次、运动frames恰1，约1.610秒完成单命令；57次终点完整向量读回一致，109有效反馈、68不同序号hold快照/全轴变化0、maxage102ms、解析错误/响应超时/舵机故障0，观测10.047秒后仍差121单位=0.0121rad=0.693279°而到位超时。无再次目标或返回，后端OFF/idle/unarmed无fault、PS/CPU恢复、host2/XSDB0、自有服务关闭。单目标对照确已执行但精度未通过；它削弱仅由连续目标更新解释，仍不能唯一判断下位机目标接收/舵机保持/死区/低速问题，因spd也从16降11并非严格单变量。T105不含PID/死区/目标寄存器确认，实际固件版本仍未查。没有自动调PID/死区/固件/力矩、补偿、放宽容差或再发运动。下一仅提出独立标注临时约1°（174单位）功能判据，在原5°两个端点内低速往返；原0.004rad精度失败保留，需用户选择后才开发试板。报告board_evidence/roarm_same_endpoint_20261023_v0_3_1/ACTUAL_RESULT_CN.md及NEXT_FUNCTIONAL_PROPOSAL_CN.md。原RTL/BIT/HWH/XSA/模型/相机/XDC不变、无新硬件实现，继承21187LUT/17410FF/53BRAM/26DSP/WNS+.104/WHS+.051ns。原始姿态/PRIVATE/telemetry只本地不进Git，不推送；视觉仍交CNN队友，旧VGA分支暂停。

Scoped source backups snapshot_20261023_SameEndpoint_ScopedSources.zip and snapshot_20261023_SameEndpointFreshReference_ScopedSources.zip passed CRC/every-member checks before changes; no large regenerable build caches included. The failed initial reference attempt, fresh query and actual single-command attempt are separate immutable directories.

Local package D:\FPGA_Projects\Gesture\deliverables\Gesture_RoArm_SameEndpoint_v0.3.1_20261023_EvidenceOnly.zip; 194 files/487093 bytes/SHA256 96eb1014e704e0be3e53952685eb9be6aefa8c71098727ab75cbb160a1cb7646. CRC/every-member SHA256 PASS. Contains raw private feedback, excluded from Git and no push.


## 2026-10-23 RoArm unloaded functional v0.4.0 / reference query v0.1.3

2026-10-23低速空载功能候选v0.4.0：用户说明底座残差在AI PC也复现，认为产品表现并要求暂时跳过定位，记录为用户信息不独立断言唯一根因；沿前述临时174单位（约1°）提案开发原5°两绝对端点内32/Na8及80/Na20、100ms/spd11/acc1一次往返候选，保留40单位严格精度失败、旧窗口与其他保护。旧参考45PC+2真实RTL XSim通过（112样本672映射逐字节/反压/连续性；另单样本真实S1 UART持续查询、仿真计数缩放）。新reference_query_v0.1.3逐字节复用已过查询源码/门禁，仅T105未ARM，实测约10秒/43样本/42不同完整快照/100反馈、六轴跨度0、maxage98ms、错误超时运动0，480写中ARM/S2均0，PS/CPU正常恢复、host/XSDB0、自有服务关闭。将新参考冻结进候选时旧非底座逻辑一致性检查拒绝：肩−15/肘−76/夹爪+31单位；肘−0.0076rad约0.435°及夹爪+0.0031rad超30单位，肘也超旧非底座±0.005rad窗口。不同轮次间差异、当次稳定，成因未确定，不归为本轮运动。最终新参考RTL门禁未运行、运动许可未生成、运动服务未启动，ARM/运动0；新增HARDWARE_RUN_BLOCKED明确封锁，原OFFLINE_CHECKS仅初始旧参考历史证据不可实板。未扩大窗口/容差。最小下一提案：用户确认后新隔离中只将其他五通道逻辑坐标及±0.005rad窗口冻结到新当前稳定参考，仍无它们T101字段；底座旧两端点/窗口、ARM前30单位、150ms及非预期变化100等保持，门禁后仅一次低速往返。尚未获此确认，不开发试板。原RTL/BIT/模型/相机/XDC不变、资源时序继承21187LUT/17410FF/53BRAM/26DSP/WNS+.104/WHS+.051ns；完整A/严格精度未通过。报告board_evidence/roarm_unloaded_roundtrip_20261023_v0_4_0/ACTUAL_RESULT_CN.md，原始PRIVATE/会话仅本地，不推送。


## 2026-10-23 RoArm functional roundtrip v0.4.1 PASS

2026-10-23底座低速空载功能v0.4.1通过：用户在v0.4.0旧非底座窗口拒绝后明确同意重新冻结其他五通道逻辑坐标和各自±0.005rad窗口，底座仍原v0.2.0两绝对端点与原窗口、仅T101 joint1，无其他轴目标字段。新reference_query_v0.1.4逐字节相同已通过查询源码/复用离线门禁，实际101反馈/42不同完整快照/六轴跨度0/未ARM运动0/正常恢复服务关闭。最新参考重生成后45PC（含174允许/175拒绝、121残差功能通过而严格失败、重复序号、首段失败不返回和异常停止）+2实际XSim通过：112样本672映射逐字节/反压/连续性；另单样本真实S1 UART持续查询采用加速仿真计数。一次实板95主机样本（6prime/27out/62return）中94完整有效、132反馈、恰112运动帧、ARM1/START2、错误/超时/舵机故障0、maxage110ms，其他五轴实动期间反馈变化0。首段32帧/3新鲜到位seq，残差−91单位=−0.521392°且反馈未变化（起始已在临时容差）；返回80帧/3新鲜seq，实际转回−3.861736°、最终比旧起点+108单位=+0.618794°。两段按临时174单位约0.997°功能到位通过，原40/.004rad精度失败保留，本次也未过严格精度；不能称双向各完整5°。593实际MMIO写精确序列重放通过（436配置+61有限运动+快照/OFF），6次LAST_DELIVERED完整向量与冻结目标一致。后端OFF/idle/unarmed无fault、PS/CPU恢复PASS、host/XSDB0、自有服务关闭，无继续控制或新增动作。原v0.4.0保持封锁及未ARM记录。原RTL/BIT/HWH/XSA/模型/相机/XDC均不变，无新实现，继承21187LUT/17410FF/53BRAM/26DSP/WNS+.104/WHS+.051ns。用户AI PC同样残差的信息仅记录、按要求暂停定位，不改PID/死区/固件/补偿。仅底座有限功能链通过，其他轴/六轴标定/抓取/完整A仍NOT_RUN，普通全臂profile关闭。报告board_evidence/roarm_unloaded_roundtrip_20261023_v0_4_1/ACTUAL_RESULT_CN.md及相对角度曲线，原始PRIVATE仅本地、不进Git、不推送。


## 2026-10-24 桌面完整布局设计 v0.1（静态方案）

- 根据用户提供AIPC建系交接和本仓库器件/计划形成独立资料：docs/desktop_layout_20261024_v0_1；本机包deliverables/Gesture_Desktop_Layout_v0_1_20261024.zip。
- 用户确认黑布600×800、OpenSOC原装镜头视角未知；推荐C(300,230,450)，整手G为280×220，交付掌面70、物体中心H(350,190,100)，P/B/I及独立退回托盘和架空PYNQ预留见图表。
- 同时核算60°对角/水平两种假设，非实测FOV；Z90时G估算最小余量14.71mm、全帧黑布估算最小余量35.14mm。释放30×30掌心中心窗依赖80mm承托宽和5mm总误差预算；不把bbox中心当掌心。
- 实际离线几何、区域边界、XML/SVG、A3单页/坐标文本/嵌入字体、PNG渲染及ZIP CRC检查通过，最终图已目视检查；真实FOV/模型识别/标定/IK/整臂扫掠/假手/真人均NOT_RUN。
- 无硬件访问、运行配置/RTL/BIT/HWH/模型/曝光/协议变更，无新增资源时序结论；T_D_from_V、T_B_from_D及TCP/Q标定保留null。下一步按说明静态测量并核对原取物区四角、镜头视野及实际夹具包络。


## 2026-10-24 Mode A black-scene v2 hardware v0.3.0 offline delivery

2026-10-24黑背景v2硬件v0.3.0离线交付完成：按用户新模型更新授权，从dev/Rain固定e4c43d44199762516e62da31672021cc73176a4c仅导入black_scene_vision_v2_int8_B_gate030_20261024，独立硬件分支codex/mode-a-black-scene-v2-20261024/构建源码744e8347d615903011cb4795ca035b288b98dda4，复用托管camera-phase2-alt工作树，旧曝光分支及暂停VGA/IDELAY分支保留。新分类器39488B及64描述符字/M-shift配套替换，实际RTL接纳改signed raw>=−11748（0.30，−11749拒绝/−11748接纳），模型ID E4C43D44；Locator ROM/其他参数、Phase2采集/双128缓存/B同帧nearest32、曝光初始化、类映射、任务运动和XDC不改。生产RTL/构建脚本仅3文件变动，其余120 RTL/约束逐字节保护核对，无新增可综合模块、active与旧候选未覆盖。包完整性2313/含manifest校验2314、26样本832逐层+独立oracle/bank/输出流通过；37实际XSim通过：8控制/边界、26全链路、Locator26逐层、Classifier26逐层、生产顶层6连续帧。全链路425984相机字节/33280定位raw/peak/ROI/22528分类字节/132logits与参考一致，22接纳/4拒绝；静态26源ROI与PC一致，46事件EMA最大差0像素。顶层6帧最后palm5→task4 qualified/event_valid，模拟age43/44ms，D5低UART空闲。初次harness a1遗漏MEM及过早采元数据被外层门禁拒绝，保留失败/X假PASS记录，修正夹具/采样并加入X-data断言后a2复跑；未因这些脚本问题改生产RTL。完整综合实现最终21108LUT/17378FF/53BRAM/26DSP，比旧版−79LUT/−32FF，WNS/WHS+.045/+.033ns、TNS/THS0、路由完整/DRC Error0，CDC28/28safe/unsafe unknown0。独立网表10正沿IOB、原1相机MMCM、8RAMB36/唯一32KiB双128缓存、nearest ROI DSP0，无VGA retained/PIL/IDELAY/诊断冗余；输入setup/hold最小1.710/11.050ns，Gray skew .817/.798ns。原2..8ns仍临时外部预算、余量薄，不称实物采样签核。BIT/HWH/XSA同次且内部SHA一致；完整Candidate ZIP 46971009B/2701文件，SHA 2c5d031e4e4ea847bd027bb7bb5d4c9adcb74fba361c71ae9264580a857a69fd，CRC及所有成员SHA通过。初版封包证据中重复硬件文件已移出最终包，原包保存在backups/black_scene_v2_packaging_attempt1_20261024，无RTL/模型变动。原始v2含一张TRAIN palm被模型判fist，RTL复现不重写为100%识别率。未训练/未开封TEST/未重跑完整开发集，不将队友PC现场认可或200/240当本轮板测。本轮JTAG/串口/机械臂均未访问，新INT8实景准确率、周期问题及完整A仍NOT_RUN；曝光984行/gain80仍需以后明确重放读回。报告board_evidence/mode_a_black_scene_v2_20261024_v0_3_0/REPORT_CN.md，包deliverables/Gesture_ModeA_BlackSceneV2_v0.3.0_20261024_Candidate.zip。所有本地，不推送；根目录原有未提交USB诊断日志保留且不混入本次提交。


## 2026-10-24 桌面布局 v0.2（依据队友独立审核修订）

- 用户提供LAYOUT_REVIEW_CN.md并要求修改计划。独立复现v0.1三项问题：yaw45需承托92.43mm、H与整手G接受范围不全相容、BUFFER相交20×60mm。原v0.1目录/包保留。
- 新H=(330,200,115)，掌心中心候选窗20×20；示例整手全域在G内、最小边距10mm。候选姿态yaw±10°/roll-pitch各±2°至首次承托，保守投影37×37，80×80真实内接承托/5mm总XY误差等条件仍待测，不以缩窗或命令姿态代替验收。
- B=(510,300,160)，中心盒X490..530/Y280..320/Z145..175，与G分开；含任意yaw物块/5mm误差净距23mm，夹爪向左伸出≤35mm时条件净距10mm，完整扫掠未测。
- P改名P_PRE=(450,200,130)；保留夹指P黑点。H高度与d_down≤20/Ez≤5/手部顶≤80条件给出10mm净空，但几何落差13..45mm未验收。托盘R_RELEASE=(520,410,60)，R_REST中心35仅落稳状态、非携物运动终点。
- 查阅原S4源码，B仅PH_OUT关键点，不新增WAIT_B；P_PRE对应PRE_DELIVERY/S_WAIT_PALM，盲窗计至PH_RELEASE完成。三角变换/TCP/测量/关节目标保留null，取物区四角、托盘393.22mm水平距离可达性与P_PRE可见性优先补测。
- 31项静态几何/反例/条件预算/图文一致性/文件/基线保持检查通过，最终嵌入字体A3/PNG已目视检查，12文件ZIP CRC与11文件SHA清单通过。实际FOV/姿态/误差/IK/完整扫掠/假手/真人均NOT_RUN，无硬件访问或运行配置/RTL/BIT/HWH/模型/曝光修改，无新增资源时序结论。
- 资料docs/desktop_layout_20261024_v0_2；本机deliverables/Gesture_Desktop_Layout_v0_2_20261024.zip，SHA256 dcd8448afe098f41b634968b93e915c4fa01d173871976658ecb75d1e93c3d98。


## 2026-10-24 AI PC 桌面布局接口补充 v0.1.0

- 根据用户要求，基于desk_20261024_v0_2新增docs/aipc_layout_contract_20261024_v0_1_0，提供UTF-8 JSON、JSON Schema、字段表、读取示例、标准库离线校核和复现脚本；不改原v0.1/v0.2图纸或运行合同。
- 明确BUFFER为Q中心盒X490..530/Y280..320/Z145..175，HANDOVER为掌心中心窗X320..340/Y190..210，固定H仍(330,200,115)；新增左侧X0..440/Y0..600用途索引外框，非可达或无障碍空间。
- 正常路径从待测PICK接近/抓取/抬升至B/P_PRE/H/释放/待测撤回/I，逐点区分Q/TCP、名义z/已验证安全z、开合语义/真实伺服参数、物块姿态/实际夹爪姿态；未知取物XY、姿态、标定、间距和安全高度保留null。
- 区分当前USB RGB/V系和OV5640设计光学系；提供理想安装矩阵与原4个V角点，D配对/真实相机外参/机器人及TCP变换仍null。B中心盒与掌心窗距离165.529mm不作为全臂净距，局部10mm/5mm仅条件设计目标。
- 实际静态格式及几何语义检查通过，12项错误修改和非有限/重复键拒绝检查通过；旧两版9+11个清单成员哈希保持。8文件ZIP CRC及7文件SHA通过，包deliverables/Gesture_AIPC_Layout_Contract_v0_1_0_20261024.zip，SHA256 07995f077725ab1b9a5f1611dfe785f556b25e96fae15cebd6f4075a77dd2234。
- 本版execution_ready=false，物理标定/IK/全臂扫掠/假手/真人NOT_RUN；未接入现有AI PC程序或通信协议，无硬件访问、运行配置/RTL/BIT/HWH/模型/曝光变更，无新增资源时序结论。仅本地资料与提交，不推送；保留原有未提交PROJECT_LOG内容。


## 2026-10-24 AI PC 布局疑问补充 v0.1.1

- 用户转述队友要求补充OV5640实际视野/图像映射和支架/托盘实物尺寸，确认BUFFER按悬停区理解，并明确先固定承托面搬运、后确认人手交付参数。新增docs/aipc_layout_clarification_20261024_v0_1_1，原布局和接口包保持。
- 无法给出实际FOV、安装后方向/内外参及支架/托盘实物尺寸，明确null；区分支架40×40/PYNQ160×110/托盘外120内100和底面z20边顶z30等设计预留与实物数据，不把全局z20当板厚。
- 只读固定源码744e8347d615903011cb4795ca035b288b98dda4四文件，补充640×480抽样128×96/上下16零填充、源ROI到小图floor/ceil及同帧nearest32公式，标注代码事实不等于安装相机或现场BIT标定。最后保留原像素635/475，实际镜像/旋转及像素到桌面仍未知。
- BUFFER保持Q中心(510,300,160)及原中心盒，持物悬停/PH_OUT中间点、不落物、不新增WAIT_B。当前阶段记录为固定承托面验证准备，真实目标面/释放姿态/路径未提供；5mm误差、yaw±10/roll-pitch±2、80×80承托及20×20掌心窗口仍未验证，不自动沿用H115到固定面。
- 15项静态资料/源码/映射/阶段约束核对通过，旧三套9+11+7清单成员SHA保持；4文件ZIP CRC/3文件SHA通过。包deliverables/Gesture_AIPC_Layout_Clarification_v0_1_1_20261024.zip，SHA256 d8fce1d74d392a724cb0d1327d89d428de37f9d44bae8f6ff0066a2ceea8740c。
- 新仿真/硬件访问/运行配置修改均0；固定面搬运和人手试验NOT_RUN，未修改RTL/BIT/HWH/模型/曝光/FSM/现有AI PC协议或绕过PALM，无新增资源时序结论。仅本地提交、不推送，原未提交日志保留。


## 2026-10-24 新模型相机自主测试工具 v0.3.1 与后续联测计划

按用户五阶段安排，优先交付可重复相机自主测试代码；关节有限验证与另窗口AI PC环境可并行，固定槽位路径/布局完成后A联测，B独立通过后做AB切换与唯一控制权验证。新增scripts/run_mode_a_camera_v2.py及版本化模板，严格绑定v0.3.0/744e8347/E4C43D44与同次BIT/HWH/XSA哈希，旧入口不改。每次新会话；支持无标签LED持续观测、固定标签按不同结果身份去重准确率与联合确认比例/10秒窗口、0..10张128小图先拍后统计、到时或Ctrl+C正常恢复。仅快照/原曝光白名单写，984行/gain80实际读回，原格式基线/250ms/异常即停保持，新增运行期ID及停帧检查，无UART/运动/任务启动。68PC预检（16Tcl/17相机/13曝光/8监控/14v2）+5入口离线检查通过；入口两次实际复制和完整预检后在硬件边界替换，服务未启动。初次PC mock生成模板假SESSION_RESULT已标明PC_ONLY封存，修正保存隔离后最终全套重跑通过。完整硬件未改，无新实现/可综合模块，继承21108LUT/17378FF/53BRAM/26DSP/WNS+.045/WHS+.033ns。新工具实板、最新模型现场准确率/周期误判改善、完整关节及AB闭环均NOT_RUN；用户自行后续上板，要求机械臂断开/D5低/JTAG。报告board_evidence/mode_a_camera_v2_operator_20261024_v0_3_1/REPORT_CN.md，说明scripts/mode_a_camera_v2_v0_3_1/README_CN.md，计划docs/DEVELOPMENT_PLAN_20261024_CN.md，软件包Gesture_ModeA_CameraV2_Operator_v0.3.1_20261024.zip依赖已有完整v0.3.0硬件目录。原USB诊断未提交日志保留不混入提交，全部本地不推送。


## 2026-10-25 六关节有限验证准备 v0.5.0，当前等待D5就绪

用户要求开始完整关节有限验证，确认TX/RX/GND、JTAG/两端上电初始化、空载固定无遮挡、人在旁可断电、原厂开机姿态、D5低；夹爪新增海绵且未完全闭合，按用户说明不调力矩、不新增闭合目标，只小幅张开再回原开度。先以原已验证Phase2Exposure v0.2.0/e58b433 BIT完成T105只查询：100有效反馈、43不同完整快照、六轴跨度全0、maxage102ms、解析错误/超时/运动帧0，OFF/PSCPU恢复/自有服务关闭通过，当前未实动。新增隔离roarm_all_joint_finite_20261025_v0_5_0模板及base/shoulder/elbow/wrist/roll/gripper六独立候选：每次仅T101单joint与对应ch，底座+5°往返80/Na20/100ms，其他−3/−3/−3/+3/−3°往返48/Na12/100ms，规划≤1°/s/≤2°/s²，原厂spd11/acc1；功能到位174单位/至少3不同序号、严格40单位另记，150ms反馈/ARM前30单位/非目标轴100单位/配置次序和异常停止保持，首次不到位无自动返回。每轴本轮初始稳定参考均经公开原厂源码各自命令钳位筛查，不把它当实物全臂标定；固件准确版本仍未知，普通全臂profile继续关闭。六候选各45PC共270通过，12真实XSim通过：全往返640样本/3840映射/每字节精确、六S1 UART单目标与持续查询；仿真时序缩放，不冒充物理UART。最终6源/硬件/计划/夹具绑定及实际入口无许可拒绝通过，无D5就绪许可生成、运动NOT_RUN。原RTL/模型/BIT/相机/XDC/固件/PID均不改、无新实现或可综合模块，继承21187LUT/17410FF/53BRAM/26DSP/WNS+.104/WHS+.051ns。已请求用户D5拉板上3.3V并确认，首轮只底座+5°再条件返回；其余逐项、每关节前重新取得稳定参考并重新冻结/门禁，不沿用上一关节残差后的旧姿态。候选PRIVATE ZIP817704B/SHA dc0b0724ff5b978522f68384dc43889354aaef9114c932f3bf8161641850e3f4，CRC/381成员逐字节通过，完整硬件依赖旧v0.2.0包不重复。备份RoArm_AllJointFinite_before_20261025.zip/SHA74cc8e4194883650cdc7b6f8d6b48255f8a497b0089caf630636e3b9fa83744e。原始姿态/计划/夹具/实际JTAG仅本地，公共日志与源码选择性提交、不推送；原未提交USB诊断日志保留。说明及门禁见board_evidence/roarm_all_joint_finite_20261025_v0_5_0/README_CN.md和FINAL_GATES.json，只查询公共结果见roarm_joint_reference_20261025_v0_1_0/ACTUAL_RESULT_PUBLIC.json。


## 2026-10-26 六逻辑关节有限实测完成，保留未通过项

沿用户D5高/空载固定无遮挡/人在旁可断电确认，以原e58b433/Phase2Exposure v0.2.0 BIT依次完成六逻辑关节8次实物尝试，共704运动帧。底座+5°往返160帧，实际首段+4.223°、误差−0.779°，返回+0.619°残差，174单位临时功能往返通过，严格40未通过。肩初始−3°48帧实际−0.527°/残差2.475°，发完后保持9.266s不再动，到位超时且不返回；用户未注意并要求更大，独立v0.6.0从新参考单程−5°80帧实际−2.372°/残差2.630°；用户要求两分钟内快速重复，r2再次从新实测位置单程−5°80帧实际−2.458°/残差2.544°，建候选至收尾115.92s；均正常停止，不返回、不扩大后续角度。用户观察肩部有一些卡顿，认为可能缺插值、误差来自本体并将交AI PC考虑；明确告知当前已有FPGA S2梯形插值/100ms更新，用户归因仅记录、没有独立确定唯一根因。用户明确要求不纠结卡顿/误差并尽快完成余轴；保持原174判据及所有保护，仅把已知到位超时保留未通过后继续下一独立关节。肘−3°48帧实际0、残差3.002°，不记实动通过且未返回。腕俯仰−3°往返96帧实际首段−2.017°/误差+.985°，返回−.350°残差，临时功能通过。腕旋转+3°往返96帧实际+2.636°/误差−.367°，返回+.527°，临时功能通过。夹爪小张−3°后回原开度96帧，实际−2.194°/张开误差+.808°到位，返回残差−1.054°（184单位比174超10），记录返回未通过、不增加闭合量。没有调整到位阈值、PID、死区、力矩、固件、采样周期或生产RTL。

每轴前均未ARM T105稳定查询，后按当前姿态重新冻结并通过45PC及2真实RTL；肩一程新候选同样门禁通过，帧/角度严格限制。全部8运动会话实际MMIO序列按冻结配置重放通过，完整LAST_DELIVERED及完成最终UART帧后的S1命令设备值均匹配；解析错误/响应超时/报告舵机故障标志0，maxage≤104ms，各轮非目标关节反馈变化0。未独立捕获实际UART字节，不把这些状态证明成机械本体唯一原因。腕实际往返通过后，离线审计误把DONE但47/48帧的过渡样本当最终目标（差1单位），自动流程在下一关节前停住；核对最终48/96帧目标正确，修正仅PC审计完成帧过滤，与原实测门槛一致，保留原样本/失败审计/中断记录，未改硬件或控制参数。随后从已正常停止腕状态完成roll/gripper。全部会话均OFF/idle/unarmed、PS/CPU恢复、自有服务关闭。无全臂归零，最后确认D5高，可由用户恢复低；不再自动追加动作。用户要求本轮停止追查，肩/肘/夹爪未通过项保留，不表述为全六关节精度、标定或A闭环通过。

完整报告board_evidence/roarm_all_joint_finite_20261025_v0_5_0/ACTUAL_REPORT_CN.md及LATEST_ACTUAL_STATUS.json，各实测目录ACTUAL_AUDIT_PUBLIC.json。PRIVATE实测证据ZIP2153179B/894成员，SHA1bc710a53ca2e57651921e788386f3763f40b25f17d5709a240cc264eab19033，CRC/逐成员通过；候选和全部失败版本保留。原RTL/BIT/模型/相机/XDC不改，无新实现或可综合模块；继承21187LUT/17410FF/53BRAM/26DSP/WNS+.104/WHS+.051ns。源码与公共相对结果选择性本地提交，不推送；绝对姿态/原始JTAG/夹具/许可只本地，原USB诊断未提交记录不混入。


## 2026-11-02 运动系统与 P2P 技术报告图 v1.0

按用户总图、classifier/locator参考图及确认的“运动系统主图＋P2P展开图”范围，交付docs/diagrams/motion_planner_report_20261102/。原生motion_planner.drawio含两页；motion_system.png为6000×4060，p2p_planner_detail.png为6880×4640，另有同源SVG、生成/验证/渲染入口、README、13个RTL的SHA绑定与布局检查结果。仅制作图稿；参考图、RTL、模型、BIT/HWH、约束及板包均未修改，无硬件访问或机械动作。按本地native_motion/rtl/robot源码核对三管理窗、目标和样本独立192位接口、单级弹性寄存器、后端接收后更新LAST_DELIVERED、UART/许可2FF、32×32=128B LUTRAM、33×32→65顺序乘法、31位除法输入、33→32截取及同宽末点旁路。明确VMAX=UQ16.16、AMAX=UQ0.32，并注明此native版本source_sel固定PLAN、TRAJ结构端保留，未照搬旧隔离S2复位选TRAJ的注释。两页布局/正交/XML/端点一致性检查无检出问题，最终PNG逐页视觉核对；未在Draw.io桌面客户端二次导出。仿真/综合/实现/时序/板测本轮NOT_RUN，资源与时序未重测，无新增硬件性能结论。原PROJECT_LOG既存USB诊断改动保留且不混入本次提交。fetch后dev/filid与origin/dev/filid已分叉（本地2、远端136），本次图稿选择性本地提交，不自动合并或推送。


## 2026-11-02 P2P技术报告图v2：单内核与标准符号

按用户新要求改为仅绘制P2P，旧两页v1保留。本次交付docs/diagrams/p2p_planner_symbols_v2_20261102/的单页p2p_planner.drawio、6400×3660 PNG及SVG。图内删除解释段落/公式/地址与实现注释，信号线上仅位宽，端口名置边界外，内部仅必要单元名；使用圆形算术运算、带时钟三角端寄存器、梯形MUX及凹口ALU。全部28个planner_p2p_core边界端口方向/位宽与本地native_motion RTL解析结果逐项一致；两路乘法输入MUX和末点MUX等宽，顺序乘法器复用及真实舍入截位保留，控制器按功能级折叠校验/定时/地址生成。正交、矩形及真实符号轮廓穿线、穿字、文字互叠与越界检查未检出问题，最终PNG视觉检查通过；单页XML/SVG可解析，未运行Draw.io桌面二次导出。RTL/模型/BIT/HWH/约束均未改，无硬件访问或机械动作；仿真/综合/实现/时序/板测NOT_RUN，不产生新资源或性能结论。既存PROJECT_LOG未提交改动保留，不混入本次提交；个人分支已与远端分叉，仅选择性本地提交，不自动整合或推送。


## 2026-11-02 P2P硬件图v3：紧凑布局与交叉规划

按用户对疏密、松散和交叉的反馈，在docs/diagrams/p2p_planner_layout_v3_20261102/交付v3单页Draw.io、6000×3000 PNG及SVG，v2原样保留。控制器高度400→300、图幅3200×1830→3000×1500，面积减少23.16%；下方主数据通路自左向右，右上方辅助比例通路折回并就近送共享乘法器，反馈/旁路分层，输出控制沿右外围走线。多序正交A*和拆线重布后，按不同逻辑网络交点统一口径计数的真实交叉26→2，全部两处使用拱桥，不用删线/遮线隐藏交叉；不声称无限制的全局数学最优。保留硬件符号、位宽守恒和28个端口；布局/真实符号轮廓穿线/文字/标签边界/接口检查未检出问题，最终PNG视觉核对，XML/SVG/内嵌图元可解析；路由缓存和搜索记录随附。未在Draw.io客户端二次导出。RTL/模型/BIT/HWH/XDC和板包不改，无硬件访问；仿真/综合/实现/时序/板测NOT_RUN，无新资源/性能结论。PROJECT_LOG既存USB诊断改动保留，不混入本次提交；个人分支与远端已分叉，仅选择性本地提交，不自动合并或推送。


## 2026-11-02 P2P硬件图v3.1：幅值单元改为ABS矩形

用户询问单输入后明确要求修改符号。将magnitude的凹口ALU轮廓与|·|标注替换为普通矩形组合逻辑框及ABS标注，保留左33位输入、右33位幅值输出和下1位符号输出；下方接点从ALU斜边移到矩形底边，其余布局和接口保持。生成PNG/Draw.io/SVG，复用并核对原路由；28个接口匹配，穿字/穿框/正交检查无检出问题，交叉仍2处。RTL及板包不改，无硬件访问；仿真/综合/实现/板测本轮NOT_RUN。新交付包p2p_planner_layout_v3_1_20261102.zip，旧v3 ZIP保留；仅选择性本地提交，原日志未提交改动保留，不推送。

## 2026-11-02 P2P硬件图v3.2：显式正交连接器

按用户要求修正Draw.io连接器类型：全部63条信号线由edgeStyle=none改为orthogonalEdgeStyle，启用orthogonal=1并关闭曲线与圆角，保留既有正交折点及两处跨线拱桥。导出前新增实际坐标检查，137段信号线均水平或垂直，斜线段0；重新解析Draw.io逐段复核，28个RTL端口匹配，布局检查无检出问题。重新生成6000×3000 PNG及SVG并查看PNG；原栅格走线本已正交，本次主要修正可编辑源文件的连接器属性。未在Draw.io桌面客户端二次导出。交付p2p_planner_layout_v3_2_20261102.zip，旧ZIP保留。仅图稿与生成器变更，无RTL/模型/板包变化和硬件访问，仿真/综合/实现/板测本轮NOT_RUN。保留原日志未提交改动；分支已分叉，仅选择性本地提交，不合并或推送。

## 2026-11-02 P2P图v4：用户XML上的最小修订

按用户“仅最小改动，不改整体布局”要求，以用户上传XML为基准独立交付docs/diagrams/p2p_planner_minimal_v4_20261102/，原图保留input.drawio.xml。131个既存图元位置/尺寸均未改变；调整必要名称，将舍入单元同位置同尺寸改为“舍入与位置恢复”矩形功能框，补减法输入极性、4个接线圆点和现有方向线上的neg_r寄存器。仅e28/e61/e49三条原线局部几何调整（加法输入从文字改接圆形实体、微小偏斜接点整理、插入符号寄存器），其余60条原线折点原样，部分端口小数对齐0.1像素；未重新布局/路由。diagrams.net原生Graph渲染SVG/5458×2858 PNG并查看，64条线实际渲染坐标斜线段0（0.01像素容差），28个外部端口与原图逐项一致；XML/源图哈希/封包核对通过。舍入框保持功能抽象，内部取位、扩展、恢复和加法未进一步展开，README明确边界。原用户下载文件、旧图版本、RTL/模型/约束/板包均不改，无硬件访问，仿真/综合/实现/板测本轮NOT_RUN。保留既存USB日志改动；个人分支与远端分叉，仅选择性本地提交，不合并/推送。

## 2026-11-02 P2P图v4.1：指定英文名称替换

按用户清单在v4图上替换8处指定名称，移除除法器÷并在上下输入端分别标DEN/NUM；两个长标签分两行。原有全部图元位置/尺寸不变，64条连接线XML及原生渲染实际路径与v4逐点一致、斜线段0。交付docs/diagrams/p2p_planner_english_v4_1_20261102/的Draw.io/XML/SVG/5458×2858 PNG及ZIP；已解析/视觉/路径对比/哈希和封包核对，无RTL或板包变动，无硬件访问，仿真/综合/实现/板测本轮NOT_RUN。原图保留，既存USB日志改动不混入提交，个人分支分叉仅本地选择性提交，不合并/推送。

## 2026-11-03 P2P图v4.2：剩余标签统一英文

在v4.1基础上按用户要求仅翻译剩余6处中文标签（5组术语）：P2P Motion Planner、Sign Extend两处、Sequential MUL、Endpoint MUX、Magnitude & Sign，保持其余已确认英文不变。全部原图元几何及64条连线XML原样，原生渲染实际路径与v4.1逐点一致、斜线段0，图中中文标签清零。已查看5458×2858 PNG，解析Draw.io/XML/SVG，路径/封包核对通过；交付docs/diagrams/p2p_planner_english_v4_2_20261103/及ZIP。无RTL/模型/约束/板包变化和硬件访问，仿真/综合/实现/板测本轮NOT_RUN。保留旧图和既存USB日志修改；个人分支与远端分叉，仅选择性本地提交，不合并或推送。
