# 图片与漫画翻译接口

图片复用中间模型 v2 和现有批量多线程翻译服务。桌面“接口管理 → OCR 接口”单独配置文字识别服务，与翻译和转录配置分开保存。首版接入百炼 Qwen-OCR 原生 DashScope HTTP API；桌面使用独立[图片预览工作区](media_workspaces.md)，所有图片操作进入 `image` 队列，同类依次执行，可与文档、音频任务并行。另有不经过 OCR 的[生图模型翻译流程](image_generation.md)。

OCR 及可选原文复核结束后，自动通过本地语言检测器补齐文字条目的 `lang_code` 和文件语言统计，再返回并保存结果；复用的 OCR 结果也会补齐缺失信息。此步骤不调用在线接口。检测失败时保留文字、坐标和用量，报告 `operation_errors` 并停止后续自动翻译；翻译入口仍兼容缺少语言信息的旧模型。

OCR 接口页管理连接名称、地址、密钥、协议、模型和超时；阅读顺序、合并相邻文字行及气泡原文复核位于“任务配置 → 图译设置”，修改后自动保存于全局 `image_translation_settings.ocr` 的 `reading_order`、`group_lines`、`refine_text`。任务设置独立于接口，可在尚未配置密钥时保存。

桌面翻译页以箭头连接“OCR 识别 → 文字翻译 → 译图回填”步骤，可单独勾选或组合执行。每次执行选中的识别、翻译步骤分别传入 `reocr=true`、`retranslate=true`，会重新处理已完成内容，不设单独重译开关。只需更新后续结果时应取消勾选前面步骤；程序不会隐式添加识别或翻译请求。后端分步接口的默认缓存复用与显式覆盖参数保持不变。

运行期按“接口保存值 → 全局图译识别设置 → 本次请求显式覆盖”的顺序合并。首次升级只将当前激活 OCR 接口的旧任务字段补入缺失的全局字段，无激活接口时采用默认值；已有全局设置和旧接口字段均保留。配置存储负责迁移落盘，运行期快照只读补全。手动构造的 `OCRConfig` 使用自身字段，不重新读取全局设置。

## 独立模块

- `domain/config/ocr_config.py`：解析独立 `ocr_platforms`、`active_ocr_platform`，不读取翻译密钥作为回退。
- `infrastructure/ocr/dashscope.py`：只负责图片请求、HTTP 错误和 OCR 响应解析，不依赖音频转录或桌面。
- `application/ocr_service.py`：源文件校验、坐标还原、阅读顺序、模型更新与逐页恢复。
- `infrastructure/images/`：图片读取、字体、文字像素遮罩和排版。
- `application/image_translation_service.py`：按阶段调用读取、OCR、现有翻译和导出服务。

接口默认地址为 `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`，模型为 `qwen-vl-ocr`，任务固定为 `advanced_recognition`，使用百炼 API Key。支持改为业务空间专属地址或其他提供相同响应协议的 Qwen-OCR 模型。接口会校验文字坐标；只有纯文本、截断输出或无效坐标时不会将其用于擦字。

