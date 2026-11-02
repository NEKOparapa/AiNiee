# 音频转录、翻译与字幕接口

接口按“读取 → 转录 → 翻译 → 字幕写出”串行执行，翻译阶段复用现有多线程批量翻译服务。可以逐步调用，也可以一次调用 `POST /api/v2/audio/translate`。整个流程只占用一个顶层操作，不创建 Job，不改变桌面当前项目。

桌面“接口管理”下有“翻译接口”和“转录接口”。翻译接口沿用原设置；转录接口单独保存多个服务配置，并选择当前使用的服务。“任务配置 → 音译设置”展示说话人分离、切片时长、并发数及字幕导出格式和内容，修改后自动保存。

## 配置与环境

转录配置保存在 `transcription_platforms` 和 `active_transcription_platform`，与翻译的 `platforms`、接口绑定分别管理。默认提供阿里云百炼配置，密钥默认为空。请在转录接口页填写自己的密钥。API 调用可用 `config.provider_id` 选择已保存服务，也可通过本次调用覆盖配置；覆盖不回写设置。

接口页管理名称、地址、密钥、协议、模型和请求超时；火山豆包另有资源 ID 和可选的旧版应用 ID。任务参数保存于全局 `audio_translation_settings`：`language_hints`、`speaker_diarization_enabled`、`chunk_duration_seconds`、`chunk_overlap_seconds`、`chunk_concurrency`、`vad_threshold`。这些设置按所选协议的能力应用；保存任务设置不要求先填写 API Key。

桌面音译设置不提供语言提示、切片重叠时长或 VAD 阈值控件；已有配置值保持不变，仍可通过配置/API 使用这些参数。

桌面导出选项保存为 `audio_translation_settings.export`，默认 `{ "format": "srt", "mode": "bilingual" }`。格式支持 `srt/vtt/ass/lrc`，内容支持 `bilingual/translated/source`；点击工作区顶部“导出结果”时读取最新设置并选择输出目录，处理完成后不自动导出。

配置优先级从低到高为接口保存值、全局音译设置、本次请求的显式覆盖。首次升级在合并默认配置之前，将当前激活转录接口的旧任务字段补入全局设置；没有激活接口时使用默认值。已有全局字段不会被覆盖，旧接口字段保留用于兼容。配置读取和保存会将迁移结果写入配置文件；运行期快照只读补全，手动构造 `TranscriptionConfig` 仍按对象自身值执行。

百炼 DashScope 使用原生语音识别 HTTP API，默认模型 `qwen-audio-3.1-asr-flash`，默认请求地址：

```text
https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

该地址与 OpenAI 兼容的聊天接口地址不同。新工作空间可按百炼控制台说明配置工作空间专用地址；密钥、模型与地域需匹配。协议及请求字段见[百炼语音识别 HTTP 文档](https://help.aliyun.com/zh/model-studio/qwen-audio-asr-http-api)。

读取 MP3 等格式需要后端机器可执行 `ffprobe`（安装 FFmpeg 并加入 PATH）；PCM WAV 在缺少 ffprobe 时可用 Python 标准库读取。输入是后端可访问的本地文件或目录，目录递归读取，`exclude_rule` 为逗号分隔的文件匹配规则。不会在中间模型中保存音频 Base64 或密钥。

`qwen-audio-3.1-asr-flash` 单次请求音频最长 5 分钟。超过 5 分钟的本地音频会自动通过 VAD 选择切点，分片批量转录后恢复原始时间轴。长音频需要后端可用的 FFmpeg；每个提交给百炼的切片仍不超过接口上限。模型限制见[百炼语音识别模型列表](https://help.aliyun.com/zh/model-studio/asr-model)。

## 火山豆包（极速）

火山豆包转录使用 `VolcengineASRFast` 协议，将本地音频以 Base64 提交，一次请求返回识别结果。地址为 `https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash`，模型名称为 `bigmodel`，资源 ID 为 `volc.bigasr.auc_turbo`。

新版控制台填写 `api_key`，发送 `X-Api-Key`；旧版填写 `app_id` 和对应的 Access Token（保存在 `api_key`），发送 `X-Api-App-Key` 与 `X-Api-Access-Key`。资源 ID 保存为 `resource_id`。参见[极速版协议](https://docs.volcengine.com/docs/doubao-voice/large-model-recording-file-lite-recognition-api?lang=zh)和[旧版鉴权说明](https://docs.volcengine.com/docs/doubao-voice/old-version-console-authentication-reference-example?lang=zh)。

官方单次限制为 100 MB、2 小时，支持 WAV、MP3、OGG OPUS。本地超过 5 分钟的音频继续复用现有 VAD 切片与恢复流程；短音频格式不直接受支持或文件过大时也先通过 FFmpeg 转成有界 WAV 切片。每片按极速版协议提交。接口不自动重发失败的 POST，避免网络中断后重复扣量；`max_retries` 不会开启火山音频提交重试。官方按音频时长计费，参见[计费概述](https://docs.volcengine.com/docs/doubao-voice/billing-overview?lang=zh)。

请求开启 `show_utterances`，将分句毫秒时间和 `additions.speaker` 转成统一字幕条目。火山仅支持单一语言提示。历史全局多选或不受支持的提示会退回服务默认识别，并在报告中说明；本次 API 显式传入不受支持的提示会被拒绝。指定非中文语种时，接口不支持说话人分离，本次只识别文本并返回提示。百炼特有的 `keep_dialect` 不发送给火山；协议固定为 HTTP JSON，已有 `stream` 设置不会把火山调用改成 SSE。

桌面工作区以箭头连接“转录字幕”和“翻译字幕”步骤，可分别勾选执行。每次执行选中的转录步骤都会发送 `retranscribe: true`，选中的翻译步骤发送 `retranslate: true`，重新处理已完成内容，不再提供独立重译开关；重复转录会重新发送音频并可能再次计费。只需翻译已有字幕时取消勾选转录。API 的默认复用行为不变：通过 `/api/v2/transcribe` 或 `/api/v2/media/{workspace_id}/run` 传入已有模型并设置 `retranscribe: false`，仍可跳过完整结果或恢复未完成切片。

## 分步调用

```python
import os
import json
from pathlib import Path
import httpx

