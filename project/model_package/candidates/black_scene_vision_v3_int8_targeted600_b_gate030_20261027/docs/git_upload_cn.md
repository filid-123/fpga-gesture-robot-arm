# Git范围与获取

原仓库https://github.com/filid-123/Gesture.git，分支dev/Rain，本版只新增`model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027`及PROJECT_LOG。旧v1/v2、active、RTL不改；不上传训练原图全集、开发数据、S快照/录像、.venv、校准cache或重复ZIP。26个小TRAIN源图仅用于golden复现。

包内.gitattributes禁止autocrlf/clean过滤改变参数和向量字节，.gitignore明确放行本包.bin。提交前核对每个candidate Git index blob SHA与本地manifest一致，路径清单只允许本candidate和PROJECT_LOG，不用git add -A或强推。原克隆需干净并fetch后保持dev/Rain fast-forward；若失败保留文件检查，不reset覆盖。

硬件同事在自己的干净工程先fetch该分支，通过既有流程取得这个candidate目录；不把整个算法工作树覆盖硬件开发分支。实际提交SHA和远端确认由发布完成记录提供，本说明不伪造尚未产生的commit。
