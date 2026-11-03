# 将 AiNiee 翻译能力提供给 MCP 客户端

后端在现有 HTTP 服务的 `/mcp` 提供 Streamable HTTP MCP 接口，使用官方 Python SDK `mcp==2.3.0`。无需另起 MCP 服务进程，也无需启动桌面。MCP 与 REST、桌面共用同一个 Runtime、配置和[三类任务队列](task_queues.md)。

此接口提供翻译提交、任务查询和取消工具；不提供任意 Python 调用或配置密钥查询工具。翻译提交立即返回应用层 job ID，实际模型调用在对应队列执行。MCP 连接不是任务生命周期，客户端断开后任务继续运行。

## 连接与鉴权

桌面“应用设置”中的“MCP 服务”默认开启（`mcp_enable: true`）。修改开关保存后立即生效，无需重启后端；关闭后，已通过鉴权的 `/mcp` 请求返回 HTTP 503，错误码为 `MCP_DISABLED`，包括工具发现、查询和取消。已提交任务继续执行。需要管理这些任务时，REST 配置、`GET /api/jobs/{job_id}` 与 `POST /api/jobs/{job_id}/cancel` 仍可使用；也可重新开启 MCP。无桌面时可用 `PATCH /api/config` 发送 `{"values":{"mcp_enable":false}}` 关闭，改为 `true` 重新开启。

同一设置页的“MCP 连接地址”按当前后端地址加 `/mcp` 自动生成，只读显示，并提供“复制地址”按钮。将该地址粘贴到客户端的 Streamable HTTP 连接设置即可；远程连接仍需配置下述令牌与允许的 Host/Origin。

