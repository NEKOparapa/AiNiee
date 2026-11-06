"""Manual per-provider limits for media operations."""

DEFAULT_MEDIA_CONCURRENCY = 3
MAX_MEDIA_CONCURRENCY = 64


def validate_media_concurrency(value):
    if type(value) is not int or not 1 <= value <= MAX_MEDIA_CONCURRENCY:
        raise ValueError("接口并发任务数必须是 1 至 64 的整数")
    return value


def normalize_media_concurrency(config):
    """Retire saved slice limits without inheriting them into provider limits."""
    changed = False
    for key in ("audio_translation_settings", "video_translation_settings"):
        settings = config.get(key)
        if isinstance(settings, dict) and "chunk_concurrency" in settings:
            settings.pop("chunk_concurrency")
            changed = True
    for key in ("transcription_platforms", "image_generation_platforms"):
        platforms = config.get(key, {})
        if not isinstance(platforms, dict):
            raise ValueError(f"配置字段 {key} 必须是 JSON 对象")
        for platform in platforms.values():
            if not isinstance(platform, dict):
                raise ValueError("接口配置必须是 JSON 对象")
            validate_media_concurrency(platform.get("user_thread_counts", DEFAULT_MEDIA_CONCURRENCY))
            if "chunk_concurrency" in platform:
                platform.pop("chunk_concurrency")
                changed = True
            if "user_thread_counts" not in platform:
                platform["user_thread_counts"] = DEFAULT_MEDIA_CONCURRENCY
                changed = True
    return changed
