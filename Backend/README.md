# FastAPI 后端

后端独立管理配置、项目、缓存、翻译、表格条目润色、提取、校对和导出。PyQt 桌面仅通过 HTTP 与 WebSocket 访问后端，两端不导入对方的 Python 模块。

其他 MCP 客户端可连接 `http://127.0.0.1:3389/mcp`，使用 Streamable HTTP 提交文档、图片和音频翻译，并查询或取消任务。MCP 与现有接口共享队列，沿用 `AINIEE_API_TOKEN`；无需另起进程。连接、工具参数和官方 SDK 示例见 [MCP 接入说明](docs/mcp.md)。

后端提供统一中间模型及 `/api/v2` 接口，使用文档、图片、音频三个任务队列。同类型任务按提交顺序执行，不同类型最多同时运行三个顶层任务；单次翻译内部保留多线程批量处理，各任务独立使用线程数与模型额度，不共享限流器。PDF 仅使用 BabelDOC；Office 自动化转换链及旧 `.doc` 入口已移除，DOCX、PPTX、XLSX 的原生读写保留。音频支持本地读取、在线转录、翻译与字幕导出；图片支持独立在线 OCR、翻译、擦字回填，也可使用独立生图接口直接翻译整图，两种流程均保存中间模型。当前调度与调用方式见 [任务队列](docs/task_queues.md)，历史设计见 [后端改造计划](docs/backend_refactoring_plan.md)，具体流程见 [音频接口](docs/audio_pipeline.md)、[OCR 图片接口](docs/image_pipeline.md)、[生图翻译接口](docs/image_generation.md) 和 [图片/音频预览工作区](docs/media_workspaces.md)。

超过 5 分钟的音频自动通过 Silero VAD 选择切点，并发提交带上下文重叠的切片，合并回原始时间轴。失败切片可通过返回的中间模型恢复，已完成片不会重复提交；长音频处理需要 FFmpeg。

业务通过明确的应用服务方法调用，后端不再使用全局事件总线或全局停止状态。结果提交、缓存保存和生命周期由 Runtime 显式管理，保存完成后才发送具名通知。桌面连接协议为 2，前后端需要配套升级；旧 `/api/commands` 数字事件入口已删除。

## 启动与部署

源码版安装前后端依赖后，运行 `python AiNiee.py`（或 `python -m Frontend`）即可。入口优先连接已有后端；本机后端未启动时，会自动执行 `python -m Backend` 启动独立进程并等待健康检查通过。也可以按以下步骤分别启动。

后端环境需要 Python 3.12+：

```powershell
python -m pip install -r requirements-backend.txt
# 按项目依赖说明安装 MediaPipe / BabelDOC 等特殊依赖
python -m pip install --no-deps -r requirements_no_deps.txt
python -m Backend --host 127.0.0.1 --port 3389
```

PDF 解析使用项目固定的 `pymupdf==1.26.7`。已在真实 PDF 上复现 PyMuPDF 1.28.0 渲染页面时发生原生堆损坏，导致整个后端退出，随后桌面显示 `WinError 10061`。读取和写出 PDF 前会检查版本，不匹配时返回 `PDF_DEPENDENCY_INCOMPATIBLE`；请在后端使用的 Python 环境执行 `python -m pip install --no-deps "pymupdf==1.26.7"` 并重启后端。普通文档读取不受 PDF 版本检查影响。

前端使用独立环境和独立终端：

```powershell
python -m pip install -r requirements-frontend.txt
python -m Frontend --backend-url http://127.0.0.1:3389
# 等价入口：python AiNiee.py --backend-url http://127.0.0.1:3389
```

源码部署时，后端需要 `Backend` 目录及其依赖；前端需要 `Frontend`、`AiNiee.py` 及前端依赖。前端默认连接 `http://127.0.0.1:3389`，也可以设置 `AINIEE_BACKEND_URL`。前端不导入后端代码；本机自动启动通过独立进程完成，远程部署仅连接已有服务。

发布包同时携带前端和后端可执行程序及各自运行环境，无需安装 Python。Windows 后端位于 `backend/AiNieeBackend.exe`；macOS 后端位于应用包的 `Contents/Helpers/AiNieeBackend.app/Contents/MacOS/AiNieeBackend`。macOS 后端使用标准后台应用包，将运行库与数据资源分开放置以满足签名要求。桌面优先连接已有服务，必要时自动启动随包后端。可用 `AINIEE_BACKEND_EXECUTABLE` 指定其他后端程序，或设置 `AINIEE_BACKEND_PYTHON`（Python 解释器）与 `AINIEE_BACKEND_DIR`（包含 `Backend` 包的目录）使用源码后端。自动启动时，`AINIEE_APP_ROOT` 将后端的便携数据位置设为桌面发布目录。

