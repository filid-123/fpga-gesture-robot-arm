# Gesture 工程当前上下文

2026-10-29 v0.14.0空槽自动复原离线通过、完整包待封：用户确认v0131显示正常；公共木块中心D=(300,200,15)mm、30mm同桌面，三色空槽数字自动取回原槽/HOME后恢复库存，有货仍原交付。复原不需PALM/跟手；FIST开爪前逆退公共点/HOME保持空槽，提交开爪后完成退出，背景重武装防持续数字连发。ABI340B/bit29/段bank1/KPbank3/事件14计数388；正常表340A与原模型/路径/1320-66-50Hz/observe_all/720p冻结。新S4真实RAM7组、旧流程7组、实际S2 176段8776采样、Coppelia153862采样0碰撞、70源码PC/终端、HDMI7项/12VGA15项通过。最终a2为26568LUT/23188FF/113BRAM/32DSP，最高80.714%<85%，WNS/WHS+.302/+.009ns，114CDC全safe，DRC0错误/44既有警告；91输入与BIT/HWH/XSA绑定、独立网表通过。新实物NOT_RUN；D5预接，新入口run_mode_a_restock.py，同进程先交付成空槽再公共点放块做原数字，勿按r/y/b替代。新分支codex/mode-a-auto-restock-20261029，手册docs/mode_a_restock_v0_14_0/README_CN.md。


2026-10-29 v0.13.1最终完整包已封存：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.13.1_20261029_HDMI720p_DisplayFix_Final，46992811B/3103文件，ZIP SHA256 5648c8978f7be9f3dd0961866af96081795d21da34eea7dbb4b9cc38c58fecf4，源码检查点f0fab40eb8888707756fc243afec216ebd348943。1280×720/60Hz居中画布、四路匹配串行器及坐标ROM流水；46PC/13终端、全成员SHA/CRC、4显示证明98源哈希绑定通过。整机26052LUT/23024FF/113BRAM/32DSP，最高80.714%<85%，WNS/WHS+.222/+.019ns，111CDC全部safe，91构建输入/BIT-HWH-XSA绑定。三色路径/速度/Rain模型/PALM/FIST冻结，终端跨采样标签KeyError修复。新显示器/实物NOT_RUN，D5启动前预接，run_mode_a_upgrade.py先monitor-only30秒检查布局。完整包/图像/原始报告留本地，源码/手册/非原始证据推codex/mode-a-hdmi-alignment-20261029。


2026-10-29 v0.13.1 HDMI720p离线实现通过、完整包待封：codex/mode-a-hdmi-alignment-20261029基于9077a543。旧照片整幅横向环绕，旧完整串行接收正确但clock/data严格同相位失败，根因尚未实板确定。改1280×720/60Hz+居中960×720画布、四路匹配串行器；a1组合缩放时序失败保留，a2同步坐标ROM/同拍同步链通过。整帧921600像素零差、12VGA生产集成、6显示单项、46PC/13终端通过；62非HDMI RTL、Rain模型和全部路径/速度/手势规则冻结，额外修复终端RETRACE跨采样标签KeyError。新整机26052LUT/23024FF/113BRAM/32DSP，最高80.714%<85%，WNS/WHS+.222/+.019ns，111CDC安全，91构建输入/BIT-HWH-XSA绑定及网表审查通过。继承XDC if解析警告记录并独立复核异步组。新显示器与实物NOT_RUN，D5启动前预接，先monitor-only30秒显示检查。


2026-10-28 v0.13.0 最终完整包已核对：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.13.0_20261028_ParallelHD_ContinuousSmooth_Final，46782973B/3060文件，ZIP SHA256 805fc1da0383e9c99c2b02d22931c7eb3f4b70b3bb3ad2e0682a5ffae8089173，源码检查点92ce4a5522fbdb47c469d821cd4d43636a37cb7a。已补齐父包4份旧A残差基准，包内独立重算33规划文件逐字节一致，45PC/13终端、check-only、成员SHA/ZIP CRC及89构建输入/BIT-HWH-XSA绑定通过。整机26159LUT/23021FF/111.5BRAM/32DSP，最高79.643%<85%，WNS/WHS+.270/+.021ns，111CDC安全。新实板/显示器测试NOT_RUN；D5启动前预接，run_mode_a_upgrade.py先monitor-only15秒再闭环。旧v012、失败构建及首次封包未交付记录保留。源码/文档/非原始证据推codex/mode-a-v013-upgrade-20261028，完整ZIP/图像/详细规划在本地。


2026-10-28 v0.13.0 首次封包运行与输入校验通过，包内重规划发现遗漏4个旧A残差基准，已保留PackagingAttempt_a1_NOT_FOR_DEPLOYMENT，补齐后重新封包。原首次封包记录：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.13.0_20261028_ParallelHD_ContinuousSmooth_Final，46770243B/3056文件，ZIP SHA2567bb4196160198f88aec54c3bf58fcd43029838c5b5bf76a2f397fed38ef8e267，源码检查点eaf54597245fd587197e0469c52a101c97bdea46。包内45PC/13终端、独立入口check-only、所有输入/成员SHA及ZIP CRC通过；同次89硬件输入/BIT/HWH/XSA绑定，整机26159LUT/23021FF/111.5BRAM/32DSP（最高79.643%，各类<85%），WNS/WHS+.270/+.021ns，111CDC安全。CNN26样本精确且4.68486ms、真256×192单框HDMI、五次Q32标量、有界细分Y及片上事件/六轴记录完成；65位置1224990 Coppelia采样和59316改向归还采样0碰撞，45PC/13终端、12真实VGA/ML显示集成通过。新入口scripts/run_mode_a_upgrade.py，D5启动前预接，先monitor-only15秒再三色闭环；PALM锁定盲交付/FIST归还/库存/observe_all保留，无新增实体采样，ESP32未改。新实板/显示器测试NOT_RUN，完整ZIP/图像/规划原始数据在本地；源码/手册/非原始证据推codex/mode-a-v013-upgrade-20261028。


2026-10-28 v0.13.0 五项升级离线开发与整机实现通过，完整包待封：独立codex/mode-a-v013-upgrade-20261028基于85b4bcaf。分类卷积双输出通道共享双读ROM，Rain模型不变，26冻结样本逐层/logit/margin精确，750170→468486周期（100MHz4.68486ms）。真实256×192Gray8预览与单框/三卡片、L/C/A毫秒页脚；三锚点原坐标计算64细分Y、约3.75mm死区/新鲜Locator，PALM锁定盲交付与FIST1s归还原槽/HOME保持。五次Q32标量复用顺序算术单元，1320/66/50Hz，普通段速度上限2倍/近手及夹爪约1.5倍，中心三色插补29.06/29.14/29.74s，六轴误差observe_all。65位置Coppelia精确/四位小数共1224990采样、取消/改向回放59316采样0碰撞；594段29658实际S2回放、三锚点28269采样与暂停/反压、45PC/13终端、12真实VGA帧及HDMI/UNISIM单项通过。a5同次整机26159LUT/23021FF/111.5BRAM/32DSP（最高79.643%，全部<85%），WNS/WHS+.270/+.021ns，TNS/THS0，内部未约束0，111CDC全safe，Gray skew9.189/9.227ns，DRC0错误44建议(4类)，89构建输入与BIT/HWH/XSA绑定/独立网表通过。D5启动前预接，PYNQ D1/D0原TTL；ESP32未改，无新增实体采样。新显示器和实物闭环NOT_RUN；旧v012与失败构建保留。


2026-10-28 v0.12.0 HDMI完整包已封版：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.12.0_20261028_HDMI_Clean_Final，50649795B/3415文件，ZIP SHA256 c5285dcbe1b836672e0251287eed30ac9399c74568efea13bd09f4ee8c672708，源码检查点70c5875b741f3f775ca901ce18495506fdc27614。新BIT/HWH/XSA及85构建输入绑定，包内48PC/13终端、独立入口check-only、全部成员SHA/CRC通过；模型/全部路径和控制原语冻结，除S4顶层只读tap外同一。6项显示/真实UNISIM仿真、a8十真实VGA帧/最终匹配图像及PALM快照通过（长整机回放串行器sink、实际串行原语独立验证）。22332LUT/20430FF/72.5BRAM/26DSP，WNS/WHS+.409/+.035ns，87CDC全部安全。HDMI_OUT→显示器；D5启动前预接，run_mode_a_hdmi.py先monitor-only15秒再闭环。新显示器/实物闭环NOT_RUN，完整ZIP/预览图在本地，源码/文档/非原始证据推codex/mode-a-hdmi-20261028。

2026-10-28 v0.12.0 HDMI简洁显示版开发中：用户要求参照Phase2，只有一个最终框，显示手势/无手势、机械臂命令和执行状态，注重简洁美观。独立codex/mode-a-hdmi-20261028基于12010faa；新增PL灰度384×288画面与中文三卡片、反馈在线标志，640×480/60Hz HDMI OUT。保留v0111模型、三档路径/速度、PALM中心条件/FIST归还/无精度门槛/预接D5；控制源逐项一致，S4顶层只新增只读tap。实际a3新整机22332LUT/20430FF/72.5BRAM/26DSP，100MHz WNS/WHS+.409/+.035ns，TNS/THS0、内部未约束0、87CDC全部safe、Gray skew9.077/9.029ns、DRC0错误35警告(4类)，85构建输入与BIT/HWH/XSA同次绑定通过，新增HDMI MMCM/6 OSERDES/16显示RAMB36及25.2/126MHz独立检查通过。48PC、5显示单项和实际UNISIM串行器通过；整机十帧回放及最终匹配图像/确认PALM快照在a8通过（长回放串行器sink，生产原语独立UNISIM通过）。硬件/显示器实测NOT_RUN，最终包待封。

2026-10-28 v0.11.1最终完整包已核对：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.11.1_20261028_PalmCenterGate_Final，50155203B/3344文件，ZIP SHA256 a9307055f98a21e3469434a2ac9c7b7a8d7f934260a20e996b77098fc5f0bc0b，源码检查点5a47d6dc4a61524684ea476c23b1f34479432453。包内45PC/13终端、独立新入口check-only、全部成员SHA/ZIP CRC通过，2486冻结文件及74构建输入与v011逐字节一致；复用原BIT/HWH/XSA、模型、全部三色轨迹/速度和S2/Coppelia证据。新适配器+core+S4共6项离线回归通过（mock运动链），新实板NOT_RUN。D5运行前预接，入口scripts/run_mode_a_palmfix.py，使用手册docs/mode_a_palmfix_v0_11_1/README_CN.md。完整ZIP与原始日志保留本地，源码/文档/非原始证据推codex/mode-a-palm-window-fix-20261028。

2026-10-28 v0.11.1 PALM中心区域修订：已查v0.11.0 follow_board_02，1242快照约202.10秒正常退出，done0/cancel2，通信/规划错误0；最后PALM分类已确认，同区PRE等待超过2秒，但raw框下缘126～128超过旧整框Y16～112，window始终0、PALM计时0。v011切raw后保留旧整框/角点限制是回归。新codex/mode-a-palm-window-fix-20261028基于ac151d7d，仅数据/软件改适配器X/Y0～128、角点128，保留3帧PALM；实际空间由S4新鲜已接受中心cell控制，PRE2秒/PALM500ms/80ms2帧定位/250ms新鲜度保持。三个档位各完整盲交付/释放/HOME及中心越界/陈旧拒绝、旧配置复现共6项实际适配器+core+S4 XSim通过（运动mock）；45PC通过。硬件ABI3409、模型、路径/速度/归还均冻结复用v011，待完整封包核对；新补丁实板NOT_RUN。手册docs/mode_a_palmfix_v0_11_1/README_CN.md。

2026-10-28 v0.11.0三档修复完整包已完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.11.0_20261028_LocatorFollow3_Fast_Final，50008801B/3315文件，ZIP SHA256 d43c4b669cf3da663218e8006ad8f18124b2d37cec60ed45b59e782d15963c49，源码检查点681b185975b4745a3753c9ec84ec7886b0fc1439。新ABI3409整机21539LUT/19842FF/55.5BRAM/26DSP，100MHz WNS/WHS+.414/+.018ns，TNS/THS0、内部未约束0、28CDC安全、Gray skew余量9.168/8.902ns、DRC0错误/35警告(4类)。包内40PC/13终端、25项规划逐字节重现、74构建输入与同次BIT/HWH/XSA绑定、独立入口check-only、逐成员SHA/ZIP CRC通过。S2精确57285采样、Coppelia精确/舍入114570采样0碰撞，10真实VGA帧及原始Locator中心不受分类去抖/EMA阻塞的整机断言通过。独立定位80ms/2帧、Y54/74三档/120mm跨度、途中PAUSE排空接续与48ms局部停稳、660/33整体约+10%、预接D5和无精度门槛；ESP32未改。新实板/实际延迟/PA现场复测NOT_RUN。只用Final后缀完整包，旧版及失败记录保留。

