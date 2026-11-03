# v0.14.0 接口

新整机AUTO_RESTOCK=1，TASK ABI=0x340B；ARM/PLAN/VIS/MODEL保持3101/3203/3506/022267A9。只用同次构建的BIT/HWH/XSA与本版入口。

正常三色文件S4_BANKED_CANDIDATE.json仍为原340A数据格式并逐字节保留；新入口载入后将运行合同合并为340B，附加RESTOCK表。正常跟手使用原关键点bank0/1/2，原备用bank3改存补料关键点。补料时禁止混合插值，直接读取bank3。原段表仍在segment bank0，新增bank1共享同一段RAM；SEG_ADDR从7bit扩为8bit，bit7选bank。每bank仍最多64段，两word/段。配置写入只允许OFF/IDLE。

| 地址（TASK基址0x43C50000） | 含义 |
|---|---|
| STATUS +0x004 bit29 | 当前为自动复原任务 |
| +0x374 | 补料公共前缀描述符 |
| +0x378 / +0x37C / +0x380 | 红/黄/蓝各自尾段描述符 |
| 描述符bits5:0 /13:8 /21:16 | first / count / 原槽开爪关键点（前缀无开爪点） |
| +0x388 | 完成补料计数，HOME完成后增加 |
| EVENT bit14 | 补料完成事件；原bit11继续为PS_WRITE_BLOCKED |

新表46关键点/51段：共享前缀15段，三色尾段各12段。所有任务在PH_OUT完成，不进入PALM或跟手。预查检查原生限位、单次GRASP、单次原槽开爪和末端HOME；复原完成后才置库存，取消则保持空槽。原取消栈/PAUSE排空/CLEAR/LAST_DELIVERED机制复用。已开始开爪放回即设置released，后续FIST按旧释放后策略处理。

## 离线复现

```powershell
python -X utf8 -B scripts/test_mode_a_restock.py
python -X utf8 -B scripts/run_mode_a_restock_task.py --attempt local01
python -X utf8 -B scripts/run_mode_a_upgrade_hdmi.py --attempt local01
python -X utf8 -B scripts/run_mode_a_restock_integration.py --attempt local01
```

规划重算需现有D:/RobotSim/.venv/Scripts/python.exe（SciPy/NumPy）；默认读包内candidate/bank1：

```powershell
D:/RobotSim/.venv/Scripts/python.exe -X utf8 -B scripts/prepare_mode_a_restock.py --out board_evidence/replanned_restock
```

新目录内4个文件应与candidate/restock对应原始规划文件一致。Coppelia必须加载现有roarm_m3_phase3.ttt并停止，23001端口；verify_mode_a_restock.py --candidate candidate/restock --out 新目录 [--wire]进行真实网格几何检查。启动参数参见[Coppelia官方命令行](https://manual.coppeliarobotics.com/en/commandLine.htm)。本轮原始记录包含模型/桌面/相机/其他木块，未假定固定人手障碍；没有动力学和实物结论。

S4联测使用真实s4_task_regs表RAM/读流水、FSM和手势目标核，执行器接口明确为MOCK。实际MOVE导出的7路线/176段/8776采样在SMOOTH_PROFILE=1的生产S2逐轴精确对照；仅仿真采样周期缩短为512cycle，生产仍2000000cycle。MOCK暂停反馈为关节中点，停止前向前缀保留原N缩短到该LAST_DELIVERED，返回目标和N不改；这不是实物制动测量。

整机构建、独立网表检查、总结入口依次为build_mode_a_restock.py、inspect_mode_a_restock.py、summarize_mode_a_restock_impl.py。源码/模型/约束91项与同次硬件哈希绑定。构建路径a2已存在时需要在隔离副本中换尝试路径，禁止覆盖现有通过记录。资源必须每项不超过85%，setup/hold均非负，不以OOC相加代替整机结果。
