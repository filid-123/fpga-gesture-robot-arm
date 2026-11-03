# 从零复现与验证

## 1. 源码和独立工具

安装 Python 3.12 x64。可直接解压源码 ZIP，或用 `git clone -c core.autocrlf=false https://github.com/filid-123/fpga-gesture-robot-arm.git` 克隆，保留封存文件的换行字节。运行根 README 的源码检查与42项工具测试（含10项指标复算测试）；这部分只需标准库，不连接硬件，不需要第三方权重。`skill/` 的三个目录可独立复制；详见各 skill.md。

源码检查通过表示当前文件与源包或经记录的脱敏清单一致。`missing_external_assets` 和 `full_runtime_ready` 必须一起阅读。完整原包检查在缺失资产时应失败，不得通过删清单绕过。

## 2. 外部资产

合法持有指定源 ZIP 时：

```powershell
py -3.12 tools/restore_assets.py --archive C:/path/to/gesture_mode_ab_v0_1_0_20261030_p4_1.zip
py -3.12 tools/check_repository.py --complete
```

整个 ZIP SHA256 为 `c29a4f659c341646d2354006435401aa5458eb135630601a7b1077b9ba7b8adf`。工具只恢复被排除文件，拒绝错误整包和已有不同内容，保留所有已收录生产源码。原历史回退包/重复报告产物仅为完整封存校验而恢复，不作为当前默认版本。

完整历史封存包仍由团队保管。运行当前 A/B 版只需按 [运行资产获取说明](runtime_assets.md) 获取九项固定版本外部资产。历史原图和训练资产不参与该运行配置。

## 3. Windows 原生应用环境

按 `docs/model.md` 确认 AMD GPU、驱动、Python 和封存版本锁。使用显式 Python 路径，避免依赖原开发者用户目录：

```powershell
py -3.12 tools/install_runtime_assets.py --download
cd project
powershell -ExecutionPolicy Bypass -File ./setup_mode_ab.ps1 -Python C:/path/to/Python312/python.exe
powershell -ExecutionPolicy Bypass -File ./start_mode_ab.ps1 -CheckOnly -RuntimeOnly
```

安装会访问原包声明的 AMD wheel 索引并创建项目本地 `.venv-ab-rocm`；虚拟环境不随 Git 发布。公开版预期返回 `PUBLIC_RUNTIME_INPUTS_PASS` 及 p4.1 patch/hotfix。完成现场准备后，使用 `start_mode_ab.ps1 -RuntimeOnly` 启动。如需严格检查原始封存包，使用独立目录解压原 ZIP，在该目录运行：

```powershell
./.venv-ab-rocm/Scripts/python.exe -X utf8 -B scripts/check_mode_ab_package.py
```

环境探测可从仓库根使用该解释器运行 `skill/amd-pc-deploy/scripts/probe_environment.py`，传入 `project/requirements_mode_ab_lock.txt` 和模型 JSON。`--require-hip` 会实际执行设备算术，但不跑相机/机械臂；原 `-VerifyModels` 需要完整原包的九张历史图。公开版部署步骤省略此选项。

本次没有在新机器完整下载和安装全部应用依赖；使用既有环境重跑的结果与干净标准库工具环境验证分开记录。wheel/驱动不兼容则停止，保存失败，不切换 CPU 后仍报 ROCm 成功。

## 4. FPGA 重建

使用 AMD Vivado2026.1、PYNQ-Z2 board part、所需原模型资产及含 NumPy/OpenCV 的 Python。原 Tcl 构建时调用整数模型审计。先输出计划：

```powershell
python tools/build_fpga.py --vivado E:/Xilinx/2026.1/Vivado/bin/vivado.bat --out C:/fpga_builds/gesture_p41_run1
```

确认计划后加 `--execute`。输出目录必须是新目录、位于封存 `project/` 之外；不会覆盖 `project/hardware/`。脚本采用当前 Tcl 副本、原器件及构建参数，记录新报告；新构建完成仍要审查 CDC、DRC、setup/hold、资源和新 BIT/HWH/XSA，形成新来源摘要。不能把编译退出0当作板测通过，也不要求新实现位流与旧实现逐字节相同。

本次只验证构建计划和105项输入绑定，没有重复综合实现。封存构建的文件一致性可运行：

```powershell
python skill/fpga-artifact-check/scripts/verify_artifacts.py --root project --summary evidence/implementation/implementation_summary.json --sources evidence/implementation/built_source_hashes.json
```

## 5. 现场运行与测量

按 `docs/hardware_setup.md` 和封存现场说明逐级执行。CheckOnly 是离线文件检查；MonitorOnly 会真实访问板卡，不能在本次离线授权下自动运行。

先定义试验成功/失败/人工干预、计数和测量端点，再采集原始日志。传感到物理响应必须有可观察的执行器响应终点；通信单向测量要说明时钟同步。按 `skill/robotics-metrics/skill.md` 统计，填回 `metrics/metrics.csv` 的对应条件、次数和证据。原9张保存帧不能代替新的物理测量。

## 6. 回退

本次源码整理不改变原包。恢复完整旧版本须使用它自己的完整目录、模型和位流，不混用 p3 ABI340D 与 p4 ABI340E。历史 main 快照在 Git 提交 `964ee78c`，开发分支保持原状态。源码克隆中的外部资产缺口应通过合法资产恢复处理，不能用旧权重凑齐哈希。

## 公开运行入口

按 [运行资产获取说明](runtime_assets.md) 安装两份权重与七个 STL，再使用 `start_mode_ab.ps1 -CheckOnly -RuntimeOnly`。
