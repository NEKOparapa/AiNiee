"""OpenAI image edits: one multipart upload, inline output or resumable URL."""
import base64
import binascii
import io
import json
import re
import warnings

import httpx
from PIL import Image

from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.image_generation_config import validate_size
from Backend.domain.config.openai_media import openai_media_endpoint
from Backend.infrastructure.image_generation.dashscope import _https_url


MAX_INPUT_BYTES = 50_000_000
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_RESPONSE_BYTES = 90 * 1024 * 1024
MAX_OUTPUT_PIXELS = 24_000_000


def _unknown(message, details=None):
    return PipelineError("IMAGE_GENERATION_UNKNOWN", message + "，请检查请求记录后再决定是否重新生成", 502, details)


def _details(payload, request_id="", key=""):
    if not re.fullmatch(r"[A-Za-z0-9_-]{0,128}", request_id) or key and key in request_id:
        request_id = ""
    usage = payload.get("usage") if isinstance(payload, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    return {"request_id": request_id, "usage": {name: usage[name] for name in
            ("input_tokens", "output_tokens", "total_tokens")
            if type(usage.get(name)) is int and 0 <= usage[name] <= 10 ** 18}}


def _decode_image(encoded, details):
    if not isinstance(encoded, str) or not encoded or len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise _unknown("OpenAI 图片数据为空或超过接收上限", details)
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("byte limit")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if (image.format not in ("PNG", "JPEG", "WEBP") or getattr(image, "n_frames", 1) != 1
                        or image.width * image.height > MAX_OUTPUT_PIXELS):
                    raise ValueError("image format or pixel limit")
                image.load()
                converted = image.convert("RGBA" if image.mode in ("RGBA", "LA") or "transparency" in image.info else "RGB")
                output = io.BytesIO()
                converted.save(output, format="PNG")
                data = output.getvalue()
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError("normalized byte limit")
                return {"data": data, "width": image.width, "height": image.height, "format": "png"}
    except (ValueError, OSError, binascii.Error, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _unknown("OpenAI 返回的图片无法解码或尺寸不安全", details) from None


def parse_generation_response(payload, *, request_id="", key=""):
    details = _details(payload, request_id, key)
    if not isinstance(payload, dict):
        raise _unknown("OpenAI 生图响应结构无效", details)
    if payload.get("error"):
        raise PipelineError("IMAGE_GENERATION_REJECTED", "OpenAI 拒绝生图请求，请检查模型、参数及额度", 502, details)
    images = payload.get("data")
    if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
        raise _unknown("OpenAI 生图没有返回唯一图片", details)
    row = images[0]
    if row.get("b64_json") is not None:
        return {"inline_image": _decode_image(row["b64_json"], details), **details}
    try:
        url = _https_url(row.get("url"))
    except PipelineError:
        raise _unknown("OpenAI 生图未返回有效图片或下载地址", details) from None
    if key and key in url:
        raise _unknown("OpenAI 返回了不安全的结果地址", details)
    return {"result_url": url, **details}


def request_generation(image_bytes, *, prompt, size, config, client=None):
    if not isinstance(image_bytes, bytes) or not image_bytes or len(image_bytes) >= MAX_INPUT_BYTES:
        raise PipelineError("IMAGE_GENERATION_INPUT_TOO_LARGE", "OpenAI 输入图片必须小于 50 MB", 422)
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 32000:
        raise PipelineError("IMAGE_GENERATION_PROMPT_TOO_LONG", "OpenAI 图片提示词需为 1 至 32000 字", 422)
    endpoint = openai_media_endpoint(config["api_url"], "/images/edits")
    # GPT Image returns b64_json by default; response_format is not sent.
    # Provider-specific seed/watermark/prompt_extend must not leak into this API.
    data = {"model": config["model"], "prompt": prompt, "n": "1",
            "size": validate_size(size, "OpenAI"), "output_format": "png"}
    key = config["api_key"]
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(config["request_timeout"], connect=30), follow_redirects=False)
    try:
        with client.stream("POST", endpoint, headers={"Authorization": f"Bearer {key}"}, data=data,
                           files={"image": ("image.png", image_bytes, "image/png")}, follow_redirects=False) as response:
            request_id = response.headers.get("x-request-id", "")
            details = _details({}, request_id, key)
            if response.status_code >= 500 or response.status_code == 408 or response.is_redirect:
                raise _unknown("OpenAI 生图服务未确认生成结果，勿自动重发", details)
            if response.is_error:
                raise PipelineError("IMAGE_GENERATION_REJECTED", f"OpenAI 拒绝生图请求（HTTP {response.status_code}），请检查配置和额度",
                                    502, details)
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise _unknown("OpenAI 生图响应超过接收上限", details)
            try:
                payload = json.loads(content)
            except (ValueError, UnicodeError):
                raise _unknown("OpenAI 生图响应不是有效 JSON", details) from None
            return parse_generation_response(payload, request_id=request_id, key=key)
    except httpx.HTTPError as error:
        raise _unknown(f"OpenAI 生图请求结果未知（{type(error).__name__}），未自动重发") from None
    finally:
        if owned:
            client.close()
