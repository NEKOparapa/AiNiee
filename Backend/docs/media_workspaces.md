# 图片与音频预览工作区

媒体工作区分别保存图片与音频的中间模型，不替换原有文档翻译工作区。图片识别、音频转录、批量翻译和输出仍使用既有应用服务；工作区接口负责导入、持久保存和提供预览资源。

## 导入与恢复

`POST /api/v2/media/import`：

```json
{"kind":"image","paths":["D:/漫画/第一卷.zip"],"exclude_rule":""}
```

`kind` 为 `image` 或 `audio`。`paths` 支持 1 至 100 个后端机器可访问的单文件、目录或 ZIP；同一工作区只接收对应媒体类型。目录递归读取，多个输入合并为一个中间模型，自然顺序排序且消除重复源引用。名称冲突会添加输入前缀，不覆盖已有文件。

ZIP 中的有效媒体被解压至持久工作区，保留子目录和中日文文件名。拒绝绝对路径、父目录穿越、链接、特殊文件、重复路径和大小写冲突，不递归解压嵌套压缩包。限制为 10000 个条目、单媒体 2 GiB、有效媒体累计 8 GiB；超过 1 MiB 的媒体还会校验压缩比上限 1000。加密 ZIP 需先解密。部分输入不可读时，保留有效文件并返回 `partial` 和具体报告。

响应包含：

| 字段 | 内容 |
| --- | --- |
| `workspace_id` | 稳定的工作区 ID |
| `kind` | `image` / `audio` |
| `model` | 中间数据模型 v2 |
| `model_path` | 纯模型 JSON 的后端绝对路径 |
| `preview_dir` | 该工作区专属图片预览输出目录 |
| `files` | `file_id`、`storage_path`、`source_url`、`translated_url` |
| `status` / `report` | 处理状态及报告 |

`GET /api/v2/media?kind=image` 返回最近 20 个工作区的简表；`limit` 可取 1 至 100。`GET /api/v2/media/{workspace_id}` 恢复完整模型和预览索引。未运行 OCR/转录时，源文件仍可预览，`items` 为空。

工作区默认保存在项目缓存目录的 `MediaWorkspaces` 中，可用 `AINIEE_MEDIA_WORKSPACE_DIR` 指定独立目录。ZIP 解压源属于工作区，删除原 ZIP 后仍可恢复；普通文件和目录使用源路径引用，移动或改变源文件后应重新导入。

## 模型保存与预览

`POST /api/v2/media/{workspace_id}/model` 接收 `{ "model": ... }`。服务验证模型仍属于该工作区，拒绝替换项目、文件 ID、媒体类型、源路径或源 SHA256。保存原子更新，HTTP 响应返回最新工作区。

图片预览使用已有 `/api/v2/write/image`，输出目录为导入响应的 `preview_dir`，重新渲染时明确 `overwrite=true`。将渲染响应中的模型及 `files` 保存：

```python
workspace = client.post(f"/api/v2/media/{workspace_id}/model", json={
    "model": rendered["model"], "preview_files": rendered["files"]
}).json()
```

`preview_files` 可省略。只有工作区 `preview_dir` 内、与模型中渲染产物路径及 SHA256 对应的图片可以注册为预览。源文、译文或条目发生变化时，旧图不会冒充新结果，`translated_url` 变为 `null`，需要重新渲染。正式导出到其他目录后仅保存模型，不将外部导出路径注册为预览。

资源接口：

- `GET/HEAD /api/v2/media/{workspace_id}/files/{file_id}/source`
- `GET/HEAD /api/v2/media/{workspace_id}/files/{file_id}/translated`

两个接口都使用已有 `Authorization: Bearer ...` 鉴权，仅访问工作区登记的文件，不接受任意文件路径。支持 HTTP byte ranges，音频播放器可跳转播放位置。源或预览文件被移动、修改时返回 `409 MEDIA_SOURCE_CHANGED`；尚无可用译图返回 `404 MEDIA_PREVIEW_NOT_READY`。原图保持原格式，客户端显示 JPEG 等格式时应启用 EXIF 方向处理。

导入、公共模型保存、工作区处理与删除共用后端顶层业务互斥。有操作正在运行时，其他公共写操作返回 `409 BACKEND_BUSY`，防止旧快照覆盖结果或删除正在使用的文件。内部处理回调可逐批持久化，不受此公共接口限制。读取图片或音频本身不会调用在线 OCR、转录或翻译接口。

## 删除工作区

`DELETE /api/v2/media/{workspace_id}` 无请求体，使用相同的 Bearer 鉴权。全部清理成功后返回：

```json
{"status":"deleted","workspace_id":"工作区 ID"}
```

删除范围仅为该 ID 的工作区目录（进度、中间模型、预览、ZIP 解压素材）及 `ImageGeneration/{workspace_id}` 生图缓存。普通原始媒体、原 ZIP 和工作区外的用户导出目录保留，不按照模型记录的任意路径删除文件。服务先校验工作区与项目 ID、根目录边界及完整目录树；符号链接、Windows junction/reparse point、特殊文件或删除期间改变的路径会被拒绝。

