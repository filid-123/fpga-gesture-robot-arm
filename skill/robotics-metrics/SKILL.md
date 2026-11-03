---
name: robotics-metrics
description: Compute task success rates and timing percentiles from explicit robotics CSV observations, including batch-one inference components and communication RTT. Use for evidence reporting without converting synthetic or saved-input results into physical claims.
---

# 机器人指标与证据统计

使用 `scripts/summarize.py` 读取实际观测 CSV，显式提供测量条件和证据类型。缺数据写 NOT_RUN，不生成零耗时或100%成功。

```powershell
python scripts/summarize.py --csv latency.csv --kind latency --start "sensor acquisition complete" --end "measured actuator response" --conditions "hardware/model/precision/input/software/clock/power and synchronization" --evidence-kind physical --out latency_result.json
```

## CSV 合同

| kind | 必须列 | 含义 |
|---|---|---|
| task | outcome | 每个有效试验一行：success、failure 或 intervention；分母包含三者 |
| latency | duration_ms | 同一对测量端点的延迟；另给 `--start`、`--end` |
| rtt | duration_ms | 同一请求/应答定义下的 RTT；不自动推断单向延迟 |
| inference | batch, preprocess_ms, inference_ms, postprocess_ms, total_ms | 每行 batch=1，有限非负耗时；总时间不小于各分量之和 |

`--evidence-kind` 必选 physical、saved_input、simulation 或 synthetic。`--conditions` 说明硬件/设备、模型与精度、输入、软件版本、FPGA 时钟、功耗模式和测量方法。涉及不同钟域的物理延迟先确定同步/误差预算；只有主机发出命令的时间不能当执行器实际响应。

输出 P50/P95/P99/最大值和样本数，分位数使用 `(n-1)*p` 线性插值，输入文件哈希随结果保存。小样本的 P99 不证明长期尾延迟；推理与预处理拆分还需要测量代码中的同步正确。脚本检查格式和算术一致性，不证明日志真实、试验相互独立或时钟同步有效。

## 来源与复用边界

来自 Gesture 中任务状态计数/物理成功、保存帧 HIP 推理/现场端到端、规划时间/完整抓放时间的区分经验。使用前定义有效试验、成功、失败和人工干预；无效试验的剔除规则另行记录，不能事后删掉失败。

参见 [references/validation.json](references/validation.json)：实际保存帧结果重算、独立合成 CSV、无数据/NaN/错误批量等拒绝测试。未验证第二套机器人实测，不把工具的单元测试算成场景成功率。
