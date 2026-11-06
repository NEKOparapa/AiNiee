"""Pure validation for image-editing providers, independent of text-model credentials."""
import copy
import re
from urllib.parse import urlsplit


DEFAULT_IMAGE_GENERATION_PLATFORM = {
    "name": "百炼图像编辑",
    "api_format": "DashScope",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "",
    "model": "qwen-image-3.0-pro",
    "request_timeout": 300,
    "user_thread_counts": 3,
    "prompt_extend": True,
    "seed": None,
    "size": "auto",
    "prompt": "",
}
MAX_SEED = 2147483647


def validate_gemini_connection(api_url, model, api_key=""):
    """Validate native Gemini connection fields without importing the backend."""
    try:
        address = urlsplit(api_url)
        valid = (address.scheme in ("http", "https") and address.hostname
                 and not (address.username or address.password or address.query or address.fragment)
                 and address.path.rstrip("/") in ("", "/v1beta"))
        _ = address.port
    except (ValueError, TypeError):
        valid = False
    if not valid or not isinstance(model, str) or not re.fullmatch(r"(?:models/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}", model):
        raise ValueError("Gemini 请填写 API 基地址（可含 /v1beta）和有效模型名称。")
    if not isinstance(api_key, str) or any(not 33 <= ord(char) <= 126 for char in api_key):
        raise ValueError("Gemini API 密钥必须为不含空白的 ASCII 文本。")


def normalize_generation_size(value, api_format=None):
    """Validate a shared size, or restrict it to one provider protocol."""
    if not isinstance(value, str):
        raise ValueError("输出尺寸必须是文本。")
    value = value.strip().lower()
    if value == "auto":
        return value
    presets = {"DashScope": (), "VolcengineArk": ("1K", "1.5K", "2K"), "Gemini": ("1K", "2K", "4K")}
    if value.upper() in presets.get(api_format, ("1K", "1.5K", "2K", "4K")):
        return value.upper()
    if api_format == "Gemini":
        raise ValueError("Gemini 输出尺寸需为 auto、1K、2K 或 4K。")
    if len(value) > 32 or not re.fullmatch(r"[1-9]\d*\s*[x*]\s*[1-9]\d*", value, flags=re.ASCII):
        raise ValueError("输出尺寸需为 auto 或 宽*高；Seedream 支持 1K、1.5K、2K，Gemini 支持 1K、2K、4K。")
    width, height = (int(part.strip()) for part in re.split(r"[x*]", value))
    pixels, ratio = width * height, max(width, height) / min(width, height)
    dashscope = width % 16 == height % 16 == 0 and 512 ** 2 <= pixels <= 2048 ** 2 and ratio <= 8
    ark = 921600 <= pixels <= 4624220 and ratio <= 16
    allowed = dashscope if api_format == "DashScope" else ark if api_format == "VolcengineArk" else dashscope or ark
    if not allowed:
        raise ValueError("输出尺寸超出模型支持范围，请使用 auto 或调整宽高。")
    return f"{width}*{height}"


def normalize_image_generation_platform(data=None):
    if data is not None and not isinstance(data, dict):
        raise ValueError("生图接口配置必须是对象。")
    result = copy.deepcopy(DEFAULT_IMAGE_GENERATION_PLATFORM)
    result.update(copy.deepcopy(data or {}))
    result.pop("chunk_concurrency", None)
    if type(result["user_thread_counts"]) is not int or not 1 <= result["user_thread_counts"] <= 64:
        raise ValueError("接口并发任务数必须是 1 至 64 的整数")
    for key in ("name", "api_format", "api_url", "api_key", "model", "size", "prompt"):
        if not isinstance(result[key], str):
            raise ValueError("生图接口的文本字段必须是字符串。")
        if key != "prompt":
            result[key] = result[key].strip()
    result["size"] = result["size"].lower()
    result["request_timeout"] = 300
    return result


def validate_image_generation_platform(data, *, require_api_key=False):
    """Return a detached provider configuration; errors never echo credentials."""
    result = normalize_image_generation_platform(data)
    if not result["name"]:
        raise ValueError("请输入生图接口名称。")
    if result["api_format"] not in ("DashScope", "VolcengineArk", "Gemini"):
        raise ValueError("请选择 DashScope、VolcengineArk 或 Gemini 图像编辑接口。")
    try:
        parsed = urlsplit(result["api_url"])
        valid_url = (parsed.scheme in ("http", "https") and bool(parsed.hostname)
                     and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
                     and not any(character.isspace() for character in result["api_url"]))
        _ = parsed.port
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("请输入不含账号、密码、查询参数或片段的 HTTP(S) 接口地址。")
    if not result["model"]:
        raise ValueError("请输入生图模型名称。")
    if any(character in result["api_key"] for character in "\r\n"):
        raise ValueError("生图接口密钥不能包含换行。")
    if require_api_key and not result["api_key"]:
        raise ValueError("请先填写并保存接口密钥，再激活此生图接口。")
    if result["api_format"] == "Gemini":
        validate_gemini_connection(result["api_url"], result["model"], result["api_key"])
    if type(result["prompt_extend"]) is not bool:
        raise ValueError("自动改写必须是开启或关闭。")
    seed = result["seed"]
    if seed is not None and (type(seed) is not int or not 0 <= seed <= MAX_SEED):
        raise ValueError("随机种子必须留空或填写 0 至 2147483647 的整数。")
    result["size"] = normalize_generation_size(result["size"], result["api_format"])
    return result


def build_image_generation_config_update(config, platform_id, platform=None, *, action="save"):
    """Patch only owned keys and retain concurrently loaded advanced fields."""
    if not isinstance(config, dict) or not isinstance(platform_id, str) or not platform_id.strip():
        raise ValueError("生图配置或接口标识无效。")
    providers = config.get("image_generation_platforms", {})
    if not isinstance(providers, dict):
        raise ValueError("生图接口列表必须是对象。")
    providers = copy.deepcopy(providers)
    active = config.get("active_image_generation_platform", "")
    if not isinstance(active, str):
        raise ValueError("激活的生图接口标识必须是文本。")
    if action == "save":
        if not isinstance(platform, dict):
            raise ValueError("请提供需要保存的生图接口配置。")
        previous = providers.get(platform_id, {})
        if not isinstance(previous, dict):
            raise ValueError("已有生图接口配置无效。")
        providers[platform_id] = validate_image_generation_platform({**previous, **platform})
    elif action == "activate":
        if platform_id not in providers:
            raise ValueError("生图接口不存在，请刷新页面。")
        providers[platform_id] = validate_image_generation_platform(providers[platform_id], require_api_key=True)
        active = platform_id
    elif action == "delete":
        if platform_id not in providers:
            raise ValueError("生图接口不存在，请刷新页面。")
        del providers[platform_id]
        if active == platform_id:
            active = ""
    else:
        raise ValueError("未知的生图配置操作。")
    return {"image_generation_platforms": providers, "active_image_generation_platform": active}