不存在的工作区返回 `404 MEDIA_WORKSPACE_NOT_FOUND`，不安全的目录返回 `409 MEDIA_WORKSPACE_DELETE_UNSAFE`。占用文件、权限或磁盘错误造成清理未完成时返回 `500 MEDIA_WORKSPACE_DELETE_FAILED`，不会返回 `deleted`。删除不是跨目录事务，失败前部分缓存可能已清理；错误详情中的 `partial`、`deleted`、`pending` 说明清理进度。工作区清单最后删除，尽可能保留失败项目供关闭占用文件后重试。客户端只在成功响应后移除最近项目，并在删除当前项目之前停止音频播放、释放预览资源。

## 工作区处理与停止

`POST /api/v2/media/{workspace_id}/run` 接收 `stage`、调用方生成的 `operation_id`（16 至 80 个字母、数字、下划线或连字符）、可选 `config` 与 `options`。

- `recognize`：图片调用 OCR，音频调用转录；读取对应独立接口连接及全局图译/音译任务设置，`config` 的显式字段优先覆盖。
- `translate`：调用现有多线程批量翻译，`config` 沿用翻译接口参数。
- `generate`：仅图片可用，调用独立生图模型翻译整张图片；`config` 沿用[生图接口](image_generation.md)。不调用 OCR 或文本翻译，逐页保存结果并直接注册预览。
- `preview`：仅图片可用，受控输出至该工作区的 `preview_dir` 并注册译图。
- `export`：图片写正式文件，音频写字幕；`options` 沿用对应输出接口参数。

图片的 `preview` / `export` 可通过 `options.mode` 指定 `ocr` 或 `generation`，省略时使用模型的 `extra.image_translation_mode`，默认 `ocr`。生图模式直接导出已生成图片；OCR 模式使用原有擦字排版。生图预览从受控生成缓存自动登记，校验路径、SHA256 与当前选项，切换模式保留各自预览。响应 `files[].generation_status` 提供每页生成状态；`stale` 表示配置或文本已变化，`unavailable` 表示产物缺失或不可用。

该请求同步等待操作完成，不创建后台 job。响应为 `{status, workspace, report, files}`；`workspace` 含更新后的中间模型。识别、转录与翻译的可恢复结果会通过回调逐步保存。停止后再次执行对应阶段会复用模型中已完成的内容。

`POST /api/v2/media/operations/{operation_id}/stop` 只取消匹配的媒体调用，不能停止其他页面、其他调用 ID 或原有桌面翻译任务。停止请求仅表示已发出协作取消信号，调用方仍需等待在途请求返回并处理最终模型。

当磁盘保存失败时，响应仍保留最新内存模型与已有用量报告，但 `workspace.persisted=false`、`model_path=null`，并在 `report.operation_errors` 返回 `MEDIA_CHECKPOINT_FAILED`。客户端应保留该模型，提示未保存，并重试保存；不能将旧磁盘路径显示为已保存的最新结果。不要因断线或保存错误自动重发整个付费流程。

## 桌面工作区

侧边栏的“图片翻译”和“音频翻译”各自维护独立工作区。起始页支持拖放或选择文件、目录、ZIP，以及恢复最近项目。项目详情分为“翻译”和“校润”两页，共用顶部返回、保存和导出操作。图片校润通过“图片预览 / OCR 信息”标签切换原译图对照与文字编辑；音频校润提供字幕表、时间轴、播放定位和音量。双击译文后自动保存；图片译文修改后点击“更新译图预览”。

通用识别与生成参数在“任务配置”的“音译设置”和“图译设置”中调整，修改后自动保存。两页只展示设置卡片；语言提示、随机种子和全局补充要求不在页面编辑，已有配置及 API 支持保留。图片工作区也不提供项目补充要求输入。字幕格式和内容由 `audio_translation_settings.export` 管理，图片格式由 `image_translation_settings.export` 管理；对应设置页提供自动保存的“导出设置”。

翻译页按箭头连接的步骤卡选择本次操作，卡片不另设底部计数。音频步骤为转录、翻译；图片 OCR 步骤为识别、翻译、回填。可单独执行或组合执行，缺少必要前置结果时提示补选，不会隐式增加付费步骤。桌面每次执行均明确重新处理勾选步骤：识别传 `reocr=true` 或 `retranscribe=true`，翻译传 `retranslate=true`，生图传 `regenerate=true`；已完成内容也会重新处理，界面不再设置单独的重译开关。后端/API 仍支持这些覆盖项及默认的结果复用语义。

步骤按固定顺序执行，每步保存后再继续；部分完成可沿用有效结果，失败、停止或保存失败时不再启动后续步骤。翻译仍使用原有线程池，两页不会并行启动多个顶层任务。停止会等待在途请求结束并保存有效结果。完成后不自动导出，点击顶部“导出结果”并选择目录时读取最新任务设置；支持 PNG/JPEG/WebP 和 SRT/VTT/ASS/LRC，音频支持原文、译文和双语。

图片页的“图像模型直接翻译”使用独立生图接口，桌面固定请求 `text_mode=direct`，不展示文字模式切换或补充要求输入。OCR 与生图流程保留各自预览。后端/API 仍支持 `text_mode=specified`、`replacements`、`prompt` 等参数，详见[生图流程](image_generation.md)。

远程后端需要能访问所选路径。预览通过鉴权资源接口读取；在 Windows 上，带鉴权的音频先由 Qt 网络层下载到临时文件后播放，以避免系统媒体后端丢失鉴权头。切换文件或退出会清理临时文件。

验证命令：`python Tests/run_all.py`。后端与桌面测试分进程执行，与正式应用结构一致，避免 Windows 下 QtMultimedia 与 ONNX Runtime 同进程加载时的 DLL 初始化冲突。
