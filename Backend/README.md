# 后端接口说明

AiNiee 后端提供文档、图片、音频和视频处理接口，以及桌面工作区、配置和任务管理接口。MCP 接入见 [MCP.md](MCP.md)。

## 连接与调用约定

安装后端依赖后，在项目根目录启动：

```powershell
python -m Backend --host 127.0.0.1 --port 3389
```

- 默认地址：`http://127.0.0.1:3389`；完整字段、类型和默认值见运行后的 [交互文档](http://127.0.0.1:3389/docs) 与 [OpenAPI](http://127.0.0.1:3389/openapi.json)。
- 请求体使用 JSON。设置 `AINIEE_API_TOKEN` 后，HTTP 和 WebSocket 请求须携带 `Authorization: Bearer <令牌>`；监听非本机地址必须设置令牌。
- 所有输入、输出及导入导出路径均属于**后端所在机器**；路径参数不会上传客户端文件。
- 文档、图片、音频、视频分别使用 `document`、`image`、`audio`、`video` 队列。同类任务串行，不同类可并行；后端使用单进程、单 worker。

## 任务查询与取消

| 接口 | 用途与返回 |
| --- | --- |
| `GET /health` | 返回服务名称与协议版本 |
| `GET /api/status` | 当前文档状态、进度，以及全局 `any_busy`、`queues`；`busy` 仅表示文档队列 |
| `GET /api/queues` | 返回四类队列的运行任务和等待任务，字段为 `queues` |
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
| `POST /api/v2/translate` | `model`，可选 `config`；翻译文档、音频或视频转录模型中的文本 |
| `POST /api/v2/write` | `model`，可选 `options.output_dir/mode/overwrite`；将文档模型写出为文件 |

典型流程：`read/document` → 将返回的 `model` 交给 `translate` → 将更新后的 `model` 交给 `write`。

- 读取默认 `format: "AutoType"`。PDF 使用 BabelDOC；`pages` 如 `"1-3,5"`，仅适用于 `AutoType` 或 `BabeldocPdf`。
- 翻译配置可设置 `provider_id`、`source_language`、`target_language`、线程数、分块和术语规则；省略字段时继承任务提交时的后端配置，不修改全局设置。`provider_id` 是已保存接口的 ID。
- 并发任务数按接口保存为 `platforms.<接口 ID>.user_thread_counts`，0 为自动，正整数为指定并发数。提取、翻译按对应角色绑定选择接口，未绑定时跟随激活接口；自动模式先以 1–8 个请求并发启动，按成功请求的耗时移动平均和 RPM 估算目标值，保留 10% 余量，每次最多增加约 25%，上限 64；连续两次请求失败时减半并等待 5 秒，再逐步恢复。请求按 RPM 间隔和到达顺序发送，排队可取消，并受请求超时约束；排队耗时及取消不计入响应统计。重复或空密钥不再放大 RPM。本地 llama.cpp 优先使用有效槽位数（最多 64），探测超时 2 秒，失败回退到 2 个并发。自动控制状态按任务隔离，不写入配置；手动正整数仍使用指定值。旧接口缺少该字段时初始化为 0，旧全局并发字段不再使用。REST/MCP 显式传入 `user_thread_counts` 仅覆盖本次翻译操作；省略时读取所选接口配置，已提交任务不受后续修改影响。
- 默认跳过有效译文；切换目标语言需显式设置 `retranslate: true`。文档导出 `mode` 支持 `translated`、`bilingual`、`both`。
- 读取、翻译返回 `status/model/report`；文档写出返回 `status/files/report`。HTTP 200 仍须检查业务 `status` 和报告；非 2xx 查看 `detail`，以及响应中可能包含的 `error.code/message`。

## 图片接口

图片统一使用单步整图翻译：将原图与翻译提示词一次发送给生图模型，由模型完成识别、翻译、擦字和原位回填。读取图片只建立文件模型，不再调用本地检测或 OCR 服务。

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/read/image` | `path`、可选 `options.exclude_rule`；读取图片或目录，建立原图文件模型 |
| `POST /api/v2/image/generate-translation` | `model`、可选 `config/operation_id`；调用生图接口生成译图，返回含产物引用的模型 |
| `POST /api/v2/write/generated-image` | `model`、`options.output_dir`；导出生图产物及可选中间模型 |
| `POST /api/v2/image/generate-pipeline` | `path`、`output.output_dir`；可选 `read_options/generation/operation_id`，执行读取 → 生图翻译 → 导出 |
| `POST /api/v2/image/operations/{operation_id}/stop` | 按提交时的操作 ID 停止对应 API 任务；也可使用通用任务取消接口 |

生图接口独立配置，支持阿里云 DashScope、火山 Volcengine Ark 和 Gemini 官方接口。Gemini 使用官方 `generateContent` 协议，在请求中发送原图与提示词，直接保存响应中的图片；不需要先上传至公开图床。模型返回的文字不会作为成功译图。

默认提示词要求逐个文字区域对应原位替换，完整清除可读原文、不跨气泡混合对白、不新增人物或气泡，并保留分镜、画面颜色与品牌标志。模型仍可能漏译或改动画面，应在导出前检查译图。任务失败或结果未知时不会自动重复付费请求。

`GET /api/config/prompt-presets/image_translation` 返回内置图片翻译指令。根配置 `image_translation_user_prompt_data` 保存自定义提示词库，`image_translation_prompt_selection.last_selected_id` 选择正在使用的条目。生成时读取选中条目的正文，替换默认指令，并自动加入源语言、目标语言与原图；旧版 `image_translation_settings.generation.prompt` 仍作为补充要求兼容。提示词修改在下次生成生效，已有译图仍可预览、导出。图译提示词配置与文译提示词相互独立。

## 音频接口

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/read/audio` | `path`、可选 `options.exclude_rule`；读取音频或目录，建立音频模型 |
| `POST /api/v2/transcribe` | `model`、可选 `config`；在线转录，补充原文和时间轴 |
| `POST /api/v2/write/subtitles` | `model`、`options.output_dir`；导出字幕，可设置 `format/mode/bilingual_order` |
| `POST /api/v2/audio/translate` | `path`、`output.output_dir`；可选 `read_options/transcription/translation`，执行读取 → 转录 → 翻译 → 字幕导出 |

转录使用独立的转录平台配置。字幕格式支持 `srt/vtt/lrc/ass`，模式支持 `translated/source/bilingual`；完整流程返回 `status/model/files/report`。长音频自动分片处理，依赖 FFmpeg。

## 视频接口

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/read/video` | `path`、可选 `options.exclude_rule`；探测本地视频或目录，建立 `Video` 模型，不立即提取音频 |
| `POST /api/v2/video/translate` | `path`、`output.output_dir`；可选 `read_options/transcription/translation`，执行读取 → 提取音轨 → 转录 → 翻译 → 字幕导出 |

支持 MP4、MKV、MOV、AVI、WebM、M4V、WMV、FLV。自动构建的 Windows/macOS 发布包已内置 `ffmpeg`、`ffprobe`，用户无需另外安装或配置 PATH。后端优先使用自身 PyInstaller 包内 `media-tools` 目录中的工具，找不到时才查找系统 PATH；源码运行仍需在后端机器安装 FFmpeg。选择标记为默认的音轨；没有默认标记时选择第一条。只向转录接口上传提取的 16 kHz 单声道 PCM WAV；保留音轨相对视频的起始偏移，字幕使用视频播放时间轴。不执行画面 OCR、配音或字幕烧录。
## 媒体工作区

需要保存项目状态、编辑音频转录结果或预览文件时使用这些接口。

| 接口 | 主要参数与用途 |
| --- | --- |
| `POST /api/v2/media/import` | `kind: image/audio/video`、`paths` 为媒体文件或目录路径，可选 `exclude_rule`；导入并创建工作区，不读取 ZIP 等压缩包 |
| `GET /api/v2/media` | 返回 `workspaces` 历史列表；可选 `kind`、`limit`（1–100，默认 20） |
| `GET /api/v2/media/{workspace_id}` | 获取工作区模型、文件信息与处理状态 |
| `POST /api/v2/media/{workspace_id}/model` | `model`、可选 `preview_files`；保存编辑后的模型 |
| `POST /api/v2/media/{workspace_id}/run` | `stage`、`operation_id`，可选 `config/options`；运行一个处理阶段并保存结果 |
| `DELETE /api/v2/media/{workspace_id}` | 删除工作区 |
| `GET /api/v2/media/{workspace_id}/files/{file_id}/{variant}` | 预览 `source`、`translated` 或视频 `preview` 文件，支持 Range 请求 |
| `POST /api/v2/media/{workspace_id}/files/{file_id}/video-preview` | 请求体 `{}` 或 `operation_id`；准备仅含选定音轨的视频预览，视频流直接复制，返回 `url` |
| `HEAD /api/v2/media/{workspace_id}/files/{file_id}/{variant}` | 获取预览文件响应头 |
| `POST /api/v2/media/operations/{operation_id}/stop` | 停止指定 API 媒体任务 |

图片 `stage` 支持 `generate`、`export`，以及仅复制已有生图产物的 `preview`；音频和视频支持 `recognize`、`translate`、`export`。导入图片只读取原图，生成阶段传 `config`，预览或导出阶段传 `options`。导出要求已有有效生成结果；旧 OCR 阶段与接口已移除。`operation_id` 必须为 16–80 位字母、数字、下划线或连字符。

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
| `POST /api/tasks/stop` | 停止文档队列中桌面发起的当前或首个等待任务，不停止图片、音频和视频任务 |
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
