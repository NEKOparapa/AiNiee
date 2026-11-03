"""Dispatch native image-generation protocols without retrying paid requests."""

from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.image_generation import dashscope, volcengine_ark, gemini
from Backend.infrastructure.image_generation.dashscope import download_image, safe_message


def request_generation(image_bytes, *, prompt, size, config, client=None):
    api_format = config.get("api_format", "DashScope")
    adapters = {"DashScope": dashscope, "VolcengineArk": volcengine_ark, "Gemini": gemini}
    if api_format not in adapters:
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "不支持的生图接口格式", 422)
    return adapters[api_format].request_generation(image_bytes, prompt=prompt, size=size, config=config, client=client)