参见[百炼 Qwen-OCR API 文档](https://help.aliyun.com/zh/model-studio/qwen-vl-ocr-api-reference)和[高精识别说明](https://help.aliyun.com/zh/model-studio/qwen-vl-ocr)。通用视觉聊天接口与该原生 OCR 接口不是同一协议。

## HTTP 接口

| POST 路径 | 输入 | 输出 |
| --- | --- | --- |
| `/api/v2/read/image` | `path`、`options.exclude_rule` | `status/model/report` |
| `/api/v2/ocr` | `model`、`config` | `status/model/report` |
| `/api/v2/translate` | `model`、现有翻译 `config` | `status/model/report` |
| `/api/v2/write/image` | `model`、`options` | `status/model/files/model_path/report` |
| `/api/v2/image/translate` | `path/read_options/ocr/translation/output` | 图片、中间模型、分阶段报告 |

这些接口与桌面共用 `image` 队列，繁忙时排队，默认同步等待排队与执行完成。发送 `Prefer: respond-async` 可取得 `202 {job}`，再查询进度和完整结果，详见 [任务队列](task_queues.md)。逐页 OCR 串行执行，翻译保留现有线程池，各任务独立使用模型额度。不会切换桌面当前文档项目。网络断开不会取消任务，调用方应查询既有 job 并保存返回模型，不自动重发全流程。

全流程示例：

```python
import json
from pathlib import Path
import httpx

with httpx.Client(base_url="http://127.0.0.1:3389", timeout=3600) as client:
    response = client.post("/api/v2/image/translate", json={
        "path": "D:/inputs/comic",
        "ocr": {
            "provider_id": "bailian_ocr", "reading_order": "manga_rtl", "group_lines": True,
            "model": "qwen3.5-ocr", "max_tokens": 16384, "refine_text": True,
        },
        "translation": {
            "provider_id": "deepseek", "source_language": "japanese",
            "target_language": "chinese_simplified",
        },
        "output": {
            "output_dir": "D:/outputs/comic", "format": "png",
            "save_model": True, "debug_overlay": True,
        },
    })
    response.raise_for_status()
    result = response.json()
    # HTTP 200 也可能是 partial、failed 或 cancelled。
    Path("last-image-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["status"], result.get("model_path"), result["files"])
```

启用后端鉴权时，另传 `Authorization: Bearer <AINIEE_API_TOKEN>`。

## 模型和坐标

支持静态 PNG、JPEG、WebP；目录按自然顺序读取。原图保持不变。读取时处理 EXIF 方向，公开的 `media_metadata.width/height` 和 `locator.polygon` 统一对应**EXIF 转正后的整张图片像素**。OCR 使用缩小副本时，坐标还原到该完整画布。

文件保留 `source_ref.path/sha256`。条目继续使用 `source_text`、`translated_text`、稳定 `item_id` 与 `locator.kind=image`；扩展信息放在 `extra`，无需升级模型版本。OCR 行框、排版区域和实际擦字遮罩分开保存。`extra.ocr.lines` 保存原始识别行及坐标，`extra.layout` 保存排版方向和区域等信息。模型只引用图片、遮罩等产物的路径和校验值，不保存图片 Base64、密钥或临时文件路径。

首版阅读顺序支持 `auto`、`ltr`、`manga_rtl`。日文漫画先根据连续边框识别漫画格，再按分隔带安排格与气泡顺序；气泡内部处理从右到左的竖列及上下分段。无法可靠判断漫画格时退回几何排序。`group_lines` 默认关闭，保留独立 OCR 行；开启时只合并明确位于同一封闭亮背景中的文字，排除大面积面板背景，并用气泡正文判断单个方形字的方向。它仍不是完整漫画气泡检测器，多栏漫画或跨气泡顺序应通过坐标预览复核。

真实漫画中，`qwen-vl-ocr` 的 4096 输出上限可能截断密集页面，坐标也可能错配；可按上述示例使用支持更长输出的 `qwen3.5-ocr`，配置页可直接修改模型。更换模型不能保证消除日语、手写字或拟声字的误识别。不要把纯文本多语言识别的结果直接当成坐标结果来擦字。

`refine_text` 默认关闭，需要同时开启 `group_lines`。开启后，对明确封闭且不会混入其他组文字的气泡，额外调用百炼 `multi_lan` 复核原文，保留首次高精识别的坐标及原始行。它会增加请求数；开放背景、无法可靠判断的区域仍需校对。模型保存每个气泡的复核状态与原始识别文本，成功且原文改变时才清除该项旧译文。传入已识别模型再次调用 `/ocr`，可复用基础 OCR 并继续尚未完成的复核，无需重新识别整页。

纯文本复核也可能漏列或颠倒列序，因此回复还需通过完整性校验：仅在能与原始 OCR 行建立可靠一一对应时采用，并按已有坐标的行序重排。缺列、重复、歧义或明显缩水会返回 `OCR_REFINE_REJECTED`、计入 `report.refinement.rejected` 并使状态为 `partial`，同时保留原文和译文。被拒的服务原始回复保存在 `provider_text` 中，校验结果保存在 `validation` 中；重复调用会复用这些结果，不会因质量拒绝自动反复收费。旧的未校验缓存可在本地重新校验。此校验不能保证每个字符正确，复核结果仍应对照原图检查。

## 导出与恢复

默认导出 PNG，支持 JPEG、WebP；`save_model` 默认为 `true`。最终模型为输出目录下的 `{project_id}_image_model.json`；遮罩与可选预览放在 `_image_assets/{project_id}/`。全流程还会把读取、OCR、翻译阶段模型分别保存到 `.ainiee/checkpoints/{project_id}/`；OCR 页与气泡复核完成后更新 `ocr-progress.json`，响应中的 `report.checkpoints` 提供完整路径。

桌面图片格式由“图译设置 → 导出设置”保存于 `image_translation_settings.export.format`。工作区只通过顶部“导出结果”选择目录并读取最新格式，处理完成后不自动导出；这不影响 `/image/translate` 等后端全流程接口自身的写出步骤。

失败后用最近的模型调用相应分步接口。例如 OCR 完成但翻译失败时，只重试 `/translate`；导出失败或调整译文后，只调用 `/write/image`。重复 OCR 默认复用已完成且源文件、识别配置匹配的页；`reocr=true` 明确重新识别。重新 OCR 成功后才替换该页原文并清除旧译文。无文字页也有完成标记，避免反复付费。

`/image/translate` 每次从路径建立新模型，重新调用会重新 OCR。恢复时应加载返回的 `model` 或 `model_path`，再调用分步接口。OCR 的原文仍可能误识别，尤其是竖排、标点和艺术字；可在中间模型中校对原文、重新翻译，再导出图片。

输出支持字体路径、字号上下限、文字颜色、内边距与横竖排。未翻译、缺字或无法容纳的条目保留原文并报告，不先擦掉原文再丢弃译文。源文件变化、输出覆盖源文件和目标冲突会被拒绝。默认不覆盖已有输出；重新导出到相同目标需明确 `overwrite=true`。

原译文相同的区域保留原画字形，计入 `preserved_items`，不会仅因此降低成功状态。明显重叠的 OCR 行、封闭气泡内疑似遗漏的独立文字，以及与线稿连通的遮罩会保留原区域并返回复核告警。翻译批次在回复结构与序号可靠时逐项检查，保留通过项，只重试或报告失败项；结构错位仍整批拒绝，避免错误译文对应到气泡。

明确封闭的气泡使用填孔后的内部区域约束排版，避免矩形框跨出连通气泡而覆盖人物。竖排会重排 OCR 列换行、对齐各列顶部，将 Latin 单词整体侧转，并处理常见竖排标点；艺术字和复杂版式仍不等同于人工嵌字效果。

`erase_mode=auto` 优先处理纯色气泡与简单背景，生成文字像素遮罩而非直接涂白整个 OCR 矩形。复杂网点、艺术字、插画上的文字可能被保守跳过并产生 `partial`；可人工调整区域或显式选择 `inpaint` 后复核。首版不承诺复杂漫画背景无痕修复。

图片后端使用 Pillow、OpenCV 和 FreeType。OpenCV 使用与 RapidOCR 一致的 `opencv-python`，不要另行同时安装 headless 版本。建议明确指定有目标语言字形的字体；后端无可用字体时会报错，字体文件不随中间模型嵌入。透明图片推荐 PNG/WebP，JPEG 不支持透明通道。
