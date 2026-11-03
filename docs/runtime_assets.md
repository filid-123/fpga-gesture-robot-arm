# p4.1 公开运行资产与获取渠道

公开版包含 A 板端部署参数、p4.1 硬件文件、主机与 FPGA 源码、标定参考、规划模板和复算证据。另需 9 个外部运行文件。[渠道表](runtime_asset_channels.csv)逐项列出固定下载地址、字节数、SHA256 和上游声明。

| 提供方 | 所需文件 | 固定版本 |
|---|---|---|
| Giao · Gesture-AIPC | B 检测 `model.onnx`、顶面 `weights.pt` | [权重分发记录](https://github.com/HaoxWwwgiao/Gesture-AIPC/blob/9ef51606a9ad037b57bd1ce584aac39e55e7fac5/docs/WEIGHT_DISTRIBUTION_RECORD.json) |
| Waveshare · roarm_ws | `base_link.stl`、`gripper_link.stl`、`link1.stl` 至 `link5.stl` | [RoArm-M3 网格](https://github.com/waveshareteam/roarm_ws/tree/40dbd84b553695212fab713e8465f817ba95454d/src/roarm_main/roarm_description/meshes/roarm_m3)及[上游包声明](https://github.com/waveshareteam/roarm_ws/blob/40dbd84b553695212fab713e8465f817ba95454d/src/roarm_main/roarm_description/package.xml) |
| 部署者 | Windows AMD 驱动、ROCm/HIP 和 Vivado/XSDB | [复现说明](reproduction.md)列出版本和环境要求 |

在仓库根目录执行以下命令。工具从固定提交下载，核对全部文件的字节数和 SHA256 后再写入。

```powershell
py -3.12 tools/install_runtime_assets.py --download
py -3.12 -X utf8 -B project/scripts/run_mode_ab.py --check-only --runtime-only
```

两份权重和七个网格由上游提供，本仓库和源码 ZIP 均采用外链交付。请保留上游声明并遵循其适用条款。权重分发记录保留了训练来源和权重再分发的待确认范围。

离线时，可将已取得的文件按渠道表中的 `project/` 相对路径放入本地交接目录，再运行 `py -3.12 tools/install_runtime_assets.py --source-dir C:/path/to/handoff`。无参数运行只校验本地文件。

团队也可用安装工具的 `--archive` 参数从合法持有的原 p4.1 ZIP 提取这 9 项。工具核验字节与 SHA256，拒绝覆盖不同内容。公开运行配置省略 181 项历史、图片、训练或缓存等外部文件，仍核验其余封存输入。默认启动保留完整封存校验。

目标 Windows AMD AI PC 装好匹配依赖后，使用 `project/start_mode_ab.ps1 -CheckOnly -RuntimeOnly` 检查。环境变量 `GESTURE_XSDB` 可设为本机 xsdb.bat 的完整路径。操作者按硬件与标定说明完成现场准备后，可用 `-RuntimeOnly` 进入联测。验收覆盖 A 启动、A/B HOME 切换、B 视觉定位、路径规划、下发、取放及反馈。