2026-10-28 v0.11.0 Locator独立三档修复开发中：用户采用独立新鲜定位去抖、收窄选区并要求明显运动、缩短局部段与少量整体提速，ESP32先不处理。新codex/mode-a-locator-follow-20261028基于ac4daec6；三档Y54/74分界，H=(285,135/195/255,175)、PRE=(350,155/215/275,180)，跨度120mm，bank3同bank2备用不启用。新HAND_ALIGN_LOCATOR参数/ABI3409，原始同帧Locator中心和检测有效性独立80ms/2帧/250ms新鲜度，PALM/FIST语义仍按原确认。对齐中新目标PAUSE→等pending0→CLEAR→LAST_DELIVERED实际角差重定时；局部48ms停稳，整体规划上限+10%、660/33/50Hz，无到位精度门槛。JTAG每个mrd/mwr绑定唯一Cortex-A9#0 target-id，无自动运动写重试。40PC、实际S4三色三档/六方向/改向/排空/原槽归还/故障、独立定位/竞态/旧默认、真实115200新速度通过；S2共57285精确采样、Coppelia114570采样0碰撞。a1角差组合链时序不足主动终止保留，已拆流水并在a2重实现；最终硬件/包仍待核对，实板NOT_RUN。

2026-10-28 v0.10.0完整四区包已完成：D:\FPGA_Projects\Gesture\deliverables\Gesture_ModeA_FPGA_v0.10.0_20261028_FourZone_FixedThreshold，49551520B/3185文件，ZIP SHA256 0fd038d9ff8ba730ff0979cb48f1b5eb5701217ee69bb6bc4e21916e48d61892。源检查点adfd9fefd602a88ffae1aa54867f197f229b8976；包内33PC/13终端、25项规划导出逐字节重现、74输入与同次BIT/HWH/XSA绑定、独立check-only、全成员SHA/ZIP CRC通过。新整机20999LUT/19728FF/55.5BRAM/26DSP，WNS/WHS+.202/+.022ns，内部未约束0，28CDC安全，Gray skew余量8.981/9.151ns，DRC0错误/35警告(4类)。不需掌位采样或hand-map文件，D5运行前预接。四区实体NOT_RUN，第一稿/v091保留。

2026-10-28 v0.10.0四区最终候选开发完成、封包待核对：用户确认约390×390mm视域、画面上方→桌面+Y；取消实体采样，固定框中心Y40/64/88分界，原128图内容16～111。H=(285,115/170/220/275,175)，PRE=(350,135/190/240/295,180)，H_CLEAR z195；扩大至160mm跨度，X因可达性收回。最上区H倾角35°，随已有退爪175→195mm恢复40°，消除a2约.07mm掌面相交；失败证据保留。四bank/16配对NNa、运动中最新候选邮箱、120ms/3帧与局部160ms；PALM/FIST/库存/600-27/50Hz/无精度门槛/预接D5保持。新ABI3408整机20999LUT/19728FF/55.5BRAM/26DSP，WNS/WHS+.202/+.022ns；74输入绑定。S4全3色×4bank及十二方向切换/途中归还、寄存器/接收确认竞态/旧默认/真实UART通过；实际S2五组82600精确采样，Coppelia正常四bank和FSM回放精确/舍入165200采样0碰撞；10真实VGA PALM帧生产去抖final-top通过。Rain模型和部署视觉2400文件与v091逐字节同一，既有26样本模型/定位/流水证据复用；本轮四区实板NOT_RUN。第一稿和v091包保持；源码在codex/mode-a-four-zone-20261028，完整包在交付区封包后更新记录。

2026-10-28 v0.9.1完整包已完成：D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.9.1_20261028_ImageY_DeskY，46807974B/3042文件，ZIP SHA256 e60a8403181b0282d508ef9602695bf36e6dd3d881066c196064e66fa9b41fcd。包内34PC/13终端、19项规划导出逐字节重现、全74硬件输入和冻结模型/RTL/约束/BIT-HWH-XSA逐字节复用、独立入口check-only、逐成员SHA/ZIP CRC通过。新方向实板NOT_RUN，需按前/中/后掌位生成IMAGE_Y/DESK_Y映射，旧左右映射不复用；D5继续运行前预接。


2026-10-28 v0.9.1方向调整：用户明确改为画面上中下→桌面前后Y±20mm，高度保持。H=(240,135/155/175,175)，PRE=(320,155/175/195,180)，H_CLEAR同Hxy/z195；三槽/B/相机/1.5倍600-27/50Hz/PALM锁定盲交付/FIST1s原槽归还/无精度到位门槛保持。原PL矩形LUT支持Y选区，74构建输入及模型/RTL/约束/BIT-HWH-XSA与v090逐字节一致，复用ABI3407和原实现证据，无新Vivado。新图像Y采样工具按前/中/后掌位自动处理图像Y反向，拒绝旧左右映射；图像X全宽不参与选档。三组47KP/59段/最大栈23，局部N44/Na11(0.88s)。新S4/LUT/AXI、新三组实际S2和FIST回放共48762精确采样，Coppelia精确/舍入97524采样0碰撞，34PC/13终端通过。v091完整包待本轮封包核对，新方向实板NOT_RUN；v090及第一稿封存保持。


2026-10-28 v0.9.0最终完整包：D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.9.0_20261028_HandAlign3_Final，46197925B/2974文件，ZIP SHA256 0b70598458457ab38f929c88fcf339b10ee8789848dd7db2f72f05234fca6745。32PC/13终端按完整包通过，19个规划/表/采样/CSV逐字节重现；74整机构建输入、Rain冻结包、同次BIT/HWH/XSA、全成员SHA/ZIP CRC通过。第一稿封存标签与ZIP不变，新实板NOT_RUN。封包首个未完成目录已标INCOMPLETE_NOT_FOR_DEPLOYMENT，不供测试；只用Final后缀版本。


2026-10-28 v0.9.0离线验收完成、封包中：a2同次整机20657LUT/19077FF/55.5BRAM/26DSP，100MHz WNS/WHS +.232/+.019ns，TNS/THS0，内部未约束0，28CDC safe，Gray双向skew余量8.987/8.762ns，DRC0错误/35警告(4类)。74输入及BIT/HWH/XSA同次绑定通过。V3 classifier/locator各26样本整数精确，完整DVP→ROI→分类26样本逐阶段精确；12帧连续流12结果、7次重叠且每个定位/ROI/logit/id/time精确，10真实PALM帧覆盖生产300ms后确认qualified/event，未缩短生产计时。S4三bank/十次全方向切换/两种途中FIST/原槽开爪/HOME/库存/陈旧帧/D5/COMM、AXI配置锁、旧默认归还、真实115200600/27/50Hz通过；实际S2四组共49330采样精确，Coppelia正常三bank和回放精确/舍入总98660采样0碰撞。32PC/13终端通过。新实板NOT_RUN；第一稿标签/旧ZIP保持，V2完整包封包复现和SHA检查后记录最终文件名/哈希。


2026-10-28 第二版v0.9.0开发中：独立codex/mode-a-v2-handalign-20261028，以第一稿标签b0de57bb为基线，选择性适配硬件优化分支88de55d2（不合入其旧模型/ABI/取消/UART策略）。新增ABI3407、3x64关键点bank/common59段、PL像素区域映射与有限三位置对齐，H220/240/260、PRE300/320/340、其他坐标/高度/600-27速度不变；PALM接受区域并停稳等PRE2s后连续500ms锁定盲交付；FIST1s偏侧归还经中央PRE接回原槽/HOME。局部对齐不压栈，槽/回退语义沿用。初次优化移植G1/G2误带旧常数被整数向量检出，a1整机构建主动终止；已恢复Rainv3常数，locator26样本逐层精确/1647640cycles通过，当前a2整机实现及全流水线验证中。新软件提供D5预接、ARM0三位置PALM只读采样、静态像素图一次配置；运行决策均在PL。实板NOT_RUN，最终包/资源时序尚待本轮实现完成，旧第一稿不覆盖。


2026-10-28第一稿封存与第二版授权：用户明确封存当前已通过v082为“第一稿A模式闭环版本”，README末尾原样附底座左直延56、物块左下角(53,23.5)/(66,22.5)/(58.7,29)、相机(19.5,19.5,33.3)注释；原始数字不改写，备注不替代运行坐标。用户已授权第二版结合codex/fpga-hw-opt-20261026开发，并确认有限区域跟手、以H(240,155,175)为中心左右各20mm三位置、PALM锁定后盲交付，速度/交付高度/FIST原槽归还保持，第二版沿用已通过坐标。上一条“本轮不开发”限制已由此授权替代。第一稿独立封存/标签mode-a-closed-loop-v1-20261028；第二版在新独立工作树适配，不覆盖第一稿。

2026-10-28 v0.8.2最新实测补充：用户报告通过，已只读核对最终board_04（01:07:57～01:14:12本地）2375遥测，OPERATOR_SESSION_ENDED/error null，done3/cancel4；黄/蓝/红各交付一次，4次取消均回IDLE并恢复槽库存，传感器/PS/CPU/自建服务正常恢复。末尾ONE/TWO/THREE仍分别有22/93/47份有效确认样本，但三次交付后stock000，FPGA以EMPTY_SLOT拒绝，末尾refused计数7、fault NONE/arm_errors0/feedback errors与timeouts0；手动摆回块不会自动补库存，同一会话需终端r/y/b确认、再回背景重新选物。此前board01 D5低、board02 ARM_FAULT、board03和重启后只查询UART_FRAMING均保留，最终正常不证明其根因已修复。新实测汇总board_evidence/mode_a_cancel_shift_v082_a1/FIELD_BOARD04_RESULT.json及docs/mode_a_cancel_shift_v0_8_2/FIELD_RESULT_CN.md；下文NOT_RUN为封包当时状态。用户限定本轮仅答复/记录测试结果，不继续开发。只读核对优化分支codex/fpga-hw-opt-20261026@88de55d2：离线优化候选；HandAlign核心未接S4动作，旧E4C43D44/ABI3403/旧UART策略不能直接替换现v082，不合并、不改运行代码、不上板。

2026-10-28 v0.8.2归还与PRE平移：用户报告v081通过，确认FIST改为归还原槽/开爪/抬升/HOME并恢复槽，只移PRE到(320,175,180)，B/H不动。已读v081 board_01三色done=3、正常退出/恢复；第四次红块FIST持物HALT为旧CFG HOLD位，不是通信故障。新CFG000e8106→000e8102清HOLD，表hold_policy=false，复用现有PL回退栈/ABI3406和同次v080硬件；1.5倍速度600/27、20ms、PRE2s/PALM0.5s/FIST1s、盲交付和无精度门槛保持。新PRE朝向40°不变，B20°与H40°；三色前14段目标/时间、H终点/释放/退爪/HOME保持，仅到PRE/到H重解，43KP/55段/栈19。28PC/13终端按完整包复验；实际FSM原生表三色PRE/递送途中/未持物/夹取中取消归还、开爪位置/库存/HOME、短FIST/释放后忽略及回退中D5/通信检查通过。新S2正常165段11925采样及FSM12场景304段20132采样精确通过；相应Coppelia精确/舍入各两组总64114采样0碰撞。FSM运动link为mock、tick32cycles；S2 TB周期512cycles，生产仍20ms；五个mock停止前缀保守重放，不作实机制动动力学声明。新入口docs/mode_a_cancel_shift_v0_8_2/README_CN.md，完整本机包Gesture_ModeA_FPGA_v0.8.2_20261028_CancelReturn_PRE320；新取消/新PRE实板NOT_RUN，旧通过包/标签保留，开发端未开实体接口。最终完整包45160843B/2798文件，SHA256 682bf4468e6b3fc2f5332716640cc1a0d592ec68b60814e66368391d71b7a5e9；包内28PC/13终端、规划表逐字节重现、2385项冻结输入/70构建输入/同次XSA绑定与ZIP校验通过，见board_evidence/mode_a_cancel_shift_v082_a1/VERIFIED_SUMMARY.json。

