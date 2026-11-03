# 当前发布上下文

日期：2026-11-01。整理版本：`0.1.0-publication.9`。运行基线：p4.1 / ABI340E。

- 唯一导入基线：`gesture_mode_ab_v0_1_0_20261030_p4_1.zip`，SHA256 `c29a4f659c341646d2354006435401aa5458eb135630601a7b1077b9ba7b8adf`，4,521 文件。
- 源包原生产文件位于 `project/`。Git 收录子集与被排除资产逐项见 `report/provenance/`；原始 manifest 和 SHA 清单保留不变。
- 身份：patch `native_giao_full_workspace_p4`；hotfix `startup_route_map_p4_1`；TASK ABI 0x340E；B 路径 RAM ABI 0xB001；a14 匹配 BIT/HWH/XSA。
- 实际系统：Windows 原生 AMD AI PC，普通 RGB，本地 ROCm/HIP 感知；XSDB/JTAG 到 PL AXI；OV5640→Locator→同帧 ROI→分类/事件；A 固定槽位，B PC 规划与 PL 路径执行；RoARM-M3-S 原生 TTL。
- 封存实现：30,657 LUT / 25,196 FF / 117.5 BRAM tile / 56 DSP，WNS/WHS +0.013/+0.011ns。余量薄，后续硬件修改必须重新实现审查。
- 当前 p4.1 已实测通过，状态 `USABLE_USER_ACCEPTED` / `PASS_USER_CONFIRMED`，可作为后续可用/回退基线。依据：用户现场确认及六次会话摘要，见 `report/acceptance/board_test_20261101.json`。A/B 任务完成和双向 HOME 过渡已有记录；六次共24,446条遥测无FPGA fault/反馈错误或超时/原生路径错误。
- 既有17次执行经用户确认16成功、1失败，94.117647%；A交付5/5、A补回3/3、B交付5/6、B补回3/3。新增复核单记录操作者复核结论，不改原session_result。尚未记录橡皮完成交付，不外推连续全域验证。
- 已从既有证据复算：52,884次RPC/2异常，RTT P50/P95/P99/max为28.1686/217.282845/244.564982/5551.759ms；当前INT8整数参考550张DEV准确率91.454545%、Macro-F1 92.304743%；FPGA两段CNN服务时间16.4764+4.68486=21.16126ms。DEV不是独立TEST，CNN周期和RPC时间不是物理响应。物理响应新增用户实物视频人工计时0.62秒=620ms：触发手势已进入摄像头视野→机械臂首次可见运动。此前2.4秒读数由用户撤回；仅有一个报告值，实际试验次数/A或B阶段未说明，不推断P50/P95/P99/max。当前指标表统一为sensor_to_physical_response=620ms，合并此前重复条目并移除分位数占位行，共54项；统计范围在说明中保留。复核单report/acceptance/video_response_review_20261101.json；原日志复算快照保持历史原文。详见docs/metrics_recovery_20261101.md。
- 两次完成任务后JTAG Invalid context和恢复未确认、历史UART间歇问题仍OPEN；RPC统计保留失败，不将其归因到具体B物理失败。
- 本轮仅同步既有实测验收，没有新开硬件或重跑现场试验；原ZIP及 `project/` 中历史NOT_RUN不改写。
- 新增三类独立 skill：环境/模型自检、FPGA 文件/证据绑定、指标统计。实际复用验证记录在各 skill 的 `references/validation.json` 和 `report/validation/`；不宣称跨板实测。
- 团队当前只有赛事使用授权，团队原创源码采用 AGPL-3.0-only，第三方再分发许可分别核对。被排除资产不随 Git 发布；完整本地复现先按 `docs/reproduction.md` 恢复合法持有的原 ZIP。
- 本次允许在保留历史和个人分支的前提下更新远端 main；旧开发目录 dev/filid 的未提交改动不属于本次提交。

入口：`README.md`、`docs/release_scope.md`、`docs/license_audit.md`、`report/submission_status.md`。

2026-11-03 延迟更新。正式报告的闭环延迟采用既有板端遥测复算。合格手势观测至运动发送后新鲜 TTL 反馈观测，A 模式14条的 P50/P95/P99/max 为493/542.95/551.79/554 ms，B 模式18条为14985/22125.55/23007.51/23228 ms。该指标的端点是轮询观测到的电气反馈，物理位移起始仍缺同步事件记录。

Giao 的冻结 B 模式模型评测已收录。38 张开发验证图的 mAP@0.5:0.95 为 65.52%，GT 框内顶面二分类 mIoU 为 82.81%。历史单布局 20 帧分别为 83.28% 和 95.45%。两组均使用 CPU 离线评测和 AI 近似标注。原始图像与现有 B 模式权重由团队保管。
