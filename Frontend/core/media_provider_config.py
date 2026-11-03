"""Media provider presets and connection-only edits, independent of Qt pages."""

import copy
from urllib.parse import urlsplit

from Frontend.core.image_generation_config import DEFAULT_IMAGE_GENERATION_PLATFORM
from Frontend.core.ocr_config import DEFAULT_OCR_PLATFORM


DEFAULT_TRANSCRIPTION_PLATFORM = {
    "name": "阿里云百炼", "api_format": "DashScope",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "", "model": "qwen-audio-3.1-asr-flash", "request_timeout": 300,
    "language_hints": [], "speaker_diarization_enabled": False,
    "chunk_duration_seconds": 240, "chunk_overlap_seconds": 2,
    "chunk_concurrency": 3, "vad_threshold": 0.35,
}
SUPPORTED_LANGUAGE_HINTS = frozenset(
    "zh en ja ko vi th id ms tl hi ar fr de es pt ru it nl sv da fi no el pl cs hu ro bg hr sk".split()
)
PROVIDER_FORMATS = {
    "transcription": ("DashScope", "VolcengineASRFast"),
    "ocr": ("DashScope",),
    "image_generation": ("DashScope", "VolcengineArk"),
}
PROVIDER_DEFAULTS = {
    "transcription": DEFAULT_TRANSCRIPTION_PLATFORM,
    "ocr": DEFAULT_OCR_PLATFORM,
    "image_generation": DEFAULT_IMAGE_GENERATION_PLATFORM,
}


def get_media_provider_presets(kind):
    defaults = copy.deepcopy(PROVIDER_DEFAULTS[kind])
    presets = {
        "bailian": {
            **defaults, "name": "阿里云百炼", "group": "online", "icon": "dashscope",
            "description": {"transcription": "本地音频转录", "ocr": "图片文字识别",
                            "image_generation": "图像编辑与图片翻译"}[kind],
        },
    }
    if kind == "transcription":
        common = {
            "model": "bigmodel", "api_key": "", "app_id": "", "icon": "volcengine",
            "group": "online", "request_timeout": 300,
        }
        presets.update({
            "volcengine_asr_fast": {
                **common, "name": "火山豆包（极速）", "api_format": "VolcengineASRFast",
                "api_url": "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
                "resource_id": "volc.bigasr.auc_turbo", "description": "火山引擎 · 直接转录本地音频文件",
            },
        })
    elif kind == "image_generation":
        presets["volcengine_seedream"] = {
            "name": "火山", "api_format": "VolcengineArk",
            "api_url": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            "api_key": "", "model": "doubao-seedream-5-0-pro-260628", "request_timeout": 300,
            "group": "online", "icon": "volcengine", "description": "火山引擎 · 豆包图像编辑与图片翻译",
        }
    presets["custom"] = {
        **defaults, "name": "自定义接口", "group": "custom", "icon": "custom",
        "api_url": "", "api_key": "", "model": "", "description": "兼容所选协议的第三方服务",
        "format_datas": list(PROVIDER_FORMATS[kind]),
    }
    for tag, preset in presets.items():
        preset["preset_id"] = tag
        preset.setdefault("format_datas", [preset["api_format"]])
        preset.setdefault("model_datas", [preset["model"]] if preset["model"] else [])
    return presets


def normalize_media_provider(kind, data=None):
    if kind not in PROVIDER_DEFAULTS:
        raise ValueError("未知媒体接口类型。")
    if data is not None and not isinstance(data, dict):
        raise ValueError("接口配置必须是对象。")
    result = copy.deepcopy(PROVIDER_DEFAULTS[kind])
    result.update(copy.deepcopy(data or {}))
    for key in ("name", "api_format", "api_url", "api_key", "model"):
        if not isinstance(result[key], str):
            raise ValueError("接口名称、格式、地址、密钥与模型必须是文本。")
        result[key] = result[key].strip()
    if kind == "transcription" and result["api_format"] == "VolcengineASRFast":
        result.setdefault("app_id", "")
        result.setdefault("resource_id", "volc.bigasr.auc_turbo")
        for key in ("app_id", "resource_id"):
            if not isinstance(result[key], str):
                raise ValueError("APP ID 和资源 ID 必须是文本。")
            result[key] = result[key].strip()
    # 超时不再提供编辑，旧配置也统一使用默认值。
    result["request_timeout"] = 300
    if result.get("group") not in ("online", "custom"):
        try:
            host = urlsplit(result["api_url"]).hostname or ""
        except ValueError:
            host = ""
        official = host.endswith(".aliyuncs.com") or host in (
            "openspeech.bytedance.com", "ark.cn-beijing.volces.com",
        )
        result["group"] = "online" if official else "custom"
    return result


