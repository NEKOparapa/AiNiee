# 后端接口说明

AiNiee 后端提供文档、图片和音频处理接口，以及桌面工作区、配置和任务管理接口。MCP 接入见 [MCP.md](MCP.md)。

## 连接与调用约定

安装后端依赖后，在项目根目录启动：

```powershell
python -m Backend --host 127.0.0.1 --port 3389
```

- 默认地址：`http://127.0.0.1:3389`；完整字段、类型和默认值见运行后的 [交互文档](http://127.0.0.1:3389/docs) 与 [OpenAPI](http://127.0.0.1:3389/openapi.json)。
- 请求体使用 JSON。设置 `AINIEE_API_TOKEN` 后，HTTP 和 WebSocket 请求须携带 `Authorization: Bearer <令牌>`；监听非本机地址必须设置令牌。
- 所有输入、输出及导入导出路径均属于**后端所在机器**；路径参数不会上传客户端文件。
- 文档、图片、音频分别使用 `document`、`image`、`audio` 队列。同类任务串行，不同类可并行；后端使用单进程、单 worker。

## 任务查询与取消

| 接口 | 用途与返回 |
| --- | --- |
| `GET /health` | 返回服务名称与协议版本 |
| `GET /api/status` | 当前文档状态、进度，以及全局 `any_busy`、`queues`；`busy` 仅表示文档队列 |
| `GET /api/queues` | 返回三类队列的运行任务和等待任务，字段为 `queues` |
| `GET /api/jobs` | 返回 `jobs` 列表；可选 `lane`、`limit`（1–200，默认 50），不含完整结果 |
| `GET /api/jobs/{job_id}` | 返回 `job`，包含 `state`、`progress`、`result` 和 `error` |
| `POST /api/jobs/{job_id}/cancel` | 取消指定任务，返回更新后的 `job` |

下文 `/api/v2` 的处理、保存和删除接口默认等待执行完成。添加请求头 `Prefer: respond-async` 可立即取得 `202 {"job": ...}`，响应头 `Location` 指向任务查询地址；查询、预览和停止接口直接返回。

任务状态为 `queued`、`running`、`cancelling`，以及终态 `succeeded`、`partial`、`failed`、`cancelled`、`interrupted`。运行任务采用协作取消，需要等待在途请求和保存收尾；断线不会取消任务，重启也不会自动重放未完成任务。

## 文档与通用翻译

以下接口使用请求携带的中间模型，不切换桌面的当前文档项目。`model` 为 `schema_version: 2` 的项目 → 文件 → 条目结构，应保留读取结果中的源文件引用、定位信息和 `extra`。

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/read/document` | `path`，可选 `options.format/exclude_rule/pages`；读取文档或目录，返回模型与读取报告 |
| `POST /api/v2/translate` | `model`，可选 `config`；翻译文档、图片 OCR 或音频转录模型中的文本 |
| `POST /api/v2/write` | `model`，可选 `options.output_dir/mode/overwrite`；将文档模型写出为文件 |

典型流程：`read/document` → 将返回的 `model` 交给 `translate` → 将更新后的 `model` 交给 `write`。

- 读取默认 `format: "AutoType"`。PDF 使用 BabelDOC；`pages` 如 `"1-3,5"`，仅适用于 `AutoType` 或 `BabeldocPdf`。
- 翻译配置可设置 `provider_id`、`source_language`、`target_language`、线程数、分块和术语规则；省略字段时继承任务提交时的后端配置，不修改全局设置。`provider_id` 是已保存接口的 ID。
- 默认跳过有效译文；切换目标语言需显式设置 `retranslate: true`。文档导出 `mode` 支持 `translated`、`bilingual`、`both`。
- 读取、翻译返回 `status/model/report`；文档写出返回 `status/files/report`。HTTP 200 仍须检查业务 `status` 和报告；非 2xx 查看 `detail`，以及响应中可能包含的 `error.code/message`。

## 图片接口

两种完整流程分别为 OCR 识别后翻译回填，以及直接调用生图接口翻译整图。各阶段也可单独调用。

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/read/image` | `path`、可选 `options.exclude_rule`；读取图片或目录并完成本地文本检测，返回检测区域与待识别条目，不调用在线 OCR |
| `POST /api/v2/image/detect` | `model`；对已导入图片补做或重新执行本地文本检测 |
| `POST /api/v2/ocr` | `model`、可选 `config`；复用检测区域识别原文，再按阅读顺序合并对白 |
| `POST /api/v2/image/repair` | `model`、`options.output_dir`；按可安全回填的文字区域擦除原文，保存修复图和排版计划 |
| `POST /api/v2/image/render` | `model`、`options.output_dir`；复用有效修复图，将译文排入原文位置 |
| `POST /api/v2/image/export` | `model`、`options.output_dir`；复制或转码有效译图，不重新修复或渲染 |
| `POST /api/v2/write/image` | `model`、`options.output_dir`；兼容的一键修复 → 渲染 → 导出，可设置字体、方向、擦除方式及图片格式 |
| `POST /api/v2/image/translate` | `path`、`output.output_dir`；可选 `read_options/ocr/translation`，顺序执行完整七步并保存检查点 |
| `POST /api/v2/image/generate-translation` | `model`、可选 `config/operation_id`；调用生图接口生成译图，返回含产物引用的模型 |
| `POST /api/v2/write/generated-image` | `model`、`options.output_dir`；导出生图产物及可选中间模型 |
| `POST /api/v2/image/generate-pipeline` | `path`、`output.output_dir`；可选 `read_options/generation/operation_id`，执行读取 → 生图翻译 → 导出 |
| `POST /api/v2/image/operations/{operation_id}/stop` | 按提交时的操作 ID 停止对应 API 任务；也可使用通用任务取消接口 |

OCR 使用独立的 OCR 平台配置，生图使用独立的生图平台配置。图片写出、完整流程及生图处理返回 `status/model/files/report`；支持的图片输出格式为 `png`、`jpeg`、`webp`。

图片 OCR 翻译按 [Saber-Translator](https://github.com/MashiroSaber03/Saber-Translator#readme) 的七步组织：**导入图片 → 文本检测 → OCR 识别 → AI 翻译 → 图像修复 → 文字渲染 → 导出**。读取接口一次完成前两步，并在 `file.extra.text_detection` 保存源文件指纹、检测版本、原图坐标及空白页标记；读取结果已包含带定位的待识别条目。检测失败和取消会保留已读取图片并返回对应状态，不将其伪装为无文字图片。

OCR 默认 `recognition_mode: "regions"`：复用读取时的本地检测区域 → 按区域裁切识别原文 → 合并对白。局部处理思路也参考 [manga-image-translator](https://github.com/zyddnys/manga-image-translator)，检测使用已有 RapidOCR，文字识别继续使用配置的 OCR 接口。`recognition_mode: "page"` 可切回接口整页识别。未保存检测记录的旧模型可在 OCR 时补检；失败或失效的检测需显式重做。

- 分区识别每个文字区域分别请求接口，每页最多 128 区；坐标来自本地检测，接口返回值只用于原文。区域结果及用量随检查点保存，失败或取消后可继续；已完成页面显式 `reocr: true` 会重新识别。
- `group_lines: true` 将同气泡中的文字行合并成翻译条目，避免将一句对白拆开翻译。新配置默认开启，已有显式关闭的设置保留。`refine_text` 仍表示可选的额外气泡原文复核，默认关闭。
- 检测、OCR 和回填仍可能漏掉手写字或无法可靠分离的线稿。未完成的识别区域保留定位且不翻译半句；回填报告区分实际写入、主动保留和跳过，并保存具体原因。完整气泡可利用内部空白排版，自定义布局保持原样。
- 修复、渲染分别保存产物及校验指纹；源图、文字、定位或排版设置改变后，需要重新执行受影响步骤。独立导出接口遇到缺失或过期译图会明确报错。各步应传递上一步返回的完整 `model`；修复/渲染使用相同排版选项，导出仅改变目录、格式等输出选项。

## 音频接口

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/read/audio` | `path`、可选 `options.exclude_rule`；读取音频或目录，建立音频模型 |
| `POST /api/v2/transcribe` | `model`、可选 `config`；在线转录，补充原文和时间轴 |
| `POST /api/v2/write/subtitles` | `model`、`options.output_dir`；导出字幕，可设置 `format/mode/bilingual_order` |
| `POST /api/v2/audio/translate` | `path`、`output.output_dir`；可选 `read_options/transcription/translation`，执行读取 → 转录 → 翻译 → 字幕导出 |

转录使用独立的转录平台配置。字幕格式支持 `srt/vtt/lrc/ass`，模式支持 `translated/source/bilingual`；完整流程返回 `status/model/files/report`。长音频自动分片处理，依赖 FFmpeg。

## 图片与音频工作区

需要保存中间状态、编辑识别结果或预览文件时使用这些接口。

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/media/import` | `kind: image/audio`、`paths`，可选 `exclude_rule`；导入并创建工作区 |
| `GET /api/v2/media` | 返回 `workspaces` 历史列表；可选 `kind`、`limit`（1–100，默认 20） |
| `GET /api/v2/media/{workspace_id}` | 获取工作区模型、文件信息与处理状态 |
| `POST /api/v2/media/{workspace_id}/model` | `model`、可选 `preview_files`；保存编辑后的模型 |
| `POST /api/v2/media/{workspace_id}/run` | `stage`、`operation_id`，可选 `config/options`；运行一个处理阶段并保存结果 |
| `DELETE /api/v2/media/{workspace_id}` | 删除工作区 |
| `GET /api/v2/media/{workspace_id}/files/{file_id}/{variant}` | 预览 `source`、`repaired` 或 `translated` 文件，支持 Range 请求 |
| `HEAD /api/v2/media/{workspace_id}/files/{file_id}/{variant}` | 获取预览文件响应头 |
| `POST /api/v2/media/operations/{operation_id}/stop` | 停止指定 API 媒体任务 |

`stage` 支持 `detect`（仅图片）、`recognize`（OCR/转录）、`translate`、`repair`、`render`、`generate`（仅图片）、兼容的 `preview`（修复并渲染）、`export`。导入图片自动完成 `read` 与 `detect`，无需再提交检测步骤。识别/翻译/生图阶段传 `config`；修复/渲染/预览/导出阶段传 `options`。修复和渲染目录由工作区管理；OCR 导出要求已有有效译图。`operation_id` 必须为 16–80 位字母、数字、下划线或连字符。

## 桌面当前项目接口

这些接口操作后端当前文档项目。表中标记 **202** 的接口提交任务后立即返回状态及 `job_id/job`；加载、保存和检查等待完成后返回。

| 接口 | 主要参数与用途 |
| --- | --- |
| `GET /api/project` | 返回当前 `project` 快照；未加载时为 `null` |
| `GET /api/project/types` | 返回支持的项目格式列表 |
| `POST /api/project/load` | `input_path`，可选 `project_type/exclude_rule`；加载并保存当前项目 |
| `GET /api/project/preflight/{role}` | 检查 `translate` 或 `polish` 绑定的接口，返回 `selected_tag/exists` |
| `POST /api/tasks/translation` | `continue_status`（默认 `false`）；开始或继续翻译，**202** |
| `POST /api/tasks/analysis` | 分析当前项目，**202** |
| `POST /api/tasks/table/translate` | `file_path/items_to_translate` 或 `translate_jobs`；翻译指定条目，**202** |
| `POST /api/tasks/table/polish` | `file_path/items_to_polish` 或 `polish_jobs`；润色指定条目，**202** |
| `POST /api/tasks/table/proofread` | `file_path/items_to_proofread` 或 `proofread_jobs`；校对指定条目，**202** |
| `POST /api/tasks/glossary/translate` | `table_id/prompt_dictionary_data`、可选 `request_id`；翻译术语，**202** |
| `POST /api/tasks/api-test` | `api_url/api_key/api_format/model` 等接口配置；测试连接，**202** |
| `POST /api/tasks/stop` | 停止文档队列中桌面发起的当前或首个等待任务，不停止图片和音频任务 |
| `POST /api/project/export` | 可选 `export_path`；导出当前项目文件，**202** |
| `POST /api/project/save` | 保存当前项目缓存 |
| `POST /api/check/{kind}` | `kind` 为 `language/rule/terminology`；请求体传对应检查参数 |
| `POST /api/cache/{method}` | `args/kwargs/project_id`；调用缓存白名单操作，返回 `result/project` |

表格条目包含 `text_index/source_text/translation_text`；单文件参数与多文件 `*_jobs` 不能混用。可选 `view` 用于指定结果通知的界面。

缓存白名单：`list_project_histories`、`delete_project_cache`、`load_from_project_id`、`load_from_file`、`save_to_file`、`reset_project_status`、`set_analysis_data`、`clear_analysis_data`、`update_item_text`、`update_generated_translation`、`search_items`。当前项目编辑、搜索等调用需携带匹配的 `project_id`，防止项目切换后操作错位。

## 配置与辅助接口

| 接口 | 主要参数与用途 |
| --- | --- |
| `GET /api/config` | 返回 `config` 与版本标识 `revision` |
| `PATCH /api/config` | `values`，可选 `revision/table_update`；更新配置，版本冲突返回 409 |
| `GET /api/config/info` | 返回后端配置文件路径 |
| `GET /api/config/defaults/{section}` | 获取指定配置分组的默认值 |
| `GET /api/config/platform-presets` | 获取接口预设 |
| `GET /api/config/prompt-presets/{kind}` | 获取 `translation/polishing/extraction` 提示词模板 |
| `POST /api/config/import` | `path` 为配置文件；合并导入配置 |
| `POST /api/config/export` | `path` 为输出目录；生成 `ainiee_profile.json` |
| `POST /api/editor/{operation}` | `args/kwargs`；执行表格、角色、术语、正则、模型选项、请求头或路径辅助操作，返回 `result` |
| `POST /api/models` | `url/headers` 或 `google_config`；查询模型列表 |
| `POST /api/names` | `path` 为目录；提取目录中的人名信息 |
| `POST /api/shutdown` | 请求关闭后端；外部 API/MCP 任务未结束或当前启动方式不支持关闭时返回 409 |

编辑操作白名单及各操作签名见 [editor.py](application/editor.py)。配置更新影响之后提交的任务；代理设置需要等全部队列空闲后生效，可查询 `network_settings_pending`。

## 实时通知

连接 `WS /ws/events` 接收状态、日志与任务通知：

| `type` | 内容 |
| --- | --- |
| `connected`、`status` | 初始状态与空闲等待时每 2 秒的状态心跳 |
| `job` | 任务元信息和进度；完整结果通过任务查询接口获取 |
| `notification` | `name/data`，如 `translation.completed`、`table.updated`、`project.export.completed` |
| `log` | 日志文本与等级 |
| `settled`、`error` | 具名业务操作的结束状态或错误 |
| `resync` | 客户端消费过慢；重新连接并读取状态、项目和任务快照 |

MCP 使用同一个后端和任务队列，但通过 `/mcp` 提供工具调用，详见 [MCP 接入说明](MCP.md)。
