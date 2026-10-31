"""Backend-local configuration access. Desktop clients use the configuration API."""
from Backend.infrastructure.config.store import ConfigStore


class ConfigMixin(ConfigStore):
    def load_config_from_default(self):
        return self.fill_config(self.load_config(), getattr(self, "default", {}))
