# FastAPI 后端

后端独立管理配置、项目、缓存、翻译、表格条目润色、提取、校对和导出。PyQt 桌面仅通过 HTTP 与 WebSocket 访问后端，两端不导入对方的 Python 模块。

后端提供统一中间模型及六个 `/api/v2` 接口，同一时刻执行一个顶层操作，单次翻译内部保留多线程批量处理。PDF 仅使用 BabelDOC；Office 自动化转换链及旧 `.doc` 入口已移除，DOCX、PPTX、XLSX 的原生读写保留。图片和音频读取接口暂返回 501。设计与迁移范围见 [后端改造计划](docs/backend_refactoring_plan.md)。

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

一个后端拥有一个当前项目和一项后台任务。使用一个 worker 和一个活动桌面客户端，任务期间不要自动重载服务。请通过终端正常停止后端，让任务取消和缓存保存完成。

新接口直接处理请求携带的模型，不切换桌面当前项目。它们与桌面任务共用顶层互斥，忙碌时返回 `409 BACKEND_BUSY`；模型内部仍按线程数和 RPM 配置并行翻译批次。新接口同步等待完成，不创建 Job 或队列。连接中断不会立即终止工作线程，调用方应设置足够的超时，不自动重发整次翻译请求。

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

## API

运行后打开 `http://127.0.0.1:3389/docs` 查看 OpenAPI 请求结构。

| 接口 | 用途 |
| --- | --- |
| `GET /health` | 服务与协议版本 |
| `GET /api/status` | 任务状态、进度和错误 |
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
| `POST /api/tasks/stop` | 协作停止当前工作区任务，等待在途请求收尾 |
| `POST /api/project/export` / `save` | 当前项目正式文件导出、缓存保存 |
| `POST /api/shutdown` | 确认退出后关闭服务，需通过后端正式入口启动（源码或随包程序） |
| `POST /api/models` / `POST /api/names` | 模型列表和目录人名提取 |
| `WS /ws/events` | 实时状态、日志、任务结果 |

编辑操作只接受 `application/editor.py` 中明确列出的操作，不提供任意 Python 方法调用。输入为 `args` 和 `kwargs`，输出为 `result`，行规范化附带批量校验结果以供前端着色。

工作区操作使用明确路由与类型化请求，不再发送 `event`、`update_event`、`done_event`。向 `POST /api/tasks/translation` 发送：

```json
{"continue_status": false}
```

这些工作区操作使用后端当前项目，长任务返回 202 接受确认，结果通过 WebSocket 通知和项目快照获取；保存、停止接口返回 200。运行时仍只接纳一个顶层操作，不排队，不建立持久化 Job。外部 Agent 组合读写翻译时使用下文同步 `/api/v2` 接口，可直接取得完整返回模型。

表格条目润色传入 `file_path`、`items_to_polish`（包含 `text_index`、`source_text`、`translation_text`）和可选 `view`。多文件一次提交 `translate_jobs`、`polish_jobs` 或 `proofread_jobs`，每项包含 `file_path` 和对应的条目数组，内部逐文件处理；不能与单文件参数混用。`view` 只用于把通知交给 `basic`、`search`、`language_check`、`rule_check`、`terminology_check` 中的对应界面，不参与业务保存。

停止仅设置当前工作区操作的 `ExecutionContext` 取消信号；在途请求完成并保存已产生的结果后才释放准入。文件读取、检查、正式导出暂不支持取消；模型接口发起的操作不能被工作区停止接口中断。正常退出等待实际执行结束后关闭缓存与模型客户端。

WebSocket 消息类型为 `connected`、`status`、`notification`、`log`、`settled`、`error`、`resync`。通知使用 `name` 与 `data`，例如 `translation.progress`、`analysis.completed`、`table.updated`、`glossary.completed`、`project.export.completed`；`settled` 和 `error` 使用具名 `operation`。导出完成通知保留完整的 `status`、`files` 和 `report`，包括部分成功时的逐文件错误；桌面显示结果提示，并将完整报告写入运行日志。状态心跳间隔两秒，`last_operation` 给出最近一次工作区操作的名称和结果状态；慢客户端队列满时要求重连获取快照。通知失败或没有连接者不会阻断结果保存，前端收到通知后仅在本地分发 UI 信号。

## 统一中间模型接口

| 接口 | 输入与结果 |
| --- | --- |
| `POST /api/v2/read/document` | `path`、`options.format/exclude_rule` → 文档模型与读取报告；PDF 使用专用接口 |
| `POST /api/v2/read/pdf` | `path`、可选 `options.pages/exclude_rule` → BabelDOC 模型与报告 |
| `POST /api/v2/read/image` | 保留 `path` 与空 `options`，返回 `501 IMAGE_READ_NOT_IMPLEMENTED` |
| `POST /api/v2/read/audio` | 保留 `path` 与空 `options`，返回 `501 AUDIO_READ_NOT_IMPLEMENTED` |
| `POST /api/v2/translate` | `model`、`config` → 更新后的模型、用量及逐条失败报告 |
| `POST /api/v2/write` | `model`、可选 `options` → 实际生成文件清单与写出报告 |

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

```powershell
python -m pytest tests -q
```

测试使用临时目录和模拟模型回复，覆盖模型与缓存迁移、多线程翻译、取消与重试、显式工作区接口、持久化与通知顺序、服务独立调用、桌面请求和状态恢复、TXT/字幕/DOCX/EPUB/PPTX 等格式读写及 PDF 映射。真实 BabelDOC PDF 测试需启用相应环境变量，并已具备 BabelDOC 所需的模型和字体资产：

```powershell
$env:AINIEE_TEST_REAL_PDF = "1"
python -X utf8 -m pytest tests -q
```
