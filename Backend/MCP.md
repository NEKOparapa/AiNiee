# MCP 使用说明

AiNiee 在同一个后端提供 MCP 工具，可提交文档、图片、音频和视频翻译任务，并查询或取消任务。安装与启动方式见 [后端说明](README.md)。

## 连接

- 地址：`http://127.0.0.1:3389/mcp`，传输方式选择 **Streamable HTTP**。
- 设置了 `AINIEE_API_TOKEN` 时，每个 HTTP 请求都须携带 `Authorization: Bearer <令牌>`，与 REST 共用令牌；本机未设置令牌时可不传。
- 使用支持 MCP 的客户端完成初始化和协议协商，再通过 `tools/list` 获取工具定义。
- 应用设置中的 MCP 开关对应布尔配置 `mcp_enable`，默认开启，保存后立即生效。关闭时 MCP 返回 HTTP 503、错误码 `MCP_DISABLED`；REST 仍可用，已提交任务继续执行。

路径均指向**后端机器**上的文件或目录，输出也保存在后端。远程客户端应使用后端可访问的路径。模型、语言和接口配置默认继承后端在提交时保存的设置；可在请求中覆盖，优先使用已有接口的 `provider_id`。

## 8 个工具

下表列出 `tools/call` 的 `arguments`。四个提交工具统一用 `request` 包裹；查询和取消工具直接传参数。schema 以外的字段会被拒绝，完整嵌套结构以 `tools/list` 返回的 schema 为准。

| 工具 | 参数 | 返回数据 |
| --- | --- | --- |
| `submit_document_translation` | `request`：必填 `path`；可选 `read_options`、`translation`、`output`、`request_id` | `job`，文档队列 |
| `submit_image_generation` | `request`：必填 `path`、`output`；可选 `read_options`、`generation`、`request_id` | `job`，图片队列，整图生成翻译 |
| `submit_audio_translation` | `request`：必填 `path`、`output`；可选 `read_options`、`transcription`、`translation`、`request_id` | `job`，音频队列，转录 → 翻译 → 字幕 |
| `submit_video_translation` | `request`：必填 `path`、`output`；可选 `read_options`、`transcription`、`translation`、`request_id` | `job`，视频队列，默认音轨提取 → 转录 → 翻译 → 字幕 |
| `get_job` | 必填 `job_id`；可选 `include_result`，布尔值，默认 `false` | `job`；启用后包含 `job.result` |
| `list_jobs` | 可选 `lane`：`document` / `image` / `audio` / `video`；`limit`：1–200 的整数，默认 50 | `jobs`，省略完整结果 |
| `cancel_job` | 必填 `job_id` | `job`，取消后的状态 |
| `get_queues` | `{}` | `queues`，四类队列的 `running` 与 `queued` |

返回数据位于工具结果的 `structuredContent`，同时提供等价的 JSON 文本 `content`。

常用提交选项：

- 文档 `read_options.format` 默认 `AutoType`；`pages: "1-3,5"` 仅适用于 `AutoType` 或 `BabeldocPdf`，混合目录中只影响 PDF。`exclude_rule` 用于排除文件。
- 文档 `output` 省略或为 `null` 时仅返回翻译后的模型；传入对象时执行导出。`output.output_dir` 可指定目录，`mode` 可选 `translated`、`bilingual`、`both`，默认 `translated`。
- 整图生成、音频和视频必须提供 `output.output_dir`。图片的 `output.format` 可选 `png`、`jpeg`、`webp`，默认 `png`；音频可选 `srt`、`vtt`、`lrc`、`ass`，默认 `srt`，`output.mode` 默认 `translated`，也可选 `source`、`bilingual`。
- `translation` 常用字段为 `provider_id`、`source_language`、`target_language`、`user_thread_counts`。整图生成的语言和接口覆盖放在 `generation` 中。
- `request_id` 可省略；提供时须为 16–80 位英文字母、数字、下划线或连字符，将直接作为任务 ID。整图生成在 MCP 中也使用它，不传 REST 的 `operation_id`。

## 提交文档并取回结果

下面代码块是 MCP `tools/call` 的 `params`。先在后端配置可用的翻译接口，再替换路径和本次唯一的 `request_id`：

