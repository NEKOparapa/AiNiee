# FastAPI 后端

后端独立管理配置、项目、缓存、翻译、润色、提取、校对和导出。PyQt 桌面仅通过 HTTP 与 WebSocket 访问后端，两端不导入对方的 Python 模块。

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

发布包同时携带前端和后端可执行程序及各自运行环境，无需安装 Python。Windows 后端位于 `backend/AiNieeBackend.exe`；macOS 后端位于应用包的 `Contents/Helpers/AiNieeBackend/AiNieeBackend`。桌面优先连接已有服务，必要时自动启动随包后端。可用 `AINIEE_BACKEND_EXECUTABLE` 指定其他后端程序，或设置 `AINIEE_BACKEND_PYTHON`（Python 解释器）与 `AINIEE_BACKEND_DIR`（包含 `Backend` 包的目录）使用源码后端。自动启动时，`AINIEE_APP_ROOT` 将后端的便携数据位置设为桌面发布目录。

用户确认退出界面后，通过 `POST /api/shutdown` 通知后端停止任务、保存缓存并退出。取消退出不会关闭任何一端；关闭请求失败会提示错误并保留窗口。仅断线或客户端异常退出不会关闭后端，重连时重新读取项目和状态。

原单进程模式、临时 HTTP 监听服务及其完成回调已经删除。旧的 `/api/translate`、`/api/stop` 不再提供；历史配置中的监听开关、监听地址和回调 URL 会由配置存储自动清理。

一个后端拥有一个当前项目和一项后台任务。使用一个 worker 和一个活动桌面客户端，任务期间不要自动重载服务。请通过终端正常停止后端，让任务取消和缓存保存完成。

## 目录职责

```text
Backend/
  __main__.py        服务入口
  api/               FastAPI 路由、请求模型、WebSocket 分发
  application/       任务编排、编辑规则接口、运行状态、校对检查
  domain/            项目模型、配置规则、提示词、文本处理
  infrastructure/    配置存储、项目缓存、文件格式读写、模型接口、分词器
  core/              后端事件、路径、日志和配置访问
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
| `POST /api/commands` | 开始、停止、提取、表格任务、导出和 API 测试 |
| `POST /api/shutdown` | 确认退出后关闭服务，需通过后端正式入口启动（源码或随包程序） |
| `POST /api/models` / `POST /api/names` | 模型列表和目录人名提取 |
| `WS /ws/events` | 实时状态、日志、任务结果 |

编辑操作只接受 `application/editor.py` 中明确列出的操作，不提供任意 Python 方法调用。输入为 `args` 和 `kwargs`，输出为 `result`，行规范化附带批量校验结果以供前端着色。

任务指令采用版本化 JSON 协议，编号见 `core/base.py` 和 `core/protocol.py`。翻译示例：

```json
{"event": 210, "data": {"current_mode": 1000, "continue_status": false}}
```

WebSocket 消息类型为 `connected`、`status`、`event`、`log`、`settled`、`resync`。状态心跳间隔两秒；慢客户端队列满时断开并要求重新获取项目。前端拥有独立的协议常量和显示数据结构，测试检查协议兼容性，不通过共享 Python 类交换对象。

## 验证

```powershell
python -m pytest tests -q
```

测试使用临时目录和模拟模型回复，覆盖配置、任务、WebSocket、实际 TXT 读写流程、独立客户端快照、编辑 API、旧接口移除、前端独立导入和打包边界。
