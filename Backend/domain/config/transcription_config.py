"""Read-only, per-call configuration for the independent online ASR provider."""
import copy
import json
import math
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

from Backend.application.pipeline_common import PipelineError


DEFAULT_TRANSCRIPTION_PROVIDER_ID = "bailian_asr"
DEFAULT_TRANSCRIPTION_PLATFORM = {
    "name": "百炼语音转录",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "", "model": "qwen-audio-3.1-asr-flash", "api_format": "DashScope",
    "request_timeout": 300, "language_hints": [], "speaker_diarization_enabled": False,
    "chunk_duration_seconds": 240, "chunk_overlap_seconds": 2,
    "chunk_concurrency": 3, "vad_threshold": 0.35,
}
LANGUAGE_HINTS = frozenset("zh en ja ko vi th id ms tl hi ar fr de es pt ru it nl sv da fi no el pl cs hu ro bg hr sk".split())
_OVERRIDE_FIELDS = frozenset({
    "provider_id", "api_url", "api_key", "model", "api_format", "request_timeout", "timeout",
    "language_hints", "speaker_diarization_enabled", "keep_dialect", "stream", "max_retries", "retranscribe",
    "chunk_duration_seconds", "chunk_overlap_seconds", "chunk_concurrency", "vad_threshold",
})


@dataclass(frozen=True)
class TranscriptionConfig:
    provider_id: str = DEFAULT_TRANSCRIPTION_PROVIDER_ID
    api_url: str = DEFAULT_TRANSCRIPTION_PLATFORM["api_url"]
    api_key: str = field(default="", repr=False)
    model: str = "qwen-audio-3.1-asr-flash"
    api_format: str = "DashScope"
    request_timeout: float = 300
    language_hints: tuple[str, ...] = ()
    speaker_diarization_enabled: bool = False
    keep_dialect: bool = False
    stream: bool = True
    max_retries: int = 0
    retranscribe: bool = False
    chunk_duration_seconds: int = 240
    chunk_overlap_seconds: float = 2
    chunk_concurrency: int = 3
    vad_threshold: float = 0.35

    @classmethod
    def read_snapshot(cls) -> dict:
        """No migration, backup, normalization write, or translation credentials."""
        from Backend.core.paths import config_path
        from Backend.infrastructure.config.store import ConfigStore

        result = {
            "transcription_platforms": {DEFAULT_TRANSCRIPTION_PROVIDER_ID: copy.deepcopy(DEFAULT_TRANSCRIPTION_PLATFORM)},
            "active_transcription_platform": DEFAULT_TRANSCRIPTION_PROVIDER_ID,
        }
        try:
            with ConfigStore.CONFIG_FILE_LOCK:
                path = config_path()
                if path.exists():
                    with path.open("r", encoding="utf-8") as reader:
                        saved = json.load(reader)
                    if not isinstance(saved, dict):
                        raise ValueError("invalid root")
                    for key in result:
                        if key in saved:
                            result[key] = copy.deepcopy(saved[key])
        except (OSError, ValueError, TypeError) as error:
            raise PipelineError("ASR_CONFIG_ERROR", "无法读取转录接口配置", 400) from error
        return result

    def to_request_config(self) -> dict:
        result = asdict(self)
        result["language_hints"] = list(self.language_hints)
        result.pop("retranscribe")
        return result


