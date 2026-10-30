"""Bilingual startup notices used before the browser's i18n is available."""

MESSAGES = {
    "already_running": {
        "zh-CN": "AiNiee 已在运行。请返回已打开的浏览器标签；需要退出时，请在“关于 / 更新”页选择“退出应用”。",
        "en": "AiNiee is already running. Return to its browser tab. To exit, choose Quit application on the About page.",
    },
    "startup_failed": {
        "zh-CN": "AiNiee 启动失败。请查看程序旁 Logs 文件夹中的日志，并确认已完整解压程序。",
        "en": "AiNiee could not start. Check the Logs folder beside the application and make sure the entire archive was extracted.",
    },
    "port_busy": {
        "zh-CN": "指定的本机端口不可用，AiNiee 未启动。请移除 --port 参数或指定空闲端口。",
        "en": "The selected local port is unavailable. Remove --port or select a free port and try again.",
    },
    "browser_failed": {
        "zh-CN": "无法打开默认浏览器，AiNiee 正在退出。请配置 Windows 默认浏览器后重试。",
        "en": "The default browser could not be opened. AiNiee is shutting down. Set a default Windows browser and try again.",
    },
}


def startup_message(key: str) -> str:
    messages = MESSAGES[key]
    return messages["zh-CN"] + "\n\n" + messages["en"]
