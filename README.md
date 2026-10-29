<div align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png" width=60%>
  </a>
</div>


<div align="center">
  <a href="README_EN.md">English</a> | 简体中文
</div>

---


## 软件介绍🧾 

  
<div align="center">
<strong>AiNiee</strong> 是一款专注于 AI 翻译的工具，<br>一键自动翻译游戏、书籍、字幕、文档等复杂长文本内容。
</div>


* **格式全能，覆盖广泛**
    * 🎮 **游戏翻译**：深度支持 Mtool, Renpy, Translator++, ParaTranz, VNText, SExtractor 等游戏文本导出工具。
    * 📚 **多样支持**：轻松处理 I18Next/.trans/Po/CSV 数据、Epub/TXT 电子书、Srt/Ass/Vtt/Lrc 字幕、Word/PDF/MD/PPT 文档等。

* **智能高效，省时省心**
    * 🚀 **完整工作流**：打开本机项目，配置接口与提示词，翻译后检查、校对并导出。
    * ⏱️ **可恢复任务**：查看实时进度和日志，停止后继续处理剩余条目。

* **长文优化，质量出众**
    * 🎯 **突破局限**：采用轻盈翻译格式、思维链翻译、AI术语表、上下文关联等技术，确保长文本翻译的连贯性与准确性。
    * 💎 **质量追求**：支持 基础提示、角色介绍、背景设定、翻译风格 等提示词调整，拥有 一键AI润色、一键提取术语 等功能，满足对翻译质量有更高要求的用户。

---

## 项目推荐 ✨

