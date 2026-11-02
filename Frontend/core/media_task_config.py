"""Pure task settings for media translation, separate from provider credentials."""

import copy
import math

from Frontend.core.image_generation_config import MAX_SEED, normalize_generation_size
from Frontend.core.ocr_config import READING_ORDERS


DEFAULT_AUDIO_TRANSLATION_SETTINGS = {
    "language_hints": [],
    "speaker_diarization_enabled": False,
    "chunk_duration_seconds": 240,
    "chunk_overlap_seconds": 2,
    "chunk_concurrency": 3,
    "vad_threshold": 0.35,
    "export": {"format": "srt", "mode": "bilingual"},
}
DEFAULT_IMAGE_TRANSLATION_SETTINGS = {
    "ocr": {
        "reading_order": "auto",
        "group_lines": False,
        "refine_text": False,
    },
    "generation": {
        "size": "auto",
        "seed": None,
        "prompt_extend": True,
        "prompt": "",
        "watermark": False,
    },
    "export": {"format": "png"},
}
MEDIA_EXPORT_FORMATS = {"audio": ("srt", "vtt", "ass", "lrc"), "image": ("png", "jpeg", "webp")}
AUDIO_EXPORT_MODES = ("bilingual", "translated", "source")
SUPPORTED_LANGUAGE_HINTS = frozenset(
    "zh en ja ko vi th id ms tl hi ar fr de es pt ru it nl sv da fi no el pl cs hu ro bg hr sk".split()
)


def _require_object(value, message):
    if not isinstance(value, dict):
        raise ValueError(message)
    return value


def _merge_known(target, source):
    """Copy only the schema's keys; never carry provider credentials forward."""
    for key in target:
        if key in source:
            if isinstance(target[key], dict):
                _merge_known(target[key], _require_object(source[key], "媒体任务设置的配置分组必须是对象。"))
            else:
                target[key] = copy.deepcopy(source[key])
    return target


def _normalize_export_settings(values, kind):
    defaults = (DEFAULT_AUDIO_TRANSLATION_SETTINGS if kind == "audio" else DEFAULT_IMAGE_TRANSLATION_SETTINGS)["export"]
    result = _merge_known(copy.deepcopy(defaults), _require_object(values, "导出设置必须是对象。"))
    if not isinstance(result["format"], str) or result["format"] not in MEDIA_EXPORT_FORMATS[kind]:
        label = "字幕" if kind == "audio" else "图片"
        raise ValueError(f"{label}导出格式必须为 {'、'.join(MEDIA_EXPORT_FORMATS[kind])}。")
    if kind == "audio" and (not isinstance(result["mode"], str) or result["mode"] not in AUDIO_EXPORT_MODES):
        raise ValueError("字幕导出模式必须为 bilingual、translated 或 source。")
    return result


def read_media_export_settings(config, kind):
    """Read and validate export options only; unrelated task/provider values are ignored."""
    if not isinstance(kind, str) or kind not in MEDIA_EXPORT_FORMATS:
        raise ValueError("媒体类型必须为 audio 或 image。")
    _require_object(config, "媒体配置必须是对象。")
    section = _require_object(config.get(f"{kind}_translation_settings", {}), "媒体翻译设置必须是对象。")
    return _normalize_export_settings(section.get("export", {}), kind)


def _active_provider(config, providers_key, active_key):
    active = config.get(active_key, "")
    providers = config.get(providers_key, {})
    if not isinstance(active, str) or not active or not isinstance(providers, dict):
        return {}
    provider = providers.get(active)
    return provider if isinstance(provider, dict) else {}


def _merge_image_settings(target, source):
    for section in target:
        if section in source:
            values = _require_object(source[section], "图片翻译的识别、生成和导出设置必须是对象。")
            _merge_known(target[section], values)
    return target


def read_audio_translation_settings(config):
    """Read detached known settings, with global values overriding legacy values."""
    _require_object(config, "音频翻译配置必须是对象。")
    result = copy.deepcopy(DEFAULT_AUDIO_TRANSLATION_SETTINGS)
    legacy = _active_provider(config, "transcription_platforms", "active_transcription_platform")
    _merge_known(result, {key: value for key, value in legacy.items() if key != "export"})
    current = _require_object(config.get("audio_translation_settings", {}), "音频翻译设置必须是对象。")
    return _merge_known(result, current)


def read_image_translation_settings(config):
    """Read OCR and image-generation task options without copying credentials."""
    _require_object(config, "图片翻译配置必须是对象。")
    result = copy.deepcopy(DEFAULT_IMAGE_TRANSLATION_SETTINGS)
    _merge_known(result["ocr"], _active_provider(config, "ocr_platforms", "active_ocr_platform"))
    _merge_known(result["generation"], _active_provider(
        config, "image_generation_platforms", "active_image_generation_platform"))
    current = _require_object(config.get("image_translation_settings", {}), "图片翻译设置必须是对象。")
    return _merge_image_settings(result, current)


