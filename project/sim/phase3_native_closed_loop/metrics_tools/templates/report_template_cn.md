# Phase 3 指标报告

{{BANNER}}

- 生成时间：{{GENERATED}}
- 数据类型：**{{DATA_KIND}}**
- 规则：百分位 = 最近秩（不插值）；P90 需 n ≥ 10，P95 需 n ≥ 20，P99 需 n ≥ 100，不足时写 INSUFFICIENT_SAMPLES；无数据写 NOT_MEASURED。时延只用同一时钟的差值；网络往返 = PS 往返 − PC 处理。

## 1. 输入（原始文件与 SHA-256）

{{INPUTS}}

## 2. 手势识别

{{GESTURE}}

## 3. 任务结果（按模式）

{{TASKS}}

## 4. FIST 取消归还

{{FIST}}

## 5. 时延

{{LATENCY}}

## 6. 截止期

{{DEADLINES}}

## 7. 连续运行

{{CONTINUOUS}}

## 8. 资源与时序

{{HARDWARE}}

## 9. 未测项

{{NOT_MEASURED}}

---
本报告只由 `compute_metrics.py` 从上表列出的原始文件计算得出；没有手工填写的数字，也没有图表。