* [**ReaDreamAI**](https://github.com/NEKOparapa/ReaDreamAI)（作者：NEKOparapa） - 阅你所想，绘你所梦，从一个想法到一本完整的精彩小说。ReaDreamAI为你包办写作、插图与视频。
* [**Wintermute**](https://github.com/NEKOparapa/Wintermute)（作者：NEKOparapa） - 一个长期陪伴你的个人 AI 执事。它会通过对话、录音、视频和更多关于你的数据流，逐渐理解你的语言习惯、长期偏好、正在推进的计划，以及你不希望被越过的边界。
* [**AiNiee-Next**](https://github.com/ShadowLoveElysia/AiNiee-Next)（作者：ShadowLoveElysia） - 针对 AiNiee 核心逻辑进行工程化重构的命令行版本，引入 uv 与运行时稳定性优化，适合长时间挂机、服务器部署及自动化工作流。
* [**ainiee-translate-skill**](https://github.com/xuanji86/ainiee-translate-skill)（作者：xuanji86） - 独立、Agent 原生的小说翻译系统（任意源 → 目标语言，不限中译）


---

## 本分支：本地 Web 工作台

后端是独立的 Python 3.12 / FastAPI 进程，前端是 `frontend/` 中的 React 应用，通过 REST 和 WebSocket 通信。浏览器提供接口管理、项目概览、条目校对、提示词、公共表格、质量检查、分析、导出和任务日志。界面默认中文，也可切换英文、浅色或深色主题。

当前一次运行一个翻译、润色或分析任务。右侧智能体面板为占位，可用 `Ctrl+L` 展开或收起。音频、视频、图片翻译不在本分支的交付范围内。Windows 便携包由 PyInstaller 打包后端并托管已构建的前端，双击后在默认浏览器中操作。[历史发行版](https://github.com/NEKOparapa/AiNiee/releases)的界面和启动方式可能与本分支不同。

### 安装依赖

准备 Python **3.12（64 位）**、Node.js **24** 和 npm。下列命令从包含 `AiNiee.py`、`Server/`、`frontend/` 的仓库根目录执行；Windows 示例使用 PowerShell，无需激活虚拟环境。

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install --no-deps -r requirements_no_deps.txt
npm --prefix frontend ci
```

`requirements_no_deps.txt` 中的包按仓库的依赖拆分方式安装；先安装 `requirements.txt`，再执行 `--no-deps` 步骤。不要将第二步替换为普通的依赖解析安装。前端使用已提交的 `package-lock.json`，因此用 `npm ci` 安装。

macOS / Linux 可用 `python3.12 -m venv .venv` 创建环境，并将上述 Python 命令中的 `.venv\Scripts\python.exe` 替换为 `.venv/bin/python`。系统和架构仍需满足各 Python 依赖的安装要求。

### 启动开发环境

终端一运行前端：

```powershell
npm --prefix frontend run dev
```

终端二运行后端：

```powershell
.venv\Scripts\python.exe AiNiee.py --dev
```

前端地址为 `http://127.0.0.1:5173`。后端默认地址为 `http://127.0.0.1:8000`。`--dev` 在后端就绪后打开浏览器，将后端地址和访问令牌通过 URL fragment 交给前端；**它不会启动前端进程**。两端均需保持运行。

后端就绪后，启动终端会打印：

```text
TOKEN <随机访问令牌>
READY <实际监听端口>
```

也可手动打开前端，点击右上角连接设置，填写后端地址和 `TOKEN`。访问令牌用于连接本机服务，与翻译平台的 API Key 不同。连接信息保存在当前浏览器会话中。

| 参数 | 行为 |
| --- | --- |
| `--host 127.0.0.1` | 唯一允许的监听地址，也是默认值。 |
| `--port 8000` | 指定后端端口；源码默认 `8000`，打包版默认 `0` 自动选择空闲端口。控制台模式以 `READY` 为准。 |
| `--token <令牌>` | 使用指定令牌；省略时生成随机令牌。指定令牌时不再打印 `TOKEN` 行。 |
| `--dev` | 就绪后打开固定的前端地址 `http://127.0.0.1:5173`。 |
| `--web` | 托管 `frontend/dist/`，就绪后打开后端同源的工作台；打包版默认启用。与 `--dev` 互斥。 |
| `--no-browser` | 不自动打开浏览器，也不显示原生启动提示，适用于自动化验收。 |

端口已被占用时，可以为后端选择其他端口；前端保持 `5173`。停止后端时使用终端的 `Ctrl+C`，进程会等待正在进行的任务收尾和缓存保存。

### 构建与本地预览

```powershell
npm --prefix frontend run build
npm --prefix frontend run preview
```

构建结果写入 `frontend/dist/`；预览服务同样使用 `http://127.0.0.1:5173`，需要先停止占用此端口的开发服务。另开终端运行后端，再连接前端即可。

也可由后端直接托管构建结果，无需另外运行 Vite：

```powershell
npm --prefix frontend run build
.venv\Scripts\python.exe AiNiee.py --web --port 0
```

就绪后浏览器自动打开随机本机端口，连接令牌通过 fragment 传入，前端读取后立即从地址栏移除。直接刷新设置等深层页面也可正常加载。

### Windows 便携包

在 Windows x64 上完成上面的 Python 3.12、Node.js 24 依赖安装后，从完整 Git 检出目录运行：

```powershell
.venv\Scripts\python.exe Tools/pyinstall.py
```

脚本自动构建前端，再生成隐藏控制台的 PyInstaller 文件夹包和 ZIP。输出位于 `dist/windows-<UTC时间>-<随机ID>/`：其中 `AiNiee/AiNiee.exe` 可直接运行，`AiNiee-<版本>-windows-x64.zip` 用于分发，旁边的 `.sha256` 用于核对完整性。终端会打印实际 `EXECUTABLE`、`PACKAGE` 和 `SHA256`。每次构建使用新目录，不覆盖已有包；`--console` 可生成可见的诊断控制台，`--skip-frontend-build` 可复用已经构建且会再次校验的 `frontend/dist/`。

使用时完整解压 ZIP，保留 `AiNiee.exe`、`_internal/` 和 `portable.txt`，然后双击 `AiNiee.exe`。无需安装 Python、Node.js，也无需另开前端服务。程序只监听 `127.0.0.1`，默认随机端口与令牌，就绪后打开默认浏览器。重复启动会提示已有实例运行。

关闭标签页后，后台任务仍继续运行。需要结束程序时，在「关于 / 更新」点击「退出应用」并确认；后端会停止任务，等待正在执行的请求结束并保存缓存，再退出。页面显示「退出请求已接受」只表示已开始关闭流程，不代表进程已经结束。源码模式也可以使用此按钮或终端的 `Ctrl+C`。

包内仅带应用资源和空默认配置，不复制构建者的用户配置、缓存或日志。`build-info.json` 记录构建版本、依赖和资源校验信息。首次启动后，可写的便携目录会在 EXE 旁创建 `Resource/config.json`、`ProjectCache/` 和 `Logs/`。升级前先退出程序，保留旧目录的配置和缓存，将它们复制到新包根目录对应位置；不要放进 `_internal/`，也不要用默认配置覆盖原配置。目录不可写时沿用现有规则回落到用户数据目录。

### 人工操作流程

1. 在「接口管理」添加平台、测试连接，并为翻译、润色和分析绑定所用接口。
2. 在「首页」输入本机项目路径，或通过目录浏览器选择文件夹；按需选择项目类型并打开。浏览器拖放无法取得完整目录路径时，改用路径输入或目录浏览器，不会上传或复制源文件。
3. 配置任务、输出、提示词和公共表格，在底部任务栏开始翻译；可查看进度、打开日志、停止和继续任务。
4. 在「质量检查」运行规则、语言或术语检查，点击问题跳到「条目校对」并编辑。校对表支持搜索、正则筛选、多选和分页，滚动时只渲染可见行。
5. 在「导出」选择输出目录，导出译文和双语文件，也可手动保存缓存。「项目分析」支持整理角色、术语和禁翻结果，并将选中内容写入公共表格。

公共表格支持多子表、JSON/XLSX 导入导出；分析结果使用 JSON。提示词库可管理翻译、润色和两阶段分析的自定义提示。历史项目会保留缓存，可从首页继续；删除历史会删除该项目缓存，需要确认，当前打开的项目不可删除。

### 配置、缓存与升级

沿用现有 `config.json` 和 `CacheManager` 项目格式。源码目录可写时默认使用便携布局：

| 内容 | 默认位置 |
| --- | --- |
| 用户配置及接口设置 | `Resource/config.json` |
| 项目缓存及翻译进度 | `ProjectCache/<项目 ID>/` |
| 运行日志 | `Logs/` |

升级源码前保留配置和整个 `ProjectCache/`，使用相同的数据路径启动即可继续读取；不要用示例配置覆盖已有配置。输入、输出目录保留在配置中。启用自动输出目录时，译文写入输入目录旁的 `AiNieeOutput/`，润色写入 `AiNieePolishOutput/`。

可用 `AINIEE_USER_DATA_DIR` 指定配置目录（其中的 `config.json`），用 `AINIEE_PROJECT_CACHE_DIR` 指定项目缓存目录，用 `AINIEE_LOG_DIR` 指定日志目录。Windows 设置 `AINIEE_PORTABLE=0` 后默认使用 `%LOCALAPPDATA%/AiNiee/`；macOS 非便携模式的配置默认在 `~/Library/Application Support/AiNiee/`。改变数据路径时需同步迁移原配置和缓存。

可从仓库根目录查看本次环境解析到的实际路径：

```powershell
.venv\Scripts\python.exe -c "from ModuleFolders.Config.FilePathConfig import config_path, project_cache_root, user_log_dir; print(config_path()); print(project_cache_root()); print(user_log_dir())"
```

### 本机访问与接口契约

`GET /health` 无需令牌。启用 `--web` 或使用便携包时，构建目录内的前端静态资源也允许免令牌的 `GET/HEAD`，便于浏览器首次加载页面；此例外不开放用户配置、项目文件或 API。其他 HTTP 请求（包括 OpenAPI）使用 `Authorization: Bearer <token>`，WebSocket 使用 `/api/v1/ws?token=<token>`。白名单来源的 `OPTIONS` 预检免令牌，实际 API 请求仍鉴权。允许的浏览器来源是 `http://127.0.0.1:5173`、`http://localhost:5173` 和当前后端自身地址；不使用通配 CORS，也不支持远程监听。令牌不应随链接共享。

REST 入口为 `/api/v1/`。WebSocket 推送进度、日志和数据变化；断线后前端自动重连并重新查询状态，不重放已丢失事件。前端接口类型和 WebSocket 契约均来自后端 Pydantic / OpenAPI，修改接口后执行：

```powershell
.venv\Scripts\python.exe -m Server.export_openapi
npm --prefix frontend run generate:api
npm --prefix frontend run check:api
```

提交更新后的 `openapi.json` 和 `frontend/src/api/generated/schema.d.ts`，不要手改生成文件。

### 开发检查与测试

```powershell
.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run check:api
```

首次运行浏览器测试时，在 `frontend/` 安装 Playwright 的 Chromium：

```powershell
cd frontend
npx playwright install chromium
npm run build
npm run test:e2e
```

Playwright 会启动或复用 `5173` 上的本项目前端，并为测试启动使用临时数据目录的后端。默认使用仓库 `.venv` 中的 Python；可用 `AINIEE_TEST_PYTHON` 指定其他解释器路径。测试里的模型请求使用固定 mock，禁止访问真实模型接口；缓存、配置和输出均与用户数据隔离。浏览器失败截图和 trace 保存在 `frontend/test-results/`。

`hosted-workbench.spec.ts` 直接访问后端托管的 `frontend/dist/`，验证深层页面刷新、令牌交接、配置保存和确认退出。还可在 `frontend/` 中设置 `AINIEE_TEST_EXECUTABLE` 为本次构建的 `AiNiee.exe` 绝对路径，仅运行这一用例：

```powershell
# 将路径替换为本次构建终端打印的 EXECUTABLE。
$env:AINIEE_TEST_EXECUTABLE = 'D:\packages\AiNiee\AiNiee.exe'
npm run test:e2e -- hosted-workbench.spec.ts
Remove-Item Env:AINIEE_TEST_EXECUTABLE
```

可执行文件验收不启动 Vite，不借用源码资源目录，验证前端来自包内。此用例不调用模型接口，不能和模型 mock 模式混用；清除环境变量后再运行完整套件。

还可从仓库根目录运行完整的便携包验收，将 `--bundle` 替换为包含本次 `AiNiee.exe` 的文件夹：

```powershell
.venv\Scripts\python.exe Tools/smoke_package.py --bundle 'D:\packages\AiNiee' --report build/package-smoke.json
```

脚本把包复制到临时中文、空格路径，使用临时用户目录和本机固定 OpenAI mock，验证真实 EXE 的停止、重启恢复、检查、校对、导出和日志脱敏。无参数启动也会验证随机端口与浏览器交接；测试通过临时 `BROWSER` 命令捕获地址，不修改系统默认浏览器。结果写入 JSON，原始发布包不写入用户数据。

后端测试覆盖旧调用路径与 Application 调用路径的导出字节一致性，以及停止、保存、恢复和继续；浏览器测试覆盖翻译、检查、编辑、导出，以及表格、提示词、分析和设置流程。

浏览器测试还会创建真实的 50,000 条项目，检查分页、虚拟滚动、筛选和编辑后持久化。每次运行的读取耗时、交互耗时、滚动帧间隔和渲染行数写入 `frontend/test-results/` 下对应测试目录的 `large-project-performance.json`，供性能回归比较；这些指标取决于运行机器，不代表所有设备的速度保证。

GitHub Actions 使用 Windows、Python 3.12 和 Node.js 24，运行后端测试、前端单元测试与构建、生成类型检查以及 Playwright 流程，并上传测试诊断文件。CI 仅做检查和构建，不再发布旧桌面包。

### 当前限制

- 一次只运行一个任务；智能体面板仅占位。
- 旧本地模型的自动 `/slots` 探测没有超时，探测期间停止或退出需要等待该调用返回。
- 当前缓存未保存任务模式，重启后不会自动恢复润色模式；本次运行内可停止后继续润色。
- 平台未提供计费数据时，任务栏费用显示为 `—`。

---


<details>
<summary>
  
## 游戏翻译[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#游戏翻译)
</summary>


<details>
<summary> 

### 工具准备
</summary>

 * **`📖游戏文本提取工具`**

      |工具名|介绍|项目类型|
      |:----:|:-----:|:-----:|
      |[Mtool](https://afdian.com/p/d42dd1e234aa11eba42452540025c377)|上手简单，推荐新人使用|Mtool导出文件|
      |[Translator++](https://dreamsavior.net/download/)|上手复杂，功能强大，推荐大佬使用|T++导出文件或Trans工程文件|
      |[ParaTranz](https://paratranz.cn/projects)|上手中等，功能强大，推荐大佬使用|ParaTranz导出文件|
      |[RenPy SDK](https://www.renpy.org/latest.html)|上手中等，功能强大，推荐大佬使用|renpy导出文件|

 * **`🧰本地模型运行工具`**

      |工具名|说明|
      |:----:|:-----:|
      |[Sakura_Launcher_GUI](https://github.com/PiDanShouRouZhouXD/Sakura_Launcher_GUI)|Sakura模型的专属GUI启动器|
      |[LM Studio](https://lmstudio.ai/download) |一个本地部署大语言模型（LLM）平台，致力于简化LLM的使用和管理。|
      |[ollama](https://ollama.com/) |开源跨平台大模型工具 |


</details>



<details>
<summary>
  
### 翻译教程
</summary>

以下历史教程可用于了解文本提取与格式处理；本分支的浏览器界面操作以本文上方流程为准。

 * **`📺游戏翻译视频教程`**

      |视频链接|说明|
      |:----:|:-----:|
      |[Mtool教程](https://www.bilibili.com/video/BV1h6421c7MA) |初次使用推荐观看|
      |[Translator++教程](https://www.bilibili.com/video/BV1LgfoYzEaX/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501)|初次使用推荐观看|
      |[Wolf游戏教程](https://www.bilibili.com/video/BV1SnXbYiEjQ/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501)|初次使用推荐观看|
      |[人名读取教程](https://www.bilibili.com/video/BV1j1VyzqERD/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501)|进阶翻译推荐观看|

 * **`🎫游戏翻译图文教程`**

      |文章链接|说明|
      |:----:|:-----:|
      |[Mtool教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Mtool) |适合新人，懒人翻译RPG,RenPY,Krkr等游戏，进行外挂式翻译|
      |[Translator++教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Translator--%EF%BC%88%E5%B7%A5%E7%A8%8B%E6%96%87%E4%BB%B6%E7%89%88%EF%BC%89)|适合翻译RPG,RenPY,Krkr等等游戏，进行内嵌式翻译|
      |[Paratranz教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Paratranz)|适合翻译各类大型游戏的MOD|
      |[StevExtraction教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90StevExtraction)|适合翻译RPGmakerMZ/MZ游戏|
      |[Unity翻译教程](https://zhuanlan.zhihu.com/p/1894065679927313655)|适合翻译unity游戏|
      |[综合游戏翻译超详细教程](https://www.notion.so/AI-1d43d31f89b280f6bd61e12580652ce5?pvs=4)|适合翻译各类游戏，制作高质量的内嵌补丁|

</details>


</details>

---

<details>
<summary>
  
## 功能说明[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#功能说明)  
</summary>



<details>
<summary>
  
### 设置说明
</summary>

- [功能 ‐ 接口管理](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8A%9F%E8%83%BD%E2%80%90%E6%8E%A5%E5%8F%A3%E7%AE%A1%E7%90%86)

</details>

  

<details>
<summary> 

### 表格说明
</summary>

- [表格 - AI术语表](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E6%9C%AF%E8%AF%AD%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [表格 - AI禁翻表](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E7%A6%81%E7%BF%BB%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [表格 - 文本替换](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90%E6%96%87%E6%9C%AC%E6%9B%BF%E6%8D%A2%E4%BB%8B%E7%BB%8D)
    
</details>


<details>
<summary> 

### 其他说明
</summary>

* ` 多key轮询`
  >如果想使用多个key来分担消耗压力，根据key数量进行加速翻译，请使用同类型账号的key，而且输入时在每个key中间加上英文逗号，不要换行。例如：key1,key2,key3

* ` 批量文件翻译`
  >把所有需要翻译的文件放在输入文件夹即可，也支持多文件夹结构

* ` 配置迁移`
  >配置和项目缓存路径见上方「配置、缓存与升级」。升级时保留两者，才能同时恢复设置和翻译进度。

</details>


</details>



---

<details>
<summary>

## 贡献指南[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#贡献指南)  
</summary>



* **`改进或增加支持文件`**: 读写业务代码位于 `ModuleFolders/Domain/`，参见[读写器系统编写指南](ModuleFolders/Domain/FileAccessor/README.md)。本次分离改造保持这些业务逻辑不变；应用服务放在 `ModuleFolders/Application/`，HTTP 路由只校验参数并转发，前端页面位于 `frontend/src/workspaces/`，导航由 `registry.ts` 统一注册。

* **`完善正则库`**: 正则库的完备将极大帮助游戏内嵌工作的进行，并利好下一次游戏翻译工作和造福其他翻译用户，正则库在[Resource\Regex](https://github.com/NEKOparapa/AiNiee/blob/main/Resource/Regex/regex.json)文件夹中

* **`改进界面翻译`**: 前端通用文案位于 `frontend/src/i18n/`，各工作区文案位于对应目录的 `translations.ts`。新增文案需同时提供简体中文和英文。

* **`测试与许可证`**: 提交前运行上方检查，模型调用使用固定 mock；请遵守仓库 [LICENSE](LICENSE) 中的 AGPL-3.0 条款。

</details>


---

## 特别声明[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#特别声明)   

该款AI翻译工具仅供个人合法用途,任何使用该工具进行直接或者间接非法盈利活动的行为,均不属于授权范围,也不受到任何支持和认可。

* 关于开发者 @neavo 合作说明: 在AiNiee v5.2版本，已退出AiNiee的开发工作。我们对他在此期间(2024-09至2025-02)，特别是在V5版本的UI改良美化所付出的努力表示非常感谢。[详细说明](https://github.com/NEKOparapa/AiNiee/releases/tag/AiNiee6.2.3)

* **`交♂交流群`**:  Q群(反馈与交流)：7296101五零，Q群(聊天吹水)：8216248九零，入群答案：github。备用TG群：https://t.me/+JVHbDSGo8SI2Njhl ,

---



## 赞助💖
[![xxxx](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/徽章.png)](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/赞赏码.png)