2026-10-27 v0.8.1速度1.5倍：用户报告v0.8.0测试通过，要求再提速1.5倍。只读v080 board_01日志累计done=2，末尾D5_PERMISSION停止且传感器/PS/CPU恢复CONFIRMED；不把此会话结束错误写成新运动失败，也不推断已统计三色成功率。新软件/轨迹候选按v080每段N向上取ceil(N/1.5)，保持20ms50Hz；速度33/45/18/30deg/s（普通/夹爪/近手/释放），加速度99/135/54/90deg/s2，原生600/27覆盖。固定352/800ms、PRE2s、PALM0.5s和FIST1s不变，PALM仅PRE一次触发后盲交付，D5预接自动启动和无位置门槛保持。全部9路159段几何/原生目标、CNN、RTL、约束和70项构建输入一致，复用v080同次BIT/HWH/XSA/ABI3406，不重建硬件。新速度25PC+13终端通过；实际S2 RTL以生产N/Na/VMAX/AMAX比对159段11595个六轴样本（仅TB周期512cycles加速），真实115200后端600/27九命令50Hz/三查询324B反馈通过；Coppelia精确/命令舍入各11595采样0碰撞。新三色纯插补33.14/33.26/34.86s，含原固定停留39.316/39.436/41.036s，另加PRE/PALM/人工及启动。入口docs/mode_a_speed15_v0_8_1/README_CN.md；完整本机包Gesture_ModeA_FPGA_v0.8.1_20261027_Speed1p5，源码/证据推个人分支；新速度实板NOT_RUN、旧通过包保留。最终完整包44002580B/2741文件，SHA256 8d2f39507732bb96a031bbc989e10203b7b9f5a49696dfc3566fc28f6d987f03；包内25PC/13终端、规划表重生成逐字节、2385项冻结输入及全成员/ZIP校验通过，详见board_evidence/mode_a_speed15_v081_a1/VERIFIED_SUMMARY.json。

2026-10-27 v0.8.0 新交互与加速：已核对v072最新board_03(1768遥测/完成0)。黄块PRE实际等待1.407s，途中失掌约0.5s触发旧BLIND→HALT持物，后续341份PALM不能恢复；短FIST也曾取消红块。按用户最终明确：PALM只在停在PRE后触发一次，之前忽略、确认后盲递送/开爪/退爪/回HOME。新HANDOVER_V2=1/ABI3406，FIST连续1000ms，其他/无效归零；PRE至少2000ms再确认有效窗口PALM连续500ms，无等待超时；途中不再以PALM/失掌限制动作。FIST仍普通取消，未夹取回退恢复槽，持物未释放HALT保持夹紧且PALM不恢复，提交释放后忽略普通取消。D5运行前接好自动启动、无位置精度门槛保持。三色9路159段几何/原生关键点与v070逐项相同，只重定时：普通22/44、夹爪30/60、近手12/24、释放20/40deg单位，T102400/12，20ms。新FSM/完整S4-S2四例/实际115200/旧默认回归共选定7次通过，23PC+13终端按完整包复验；精确/舍入各17286Coppelia采样0碰撞，额外空手接HOME227采样0碰撞。新整机实现21013LUT/17430FF/53BRAM/26DSP，100MHz WNS/WHS+.017/+.052ns，TNS/THS0、28CDC safe，IOB/RAM/MMCM/Gray/skew和同次BIT/HWH/XSA/70输入绑定通过。Rain022267A9不改，构建26整数/832项复核。手册docs/mode_a_handover_v0_8_0/README_CN.md；完整本机包Gesture_ModeA_FPGA_v0.8.0_20261027_BlindHandover，源码和非原始证据推个人分支，旧初稿标签/包保留；开发端未开实体接口，新实板NOT_RUN。最终完整包44067946B/2703文件，SHA256 d59164f96edbf4603e415c85fd14d43a0f6326f087b726d9fe3ec4689dcbd09c；包内23PC/13终端、重规划逐字节及全部文件/模型/硬件绑定和ZIP校验通过，见board_evidence/mode_a_handover_v080_a1/VERIFIED_SUMMARY.json。

2026-10-27 v0.7.2 D5预接启动：用户明确取消运行中接D5，要求先接好再运行。v071现场board_03已收62反馈、D5高，OFF成功，重新LINE后ERROR=0x40 UART_FRAMING，尚无HOME；传感器/PS/CPU恢复CONFIRMED。新流程接受下载前D5已高，启动核对后端OFF/ARM0/空闲、S4无owner，直接LINE/ARM0查询，3份新反馈后自动保持同一LINE置ARM1并PL接HOME，无MONITOR/OFF中断、无插线/Enter步骤。--monitor-only也D5预接、LINE/ARM0查询后恢复退出。新增十六进制错误/名称/状态显示，不清错强行继续。21PC+13终端通过；实际RTL复现OFF截断324B回包引发同一0x40，新预接/ARM0阻断待发样本/回包中ARM切换不断RX/九条50Hz200/6与反馈严格检查通过。两次仿真保留a1激励缺S2首周期20ms导致查询重叠失败及a2按真实S2合同修正后的通过，生产RTL无改。硬件/CNN/路径/速度/无到位门槛复用，新手册docs/mode_a_board_v0_7_2/README_CN.md，新整包D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.7.2_20261027_D5Preconnected。v072实板NOT_RUN，旧包/初稿标签/原始日志保留。

2026-10-27 v0.7.1启动补丁：现场v0.7.0 board_04已收到有效反馈且D5从0变1，但脚本MONITOR(2)直接写LINE|ARM(0x103)，违反RTL非OFF模式切换规则而SLVERR/External abort，HOME尚未发出。修复为MONITOR→确认OFF/空闲→LINE未ARM查询→确认反馈→LINE|ARM→PL接HOME；D5前后三段显示为STEP1查询、STEP2等待D5+Enter、实际启动，仅接D5不运动，提前Enter不保留。未接管时刷新反馈快照，S4接管后只读PL快照；支持--monitor-only第一步通过后正常恢复退出。19 PC+13终端检查和1次真实115200后端XSim通过，含旧故障复现/正确切换/快照/九帧50Hz与200/6。硬件/CNN/全部路径速度不变，保留无位置精度门槛。新版手册docs/mode_a_board_v0_7_1/README_CN.md；完整包由package_mode_a_board_v071.py从封存v070 ZIP复制生成，禁止复制现场runs。v071实板NOT_RUN；旧初稿包、标签和原始失败日志保留。

2026-10-27 Git归档范围更新：用户明确要求将本轮完整包及此前规划上传，标注“A闭环初稿尝试”。新增 deliverables/mode_a_closed_loop_draft_20261027/，含原封不动的v0.7.0 ZIP、v0.4.0～v0.7.0六版规划/角度/S4表/仿真数据/布局图及来源校验索引；当前授权覆盖此前这些交付包和图纸仅本机的约定。标签mode-a-closed-loop-draft-20261027。源码/模型/硬件未修改，新板实测仍NOT_RUN；原始现场日志及LOCAL姿态继续留本机。

v0.7.0现场条件更新：用户已回复目前尚未连接，要求交付包后自行上板；将采用PYNQ→机械臂，3.3V问题已验证可行。按用户报告接受，不重复电平测试，不由开发端启动JTAG/机械臂。下段“尚未答复”为开发过程旧状态，已由此更新。

2026-10-27 v0.7.0板端验证开发完成：用户确认三色夹取/放下成型，授权上板，继续无位置门槛、略加速，等待/交付提高50mm且转运途中提前上升。三槽与抓取升降每色12个目标保持；B=(360,200,160)、PRE=(270,175,180)、H=(240,155,175)、H_CLEAR=(240,155,195)mm，掌面Z150，B20°/近手40°。新S4 TIMED_WALKTHROUGH=1/ABI3405，六轴误差不放行，flags[7:2]为16ms固定停留单位：22/50=352/800ms，细分0；PALM等待0表示无限并饱和计数，真实CNN去抖/新鲜/窗口/交付确认、FIST持物HOLD/通信/D5保留。14deg/s和近手9，T102200/6，20ms，运动每3帧查询/空闲100ms。Windows JTAG入口run_mode_a_board_v07.py：同次新BIT、传感器984/80、一次载入表、MONITOR读新反馈/D5低等许可、PL从反馈接HOME、真实1/2/3与PALM自主任务、人工r/y/b补料、Ctrl+C有序停止/恢复/关自建服务。41KP/53段/栈17、28569样本，精确/实际命令各Coppelia一次碰撞0，既有6结束姿态启动265采样碰撞0。10新PC+13终端、6XSim（1定向FSM/4全S4-S2/1真实波特率后端）通过；构建复核26整数样本/832项，新完整实现21166LUT/17448FF/53BRAM/26DSP，100MHz WNS/WHS+.173/+.005ns，TNS/THS0、28CDC safe、独立IOB/RAM/MMCM/Gray检查及同次XSA绑定通过。新实板未启动，电平/当前控制端现场确认问题已异步询问，尚无答复；旧记录Adapter5V供电不能证明PYNQ侧3.3V逻辑，不自动接未知电平。当前手册docs/mode_a_board_v0_7_0/README_CN.md；旧包/原始物理日志保留。

2026-10-27 v0.6.0新相机三色交付：用户确认沿用桌面原点、轴心与三块不变，交付侧平移；镜头(195,195,333)mm，现场桌面视域(0,0)～(310,310)。三槽抓取/升降每色12个目标逐项保持v0.5.2。新B(360,200,110)、PRE(270,175,130)、H(240,155,125)、退爪(240,155,145)，掌面参考Z100；原竖直姿态不能直接平移到新视域，交付侧采用径向向外倾角B15°/PRE及H30°，抓取侧竖直。继续全部误差observe_all/arrival_mask0，20ms和160/5及12/8deg/s保持；PRE人工Enter保留、取消120秒等待超时。新增run_mode_a_three_color.py同一串口红黄蓝依次完整运行/分色日志/失败不启动后续颜色；布局ID绑定，旧布局日志不直接续跑新交付。9路线32628样本、41KP/53段/栈17，弦偏差.197154mm；18PC检查、10个单项合成流程及连续三色150秒掌心等待通过。新Coppelia4.10实际12臂网格、旋转附着木块、新镜头/桌面/8x8cm掌面代理，精确S2与实际T102四位小数各32628采样均碰撞0，恢复关节/清自建对象。硬件/Rain不变，新实体和新相机CNN为NOT_RUN。当前入口docs/mode_a_delivery_layout_v0_6_0/README_CN.md，S4候选是数据，旧BIT未含新表/observe_all策略；三色实体确认后再集成板端。本机旧包/实际日志保持。

2026-10-27 v0.5.2全程走位：用户明确所有到位门槛先取消、速度加快、先完整走完再按位置调点。新增入口run_mode_a_walkthrough.py，默认六轴observe_all/arrival_mask0：没有精度放行、三帧确认、3秒到位超时、HOME邻域或肩轴0.15rad误差拦截；误差仅显示。保留反馈失联/无效命令/串口失败/人工停止，PRE掌心Enter确认。普通转运12deg/s/24deg/s2，近手短段8/16，原生T102160步/s/acc5，对应14.0625deg/s/43.9453125deg/s2；20ms输出，延迟拉长不突发/不丢样本，细分点不额外停留。支持--resume-log识别v0.5.1的INNER停点，从新反馈接续而不重开爪或要求回HOME。9条重定时31959样本，通过原生角度/S2，最大10.666023deg/s/二阶差分24.042266deg/s2，13项PC检查、10条持续肩/肘/夹爪误差软件流程通过；新Coppelia193041采样和真实停点续跑/重接44064采样碰撞0。新实体NOT_RUN，硬件/模型不改。操作见docs/mode_a_walkthrough_v0_5_2/README_CN.md，旧v0.5.1入口保留历史，当前走位运行新脚本。

2026-10-27 v0.5.1完整运动流程：用户确认先忽略肩轴精确到位、先完成流程。已核对本机yellow_hover_02：19.056919s、反馈1→231/最大年龄125ms，只在HOME_OPEN失败，手爪实速0.802489deg/s；根因为PC候选T102 spd11/acc1单位不匹配。新版PC入口100步/s、acc3(300步/s2)，对应8.789063deg/s、26.367188deg/s2；20ms轨迹保留。肩轴observe默认精确掩码0x3D，.02rad告警/原始误差继续记录、>.15rad明显偏离仍停；其他四臂轴.02与手爪.04不放宽。第一段从三个稳定的新反馈重生成，允许手爪部分张开但前五轴仍需在原HOME邻域。新增handover完整运动：抓取/抬升/转运/PRE等待操作者掌心就位/交付/释放/退爪/HOME；人工Enter不是CNN事件，不宣称FPGA自主闭环已验收。20项PC检查、9条单位限速软件完整流程、33个新启动场景Coppelia33066采样碰撞0通过，源几何v0.5.0与硬件v0.4.0保持，新控制实物NOT_RUN。使用docs/mode_a_fullflow_v0_5_1/README_CN.md；旧包和真实失败日志保留，不重跑原模型/RTL模块。

