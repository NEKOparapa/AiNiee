# 三类任务队列与 Job API

后端固定提供 `document`、`image`、`audio` 三个队列，每个队列一个执行线程。同类型任务按提交顺序执行（FIFO），不同类型最多同时运行三个顶层任务。一个队列按类型共享，不会为每个项目额外创建队列。例如，图片 OCR 会等待前面的图片翻译完成，但不会等待文档翻译或音频转录。

单个任务内部仍使用已有翻译线程池或音频切片并发设置。三个任务的模型额度和限流器相互独立，不合并 RPM 配额；因此“三个顶层任务”不等于“最多三个模型请求”。

## 入队范围与类型

| 队列 | 主要操作 |
| --- | --- |
| `document` | 文档/PDF 读取、文档翻译与写出，桌面当前文档的加载、缓存修改、保存、分析、表格处理、检查和导出 |
| `image` | 图片读取、OCR、图片模型翻译、擦字回填、生图翻译、图片工作区导入/处理/保存/删除 |
| `audio` | 音频读取、转录、音频模型翻译、字幕写出、音频工作区导入/处理/保存/删除 |

`POST /api/v2/translate` 根据中间模型类型选择队列；媒体工作区根据已保存的 `kind` 选择队列。文档、图片、音频混合在同一模型时返回 `422 MIXED_PROJECT_KINDS`，类型与专用接口不符时返回 `422 INVALID_PROJECT_KIND`。一个完整图片或音频流程占一个 Job，内部步骤直接调用服务，不重复入队。

配置读取/更新、健康与状态查询、任务与队列查询、项目/历史/媒体预览等只读请求，以及取消请求直接处理，不等待业务队列。忙碌本身不再触发 `409 BACKEND_BUSY`。项目切换、旧版本覆盖、重复任务 ID 等真实冲突仍可能返回 409。

