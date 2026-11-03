# 可复用 Skill 与工作流

三项工具都可整目录复制到独立目录，用 Python3.12 标准库运行；HIP 检查仅在明确请求时导入已有 torch。每个目录包含 Codex `skill.md`、可执行脚本、UI 元数据和实际验证记录。安装到 Codex 时，复制整个 Skill 子目录到 Codex 的 skills 目录，并在安装副本中将 `skill.md` 改名为 `SKILL.md`，随后按名称调用；工具也可脱离 Codex 直接运行。

| Skill | 适用范围及使用入口 | 失效条件 | 本次验证 |
|---|---|---|---|
| [amd-pc-deploy](amd-pc-deploy/skill.md) | 环境版本锁、模型哈希、可选实际 HIP 算术探测；`python scripts/probe_environment.py --help` | 未安装依赖、版本不符、缺失模型、HIP 不可用；它不验证模型质量/机器人动作 | [记录](amd-pc-deploy/references/validation.json) |
| [fpga-artifact-check](fpga-artifact-check/skill.md) | 核对源码→构建摘要→BIT/HWH/XSA、setup/hold、CDC/DRC；`python scripts/verify_artifacts.py --help` | 摘要不完整、来源/文件不符、负裕量、CDC 未闭合或不同次产物；它不能证明原报告未被伪造 | [记录](fpga-artifact-check/references/validation.json) |
| [robotics-metrics](robotics-metrics/skill.md) | 任务成功率、延迟/RTT 分位数、batch=1 推理拆分；`python scripts/summarize.py --help` | 输入为空、非有限值、缺批量/端点/条件、时间分量不一致；它不能补造测量 | [记录](robotics-metrics/references/validation.json) |

## 来源与验证边界

环境工具来自“框架名称/导入成功不等于实际 HIP 执行”的项目观察；硬件工具来自多版本 ABI、模型与构建配套，以及启动页遗漏问题；指标工具来自“保存帧推理、任务寄存器完成和物理成功不能混计”的项目经验。

验证包含真实封存项目的数据重用、故意损坏输入的拒绝测试，以及独立目录/新建无第三方包虚拟环境中的工具运行。合成测试数据标明 synthetic；不计为实物成功率、GPU 模型性能或跨板卡实测。实际执行命令和结果在 `report/validation/`，各项摘要在目录内，可随 skill 一起复制。

尚未进行第二块实物板/第二套机器人场景迁移，也未完成全套应用依赖从零安装。因此本次只证明相应工具在干净 Python 环境及第二个合成工程格式中的可执行性，不宣称整机跨设备迁移成功。整体开源许可证仍待团队决定，第三方适用声明保持不变。
