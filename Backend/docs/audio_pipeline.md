# 音频转录、翻译与字幕接口

接口按“读取 → 转录 → 翻译 → 字幕写出”串行执行，翻译阶段复用现有多线程批量翻译服务。可以逐步调用，也可以一次调用 `POST /api/v2/audio/translate`。整个流程只占用一个顶层操作，不创建 Job，不改变桌面当前项目。

桌面“接口管理”下有“翻译接口”和“转录接口”。翻译接口沿用原设置；转录接口单独保存多个服务配置，并选择当前使用的服务。暂不增加音频翻译工作区。

## 配置与环境

转录配置保存在 `transcription_platforms` 和 `active_transcription_platform`，与翻译的 `platforms`、接口绑定分别管理。默认提供阿里云百炼配置，密钥默认为空。请在转录接口页填写自己的密钥。API 调用可用 `config.provider_id` 选择已保存服务，也可通过本次调用覆盖配置；覆盖不回写设置。

首版请求协议为百炼 DashScope 原生语音识别 HTTP API，默认模型 `qwen-audio-3.1-asr-flash`，默认请求地址：

```text
https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

该地址与 OpenAI 兼容的聊天接口地址不同。新工作空间可按百炼控制台说明配置工作空间专用地址；密钥、模型与地域需匹配。协议及请求字段见[百炼语音识别 HTTP 文档](https://help.aliyun.com/zh/model-studio/qwen-audio-asr-http-api)。

读取 MP3 等格式需要后端机器可执行 `ffprobe`（安装 FFmpeg 并加入 PATH）；PCM WAV 在缺少 ffprobe 时可用 Python 标准库读取。输入是后端可访问的本地文件或目录，目录递归读取，`exclude_rule` 为逗号分隔的文件匹配规则。不会在中间模型中保存音频 Base64 或密钥。

`qwen-audio-3.1-asr-flash` 单次请求音频最长 5 分钟。超过 5 分钟的本地音频会自动通过 VAD 选择切点，分片批量转录后恢复原始时间轴。长音频需要后端可用的 FFmpeg；每个提交给百炼的切片仍不超过接口上限。模型限制见[百炼语音识别模型列表](https://help.aliyun.com/zh/model-studio/asr-model)。

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

默认使用 SSE 收集最终句子及时间戳，保留服务器提供的说话人标签。若响应只有全文而没有完整有效的分句时间轴，使用整段音频时长输出一个条目并在报告中说明降级，不把全文错误地绑定到最后一句的时间戳。

转录覆盖项包括 `provider_id`、`api_url`、`api_key`、`model`、`api_format`（`DashScope`）、`request_timeout`、`language_hints`、`speaker_diarization_enabled`、`keep_dialect`、`stream`、`max_retries`、`retranscribe`。详细类型及默认值以运行中的 `/docs` 和配置页为准。

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

桌面转录接口页可设置切片目标长度和并发数。顶层流程仍然串行、仍只允许一个活动操作；并发仅发生在当前文件的切片请求中，不创建 Job。取消后停止提交新片，并等待已经发出的请求结束。

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