def normalize_audio_translation_settings(values):
    """Normalize form input and validate the complete audio task configuration."""
    _require_object(values, "音频翻译设置必须是对象。")
    result = _merge_known(copy.deepcopy(DEFAULT_AUDIO_TRANSLATION_SETTINGS), values)
    hints = result["language_hints"]
    if isinstance(hints, str):
        hints = hints.replace("，", ",").split(",")
    if not isinstance(hints, list) or any(not isinstance(hint, str) for hint in hints):
        raise ValueError("语言提示必须是逗号分隔的语言代码或文本列表。")
    result["language_hints"] = list(dict.fromkeys(hint.strip() for hint in hints if hint.strip()))
    if len(result["language_hints"]) > 4:
        raise ValueError("语言提示最多填写 4 种语言。")
    if any(hint not in SUPPORTED_LANGUAGE_HINTS for hint in result["language_hints"]):
        raise ValueError("语言提示请使用受支持的小写短码，例如 zh、en、ja，不接受 zh-CN 等地区码。")
    if type(result["speaker_diarization_enabled"]) is not bool:
        raise ValueError("说话人分离必须是开启或关闭。")
    for key, label, lower, upper in (
        ("chunk_duration_seconds", "长音频切片时长", 30, 290),
        ("chunk_concurrency", "切片并发数", 1, 8),
    ):
        if type(result[key]) is not int or not lower <= result[key] <= upper:
            raise ValueError(f"{label}必须为 {lower} 至 {upper} 的整数。")
    for key, label, lower, upper in (
        ("chunk_overlap_seconds", "切片重叠时长", 0.5, 5),
        ("vad_threshold", "语音检测阈值", 0.01, 0.99),
    ):
        value = result[key]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not lower <= value <= upper or not math.isfinite(value)):
            raise ValueError(f"{label}必须为 {lower} 至 {upper} 之间的数字。")
    result["export"] = _normalize_export_settings(result["export"], "audio")
    return result


def normalize_image_translation_settings(values):
    """Normalize image task options without accepting provider-only fields."""
    _require_object(values, "图片翻译设置必须是对象。")
    result = _merge_image_settings(copy.deepcopy(DEFAULT_IMAGE_TRANSLATION_SETTINGS), values)
    ocr = result["ocr"]
    if not isinstance(ocr["reading_order"], str):
        raise ValueError("阅读顺序必须是文本。")
    ocr["reading_order"] = ocr["reading_order"].strip()
    if ocr["reading_order"] not in READING_ORDERS:
        raise ValueError("请选择自动、从左向右或漫画从右向左的阅读顺序。")
    if type(ocr["group_lines"]) is not bool:
        raise ValueError("合并文字行必须是开启或关闭。")
    if type(ocr["refine_text"]) is not bool:
        raise ValueError("复核气泡原文必须是开启或关闭。")
    if ocr["refine_text"] and not ocr["group_lines"]:
        raise ValueError("复核气泡原文需要先开启“合并相邻文字行”。")

    generation = result["generation"]
    if not isinstance(generation["size"], str) or not isinstance(generation["prompt"], str):
        raise ValueError("输出尺寸和补充翻译要求必须是文本。")
    if len(generation["prompt"]) > 10000 or "\x00" in generation["prompt"]:
        raise ValueError("补充翻译要求必须是不超过 10000 字且不含空字符的文本。")
    generation["size"] = generation["size"].strip().lower()
    if type(generation["prompt_extend"]) is not bool:
        raise ValueError("自动改写必须是开启或关闭。")
    if type(generation["watermark"]) is not bool:
        raise ValueError("图片水印必须是开启或关闭。")
    seed = generation["seed"]
    if isinstance(seed, str):
        seed = seed.strip()
        if not seed:
            seed = None
        elif seed.isascii() and seed.isdigit():
            digits = seed.lstrip("0") or "0"
            if len(digits) <= 10:
                seed = int(digits)
    if seed is not None and (type(seed) is not int or not 0 <= seed <= MAX_SEED):
        raise ValueError("随机种子必须留空或填写 0 至 2147483647 的整数。")
    generation["seed"] = seed
    generation["size"] = normalize_generation_size(generation["size"])
    result["export"] = _normalize_export_settings(result["export"], "image")
    return result


def build_audio_translation_settings_update(config, values):
    """Patch only global audio settings, preserving unedited known options."""
    _require_object(values, "音频翻译设置必须是对象。")
    result = _merge_known(read_audio_translation_settings(config), values)
    return {"audio_translation_settings": normalize_audio_translation_settings(result)}


def build_image_translation_settings_update(config, values):
    """Patch only global image settings, preserving unedited known options."""
    _require_object(values, "图片翻译设置必须是对象。")
    result = _merge_image_settings(read_image_translation_settings(config), values)
    return {"image_translation_settings": normalize_image_translation_settings(result)}
