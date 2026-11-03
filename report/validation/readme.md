# 本次实际验证与复跑命令

`commands.json` 记录退出码、预期退出码、耗时和对应原始输出；`summary.json` 是当前汇总。原包结果与本次重跑分别记录。两个故意拒绝案例的退出码1是预期结果，不记作被测环境通过。

2026-11-01后续同步：当前p4.1已用户现场实测验收，状态USABLE_USER_ACCEPTED，精简证据在 `report/acceptance/board_test_20261101.json`。下述是发布整理阶段实际运行的离线检查，不能将“这些检查没有访问硬件”理解为“当前版本从未实测”。旧输出中的physical_closed_loop=NOT_RUN属于状态同步前的历史输出；当前以新增验收和更新后的仓库检查输出为准。

## 干净工具环境

当时在隔离工作区旁新建不含pip/第三方包的Python3.12 venv，检查NumPy/Torch/OpenCV/PyYAML都不存在，再运行：

```powershell
python -m venv --without-pip C:/temporary/clean_skill_env
C:/temporary/clean_skill_env/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -v
```

32项测试输出在 `new_tool_tests.txt`。三个skill整目录复制到仓库之外，执行真实脚本：环境工具检查合成model.json/不透明字节哈希；FPGA工具核对另一套filter.sv及合成BIT/HWH/XSA；指标工具读取success/failure/intervention各一行的CSV。合成产物从不供板卡下载。干净环境请求HIP时因无torch而明确拒绝，输出 `clean_hip_unavailable_rejected.txt`。

每个skill内的 `references/validation.json` 保存可随目录携带的摘要；这些结果证明标准库工具部署和输入合同复用，不是整机迁移成功。

## 封存项目复核

Git子集缺190项资产时执行完整检查，预期退出1；日志 `missing_assets_rejected.txt`。使用合法持有的指定ZIP调用 `tools/restore_assets.py`，恢复190项，再完成4,521项逐成员核对，日志 `restore_original_assets.txt`、`restored_complete_inventory.txt`。

在已存在的原ROCm应用解释器下，从 `project/` 运行：

```powershell
python -X utf8 -B scripts/check_mode_ab_package.py
python -X utf8 -B scripts/run_mode_ab.py --check-only
cd scripts
python -X utf8 -B -m unittest -v test_mode_ab_control test_mode_ab_diagnostics test_mode_ab_family test_mode_ab_http test_mode_ab_native test_mode_ab_planning test_mode_ab_shared_red test_mode_ab_snapshot test_mode_ab_startup_map test_mode_ab_uploads
cd ..
node scripts/test_mode_ab_ui.cjs
```

67项PC测试、10项UI检查通过，包含3项实际生成Tcl的启动映射测试。不访问设备。原包记录78项不同Python测试覆盖另含历史门禁，本次没有把它们全部重跑。

## 实际环境、硬件证据与指标

从仓库根用既有ROCm解释器运行：

```powershell
python -X utf8 -B skill/amd-pc-deploy/scripts/probe_environment.py --requirements project/requirements_mode_ab_lock.txt --model-json project/model_package/mode_b/detector_background_v2/model.json --model-json project/model_package/mode_b/surface_eraser_repair_v1/model.json --require-hip
python -X utf8 -B skill/fpga-artifact-check/scripts/verify_artifacts.py --root project --summary evidence/implementation/implementation_summary.json --sources evidence/implementation/built_source_hashes.json
python -X utf8 -B skill/robotics-metrics/scripts/summarize.py --csv metrics/logs/saved_frame_pipeline.csv --kind latency --start "Saved frame enters perception pipeline" --end "Perception result ready in host memory" --conditions "Original nine saved frames; see metrics/conditions.json" --evidence-kind saved_input
python -X utf8 -B skill/robotics-metrics/scripts/summarize.py --csv metrics/logs/saved_frame_surface_inference.csv --kind inference --conditions "Original nine saved frames, first call included; see metrics/conditions.json" --evidence-kind saved_input
```

依赖精确匹配、两模型哈希及HIP实际设备算术通过；没有重测模型推理。105项硬件输入、同次BIT/HWH/XSA及封存时序/CDC/DRC摘要通过。保存帧分位数和原报告一致，分割拆分保留首次调用，不能用暖态流水数值覆盖首次模型调用。

另运行 `tools/build_fpga.py` 默认计划模式，确认原参数与外部输出路径；未启动Vivado。三项技能用skill-creator的 `quick_validate.py` 分别检查，均输出 `Skill is valid!`。这些工具校验不证明现场恢复、真实任务成功率或第三方许可已经完成。
