"""Native DashScope image-editing request and separate unauthenticated download.

One paid POST only. A timeout or malformed successful response has an unknown
billing outcome; the caller must persist that state rather than blindly retry.
"""
import base64
import io
import json
import math
import re
import warnings
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image

from Backend.application.pipeline_common import PipelineError

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
MAX_DOWNLOAD_PIXELS = 16_777_216


def safe_message(error, key=""):
    from Backend.core.log_system import redact
    message = str(error)
    if key:
        message = message.replace(key, "[REDACTED]")
    return re.sub(r"https?://\S+", "[URL]", redact(message))[:1200]


def _https_url(value):
    try:
        parsed = urlsplit(value)
        if not isinstance(value, str) or len(value) > 16000 or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError()
        _ = parsed.port
    except (ValueError, TypeError):
        raise PipelineError("IMAGE_GENERATION_INVALID_URL", "生图结果缺少有效HTTPS下载地址", 502) from None
    return value


def _usage(payload):
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    result = {key: value for key, value in usage.items()
              if key in ("input_tokens", "output_tokens", "total_tokens", "image_count", "image_tokens", "output_image_tokens",
                         "input_image_count", "output_image_count", "width", "height", "input_width", "input_height", "output_width", "output_height")
              and type(value) in (int, float) and math.isfinite(value) and value >= 0}
    for key in ("input_image_type", "output_image_type"):
        value = usage.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_]{1,64}", value):
            result[key] = value
    return result


def _request_id(payload):
    value = payload.get("request_id", "") if isinstance(payload, dict) else ""
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{0,128}", value) else ""


def parse_generation_response(payload):
    if not isinstance(payload, dict):
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图响应结构无效，请先检查请求记录再决定是否重新生成", 502)
    request_id = _request_id(payload)
    details = {"request_id": request_id, "usage": _usage(payload)}
    if payload.get("code"):
        raise PipelineError("IMAGE_GENERATION_REJECTED", "生图服务拒绝请求，请检查模型、密钥、额度与输入参数", 502, details)
    output = payload.get("output")
    choices = output.get("choices") if isinstance(output, dict) else None
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图没有返回唯一图片，请检查请求记录后再决定是否重新生成", 502, details)
    message = choices[0].get("message")
    contents = message.get("content") if isinstance(message, dict) else None
    if not isinstance(contents, list):
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图结果结构无效", 502, details)
    images = [part["image"] for part in contents if isinstance(part, dict) and part.get("image")]
    if len(images) != 1:
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图没有返回唯一图片", 502, details)
    try:
        url = _https_url(images[0])
    except PipelineError:
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图下载地址无效，请检查请求记录", 502, details) from None
    return {"result_url": url, **details}


def request_generation(image_bytes, *, prompt, size, config, client=None):
    if not image_bytes or len(image_bytes) > MAX_INPUT_BYTES:
        raise PipelineError("IMAGE_GENERATION_INPUT_TOO_LARGE", "提交图片超过10MiB限制", 422)
    parameters = {"n": 1, "size": size, "prompt_extend": True, "watermark": config["watermark"]}
    if config.get("seed") is not None:
        parameters["seed"] = config["seed"]
    payload = {"model": config["model"], "input": {"messages": [{"role": "user", "content": [
        {"image": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")}, {"text": prompt}]}]}, "parameters": parameters}
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(config["request_timeout"], connect=30), follow_redirects=False)
    try:
        with client.stream("POST", config["api_url"], json=payload,
                           headers={"Authorization": f"Bearer {config['api_key']}"}) as response:
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图响应超过接收上限，请检查请求记录", 502)
            try:
                document = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图响应不是有效JSON，请检查请求记录", 502) from None
            if response.status_code >= 500 or response.status_code in (408,):
                raise PipelineError("IMAGE_GENERATION_UNKNOWN", "生图服务未确认生成结果，请检查请求记录，勿自动重发", 502,
                                    {"request_id": _request_id(document), "usage": _usage(document) if isinstance(document, dict) else {}})
            if response.is_error:
                raise PipelineError("IMAGE_GENERATION_REJECTED", f"生图服务拒绝请求（HTTP {response.status_code}），请检查接口配置和额度", 502,
                                    {"request_id": _request_id(document), "usage": _usage(document) if isinstance(document, dict) else {}})
            result = parse_generation_response(document)
            if config["api_key"] in json.dumps(result):
                raise PipelineError("IMAGE_GENERATION_UNKNOWN", "服务返回了不安全的结果地址", 502)
            return result
    except PipelineError as error:
        # A malformed provider may echo credentials even in a normally safe
        # field such as request_id; never persist that echo in recovery state.
        if config["api_key"] in json.dumps(error.details, ensure_ascii=False):
            error.details = None
        raise
    except httpx.HTTPError as error:
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", f"生图请求结果未知（{type(error).__name__}），请先检查请求记录；显式重新生成可能再次计费", 502) from None
    finally:
        if owned:
            client.close()


def download_image(url, *, client=None):
    url = _https_url(url)
    owned = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=False)
    try:
        for redirect in range(6):
            request = client.build_request("GET", url)
            request.headers.pop("authorization", None)
            response = client.send(request, stream=True, auth=None, follow_redirects=False)
            try:
                if response.is_redirect:
                    if redirect == 5 or not response.headers.get("location"):
                        raise PipelineError("IMAGE_GENERATION_DOWNLOAD_FAILED", "生图下载重定向过多", 502)
                    url = _https_url(urljoin(url, response.headers["location"]))
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_DOWNLOAD_BYTES:
                        raise PipelineError("IMAGE_GENERATION_DOWNLOAD_FAILED", "生成图片超过64MiB下载限制", 502)
                break
            finally:
                response.close()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ("PNG", "JPEG", "WEBP") or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("not a static supported image")
                if image.width * image.height > MAX_DOWNLOAD_PIXELS:
                    raise ValueError("too many pixels")
                image.load()
                converted = image.convert("RGBA" if image.mode in ("RGBA", "LA") or "transparency" in image.info else "RGB")
                output = io.BytesIO()
                converted.save(output, format="PNG")
                return {"data": output.getvalue(), "width": image.width, "height": image.height, "format": "png"}
    except PipelineError:
        raise
    except (httpx.HTTPError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise PipelineError("IMAGE_GENERATION_DOWNLOAD_FAILED", f"生成图片下载或校验失败（{type(error).__name__}），可继续仅重试下载", 502) from None
    finally:
        if owned:
            client.close()
