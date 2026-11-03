# p4.1 公开运行资产与获取渠道

公开版包含 A 板端部署参数、p4.1 硬件文件、主机与 FPGA 源码、标定参考、规划模板和复算证据。另需 9 个外部运行文件。请在 [渠道表](runtime_asset_channels.csv) 登记获准的 URL 或提供方、允许的接收范围和必须附带的声明。

| 提供方 | 所需文件 | 渠道待补 |
|---|---|---|
| Giao 或权重权利人 | 检测 model.onnx 和顶面 weights.pt | 指定 SHA256 的下载入口、许可范围和声明 |
| 机械臂网格负责人或上游 | base_link.stl、gripper_link.stl、link1.stl 至 link5.stl | 匹配 SHA256 的版本、发布地址或获准提供方，以及版权和许可文本 |
| 部署者 | Windows AMD 驱动、锁定的 ROCm/HIP 依赖和 Vivado/XSDB | 使用供应商安装来源，版本见复现说明 |

将获准取得的资产放入本地交接目录，保留渠道表中的 project/ 相对路径。在仓库根执行：

```powershell
py -3.12 tools/install_runtime_assets.py --source-dir C:/path/to/handoff
py -3.12 tools/install_runtime_assets.py
py -3.12 -X utf8 -B project/scripts/run_mode_ab.py --check-only --runtime-only
```

团队也可用安装工具的 `--archive` 参数从合法持有的原 p4.1 ZIP 提取这 9 项。工具核验字节与 SHA256，拒绝覆盖不同内容。公开运行配置省略 181 项历史、图片、训练或缓存等外部文件，仍核验其余封存输入。默认启动保留完整封存校验。

目标 Windows AMD AI PC 装好匹配依赖后，使用 `project/start_mode_ab.ps1 -CheckOnly -RuntimeOnly` 检查。环境变量 `GESTURE_XSDB` 可设为本机 xsdb.bat 的完整路径。操作者按硬件与标定说明完成现场准备后，可用 `-RuntimeOnly` 进入联测。验收覆盖 A 启动、A/B HOME 切换、B 视觉定位、路径规划、下发、取放及反馈。
