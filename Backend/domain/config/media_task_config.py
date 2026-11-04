"""Task-owned media settings, independent of provider credentials."""
import copy
import math


DEFAULT_AUDIO_TRANSLATION_SETTINGS = {
    "language_hints": [],
    "speaker_diarization_enabled": False,
    "chunk_duration_seconds": 240,
    "chunk_overlap_seconds": 2,
    "chunk_concurrency": 3,
    "vad_threshold": 0.35,
    "export": {"format": "srt", "mode": "bilingual", "suffix": "_subtitles"},
}
DEFAULT_VIDEO_TRANSLATION_SETTINGS = copy.deepcopy(DEFAULT_AUDIO_TRANSLATION_SETTINGS)
DEFAULT_IMAGE_TRANSLATION_SETTINGS = {
    "generation": {
        "size": "auto", "seed": None, "prompt_extend": True, "prompt": "", "watermark": False,
    },
    "export": {"format": "png", "suffix": "_translated"},
}
MEDIA_EXPORT_FORMATS = {"audio": ("srt", "vtt", "ass", "lrc"), "video": ("srt", "vtt", "ass", "lrc"), "image": ("png", "jpeg", "webp")}
AUDIO_EXPORT_MODES = ("bilingual", "translated", "source")


def _active_platform(config, collection, active_key):
    providers = config.get(collection)
    identifier = config.get(active_key)
    if not isinstance(providers, dict) or not isinstance(identifier, str):
        return {}
    platform = providers.get(identifier)
    return platform if isinstance(platform, dict) else {}


def _fill_missing(target, defaults, legacy):
    changed = False
    for key, default in defaults.items():
        if key not in target:
            target[key] = copy.deepcopy(legacy.get(key, default))
            changed = True
        elif isinstance(default, dict) and isinstance(target[key], dict):
            old = legacy.get(key, {})
            changed = _fill_missing(target[key], default, old if isinstance(old, dict) else {}) or changed
    return changed


def migrate_media_task_settings(config):
    """Remove retired image OCR settings and fill task fields from saved providers.

    Run before merging application defaults. Existing task values, including false,
    empty strings and null seeds, always win. Malformed objects are left intact so
    validation can report them rather than silently discarding user settings.
    """
    changed = False
    for key in ("ocr_platforms", "active_ocr_platform"):
        if key in config:
            config.pop(key)
            changed = True
    if "audio_translation_settings" not in config:
        config["audio_translation_settings"] = {}
        changed = True
    audio = config["audio_translation_settings"]
    if isinstance(audio, dict):
        legacy = _active_platform(config, "transcription_platforms", "active_transcription_platform")
        changed = _fill_missing(audio, DEFAULT_AUDIO_TRANSLATION_SETTINGS,
                                {key: value for key, value in legacy.items() if key != "export"}) or changed

    if "video_translation_settings" not in config:
        config["video_translation_settings"] = {}
        changed = True
    video = config["video_translation_settings"]
    if isinstance(video, dict):
        changed = _fill_missing(video, DEFAULT_VIDEO_TRANSLATION_SETTINGS, {}) or changed

    if "image_translation_settings" not in config:
        config["image_translation_settings"] = {}
        changed = True
    image = config["image_translation_settings"]
    if isinstance(image, dict):
        if "ocr" in image:
            image.pop("ocr")
            changed = True
        for group, collection, active_key in (
            ("generation", "image_generation_platforms", "active_image_generation_platform"),
        ):
            if group not in image:
                image[group] = {}
                changed = True
            if isinstance(image[group], dict):
                legacy = _active_platform(config, collection, active_key)
                changed = _fill_missing(image[group], DEFAULT_IMAGE_TRANSLATION_SETTINGS[group], legacy) or changed
        changed = _fill_missing(image, {"export": DEFAULT_IMAGE_TRANSLATION_SETTINGS["export"]}, {}) or changed
    return changed


def _settings_object(settings, defaults, label):
    if not isinstance(settings, dict):
        raise ValueError(f"{label}必须是 JSON 对象")
    if set(settings) - set(defaults):
        raise ValueError(f"{label}包含不支持的字段")
    values = copy.deepcopy(defaults)
    values.update(settings)
    return values


