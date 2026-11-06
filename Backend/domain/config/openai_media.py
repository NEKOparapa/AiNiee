"""Connection validation for OpenAI-compatible media endpoints."""
from urllib.parse import urlsplit


def openai_media_endpoint(api_url, route):
    try:
        address = urlsplit(api_url)
        valid = (address.scheme in ("http", "https") and address.hostname
                 and not (address.username or address.password or address.query or address.fragment)
                 and not any(char.isspace() or ord(char) < 32 for char in api_url))
        _ = address.port
        path = address.path.rstrip("/")
        valid = valid and (not path or path.endswith("/v1") or path.endswith(route))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("OpenAI 请填写 API 基地址（可含 /v1）或对应的完整接口地址。")
    base = api_url.rstrip("/")
    return base if path.endswith(route) else base + ("" if path.endswith("/v1") else "/v1") + route


def validate_openai_key(key):
    if not isinstance(key, str) or any(not 33 <= ord(char) <= 126 for char in key):
        raise ValueError("OpenAI API Key 必须是不含空白的 ASCII 文本。")
