# PyQt 桌面前端

保留现有界面和操作流程，通过 HTTP 提交配置与任务，通过 WebSocket 接收进度、日志和结果。用户配置、内置提示词和业务文件读写由后端负责。

前后端使用协议版本 2。页面通过 `BackendClient` 的明确方法调用对应 HTTP 接口，例如翻译使用 `POST /api/tasks/translation`，表格翻译使用 `POST /api/tasks/table/translate`，保存使用 `POST /api/project/save`。WebSocket 业务通知使用 `{type: "notification", name: "translation.progress", data: {...}}` 等命名消息；表格通知通过 `view` 定位页面。数字事件编号仅用于前端本地 UI 通知，不跨进程发送，也不提供通用 `/api/commands` 命令入口。

更新时需要同时替换前端与后端并重启。首次连接和每次 WebSocket 重连都会通过 `/health` 校验协议版本；不兼容时显示桌面要求版本和后端实际版本，不接收旧协议的业务消息。重连仍会重试，后端更新到兼容版本后可恢复连接。

手动导出和翻译完成后的自动导出通过 `project.export.completed` 返回完整的文件清单和报告。桌面分别提示成功、部分失败或失败，并将完整报告和逐文件错误写入前端日志，保留错误码、源文件路径等诊断信息。停止任务且未执行导出时不发送导出完成通知。

## 目录结构

```text
Frontend/
  __main__.py                  python -m Frontend 入口
  app/
    bootstrap.py               启动和依赖组装
    window.py                  主窗口和页面注册
    navigation.py              导航项目
    event_bridge.py            网络事件切换到 Qt 主线程
    backend_connection.py      健康检查、复用或启动独立后端进程
    updates.py                 桌面更新流程和更新检查线程
  pages/
    workspace/                 项目启动、提取、翻译和校对
    providers/                 接口管理、模型选择和参数编辑
    prompts/                   翻译、提取提示词编辑
    settings/                  应用、任务和输出等设置
    tables/                    词典、排除表和替换表
    logs/                      运行日志
  components/
    cards/                     可复用设置卡片和信息卡片
    dialogs/                   可复用对话框
    tables/                    表格控件、委托和编辑辅助
    ...                        通知、分段控件、分隔线等
  services/
    backend_client.py          HTTP 请求、WebSocket 接收和重连，不依赖 Qt
    project_state.py           项目快照合并与远端缓存/文件读取代理
    editor.py                  后端编辑规则适配和批量校验结果缓存
    backend_paths.py           查询后端的路径默认值
    protocol.py                JSON 协议常量和序列化
    public_tables.py           用户选择的词表文件导入导出
  models/                      JSON 项目/文件/条目等显示数据结构
  platform/                    原生文件对话框、macOS 集成、进程启动和启动互斥锁
  core/                        前端事件、远端配置门面、日志、路径和主题
  resources/                   图标、本地化文本、更新程序和版本信息
```

`app` 组装页面和服务；`pages` 使用通用组件、平台适配和服务；`components` 不依赖具体页面；`services` 不依赖 Qt 或页面；`core` 和 `platform` 不反向导入页面或应用层。只属于一个页面的卡片、对话框和子页面保留在对应功能目录中。

“任务配置”中的“音译设置”管理说话人识别、长音频切片时长和并发数，“图译设置”管理输出尺寸、百炼提示词改写和译图导出格式。两页仅展示设置卡片，修改后自动保存到独立任务配置，切换接口不改变这些设置；未完成或无效的文本输入暂不保存，离开页面时会尝试保存并提示错误。接口管理仅编辑名称、地址、密钥、格式、模型及协议专用字段；转录、生图和任务的请求超时统一为 300 秒，不再提供编辑。语言提示、随机种子和全局补充翻译要求保留后端/API兼容及已有值，不在这两页编辑；图片工作区也不提供补充要求输入。

Python 文件和包使用小写下划线，类名保持原有命名。新增页面放入对应功能目录，在 `app/window.py` 或所属工作区页面注册；可复用控件放入 `components`，网络访问放入 `services`。

前端不导入 `Backend`，可以单独复制 `Frontend`、`AiNiee.py` 和 `requirements-frontend.txt` 部署。`core/config.py` 只访问远端配置；`models` 将 JSON 转为界面数据；`services/project_state.py` 保持显示对象身份并将编辑、搜索和校对转发到后端。业务规则只在后端执行，断线不会回退到本地配置或业务实现。

## 媒体接口与工作区

“接口管理”中的转录和生图页面按“官方接口 / 自定义接口”展示卡片。点击“添加接口”后，先填写名称并选择平台，再填写密钥等连接信息并完成创建。已有接口可从卡片菜单编辑、激活或删除；编辑时修改自动保存，未完成或无效的字段会提示修正。转录官方预设包含“火山豆包（极速）”，生图官方预设包含百炼、火山 Seedream 5.0 Pro 和 Gemini 官方；Gemini 使用基地址 `https://generativelanguage.googleapis.com`、`Gemini` 格式和 `gemini-3-pro-image` 模型，各接口独立保存凭据。

“火山豆包（极速）”直接使用导入的本地音频。开始转录时会固定本次选择的接口，后续切换激活接口不会改变已启动的处理。图片工作区可使用百炼、火山或 Gemini 进行单步整图翻译，输出尺寸及其他任务选项仍由“图译设置”管理。

图片和音频起始页的最近项目可双击打开。每条记录右侧的删除按钮在确认后清理该项目进度、预览、解压素材及生图缓存，保留外部原始文件和用户导出的文件。删除成功后列表立即更新；失败时保留条目并显示原因。

