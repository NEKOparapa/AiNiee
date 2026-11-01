"""Request cancellation belongs to the calling operation, never global state."""


def request_cancelled(platform_config: dict) -> bool:
    callback = platform_config.get("is_cancelled")
    if callable(callback):
        return bool(callback())
    return False
