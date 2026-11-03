# 复现和源码快照边界

日常接入只使用包内reference、models、quantized、golden与contract，按README三条python -I -B命令在独立目录验证，CPU可运行，不需要生产者D盘、原TRAIN全集或CUDA。

tools中的export/build/common及旧版helper是构建源码快照，ROOT/DATA路径按原训练工作区组织，不能在当前包里直接执行它们重建参数。完整重建需恢复原工作区布局、已审核970个Locator TRAIN与959个Classifier父图及原SHA、冻结v2核心参数和600/old400两PT。先export（只读TRAIN，核心保持、新G和Classifier max-range PTQ），参数冻结后--validate（三个DEV，只比较不挑常数），再build/docs/hash/隔离验证。原训练全集、校准大缓存和工作区绝对来源映射未上传；公开calibration.json保留父图ID/输入SHA和统计，黄金只含26个TRAIN夹具，不含DEV/TEST或现场S图。

新G1范围取实际整数F3按原尺度反量化后通过浮点新G1的全TRAIN ReLU最大值；G2逐输出通道量化并换至原conv5几何尺度。Classifier按新整数几何得到的959个生产B32（背景为已批准peakROI）执行严格100%浮点激活最大值PTQ。权重/bias半数远离零，运行时正M右移半数向正无穷，累加及融合按signed32 modulo wrap，隐藏uint8 clip，FC2无ReLU。没有开发百分位/seed搜索或量化感知训练。

本版参数与模型冻结后不可原位重标量化“改善”验证数；下一次实验另建版本。golden向量用于数值对齐，不是准确率样本。portable_verification.json为构建时隔离运行记录；最终包所有文件和CHECKSUMS可再次哈希核对。
