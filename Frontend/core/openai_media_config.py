"""Desktop validation mirrors the backend without importing server modules."""
from urllib.parse import urlsplit


def validate_openai_connection(api_url, api_key, kind):
    route = "/audio/transcriptions" if kind == "transcription" else "/images/edits"
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
    if not isinstance(api_key, str) or any(not 33 <= ord(char) <= 126 for char in api_key):
        raise ValueError("OpenAI API Key 必须是不含空白的 ASCII 文本。")