2026-10-27模式A运动候选v0.5.0：用户明确要求不等待示教映射，以历史A残差外推B/C，仿真后给其自行实测。开发端无实体访问。已以Giao成功高位Q=(540,205,137)与原生反馈为参照，生成固定关节残差假设下的三槽原生数据；并非识别了真实五轴零偏。三槽悬停/原槽抓放/交付共9路线45489个20ms S2样本通过，40关键点/52段/栈17，Coppelia9正向与采样回程279066采样碰撞0。Windows显式--run单项程序支持hover/pick-return，10项PC故障/协议检查通过，原到位阈值不放宽；初始HOME不符不移动，反馈超时/调度超时停止且带载保留夹持目标。B/C可按候选直接试验，不再等待额外示教文件。首轮先悬停观察再原槽抓放，人手交付候选数据提供给PL集成；当前单项程序为PC串口调试。硬件/模型完全沿用v0.4.0同次BIT/HWH/XSA，未重建或重跑44模块测试；新实体动作NOT_RUN。手册docs/mode_a_residual_v0_5_0/README_CN.md。本记录为当前任务入口，下文v0.4.0是保留基线。

2026-10-27模式A v0.4.0离线候选完成：独立分支codex/mode-a-closed-loop-20261027，基线fd397f9；Rain 022267a9 targeted600 v3双CNN、Giao 9504e60e原红块交接已审核。44次XSim、26整数逐层样本/832检查、完整实现及独立网表通过；20991 LUT/17382 FF/53 BRAM/26 DSP，WNS/WHS +.041/+.024ns。S4库存ABI3404、显式RESTOCK、成功交付空槽/取消归还恢复；候选20ms/50Hz及每3运动帧查询通过真实115200仿真。三槽名义IK/41关键点50段/12228 S2样本、Coppelia 92295采样碰撞0；68项相机PC预检和13项终端检查通过。所有新版本实板/实体50Hz/三槽人手交付均NOT_RUN，D→原生基座/端点/工具有效映射仍缺；Giao新45段仅限原红位置，不能直接用于新三槽。源码、手册和最少标定缺项见docs/mode_a_closed_loop_v0_4_0/，完整本机包在D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_ClosedLoop_v0.4.0_20261027_ReviewCandidate。旧包/原分支/未跟踪资料保留。本记录取代下文v2状态作为本工作树入口。

2026-10-24黑背景v2硬件v0.3.0离线完成：构建源码744e834，37XSim/26CPU逐层/完整实现/独立网表通过，21108LUT/17378FF/53BRAM/26DSP，WNS/WHS+.045/+.033ns；新MODEL E4C43D44/raw>=−11748。相机/曝光/XDC/运动不变，板测NOT_RUN。完整本地Candidate及最终结果见主目录board_evidence/mode_a_black_scene_v2_20261024_v0_3_0/REPORT_CN.md。不推送。以下是此前源码检查点记录。


2026-10-24新模型离线接入进行中：独立分支codex/mode-a-black-scene-v2-20261024，来源e4c43d44的v2 B gate030；生产仅新分类权重/描述符、raw门槛−11748、模型ID E4C43D44，前端/曝光/任务运动/XDC保留。26 CPU逐层832检查通过；RTL和完整实现进行中，实板NOT_RUN，不自动上板、不推送。原曝光分支和暂停VGA分支保留。最终看主目录同名board_evidence报告。


2026-10-22曝光标定v0.2.0：实测源码e58b433，20XSim+完整实现/IOB/CDC通过；984行/5x作为静态调试档，10张原始小图/4147实时样本/format0->0/maxage191ms，75.156秒末尾选定档通过。冻结参考7张张掌仍全部background，画面改善但识别未恢复，完整A未测。正常恢复传感器原值/PS/CPU并关闭调试服务。原ROM未改、下次需重放配置，原VGA路线继续暂停。证据位于主目录board_evidence/mode_a_phase2_exposure_20261022_v0_2_0/，原4a82b6d Phase2分支保留；本次独立曝光分支，不自动合并主目录历史源码，不推送。

更新日期：2026-10-18
当前状态：板包仍为软件v0.2.3、沿用0.2.1最终BIT/HWH；Windows诊断工具v1.2.0。03:19 PC→CH340→Adapter→机械臂真实查询五发五收/1599B通过。用户最新纠正为5V供电、P_RX/P_TX侧接TTL、A2/A4侧接机械臂，旧P2主机/P1机械臂及指定3.3V的Adapter现场表已撤回，见docs/ROARM_ADAPTER_WIRING_CORRECTION_20261018_CN.md。原图却标3V3且A4→缓冲→P_TX，不能把两者直接合并为新确定接法；准确TX/RX、5V来源/接入点、共地、原3V3节点、板载USB状态和实际电平待核实。保持PC通过结论，不据此宣告供电健康或旧失败根因。FPGA D0/D1为LVCMOS33，未核实前不移接5V方案。下一阶段同一最终BIT/D5低的PL只读UART；相机连续性、限位/示教/停止距离/模式A实体交付仍未验证。

## 2026-10-18 用户纠正Adapter方向和电源，撤回旧现场接线表

- 用户报告成功时应使用5V供电，标P_RX/P_TX侧接TTL、A2/A4侧接机械臂。保留03:19五T105/五完整T1051的实测通过，不要求重新回环；同时不能推断每根线的交叉对应、实际芯片VCC和输出电平已确认。已询问逐线接法，当前未获答复。
- 原图是3V3供电的SN74LVC1G126及A4→Y→P_TX单向缓冲。其与实物使用说明的对应存在缺口；此前直接指定P2为主机侧、P1为机械臂侧和供电的表格撤回作为操作依据。五份相关现场手册加置顶纠正，旧包保留历史并受纠正说明约束，不用未核实的反向/5V表替代原表。
- 芯片若实际VCC=5V，TI规定VIH为0.7VCC，标称3.5V，输出高电平由该电源产生；不能保证3.3V源输入门槛或PYNQ接收兼容。若外部5V经实际稳压到3.3V，应按真实电路判定。只凭供电端名称或五查询不能确定兼容性；不把5V接D0/D1，不擅自把标3V3节点接5V。
- 本轮只核对既有图/官方规格、修正文档，未打开串口或发送查询/动作，无源码/RTL/BIT/HWH/模型/约束/软件版本变化，无需重跑软件测试或Vivado。旧16项检查和发布包不变；实物接线/电平与PL经Adapter板测待确认。

## 2026-10-18 外置TTL真实查询五发五收通过

- adapter_loop_new_20261018_031930_563虽以loop命名，内容是实际状态响应：COM15 CH340、115200/8N1、ttl_only、queries_via_usb=0、queries_via_header=5，五次字面T105；1599B/LF5、五条T1051，invalid/incomplete均0，error=null。离线重组与header_rx.bin逐字节相同，五条六关节字段均为有限数；SHA256 76beb8e3d96ecbc03d7c3a5579b04d6cec4b52722bc7dbb4f88a9894d4d7da58。原始关节/TCP数据只保留本地。
- 五次主机事件记录均约15ms首字节、47ms完整行；只代表五个Windows串口查询样本，不是PL/机械动作时延或长期可靠性统计。六个torswitch字段均0，不能把反馈通过写成运动/保持力通过，也不自动发送扭矩或回零命令。
- 用户已补充01:28的纯回显发生在机械臂未开机时；01:31开机后013132_496249仍0B。随后用户报告Adapter完全拆线后3V3/GND约零点几欧（回忆值，无准确双向读数），当前仅Adapter GND悬空、3V3仍接。03:19成功条件是否改变尚待补充。通信通过是有效新证据，但不证明可疑供电接法符合器件要求，亦不证明旧失败根因。
- 下一步只确认并记录成功接法，再用现有最终BIT做D5低的PL只读MONITOR；不重复已过PC/Adapter/线束回环，不先修改FPGA时序、波特率或超时。PL经Adapter的实际查询、运动/限位/示教/停止距离、相机连续性与模式A实物任务仍NOT_RUN或未验收。本轮仅审既有日志并更新文档，无串口打开/新发送、源码/RTL/BIT/HWH/模型/约束变化，原16项软件测试与发布包不变。

## 2026-10-18 正常查询命令仍纯回显，先确认实体接法

- arm_rx_compare_20261018_012842_689320原始50B/LF5，精确五次T105且与RX事件一致，T1051=0/error=null；与末端回环的原始字节相同。脚本正确未将查询回显当成六通道状态。物理接法不能从命令/日志确定，已询问短接是否全部移除、P1-4/2/6是否接arm8/10/9，当前未获答复。
- 已有空载回环通过保留，不据当前50B认定真实机械臂通信成功或具体根因。原上下文把纯回显直接等同残留回环的说法收紧：应优先检查旁路，但仍需源头隔离证据。M3当前官方JSON文档未查到回显设置；检索到的T143回显设置属于UGV文档，不能套用于未确认固件的M3，不发送此类配置命令。
- 若用户尚未恢复接线，按现有正常三线流程恢复后重测；若明确已恢复，下一次应通过隔离反馈返回线区分本地旁路与依赖机械臂TX的回显，实际操作须先断电。当前未执行此隔离或新查询。无代码/RTL/BIT/HWH/模型/约束变化，原16项软件验证和包不变。

## 2026-10-18 原线束末端回环通过，待恢复正常TTL查询

- adapter_cable_loop_20261018_012400_786：五次正确写入，精确50B/LF5，与RX事件一致；SHA256 ab138db008554306faadf96aa10e314e096b13d4ace8403bb83bf191df06bdf8，无API异常。Adapter加两根原线在本次独立回环条件下可解码；不代表机械臂GND/实际输入负载或模拟电平已通过。
- 当前无须再重复已过的输入、本体和末端回环。恢复前断电拔USB，拆除远端和板边所有短接及T形观察支路，TTL RX回P2-2。保留已过TX/RX线，P1-4→机械臂8、P1-2→10，以可靠短线P1-6→9共地；TTL3V3→P2-9/GND→P2-6不变。板载USB不接，原装12V/ON/初始化停止后执行--ttl-only COM15新目录采集。
- 正常查询判据从回显50B改为queries_via_header=5、T1051至少5、TTL_FEEDBACK_PASS/error=null。只有T105回显时应优先检查未拆回环/旁路，不能单独据此确定来源；仍0时需要共地连通和真实输入电压/波形/实物板型证据，不更改FPGA时序/驱动或UART超时。
- 本轮只读审现有实测与枚举并更新上下文，无新串口打开/发送/运动、代码/RTL/BIT/HWH/模型/约束变化。恢复正常后的新查询NOT_RUN，v1.2.0/原16项软件验证/板包保留；原始字段和标定不提交。

## 2026-10-18 Adapter本体回环通过，检查原线束末端

- adapter_loop_retest_20261018_011721_909：正确五次T105写入、原始50B、LF5、逐字节等于查询且与RX事件相同，SHA256 ab138db008554306faadf96aa10e314e096b13d4ace8403bb83bf191df06bdf8，无API错误。无真实T1051属回环预期。按已规定接法，独立Adapter缓冲输出/返回链本次可解码；不能宣布真实机械臂负载下电压/边沿或驱动能力已测通过。
- B输入通过/A输出端0与本体回环通过之间，主要差异在输出延长线、返回线、接触和A观察支路/供电接法。下一步保持TTL→P2四线和RX回P2-2不变，断电移除板边短接；P1-4/2分别接原来机械臂8/10两根线，机械臂端全部拔掉，仅将两个悬空线端短接。机械臂8/10本体不可短接，GND/电源也不加入回环。
- 末端回环50B后可用同一对线、可靠共地恢复正常TTL T105查询；若仍无返回，转向实际输入负载/共地/电气测量。末端回环不通过，先逐根替换输出/返回线并检查末端连接，保留配对证据。无需重做已通过本体回环或更改软件/FPGA。
- 本轮只复核用户日志并更新说明，无新串口查询/动作、代码/RTL/BIT/HWH/模型/约束变化。末端回环/恢复TTL新复测NOT_RUN，沿用v1.2.0、原16项软件验证和原板包，原始现场数据不上云。

## 2026-10-18 A未通过、最新B通过，准备Adapter回环

- A arm_input_unloaded_20261018_010459_469原始0B，五次正确写入；早前B010647_543原始0B。用户随后明确更正当前为A失败/B通过，本地发现最新adapter_input_tap_20261018_010850_981：原始50B、LF5、精确等于五次T105、与RX事件重组一致，无串口错误。最新B输入节点通过，不把早前失败冒充最新结果。
- 当前TTL发送及B输入观察能工作，A仍失败；故障候选在缓冲供电/使能、输出或A输出延长/分支连接，未证明芯片损坏。独立Adapter回环可区分板级输出返回链与A额外线束。此前20261017的Adapter50B回环保留历史通过，当前失败条件下的复测有独立诊断意义。
- 下一步断电并完全拆除Adapter与机械臂/FPGA的全部连接；TTL TX/RX/GND/3V3分别接P2-4/2/6/9。拆除B输入RX观察支路，唯一回环短接P1-4(P_TX)与P1-2(P_RX)，避免直接TX/RX旁路假通过。复用v1.2.0和离线精确50B判据，无T1051为回环预期。若回环通过重点查A多出的输出线/分线观察接点；若不通过仍要区分供电/OE/缓冲和P_RX返回路径，不能直接定板损坏。
- 本轮只核对既有原始数据/端口与记录，未打开实际串口、未改软件/RTL/BIT/HWH/模型/约束；当前Adapter复测NOT_RUN。沿用原16项软件验证/全部旧包，现场原始数据和标定仍仅本地。

