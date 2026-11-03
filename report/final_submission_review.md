# 提交核对

| 赛题条目 | 包内入口 |
|---|---|
| 3.2.5.1 工程包 | [工程包索引](engineering_package.md)，包括架构、接口、同次 FPGA 构建证据、部署及硬件接线 |
| 3.2.5.2 指标和原始证据 | [指标表](../metrics/metrics.csv)、[日志](../metrics/logs/)、[复算脚本](../metrics/scripts/)、[证据](../metrics/evidence/)及[实物验收](acceptance/board_test_20261101.json) |
| 3.2.5.3 Skill | [三个可复用工作流](../skill/readme.md)，含用途、失效条件和验证记录 |
| 3.2.5.4 设计报告 | [技术报告 PDF](technical_report.pdf)及[复现说明](../docs/reproduction.md) |
| 3.2.5.5 目录结构 | [根 README 对照表](../readme.md#目录与赛题对照) |

报告中的实体任务 16/17、两级 FPGA CNN 服务时间、手势开发集准确率、TTL 反馈时延分位数、板端访问总数和异常数，以及布线后时序与工程证据相符。

报告表 3-7 的 3,951 帧现场感知及各阶段统计属于报告中的现场汇总，包内未找到与之配套的逐帧原始日志和复算入口。指标表的九张保存帧推理统计是另一组测试。B 模式开发集 mAP 和顶面 mIoU 见[指标表](../metrics/metrics.csv)，其标注和样本范围见[模型说明](../docs/model.md)。

实物位移起始有报告所列的视频计时单值。A/B 分位数的终点为观测到 TTL 反馈，物理位移起始的同步波形和重复测量分布未收录。现有部署和启动检查可按包内步骤执行，新机器完整安装 AMD/HIP 并复跑实物闭环尚未验证。

仓库和提交包的文件与目录使用小写 ASCII 路径。Skill 的 Codex 安装入口命名见 [Skill 说明](../skill/readme.md)。
