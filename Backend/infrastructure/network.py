"""Apply persisted proxy settings in the process that makes model requests."""
import os


class ProxySettings:
    KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY")

    def __init__(self):
        self.original = {key: os.environ.get(key) for key in self.KEYS}
        self.current = object()

    def apply(self, config):
        proxy = str(config.get("proxy_url") or "").strip() if config.get("proxy_enable") else ""
        if proxy == self.current:
            return False
        for key in self.KEYS:
            if proxy:
                os.environ[key] = proxy
            else:
                os.environ.pop(key, None)
        self.current = proxy
        return True

    def close(self):
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