## 2026-10-18 输入节点零解码、准备加载对照

- arm_input_tap_20261018_005635_833原始文件0B、五次正确10B T105、无串口API错误。用户明确RX已从P2-2移至机械臂端8针、与Adapter发送线三点同网，实际带负载观察未通过。原方案NOT_RUN是制定时历史，不能继续当作当前状态。
- 下一步A断电后只卸机械臂8分支，保留输出线末端/RX观察支路及供电共地；恢复50B则指向接入负载/节点/电气差异，保持断开并核实针号/板型及测量。若A仍0，B把RX观察移至P2-4/A4的TTL发送输入节点；B50而A0优先查缓冲供电/使能/输出线，B也0优先查源/输入/观察支路/共地。均以精确50B/LF5为观察判据，通用T1051状态不是该观察判据。
- TI126高有效OE/VCC需要实际检查；已接3V3不代表测得3V3。进一步定性需万用表/逻辑分析仪，空闲电压不能代替动态波形。无新实际查询/代码/硬件/模型/约束变化；仅更新手册、证据和上下文，A/B未执行，v1.2.0及旧包保留。

## 2026-10-18 独立TTL零返回与输入节点观察

- arm_rx_compare_20261018_003502_499701：COM15实际CH340、正确五次10B字面T105、header_rx.bin=0B、无API异常；用户确认机械臂无板载USB仍正常运行，Adapter P2-9为TTL3.3V、P2-6为GND。已确认接线供电，不冒称实测电压或正确电气字节已到ESP32。
- 下一步不重复无负载隔离回环；断电后保持TX→Adapter→机械臂8路径，CH340 RX从P2-2拆除，改为机械臂端物理8同节点的只读T形支路。机械臂10与此节点分离，8/10禁止短接。复用v1.2.0采集，专用离线判据50B/五换行/逐字节等于五次查询；通用工具无T1051的状态是此观察的预期，不能混为正常反馈验收。
- 参考官方原理图R47 1k把CP2102 TX接U0RX，但实物板型/负载/电压仍须核对。即使CH340在节点解码50B，也不能单独证明ESP32阈值/板内连线/固件接受；若0/坏字节优先查实际路径/缓冲供电/负载/共地。
- 本轮只审已有日志和文档，离线检查当前0B正确输出False；没有新实际串口发送/动作/代码/硬件/模型/约束改动。实际节点观察NOT_RUN，原16项软件测试和包保留。

## 2026-10-18 双口反馈对照通过、准备独立TTL查询

- 用户v1.1.0双口日志arm_rx_compare_20261018_001440_955012：USB/header各1565B、五条313B/CRLF完整六通道反馈，invalid_json/incomplete_feedback均0，BOTH_FEEDBACK_PASS/error=null。二进制逐字节相同，共同SHA256 3de0c90ab616e9c080c639ce495378f08ad8b0dd1f5ff13de3f2bb42041453e8，与各自RX事件一致。原始姿态/反馈仅本地。
- 本轮已证明机械臂物理10反馈可被CH340收到；下一步仅验证外部发送。新--ttl-only --header-port COM21仅打开所选CH340发送五次字面T105，queries_via_usb=0、queries_via_header=5，以TTL_FEEDBACK_PASS判定。默认双口仍只板载USB发送，未显式选择TTL禁止header独自发送；--usb-only保留。
- 16项无硬件单测及实际COM21 check-only PASS，实际串口未打开。按docs/ROARM_UART_TTL_QUERY_v1_2_0_CN.md断电接Adapter：TTL TX/RX/GND/3V3到P2-4/2/6/9；P1-4/2/6到机械臂40PIN物理8/10/9。板载USB拔掉、FPGA不接，原装12V/ON/初始化后执行外部查询。3V3只给缓冲，未用5V不接。实物针号已由用户此前确认，转接板电压未实测。
- 没有新实际串口查询/动作或RTL/BIT/HWH/模型/约束改动；当前真实外部发送NOT_RUN。已有回环、USB单口和双口接收不再要求重复；TTL完整路径通过后才换回FPGA做只读MONITOR。旧包保留，原始数据/标定/图纸不上云。

## 2026-10-18 本机板载USB状态查询通过

- 用户v1.1.0单口输出USB_FEEDBACK_PASS/error=null；本地原始文件复核五次字面T105写入、1620B=五条324B/CRLF、T1051六字段完整、invalid_json/incomplete_feedback均0，RX事件重组与usb_rx.bin完全一致。Windows记录查询至完整行均约47ms（五例、受主机时间/读取分块影响），不是PL或物理闭环延迟验收。
- 日志目录arm_rx_compare_20261018_000844_367459；原始SHA256 c231acc4d5d43c9eacd1d5a2d22ff2a55e51f253cfe29f7eb6ba81499cfcb143。原始JSON、实际关节/末端数据仅在本地，不加入Git。前置USB_ONLY_QUERY_FAILED来自旧判断块，不覆盖本轮新工具结果。用户未说明失败到成功之间每项物理条件变化，恢复原因未确定。
- 无需继续重复已通过的CH340/Adapter/PYNQ隔离回环。下一步断电拔USB改线，仅CH340 RXD到机械臂物理10（P_RX/U0TX）、GND到9；CH340 TXD/3V3/5V、Adapter、FPGA均断开。恢复原装12V/ON并等初始化停止，板载USB独占发送T105，执行现有双口命令。此举只验证外部反馈，随后仍需验证外部输入及移除板载USB后的独立供电/共地。
- 本轮只分析已有用户实测日志、核对官方原理图与只读枚举COM20，没有新串口查询或机械动作。代码/硬件/模型/约束不改，不新增测试或重新实现。实际外部UART/运动/限位/真人交付仍未通过。

## 2026-10-18 USB单口原始采集工具v1.1.0

- 此前双口脚本COM20打开失败为Windows121；移除外置USB设备/绕过原共享USB hub后，旧usb-query已能打开但未收集有效反馈。用户确认与队友相同的ESP32 UART Type-C，不能继续从CP210x名称猜测插口。
- 新增--usb-only，板载USB发送五次字面T105、CH340无需存在；所有原始字节累积，失败保留日志。2026-10-17 23:58实际单口采集：五次写入，每次10B，RX共5B、LF0、完整T1051=0、error=null；仅通信测试，无运动/力矩/复位/固件操作。原始数据仅本地。
- 11项无硬件单测PASS，原双口行为保持；单口check-only验证COM20且不打开串口。当前CP210x驱动11.2.0.167是只读检查结果，不单独证明驱动有错。手册docs/ROARM_UART_RX_COMPARE_v1_1_0_CN.md给出同线/同供电的电脑对照、USB单口与双口命令和判据。
- 下一步当前电脑使用队友成功的同一数据线直连本体USB口复测，仍失败则同一台/同一线/同供电在队友电脑运行同版脚本。当前USB参考恢复后再做被动header RX对照。没有RTL/BIT/HWH/模型/约束变化，无新Vivado；v1.0.0工具包及v0.2.3完整板包保留。

## 2026-10-17 Windows双串口对照工具v1.0.0

- 用户确认同一台机械臂换到队友电脑，板载USB收到五条完整T1051、每条319B/CRLF，总1595B；与RX事件重组一致。实际包的软件逐字节参考解析五条均mask0x3F。原始日志和姿态数据只在本地核对，未加入Git；运动未测试。
- 外置CH340自身及经Adapter(C)的回环各50B逐字节一致；机械臂总开关ON条件的外部UART复测仍零接收。下一步CH340仅RX/GND监听40PIN物理10/9，TX/电源脚及Adapter断开，由板载USB独占发送五次T105，同时比较两路返回。
- 用户粘贴Python存在两处语句/字符串截断，Read-Host提示又被误当赋值。新`scripts/roarm_uart_rx_compare.py`保存为文件，显式CLI参数、端口/VID角色预检、--check-only零打开、自动新目录、完整原始字节/事件/控制台/结果、异常关闭与保留证据；只板载USB写T105，CH340不发送。
- 8项无硬件测试PASS；本机COM15=CH340、COM20=CP210x只读预检PASS，未打开实际串口/未发送查询。新操作手册`docs/ROARM_UART_RX_COMPARE_v1_0_0_CN.md`。RTL/约束/模型/硬件指纹不改，不重跑Vivado或生成BIT。此为独立PC工具，不替换已有v0.2.3完整板包。

## 2026-10-15 v0.2.3 UART计数纠错与无示波器诊断

- 用户已核对接线，示波器不可用。test03哈希正确，MODE=0/ERROR=0后MONITOR两秒valid_mask/fb_seq/fb_ok/lines_ignored/fb_err均0，age1→1926ms，结束STATUS0x51/ERROR0x800，无控制冲突/串口帧/协议故障。零分类行不证明没有任何RX字节。
- RTL的evt_frame_tx只在!frame_is_req时置位：MONITOR正确T105查询也保持frames_tx=0。旧checker和record-pose依赖错误条件，会误拒真实反馈；已用合成有效MONITOR复现旧错误并修复，仍要求六通道新鲜/序号和fb_ok增长/无错误，且只读期间运动计数不得增长。此缺陷不是本轮fb_ok=0的物理根因。
- `scripts/roarm_uart_diagnose.py`只发T105，保留运行期间status/error/feedback/counters；要求清洁OFF、D5低、计数0，不清错重试、不改500ms超时、不设ARM，finally回OFF。隔离D1-D0回环以lines_ignored为证据，不能当机械臂反馈。
- 无示波器现场步骤和现有test03可直接执行命令：`docs/MODE_A_UART_DIAGNOSIS_20261015_CN.md`。新完整软件包`RoarmModeA_v0_2_3_UART_Final`供新test04，BIT/HWH与原版逐字节相同。先做隔离回环再分辨PYNQ端/机械臂UART与固件；不要求Windows串口。
- XSim在未改的实际S1 RTL上验证原生T105逐字节发送、无返回500tick超时、D1-D0回环只产生忽略行、原生T1051六通道可接受且frames_tx始终0。仅TB时基加速，不是实板证据。新增31项Python/三场景RTL检查通过，整机沿用v12 LUT22524/FF18132/BRAM128.5/DSP24、WNS/WHS+0.120/+0.020ns；不重做Vivado。

## 2026-10-15 直连FPGA上板策略与v0.2.2软件工具

- 用户确认原装机械臂电源齐全、底座固定，坚持RoARM UART直接连接FPGA，Windows仅SSH/文件传输；固件/实际软限位/停止距离仍须现场记录，不走USB前置。
- 完整逐阶段策略：`docs/MODE_A_BOARD_TEST_STRATEGY_20261015_CN.md`。新`record-pose`只从本点的新PL monitor日志采集已停稳反馈，自动备份session，不改verified/限位；`vision-read`只读实际框，`palm-window`只提案。
- `route-test --stage empty-tray`补空载回收，两个空载阶段要求HOME与开爪角一致；三槽交付/回收六条空载都通过后才回填all_empty_routes_tested。未接触现场设备、未发运动。
- 本轮24项软件检查PASS；20组发布门槛与142个冻结输入重查PASS，原生22项RTL为同一BIT的既有证据。本轮无RTL/模型/约束变化，不重复Vivado；完整新包`RoarmModeA_v0_2_2_BoardTest_Final`绑定原BIT/HWH。
- 下一步：隔离test03，D5低，系统/供电/版本→10秒PL UART与60秒无手相机日志。格式错误持续增长时不进入自主A；只读UART可独立继续。图纸/全包/实测标定本地保留，源码/操作手册推独立codex分支。

## 2026-10-14 0.2.1 相机释放修复（实现通过，板测未执行）

- 保留原0.2.0板包和427f076源码。单帧注册释放仿真在235ns复现旧调度器重选frame 11；新的available掩码排除正在释放的缓存。快照压住的释放用2位寄存器保留，退出时交付并阻止同拍重选。
- VIS升为3503，CAM1/初始化/缓存与调度状态/既有format及drop计数只读可见；快照失败在清除请求前输出JSON，默认5s不变。不改变模型、DVP边沿或输入预算。相关release、adapter、frame、真实pipeline和SCCB，以及5项相机Python/7项示教Python回归通过；原生22项回归完成。
- v12于22:03完成整机门槛，40322条可路由net全布线，DRC Error0、31 Warning、methodology18 Warning；内部未约束端点0，CDC28端点Safe，Gray写/读skew1.078/0.998ns均低于10ns。142输入指纹不变，BIT/HWH SHA绑定最终包。
- 用户重启后ls恢复，但仍USB供电，不能将此前Python/ls/tail EIO归因于模型或认定已排除。当前超时后的LED/fatal尚无证据。所有新BIT板测仍NOT_RUN。

