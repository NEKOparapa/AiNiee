"""配置读写沿用桌面版的路径、迁移和原子写入规则。"""

from copy import deepcopy

from ModuleFolders.Application.SettingsDefaults import fill_setting_defaults
from ModuleFolders.Config.Config import ConfigMixin


class ConfigService(ConfigMixin):
    def get_config(self) -> dict:
        return fill_setting_defaults(self.load_config())

    def patch_config(self, changes: dict) -> dict:
        """替换请求提供的顶级键，保留其余配置；嵌套值整体替换。"""
        patch = deepcopy(changes)
        saved = self.update_config(lambda config: config.update(patch))
        return fill_setting_defaults(saved)