```json
{
  "name": "submit_document_translation",
  "arguments": {
    "request": {
      "request_id": "document_demo_0001",
      "path": "D:/inputs/sample.txt",
      "read_options": {"format": "Txt"},
      "translation": {"target_language": "chinese_simplified"},
      "output": {"output_dir": "D:/outputs", "mode": "translated"}
    }
  }
}
```

提交立即返回 `structuredContent.job`，保存其中的 `id`。使用该 ID 定期查询进度：

```json
{
  "name": "get_job",
  "arguments": {"job_id": "document_demo_0001"}
}
```

检查 `structuredContent.job.state` 和 `progress`。`queued`、`running`、`cancelling` 表示尚未结束；`succeeded`、`partial`、`failed`、`cancelled`、`interrupted` 为终态。到达终态后，再请求完整结果：

```json
{
  "name": "get_job",
  "arguments": {"job_id": "document_demo_0001", "include_result": true}
}
```

读取 `structuredContent.job.result` 中的 `status`、`model`、`files` 和 `report`；文档报告包含各阶段执行情况。`result_available` 表示是否保存了结果，异常终止时 `result` 可能为 `null`，此时检查 `job.error`。`partial` 或取消任务也可能保留部分模型和文件，应先检查报告再决定后续操作。

## 排队、重试与取消

- MCP、REST 与桌面共用 `document`、`image`、`audio`、`video` 四个队列；各队列一次执行一个任务，四个队列可并行。同类任务忙碌时继续排队，查询和取消无需等待业务队列。
- MCP 断线不会取消任务。任务记录与结果持久保存；后端重启后未完成任务标为 `interrupted`，不会自动重新执行。
- `request_id` 在所有队列及入口之间共用任务 ID 空间。重复 ID 返回工具错误 `DUPLICATE_JOB_ID`，包括已有任务结束后；不会返回原结果，也不会再次执行。提交响应丢失时，先用原 ID 调用 `get_job`，确认后再决定是否使用新 ID 提交。
- `cancel_job` 取消排队任务时直接变为 `cancelled`；运行中任务先变为 `cancelling`，等待在途调用及保存收尾。继续查询直到终态。取消不会撤回已完成的模型调用或文件写入，重复取消不会改变终态记录。
- 工具错误通过 `isError: true` 和 `structuredContent.error.code/message` 返回，例如参数错误 `INVALID_MCP_ARGUMENTS`、任务不存在 `JOB_NOT_FOUND`。鉴权失败则是 HTTP 401。工具调用成功仍可能返回业务失败的任务，需检查 `job.state`、`job.error` 及 `job.result.status/report`。

## 远程连接

监听非本机地址必须设置 `AINIEE_API_TOKEN`。MCP 默认仅允许本机 Host / Origin；通过环境变量追加实际部署地址，修改后重启后端：

```powershell
$env:AINIEE_API_TOKEN = "替换成随机令牌"
$env:AINIEE_MCP_ALLOWED_HOSTS = "translate.example.com"
# 客户端发送 Origin 请求头时，加入该客户端的实际来源；未发送时无需设置。
$env:AINIEE_MCP_ALLOWED_ORIGINS = "https://client.example.com"
python -m Backend --host 0.0.0.0 --port 3389
```

多个值用逗号分隔。Host 填具体主机名或 IP，可附端口，例如 `192.168.1.20:3389`；Origin 填 `http://` 或 `https://` 加主机及可选端口。可用 `:*` 匹配任意端口，不支持 `*` 或域名通配符，也不能带路径、查询参数或凭据。设置会追加到本机默认允许列表；未携带 Origin 的请求仍会检查 Host 和令牌。

跨网络部署使用 HTTPS 反向代理，客户端连接如 `https://translate.example.com/mcp`。此服务面向可信环境，工具能够调用收费模型并访问后端文件，不提供多用户文件隔离。

视频翻译依赖后端 PATH 中的 `ffmpeg` 和 `ffprobe`。调用结构与音频相同，视频任务单独读取 `video_translation_settings`；默认输出 SRT 双语字幕，显式 `output.format/mode` 优先。转录接口只接收提取音频，不接收视频画面。