用户确认退出界面后，通过 `POST /api/shutdown` 通知后端停止任务、保存缓存并退出。取消退出不会关闭任何一端；关闭请求失败会提示错误并保留窗口。仅断线或客户端异常退出不会关闭后端，重连时重新读取项目和状态。

原单进程模式、临时 HTTP 监听服务及其完成回调已经删除。旧的 `/api/translate`、`/api/stop` 不再提供；历史配置中的监听开关、监听地址和回调 URL 会由配置存储自动清理。

一个后端拥有一个当前文档项目、独立媒体工作区，以及 `document`、`image`、`audio` 三个固定队列，每个队列一个执行线程。使用单服务进程、一个 Uvicorn worker 和一个活动桌面客户端，不能通过增加 Uvicorn workers 扩容；任务期间不要自动重载服务。请通过终端正常停止后端，让任务取消和缓存保存完成。

新接口直接处理请求携带的模型，不切换桌面当前项目，并与桌面共用对应类型的队列。已有同类任务时新任务排队，不因忙碌直接返回 409。`/api/v2` 默认同步等待排队与执行完成，保持原结果结构；发送 `Prefer: respond-async` 则返回 `202 {"job": ...}` 和指向任务查询的 `Location`。任务结果持久保存，断线不取消任务，也不应自动重发收费流程。配置、只读查询与取消请求不等待业务队列。

## 目录职责

```text
Backend/
  __main__.py        服务入口
  api/               FastAPI 路由、请求模型、WebSocket 分发
  application/       任务编排、编辑规则接口、运行状态、校对检查
  domain/            项目模型、配置规则、提示词、文本处理
  infrastructure/    配置存储、项目缓存、文件格式读写、模型接口、分词器
  core/              序列化、路径、日志和配置访问
  resources/         默认配置、模型、提示词、正则、接口预设
```

新增文件格式在 `infrastructure/files/readers`、`infrastructure/files/writers` 实现并登记延迟加载注册表。前端结构见 [Frontend 说明](../Frontend/README.md)。桌面可执行程序只收集前端模块与资源，明确排除 `Backend` 包；`Tools/pyinstall_backend.py` 独立打包后端模块、模型和依赖，再将两个程序放入同一个发布包。

BabelDOC 的 `skimage` 导入兼容模块位于 `infrastructure/compat/skimage`，由 PDF 访问器在缺少正式 `scikit-image` 时注册，不需要根目录的同名文件夹。当前 PDF 流程关闭扫描件检测，兼容模块仅满足导入需求，不提供图像相似度计算；已安装的正式库保持优先使用。

`hyperscan` 的导入占位模块位于 `infrastructure/compat/hyperscan.py`，同样只在缺少正式依赖时注册。AiNiee 自行管理术语表，不使用 BabelDOC 的原生 Hyperscan 术语匹配功能；后端独立部署无需再携带根目录的 `hyperscan.py`。

## 配置与文件

- `infrastructure/config/store.py` 负责配置读取、迁移、默认值初始化和原子保存。默认值在 `resources/defaults.json`；接口预设和提示词模板通过 API 提供给界面。
- 源码与便携模式使用 `Data/config.json`，系统安装模式使用平台用户目录。旧版 `Resource/config.json` 会迁移到新位置，已有新配置不会被覆盖。
- `AINIEE_USER_DATA_DIR`、`AINIEE_CACHE_DIR`、`AINIEE_BACKEND_RESOURCE_DIR` 分别覆盖后端数据、缓存、只读资源目录。后端日志位于默认日志目录的 `backend` 子目录，可通过 `AINIEE_BACKEND_LOG_DIR` 覆盖。
- Job 元信息、进度和结果保存在 `cache_root()/tasks.sqlite3`，缓存根目录可由 `AINIEE_CACHE_DIR` 覆盖。重启时未完成任务标为 `interrupted`，不会自动重放请求；恢复业务应使用已保存项目或阶段结果。
- 配置在提交任务时生成独立快照，修改配置影响之后提交的任务。代理设置立即落盘，但直到三个队列都无运行和排队任务才应用并重建客户端；`GET /api/status` 的 `network_settings_pending` 表示代理变更仍待生效。
- 项目输入、输出和配置导入导出的路径属于后端机器。文件选择器用于本机或路径一致的共享目录；未提供跨机器项目文件上传下载。词表文件由前端选择、通过 API 校验后提交配置。
- 导入配置合并已有设置及显式提供的词表，导出生成 `ainiee_profile.json`。无效结构被拒绝。表格更新使用配置版本校验，冲突返回 409。
- 后端先保存生成结果，再通知前端。断线不会丢失已保存结果；断线期间的日志可查后端日志文件。

