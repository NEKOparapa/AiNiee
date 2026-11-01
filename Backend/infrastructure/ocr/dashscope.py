"""Qwen-OCR native HTTP adapter. No desktop, ASR, or translation dependencies.

Protocol: https://help.aliyun.com/zh/model-studio/qwen-vl-ocr-api-reference
Advanced recognition returns words_info with location or rotate_rect geometry.
"""
import base64
import json
import math
import re

import httpx

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError


MAX_IMAGE_BYTES = 7 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def _invalid(message="OCR 返回的文字坐标无效"):
    return PipelineError("OCR_INVALID_RESPONSE", message, 502)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _invalid()
    return float(value)


def validate_polygon(points, width, height):
    if not isinstance(points, (list, tuple)) or not 3 <= len(points) <= 64:
        raise _invalid()
    polygon = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise _invalid()
        x, y = map(_number, point)
        # OCR rounding can put an edge at -1 px. Larger excursions indicate a
        # different coordinate frame and must never be used as an erase mask.
        if not -2 <= x <= width + 2 or not -2 <= y <= height + 2:
            raise _invalid("OCR 坐标超出提交图片范围，未执行擦字")
        polygon.append([round(max(0, min(width, x)), 4), round(max(0, min(height, y)), 4)])
    area = abs(sum(polygon[i][0] * polygon[(i + 1) % len(polygon)][1]
                   - polygon[(i + 1) % len(polygon)][0] * polygon[i][1] for i in range(len(polygon)))) / 2
    if area < 1:
        raise _invalid("OCR 返回了空文字区域")
    if len({tuple(point) for point in polygon}) != len(polygon):
        raise _invalid("OCR 返回了重复的区域顶点")
    # A self-intersecting contour can still have a nonzero shoelace area. Such
    # a contour has no unambiguous text interior, so never pass it to erasure.
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, p):
        return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])

    for i in range(len(polygon)):
        a, b = polygon[i], polygon[(i + 1) % len(polygon)]
        for j in range(i + 1, len(polygon)):
            if j == i + 1 or (i == 0 and j == len(polygon) - 1):
                continue
            c, d = polygon[j], polygon[(j + 1) % len(polygon)]
            ab_c, ab_d, cd_a, cd_b = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
            if ((ab_c * ab_d < 0 and cd_a * cd_b < 0)
                    or (ab_c == 0 and on_segment(a, b, c)) or (ab_d == 0 and on_segment(a, b, d))
                    or (cd_a == 0 and on_segment(c, d, a)) or (cd_b == 0 and on_segment(c, d, b))):
                raise _invalid("OCR 返回了自交的文字区域")
    return polygon