def _validate_export_settings(settings, kind):
    defaults = (DEFAULT_AUDIO_TRANSLATION_SETTINGS if kind in ("audio", "video") else DEFAULT_IMAGE_TRANSLATION_SETTINGS)["export"]
    values = _settings_object(settings, defaults, "导出设置")
    if not isinstance(values["format"], str) or values["format"] not in MEDIA_EXPORT_FORMATS[kind]:
        label = "字幕" if kind in ("audio", "video") else "图片"
        raise ValueError(f"{label}导出格式必须为 {'、'.join(MEDIA_EXPORT_FORMATS[kind])}")
    if kind in ("audio", "video") and (not isinstance(values["mode"], str) or values["mode"] not in AUDIO_EXPORT_MODES):
        raise ValueError("字幕导出模式必须为 bilingual、translated 或 source")
    suffix = values["suffix"]
    if not isinstance(suffix, str) or any(ord(c) < 32 or c in '/\\<>:"|?*' for c in suffix):
        raise ValueError("输出文件名后缀不能包含路径分隔符或非法文件名字符。")


def validate_audio_translation_settings(settings):
    from Backend.domain.config.transcription_config import LANGUAGE_HINTS

    values = _settings_object(settings, DEFAULT_AUDIO_TRANSLATION_SETTINGS, "音译设置")
    hints = values["language_hints"]
    if (not isinstance(hints, list) or len(hints) > 4
            or any(not isinstance(hint, str) or hint not in LANGUAGE_HINTS for hint in hints)):
        raise ValueError("语言提示最多包含 4 个受支持的小写语言代码")
    if type(values["speaker_diarization_enabled"]) is not bool:
        raise ValueError("说话人分离必须是布尔值")
    for key, lower, upper in (("chunk_duration_seconds", 30, 290), ("chunk_concurrency", 1, 8)):
        if type(values[key]) is not int or not lower <= values[key] <= upper:
            raise ValueError(f"{key} 必须为 {lower} 至 {upper} 的整数")
    for key, lower, upper in (("chunk_overlap_seconds", 0.5, 5), ("vad_threshold", 0.01, 0.99)):
        value = values[key]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not lower <= value <= upper or not math.isfinite(value)):
            raise ValueError(f"{key} 必须为 {lower} 至 {upper} 之间的数字")
    _validate_export_settings(values["export"], "audio")


def validate_image_translation_settings(settings):
    from Backend.application.pipeline_common import PipelineError
    from Backend.domain.config.image_generation_config import validate_size

    groups = _settings_object(settings, DEFAULT_IMAGE_TRANSLATION_SETTINGS, "图译设置")
    generation = _settings_object(
        groups["generation"], DEFAULT_IMAGE_TRANSLATION_SETTINGS["generation"], "图片生成设置")
    if not isinstance(generation["size"], str):
        raise ValueError("生图尺寸必须为 auto 或 宽*高")
    size_error = None
    for api_format in ("DashScope", "VolcengineArk", "Gemini"):
        try:
            validate_size(generation["size"], api_format)
            break
        except PipelineError as error:
            size_error = error
    else:
        raise ValueError(size_error.message) from None
    seed = generation["seed"]
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 2147483647):
        raise ValueError("生图随机种子必须为空或 0 至 2147483647 的整数")
    for key in ("prompt_extend", "watermark"):
        if type(generation[key]) is not bool:
            raise ValueError(f"图片生成设置 {key} 必须是布尔值")
    prompt = generation["prompt"]
    if not isinstance(prompt, str) or len(prompt) > 10000 or "\x00" in prompt:
        raise ValueError("补充翻译要求必须是不超过 10000 字且不含空字符的文本")
    _validate_export_settings(groups["export"], "image")


def validate_media_task_settings(config):
    """Validate only task options; absent or empty provider keys never block saving."""
    if "audio_translation_settings" in config:
        validate_audio_translation_settings(config["audio_translation_settings"])
    if "video_translation_settings" in config:
        validate_audio_translation_settings(config["video_translation_settings"])
    if "image_translation_settings" in config:
        validate_image_translation_settings(config["image_translation_settings"])
