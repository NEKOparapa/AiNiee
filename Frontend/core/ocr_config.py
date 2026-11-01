"""Pure desktop validation for independently configured OCR providers."""
import copy
from urllib.parse import urlsplit


DEFAULT_OCR_PLATFORM = {
    "name": "百炼文字识别",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "", "model": "qwen-vl-ocr", "api_format": "DashScope",
    "request_timeout": 180, "max_pixels": 8388608, "max_tokens": 4096,
    "reading_order": "auto", "group_lines": False, "refine_text": False, "max_retries": 0,
}
MIN_REQUEST_TIMEOUT = 10
MAX_REQUEST_TIMEOUT = 3600
READING_ORDERS = ("auto", "ltr", "manga_rtl")
MODEL_TOKEN_LIMITS = {"qwen-vl-ocr": 4096, "qwen-vl-ocr-2025-11-20": 8192}


def normalize_ocr_platform(data=None):
    if data is not None and not isinstance(data, dict):
        raise ValueError("OCR 接口配置必须是对象。")
    result = copy.deepcopy(DEFAULT_OCR_PLATFORM)
    result.update(copy.deepcopy(data or {}))
    for key in ("name", "api_url", "api_key", "model", "api_format", "reading_order"):
        if not isinstance(result[key], str):
            raise ValueError("OCR 接口名称、地址、密钥、模型、格式和阅读顺序必须是文本。")
        result[key] = result[key].strip()
    timeout = result["request_timeout"]
    if isinstance(timeout, float) and timeout.is_integer():
        result["request_timeout"] = int(timeout)
    return result


def validate_ocr_platform(data, *, require_api_key=False):
    """Validate without network or persistence; never echo secret input."""
    result = normalize_ocr_platform(data)
    if not result["name"]:
        raise ValueError("请输入 OCR 接口名称。")
    if result["api_format"] != "DashScope":
        raise ValueError("目前仅支持 DashScope OCR 接口。")
    try:
        parsed = urlsplit(result["api_url"])
        valid_url = (parsed.scheme in ("http", "https") and bool(parsed.hostname)
                     and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
                     and not any(c.isspace() for c in result["api_url"]))
        _ = parsed.port
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("请输入不含账号、密码、查询参数或片段的 HTTP(S) 接口地址。")
    if not result["model"]:
        raise ValueError("请输入 OCR 模型名称。")
    if any(c in result["api_key"] for c in "\r\n"):
        raise ValueError("OCR 接口密钥不能包含换行。")
    if require_api_key and not result["api_key"]:
        raise ValueError("请先填写并保存接口密钥，再激活此 OCR 接口。")
    for key, lower, upper in (("request_timeout", MIN_REQUEST_TIMEOUT, MAX_REQUEST_TIMEOUT),
                              ("max_pixels", 3136, 23520000), ("max_tokens", 1, 32768),
                              ("max_retries", 0, 5)):
        if type(result[key]) is not int or not lower <= result[key] <= upper:
            raise ValueError(f"OCR 配置 {key} 必须是 {lower} 至 {upper} 的整数。")
    token_limit = MODEL_TOKEN_LIMITS.get(result["model"], 32768)
    if result["max_tokens"] > token_limit:
        raise ValueError(f"{result['model']} 输出上限为 {token_limit}，请降低 max_tokens 或使用支持更长输出的模型。")
    if result["reading_order"] not in READING_ORDERS:
        raise ValueError("请选择自动、从左向右或漫画从右向左的阅读顺序。")
    if type(result["group_lines"]) is not bool:
        raise ValueError("合并文字行必须是开启或关闭。")
    if type(result["refine_text"]) is not bool:
        raise ValueError("复核气泡原文必须是开启或关闭。")
    if result["refine_text"] and not result["group_lines"]:
        raise ValueError("复核气泡原文需要先开启“合并相邻文字行”。")
    return result


def build_ocr_config_update(config, platform_id, platform=None, *, action="save"):
    """Patch only OCR-owned keys; retain unknown advanced provider fields."""
    if not isinstance(config, dict) or not isinstance(platform_id, str) or not platform_id.strip():
        raise ValueError("OCR 配置或接口标识无效。")
    providers = config.get("ocr_platforms", {})
    if not isinstance(providers, dict):
        raise ValueError("OCR 接口列表必须是对象。")
    providers = copy.deepcopy(providers)
    active = config.get("active_ocr_platform", "")
    if not isinstance(active, str):
        raise ValueError("激活的 OCR 接口标识必须是文本。")
    if action == "save":
        if not isinstance(platform, dict):
            raise ValueError("请提供需要保存的 OCR 接口配置。")
        previous = providers.get(platform_id, {})
        if not isinstance(previous, dict):
            raise ValueError("已有 OCR 接口配置无效。")
        providers[platform_id] = validate_ocr_platform({**previous, **platform})
    elif action == "activate":
        if platform_id not in providers:
            raise ValueError("OCR 接口不存在，请刷新页面。")
        providers[platform_id] = validate_ocr_platform(providers[platform_id], require_api_key=True)
        active = platform_id
    elif action == "delete":
        if platform_id not in providers:
            raise ValueError("OCR 接口不存在，请刷新页面。")
        del providers[platform_id]
        if active == platform_id:
            active = ""
    else:
        raise ValueError("未知的 OCR 配置操作。")
    return {"ocr_platforms": providers, "active_ocr_platform": active}
