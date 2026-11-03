# 模式B补回：首轮红块测试

本轮先验证已保存的红块记录：公共点中心桌面(300,200,15)mm，放回中心(651.879,257.801,15)mm。返回目标来自该次成功抓取记录，不是重新识别的新目标，也不是所有物体的固定返回槽。

## 实物准备

- TTL连接电脑，机械臂通12V电源；旧串口为COM5，本轮系统暂未列出任何串口，须以重新连接后的实际串口号为准。
- 机械臂空夹，停在已接受的低位HOME；原返回位置空闲，相机和底座保持原布置。
- 移走中心(285,195)、顶高150mm的承托物，腾出公共点及转运路线。公共点这次在桌面上，正常交付的高承托物不能留在此处。
- 将同一30mm红块中心放在桌面(300,200)。按[公共点摆放图](RED_PUBLIC_PLACEMENT.png)对齐一组边线，模型yaw约63.0°；方块另一组等价边线与+X夹角约−27.0°。公共点尚未实体校准，首轮结束后统一反馈对位和夹持结果。

## 当前完成的联调预演

`rehearse_mode_b_restock.py`将无通信状态机的9个阶段映射到实际13个运动段和4个夹爪事件。三类计划全部通过，完整指令数为红块7440、橡皮3935、圆柱7517；库存只在释放、退爪、HOME和停放闭合全部模拟完成后恢复，再次触发需背景重武装。

这些完成事件在离线预演中模拟，未发送到机械臂或FPGA，也不表示物体已被放回。尚无串口，因此本轮没有状态采集或运动。

## 测试入口

以下均为完整路径，不依赖PowerShell当前目录。先连接TTL，再进行只读状态采集（仅发送T105，不发送运动）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\scripts\collect_mode_b_serial_pose.ps1" -Port COM5 -PoseId RESTOCK_RED_PRE -SampleCount 5
```

若串口号变化，替换COM5。入口会核对新鲜状态，不能从未知姿态直接执行该轨迹。先确认上述实物布置，状态与低HOME匹配后，完整补回入口如下（不再拆成手工运动步骤）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\scripts\run_mode_b_restock.ps1" -Plan "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\phase3c\mode_b_return_20261029\plans\red_cube\RESTOCK_PLAN.json" -Verification "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\artifacts\phase3c\mode_b_return_20261029\plans\red_cube\COPPELIA_VERIFICATION.json" -SerialPort COM5 -Move -EmptyGripperConfirmed -PublicAreaClearConfirmed -OriginalSourceVacantConfirmed -PublicObjectPlacementConfirmed
```

仅预览时删掉`-Move`；预览不会访问串口。运行沿用残差观察、不因小幅关节误差停顿；通信和设备故障仍停止后续提交，不自动重发。

结束后统一反馈：是否夹起并放回原位、偏差方向及毫米数、转运有无滑落、退爪和HOME是否正常。尚未通过的公共点夹取可单独修正，不覆盖之前成功源点记录。

## 队友可复用的阶段映射

| 状态意图 | 按顺序执行的运动段或夹爪事件 |
| --- | --- |
| APPROACH_PUBLIC | HOME_OPEN → INNER_OPEN → BUFFER_OPEN → PUBLIC_HIGH |
| DESCEND_PUBLIC | PUBLIC_DESCEND |
| CLOSE_PUBLIC | GRASP_PUBLIC |
| LIFT_PUBLIC | PUBLIC_LIFT |
| RETURN_SOURCE_HIGH | RETURN_BUFFER → RETURN_INNER → SOURCE_HIGH |
| DESCEND_SOURCE | SOURCE_DESCEND |
| RELEASE_SOURCE | 先登记RELEASE_SUBMITTED，再执行RELEASE_SOURCE并等待完成 |
| WITHDRAW_SOURCE | SOURCE_EXIT_CLEARANCE → SOURCE_EXIT_UP → SOURCE_EXIT_RECENTER |
| HOME | HOME → PARK_CLOSE，全部完成后恢复程序库存 |

表中省略运动阶段统一的RESTOCK_前缀。真实执行器须在相应段/事件实际完成后才提交带task_id和completed_phase的DONE；预演不能替代设备完成回报。FPGA/网页桥接仍待实现。
