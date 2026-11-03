"""Request defaults for persisted settings; API calls may explicitly override them."""

REQUEST_TIMEOUT_SECONDS = 300


def normalize_request_timeouts(config: dict) -> bool:
    """Replace retired timeout settings in-place, returning whether they changed."""
    changed = False
    targets = [config]
    for key in ("transcription_platforms", "image_generation_platforms"):
        platforms = config.get(key)
        if isinstance(platforms, dict):
            targets.extend(platform for platform in platforms.values() if isinstance(platform, dict))
    for target in targets:
        if target.get("request_timeout") != REQUEST_TIMEOUT_SECONDS:
            target["request_timeout"] = REQUEST_TIMEOUT_SECONDS
            changed = True
    return changed