媒体项目详情分为“翻译”和“校润”两页，顶部共用返回、保存和导出操作。翻译页展示媒体项目的进度、条目或页数、文件数与本次处理用时，并集中放置流程和语言选择。校润页提供可搜索的文件树；图片只展示原图与译图对照，支持缩放和刷新预览；音频将字幕表格放在时间轴上方，底部播放条展示当前文件已译/总条目数，通过字幕和时间轴定位播放。切换两页保留当前文件和未保存修改，校润编辑仍自动保存；后台处理不会切走当前页面，保存和处理成功后不保留底部提示行。媒体监控只使用本项目快照与匹配操作的阶段进度，不订阅普通文本项目的全局统计。

翻译页的“任务状态”卡片显示当前处理阶段、实时计数及停止或异常信息，替代原“待复核文件”计数。翻译页底部不再显示状态行和进度条；任务进度环仍保留。

图片校润页不显示底部状态提示，项目文件列表仅显示文件名。生成进度及处理状态集中显示在翻译页的监控卡片中。

“图译设置”包含“任务设置”和“翻译提示词”两个子页面。提示词页复用文译提示词库的布局，支持预设预览、搜索、新建、编辑、删除及选择自定义提示词；选择后自动保存，在下次生成译图时生效。自定义内容替换默认图片翻译指令，原文和目标语言由翻译页提供。图片提示词与文译提示词独立保存，切回系统预设即可恢复默认指令。

字幕格式与字幕内容由“音译设置”的“导出设置”管理，图片格式由“图译设置”的“导出设置”管理，修改后自动保存。点击项目顶部的“导出结果”时读取最新设置；旧配置缺少导出项时使用 SRT 双语字幕、PNG 图片。对应配置分别为 `audio_translation_settings.export` 的 `format/mode` 和 `image_translation_settings.export` 的 `format`。

翻译页的图片项目直接点击“生成译图”，不显示步骤选择区域。原图与单步翻译提示词一次提交给生图接口，不提供检测、识别、逐条翻译和本地回填流程。音频仍为“转录字幕 → 翻译字幕”，可通过步骤卡片分别或组合选择执行，按钮和卡片展示当前选择及运行状态。

每次点击生成译图会发送 `regenerate=true` 重新生成所选项目，可能再次调用付费服务；预览刷新仅重新加载已有图片。音频转录发送 `retranscribe=true`，字幕翻译发送 `retranslate=true`。完成后使用项目顶部“导出结果”选择目录，格式取自任务设置。图片翻译只保留整图单步模式，不再使用指定文本替换清单或独立文字识别接口。Gemini 输出尺寸支持 `auto`、`1K`、`2K`、`4K`，不使用百炼的自动改写开关；`auto` 由模型选择尺寸。


## 启动

安装前后端依赖后，在项目根目录运行以下任一命令；默认连接 `http://127.0.0.1:3389`。入口先检查健康状态：已有服务就直接连接，本机服务未启动时自动启动独立后端进程，等待就绪后打开界面。多个入口同时启动时，通过进程间锁避免重复启动：

```powershell
python AiNiee.py
python -m Frontend
```

连接单独运行的后端：

```powershell
python -m Backend --port 3389
# 在另一个终端启动桌面
python -m Frontend --backend-url http://127.0.0.1:3389
```

`AINIEE_BACKEND_URL` 可指定连接地址，`AINIEE_API_TOKEN` 指定访问令牌。只对无路径前缀的本机 HTTP 地址自动启动；远程地址、HTTPS 地址仅连接已有服务，鉴权失败或协议不兼容时不会重复启动。源码默认使用当前 Python 在独立进程中运行 `Backend` 入口；发布版默认启动随包的独立后端可执行程序，无需安装 Python。可用 `AINIEE_BACKEND_EXECUTABLE` 指定后端程序，或用 `AINIEE_BACKEND_PYTHON` 和 `AINIEE_BACKEND_DIR` 指定源码后端的解释器和目录。启动最多等待 60 秒。后端启动、运行及 Uvicorn 日志统一写入后端主日志（便携模式默认 `Logs/backend/ainiee.log`），可通过 `AINIEE_BACKEND_LOG_DIR` 指定目录；不再生成单独的启动日志。前端日志仍由前端独立记录。

前后端始终为独立进程，不提供单进程模式。关闭窗口时选择确认，会通过 FastAPI 退出接口通知后端停止任务、保存缓存并退出；选择取消则两端继续运行。请求失败时保留窗口并提示原因。仅关闭网络连接或前端异常退出不会触发后端退出。依赖安装、配置所有权及接口协议见 [后端说明](../Backend/README.md)。

`core/resources.py` 统一定位 `Frontend/resources`，支持 `AINIEE_FRONTEND_RESOURCE_DIR` 覆盖路径和 PyInstaller 包内路径。Windows/macOS 桌面仍以根目录 `AiNiee.py` 为入口，只收集前端模块和资源并排除 `Backend`。打包脚本另行构建 `AiNieeBackend`，后端业务模块、配置模板和模型依赖只进入后端程序目录，两端使用各自的 Python 运行环境。

构建完整发布包时，先安装 `requirements-frontend.txt`、`requirements-backend.txt`、PyInstaller 6.21+，再以 `--no-deps` 安装 `requirements_no_deps.txt`。Windows 执行 `python Tools/pyinstall.py`；macOS 执行 `python Tools/pyinstall_macos.py`。Windows 发布目录包含 `AiNiee.exe`、前端 `_internal` 和 `backend` 子目录，必须整体解压。macOS 后端位于应用包的 `Contents/Helpers/AiNieeBackend.app`，通过其中的 `Contents/MacOS/AiNieeBackend` 启动；后台包不会显示额外的 Dock 图标。