## 2026-10-14 RoARM 实体模式 A 0.2.0 源码与实现（历史）

- 用户已冻结固定掌心直接递送、三槽人工补物、取消/超时有验证过的独立回收路径则回收否则HOLD、保留A/B且默认A、全部视觉决策防抖；禁止训练。现场固件/限位/高度/停止距离到货后实测，模板保留 null/false 并拒绝不满足门槛的运动。
- 开发工作树 `runs/mode_a_roarm_20261014/dev`，独立分支 `codex/mode-a-roarm-20261014`，输入个人远端基线 `237314e154c9dfdf3d34728b4c7ca0a91550a3db`。Rain 在独立 detached 工作树，冻结 `0f350087af8db4e69c4cbab724ca2ed6313eaf05`，1093条模型SHA与12样本384项独立整数结果通过。根工作区及仅本地的三旧图纸提交保持隔离。
- 硬件：七阶段上下文 locator、75 tile VGA源帧缓存、同源PIL精确ROI、六类classifier、几何EMA、时间去抖与固定掌心静止窗口→S4→唯一S2→RoARM原生T102/T105 UART。视觉/AXI/任务/执行为单100 MHz域，PCLK经异步FIFO；旧cubic接口与SO101外部通路裁剪，B控制/路径/FIFO保留，配置锁/控制权/反压/LAST_DELIVERED/故障处理保留。
- 最终v11完整XC7Z020-1实现：LUT22440、FF18062、BRAM tile128.5/140、DSP24；WNS/WHS=+0.309/+0.017 ns，TNS/THS=0，内部未约束端点0，40160条可路由net全部完成，DRC Error0。CDC报告12+12+4均Safe，Unsafe/Unknown/No ASYNC_REG为0；双向11位Gray指针额外skew为0.968/1.311ns，均低于10ns。完整报告在 `native_motion/reports/roarm_closed_loop_implemented/`。几何差值/绝对值/比较拆三拍，SCCB SDA增加两级同步；v9b时序通过检查点保留但不交付上板。继承DVP 48 MHz、fall输入2..8 ns为暂定板级预算，仍需现场测量；任何硬件改变须重做实现。
- 最新RTL：locator2356248周期/23.56248ms、classifier750170周期/7.50170ms；16例ROI最大2881316周期/28.81316ms（side479）；不含图像采集、防抖等待和机械运动。12定位/46EMA、缓存全VGA、AXI快照、滤波、五类真实DVP集成、A取消/松爪边界、22原生RTL、23后端Python及7示教/协议门槛测试通过。新增SCCB检查159次写入/636字节、100kHz ACK、三次NACK重试、XCLK丢失与复位；SCCB实体初始化仍未测。完整DVP仿真绕过SCCB，A安全定向测试有FSM状态种子，不是实体闭环成绩。失败重编译会阻止旧实例运动；替代掌心可用 `run --without-tray` 验证HOLD，但仍要求全部实測门槛。
- 空间摆放、电气、21点示教、现场分级命令及验收：`docs/MODE_A_ROARM_RUNBOOK_CN.md`；冻结导入/仿真/全实现复现：`docs/MODE_A_ROARM_BUILD_CN.md`；阶段失败与修复：`docs/MODE_A_ROARM_DEVELOPMENT_20261014_CN.md`。中间rc1/rc2均源码包无BIT、BOARD_NOT_RUN。
- 用户授权仅新源码/配置/操作手册进入独立codex分支。本地SVG/DrawIO/PNG、绘图脚本、完整板包和实体标定不上传；完整包由 `scripts/package_roarm_mode_a.py` 绑定同次BIT/HWH、源码/模型/报告SHA，并保留回退版本。下一步只用最终BIT开展无机械臂相机、只读UART、空载/方块/托盘/替代掌心验证，随后固定真人掌心。

## 2026-10-08 NativeMotion 最后一例通过，本轮优化验收完成

- native_B_fist_20261008_01 原始PYNQ/PC/SIM日志已回收：PREFLIGHT PASS、B/object2/TRAY_RETURN、held/tray_seen/moved=true、fault/refuse NONE、exit0。TX1152/FB2776，反馈错误/响应超时0，SELECTED/PATH_ACCEPTED/TASK_CANCELLED；PC五段路径COMMITTED后CANCELLED（状态码5）。
- FIST_INJECTION直接记录WAIT_PALM/object2/holding/tray_ok/modeB的一次PS_TEST FIST，t_ns=12930426668893，位于任务开始与结束之间。原cancel_source推断标签保留，不能当作真实视觉识别；原PS日志到link_down未记录PS_WRITE_BLOCKED，结论限于本次捕获内容。
- Coppelia2805次观察，物品2抓取frame422、托盘释放frame894，最终frame1148/attached0，托盘误差0.024716167mm、HOME0rad，物品1/3位移0。13份原始输入归档reports/native_motion_B_fist_01_20261008；摘要docs/evidence/native_motion_B_fist_acceptance_20261008.json、最终报告docs/PHASE3_NATIVE_MOTION_FINAL_BOARD_ACCEPTANCE_20261008_CN.md。
- 原定最终A/B连续与B持物取消全部通过，无需重跑。本轮仅读取已有日志/归档/文档，不操作现场或新增测试；原发布ZIP/BIT/HWH/源/模型/约束与发布时NOT_RUN记录不改。后续先等兼容模型包并核对合同，实物RoArm-M3-S/真实感知/动力学/故障恢复另行确认；微调延后。

## 2026-10-08 B FIST 单次流程整理（当时待执行，现已通过）

- 新流程docs/PHASE3_NATIVE_B_FIST_RUNBOOK_20261008_CN.md，统一编号native_B_fist_20261008_01、Windows场景/PC/SIM和PYNQ板端结果路径；使用实际包路径/192.168.2.99/COM16，单物品2/repeat1/无auto-palm。先启动只读状态等待器，WAIT_PALM且holding/object2/tray_ok/modeB/VISION_SIM时仅注入一次FIST并保存FIST_INJECTION.json；原RTL/BIT及board_loop等脚本不改。
- 新增172737/173957及170854尝试的Windows sim日志frame0无抓取释放；scene003 PC log仅头、未SESSION，不能认为已执行取消。旧输出不删除/覆盖，不操作当前板端或仿真应用。新流程未实际执行，正常A/B仍已通过，B取消仍待测。

## 2026-10-08 NativeMotion A/B 连续三任务板测通过

- 用户board_native_A_001和board_native_B_003：同次初始化内task1/2/3与object1/2/3均DONE，PREFLIGHT全11项PASS、fault/refuse NONE。A TX/FB2940/6114、B2940/6291，反馈错误/响应超时0，valid/arrival0x3F、servo fault0；B均PATH_ACCEPTED/TASK_DONE。
- 本机实际UART/Coppelia日志scene001/002匹配1→2→3各抓取释放一次，落点误差0.0212861/0.0346292/0.0394685mm、最终无附着/HOME0rad。PC日志虽在scene001路径但时间与B003相符，BENCH会话、task1/2/3各五段提交。板端原PS文件/退出码/板端BIT哈希尚未回传，PC终态stdout未提供；不冒称已收齐原始板日志或完成收尾事件全量审计。
- 验收摘要docs/PHASE3_NATIVE_MOTION_AB_REPEAT3_ACCEPTANCE_20261008_CN.md，JSON docs/evidence/native_motion_ab_repeat3_acceptance_20261008.json；原Windows快照reports/native_motion_ab_repeat3_20261008。原20261007发布包不改，发布时NOT_RUN保留历史含义。无RTL/BIT/模型/约束变更、无新测试。
- 正常A/B无需重跑；仅补同一个最终BIT的B持物FIST托盘归还，repeat1/object2/去auto-palm，流程第6节。真实视觉/RGB-D/实物/动力学与故障恢复板测仍未验证。

## 2026-10-07 NativeMotion RC v0.1.0 完成，最终板测 NOT_RUN

- 用户确认：只上板最终版，直接迁移 S2，无旧 cubic ABI 兼容；旧模型/工程/原生接口版本保留；当前只 Coppelia，未来 RoArm-M3-S；16mm几何抓取保留；资源收益非硬门槛，微调延后。
- 新 native_motion/ 独立继承本机 S7（Git时点4c7da78）。S1 trajectory 实例退役，motion_sample_mux 保留缓冲/反压/LAST_DELIVERED、固定 S2；S4 原生完整命令/后端快照替代内部 AXI调度；owner/排空/配置锁/PS写隔离保留。SmartConnect 管理与模式B完整路径入口保留。HAS_SO101=0，RoArm模板/反馈/最终许可门控保留。整机 ARM/S2/S4 ABI=0x3101/0x3202/0x3403，SOURCE复位1。
- 83份视觉/模型/约束SHA-256不变，冻结Locator v16与七类随机classifier；不等于真实手势模型成功。活动四类、算法新六类及locator v24结构实验不混用，本轮未修改实验模型RTL。
- Vivado2026.1 / XC7Z020 post-route：LUT20,427 / FF14,876 / BRAM tile60 / DSP28；WNS/WHS +0.138/+0.021ns，DRC errors0、routing errors0、CDC unsafe0，门禁PASS。相对S7减少LUT2856（旧已用12.266%，器件占用降5.368百分点）、FF2158、BRAM3、DSP14。
- 22/22 XSim、22/22 Python、11/11实际 Coppelia 软件任务PASS。支撑面取底座网格最低点z=0.0218391456604m，16mm物块底面齐平。正常/取消/掌心超时与支撑面相交0；锁定肩关节故障注入189相交对。仍停止运动学/位置IK/几何附着，非动力学、实物或板卡成绩。
- 新软件 sim/phase3_native_closed_loop/ 支持同次初始化内3个不同物品连续运行、显式自动PALM；正常RELEASE/OFF后才写反馈快照，故障owner保留时不发会被拒绝的PS收尾写。原日志缺拒绝地址，不声称已追定所有历史PS_WRITE_BLOCKED来源。
- 最终本机包 deliverables/Gesture_Phase3_NativeMotion_RC_v0.1.0_20261007.zip；上板流程 docs/PHASE3_NATIVE_MOTION_BOARD_GUIDE_v0.1.0_CN.md。新BIT的FPGA/UART、连续任务、实物均NOT_RUN；下一步只测试最终BIT的A/B连续和B持物取消，回传PREFLIGHT/RESULT/PS与对应SIM/B-PC日志。原S7/旧包保留，中间统一源码检查点无BIT、板测NOT_RUN。

## 2026-10-06 七轮原始板端日志与 S8 复核完成

- 收到用户 phase3_board_evidence_20261006.tar.gz（4063B，SHA256 f6a855816f1572a8a0510ef172af89209f31958effb7a2b13ceacfb03fe69242），21份PS/RESULT/PREFLIGHT均完整，七轮结果/计数/task_end字段与既有验收记录一致。原始PS文件已取回；既有逐例“未取回”描述保留历史时点。
- 原S8 collect/compute/render实际成功，11份PS/PC事件输入、7轮、schema_problems=0；20份冻结依赖哈希通过，SIMULATION标签对应真实PL/UART+Coppelia执行端/注入手势。报告 docs/PHASE3_COPPELIA_S8_RAW_LOG_REVIEW_v0.1.2_CN.md；原指标及来源审计在 docs/evidence/phase3_coppelia_s8_metrics_v0.1.2_20261006.json 与 phase3_coppelia_s8_raw_board_review_20261006.json，本机原始快照在 reports/phase3_coppelia_s8_board_logs_20261006。
- PS日志选择→提交A 0.533939～0.575286ms、B含取消105.708898～124.403489ms；B请求→收到路径42.176289～55.247095ms含PC处理，不是纯网络RTT。PC缺target_request/pipeline事件，PC处理/网络RTT仍NOT_MEASURED；P95/P99样本不足，各独立PS日志连续任务数仅1，不能称连续7任务或实物/视觉时延通过。
- 四轮B均在任务结束后6.744～12.562ms记录IDLE下PS_WRITE_BLOCKED；未改变已完成结果，日志无拒绝命令/地址，来源待查，列入收尾控制权/连续运行验证。取消原因仍推断；无真实物理/PL内部/到位系列时延。下一步可观测性适配补丁及实际故障/连续运行，七类/实物仍独立待验收；本轮仅日志分析，无新硬件动作/源码/资源时序变更。

## 2026-10-06 FPGA / Coppelia v0.1.2 七例执行闭环验收完成

