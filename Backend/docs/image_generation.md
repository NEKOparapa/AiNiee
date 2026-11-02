# 生图模型翻译图片

这是与 OCR 翻译并列的图片流程：读取图片 → 图像编辑模型翻译并生成整张图片 → 对照预览 → 导出图片与中间模型。支持百炼 DashScope（默认模型 `qwen-image-3.0-pro`）和火山方舟 Seedream 5.0 pro 原生图片生成协议。本流程不调用 OCR 或 DeepSeek，也不自动生成逐条原文、译文；原有 OCR → 文本翻译 → 擦字回填流程继续保留。

当前效果仍需人工检查，尤其是文字准确性、漏译、气泡对应和人物线稿变化。HTTP 成功只代表产物生成成功，不代表文字已逐字校验。

## 桌面入口

1. 在“接口管理 → 生图接口”填写独立 API Key，保存并激活配置。接口页设置名称、地址、协议、模型与超时；“任务配置 → 图译设置”可调整输出尺寸、自动改写提示词和导出格式，修改后自动保存。首次配置不会从 OCR 或翻译接口复制密钥。
2. 在“图片翻译”导入图片、目录或 ZIP，选择“图像模型直接翻译”，设置源语言与目标语言，勾选“生成译图”并执行。
3. 在校润页对照原图检查生成结果，通过顶部“导出结果”选择目录。PNG、JPEG 或 WebP 格式取自图译设置的 `image_translation_settings.export.format`，中间模型随导出保存；生成完成后不自动导出。

桌面固定使用 `text_mode=direct`，由图像模型翻译整张图片，不提供 `direct/specified` 切换或补充要求输入。每次执行生成步骤都会明确传入 `regenerate=true`，重新处理已完成图片，可能再次计费；界面不再提供单独的重新生成开关。后端/API 继续支持 `text_mode=specified`、`replacements`、`prompt` 和按已有结果恢复的用法，参数没有弃用。

OCR 与生图流程分别保留预览；生图语言保存于 `project.extra.image_generation_options`，不修改 OCR 流程的 `translation_context`。通过桌面修改生图语言，或通过 API 修改补充要求、文字模式及指定模式下的条目后，旧译图失效，需要重新生成。

## 独立服务

| 模块 | 职责 |
| --- | --- |
| `domain/config/image_generation_config.py` | 独立接口选择、配置快照与校验 |
| `infrastructure/image_generation/dashscope.py` | 发出一次生成请求、解析响应、独立下载结果 |
| `infrastructure/image_generation/volcengine_ark.py` | 火山方舟原生单图编辑请求与响应解析 |
| `infrastructure/image_generation/client.py` | 按接口格式选择适配器，复用下载与恢复流程 |
| `infrastructure/image_generation/prompts.py` | 图片规范化、尺寸、提示词与输入指纹 |
| `application/image_generation_service.py` | 模型输入输出、逐页生成、恢复与停止 |
| `application/generated_image_write_service.py` | 验证产物、转换格式、正式导出与模型保存 |
| `application/image_generation_pipeline_service.py` | 串行读取、生成、导出编排及模型检查点 |

配置使用 `image_generation_platforms` 与 `active_image_generation_platform`，默认配置 ID 为 `bailian_image`。请求可指定 `provider_id` 或覆盖接口字段，密钥不会保存进中间模型。

全局生成任务参数保存于 `image_translation_settings.generation`：`size`、`seed`、`prompt_extend`、`prompt`、`watermark`。优先级从低到高为接口保存值、全局图译生成设置、本次请求的显式覆盖；显式 `seed: null` 表示随机种子。任务配置保存只校验这些参数，不要求存在接口密钥。

图译设置页不提供随机种子、全局补充要求或水印控件，图片工作区也不提供补充要求输入。这些字段的已有值继续保留，后端/API 仍支持读取和覆盖；修改页面中的其他设置不会将它们重置。

首次升级在合并默认值之前，将当前激活生图接口的旧任务值补入缺失的全局字段；无激活接口时使用默认值。已有全局字段不变，旧接口字段保留兼容。配置读取、保存和初始化负责迁移落盘，运行期快照只读补全；手动构造 `ImageGenerationConfig` 仍使用对象自身值。

## 火山方舟 Seedream 5.0 pro