def _line(row, width, height):
    if not isinstance(row, dict) or not isinstance(row.get("text"), str):
        raise _invalid("OCR 文字行格式无效")
    text = row["text"].strip()
    if not text:
        return None
    rotation = 0.0
    rect = row.get("rotate_rect")
    if rect is not None:
        if not isinstance(rect, list) or len(rect) != 5:
            raise _invalid()
        cx, cy, w, h, rotation = map(_number, rect)
        if w <= 0 or h <= 0 or not -90 <= rotation <= 90:
            raise _invalid()
        angle = math.radians(rotation)
        points = [[cx + x * math.cos(angle) - y * math.sin(angle), cy + x * math.sin(angle) + y * math.cos(angle)]
                  for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
    else:
        points = None
    location = row.get("location", row.get("polygon"))
    if location is not None:
        if isinstance(location, list) and len(location) == 8 and not isinstance(location[0], (list, tuple)):
            points = [location[i:i + 2] for i in range(0, 8, 2)]
        else:
            points = location
    polygon = validate_polygon(points, width, height)
    xs, ys = zip(*polygon)
    direction = "vertical" if max(ys) - min(ys) > 1.25 * (max(xs) - min(xs)) else "horizontal"
    # Equivalent rotated rectangles may exchange width/height and add 90deg.
    # Derive the skew from the actual polygon instead of exposing that arbitrary
    # representation as a text rotation. Upright horizontal AND vertical text
    # both have zero skew; writing direction is a separate field.
    edges = [(polygon[(i + 1) % len(polygon)][0] - p[0], polygon[(i + 1) % len(polygon)][1] - p[1])
             for i, p in enumerate(polygon)]
    dx, dy = max(edges, key=lambda edge: edge[0] ** 2 + edge[1] ** 2)
    skew = (math.degrees(math.atan2(dy, dx)) + 90) % 180 - 90
    if direction == "vertical":
        skew = skew - 90 if skew >= 0 else skew + 90
    result = {"text": text, "polygon": polygon, "rotation": round(skew, 4), "direction": direction}
    if rect is not None:
        result["provider_rotation"] = rotation
    # Qwen's common response does not include confidence. Omit rather than
    # inventing one or confusing token probability with line confidence.
    if "confidence" in row:
        confidence = _number(row["confidence"])
        if not 0 <= confidence <= 1:
            raise _invalid("OCR 置信度不在 0 至 1 范围")
        result["confidence"] = confidence
    return result


def parse_response(payload, image_width, image_height):
    if not isinstance(payload, dict) or payload.get("code"):
        raise _invalid("OCR 服务返回错误，未生成文字区域")
    output = payload.get("output")
    choices = output.get("choices") if isinstance(output, dict) else None
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise _invalid("OCR 响应缺少唯一识别结果")
    choice = choices[0]
    if choice.get("finish_reason") not in (None, "stop") or output.get("finish_reason") not in (None, "stop"):
        raise PipelineError("OCR_INCOMPLETE_RESPONSE", "OCR 输出被截断或未正常完成，请增加输出上限或缩小图片", 502)
    message = choice.get("message")
    contents = message.get("content") if isinstance(message, dict) else None
    if not isinstance(contents, list):
        raise _invalid()
    results, texts = [], []
    for content in contents:
        if not isinstance(content, dict):
            raise _invalid()
        if "ocr_result" in content and content["ocr_result"] is not None:
            value = content["ocr_result"]
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (ValueError, TypeError):
                    raise _invalid("OCR 结构化结果不是有效 JSON") from None
            results.append(value)
        if isinstance(content.get("text"), str) and content["text"].strip():
            texts.append(content["text"])
    if not results and texts:
        value = "".join(texts).strip()
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value).strip()
        try:
            results = [json.loads(value)]
        except ValueError:
            raise _invalid("OCR 只返回了纯文本，缺少回填所需坐标") from None
    if not results:
        raise _invalid("OCR 响应没有文字区域结果；无字图片也需要 words_info 空数组")
    rows = []
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("words_info"), list):
            raise _invalid("OCR 响应缺少 words_info 数组")
        rows.extend(result["words_info"])
    if len(rows) > 10000:
        raise _invalid("OCR 返回过多文字区域")
    lines = []
    for row in rows:
        item = _line(row, image_width, image_height)
        if item:
            lines.append(item)
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    safe_usage = {key: usage[key] for key in ("input_tokens", "output_tokens", "total_tokens")
                  if type(usage.get(key)) is int and usage[key] >= 0}
    request_id = payload.get("request_id", "")
    request_id = request_id if isinstance(request_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{0,128}", request_id) else ""
    return {"lines": lines, "usage": safe_usage, "request_id": request_id, "warnings": []}


def request_ocr(image_bytes, *, image_width, image_height, config, context=None, client=None):
    return _request(image_bytes, image_width=image_width, image_height=image_height, config=config,
                    context=context, client=client, task="advanced_recognition", parser=parse_response)


def parse_text_response(payload, image_width=None, image_height=None):
    """Native multi_lan returns processed_text, not trustworthy new geometry."""
    if not isinstance(payload, dict) or payload.get("code"):
        raise _invalid("OCR 原文复核服务返回错误")
    output = payload.get("output")
    choices = output.get("choices") if isinstance(output, dict) else None
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise _invalid("OCR 原文复核缺少唯一结果")
    choice = choices[0]
    if choice.get("finish_reason") != "stop" or output.get("finish_reason") not in (None, "stop"):
        raise PipelineError("OCR_INCOMPLETE_RESPONSE", "OCR 原文复核输出被截断或未正常结束", 502)
    message = choice.get("message")
    contents = message.get("content") if isinstance(message, dict) else None
    if not isinstance(contents, list) or not contents:
        raise _invalid("OCR 原文复核缺少文本")
    pieces = []
    for content in contents:
        if not isinstance(content, dict):
            raise _invalid("OCR 原文复核文本格式无效")
        structured = content.get("ocr_result")
        if isinstance(structured, str):
            try:
                structured = json.loads(structured)
            except ValueError:
                raise _invalid("OCR 原文复核结果格式无效") from None
        text = structured.get("processed_text") if isinstance(structured, dict) else None
        if text is None:
            text = content.get("text")
        if not isinstance(text, str):
            raise _invalid("OCR 原文复核缺少文本")
        pieces.append(text)
    value = "\n".join(pieces).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value or len(value) > 32768 or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise _invalid("OCR 原文复核文本为空、过长或包含无效控制字符")
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    safe_usage = {key: usage[key] for key in ("input_tokens", "output_tokens", "total_tokens")
                  if type(usage.get(key)) is int and usage[key] >= 0}
    request_id = payload.get("request_id", "")
    request_id = request_id if isinstance(request_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{0,128}", request_id) else ""
    return {"text": value, "usage": safe_usage, "request_id": request_id, "warnings": []}


def request_ocr_text(image_bytes, *, image_width, image_height, config, context=None, client=None):
    """Recheck a verified bubble crop with multi_lan; never emit coordinates."""
    return _request(image_bytes, image_width=image_width, image_height=image_height, config=config,
                    context=context, client=client, task="multi_lan", parser=parse_text_response)


def _request(image_bytes, *, image_width, image_height, config, context, client, task, parser):
    """Accept JPEG/PNG bytes and return text lines in submitted-image pixels.

    Cancellation prevents new attempts; an already sent paid request completes
    so the service can preserve its result. Redirects never forward the API key.
    """
    from Backend.domain.config.ocr_config import OCRConfig, resolve_ocr_config

    if not isinstance(config, (dict, OCRConfig)):
        raise PipelineError("OCR_CONFIG_ERROR", "OCR 请求配置必须为配置对象", 400)
    try:
        resolved = resolve_ocr_config(config if isinstance(config, OCRConfig) else OCRConfig(**config))
    except TypeError:
        raise PipelineError("OCR_CONFIG_ERROR", "OCR 请求配置包含不支持的字段", 400) from None
    if type(image_width) is not int or type(image_height) is not int or image_width <= 0 or image_height <= 0:
        raise PipelineError("OCR_INVALID_IMAGE", "OCR 图片尺寸无效", 400)
    if not isinstance(image_bytes, bytes) or not 0 < len(image_bytes) < MAX_IMAGE_BYTES:
        raise PipelineError("OCR_INVALID_IMAGE", "OCR 图片需小于 7 MB", 400)
    mime = "image/png" if image_bytes.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if image_bytes.startswith(b"\xff\xd8\xff") else None
    if mime is None:
        raise PipelineError("OCR_INVALID_IMAGE", "OCR 请求需使用 PNG 或 JPEG 图片", 400)
    context = context or ExecutionContext()
    body = {"model": resolved.model,
            "input": {"messages": [{"role": "user", "content": [{
                "image": f"data:{mime};base64," + base64.b64encode(image_bytes).decode("ascii"),
                "enable_rotate": False, "min_pixels": 3136, "max_pixels": resolved.max_pixels}]}]},
            "parameters": {"ocr_options": {"task": task}, "max_tokens": resolved.max_tokens}}
    owned = client is None
    client = client or httpx.Client(timeout=resolved.request_timeout, follow_redirects=False)
    attempts = 0
    try:
        for attempt in range(resolved.max_retries + 1):
            if context.is_cancelled():
                raise PipelineError("OCR_CANCELLED", "OCR 已取消", 409, {"attempts": attempts})
            attempts += 1
            try:
                response = client.post(resolved.api_url, json=body, headers={"Authorization": "Bearer " + resolved.api_key},
                                       timeout=resolved.request_timeout, follow_redirects=False)
            except (httpx.TimeoutException, httpx.RequestError):
                if attempt < resolved.max_retries:
                    if context.cancel_event.wait(min(2 ** attempt, 8)):
                        raise PipelineError("OCR_CANCELLED", "OCR 已取消", 409, {"attempts": attempts}) from None
                    continue
                raise PipelineError("OCR_NETWORK_ERROR", "OCR 请求超时或网络连接失败", 502, {"attempts": attempts}) from None
            if response.status_code != 200:
                if (response.status_code == 429 or response.status_code >= 500) and attempt < resolved.max_retries:
                    if context.cancel_event.wait(min(2 ** attempt, 8)):
                        raise PipelineError("OCR_CANCELLED", "OCR 已取消", 409, {"attempts": attempts})
                    continue
                raise PipelineError("OCR_HTTP_ERROR", f"OCR 服务返回 HTTP {response.status_code}", 502,
                                    {"attempts": attempts, "http_status": response.status_code})
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise _invalid("OCR 响应超过大小限制")
            try:
                payload = response.json()
            except (ValueError, UnicodeError):
                raise _invalid("OCR 服务未返回有效 JSON") from None
            result = parser(payload, image_width, image_height)
            return {**result, "attempts": attempts}
        raise PipelineError("OCR_NETWORK_ERROR", "OCR 请求失败", 502, {"attempts": attempts})
    except PipelineError as error:
        error.details = {**(error.details or {}), "attempts": attempts}
        raise
    finally:
        if owned:
            client.close()