- B3用户 board_B3_019 PASS/B_AI_PC/object3/DONE/exit0，TX956/FB2541、反馈错误和响应超时0；PC会话/5段完整路径/COMMITTED/DONE及场景判据通过。一次抓取物品3/frame338、释放/frame758、最终frame952/attached0，落点误差0.0671536mm、HOME0rad、其他物品位移0。证据见 docs/evidence/phase3_coppelia_B3_019_20261006.json。
- 累计A1/A2/A3和B1/B2/B3正常交付六例、B2持物FIST托盘归还一例全部通过；正常落点最大0.1029954mm，托盘0.0597673mm，各例HOME0rad、反馈错误和响应超时0。65项验收判据、42份PC来源快照哈希及原BIT/HWH配对交叉校验通过。总报告 docs/PHASE3_COPPELIA_BOARD_ACCEPTANCE_v0.1.2_CN.md、汇总JSON docs/evidence/phase3_coppelia_board_acceptance_summary_v0.1.2_20261006.json；不是重复试验统计成功率。
- 保存证据后停止B3专用执行器，PC程序终态退出，cleanup019恢复初始姿态并撤销live descriptor，Coppelia应用保留。无需继续旧场景测试，板端去D5许可；下一步先回收七轮PYNQ原始PS/RESULT/PREFLIGHT配对S8指标，再补实际板端故障恢复/重复运行。真实七类/RGB-D/实物/动力学/持续50Hz/同步延迟仍待验收；没有新增RTL、BIT、模型或资源时序结论。

## 2026-10-06 B1 正常交付018实际闭环通过

- 用户 board_B1_018：PASS/B_AI_PC/object1/DONE/exit0，SELECTED/PATH_ACCEPTED/TASK_DONE，无fault/refuse，TX988/FB2676、反馈错误和响应超时0。原板端文件尚未取回，证据明确来自用户stdout/BOARD_RESULT；PALM监视到WAIT_PALM并返回S4Status。
- 本机PC会话/5段完整路径/COMMITTED/最终DONE全部核对；场景2716次观察、frame984，一次抓取物品1/frame338、释放/frame790，最终attached0。交付误差0.0874811mm、HOME0rad、另外两物品位移0，7项场景与4项PC判据通过。来源SHA256/摘要见 docs/evidence/phase3_coppelia_B1_018_20261006.json；9份PC输入保存在 reports/phase3_coppelia_board_B1_018_20261006。
- 本轮专用执行器已停止，快照后cleanup018/prepare_scene019成功；019配置与018一致，下一步B3正常交付。当前A三物品、B1/B2正常及B2持物FIST托盘归还通过；B3及真实模型/RGB-D/实物/动力学/持续50Hz/S8配对原始日志指标仍待验收。

## 2026-10-06 B2 FIST 托盘归还017实际闭环通过

- 用户 board_B2_cancel_017：PASS/B_AI_PC/object2/TRAY_RETURN、tray_seen=true、exit0，TX1256/FB3107，反馈错误和响应超时0，无fault/refuse；监视确到WAIT_PALM/holding后调用FIST。BOARD_RESULT的VISION_FIST标签仍是监督器推断，原PS手势事件文件未拷回；与用户监视记录分别保留来源。
- PC实际BENCH会话、5段完整路径、COMMITTED、最终CANCELLED；场景一次抓取物品2/frame338、释放/frame1062，最终frame1252/attached0；托盘误差0.0597673mm，HOME0rad，其余物品位移0。7项场景及4项PC判据通过；摘要/来源SHA256见 docs/evidence/phase3_coppelia_B2_cancel_017_20261006.json，9份PC输入快照在 reports/phase3_coppelia_board_B2_cancel_017_20261006。
- 完成后停止本轮专用执行器，归档再cleanup017/prepare_scene018；018配置与017完全一致。下一步B1正常完整网络提交/交付，再B3。模式A三物品正常、B2正常和B2持物FIST取消现已通过；真实七类/RGB-D/实物/动力学/持续50Hz/S8配对原始日志指标仍待验收。

## 2026-10-06 B2 取消016会话失败与017复测准备

- 用户 board_B2_cancel_016 初始化/反馈通过并监听8765，但60秒内没有SESSION，exit1；未生成BOARD_RESULT，监视OFF→IDLE→OFF后超时，没有FIST注入。本机临时PC启动器600秒连接等待超时退出，串口执行器仍正常；场景2872次观察全部frame0/attached0，无抓取/释放，最终HOME0rad。这轮取消路径未测，不计为托盘归还失败或成功。
- 失败摘要见 docs/evidence/phase3_coppelia_B2_cancel_016_failed_20261006.json；8份PC来源及SHA256保存在 reports/phase3_coppelia_board_B2_cancel_016_failed_20261006。停止本轮执行器并清理016后，准备停止场景017，配置内容与016完全一致。
- 017临时启动器持续等待首次TCP连接；连接后只执行一次原HELLO/完整路径/STATUS，不自动重复任务。原PC/PS核心脚本与BIT不变。用户需重载BIT、新board_B2_cancel_017目录和先启动FIST监视；实际TRAY_RETURN及场景末态待验收。

## 2026-10-06 CoppeliaSim v0.1.2 模式 B 物品2正常交付通过

- 用户 board_B2_015 为 PASS/B_AI_PC/object2/DONE，SELECTED、PATH_ACCEPTED、TASK_DONE，无fault/refuse；TX1040/FB3097，反馈错误和响应超时均0。板端结果来源为用户粘贴JSON，原始PS日志及退出码尚未取得。
- 本机 board_scene_013 的本轮 PC 日志确认 BENCH 会话、5段完整路径提交、COMMITTED及最终DONE；COM16执行器日志确认抓取物品2、释放、最终无附着，落点误差0.1029954 mm、HOME0rad、其他物品位移0。证据摘要及输入SHA256见 docs/evidence/phase3_coppelia_B2_015_20261006.json；9份PC输入快照保留在 reports/phase3_coppelia_board_B2_015_20261006。
- 本轮临时PC启动器仅等待TCP监听，连接后复用原HELLO/路径提交/STATUS；核心脚本、RTL/BIT/HWH/ABI未修改。完成后停止本轮执行器，保存快照再清理descriptor013；准备停止场景board_scene_016，下一轮验证B2在WAIT_PALM注入FIST的TRAY_RETURN。
- 当前模式A三物品正常交付及B2正常网络提交/执行闭环已通过；B1/B3及B2取消的实际板端/场景验收、真实七类/RGB-D/实物/动力学/持续50Hz/S8配对原始日志指标仍待完成。

## 2026-10-06 CoppeliaSim v0.1.2 模式 A 三物品正常交付通过

- A2：用户 runs/board_A1_010 的实际 object_id=2，PASS/DONE，无fault/refuse，TX1040/FB3115/反馈错误0/响应超时0。本机 board_scene_010 完整日志确认 grasp attached2、release、最终HOME0rad；交付误差0.1029954 mm，其余物品位移0。
- A3：用户 runs/board_A1_011 的实际 object_id=3，PASS/DONE，无fault/refuse，TX956/FB3004/反馈错误0/响应超时0。board_scene_011 确认 grasp attached3、release、HOME0rad；交付误差0.0671536 mm，其余物品位移0。输出目录名不决定任务对象；之前A1_007/008的object_id仍1，不能计作A2/A3。
- 加上已验收 A1_005，模式A三个固定物品正常交付板端/场景判据通过，最大落点误差0.1029954 mm。两份新摘要/来源SHA256在 docs/evidence/phase3_coppelia_A2_010_20261006.json 与 phase3_coppelia_A3_011_20261006.json；PC输入快照在 reports/phase3_coppelia_board_A2_010_20261006、A3_011。板端原始PS日志仍待拷回，所录板端结果明确来自用户JSON。
- 下一步先 B2 正常完整路径网络提交，再 B2 FIST 托盘归还和其余B物品；说明见 docs/PHASE3_COPPELIA_MODE_B_BOARD_TEST_CN.md。每轮新场景/配置、新输出、重新加载BIT，源/权限/初始化遵守v0.1.2。模式B、S8原始日志指标、七类真实模型/实物/动力学/持续50Hz仍待验收。

## 2026-10-06 CoppeliaSim v0.1.2 A1 正常交付板测通过

- 用户回传故障后 S2 ESTOP/COMMAND_CONFLICT；新版只读检查 FAIL/exit1。重载后 S2 IDLE/source S1/no pending/no history/no errors，board_load 和 check-board 均 PASS/exit0。实际恢复已验证，不能以旧 board_load 的较少检查代替新版状态检查。
- board_A1_005 经过 PREFLIGHT、DRY_RUN HOME、OFF/idle→LINE、实时反馈、OBJECT1、WAIT_PALM及用户PALM，最终 PASS/DONE/exit0；TX988/FB2870/反馈错误0/响应超时0，无fault/refuse。板端结论来自用户粘贴 stdout，原始PS日志尚待拷回。
- 直接读取本机 board_scene_005 的实际 SIMULATION_CONFIG 与完整 sim_events，并冻结到 reports/phase3_coppelia_board_A1_005_20261006。核对一次grasp/一次release、最终attached0；物品1落点误差0.0874811 mm（门槛2 mm）、HOME误差0 rad（门槛0.00035 rad）、物品2/3位移0。验收摘要和来源SHA256见 docs/evidence/phase3_coppelia_A1_005_20261006.json。
- 结论限定为真实FPGA/UART/Coppelia停止状态运动学/几何执行闭环的A1单例成功。A2/A3、模式B板测、真实七类、物理机械臂、接触动力学、持续50Hz与完整S8配对原始日志指标仍待验证。下一步每轮重载BIT/准备新场景，验证A2、A3，再模式B。

## 2026-10-06 CoppeliaSim 启动状态保护 v0.1.2

- 用户 v0.1.1 A1_003 回传 PASS/RETURNED_TO_SLOT/PALM_TIMEOUT，fault/refuse NONE，TX1068/FB3640/反馈错误0/响应超时0。实际 FPGA/UART/Coppelia 的取消路径板端判据通过；物品末态和 HOME 尚待 sim_events/场景核对，正常 DONE 未回传。
- A1_004 在 S2 HOME 的 planner START 写入 SIGBUS（exit135）；用户确认开始前已重载 BIT 并看到旧 board_load PASS。实际拒绝条件尚需 S2 状态/错误确认，不能断言是漏载。代码结束会 ESTOP，旧 board_load 不检查 S2 IDLE，这是必须保护的启动风险。
- v0.1.2 增加只读 board_state、强化 board_load、board_loop --check-board/配置前门禁与 HOME START 二次检查；拒绝时保存 PREFLIGHT/FAILURE，零配置/控制写入。22/22 Python 单测及 JSON 配置检查通过，实际板测 NOT_RUN，原 RTL/BIT/HWH/ABI/Windows 执行器不变。
- 下一步按 docs/PHASE3_COPPELIA_STARTUP_GUARD_v0.1.2_CN.md 先回传故障后及重载后 PREFLIGHT；D5 去许可，FAIL 不 CLEAR/START。PASS 后新建场景/运行再验证正常交付。

## 2026-10-06 CoppeliaSim 板端模式切换热修复 v0.1.1

- 用户已报告 S7 board_load/现场配置 PASS；原完整初始化 SIGBUS，PIPESTATUS=135/0，S1 MODE 页 external abort。板端最小 MODE 读写、完整 S1 配置/提交、OFF→DRY_RUN→OFF 均通过。
- 现有 S1 REG_MODE 明确拒绝两个不同非 OFF 模式直接切换；原 board_loop 的 DRY_RUN→LINE 为缺陷。改为经过 OFF/idle，确认配置有效且无 fault 后进入 LINE，保留原 HOME 与配置；增加 INIT 进度和 faulthandler。
- 15/15 Python 单测通过；v0.1.1 板端复测 NOT_RUN。无 RTL/BIT/HWH/ABI/接线变更。用户应应用 docs/PHASE3_COPPELIA_MODE_HOTFIX_v0.1.1_CN.md 对应热修复，重载原 BIT、新建场景会话并复测 A1。

## 2026-10-03 CoppeliaSim 执行闭环 v0.1.0

- 用户机械臂尚未购买，七分类队友继续优化；本阶段改为先 Python/CoppeliaSim，再由用户测试 FPGA/UART/CoppeliaSim，之后接真实七类与实物。RoArm-M3-Pro 仍仅候选，首版双后端保留。
- `sim/phase3_closed_loop/` 已打通注入稳定分类 → S4 参考 FSM → S2 位精确样本 → S1 fixture 字节流 → 实际 CoppeliaSim 六关节/物品 → 场景反馈 → 到位/通信监控 → 原 S8 指标。A/B 各三物品、取消归位/托盘、掌心超时、反馈丢失和关节阻塞共 11/11 场景通过，10/10 单测通过；S8 均 SIMULATION、schema_problems=0。配置、来源锁、证据摘要与复现/上板说明在该目录。
- 修复了 S8 模式 B 的二次事件读取竞争：服务单次 drain，监督器消费副本；冻结原文件保持字节一致。独立 simulator service 允许明确 no-robot 的 BENCH 路径进入虚拟 UART 执行，生产 LINE/真实标定门槛仍由原服务保留且单测覆盖。
- 已提供 prepare_scene、executor.py --serial、board_load/board_loop/board_gesture、pc_submit，复用原 S7 BIT/HWH；用户下一步上板。该 UART 板测 NOT_RUN，没有修改 RTL/ABI/引脚/模型。详细说明见 `sim/phase3_closed_loop/README_CN.md`。
- 本轮是停止状态运动学与几何抓取仿真，未验收动力学/碰撞/接触、真实七类、RGB-D、实物机械臂或持续 50 Hz。按节拍 A1 实际 41.80 s、逻辑 19.84 s；单独场景 RPC 200 次均值 0.684 ms、最大 76.37 ms，不能代替 UART 板测。正常物品落点误差最大约 0.103 mm。

