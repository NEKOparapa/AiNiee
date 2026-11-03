"""Native Gemini image editing via one generateContent request.

References: https://ai.google.dev/api/generate-content
            https://ai.google.dev/gemini-api/docs/generate-content/image-generation
Inline images are validated here and returned as PNG bytes, never as fake URLs.
"""
import base64
import binascii
import io
import json
import re
import warnings

import httpx
from PIL import Image

from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.image_generation_config import gemini_endpoint, validate_size

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_RESPONSE_BYTES = 90 * 1024 * 1024
MAX_OUTPUT_PIXELS = 24_000_000
_BLOCKED = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII",
            "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT", "IMAGE_RECITATION", "ESCALATION"}


def _details(payload, key=""):
    if not isinstance(payload, dict):
        return {"request_id": "", "usage": {}}
    identifier = payload.get("responseId", "")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{0,128}", identifier) or key and key in identifier:
        identifier = ""
    usage = payload.get("usageMetadata")
    usage = usage if isinstance(usage, dict) else {}
    names = {"promptTokenCount": "input_tokens", "candidatesTokenCount": "output_tokens",
             "totalTokenCount": "total_tokens", "thoughtsTokenCount": "thought_tokens"}
    return {"request_id": identifier, "usage": {target: usage[source] for source, target in names.items()
            if type(usage.get(source)) is int and 0 <= usage[source] <= 10 ** 18}}


def _unknown(message, details=None):
    return PipelineError("IMAGE_GENERATION_UNKNOWN", message + "，请检查请求记录后再决定是否重新生成", 502, details)


def decode_image(inline, details=None):
    if not isinstance(inline, dict) or inline.get("mimeType") not in ("image/png", "image/jpeg", "image/webp"):
        raise _unknown("Gemini返回了不支持的图片类型", details)
    encoded = inline.get("data")
    if not isinstance(encoded, str) or not encoded or len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise _unknown("Gemini图片数据为空或超过接收上限", details)
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("image byte limit")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                actual_mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image.format)
                if actual_mime != inline["mimeType"] or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("invalid image format")
                if image.width * image.height > MAX_OUTPUT_PIXELS:
                    raise ValueError("image pixel limit")
                image.load()
                converted = image.convert("RGBA" if image.mode in ("RGBA", "LA") or "transparency" in image.info else "RGB")
                output = io.BytesIO()
                converted.save(output, format="PNG")
                data = output.getvalue()
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError("normalized byte limit")
                return {"data": data, "width": image.width, "height": image.height, "format": "png"}
    except (ValueError, OSError, binascii.Error, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _unknown("Gemini返回的图片无法解码或尺寸不安全", details) from None


def parse_generation_response(payload, *, key=""):
    details = _details(payload, key)
    if not isinstance(payload, dict):
        raise _unknown("Gemini生图响应结构无效", details)
    feedback = payload.get("promptFeedback")
    blocked = isinstance(feedback, dict) and feedback.get("blockReason") not in (None, "BLOCK_REASON_UNSPECIFIED")
    if payload.get("error") or blocked:
        raise PipelineError("IMAGE_GENERATION_REJECTED", "Gemini未生成图片，请检查内容限制、模型权限和额度", 502, details)
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
        raise _unknown("Gemini没有返回唯一候选结果", details)
    candidate = candidates[0]
    reason = candidate.get("finishReason")
    if reason is not None and not isinstance(reason, str):
        raise _unknown("Gemini返回的完成状态无效", details)
    if reason in _BLOCKED:
        raise PipelineError("IMAGE_GENERATION_REJECTED", "Gemini因内容限制未返回译图", 502, details)
    if reason not in (None, "STOP"):
        raise _unknown("Gemini图片生成未正常完成", details)
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise _unknown("Gemini图片响应结构无效", details)
    # Reasoning images are not the final output. Do not choose one arbitrarily
    # if the service returns more than one final image for a single page.
    images = [part["inlineData"] for part in parts if isinstance(part, dict)
              and not part.get("thought") and "inlineData" in part]
    if len(images) != 1:
        raise _unknown("Gemini没有返回唯一的最终图片", details)
    return {"inline_image": decode_image(images[0], details), **details}


def request_generation(image_bytes, *, prompt, size, config, client=None):
    if not image_bytes or len(image_bytes) > MAX_INPUT_BYTES:
        raise PipelineError("IMAGE_GENERATION_INPUT_TOO_LARGE", "提交图片超过Gemini生图10MiB限制", 422)
    endpoint = gemini_endpoint(config["api_url"], config["model"])
    size = validate_size(size, "Gemini")
    key = config["api_key"]
    if not isinstance(key, str) or not key or any(not 33 <= ord(char) <= 126 for char in key):
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "Gemini API密钥必须为不含空白的有效文本", 422)
    generation_config = {"responseModalities": ["IMAGE"]}
    if size != "auto":
        generation_config["imageConfig"] = {"imageSize": size}
    payload = {"contents": [{"role": "user", "parts": [
        {"text": prompt}, {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(image_bytes).decode("ascii")}}]}],
        "generationConfig": generation_config}
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(config["request_timeout"], connect=30), follow_redirects=False)
    try:
        with client.stream("POST", endpoint, json=payload, headers={"x-goog-api-key": key}, follow_redirects=False) as response:
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise _unknown("Gemini生图响应超过接收上限")
            try:
                document = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                raise _unknown("Gemini生图响应不是有效JSON") from None
            details = _details(document, key)
            if response.is_redirect or response.status_code >= 500 or response.status_code == 408:
                raise _unknown("Gemini服务未确认生成结果，勿自动重发", details)
            if response.is_error:
                raise PipelineError("IMAGE_GENERATION_REJECTED", f"Gemini拒绝请求（HTTP {response.status_code}），请检查接口配置和额度", 502, details)
            return parse_generation_response(document, key=key)
    except httpx.HTTPError as error:
        raise _unknown(f"Gemini生图请求结果未知（{type(error).__name__}）") from None
    finally:
        if owned:
            client.close()
