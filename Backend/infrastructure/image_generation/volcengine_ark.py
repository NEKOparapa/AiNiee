"""Native Seedream image editing: one paid POST, followed by resumable download."""

import base64
import json
import re

import httpx

from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.image_generation.dashscope import MAX_RESPONSE_BYTES, _https_url


MAX_INPUT_BYTES = 30 * 1024 * 1024


def _request_id(payload, header=""):
    value = header or (payload.get("request_id", "") if isinstance(payload, dict) else "")
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{0,128}", value) else ""


def _usage(payload):
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return {}
    return {key: value for key, value in usage.items()
            if key in ("input_images", "generated_images", "output_tokens", "total_tokens")
            and type(value) is int and 0 <= value <= 10 ** 18}


def parse_generation_response(payload, *, request_id=""):
    details = {"request_id": _request_id(payload, request_id), "usage": _usage(payload)}
    if not isinstance(payload, dict):
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "火山生图响应结构无效，请先检查请求记录再决定是否重新生成", 502, details)
    if payload.get("error"):
        raise PipelineError("IMAGE_GENERATION_REJECTED", "火山生图服务拒绝请求，请检查模型权限、密钥、额度与输入参数", 502, details)
    images = payload.get("data")
    if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "火山生图没有返回唯一图片，请检查请求记录后再决定是否重新生成", 502, details)
    if images[0].get("error"):
        raise PipelineError("IMAGE_GENERATION_REJECTED", "火山生图未生成图片，请检查内容限制与接口状态", 502, details)
    try:
        url = _https_url(images[0].get("url"))
    except PipelineError:
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", "火山生图下载地址无效，请检查请求记录", 502, details) from None
    return {"result_url": url, **details}


def request_generation(image_bytes, *, prompt, size, config, client=None):
    if not image_bytes or len(image_bytes) > MAX_INPUT_BYTES:
        raise PipelineError("IMAGE_GENERATION_INPUT_TOO_LARGE", "提交图片超过火山生图30MiB限制", 422)
    # Seedream 5.0 pro has its own optimization modes. It does not document
    # DashScope's prompt_extend or seed fields, so neither is sent to Ark.
    payload = {
        "model": config["model"], "prompt": prompt,
        "image": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
        "size": size, "response_format": "url", "output_format": "png",
        "watermark": config["watermark"], "optimize_prompt_options": {"mode": "standard"},
    }
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(config["request_timeout"], connect=30), follow_redirects=False)
    try:
        with client.stream("POST", config["api_url"], json=payload,
                           headers={"Authorization": f"Bearer {config['api_key']}"},
                           follow_redirects=False) as response:
            data = bytearray()
            request_id = response.headers.get("x-request-id", "")
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise PipelineError("IMAGE_GENERATION_UNKNOWN", "火山生图响应超过接收上限，请检查请求记录", 502,
                                        {"request_id": _request_id({}, request_id)})
            try:
                document = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                raise PipelineError("IMAGE_GENERATION_UNKNOWN", "火山生图响应不是有效JSON，请检查请求记录", 502,
                                    {"request_id": _request_id({}, request_id)}) from None
            details = {"request_id": _request_id(document, request_id), "usage": _usage(document)}
            if response.status_code >= 500 or response.status_code == 408 or response.is_redirect:
                raise PipelineError("IMAGE_GENERATION_UNKNOWN", "火山生图服务未确认生成结果，请检查请求记录，勿自动重发", 502, details)
            if response.is_error:
                raise PipelineError("IMAGE_GENERATION_REJECTED", f"火山生图服务拒绝请求（HTTP {response.status_code}），请检查接口配置和额度", 502, details)
            result = parse_generation_response(document, request_id=request_id)
            if config["api_key"] in json.dumps(result):
                raise PipelineError("IMAGE_GENERATION_UNKNOWN", "服务返回了不安全的结果地址", 502)
            return result
    except PipelineError as error:
        if config["api_key"] in json.dumps(error.details, ensure_ascii=False):
            error.details = None
        raise
    except httpx.HTTPError as error:
        raise PipelineError("IMAGE_GENERATION_UNKNOWN", f"火山生图请求结果未知（{type(error).__name__}），请先检查请求记录；显式重新生成可能再次计费", 502) from None
    finally:
        if owned:
            client.close()