## 2026-10-03 封存与下一步计划

- 本轮封存为 `Phase3 PreDemo Frozen v0.1.0`，状态 `FROZEN_CANDIDATE`；说明/清单见 `docs/PHASE3_PREDEMO_FROZEN_v0.1.0_CN.md` 与同名 JSON。输入代码提交 `e848dc198e1e383ac7c3a2f84a344f05306d5a3e`；本机精简封存包包含 Git 输入源与选定的未跟踪集成资料，ZIP 未加入 Git。
- 用户确认 RoArm-M3-Pro 仍为候选；首版保留双机械臂后端，实物与固件确认后再裁剪。水平跟手微调为首版成功后的可选功能，当前不冻结轴数或算法。
- 后续顺序已按本日新增要求调整：CoppeliaSim Python → FPGA/UART/CoppeliaSim → 真实七类/实物固定点首版闭环 → 以 S2 为基础统一运动执行入口 → 内部原生命令/状态接口与按整机实测裁剪。不得直接删除 `motion_sample_mux` 的缓冲/反压/已接受目标行为；window 的控制权、原子配置、快照和超时语义必须迁移。具体计划与阶段出口见 `docs/PHASE3_NEXT_DEVELOPMENT_PLAN_CN.md`。
- 本轮只做封存、架构核对和计划；未修改 RTL/模型/硬件配置，未新增仿真、实现或板测结论。资源节省 5%～8% 为待验证假设。

## 当前目标与环境

- 最终双模式物品递送目标与开发规则见 `AI_INSTRUCTIONS.md`；总体架构见 `docs/EMBODIED_OBJECT_HANDOVER_PROJECT_PLAN_CN.md`。
- 最终 AI PC 是用户当前 ROG Flow Z13 GZ302EA：Ryzen AI Max+ 395、Radeon 8060S、约 64 GB 物理内存、Windows 11 25H2。用户要求最终演示 Windows 原生运行；ROCm 7.14.0+ 与实际 GPU/驱动/推理框架的组合尚待验证。
- 七类目标仍为 `BACKGROUND`、`OBJECT_1`、`OBJECT_2`、`OBJECT_3`、`PALM_READY`、`FIST_CANCEL`、`OTHER_INVALID`；需要在最终 OV5640 安装视角采样、重标旧数据、训练量化并完成 PL 兼容性和真实识别验证。不要把旧四类或随机测试权重称作七类交付模型。
- 三人各自维护本机目录与个人分支；`main` 是建仓者个人快照，并非三方共同基线。当前个人分支 `dev/filid`；合并之前核对依赖、接口和证据。

## 已确认硬件与证据边界

- 板卡：PYNQ-Z2，器件XC7Z020。
- 相机：OV5640经DVP直接进入PL。
- 已有链路：OV5640采集、128×128 Locator、同帧ROI、32×32分类器、
  Top-1与稳定确认均在PL内。
- 活动分类模型仍为四类：
  `background/fist/mute/palm`；七分类尚未训练、量化或部署。
- 现有 Locator 对部分遮挡、侧手姿态的召回仍需在最终视角实测；不要沿用未经验证的准确率。
- 历史无 HDMI 视觉版本 post-route 为 11,665 LUT、5,483 FF、58.5 BRAM、28 DSP，WNS/WHS `+0.232/+0.024 ns`，只属于该视觉版本。
- S7 托盘候选集成实现为 23,283 LUT、63 BRAM tile、42 DSP，WNS/WHS `+0.064/+0.013 ns`，余量很薄；模型、RTL 或约束变化后必须重新实现，不能把两个版本的资源相加。
- S1/S2/S4 已有无机械臂 DRY_RUN 板测。S5 随机测试权重集成 BIT 的板测冒烟通过；S6 合成 PC/网络/PS/PL 路径及 S7 托盘取消的无机械臂台架测试通过。S8 在一条 S7 合成运行上验证了指标工具，不能当作物理任务性能。真实七类识别、RGB-D/IK、机械臂抓取递送均未验收。

## 开发入口与保留路径

- 总计划：`docs/EMBODIED_OBJECT_HANDOVER_PROJECT_PLAN_CN.md`
- 当前活动分类包：`model_package/active/`
- 当前分类参考导出：`quantized_export_v3_failure_adaptation/`
- 当前Locator参考导出：`quantized_locator_v16_failure_adaptation/`
- 训练与向量工具：`model/`
- FPGA源码与测试：`rtl/`、`sim/`
- 构建与模型检查：`scripts/`
- 约束：`constraints/`
- 历史视觉实现报告：`reports/phase2_l2_autonomous_final_implemented/`
- 板测证据：`board_evidence/`；部分本机未跟踪，GitHub 上未必可见。
- S5/S7 集成工作与交付：`s5b/`、`s7b/`、`deliverables/`；当前为本机未跟踪资料，不把它们当作远端基线。
- 保护基线：`releases/Gesture_Phase1_Baseline_v1.0/`
- 分类器/Locator联合基线：
  `releases/Gesture_Phase2_L1_v16_Classifier_v3_20260820/`
- OV5640同帧ROI基线：
  `releases/Gesture_Phase2_L2_OV5640_8Lane_Top1_SameFrame128_Confirm2_3_SCCB_Retry3_Functional_RC_Draft1_20260826/`

## 当前交互决策

- 1/2/3直接在手势等待区内输入，由连续帧防抖、置信度条件和一次性任务锁定处理。
- PALM_READY在最终短轨迹前确认；机械臂遮挡后允许在受限有效期内完成短时盲交付。
- FIST_CANCEL是普通取消，不是急停；暂停不用额外手势。
- 首版不增加ToF、接触传感器或腕部相机。

## 阅读规则

- 默认从本文件开始，不整篇读取`PROJECT_LOG.md`。
- 历史日志、旧发布和旧部署仅在排查历史问题时按关键词读取。
- 不把计划目标写成现有板测成绩。
- 不扫描或恢复已清理的可再生Vivado/XSim输出。
- 以下带日期的记录为历史快照；与上面的当前状态冲突时，核对版本包、BIT/HWH、报告与板测日志，不从旧计划推断新功能已通过。

## 2026-09-21 清理状态

- 已删除207个历史或可再生目标，共5,996个文件、约6,020.88 MB。
- 已删除绝大多数历史工程快照、旧部署副本、旧候选模型和Vivado/XSim生成物。
- 当前保留三份关键发布基线、两份当前部署、活动模型、训练/量化链、源码、脚本、报告和板测证据。
- 清理后非Git、非备份内容约122.25 MB，默认`rg --files`可见1,068个文件。
- 保留清理前v1.2快照和清理后精简快照，共约185 MB。
- `backups/`默认不参与搜索；历史恢复优先使用用户2026-09-15整目录备份或保留的项目快照。

## Phase 3机械臂仿真控制支线状态

- Windows/CoppeliaSim外部Python已完成六关节、TCP、位置IK、夹爪语义和无FPGA抓放FSM验证。
- 已冻结开发用轨迹合同`phase3_trajectory_q16_16_v1`：六通道Q16.16弧度、逐级最近值/半值远离零舍入、32逻辑tick/段。
- 已从通过的抓放结果导出11个关键帧、10段、321个CSV/MEM黄金样本，供后续轨迹RTL和Testbench位精确比对。
- 固定32 tick的隔离PL轨迹叶模块已实现；XSim对10段、320个生成样本逐位通过。PYNQ-Z2
  OOC综合为1,461 LUT、934 FF、14 DSP、0 BRAM，100 MHz内部寄存器路径WNS `+0.968 ns`。
  这不是整机实现；OOC端口无板级IO/LOC约束，AXI/FIFO/UART和bitstream均未完成。
- 已增加可编程节拍输出层：32×192段缓冲、命令ready/valid、输出反压保持和最小周期门禁。
  XSim对10段/320点及非法周期、忙时命令、7周期反压全部通过；OOC为1,649 LUT、1,410 FF、
  3 BRAM、14 DSP，100 MHz内部WNS `+0.968 ns`。UART、取消/反馈超时仍未完成。
- 已增加独立AXI4-Lite开发控制层（ABI `0x0000_3001`）：六轴起点/终点/周期shadow经COMMIT
  原子提交，稳定六轴样本窗经POP确认，支持DONE/ERROR中断和sticky诊断。XSim两段64点
  逐位通过，并覆盖AW/W乱序、响应背压和错误路径；OOC为1,894 LUT、1,919 FF、3 BRAM、
  14 DSP，100 MHz内部WNS `+0.968 ns`。隔离BD地址固定`0x43C2_0000/4K`；post-route为
  2,241 LUT、2,361 FF、3 BRAM、14 DSP，WNS/WHS `+0.677/+0.036 ns`，路由错误与DRC
  Error均为0，已生成BIT/HWH/XSA；尚未上板或连接UART。
- 已增加`ps/robot/trajectory_axi_driver.py`，支持显式基地址、ABI检查、shadow/COMMIT、
  样本读取/POP和错误解码；FakeMMIO聚焦测试4项通过。最小板端smoke部署目录已生成，
  仅验证PS-MMIO-PL-MMIO，不驱动机械臂。
- 当前20 Hz外部Python/ZMQ文件回放无整周期超限；50 Hz逐轴远程写入有130次整周期超限，尚未完成批量桥接优化。
- 该合同不是最终RoArm UART协议；物理周期、舵机零位/方向/限位和设备单位必须等待实物标定。

## 2026-09-24 Phase 3 S1双机械臂数据通路候选（v0.1.1，未上板）

- 隔离S1 overlay `phase3_s1_armpath`（候选）：轨迹窗口`0x43C2_0000`以ABI `0x0000_3002`运行，样本在PL内
  直接进入机械臂后端`0x43C3_0000`（ABI `0x0000_3101`）；RoArm JSON行/桥v1与SO-ARM101 Feetech半双工
  共用一个模板格式化器；反馈看门狗、急停许可、最后门控。
- 只有Python测试PASS；Icarus/pyslang/Yosys为补充层；XSim/Vivado/板测/实物均未运行。
- v0.1.1：Vivado资源以`report_utilization`总“Slice LUTs”（含LUT as Memory）判定；OOC三构建全部报告，
  超预算（6000 LUT/6000 FF/8 BRAM tile/16 DSP）打印`OVER_BUDGET`并以12退出；实现以运动子系统`armpath_0`判定。
- 官方协议字段、标定参数和引脚全部TBD，真实输出默认拒绝；详见版本包
  `Gesture_Phase3_S1_DualArmDataPath_Candidate_v0.1.1`的`README_CN.md`与`config/UNKNOWN_PARAMETERS.yaml`。

## 2026-09-24 Phase 3 S1 v0.1.1 本机验收更新

- XSim 12/12 PASS；Vivado 2026.1三种OOC构建和双后端完整实现通过。
- 运动子系统post-route为4903 LUT、3917 FF、3 BRAM、14 DSP；100 MHz WNS/WHS为`+0.336/+0.033 ns`，失败端点、路由错误、DRC Error均为0。
- 已生成BIT/HWH/XSA和`deploy/phase3_s1_armpath_v0.1.1_20260924/`；板卡连接检查超时，B1-B6未运行，状态是`IMPLEMENTED_CANDIDATE`，不是`BOARD_PASS`。

## 2026-09-25 Phase 3 S1 板测更新

- 用户提供的板端日志显示BIT/HWH哈希匹配、B1只读PASS、B4 RoArm UART回环复测PASS（32帧/32反馈，最长帧8.42495 ms，错误和超时均为0）。首次B4因许可线未接而报`no permission`，接线后通过。
- B2 RoArm与B3 SO-ARM101的DRY_RUN软件检查均PASS；外部TX/DIR空闲电平仍未观察。B5 SO-ARM101仿真板端脚本PASS（32帧、213有效反馈、0错误/超时），但PC端replies日志未提供，最大处理周期73.22813 ms，持续50 Hz尚未证实。B6后续运行检出`ESTOP_EVENT`且停在11/32帧，负向逻辑判据PASS；外部TX停发波形尚未提供。B4b抓包未运行，整体为`PARTIAL_BOARD_PASS`。详见`board_evidence/phase3_s1_v0.1.1_partial_20260925.json`。
