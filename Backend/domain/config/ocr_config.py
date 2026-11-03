"""Independent, read-only OCR provider configuration."""
import copy
import json
import math
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.media_task_config import migrate_media_task_settings


DEFAULT_OCR_PROVIDER_ID = "bailian_ocr"
DEFAULT_OCR_PLATFORM = {
    "name": "百炼图片 OCR", "api_format": "DashScope",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "", "model": "qwen-vl-ocr", "request_timeout": 180,
    "max_retries": 0, "max_pixels": 8388608, "max_tokens": 4096,
    "reading_order": "auto", "group_lines": False, "refine_text": False,
}


@dataclass(frozen=True)
class OCRConfig:
    provider_id: str = DEFAULT_OCR_PROVIDER_ID
    api_url: str = DEFAULT_OCR_PLATFORM["api_url"]
    api_key: str = field(default="", repr=False)
    api_format: str = "DashScope"
    model: str = "qwen-vl-ocr"
    request_timeout: float = 180
    max_retries: int = 0
    max_pixels: int = 8388608
    max_tokens: int = 4096
    reading_order: str = "auto"
    group_lines: bool = False
    refine_text: bool = False
    reocr: bool = False

    @classmethod
    def read_snapshot(cls):
        from Backend.core.paths import config_path
        from Backend.infrastructure.config.store import ConfigStore

        result = {"ocr_platforms": {DEFAULT_OCR_PROVIDER_ID: copy.deepcopy(DEFAULT_OCR_PLATFORM)},
                  "active_ocr_platform": DEFAULT_OCR_PROVIDER_ID,
                  "image_translation_settings": {}}
        try:
            with ConfigStore.CONFIG_FILE_LOCK:
                path = config_path()
                if path.exists():
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(saved, dict):
                        raise ValueError("invalid configuration root")
                    migrate_media_task_settings(saved)
                    for key in result:
                        if key in saved:
                            result[key] = copy.deepcopy(saved[key])
                migrate_media_task_settings(result)
        except (OSError, ValueError, TypeError):
            raise PipelineError("OCR_CONFIG_ERROR", "无法读取 OCR 接口配置", 400) from None
        return result

    def to_request_config(self):
        return {key: value for key, value in asdict(self).items()
                if key not in {"reocr", "reading_order", "group_lines", "refine_text"}}


