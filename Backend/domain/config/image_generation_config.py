"""Independent image-generation credentials and per-call translation settings."""
import copy
import json
import math
from dataclasses import asdict, dataclass, field
import re
from urllib.parse import urlsplit

from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.media_task_config import migrate_media_task_settings
from Backend.domain.config.request_defaults import REQUEST_TIMEOUT_SECONDS
from Backend.domain.config.image_translation_prompt import (
    DEFAULT_IMAGE_TRANSLATION_PROMPT, SELECTION_KEY, USER_PROMPTS_KEY,
    MAX_PROMPT_LENGTH, selected_image_translation_prompt,
)

DEFAULT_IMAGE_GENERATION_PROVIDER_ID = "bailian_image"
DEFAULT_IMAGE_GENERATION_PLATFORM = {
    "name": "百炼生图", "api_format": "DashScope",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "", "model": "qwen-image-3.0-pro", "request_timeout": REQUEST_TIMEOUT_SECONDS,
    "prompt_extend": True, "watermark": False, "size": "auto", "seed": None,
}
VOLCENGINE_ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
VOLCENGINE_SEEDREAM_MODEL = "doubao-seedream-5-0-pro-260628"
GEMINI_API_URL = "https://generativelanguage.googleapis.com"
GEMINI_IMAGE_MODEL = "gemini-3-pro-image"


@dataclass(frozen=True)
class ImageGenerationConfig:
    provider_id: str = DEFAULT_IMAGE_GENERATION_PROVIDER_ID
    api_url: str = DEFAULT_IMAGE_GENERATION_PLATFORM["api_url"]
    api_key: str = field(default="", repr=False)
    api_format: str = "DashScope"
    model: str = "qwen-image-3.0-pro"
    request_timeout: float = REQUEST_TIMEOUT_SECONDS
    prompt_extend: bool = True
    watermark: bool = False
    size: str = "auto"
    seed: int | None = None
    source_language: str = "japanese"
    target_language: str = "chinese_simplified"
    prompt: str = ""
    regenerate: bool = False
    # Resolved from the task prompt library, not a provider or per-call override.
    translation_prompt: str = DEFAULT_IMAGE_TRANSLATION_PROMPT

    @classmethod
    def read_snapshot(cls):
        from Backend.core.paths import config_path
        from Backend.infrastructure.config.store import ConfigStore
        result = {"image_generation_platforms": {
            DEFAULT_IMAGE_GENERATION_PROVIDER_ID: copy.deepcopy(DEFAULT_IMAGE_GENERATION_PLATFORM)},
            "active_image_generation_platform": DEFAULT_IMAGE_GENERATION_PROVIDER_ID,
            "image_translation_settings": {}, SELECTION_KEY: {}, USER_PROMPTS_KEY: []}
        try:
            with ConfigStore.CONFIG_FILE_LOCK:
                path = config_path()
                if path.exists():
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(saved, dict):
                        raise ValueError("invalid config")
                    migrate_media_task_settings(saved)
                    for key in result:
                        if key in saved:
                            result[key] = copy.deepcopy(saved[key])
                migrate_media_task_settings(result)
        except (OSError, ValueError, TypeError):
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "无法读取生图接口配置", 400) from None
        return result

    def to_request_config(self):
        return {name: getattr(self, name) for name in ("api_url", "api_key", "api_format", "model", "request_timeout",
                                                      "prompt_extend", "watermark", "seed")}


def validate_size(value, api_format="DashScope"):
    if value is None or value == "auto":
        return "auto"
    if api_format == "Gemini":
        if isinstance(value, str) and value.upper() in ("1K", "2K", "4K"):
            return value.upper()
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "Gemini生图尺寸需为auto、1K、2K或4K", 422)
    if api_format == "VolcengineArk":
        if isinstance(value, str) and value.upper() in ("1K", "1.5K", "2K"):
            return value.upper()
        if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,4}[x*][1-9][0-9]{0,4}", value):
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "Seedream 5.0 pro尺寸需为auto、1K、1.5K、2K或宽*高", 422)
        width, height = map(int, re.split(r"[x*]", value))
        if not 921600 <= width * height <= 4624220 or max(width, height) / min(width, height) > 16:
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "Seedream 5.0 pro总像素需为921600至4624220且宽高比不超过16", 422)
        return f"{width}x{height}"
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,4}\*[1-9][0-9]{0,4}", value):
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "生图尺寸必须为 auto 或 宽*高", 422)
    width, height = map(int, value.split("*"))
    if (width % 16 or height % 16 or not 512 ** 2 <= width * height <= 2048 ** 2
            or max(width, height) / min(width, height) > 8):
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "生图尺寸需为16的倍数，总像素为512²至2048²且宽高比不超过8", 422)
    return value


def gemini_endpoint(api_url, model):
    """Resolve a native Gemini base URL without putting credentials in URLs."""
    try:
        address = urlsplit(api_url)
        valid = address.scheme in ("http", "https") and address.hostname and not (
            address.username or address.password or address.query or address.fragment)
        valid = valid and address.path.rstrip("/") in ("", "/v1beta")
        _ = address.port
    except (ValueError, TypeError):
        valid = False
    if not valid or not isinstance(model, str) or not re.fullmatch(r"(?:models/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}", model):
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "Gemini请填写官方基地址（可含/v1beta）和有效模型名称", 422)
    base = api_url.rstrip("/")
    if not base.endswith("/v1beta"):
        base += "/v1beta"
    return base + "/models/" + model.removeprefix("models/") + ":generateContent"


