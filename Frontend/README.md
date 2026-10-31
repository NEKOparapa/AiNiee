# PyQt 桌面前端

保留现有界面和操作流程，通过 HTTP 提交配置与任务，通过 WebSocket 接收进度、日志和结果。用户配置、内置提示词和业务文件读写由后端负责。

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
    prompts/                   翻译、提取、润色提示词编辑
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

Python 文件和包使用小写下划线，类名保持原有命名。新增页面放入对应功能目录，在 `app/window.py` 或所属工作区页面注册；可复用控件放入 `components`，网络访问放入 `services`。

前端不导入 `Backend`，可以单独复制 `Frontend`、`AiNiee.py` 和 `requirements-frontend.txt` 部署。`core/config.py` 只访问远端配置；`models` 将 JSON 转为界面数据；`services/project_state.py` 保持显示对象身份并将编辑、搜索和校对转发到后端。业务规则只在后端执行，断线不会回退到本地配置或业务实现。

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