PDF 读取入口为 `POST /api/v2/read/document`，默认 `AutoType` 自动识别 PDF，页范围使用 `options.pages`，详见 [统一中间模型接口](../README.md#统一中间模型接口)。

## 同步兼容与异步提交

现有 `/api/v2` 业务接口默认创建 Job 并同步等待，等待时间包含排队时间。成功返回的结构不变，例如读取/翻译为 `{status, model, report}`，媒体阶段为 `{status, workspace, report, files}`。HTTP 200 不保证业务全部成功，仍需检查 `status` 和报告。

在这些业务请求中增加 `Prefer: respond-async`，后端接受后返回：

```http
HTTP/1.1 202 Accepted
Preference-Applied: respond-async
Location: /api/jobs/生成的任务ID
Content-Type: application/json
```

响应为 `{"job": <任务记录>}`。任务记录中的 `id` 与 `job_id` 相同；接受响应中的状态可能已从 `queued` 进入 `running`，较短任务也可能已经完成。202 只表示请求已接受，执行期间发现的错误由 job 的 `state/error/result` 表示。

大部分接口自动生成 job ID。媒体 `POST /api/v2/media/{workspace_id}/run` 必须提供 `operation_id`，生图处理接口也允许提供该字段；这些接口直接将它作为 job ID。不要给未声明该字段的文档接口额外传 `operation_id`。重复提交已存在的 ID 返回 `409 DUPLICATE_JOB_ID`，不会自动重放任务，也不会将重复 POST 当作查询。

桌面文档长任务（如 `/api/tasks/translation`、分析、表格处理和 `/api/project/export`）保留原有 202 行为：响应为原状态字段加 `job_id`、`job`，并继续发送完成通知。`/api/project/save` 等旧同步接口入队后仍等待完成再返回。配置和停止接口不使用 `Prefer` 入队。

## 查询、结果与取消

启用鉴权时，下列接口和业务请求都需要 `Authorization: Bearer <AINIEE_API_TOKEN>`。

| 请求 | 响应与用途 |
| --- | --- |
| `GET /api/jobs?lane=image&limit=50` | `{jobs: [...]}`；`lane` 可省略，`limit` 默认 50、范围 1–200。按新任务在前排列，列表不包含完整 `result` |
| `GET /api/jobs/{job_id}` | `{job: {...}}`；包含进度、完整结果与错误，任务不存在返回 404 |
| `POST /api/jobs/{job_id}/cancel` | 无请求体；返回 `{job: {...}}`，取消指定任务 |
| `GET /api/queues` | `{queues: {document: ..., image: ..., audio: ...}}`；每类包含 `running`（任务记录或 `null`）和 `queued`（待执行记录数组） |

任务记录包含 `id/job_id`、`lane`、`name`、`source`、`project_id`、`state`、`progress`、`result`、`error` 以及创建、开始、结束和更新时间。`progress` 由业务决定，例如翻译行数、音频切片数或图片页数，不保证所有任务都有相同字段。媒体阶段的进度还包含 `workspace_id` 和 `stage`。

| `state` | 含义 |
| --- | --- |
| `queued` | 等待同类前序任务完成 |
| `running` | 正在执行 |
| `cancelling` | 已收到停止信号，仍在等待实际执行和保存收尾 |
| `succeeded` | 执行成功，业务返回值位于 `result` |
| `partial` | 部分完成，检查 `result.report` 并保留有效结果 |
| `failed` | 执行失败，检查 `error` 和可能存在的 `result` |
| `cancelled` | 已取消，运行后取消时可能仍有部分结果 |
| `interrupted` | 上次后端退出前未完成，没有自动恢复执行 |

取消排队任务会立即将其标为 `cancelled`，不会进入业务函数。取消运行任务使用协作信号，停止提交新的批次或页，并等已发出的请求、结果保存和任务函数收尾后才释放队列。读取、检查和部分写出不会在函数内部中断，不能把取消响应视为执行已经停止。对已结束任务再次取消只返回已有记录。

旧 `POST /api/tasks/stop` 只选择文档队列中桌面发起的当前任务，或首个排队任务，不影响图片、音频和外部模型调用。已有媒体/生图 `.../operations/{operation_id}/stop` 按 ID 控制模型接口调用。需要明确指定目标时使用通用 job 取消接口。

下面示例异步读取文档，轮询同一个 job，并保存完整结果。路径属于后端机器；如需停止，可发送注释中的取消请求，然后继续查询终态。

```python
import json
import os
from pathlib import Path
import time

import httpx

headers = {}
if token := os.environ.get("AINIEE_API_TOKEN"):
    headers["Authorization"] = f"Bearer {token}"

terminal = {"succeeded", "partial", "failed", "cancelled", "interrupted"}
with httpx.Client(base_url="http://127.0.0.1:3389", headers=headers, timeout=30) as client:
    response = client.post(
        "/api/v2/read/document",
        headers={"Prefer": "respond-async"},
        json={"path": "D:/inputs/example.pdf", "options": {"pages": "1-3"}},
    )
    response.raise_for_status()
    job = response.json()["job"]
    job_id = job["id"]  # 保存此 ID，断线后仍查询同一个任务。
    print("job:", job_id, "lane:", job["lane"])

    # 停止指定任务：
    # client.post(f"/api/jobs/{job_id}/cancel").raise_for_status()

    while job["state"] not in terminal:
        time.sleep(1)
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()["job"]
        print(job["state"], job["progress"])

    if job.get("result") is not None:
        Path("job-result.json").write_text(
            json.dumps(job["result"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print("final:", job["state"], job.get("error"))
```

断线或同步 HTTP 等待被取消不会取消已接受的任务。已经拿到 ID 时继续查询，不自动重发整次翻译、转录或生图流程。若接受响应丢失而未取得 ID，可先检查任务列表；不能仅凭网络错误判断付费调用未执行。

## 配置快照、状态与工作区版本

任务提交时深拷贝后端实际配置；排队期间或执行过程中修改接口、语言、线程数、提示词等，不会改变已经提交的任务。请求中的显式覆盖仍优先于该快照。任务内部读取配置使用隔离上下文，配置 API 始终查询和修改真实持久配置；自动规范化任务配置不会将旧快照写回配置文件。

代理是进程级网络设置：修改后立即落盘，但直到三个队列都没有运行或排队任务时才切换代理，并关闭旧缓存客户端。在此之前，新旧排队任务都使用当前已应用的代理。`GET /api/status` 的 `network_settings_pending: true` 表示仍有代理变更待应用，不能仅凭配置保存成功认定连接已切换。

`GET /api/status` 中兼容文档桌面的 `busy`、`app_status`、`work_status_code` 和 `operation` 只表示文档队列。`any_busy` 表示任意队列是否有任务，`queues` 是三个队列的快照。图片、音频页面分别查询自己 operation ID 对应的 job；排队显示等待前序同类任务，运行后使用该 job 的进度。WebSocket 新增 `type: "job"` 消息，推送元信息和进度，完整结果仍通过单任务查询获取。

媒体公共保存与处理共享同类队列。保存请求记录提交时的工作区版本；等待期间工作区被前一个任务更新后，保存会以 `MEDIA_WORKSPACE_CHANGED` 失败，默认同步调用返回 HTTP 409，异步调用的 job 记录对应错误。应重新加载并确认要保留的修改，再提交保存，避免旧模型覆盖新的识别或翻译结果。

## 持久化与部署

Job 元信息、进度和结果保存到 `cache_root()/tasks.sqlite3`，`AINIEE_CACHE_DIR` 可指定缓存根目录。任务配置快照、执行函数和队列运行对象保留在当前进程内，不作为可恢复执行指令写入数据库。重启时，未结束的 `queued/running/cancelling` 任务统一标为 `interrupted`，不会自动重复付费请求。已结束任务仍可查询结果；恢复业务时先检查项目缓存或阶段模型，再由调用方明确提交新任务。

此调度器按单后端进程部署，使用一个 Uvicorn worker。三个业务队列已提供跨类型并发，不能启动多个 worker 共享该 SQLite 文件和项目缓存，也不要在运行任务时使用自动重载。数据库记录用于查询与故障辨识，不提供分布式抢占、自动重试、跨进程任务恢复或请求去重重放。