## 鉴权

默认监听本机。监听其他网卡时必须设置访问令牌，前端使用相同令牌：

```powershell
$env:AINIEE_API_TOKEN = "替换成随机令牌"
python -m Backend --host 0.0.0.0 --port 3389
```

HTTP 和 WebSocket 均使用 `Authorization: Bearer ...`。跨网络部署时通过支持 WebSocket 的 HTTPS 反向代理提供 TLS。该服务面向个人可信环境，不提供多用户文件权限隔离。

MCP 的每个 HTTP 请求也使用相同的 Bearer 令牌。远程 MCP 地址需额外通过 `AINIEE_MCP_ALLOWED_HOSTS` 和 `AINIEE_MCP_ALLOWED_ORIGINS` 显式允许；默认只允许本机，配置方法见 [MCP 鉴权与部署](docs/mcp.md#连接与鉴权)。

## API

运行后打开 `http://127.0.0.1:3389/docs` 查看 OpenAPI 请求结构。

| 接口 | 用途 |
| --- | --- |
| `/mcp`（Streamable HTTP） | MCP 工具发现、翻译任务提交、查询与取消 |
| `GET /health` | 服务与协议版本 |
| `GET /api/status` | 文档兼容状态、全局 `any_busy/queues` 和代理待应用标志 |
| `GET /api/jobs?lane=document&limit=50` | 查询任务列表，列表省略完整结果 |
| `GET /api/jobs/{job_id}` | 查询任务状态、进度、结果及错误 |
| `POST /api/jobs/{job_id}/cancel` | 取消指定排队或运行中的任务 |
| `GET /api/queues` | 三类队列的运行任务与待执行任务 |
| `GET /api/config` / `PATCH /api/config` | 读取配置、带版本校验的更新 |
| `GET /api/config/info` | 后端配置路径 |
| `GET /api/config/defaults/{section}` | 页面默认值 |
| `GET /api/config/platform-presets` | 接口预设 |
| `GET /api/config/prompt-presets/{kind}` | translation / polishing / extraction 模板 |
| `POST /api/config/import` / `POST /api/config/export` | 后端执行配置导入导出 |
| `GET /api/project` / `GET /api/project/types` | 项目快照和支持格式 |
| `POST /api/project/load` | 加载并保存项目 |
| `GET /api/project/preflight/{role}` | translate / polish 接口绑定预检查 |
| `POST /api/cache/{method}` | 白名单内的缓存编辑、历史管理、保存和 search_items 搜索 |
| `POST /api/check/{kind}` | language / rule / terminology 校对 |
| `POST /api/editor/{operation}` | 编辑规则、表格/角色/正则校验、模型选项、请求头与路径处理 |
| `POST /api/tasks/translation` | 当前项目翻译，`continue_status` 控制继续任务统计 |
| `POST /api/tasks/analysis` | 当前项目分析 |
| `POST /api/tasks/table/translate` / `polish` / `proofread` | 表格条目翻译、润色、校对 |
| `POST /api/tasks/glossary/translate` | 指定术语表的未翻译条目翻译 |
| `POST /api/tasks/api-test` | 测试传入的模型接口配置 |
| `POST /api/tasks/stop` | 停止文档队列中桌面发起的当前或首个排队任务 |
| `POST /api/project/export` / `save` | 当前项目正式文件导出、缓存保存 |
| `POST /api/shutdown` | 确认退出后关闭服务，需通过后端正式入口启动（源码或随包程序） |
| `POST /api/models` / `POST /api/names` | 模型列表和目录人名提取 |
| `WS /ws/events` | 实时状态、日志、任务结果 |

编辑操作只接受 `application/editor.py` 中明确列出的操作，不提供任意 Python 方法调用。输入为 `args` 和 `kwargs`，输出为 `result`，行规范化附带批量校验结果以供前端着色。

工作区操作使用明确路由与类型化请求，不再发送 `event`、`update_event`、`done_event`。向 `POST /api/tasks/translation` 发送：

```json
{"continue_status": false}
```

这些工作区操作使用后端当前文档项目，长任务入队后返回 202，响应保留原状态字段并增加 `job_id`、`job`；结果可通过任务查询、WebSocket 通知和项目快照获取。保存接口入队并同步等到完成后返回 200，停止接口直接返回。文档页面使用的 `status.busy`、`work_status_code`、`operation` 只表示文档队列；`any_busy` 与 `queues` 表示全局状态。图片与音频页面按自己的 job ID 查询进度，不占用文档页面的忙碌状态。

表格条目润色传入 `file_path`、`items_to_polish`（包含 `text_index`、`source_text`、`translation_text`）和可选 `view`。多文件一次提交 `translate_jobs`、`polish_jobs` 或 `proofread_jobs`，每项包含 `file_path` 和对应的条目数组，内部逐文件处理；不能与单文件参数混用。`view` 只用于把通知交给 `basic`、`search`、`language_check`、`rule_check`、`terminology_check` 中的对应界面，不参与业务保存。

取消排队任务会直接标为 `cancelled`，不开始执行；取消运行任务先标为 `cancelling` 并设置协作取消信号，在途请求和保存收尾后才释放该类型的队列。读取、检查和部分写出不会中途打断，仍需等待实际函数返回。旧工作区停止接口只控制桌面发起的文档任务；指定任意 job 使用通用取消接口，媒体专用停止接口仍按 operation ID 定位。正常退出等待实际执行结束后关闭缓存与模型客户端。

WebSocket 消息类型包括 `connected`、`status`、`job`、`notification`、`log`、`settled`、`error`、`resync`。`job` 推送任务元信息和进度，完整结果通过 `GET /api/jobs/{job_id}` 获取。通知使用 `name` 与 `data`，例如 `translation.progress`、`analysis.completed`、`table.updated`、`glossary.completed`、`project.export.completed`；`settled` 和 `error` 使用具名 `operation`。导出完成通知保留完整的 `status`、`files` 和 `report`，包括部分成功时的逐文件错误；桌面显示结果提示，并将完整报告写入运行日志。状态心跳间隔两秒，`last_operation` 给出最近一次工作区操作的名称和结果状态；慢客户端队列满时要求重连获取快照。通知失败或没有连接者不会阻断结果保存，前端收到通知后仅在本地分发 UI 信号。

## 统一中间模型接口

| 接口 | 输入与结果 |
| --- | --- |
| `POST /api/v2/read/document` | `path`、可选 `options.format/exclude_rule/pages` → 文档模型与读取报告；自动识别包含 PDF 的单文件或混合目录 |
| `POST /api/v2/read/image` | 读取本地静态图片或目录，记录尺寸、方向和源文件指纹 |
| `POST /api/v2/ocr` | 独立在线 OCR，返回原文、像素坐标和阅读顺序 |
| `POST /api/v2/write/image` | 擦字、回填译文，保存图片、遮罩及中间模型 |
| `POST /api/v2/image/translate` | 读取 → OCR → 现有批量翻译 → 图片导出的串行流程 |
| `POST /api/v2/image/generate-translation` | 中间模型 → 独立生图接口 → 含译图产物的中间模型 |
| `POST /api/v2/write/generated-image` | 直接导出生图产物及中间模型，无需 OCR 或字体排版 |
| `POST /api/v2/image/generate-pipeline` | 读取 → 生图翻译 → 图片与模型导出的串行流程 |
| `POST /api/v2/image/operations/{operation_id}/stop` | 协作停止匹配的生图流程，保存在途页结果 |
| `POST /api/v2/read/audio` | `path`、可选 `options.exclude_rule` → 音频引用、媒体元信息及空条目的中间模型 |
| `POST /api/v2/transcribe` | `model`、可选 `config` → 在线识别后带原文及时间轴的中间模型 |
| `POST /api/v2/translate` | `model`、`config` → 更新后的模型、用量及逐条失败报告 |
| `POST /api/v2/write` | `model`、可选 `options` → 实际生成文件清单与写出报告 |
| `POST /api/v2/write/subtitles` | `model`、`options.output_dir/format/mode` → SRT、VTT、LRC 或 ASS 字幕 |
| `POST /api/v2/audio/translate` | `path/read_options/transcription/translation/output` → 串行完成音频翻译，返回模型、字幕文件及分阶段报告 |

文档读取默认 `format: "AutoType"`，按文件类型选择读取器，PDF 使用 BabelDOC。显式指定 `format: "BabeldocPdf"` 时仅读取 PDF，其他指定格式仍只读取匹配文件。可选 `pages`（例如 `"1-3,5"`）仅用于 `AutoType` 或 `BabeldocPdf`：混合目录中每个 PDF 使用同一页范围，其他文档不受影响；省略时读取全部页。PDF 的源文件指纹、解析参数及原文顺序摘要继续保存在中间模型中，供后续翻译和写出使用。扫描件仍不支持，混合目录中的单文件失败会记录在报告中并保留其他文件的读取结果。

读取和翻译响应包含 `status`、`model`、`report`；写出响应包含 `status`、`files`、`report`。执行结果的 `status` 为 `success`、`partial`、`failed`，取消的翻译返回 `cancelled`。执行前错误使用非 2xx HTTP 响应，并提供 `error.code` 和 `error.message`；HTTP 200 时仍需检查业务状态及报告。

模型的 `schema_version` 为 2，沿用项目 → 文件 → 条目结构，增加 `file_id`、`item_id`、`source_ref`、`locator`、`media_metadata` 和 `translation_context`。格式专用 `extra` 原样保留，图片区域和音频时间轴已有类型定义。原文件不嵌入 JSON；源文件引用包含路径、SHA256 和验证标志，依赖原文件的格式在写出前进行校验。

旧缓存加载时先保存 `.pre-v2.bak`，再原子迁移，稳定 ID 随缓存保存。旧 Office 类型历史内容保留，写出返回 `FORMAT_REMOVED`；需要重新通过 BabelDOC 读取原 PDF，或先把 `.doc` 转为 `.docx`。

翻译的 `provider_id` 是已有后端接口配置的键，不是模型名称；省略时使用当前翻译接口绑定。本次 `config` 可覆盖语言、线程数、分块、重试、提示词和术语规则，不修改全局配置。默认跳过已有有效译文；切换目标语言必须显式传 `retranslate: true`，重译在副本中清空旧译文，失败片段不会残留旧目标语言。

分块模式只需传 `lines_limit_switch` 或 `tokens_limit_switch` 中的一个；同时传入时必须恰好启用一个。术语、禁翻、译前和译后规则支持多表 `*_tables` 或旧式 `*_switch` / `*_data`，同一类别不能混用两种写法。临时 `*_data` 替换本次该类别的规则，省略开关时沿用当前启用状态；仅传开关则统一切换该类别各表的启用状态，均不回写已保存配置。

写出的 `options` 支持 `output_dir`、`mode`（`translated`、`bilingual`、`both`）、文件名后缀、双语顺序、编码与 `overwrite`。默认输出到用户数据目录的 `Outputs/<project_id>/`，默认不覆盖已有文件，也不会覆盖原文件。未翻译条目按原文写出；写出不再调用翻译模型。

以下例子在后端已配置可用模型接口时运行；路径属于后端机器，访问令牌与后端一致：

```python
import os
import httpx

headers = {}
if token := os.environ.get("AINIEE_API_TOKEN"):
    headers["Authorization"] = f"Bearer {token}"

def call(client, operation, payload):
    response = client.post(f"/api/v2/{operation}", json=payload)
    response.raise_for_status()
    result = response.json()
    if result["status"] != "success":
        raise RuntimeError(result["report"])
    return result

with httpx.Client(base_url="http://127.0.0.1:3389", headers=headers,
                  timeout=httpx.Timeout(3600, connect=10)) as client:
    model = call(client, "read/document", {
        "path": "D:/inputs/sample.txt", "options": {"format": "Txt"}
    })["model"]
    model = call(client, "translate", {
        "model": model,
        "config": {"source_language": "auto", "target_language": "chinese_simplified",
                   "user_thread_counts": 4}
    })["model"]
    result = call(client, "write", {
        "model": model, "options": {"output_dir": "D:/outputs", "mode": "translated"}
    })
    print(result["files"])
```

## 验证

后端队列、配置隔离、缓存并发和统一文档/PDF 入口的回归测试（使用临时目录与模拟模型服务，不发起收费模型请求）：

```powershell
python -X utf8 -m pytest Tests/test_job_scheduler.py Tests/test_runtime_queues.py Tests/test_queue_api.py Tests/test_task_resources.py Tests/test_cache_concurrency.py Tests/test_document_read.py -q
```

MCP 的服务、鉴权与真实 HTTP 协议测试：

```powershell
python -X utf8 -m pytest Tests/test_mcp_service.py Tests/test_mcp_security.py Tests/test_mcp_http.py -q
```

前端测试单独运行，不与后端原生依赖放在同一 Python 进程。Qt 测试设置 `QT_QPA_PLATFORM=offscreen`，覆盖连接错误提示、媒体队列进度与取消请求独立发送：

```powershell
python -X utf8 -m pytest Tests/test_frontend_queue_clients.py Tests/test_startup_errors.py Tests/test_media_queue_progress.py -q
```

文档入口测试模拟 PDF 解析和语言检测，不验证真实模型效果。真实 PDF 读取仍需要固定版本的 PyMuPDF，以及 BabelDOC 所需模型和字体资产；不要将 QtMultimedia 与后端 ONNX Runtime/PDF 原生库放入同一个测试进程。
