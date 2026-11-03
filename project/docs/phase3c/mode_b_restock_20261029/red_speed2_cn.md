# 红块补回运动提高到当前2倍

下降8mm修正版已获用户“全程正常”接受，独立`ACCEPTED_DEPTH8.json`绑定该轮计划和实发结果。本版以其为唯一基线，将补回运动速度提高到当前2倍；不叠加第二次深度修正，也不改变原物体坐标、返回中心、刚体附件或4个夹爪事件。

`scripts/prepare_mode_b_restock_speed.py`重新采样已接受的关节曲线，保持13段及所有端点，周期20ms。运动T102使用spd640；按加速倍率计算的acc320限制为254，同时同步收紧轨迹加速度界至304.8°/s²、速度界48°/s。短段会受加速度约束，名义运动时间150.78→76.62秒；夹爪动作、停留和串口反馈仍耗时，实际整程不能直接按时间减半估算。

26项软件检查通过，Coppelia4.10检查3873个精确原生样本无网格碰撞。仿真不包含摩擦、夹持力或伺服动力学，新速度已获用户“一切正常”实物接受，独立ACCEPTED_SPEED2.json绑定原计划与实发结果。之前的2倍参考运动现相当于4倍参考运动，仅此红块补回试验使用，不自动更改三类原抓取交付流程。

计划、仿真、状态预演、软件及执行证据目录：`artifacts/phase3c/mode_b_return_20261029/red_speed2_v1/`。原8mm成功基线和旧审阅ZIP保持；新速度不回写原计划的接受标志。

实物条件同上一版：移走覆盖公共点的150mm承托物、红块在公共点(300,200)按原朝向摆放、原位空闲、空夹低HOME。整段入口如下：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\scripts\run_mode_b_restock.ps1" -Plan "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\phase3c\mode_b_return_20261029\red_speed2_v1\RESTOCK_PLAN.json" -Verification "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\phase3c\mode_b_return_20261029\red_speed2_v1\COPPELIA_VERIFICATION.json" -SerialPort COM5 -Move -EmptyGripperConfirmed -PublicAreaClearConfirmed -OriginalSourceVacantConfirmed -PublicObjectPlacementConfirmed
```

删除`-Move`为离线检查。运行继续观察位置残差，通信/设备故障仍停止后续提交，无自动重发。取消接续须从已知停稳节点另行规划并仿真，既有取消规划器按原参考倍率保守重计时，不自动继承本试验的提速接受。

实际整程204.040秒，上一版327.877秒，缩短37.77%；13运动段实发时间合计120.592秒，名义76.62秒，剩余发送和反馈开销是下一轮执行层优化目标。当前串口已关闭，未自动再次运行。
