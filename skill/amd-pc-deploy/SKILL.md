---
name: amd-pc-deploy
description: Inspect pinned Python dependencies, declared model hashes and an optional real ROCm HIP device before local AMD AI PC inference deployment. Use for deployment diagnosis; model accuracy and robot actuation need separate validation.
---

# AMD AI PC 环境与模型自检

先确认目标操作系统、设备、Python 和版本锁，以实际目标环境执行此目录 `scripts/probe_environment.py`。工具不安装依赖、不下载权重、不打开相机或机器人；`--require-hip` 才进行 torch/HIP 算术探测。

```powershell
python scripts/probe_environment.py --requirements path/to/requirements_lock.txt --model-json path/to/model.json --require-hip --out environment_result.json
```

要求清单每行使用 `package==version`，可含 extras 和注释空行；不把复杂 pip 选项当作包名猜测。模型声明支持 `onnx` 或 `checkpoint` 对象，含包内 `file` 和 `sha256`。示例：`{"onnx":{"file":"model.onnx","sha256":"64位实际小写SHA256"}}`。保持真实模型哈希，不以更新清单绕过失败。

没有 `--require-hip` 时 HIP 结果为 NOT_RUN；包版本正确不代表 HIP 可用。启用 HIP 时必须存在实际设备并通过设备计算/同步；CPU 回退不记作 AMD 加速成功。输出不验证驱动兼容矩阵、模型数值、延迟或精度；这些另用当前框架官方支持信息和实际 batch=1 基准核验。不要因为某个旧 wheel 源失效而自动换后端。

## 边界与来源

用于显式版本锁和模型元数据的部署自检；无锁依赖、任意自定义模型格式或无 HIP 的机器需要适配，不能宣称原合同通过。工具的版本匹配为精确字符串比较，不求解依赖图。

来自 Gesture 中 Windows 原生 ROCm 部署、无 CPU 静默回退和冻结模型比对的实践；项目运行路径/设备型号不写死在工具内。实际复用范围、失败输入和干净环境记录见 [references/validation.json](references/validation.json)。复用时填写自己的版本锁、模型和设备，不能照搬该项目的性能数字。