headers = {}
if token := os.environ.get("AINIEE_API_TOKEN"):
    headers["Authorization"] = f"Bearer {token}"

def call(client, operation, payload):
    response = client.post(f"/api/v2/{operation}", json=payload)
    response.raise_for_status()
    result = response.json()
    # HTTP 200 仍可能是 partial、failed 或 cancelled；请保存中间结果。
    if "model" in result:
        Path("audio-checkpoint.json").write_text(
            json.dumps(result["model"], ensure_ascii=False, indent=2), encoding="utf-8")
    if result["status"] != "success":
        raise RuntimeError(result["report"])
    return result

with httpx.Client(base_url="http://127.0.0.1:3389", headers=headers,
                  timeout=httpx.Timeout(3600, connect=10)) as client:
    model = call(client, "read/audio", {"path": "D:/inputs/speech.mp3"})["model"]
    model = call(client, "transcribe", {
        "model": model,
        "config": {"provider_id": "bailian_asr", "language_hints": ["en"]},
    })["model"]
    model = call(client, "translate", {
        "model": model,
        "config": {"provider_id": "deepseek", "source_language": "english",
                   "target_language": "chinese_simplified"},
    })["model"]
    result = call(client, "write/subtitles", {
        "model": model,
        "options": {"output_dir": "D:/outputs", "format": "srt", "mode": "bilingual"},
    })
    print(result["files"])