def resolve_transcription_config(config=None) -> TranscriptionConfig:
    if isinstance(config, TranscriptionConfig):
        # Validate manually constructed objects as rigorously as API overrides.
        values = asdict(config)
    else:
        if config is None:
            config = {}
        if not isinstance(config, dict) or set(config) - _OVERRIDE_FIELDS:
            raise PipelineError("ASR_CONFIG_ERROR", "转录配置必须为仅包含支持字段的对象", 400)
        overrides = copy.deepcopy(config)
        if "timeout" in overrides:
            if "request_timeout" in overrides and overrides["request_timeout"] != overrides["timeout"]:
                raise PipelineError("ASR_CONFIG_ERROR", "timeout 与 request_timeout 不一致", 400)
            overrides["request_timeout"] = overrides.pop("timeout")
        snapshot = TranscriptionConfig.read_snapshot()
        platforms = snapshot.get("transcription_platforms")
        provider_id = overrides.pop("provider_id", snapshot.get("active_transcription_platform"))
        if not isinstance(platforms, dict) or not isinstance(provider_id, str) or not provider_id.strip():
            raise PipelineError("ASR_CONFIG_ERROR", "请先选择转录接口", 400)
        platform = platforms.get(provider_id)
        if not isinstance(platform, dict):
            raise PipelineError("ASR_CONFIG_ERROR", "所选转录接口不存在", 400)
        values = asdict(TranscriptionConfig())
        values.update({key: copy.deepcopy(value) for key, value in platform.items() if key in values and key != "provider_id"})
        values.update(overrides)
        values["provider_id"] = provider_id

    for key in ("api_url", "api_key", "model", "provider_id"):
        if not isinstance(values[key], str) or not values[key].strip():
            messages = {"api_key": "请配置转录接口 API Key", "api_url": "转录接口地址不能为空",
                        "model": "转录模型不能为空", "provider_id": "转录接口标识不能为空"}
            raise PipelineError("ASR_CONFIG_ERROR", messages[key], 400)
        values[key] = values[key].strip()
    try:
        url = urlsplit(values["api_url"])
        valid_url = url.scheme in ("http", "https") and url.hostname and not (url.username or url.password or url.query or url.fragment)
        _ = url.port
    except ValueError:
        valid_url = False
    if not valid_url or any(char in values["api_url"] for char in "\r\n"):
        raise PipelineError("ASR_CONFIG_ERROR", "转录接口必须为不含凭证或查询参数的 HTTP(S) 地址", 400)
    if any(char in values["api_key"] for char in "\r\n"):
        raise PipelineError("ASR_CONFIG_ERROR", "转录接口 API Key 格式无效", 400)
    if not isinstance(values["api_format"], str) or values["api_format"].lower() != "dashscope":
        raise PipelineError("ASR_CONFIG_ERROR", "当前转录接口仅支持 DashScope 格式", 400)
    values["api_format"] = "DashScope"
    timeout = values["request_timeout"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise PipelineError("ASR_CONFIG_ERROR", "转录超时必须为 0 至 3600 秒之间的正数", 400)
    retries = values["max_retries"]
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 5:
        raise PipelineError("ASR_CONFIG_ERROR", "转录重试次数必须为 0 至 5 的整数", 400)
    for key in ("speaker_diarization_enabled", "keep_dialect", "stream", "retranscribe"):
        if not isinstance(values[key], bool):
            raise PipelineError("ASR_CONFIG_ERROR", "转录开关必须为布尔值", 400)
    hints = values["language_hints"]
    if not isinstance(hints, (list, tuple)) or len(hints) > 4 or any(not isinstance(hint, str) or hint not in LANGUAGE_HINTS for hint in hints):
        raise PipelineError("ASR_CONFIG_ERROR", "language_hints 最多包含 4 个受支持的语言代码", 400)
    values["language_hints"] = tuple(dict.fromkeys(hints))
    for key, lower, upper in (("chunk_duration_seconds", 30, 290), ("chunk_concurrency", 1, 8)):
        value = values[key]
        if type(value) is not int or not lower <= value <= upper:
            raise PipelineError("ASR_CONFIG_ERROR", f"{key} 必须为 {lower} 至 {upper} 的整数", 400)
    for key, lower, upper in (("chunk_overlap_seconds", 0.5, 5), ("vad_threshold", 0.01, 0.99)):
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise PipelineError("ASR_CONFIG_ERROR", f"{key} 必须为 {lower} 至 {upper} 之间的数字", 400)
    return TranscriptionConfig(**values)
