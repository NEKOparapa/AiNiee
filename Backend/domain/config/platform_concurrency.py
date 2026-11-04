"""Per-interface concurrency defaults and validation."""

MAX_THREAD_COUNT = 9999999


def validate_thread_count(value):
    if type(value) is not int or not 0 <= value <= MAX_THREAD_COUNT:
        raise ValueError(f"接口并发任务数必须是 0 至 {MAX_THREAD_COUNT} 的整数（0 表示自动）")
    return value


def normalize_platform_concurrency(config: dict) -> bool:
    """Retire the global count; missing provider values start in automatic mode."""
    platforms = config.get("platforms", {})
    if not isinstance(platforms, dict):
        raise ValueError("配置字段 platforms 必须是 JSON 对象")
    for platform in platforms.values():
        if not isinstance(platform, dict):
            raise ValueError("接口配置必须是 JSON 对象")
        validate_thread_count(platform.get("user_thread_counts", 0))

    changed = "user_thread_counts" in config
    config.pop("user_thread_counts", None)
    for platform in platforms.values():
        if "user_thread_counts" not in platform:
            platform["user_thread_counts"] = 0
            changed = True
    return changed