```

读取响应中，每个文件的 `media_type` 为 `audio`，`source_ref` 保存绝对路径和 SHA256，`media_metadata` 保存时长、采样率、声道等元信息；初始 `items` 为空。

转录前验证源文件指纹。转录结果写入条目的 `source_text`，`locator` 为 `{kind: "audio", index, start_ms, end_ms, speaker_id?}`，时间统一为毫秒。只处理音频文件，其他文件保持不变；有原文的音频默认跳过，显式 `retranscribe: true` 才重新识别。重转录成功后清除该文件的旧译文，失败时保留原内容。批量处理逐文件保留成功结果，报告包含失败文件。

百炼默认使用 SSE 收集最终句子及时间戳，火山使用各自的 JSON 响应，均保留服务器提供的说话人标签。若响应只有全文而没有分句时间轴，使用整段音频时长输出一个条目并在报告中说明降级，不把全文错误地绑定到最后一句的时间戳。

转录覆盖项包括 `provider_id`、`api_url`、`api_key`、`app_id`、`resource_id`、`model`、`api_format`（`DashScope`、`VolcengineASRFast`）、`request_timeout`、`language_hints`、`speaker_diarization_enabled`、`keep_dialect`、`stream`、`max_retries`、`retranscribe`。详细类型及默认值以运行中的 `/docs` 和配置页为准。

## 一次执行全流程

向 `POST /api/v2/audio/translate` 发送：

```json
{
  "path": "D:/inputs/speech.mp3",
  "read_options": {"exclude_rule": "*_backup.*"},
  "transcription": {"provider_id": "bailian_asr", "language_hints": ["en"]},
  "translation": {
    "provider_id": "deepseek",
    "source_language": "english",
    "target_language": "chinese_simplified",
    "user_thread_counts": 4
  },
  "output": {"output_dir": "D:/outputs", "format": "srt", "mode": "bilingual"}
}
```

响应包含 `status`、`model`、`files`、`report`，报告按 `read/transcription/translation/write` 列出结果。配置与输出路径先校验；后续阶段失败会返回最近可用的模型。比如字幕写出失败后，修正输出设置并调用 `/write/subtitles` 即可，无需重新转录或翻译。调用方应保存返回模型。

业务状态 `partial` 表示有部分文件或条目未完成，不能只看 HTTP 200。执行前的非法配置、读取失败或请求结构错误返回非 2xx；转录阶段的逐文件错误（例如源文件变化或切片请求失败）进入 HTTP 200 响应的 `failed/partial` 报告。与其他桌面/API 操作冲突时返回 `409 BACKEND_BUSY`。

转录默认不自动重试。显式设置 `max_retries` 可重试部分临时错误，但服务端可能已处理请求，重试可能再次计费；已收到识别事件后断流不会自动重发。保存中间模型可以复用已经返回的成果，并不保证第三方请求只执行一次。

## 长音频与分片恢复

长音频先由 FFmpeg 解码为 16 kHz 单声道 PCM，再用随项目提供的 [Silero VAD](https://github.com/snakers4/silero-vad) ONNX 模型寻找语音停顿。VAD 只选择切点，不删除音频区间；即使轻声未被检出，整段音频仍会覆盖在切片中。连续讲话没有合适停顿时使用有重叠的强制切点。

切片核心区间连续覆盖整段录音，相邻请求额外携带边界上下文。合并时将局部时间加上切片起点，利用核心区间归属、重叠区词时间和文本对齐去重。不会因为远处出现相同台词就删除真实重复发言。无法可靠判断的边界保守保留并返回警告；在线识别本身可能出现错字或漏识别，不能保证绝对逐字无误。

下列配置可放在 `/transcribe` 的 `config` 或 `/audio/translate` 的 `transcription` 中：

| 字段 | 默认值与范围 | 用途 |
| --- | --- | --- |
| `chunk_duration_seconds` | 240，整数 30–290 | 每片目标核心长度，实际边界按附近停顿调整 |
| `chunk_overlap_seconds` | 2，0.5–5 | 每片两侧额外上下文长度；与核心合计不超过 300 秒 |
| `chunk_concurrency` | 3，整数 1–8 | 每个文件同时在途的转录请求数 |
| `vad_threshold` | 0.35，0.01–0.99 | VAD 语音概率阈值，较低值更倾向把轻声视为语音 |

例如，向 `/transcribe` 传入完整的 `model`，并使用以下 `config`：

```json
{
  "provider_id": "bailian_asr",
  "language_hints": ["ja"],
  "chunk_duration_seconds": 240,
  "chunk_overlap_seconds": 2,
  "chunk_concurrency": 3
}
```

桌面“任务配置 → 音译设置”可调整切片目标长度和并发数，并自动保存；重叠时长与 VAD 阈值继续沿用已保存配置或本次 API 覆盖。顶层流程仍然串行、仍只允许一个活动操作；并发仅发生在当前文件的切片请求中，不创建 Job。取消后停止提交新片，并等待已经发出的请求结束。

所有切片成功且源文件复验通过后，才原子替换该音频的字幕条目。请求失败或取消时，已成功片的纯文本和时间结果保存在返回模型的文件 `extra.transcription_checkpoint`，不会存储音频内容、密钥或临时路径。保存这个模型，使用 `retranscribe: false` 再调用 `/transcribe`，即可只请求缺失片。恢复时会核对源文件、模型、接口地址及相关切片/识别参数；这些参数变化或显式重转录会重新识别。不要用 `/audio/translate` 从原路径重新开始来代替中间模型恢复。

说话人标签仅在同一切片内可靠，合并结果为不同切片添加前缀，避免把各片的 `speaker_0` 错认成同一个人；暂不进行跨切片声纹匹配。

## 字幕输出

`POST /api/v2/write/subtitles` 接受中间模型和以下 `options`：

| 字段 | 值 |
| --- | --- |
| `output_dir` | 必填，后端机器输出目录 |
| `format` | `srt`（默认）、`vtt`、`lrc`、`ass` |
| `mode` | `translated`（默认）、`source`、`bilingual` |
| `bilingual_order` | `source_first`（默认）、`translation_first` |
| `suffix` | 默认 `_subtitles` |
| `overwrite` | 默认 `false` |

输出使用 UTF-8，按时间顺序写出。未翻译条目回退到原文并在报告中计数。LRC 只表示开始时间，精度为百分之一秒；SRT/VTT 保留毫秒，ASS 使用百分之一秒。默认不覆盖已有文件，拒绝覆盖原音频；模型不会因导出而改变。

现有 `/api/v2/write` 继续服务原文档/PDF导出；音频字幕应调用专用 `/write/subtitles`。这些模型接口同步返回，网络断开不会立即取消后端线程；不要自动重发整个收费流程。应用服务的 `ExecutionContext` 支持协作取消，当前桌面停止接口只控制工作区任务。
