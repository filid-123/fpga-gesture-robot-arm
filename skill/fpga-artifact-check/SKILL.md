---
name: fpga-artifact-check
description: Verify a recorded FPGA build against its source manifest, routed timing, CDC/DRC summary and matching BIT/HWH/XSA files. Use before packaging or deployment; it never programs a board or replaces implementation review.
---

# FPGA 构建与配套文件核验

使用 `scripts/verify_artifacts.py` 核对指定包内的来源和产物；不搜索其他开发目录补文件，不连接板卡。

```powershell
python scripts/verify_artifacts.py --root path/to/package --summary evidence/implementation_summary.json --sources evidence/built_source_hashes.json --artifact-dir hardware --out result.json
```

## 输入合同

来源清单为 `{"files":{"relative/source.v":"实际SHA256"}}`，不能为空。构建摘要必须含：

- `source_binding_sha256`：来源清单文件本身的 SHA256。
- `timing_ns`：有限数值 WNS、WHS、TNS、THS。setup/hold 最差裕量不得负，总负裕量须为0。
- `drc_errors`、`cdc_endpoints`、`cdc_safe`、`cdc_unsafe`、`cdc_unknown`：显式非负整数；错误/unsafe/unknown 为0，端点数量与 safe 相等。确实无跨域端点的设计可报告0，不能用缺字段代替0。
- `artifacts`：按文件名列出恰好一个 `.bit`、`.hwh`、`.xsa`，每项有 `bytes` 和 `sha256`。XSA 内须有与外置 BIT/HWH 同名且字节一致的唯一成员。
- 可选 `utilization`：原样带入结果，不拿 OOC 相加推断整机资源。

缺失字段、非有限数值、目录越界、源码变动、重复产物或内部文件不匹配都要停止，保留错误报告。摘要格式不同的工程先显式转换其真实报告字段，不填造通过值。该工具检查的是已记录证据的一致性；摘要不是签名，不能据此证明报告真实产生。仍须保存原始实现报告、工具版本和命令。

## 来源与失效条件

来自 Gesture 的同次源码/模型/约束/位流绑定、薄时序余量及不同 ABI 配套经验。不会替用户选择板卡引脚、复位、许可或现场动作，也不会因文件核验通过就启动机械臂。时序、模型或 RTL 改动后要新建构建版本。

参见 [references/validation.json](references/validation.json)：实际 p4/a14 记录核对，加上第二个最小合成工程的通过/损坏拒绝测试。合成 XSA 只验证文件合同，不是可下载硬件。