def validate_media_provider(kind, data, *, require_credentials=False):
    result = normalize_media_provider(kind, data)
    if not result["name"]:
        raise ValueError("请输入接口名称。")
    if result["api_format"] not in PROVIDER_FORMATS[kind]:
        raise ValueError("请选择受支持的接口协议。")
    try:
        url = urlsplit(result["api_url"])
        valid = (url.scheme in ("https", "http") and bool(url.hostname)
                 and not (url.username or url.password or url.query or url.fragment)
                 and not any(c.isspace() for c in result["api_url"]))
        _ = url.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("请输入不含账号、密码、查询参数或片段的 HTTP(S) 接口地址。")
    if not result["model"]:
        raise ValueError("请输入模型名称。")
    if any(c in result["api_key"] for c in "\r\n\x00"):
        raise ValueError("接口密钥必须是单行文本。")
    if require_credentials and not result["api_key"]:
        raise ValueError("请先填写接口密钥，再激活此接口。")
    if kind == "transcription" and result["api_format"] == "VolcengineASRFast":
        expected_path = "/api/v3/auc/bigmodel/recognize/flash"
        if not url.path.rstrip("/").endswith(expected_path):
            raise ValueError("火山接口地址与极速版协议不匹配。")
        if result["model"] != "bigmodel":
            raise ValueError("豆包录音转录的模型名称必须为 bigmodel。")
        if result["resource_id"] != "volc.bigasr.auc_turbo":
            raise ValueError("火山资源 ID 与极速版协议不匹配。")
        if any(not result[key].isascii() or any(c.isspace() for c in result[key])
               for key in ("api_key", "app_id", "resource_id") if result[key]):
            raise ValueError("火山密钥、APP ID 和资源 ID 必须是不含空白的 ASCII 文本。")
    for key in ("preset_id", "icon"):
        if key in result and not isinstance(result[key], str):
            raise ValueError("接口预设与图标标识必须是文本。")
    return result


def build_media_provider_update(config, kind, platform_id, platform=None, *, action="save"):
    if kind not in PROVIDER_DEFAULTS or not isinstance(config, dict):
        raise ValueError("接口配置无效。")
    if not isinstance(platform_id, str) or not platform_id.strip():
        raise ValueError("接口标识不能为空。")
    providers_key, active_key = kind + "_platforms", "active_" + kind + "_platform"
    source = config.get(providers_key, {})
    if not isinstance(source, dict):
        raise ValueError("接口列表必须是对象。")
    providers = copy.deepcopy(source)
    active = config.get(active_key, "")
    if not isinstance(active, str):
        raise ValueError("激活接口标识必须是文本。")
    if action == "save":
        if not isinstance(platform, dict) or not isinstance(providers.get(platform_id, {}), dict):
            raise ValueError("接口配置必须是对象。")
        providers[platform_id] = validate_media_provider(kind, {**providers.get(platform_id, {}), **platform})
    elif action == "activate":
        if platform_id not in providers:
            raise ValueError("接口不存在，请重新打开页面。")
        providers[platform_id] = validate_media_provider(kind, providers[platform_id], require_credentials=True)
        active = platform_id
    elif action == "delete":
        if platform_id not in providers:
            raise ValueError("接口不存在，请重新打开页面。")
        del providers[platform_id]
        if active == platform_id:
            active = ""
    else:
        raise ValueError("未知的接口配置操作。")
    return {providers_key: providers, active_key: active}