按 [后端启动说明](../README.md#启动与部署) 安装依赖并启动，例如：

```powershell
python -m pip install -r requirements-backend.txt
python -m Backend --host 127.0.0.1 --port 3389
```

在支持远程 HTTP MCP 的客户端中填写：

| 配置 | 值 |
| --- | --- |
| 传输 | Streamable HTTP |
| 地址 | `http://127.0.0.1:3389/mcp` |
| 请求头 | 设置了 `AINIEE_API_TOKEN` 时填写 `Authorization: Bearer <令牌>` |

端点为 `/mcp`，没有尾部斜杠，也不是 `/api/mcp`；无需 stdio 启动命令。具体客户端保存连接配置的字段名不同，请使用其 HTTP MCP 连接入口。后端 SDK 同时支持当前协议发现及旧版 `initialize` 连接流程；端到端测试覆盖官方客户端的自动协商和 legacy 模式。[官方客户端与传输文档](https://py.sdk.modelcontextprotocol.io/client/transports/)

访问令牌沿用 REST 的 `AINIEE_API_TOKEN`。设置令牌后，每个 MCP HTTP 请求都会校验它，携带 MCP session ID 不能绕过鉴权。只支持现有 Bearer 令牌，不提供 OAuth 登录或多用户权限隔离。

默认仅允许本机 Host/Origin。通过远程域名、局域网 IP 或反向代理访问时，除设置访问令牌外，还需在启动前显式添加相应地址：

```powershell
$env:AINIEE_API_TOKEN = "替换成随机令牌"
$env:AINIEE_MCP_ALLOWED_HOSTS = "ainiee.example.com,192.168.1.20:3389"
$env:AINIEE_MCP_ALLOWED_ORIGINS = "https://ainiee.example.com"
python -m Backend --host 0.0.0.0 --port 3389
```

`AINIEE_MCP_ALLOWED_HOSTS` 与 `AINIEE_MCP_ALLOWED_ORIGINS` 使用逗号分隔，追加到本机默认值。Host 为具体域名/IP，可附端口或 `:*`；Origin 为 `http://` 或 `https://` 加具体主机及可选端口。只列入实际使用的地址，不支持通配域名或 `*` 关闭校验。没有 Origin 请求头的非浏览器客户端仍可连接。域名入口应由 HTTPS 反向代理提供 TLS，并保留或正确设置 Host 与请求头。

所有 `path`、`output_dir` 都属于**后端机器**。远程 MCP 客户端不能直接把自己机器上的路径当作后端文件；本接口不上传原文件，也不提供跨机器的任意文件下载。

## 工具与参数

使用 MCP 工具列表获得完整 JSON Schema。四个提交工具的参数都包在 `request` 对象内。

| 工具 | 参数与行为 |
| --- | --- |
| `submit_document_translation` | `request.path` 必填；可选 `read_options`、`translation`、`output`。文档/PDF读取 → 翻译 → 可选导出，进入 `document` 队列 |
| `submit_image_translation` | `request.path` 与 `request.output.output_dir` 必填；可选 `read_options`、`ocr`、`translation`。图片读取 → OCR → 翻译 → 图片导出，进入 `image` 队列 |
| `submit_image_generation` | `request.path` 与 `request.output.output_dir` 必填；可选 `read_options`、`generation`。整图生成翻译与导出，进入同一个 `image` 队列 |
| `submit_audio_translation` | `request.path` 与 `request.output.output_dir` 必填；可选 `read_options`、`transcription`、`translation`。音频读取 → 转录 → 翻译 → 字幕导出，进入 `audio` 队列 |
| `get_job` | `job_id` 必填；`include_result` 默认 `false`。返回 `{job}`，默认省略完整模型与结果 |
| `list_jobs` | 可选 `lane`（`document/image/audio`）与 `limit`（1–200，默认 50）。返回 `{jobs}`，列表不包含完整结果 |
| `cancel_job` | `job_id` 必填。返回 `{job}`，精确取消指定任务 |
| `get_queues` | 无参数。返回 `{queues}`，包含三个队列的运行任务与待执行任务 |

提交工具返回 `{job}` 摘要，包括 ID、队列、状态、进度和 `result_available`；新任务的 `source` 为 `mcp`。查询与取消直接访问调度器，不排在翻译之后。查询结果包含同一后端的 REST、桌面和 MCP 任务，通用取消工具也可取消这些任务。

文档 `output` 省略时只取得翻译后的模型，不自动导出文件；提供 `output` 时按文档写出选项导出。文档读取默认自动识别 PDF，选页使用 `read_options.pages`。文档流水线某阶段部分完成或失败时保留当前模型及分阶段报告，不自动继续后续收费或写出步骤。

图片、音频参数复用对应 [OCR 图片流程](image_pipeline.md)、[生图流程](image_generation.md) 和 [音频流程](audio_pipeline.md)。省略的接口、语言、提示词等使用**提交时**的后端配置快照，显式参数覆盖该快照。`provider_id` 是后端已保存接口的 ID，不是模型名称；优先引用已配置接口，无需向客户端复制密钥。

四个提交工具均允许可选 `request.request_id`，由 16–80 个字母、数字、下划线或连字符组成，直接作为 job ID。省略时后端生成 ID。相同 ID 再次提交返回 `DUPLICATE_JOB_ID`，不会自动重复执行，也不会作为幂等请求返回原结果。若提交响应丢失，应先按已知 ID 查询；不要直接重发收费任务。MCP 使用 `request_id`，不使用 REST 生图接口的 `operation_id`。

文档工具调用参数示例：

```json
{
  "request": {
    "path": "D:/inputs/book.pdf",
    "read_options": {"pages": "1-3,5"},
    "translation": {"target_language": "chinese_simplified", "user_thread_counts": 4},
    "output": {"output_dir": "D:/outputs/book", "mode": "translated"},
    "request_id": "translate_book_20261103"
  }
}
```

音频工具调用参数示例：

```json
{
  "request": {
    "path": "D:/inputs/episode.mp3",
    "translation": {"target_language": "chinese_simplified"},
    "output": {"output_dir": "D:/outputs/subtitles", "format": "srt", "mode": "translated"}
  }
}
```

## 使用官方 SDK 提交与查询

以下示例使用与后端相同的官方 SDK 2.3.0。SDK 的 HTTP 客户端为 `httpx2`；通过 `streamable_http_client` 传入自定义 Bearer 请求头。[官方 SDK 用法](https://py.sdk.modelcontextprotocol.io/client/)

```python
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


def payload(result):
    if result.is_error:
        raise RuntimeError(result.structured_content or result.content)
    return result.structured_content


async def main():
    headers = {}
    if token := os.environ.get("AINIEE_API_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    async with httpx2.AsyncClient(headers=headers, trust_env=False, timeout=30) as http:
        transport = streamable_http_client("http://127.0.0.1:3389/mcp", http_client=http)
        async with Client(transport) as client:
            tools = await client.list_tools()
            print([tool.name for tool in tools.tools])
            request_id = uuid4().hex  # 提交前保存 ID，便于响应丢失后查询。
            submitted = payload(await client.call_tool("submit_document_translation", {
                "request": {"path": "D:/inputs/example.txt", "request_id": request_id}
            }))
            job_id = submitted["job"]["id"]
            terminal = {"succeeded", "partial", "failed", "cancelled", "interrupted"}
            while True:
                job = payload(await client.call_tool("get_job", {"job_id": job_id}))["job"]
                print(job["state"], job["progress"])
                if job["state"] in terminal:
                    break
                await asyncio.sleep(1)

            final = payload(await client.call_tool("get_job", {
                "job_id": job_id, "include_result": True
            }))["job"]
            Path("ainiee-job-result.json").write_text(
                json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(final["state"], final.get("error"))


asyncio.run(main())
```

工具返回结构化数据和相同内容的文本；协议字段为 `structuredContent`、`isError`，官方 Python 客户端对应 `structured_content`、`is_error`。参数错误、未知任务、重复 ID 等工具调用错误使用 `isError=true`，结构为 `{error: {code, message}}`，参数校验不会回显提交的密钥值。

**工具成功与任务成功是两回事。** 提交成功表示已入队；`get_job` 成功也可能查询到 `state=failed`。必须检查 job 状态与错误，并保留 `partial/cancelled` 的有效结果。轮询默认摘要，只有确实需要完整模型时才设置 `include_result=true`，避免反复传输整份文档。

## 取消、断线与重启

调用 `cancel_job` 并传入目标 ID。排队任务直接取消；运行任务进入 `cancelling`，等待在途请求、文件保存和任务函数返回后才释放该队列。取消不会撤回已产生的模型费用或文件写入，应继续查询至终态。

断开 MCP 连接不会取消应用 Job。重新连接后用原 ID 查询；REST 的 `GET /api/jobs/{job_id}` 同样可查询 MCP 任务，完整结果位于 `job.result`。旧文档停止接口不会停止 MCP 发起的任务，应使用具体 job 的取消工具或 REST 取消接口。

Job 元信息、进度与结果仍保存在队列 SQLite 数据库；后端重启时未完成任务标为 `interrupted`，不会自动重放付费调用。恢复时检查已保存模型或阶段结果，再明确提交新任务。代理变更、任务内并发和单进程部署约束与 REST 完全一致，见 [任务队列说明](task_queues.md)。

## 验证

```powershell
python -X utf8 -m pytest Tests/test_mcp_http.py -q
```

测试通过官方 SDK 连接临时 TCP 端口上的实际 ASGI 应用，覆盖当前与 legacy 协议、工具发现、参数与错误、结果查询、Bearer 拒绝、REST/MCP 队列共享、取消和断线后继续执行。业务服务使用隔离替身，不连接收费接口、不访问真实用户配置，也不使用桌面后端的 3389 端口。

2026 年 11 月 3 日还完成了独立进程的真实文档流程验证：官方 SDK → MCP → Runtime 启动 → TXT 读取 → 批量翻译 → 文件写出，仅替换底层 `LLMRequester.sent_request`，未发起付费请求。两个条目的模型译文与输出文件内容均通过校验；重启后能查询同一 job 的持久结果，没有再次调用模型。该次本地报告位于 `Logs/validation/mcp-validation-20261103.json`（运行日志，不随源码分发）。