接口格式选择 `VolcengineArk`，地址填写 `https://ark.cn-beijing.volces.com/api/v3/images/generations`，模型填写 `doubao-seedream-5-0-pro-260628`，使用方舟 API Key。模型 ID 已按 [Seedream 5.0 pro 官方教程](https://docs.volcengine.com/docs/ark/seedream-5-0-pro?lang=en)核实。

适配器将每张原图作为 PNG data URL 提交一次，要求返回单张 PNG 的 HTTPS 下载地址。输入像素和比例、输出尺寸遵循[火山方舟图片生成 API](https://docs.volcengine.com/docs/ark/image-generation-api?lang=zh&redirect=1)：

- 输入宽高大于 14，总像素不超过 3600 万，宽高比不超过 16，规范化后的 PNG 不超过 30 MiB。
- 输出支持 `1K`、`1.5K`、`2K` 或明确的 `宽*高` / `宽x高`；明确尺寸总像素为 921600–4624220，宽高比不超过 16。应用的 `auto` 会根据原图比例计算合法尺寸，再以 `宽x高` 提交，不向普通生成接口传 `auto`。
- 使用 `optimize_prompt_options.mode=standard`。官方协议未列出 DashScope 的 `seed` / `prompt_extend`，因此不透传；遗留非空种子或关闭自动改写时，任务报告会提示这两个设置未应用。更改这些无效参数不会改变 Ark 输入指纹。
- 请求不开启流式、组图或图层拆分，保持一页对应一个付费生成结果。官方结果链接有效期为 24 小时，收到结果后立即保存检查点并下载；链接过期不能靠重新下载恢复，需要显式重新生成。

两种协议共用相同的 `unknown` 状态、下载恢复、停止、缓存校验和导出逻辑。适配器不会自动重发付费 POST，也不会携带接口密钥下载生成图片。

## HTTP 接口

| POST 路径 | 输入 | 输出 |
| --- | --- | --- |
| `/api/v2/read/image` | `path`、`options` | 复用图片读取，输出中间模型 |
| `/api/v2/image/generate-translation` | `model`、`config`、可选 `operation_id` | 更新后的模型、检查点路径、报告 |
| `/api/v2/write/generated-image` | `model`、`options` | 导出图片、中间模型、报告 |
| `/api/v2/image/generate-pipeline` | `path`、`read_options`、`generation`、`output`、可选 `operation_id` | 串行全流程结果 |
| `/api/v2/image/operations/{operation_id}/stop` | 无请求体 | 请求取消匹配的在途操作 |

这些接口同步等待，与其他业务共用顶层互斥，忙碌时返回 `409 BACKEND_BUSY`。逐页串行处理，不创建并行 Job。启用鉴权时使用 `Authorization: Bearer <AINIEE_API_TOKEN>`。

已在桌面配置生图接口后，可以这样调用：

```python
import json
from pathlib import Path
from uuid import uuid4
import httpx

with httpx.Client(base_url="http://127.0.0.1:3389", timeout=3600) as client:
    response = client.post("/api/v2/image/generate-pipeline", json={
        "path": "D:/inputs/comic",
        "operation_id": uuid4().hex,
        "generation": {
            "provider_id": "bailian_image",
            "source_language": "japanese",
            "target_language": "chinese_simplified",
            "text_mode": "direct",
            "prompt": "保留原有竖排布局。",
        },
        "output": {
            "output_dir": "D:/outputs/comic-generated",
            "format": "png", "save_model": True,
        },
    })
    response.raise_for_status()
    result = response.json()
    Path("generation-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["status"], result.get("model_path"), result["files"])
```

全流程 `path` 接收图片或目录；ZIP、多输入和桌面预览使用[媒体工作区接口](media_workspaces.md)。HTTP 200 的业务状态仍可能为 `partial`、`failed` 或 `cancelled`，需要检查 `status` 与 `report`。

指定替换文本时，将 `config.text_mode` 设为 `specified`。省略 `replacements` 会使用模型中的 `items`；也可以提供以下清单，只处理各图片对应的条目：

```json
{
  "text_mode": "specified",
  "replacements": [
    {
      "file_id": "读取接口返回的文件ID",
      "source_text": "ありがとう",
      "target_text": "谢谢",
      "location": "右上角气泡"
    }
  ]
}
```

`file_id` 必填。指定模式要求模型逐字使用译文，但生成模型仍可能错字或改写；这不是确定性的文字排版器。

## 中间模型、恢复与停止

沿用中间模型 v2；源路径与源 SHA256 保持不变。每个文件在 `extra.image_generation` 保存输入指纹、设置、请求 ID、用量、状态及产物路径 / SHA256 / 尺寸。完整图片保存在项目缓存的 `ImageGeneration/{project_id}/{file_id}/`，不嵌入模型 Base64。生成尺寸可能因接口约束与原图略有差异。

分步生成与全流程在 `ImageGeneration/{project_id}/progress-model.json` 保存模型检查点；工作区调用另外逐页保存工作区模型。正式导出默认保存 `{project_id}_image_model.json`，其中仍有本机源文件、缓存产物路径引用，迁移到其他机器需一并迁移文件，不是自包含归档。

- 输入与配置指纹相同时，已完成且通过校验的产物直接复用。
- 请求成功后先保存下载地址，再下载图片。`generated_pending_download` / `download_failed` 重新调用只恢复下载，不重复提交生图请求。
- 超时或服务异常导致是否收费不明时，状态为 `unknown`；崩溃遗留的 `request_in_flight` 也不会自动重发。确认需要再次生成后，显式传 `regenerate=true`，可能再次计费。
- 停止采用协作取消：保存当前在途页的有效结果后，不再开始下一页。停止不等于撤销已经提交的请求。
- 导出失败时只调用 `/write/generated-image`。不应重新调用从路径读取的全流程；该入口会建立新的项目。恢复应使用已有 `model` / `model_path` 调用分步生成接口。

工作区的 `stage=generate` 直接调用此服务，空 `items` 也能生成并预览。`stage=export` 可用 `options.mode="generation"` 选择直接导出生图产物，`"ocr"` 选择原有排版导出。默认使用模型中的 `extra.image_translation_mode`。两套译图索引独立保存。

输出默认不覆盖已有文件，需显式 `overwrite=true` 才可覆盖目标。禁止覆盖源图与生成缓存。PNG 直接导出已验证的缓存图片；WebP 为无损编码，JPEG 会用白底处理透明区域。导出不再次生成，也不调用 OCR 擦字或字体排版。

验证命令：`python Tests/run_all.py`。测试覆盖请求协议、无重复提交恢复、逐页停止、模型与预览保存、指定文字、配置隔离和桌面模式切换；自动测试使用模拟服务，不产生在线调用费用。
