"""Prepare a source image and explicit translation instructions, without OCR."""
import hashlib
import io
import math

from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.image_generation_config import validate_size
from Backend.infrastructure.image_generation.artifacts import digest
from Backend.infrastructure.image_generation.dashscope import MAX_INPUT_BYTES as DASHSCOPE_MAX_INPUT_BYTES
from Backend.infrastructure.image_generation.volcengine_ark import MAX_INPUT_BYTES as ARK_MAX_INPUT_BYTES
from Backend.infrastructure.image_generation.gemini import MAX_INPUT_BYTES as GEMINI_MAX_INPUT_BYTES

_LANGUAGES = {"auto": "图中原文的语言", "japanese": "日语", "chinese_simplified": "简体中文",
              "chinese_traditional": "繁体中文", "english": "英语", "korean": "韩语"}


def output_size(width, height, requested="auto", api_format="DashScope"):
    if api_format == "Gemini":
        return validate_size(requested, api_format)
    if requested not in (None, "auto"):
        return validate_size(requested, api_format)
    is_ark = api_format == "VolcengineArk"
    min_pixels, max_pixels, max_ratio = (921600, 4624220, 16) if is_ark else (512 ** 2, 2048 ** 2, 8)
    if max(width, height) / min(width, height) > max_ratio:
        raise PipelineError("IMAGE_GENERATION_SIZE_UNSUPPORTED", f"此接口自动尺寸不支持宽高比超过{max_ratio}的长图，请拆分图片或显式指定尺寸", 422)
    area = width * height
    factor = math.sqrt(min(max_pixels, max(min_pixels, area)) / area)
    width, height = max(16, round(width * factor / 16) * 16), max(16, round(height * factor / 16) * 16)
    while width * height > max_pixels or (is_ark and max(width, height) / min(width, height) > max_ratio):
        if width >= height:
            width -= 16
        else:
            height -= 16
    while width * height < min_pixels or (not is_ark and max(width, height) / min(width, height) > max_ratio):
        if width <= height:
            width += 16
        else:
            height += 16
    return validate_size(f"{width}*{height}", api_format)


def prepare_generation(file, image, config):
    is_ark = config.api_format == "VolcengineArk"
    is_gemini = config.api_format == "Gemini"
    if is_ark:
        if min(image.size) <= 14 or image.width * image.height > 36_000_000 or max(image.size) / min(image.size) > 16:
            raise PipelineError("IMAGE_GENERATION_INPUT_TOO_LARGE", "火山生图输入宽高需大于14，总像素不超过3600万，宽高比不超过16", 422)
    elif not is_gemini and (max(image.size) > 8000 or max(image.size) / min(image.size) > 10):
        raise PipelineError("IMAGE_GENERATION_INPUT_TOO_LARGE", "生图输入边长不能超过8000，宽高比不能超过10", 422)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    data = stream.getvalue()
    max_bytes = ARK_MAX_INPUT_BYTES if is_ark else GEMINI_MAX_INPUT_BYTES if is_gemini else DASHSCOPE_MAX_INPUT_BYTES
    if len(data) > max_bytes:
        raise PipelineError("IMAGE_GENERATION_INPUT_TOO_LARGE", f"规范化图片超过{max_bytes // (1024 * 1024)}MiB，请先缩小图片", 422)
    size = output_size(*image.size, config.size, config.api_format)
    source = _LANGUAGES.get(config.source_language, config.source_language)
    target = _LANGUAGES.get(config.target_language, config.target_language)
    source_text = "文字" if config.source_language == "auto" else f"{source}文字"
    text_source, text_identity = "none", digest([])
    prompt = (
        f"任务：把这张漫画或插画页面中需要翻译的{source_text}译成{target}，擦除原字并将译文嵌回各自原位置。一次完成，只输出一张完整译图。\n"
        + config.translation_prompt
    )
    if config.prompt.strip():
        prompt += "\n用户补充要求：\n" + config.prompt.strip()
    if len(prompt) > 32000:
        raise PipelineError("IMAGE_GENERATION_PROMPT_TOO_LONG", "单张图片的提示词过长，请缩短补充要求", 422)
    settings = {key: getattr(config, key) for key in ("source_language", "target_language", "prompt", "translation_prompt")}
    # The complete submitted prompt already fingerprints the selected body.
    # Keep this subset stable so unchanged default prompts reuse older results.
    identity_settings = {key: settings[key] for key in ("source_language", "target_language", "prompt")}
    identity = {"version": 2, "source_sha256": file.source_ref["sha256"],
                "submitted_sha256": hashlib.sha256(data).hexdigest(), "provider_id": config.provider_id,
                "api_url": config.api_url, "model": config.model, "settings": identity_settings,
                "size": size, "seed": config.seed, "prompt_extend": config.prompt_extend,
                "watermark": config.watermark, "n": 1, "prompt": prompt,
                "text_source": text_source, "text_identity": text_identity}
    if is_ark:
        # Fingerprint only effective Ark options, so ignored values never
        # invalidate the generated artifact and trigger another charge.
        identity.update(api_format="VolcengineArk", seed=None, prompt_extend=None,
                        optimize_prompt_mode="standard", output_format="png")
    if is_gemini:
        identity.update(api_format="Gemini", seed=None, prompt_extend=None, watermark=None,
                        response_modalities=["IMAGE"])
    return {"data": data, "size": size, "prompt": prompt, "identity": identity,
            "fingerprint": digest(identity), "text_source": text_source, "text_identity": text_identity,
            "settings": settings}
