# 网页与FPGA/视觉桥接接口草案 v1

这是本次新建的HTTP适配约定，不是已经实现的板端ABI。`server.py`负责将浏览器锁定请求一次性转交给桥接服务，桥接端由负责FPGA和视觉的队友实现。浏览器始终以设备确认作为“已生效”依据。

## 网页服务

| 方法/路径 | 含义 |
|---|---|
| GET /api/config | 当前展示主机信息、会话CSRF令牌、最多3选 |
| GET /api/status | 桥接状态/实际模式/实际手势映射/单调revision/未确认请求及识别视频地址 |
| POST /api/mode-lock | 模式和手势顺序的显式提交，需X-Console-Token，禁止跨Origin |
| POST /api/vision/infer | 显式提交本次相机帧/照片PNG，返回同帧图像与检测框 |
| POST /api/vision/sample | 对固定历史样例运行真实模型，标为sample_replay |

点击导航A/B仅改变URL hash和页面，不POST。没有`bridge_url`时锁定返回503/outcome=not_applied。模板图片始终是示意图，本地识别和外部视频均使用真实检测输出；浏览器不会绘制虚假检测框或置信度。

## 桥接服务 GET /status

从`bridge_url`读取。示例为模式A已生效、设备空闲：

```json
{
  "contract": "zhixing.console.bridge.v1",
  "connected": true,
  "idle": true,
  "revision": 7,
  "active_mode": "A",
  "gesture_bindings": [
    {"gesture": 1, "object_id": "red_cube"},
    {"gesture": 2, "object_id": "yellow_cube"},
    {"gesture": 3, "object_id": "blue_cube"}
  ],
  "recognized_classes": ["red_cube", "yellow_cube", "blue_cube", "eraser", "small_canister", "scissors"],
  "last_request_id": "先前请求编号",
  "last_request_outcome": "applied"
}
```

必须确认FPGA在线才给connected=true，不能只因HTTP进程在线就返回true。`idle`表示现在可原子切换任务配置。revision为非负整数，配置每次生效单调递增，重启后桥接应维护会话一致性/使旧配置不能误当新配置。

没有生效模式可用`active_mode:null, gesture_bindings:[]`。模式A映射固定；模式B允许1—3个不同类别，gesture连续为1/2/3，按所选顺序排列。recognized_classes是实际视觉支持类别；自行登记而未被模型支持的类别不能直接锁定。抓取轨迹/实物能力仍应由执行系统另行检查。

## 桥接服务 POST /mode-lock

网页服务先查询状态，拒绝未连接、非空闲、revision冲突、超过3选、重复ID或未接入模型的类别。检查通过后，只发送一次以下请求：

```json
{
  "contract": "zhixing.console.bridge.v1",
  "request_id": "唯一UUID",
  "expected_revision": 7,
  "mode": "B",
  "gesture_bindings": [
    {"gesture": 1, "object_id": "eraser"},
    {"gesture": 2, "object_id": "red_cube"},
    {"gesture": 3, "object_id": "small_canister"}
  ]
}
```

桥接必须在设备端**原子复核空闲与revision、去重request_id、应用整个模式+映射、等到FPGA确认**后回复。HTTP已收到不能替代FPGA已生效。不能在此接口中顺带启动抓取、回HOME或自动重发运动。

成功响应HTTP200：

```json
{
  "request_id": "同一个UUID",
  "applied": true,
  "status": {
    "contract": "zhixing.console.bridge.v1",
    "connected": true,
    "idle": true,
    "revision": 8,
    "active_mode": "B",
    "gesture_bindings": [
      {"gesture": 1, "object_id": "eraser"},
      {"gesture": 2, "object_id": "red_cube"},
      {"gesture": 3, "object_id": "small_canister"}
    ],
    "recognized_classes": ["red_cube", "yellow_cube", "blue_cube", "eraser", "small_canister", "scissors"],
    "last_request_id": "同一个UUID",
    "last_request_outcome": "applied"
  }
}
```

网页服务验证请求编号、模式、完整有序映射、revision增加和applied状态；任一项不符，不显示成功。锁定B的变化还包含编号变化，因此取消再选之后也必须重新提交。

## 错误与不确定状态

- 请求发出前的未连接/忙/非法选择/旧revision：不转发，返回not_applied。
- POST超时、断链、错误或无匹配确认：返回504/outcome=unknown，不自动重发，不声称“实体没有变化”。同一服务进程中阻止后续锁定。
- 桥接`GET /status`用`last_request_id`及`last_request_outcome:applied|rejected`明确解决该请求，网页服务才解除阻止。桥接应持久化去重/请求结果；网页服务重启不能成为设备端重复执行的理由。
- 已释放物体、取消/故障等机器人行为不属于此网页接口。此次服务没有改动板端控制/运动状态机。

## 识别视频

`vision.stream_url`目前接受浏览器可显示的HTTP(S) MJPEG或持续图像流，带框视频由视觉端合成，须用同一帧的识别输出，不能把旧框叠到新图上。建议同机端口或同一HTTP网关，部署HTTPS页面时视频也需HTTPS。HLS/RTSP/WebRTC需另加播放器适配，不能直接把RTSP地址塞给img。

浏览器本地摄像头模式可先展示真实原始画面，使用getUserMedia且用户明确选择设备；点击“开始识别”后才将PNG传给本机模型推理，不使用浏览器模型。真实识别程序占用相机时应使用其输出视频接口，而非同时打开同一设备。


## 已实现的本机六类检测接口

`GET /api/status`的`vision.local`给出available/loaded/backend/classes/sample_available/npu_accepted/last_error；查询不加载模型，且不改变FPGA connected/active_mode。available表示模型文件在本机，依赖或哈希错误仍可能在首次推理时返回503。

两个POST都需要同源和`X-Console-Token`。`infer`请求：

```json
{"frame_id":"唯一帧ID","source":"camera","image":"data:image/png;base64,..."}
```

source只接受camera/photo，sample接口只需要frame_id，来源固定为sample_replay。无任意文件路径参数。PNG大小最多8MiB，原尺寸32px起、最长边1920px、总像素不超过1920×1080；不在适配层旋转、翻转、矫色或重缩放。浏览器文件输入会解码为PNG，接口哈希指该次提交的PNG和解码BGR像素，不代表原JPEG文件字节。

返回`schema=zhixing.console.vision.v1`、原frame_id/source、frame_sha256（BGR像素）、input_file_sha256、image_size_wh、detections、image（同一帧的显示JPEG）、实际backend、冻结模型SHA与已校验文件数、耗时。detections只含class_name/confidence/bbox_xyxy_raw/trained，不带旧硬编码task_id；raw框坐标与输入原图尺寸一致。JPEG仅用于显示，检测仍基于原PNG解码像素。

返回始终`physical_execution=false/path_submissions=0/metric_coordinates_enabled=false/npu_accepted=false`。没有识别目标时detections为空；不能补上历史框。浏览器在同一显示JPEG上绘框，当前选中类别按当前顺序显示编号；其余类别仍显示识别框，不因此获得实体任务绑定。

一次最多处理一帧，忙时409，不排队/重试；请求或图片错误400/413，模型/依赖/冻结校验不通过503。浏览器识别超时或失败会清除框，回到原始画面并暂停；切页/断开后的迟到结果按会话代数丢弃。图像只留在内存，不写入上传目录。浏览器来源不是经过原曝光/标定采集链路验证的毫米定位输入，禁止直接复用此预览输出执行抓取。