def resolve_image_generation_config(config=None):
    fields = set(ImageGenerationConfig.__dataclass_fields__) - {"translation_prompt"}
    if isinstance(config, ImageGenerationConfig):
        values = asdict(config)
    else:
        overrides = {} if config is None else config
        if not isinstance(overrides, dict) or set(overrides) - fields:
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "生图配置包含不支持的字段", 422)
        snapshot = ImageGenerationConfig.read_snapshot()
        provider = overrides.get("provider_id", snapshot.get("active_image_generation_platform"))
        platforms = snapshot.get("image_generation_platforms")
        if not isinstance(platforms, dict) or not isinstance(provider, str) or not isinstance(platforms.get(provider), dict):
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "请先配置并选择独立生图接口", 400)
        values = asdict(ImageGenerationConfig())
        # Saved timeouts are retired; only an explicit per-call override may change the default.
        values.update({key: copy.deepcopy(value) for key, value in platforms[provider].items()
                       if key in fields and key not in {"provider_id", "request_timeout"}})
        task_settings = snapshot.get("image_translation_settings")
        if not isinstance(task_settings, dict) or not isinstance(task_settings.get("generation"), dict):
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "图译生成设置必须为对象", 422)
        values.update({key: copy.deepcopy(value) for key, value in task_settings["generation"].items()
                       if key in ("size", "seed", "prompt_extend", "prompt", "watermark")})
        values.update(copy.deepcopy(overrides))
        values["provider_id"] = provider
        try:
            values["translation_prompt"] = selected_image_translation_prompt(snapshot)
        except ValueError as error:
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", str(error), 422) from None
    for key in ("provider_id", "api_url", "api_key", "model", "source_language", "target_language"):
        value = values[key]
        if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\x00"):
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", f"生图 {key} 必须为非空单行文本", 400)
        values[key] = value.strip()
    try:
        address = urlsplit(values["api_url"])
        valid = address.scheme in ("http", "https") and address.hostname and not (
            address.username or address.password or address.query or address.fragment)
        _ = address.port
    except ValueError:
        valid = False
    if not valid or values["api_format"] not in ("DashScope", "VolcengineArk", "Gemini"):
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "请使用无凭据或查询参数的HTTP(S)地址与受支持的生图接口格式", 400)
    if values["api_format"] == "Gemini":
        gemini_endpoint(values["api_url"], values["model"])
        if any(not 33 <= ord(char) <= 126 for char in values["api_key"]):
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "Gemini API密钥必须为不含空白的有效文本", 422)
    timeout = values["request_timeout"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "生图超时需大于0且不超过3600秒", 422)
    for key in ("prompt_extend", "watermark", "regenerate"):
        if type(values[key]) is not bool:
            raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", f"生图 {key} 必须为布尔值", 422)
    if values["seed"] is not None and (type(values["seed"]) is not int or not 0 <= values["seed"] <= 2147483647):
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "seed需为0至2147483647的整数或空值", 422)
    values["size"] = validate_size(values["size"], values["api_format"])
    if not isinstance(values["prompt"], str) or len(values["prompt"]) > 10000 or "\x00" in values["prompt"]:
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "补充提示词需为不超过10000字的文本", 422)
    if (not isinstance(values["translation_prompt"], str) or not values["translation_prompt"].strip()
            or len(values["translation_prompt"]) > MAX_PROMPT_LENGTH or "\x00" in values["translation_prompt"]):
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "图片翻译提示词需为非空且不超过10000字的文本", 422)
    return ImageGenerationConfig(**values)


def validate_image_generation_platform(identifier: str, platform: dict) -> None:
    """验证单个生图平台配置项，抛出 ValueError 表示配置非法。"""
    if not isinstance(identifier, str) or not identifier.strip() or not isinstance(platform, dict):
        raise ValueError("生图接口配置必须使用非空字符串 ID 和 JSON 对象")
    for field in ("name", "api_url", "api_key", "model", "api_format", "size", "prompt"):
        if field in platform and not isinstance(platform[field], str):
            raise ValueError(f"生图接口字段 {field} 必须是字符串")
    for field in ("prompt_extend", "watermark"):
        if field in platform and type(platform[field]) is not bool:
            raise ValueError(f"生图接口字段 {field} 必须是布尔值")
    seed = platform.get("seed")
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 2147483647):
        raise ValueError("生图随机种子必须为空或0至2147483647的整数")
    try:
        api_format = platform.get("api_format", "DashScope")
        if api_format not in ("DashScope", "VolcengineArk", "Gemini"):
            raise ValueError("不支持的生图接口格式")
        if api_format == "Gemini":
            gemini_endpoint(platform.get("api_url", GEMINI_API_URL), platform.get("model", GEMINI_IMAGE_MODEL))
        validate_size(platform.get("size", "auto"), platform.get("api_format", "DashScope"))
    except PipelineError as error:
        raise ValueError(error.message) from None
