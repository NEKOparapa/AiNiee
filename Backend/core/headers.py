import json
import re


def normalize_extra_headers(raw) -> dict[str, str]:
    """Validate configured HTTP headers without including their values in errors."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("extra_headers must be a JSON object of strings")

    headers = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("extra_headers names and values must be strings")
        name = name.strip().lower()
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+", name):
            raise ValueError("extra_headers contains an invalid header name")
        if name in headers:
            raise ValueError("extra_headers contains duplicate header names")
        if any(ord(char) < 32 or ord(char) > 126 for char in value):
            raise ValueError("extra_headers values must contain printable ASCII only")
        headers[name] = value.strip()
    return headers


def parse_extra_headers(text: str) -> dict[str, str]:
    def unique_pairs(pairs):
        headers = {}
        for name, value in pairs:
            if name in headers:
                raise ValueError("extra_headers contains duplicate header names")
            headers[name] = value
        return headers

    raw = json.loads(text, object_pairs_hook=unique_pairs) if text.strip() else {}
    if not isinstance(raw, dict):
        raise ValueError("extra_headers must be a JSON object of strings")
    return normalize_extra_headers(raw)
