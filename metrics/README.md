# 指标表口径

`metrics.csv` 前七列对应赛题表头：指标名称、类别、数值、单位、测量条件、测试次数/时长、证据文件；另有 status 和 method。证据路径从仓库根解析。当前运行基线仍为已验收的 p4.1，指标整理版本为 `0.1.0-publication.7-review`。

正式参赛结果采用既有 p4.1 实测与复核证据。2026-11-01 从既有记录复算四类指标后，补入视觉确认至 TTL 反馈的分模式观测统计。详见 [复算报告](../docs/metrics_recovery_20261101.md) 和 [完整数值及分组统计](evidence/recovered_20261101/summary.json)：

| 指标 | 可填写数值 | 条件 |
|---|---:|---|
| 闭环任务成功率 | 16/17 = 94.117647% | 用户逐类复核既有17次执行；A交付5/5、A补回3/3、B交付5/6、B补回3/3 |
| AI任务质量 | Accuracy 91.454545%；Macro-F1 92.304743% | PL当前INT8整数参考，550张DEV，六类动作输出；开发集参与选型 |
| FPGA处理贡献 | Locator 16.4764ms；Classifier 4.68486ms；两段合计21.16126ms | 实测锁存周期/100MHz；合计为CNN服务时间 |
| PC–FPGA通信 | P50/P95/P99/max = 28.1686/217.282845/244.564982/5551.759ms；异常率0.003781862% | 52,884次RPC，保留2次异常；成功调用最大786.7561ms另列 |
| 视觉确认至 TTL 反馈观测 | A P50 493 ms，B P50 14985 ms | 分位数、最大值及样本见指标表 |

正式报告的闭环延迟采用既有板端遥测复算。合格手势观测至运动发送后新鲜 TTL 反馈观测，A 模式14条的 P50/P95/P99/max 为493/542.95/551.79/554 ms，B 模式18条为14985/22125.55/23007.51/23228 ms。该指标的端点是轮询观测到的电气反馈，物理位移起始仍缺同步事件记录。 复算方法和样本边界见 [视觉至 TTL 反馈说明](../docs/vision_ttl_latency.md)。

这些指标有各自的分母和测量端点。任务成功率来自用户对已记录执行的回溯确认；AI质量来自已有整数参考预测；FPGA时间来自硬件周期计数；通信时间来自主机调用计时。DEV质量不等于独立TEST成绩，CNN服务时间及RPC RTT也不等于传感到实物动作的响应。根表将原混合字段`pc_fpga_rtt_error_rate`拆为独立标量行，将`formal_ai_quality`改为明确带`int8_development`范围的字段；不再用含糊的NOT_MEASURED覆盖已有证据。

仅用Python标准库即可复核本次公开证据，无须设备或受限权重：

```powershell
py -3.12 metrics/scripts/recover_recorded_metrics.py --verify-public metrics/evidence/recovered_20261101
py -3.12 -m unittest discover -s tests -v
```

`evidence/recovered_20261101/`包含脱敏RPC样本、周期计数直方图、DEV标签/预测、复算摘要及来源哈希；任务复核单在`report/acceptance/task_outcomes_review_20261101.json`。原始现场图像、关节位置、JTAG载荷及设备路径不随本次提交。

此前9帧证据继续保留：`logs/saved_frame_pipeline.csv`是暖态流水延迟；`logs/saved_frame_surface_inference.csv`包含首次分割调用，并拆分预处理/推理/后处理/总时间。它们来自原测试的不同调用位置，不能逐行相加当一次端到端流程。`conditions.json`只描述这9帧，不适用于本次六会话指标。

9帧重算脚本仍为`skill/robotics-metrics/scripts/summarize.py`，实际输出见`report/validation/saved_frame_percentiles.json`和`saved_frame_surface_inference.json`。资源、时序和CDC是同次封存实现报告，本轮未重新实现。`project/metrics/metrics.csv`及封存原始材料保持原文。