def resolve_ocr_config(config=None):
    supported = set(OCRConfig.__dataclass_fields__)
    if isinstance(config, OCRConfig):
        values = asdict(config)
    else:
        overrides = {} if config is None else config
        if not isinstance(overrides, dict) or set(overrides) - supported:
            raise PipelineError("OCR_CONFIG_ERROR", "OCR 配置包含不支持的字段", 400)
        snapshot = OCRConfig.read_snapshot()
        provider_id = overrides.get("provider_id", snapshot.get("active_ocr_platform"))
        platforms = snapshot.get("ocr_platforms")
        if not isinstance(provider_id, str) or not provider_id.strip() or not isinstance(platforms, dict):
            raise PipelineError("OCR_CONFIG_ERROR", "请先选择 OCR 接口", 400)
        platform = platforms.get(provider_id)
        if not isinstance(platform, dict):
            raise PipelineError("OCR_CONFIG_ERROR", "所选 OCR 接口不存在", 400)
        values = asdict(OCRConfig())
        values.update({key: copy.deepcopy(value) for key, value in platform.items() if key in supported and key != "provider_id"})
        task_settings = snapshot.get("image_translation_settings")
        if not isinstance(task_settings, dict) or not isinstance(task_settings.get("ocr"), dict):
            raise PipelineError("OCR_CONFIG_ERROR", "图译识别设置必须为对象", 400)
        values.update({key: copy.deepcopy(value) for key, value in task_settings["ocr"].items()
                       if key in ("reading_order", "group_lines", "refine_text")})
        values.update(copy.deepcopy(overrides))
        values["provider_id"] = provider_id
    for key in ("provider_id", "api_url", "api_key", "model"):
        value = values[key]
        if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\x00"):
            raise PipelineError("OCR_CONFIG_ERROR", f"OCR {key} 必须为非空单行文本", 400)
        values[key] = value.strip()
    try:
        url = urlsplit(values["api_url"])
        valid = url.scheme in {"https", "http"} and url.hostname and not (url.username or url.password or url.query or url.fragment)
        _ = url.port
    except ValueError:
        valid = False
    if not valid:
        raise PipelineError("OCR_CONFIG_ERROR", "OCR 地址必须为不含凭据或查询参数的 HTTP(S) 地址", 400)
    if values["api_format"] != "DashScope":
        raise PipelineError("OCR_CONFIG_ERROR", "当前 OCR 仅支持 DashScope 格式", 400)
    timeout = values["request_timeout"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise PipelineError("OCR_CONFIG_ERROR", "OCR 请求超时必须大于 0 且不超过 3600 秒", 400)
    for key, lo, hi in (("max_retries", 0, 5), ("max_pixels", 3136, 23520000), ("max_tokens", 1, 32768)):
        if type(values[key]) is not int or not lo <= values[key] <= hi:
            raise PipelineError("OCR_CONFIG_ERROR", f"OCR {key} 必须为 {lo} 至 {hi} 的整数", 400)
    if values["model"] == "qwen-vl-ocr" and values["max_tokens"] > 4096:
        raise PipelineError("OCR_CONFIG_ERROR", "qwen-vl-ocr 默认输出上限为 4096，请使用支持更长输出的模型", 400)
    if values["model"] == "qwen-vl-ocr-2025-11-20" and values["max_tokens"] > 8192:
        raise PipelineError("OCR_CONFIG_ERROR", "qwen-vl-ocr-2025-11-20 输出上限为 8192", 400)
    if values["reading_order"] not in ("auto", "ltr", "manga_rtl"):
        raise PipelineError("OCR_CONFIG_ERROR", "OCR 阅读顺序必须为 auto、ltr 或 manga_rtl", 400)
    for key in ("group_lines", "reocr", "refine_text"):
        if not isinstance(values[key], bool):
            raise PipelineError("OCR_CONFIG_ERROR", f"OCR {key} 必须为布尔值", 400)
    if values["refine_text"] and not values["group_lines"]:
        raise PipelineError("OCR_CONFIG_ERROR", "复核气泡原文需要先开启合并文字行", 400)
    return OCRConfig(**values)


def validate_ocr_platform(identifier: str, platform: dict) -> None:
    """验证单个 OCR 平台配置项，抛出 ValueError 表示配置非法。"""
    if not isinstance(identifier, str) or not identifier.strip() or not isinstance(platform, dict):
        raise ValueError("OCR 接口配置必须使用非空字符串 ID 和 JSON 对象")
    for field in ("name", "api_url", "api_key", "model", "api_format", "reading_order"):
        if field in platform and not isinstance(platform[field], str):
            raise ValueError(f"OCR 接口字段 {field} 必须是字符串")
    if "request_timeout" in platform and (isinstance(platform["request_timeout"], bool)
            or not isinstance(platform["request_timeout"], (int, float))):
        raise ValueError("OCR 接口字段 request_timeout 必须是数字")
    for field in ("max_pixels", "max_tokens", "max_retries"):
        if field in platform and type(platform[field]) is not int:
            raise ValueError(f"OCR 接口字段 {field} 必须是整数")
    ocr_model = platform.get("model", "qwen-vl-ocr").strip()
    token_limit = {"qwen-vl-ocr": 4096, "qwen-vl-ocr-2025-11-20": 8192}.get(ocr_model, 32768)
    if not 1 <= platform.get("max_tokens", 4096) <= token_limit:
        raise ValueError(f"OCR 模型 {ocr_model} 的 max_tokens 必须是 1 至 {token_limit} 的整数")
    for field in ("group_lines", "refine_text"):
        if field in platform and type(platform[field]) is not bool:
            raise ValueError(f"OCR 接口字段 {field} 必须是布尔值")
    if platform.get("refine_text", False) and not platform.get("group_lines", False):
        raise ValueError("复核气泡原文需要先开启“合并相邻文字行”。")
