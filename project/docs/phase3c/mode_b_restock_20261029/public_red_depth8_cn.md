# 红块公共点抓取再下降8 mm

用户在首轮补回后反馈“在夹取时需要再向下8mm”。本修正只绑定该轮红块公共点(300,200)及其计划/实发结果，不套到橡皮、圆柱或其他位置，不重复累加原补偿。物体中心仍为桌面(300,200,15)，原返回中心仍为(651.879,257.801,15)mm。

新增`scripts/prepare_mode_b_restock_depth.py`根据原模型求出抓取臂目标下降8mm，保持XY。更深接触改变物体在夹爪内的位置，模型据此重新绑定刚体附件，再重算原位下降和退爪，保持原释放中心。原成功抓取指令仍在冻结源记录中，本轮源放回指令随接触深度调整，不能盲用旧关节终点。

修正前计划、7440请求实发结果和原三类审阅ZIP均保留。`review/`及`MODE_B_RESTOCK_REVIEW_20261029.zip`是本修正前的归档；本次轨迹、仿真、预演及实体记录以`artifacts/phase3c/mode_b_return_20261029/red_public_depth8_v1/`和本轮运行日志为准。

新整程13段/4夹爪事件、7543请求，名义运动150.78秒。Coppelia4.10检查7581样本通过，模型夹指最低点约5.01mm，物体仍保持桌面接触高度；这是刚体运动学/网格检查，不验证真实夹持力、摩擦或实体残差。实体结果须另记录，不改写计划内的未接受标志。

整段入口沿用现有脚本，仅替换计划/仿真路径。实物布置仍须先移走覆盖公共点的150mm承托物，红块按原公共点朝向摆好、原位空闲、空夹低HOME。完整命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\scripts\run_mode_b_restock.ps1" -Plan "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\phase3c\mode_b_return_20261029\red_public_depth8_v1\RESTOCK_PLAN.json" -Verification "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\phase3c\mode_b_return_20261029\red_public_depth8_v1\COPPELIA_VERIFICATION.json" -SerialPort COM5 -Move -EmptyGripperConfirmed -PublicAreaClearConfirmed -OriginalSourceVacantConfirmed -PublicObjectPlacementConfirmed
```

删除`-Move`可离线核对。源点及本轮修正的原始证据需保留在本机；该命令不启动识别相机或FPGA。位置残差只观察，通信或设备故障仍停止后续请求，无自动重发。
