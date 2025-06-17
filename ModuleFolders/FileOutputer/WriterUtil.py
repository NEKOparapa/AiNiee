from ModuleFolders.TaskConfig.TaskConfig import TaskConfig

_AINIEE_CONFIG_INSTANCE: TaskConfig | None = None
"""Ainiee配置类单例实现"""


def get_ainiee_config():
    """获取Ainiee配置的全局单例实例"""
    global _AINIEE_CONFIG_INSTANCE
    if _AINIEE_CONFIG_INSTANCE is None:
        _AINIEE_CONFIG_INSTANCE = TaskConfig()
        # 加载配置文件
        _AINIEE_CONFIG_INSTANCE.initialize()
    return _AINIEE_CONFIG_INSTANCE


def release_ainiee_config():
    """释放Ainiee配置"""
    global _AINIEE_CONFIG_INSTANCE
    if _AINIEE_CONFIG_INSTANCE is not None:
        _AINIEE_CONFIG_INSTANCE = None
    return True
