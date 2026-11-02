"""Pure validation for image-editing providers, independent of OCR credentials."""
import copy
import re
from urllib.parse import urlsplit


DEFAULT_IMAGE_GENERATION_PLATFORM = {
    "name": "百炼图像编辑",
    "api_format": "DashScope",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "",
    "model": "qwen-image-3.0-pro",
    "request_timeout": 600,
    "prompt_extend": True,
    "seed": None,
    "size": "auto",
    "prompt": "",
}
MIN_REQUEST_TIMEOUT = 10
MAX_REQUEST_TIMEOUT = 3600
MAX_SEED = 2147483647


def normalize_image_generation_platform(data=None):
    if data is not None and not isinstance(data, dict):
        raise ValueError("生图接口配置必须是对象。")
    result = copy.deepcopy(DEFAULT_IMAGE_GENERATION_PLATFORM)
    result.update(copy.deepcopy(data or {}))
    for key in ("name", "api_format", "api_url", "api_key", "model", "size", "prompt"):
        if not isinstance(result[key], str):
            raise ValueError("生图接口的文本字段必须是字符串。")
        if key != "prompt":
            result[key] = result[key].strip()
    result["size"] = result["size"].lower()
    timeout = result["request_timeout"]
    if type(timeout) is float and timeout.is_integer():
        result["request_timeout"] = int(timeout)
    return result


def validate_image_generation_platform(data, *, require_api_key=False):
    """Return a detached provider configuration; errors never echo credentials."""
    result = normalize_image_generation_platform(data)
    if not result["name"]:
        raise ValueError("请输入生图接口名称。")
    if result["api_format"] != "DashScope":
        raise ValueError("目前仅支持 DashScope 图像编辑接口。")
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
    if type(result["request_timeout"]) is not int or not MIN_REQUEST_TIMEOUT <= result["request_timeout"] <= MAX_REQUEST_TIMEOUT:
        raise ValueError("生图请求超时必须是 10 至 3600 的整数。")
    if type(result["prompt_extend"]) is not bool:
        raise ValueError("自动改写必须是开启或关闭。")
    seed = result["seed"]
    if seed is not None and (type(seed) is not int or not 0 <= seed <= MAX_SEED):
        raise ValueError("随机种子必须留空或填写 0 至 2147483647 的整数。")
    size = result["size"]
    if size != "auto":
        if len(size) > 32 or not re.fullmatch(r"[1-9]\d*\s*\*\s*[1-9]\d*", size, flags=re.ASCII):
            raise ValueError("输出尺寸必须为 auto 或 WIDTH*HEIGHT（宽高均为正整数）。")
        width, height = (int(part.strip()) for part in size.split("*"))
        if (width % 16 or height % 16 or not 512 ** 2 <= width * height <= 2048 ** 2
                or max(width, height) / min(width, height) > 8):
            raise ValueError("输出宽高需为16的倍数，总像素为512²至2048²，宽高比不超过8。")
        result["size"] = f"{width}*{height}"
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
