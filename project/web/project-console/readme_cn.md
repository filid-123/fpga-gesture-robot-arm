# 知行 · 项目展示与协作工作台

根据用户2026-10-29的两页草图开发。网页暂用“知行”作展示名，浅色、青绿选中态，左侧模式选择，中部说明/物体库，模式B右侧摄像头画面，右上角AI PC名称和型号。

## 打开页面

在项目根目录运行一条命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_project_console.ps1
```

浏览器访问 <http://127.0.0.1:8765/#/mode-b>。模式A地址为 <http://127.0.0.1:8765/#/mode-a>。停止服务用终端Ctrl+C；关闭浏览器页面会释放页面使用的相机。

基础网页使用Python 3.10+和标准库，无前端构建、CDN或远程字体。六类识别预览复用已有numpy/OpenCV/ONNX Runtime环境与冻结模型，不下载新模型。启动优先使用`.venv-multiobject`，其次运动环境，最后PATH中的Python。可用`-Port 8766`更改端口。`file://`直接打开HTML不支持本地API，建议通过启动脚本访问。

## 网页打不开时

这是本机网页服务；电脑重启或服务进程退出后，需要重新运行启动脚本，GitHub仓库地址本身不提供在线网页。请在PowerShell执行下面这一整行，并保持该终端开启：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\redacted_user\Documents\ChatGPT\FPGA-具身智能-collab\scripts\start_project_console.ps1"
```

看到`PROJECT_CONSOLE: http://127.0.0.1:8765/#/mode-b`后，在这台电脑的浏览器打开该地址。另一台电脑的127.0.0.1指向另一台电脑，无法访问这里的服务。若8765已占用，可加`-Port 8766`并打开对应端口。

## 已实现的交互

- A/B为两个可直接访问的页面状态，点击后导航加深；仅浏览不发送设备命令。
- A显示三色固定物体、手势映射和抓取/缓冲/交付流程图。B显示动态识别简介、六类物体卡片、右侧相机。
- B最多选3个，先后标记1/2/3；再次点击取消，后续编号自动前移；重新选择排在末尾。切到A再回来保留B的选择。
- 物体库含红/黄/蓝木块、圆柱、橡皮、剪刀。加号可登记名称/识别类别ID/图标，新物体标“待接入”，**添加名称不训练或扩展识别模型**。
- 模式锁定独立于页面浏览；B至少选择1个才可锁定。点击后只提交一次，等待设备确认。浏览页与设备实际模式分别显示，更改物体选择后需再次锁定；正在执行任务或状态过期时由接口拒绝。
- 设备接口未接入时显示未连接，点击锁定不假装成功；请求结果不确定时阻止重复提交，后续状态查询核对。
- 右上角初始读取当前主机的公开制造商/型号，不作NPU能力声明；点击可改为正式AI PC名称/型号。编辑、B物体选择和自定义类别保存在当前浏览器本地，不当作设备已生效配置。
- 相机只有点击连接时才申请权限，可选工作区右侧摄像头，不访问麦克风。连接后先显示原始视频，点击“开始识别”才发送PNG帧到本机冻结检测器；每次一帧，完成后再采下一帧，不自动保存图像。暂停/断开或切到A后丢弃迟到结果。
- “查看识别样例”对历史照片运行真实六类模型，始终标“样例回放”；“识别照片”支持选取本地照片，标“照片识别”。框、类别、置信度和编号均与同一帧绑定，编号跟随当前选择，不继承旧固定task ID。初始图仍为明确标识的示意图。
- 桌面/平板/手机响应式布局、键盘焦点/ARIA选择态、ESC关闭对话框、支持减少动画偏好。

## 真实设备和识别视频接入

已从Git核对filid最新模式一代码和Rain手势模型，并接通本机真实六类物体检测预览。来源、固定commit及迁移依赖见[SOURCES_CN.md](SOURCES_CN.md)。现有Git代码还没有统一网页A/B切换接口，因此实体模式锁定仍待桥接；本网页不自动归位、抓取或发送运动请求。

1. 复制`config.example.json`到自己的配置文件，把`bridge_url`设为队友桥接服务根地址，`vision.stream_url`设为同帧带识别框的MJPEG/连续图像流地址。
2. 若有认证，通过`PROJECT_CONSOLE_BRIDGE_TOKEN`环境变量传令牌，不写进浏览器或Git。
3. 用`-Config`指定该文件重新启动；桥接协议见[API_CN.md](API_CN.md)。桥接端负责实际模式切换、任务空闲检查、识别类别支持和FPGA确认。已有P3S6协议没有网页模式切换消息，不能把页面A/B直接等同已有ARM_BACKEND的OFF/DRY_RUN/LINE寄存器值。
4. 浏览器将绑定顺序提交给桥接，桥接必须把独立MODE_B profile中的手势1/2/3映射到所选类别；不能继续硬编码旧1红/2橡皮/3圆柱而忽略网页选择。

示例配置（地址为开发示例）：

```json
{
  "device": {"name": "项目AI PC", "model": "填写正式型号"},
  "bridge_url": "http://127.0.0.1:9000",
  "bridge_timeout_s": 3,
  "bridge_token_env": "PROJECT_CONSOLE_BRIDGE_TOKEN",
  "vision": {"stream_url": "http://127.0.0.1:9001/annotated.mjpg"}
}
```

新增类别还需视觉模型支持；识别能力不代表已验证该物体的抓取轨迹。三类成功实体路径及速度/局部补偿沿用独立联测包，此网页未更改它们。当前也未验证真实NPU或板卡闭环。

## 结构与验证

`public/`为无依赖网页；`state.mjs`管理选择/映射；`server.py`提供静态资源、设备信息、状态和锁定适配；`vision.py`按需加载原冻结六类检测器，仅CPU预览，不启用桌面坐标或实体动作；服务器只开放public目录，配置/后端源码不通过静态URL暴露。模式变更请求有本机页面令牌与Origin核对。默认只监听127.0.0.1。

```powershell
python -B -m unittest scripts.test_project_console
node --test web/project-console/test-state.mjs
```

浏览器回归使用Playwright与Chrome，仅在隔离浏览器内使用合成相机和模拟设备确认；真实机械臂/相机/FPGA未访问。需要重跑时可在项目`artifacts`下单独安装Playwright，路径由`PLAYWRIGHT_MODULE`指定，Chrome路径可用`CHROME_PATH`指定，然后运行：

```powershell
node web/project-console/test-browser.cjs
```

当前9项后端、5项帧绑定/预览接口、6项状态、14项原浏览器和7项识别浏览器检查共41项通过。识别检查使用真实模型/历史样例，合成摄像头用于验证相机流程，没有打开实体摄像头。浏览器用例覆盖最多3选、取消重排、页面与实体模式分离、未连接锁定、添加/重复类别、编辑设备、合成相机连接/断开、390/768/1500px无横向溢出、精确确认和不确定结果禁止重发。截图/报告位于`artifacts/project_web_20261029/`。

识别补充回归需六类识别环境：

```powershell
.venv-multiobject\Scripts\python.exe -B -m unittest scripts.test_project_console_vision
node web/project-console/test-vision-browser.cjs
```

可用`vision.local_enabled=false`禁用本地推理；外部带框视频仍可通过`vision.stream_url`接入。浏览器相机预览不控制原标定采集脚本的曝光/机位，故此处只展示像素检测，不输出毫米坐标或触发抓取。正式NPU运行和FPGA模式切换需要继续联测。
