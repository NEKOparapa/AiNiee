
import os
import json
import copy
import random
from functools import partial

from rich import print
from PyQt5.Qt import Qt
from PyQt5.Qt import QEvent
from PyQt5.Qt import QTimer
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import InfoBar
from qfluentwidgets import InfoBarPosition
from qfluentwidgets import RoundMenu
from qfluentwidgets import FluentIcon
from qfluentwidgets import PrimaryPushButton
from qfluentwidgets import PrimaryDropDownPushButton

from Widget.FlowCard import FlowCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.APIEditMessageBox import APIEditMessageBox
from Widget.LineEditMessageBox import LineEditMessageBox

class PlatformPage(QFrame):

    DEFAULT = {
        "platforms": {
            "sakura": {
                "tag": "sakura",
                "group": "local",
                "name": "SakuraLLM",
                "api_url": "http://127.0.0.1:8080",
                "api_key": "",
                "api_format": "",
                "model": "Sakura-v1.0",
                "proxy": "",
                "account": "默认",
                "auto_complete": False,
                "model_datas": [
                    "Sakura-v0.9",
                    "Sakura-v1.0",
                ],
                "account_datas": {},
                "key_in_settings": [
                    "api_url",
                    "model",
                    "proxy",
                ],
            },
            "cohere": {
                "tag": "cohere",
                "group": "online",
                "name": "Cohere",
                "api_url": "https://api.cohere.com",
                "api_key": "",
                "api_format": "Cohere",
                "model": "command",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "command",
                    "command-r",
                    "command-r-plus",
                    "c4ai-aya-23",
                ],
                "account_datas": {
                    "试用账号": {
                        "command": {"max_tokens": 4000, "TPM": 9999999, "RPM": 10},
                        "command-r": {"max_tokens": 100000, "TPM": 9999999, "RPM": 10},
                        "command-r-plus": {
                            "max_tokens": 100000,
                            "TPM": 9999999,
                            "RPM": 10,
                        },
                        "c4ai-aya-23": {
                            "max_tokens": 100000,
                            "TPM": 9999999,
                            "RPM": 10,
                        },
                    },
                    "生产账号": {
                        "command": {"max_tokens": 4000, "TPM": 9999999, "RPM": 10000},
                        "command-r": {
                            "max_tokens": 100000,
                            "TPM": 9999999,
                            "RPM": 10000,
                        },
                        "command-r-plus": {
                            "max_tokens": 100000,
                            "TPM": 9999999,
                            "RPM": 10000,
                        },
                        "c4ai-aya-23": {
                            "max_tokens": 100000,
                            "TPM": 9999999,
                            "RPM": 10000,
                        },
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                    "account",
                ],
            },
            "google": {
                "tag": "google",
                "group": "online",
                "name": "Google",
                "api_url": "",
                "api_key": "",
                "api_format": "Google",
                "model": "gemini-1.0-pro",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "gemini-1.0-pro",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash",
                ],
                "account_datas": {
                    "免费账号": {
                        "gemini-1.0-pro": {
                            "InputTokenLimit": 30720,
                            "OutputTokenLimit": 8192,
                            "max_tokens": 8192,
                            "TPM": 32000,
                            "RPM": 15,
                        },
                        "gemini-1.5-flash": {
                            "InputTokenLimit": 30720,
                            "OutputTokenLimit": 8192,
                            "max_tokens": 8192,
                            "TPM": 1000000,
                            "RPM": 15,
                        },
                        "gemini-1.5-pro": {
                            "InputTokenLimit": 1048576,
                            "OutputTokenLimit": 8192,
                            "max_tokens": 8192,
                            "TPM": 32000,
                            "RPM": 2,
                        },
                    },
                    "付费账号": {
                        "gemini-1.0-pro": {
                            "InputTokenLimit": 30720,
                            "OutputTokenLimit": 8192,
                            "max_tokens": 8192,
                            "TPM": 120000,
                            "RPM": 360,
                        },
                        "gemini-1.5-flash": {
                            "InputTokenLimit": 30720,
                            "OutputTokenLimit": 8192,
                            "max_tokens": 8192,
                            "TPM": 4000000,
                            "RPM": 1000,
                        },
                        "gemini-1.5-pro": {
                            "InputTokenLimit": 1048576,
                            "OutputTokenLimit": 8192,
                            "max_tokens": 8192,
                            "TPM": 4000000,
                            "RPM": 360,
                        },
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                    "account",
                ],
            },
            "openai": {
                "tag": "openai",
                "group": "online",
                "name": "OpenAI",
                "api_url": "https://api.openai.com/v1",
                "api_key": "",
                "api_format": "",
                "model": "gpt-3.5-turbo",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "gpt-3.5-turbo",
                    "gpt-3.5-turbo-0301",
                    "gpt-3.5-turbo-0613",
                    "gpt-3.5-turbo-1106",
                    "gpt-3.5-turbo-0125",
                    "gpt-3.5-turbo-16k",
                    "gpt-3.5-turbo-16k-0613",
                    "gpt-4",
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-0314",
                    "gpt-4-0613",
                    "gpt-4-turbo",
                    "gpt-4-turbo-preview",
                    "gpt-4-1106-preview",
                    "gpt-4-0125-preview",
                ],
                "account_datas": {
                    "免费账号": {
                        "gpt-3.5-turbo": {"max_tokens": 4000, "TPM": 40000, "RPM": 3},
                        "gpt-3.5-turbo-0301": {
                            "max_tokens": 4000,
                            "TPM": 40000,
                            "RPM": 3,
                        },
                        "gpt-3.5-turbo-0613": {
                            "max_tokens": 4000,
                            "TPM": 40000,
                            "RPM": 3,
                        },
                        "gpt-3.5-turbo-1106": {
                            "max_tokens": 4000,
                            "TPM": 40000,
                            "RPM": 3,
                        },
                        "gpt-3.5-turbo-0125": {
                            "max_tokens": 4000,
                            "TPM": 150000,
                            "RPM": 3,
                        },
                        "gpt-3.5-turbo-16k": {
                            "max_tokens": 16000,
                            "TPM": 40000,
                            "RPM": 3,
                        },
                        "gpt-3.5-turbo-16k-0613": {
                            "max_tokens": 16000,
                            "TPM": 40000,
                            "RPM": 3,
                        },
                    },
                    "付费账号(等级1)": {
                        "gpt-3.5-turbo": {
                            "max_tokens": 4000,
                            "TPM": 60000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-0301": {
                            "max_tokens": 4000,
                            "TPM": 60000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-0613": {
                            "max_tokens": 4000,
                            "TPM": 60000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-1106": {
                            "max_tokens": 4000,
                            "TPM": 60000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-0125": {
                            "max_tokens": 4000,
                            "TPM": 120000,
                            "RPM": 2000,
                        },
                        "gpt-3.5-turbo-16k": {
                            "max_tokens": 16000,
                            "TPM": 60000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-16k-0613": {
                            "max_tokens": 16000,
                            "TPM": 60000,
                            "RPM": 3500,
                        },
                        "gpt-4": {"max_tokens": 8000, "TPM": 10000, "RPM": 500},
                        "gpt-4o": {"max_tokens": 4000, "TPM": 300000, "RPM": 500},
                        "gpt-4o-mini": {"max_tokens": 4000, "TPM": 600000, "RPM": 500},
                        "gpt-4-0314": {"max_tokens": 8000, "TPM": 10000, "RPM": 500},
                        "gpt-4-0613": {"max_tokens": 8000, "TPM": 10000, "RPM": 500},
                        "gpt-4-turbo": {"max_tokens": 4000, "TPM": 300000, "RPM": 500},
                        "gpt-4-turbo-preview": {
                            "max_tokens": 4000,
                            "TPM": 150000,
                            "RPM": 500,
                        },
                        "gpt-4-1106-preview": {
                            "max_tokens": 4000,
                            "TPM": 150000,
                            "RPM": 500,
                        },
                        "gpt-4-0125-preview": {
                            "max_tokens": 4000,
                            "TPM": 150000,
                            "RPM": 500,
                        },
                    },
                    "付费账号(等级2)": {
                        "gpt-3.5-turbo": {
                            "max_tokens": 4000,
                            "TPM": 80000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-0301": {
                            "max_tokens": 4000,
                            "TPM": 80000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-0613": {
                            "max_tokens": 4000,
                            "TPM": 80000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-1106": {
                            "max_tokens": 4000,
                            "TPM": 80000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-0125": {
                            "max_tokens": 4000,
                            "TPM": 160000,
                            "RPM": 2000,
                        },
                        "gpt-3.5-turbo-16k": {
                            "max_tokens": 16000,
                            "TPM": 80000,
                            "RPM": 3500,
                        },
                        "gpt-3.5-turbo-16k-0613": {
                            "max_tokens": 16000,
                            "TPM": 80000,
                            "RPM": 3500,
                        },
                        "gpt-4": {"max_tokens": 8000, "TPM": 40000, "RPM": 5000},
                        "gpt-4o": {"max_tokens": 4000, "TPM": 600000, "RPM": 5000},
                        "gpt-4o-mini": {"max_tokens": 4000, "TPM": 80000, "RPM": 5000},
                        "gpt-4-0314": {"max_tokens": 8000, "TPM": 40000, "RPM": 5000},
                        "gpt-4-0613": {"max_tokens": 8000, "TPM": 40000, "RPM": 5000},
                        "gpt-4-turbo": {"max_tokens": 4000, "TPM": 600000, "RPM": 5000},
                        "gpt-4-turbo-preview": {
                            "max_tokens": 4000,
                            "TPM": 300000,
                            "RPM": 5000,
                        },
                        "gpt-4-1106-preview": {
                            "max_tokens": 4000,
                            "TPM": 300000,
                            "RPM": 5000,
                        },
                        "gpt-4-0125-preview": {
                            "max_tokens": 4000,
                            "TPM": 300000,
                            "RPM": 5000,
                        },
                    },
                    "付费账号(等级3)": {
                        "gpt-3.5-turbo": {
                            "max_tokens": 4000,
                            "TPM": 160000,
                            "RPM": 5000,
                        },
                        "gpt-3.5-turbo-0301": {
                            "max_tokens": 4000,
                            "TPM": 160000,
                            "RPM": 5000,
                        },
                        "gpt-3.5-turbo-0613": {
                            "max_tokens": 4000,
                            "TPM": 160000,
                            "RPM": 5000,
                        },
                        "gpt-3.5-turbo-1106": {
                            "max_tokens": 4000,
                            "TPM": 250000,
                            "RPM": 3000,
                        },
                        "gpt-3.5-turbo-0125": {
                            "max_tokens": 4000,
                            "TPM": 160000,
                            "RPM": 5000,
                        },
                        "gpt-3.5-turbo-16k": {
                            "max_tokens": 16000,
                            "TPM": 160000,
                            "RPM": 5000,
                        },
                        "gpt-3.5-turbo-16k-0613": {
                            "max_tokens": 16000,
                            "TPM": 160000,
                            "RPM": 5000,
                        },
                        "gpt-4": {"max_tokens": 8000, "TPM": 80000, "RPM": 5000},
                        "gpt-4o": {"max_tokens": 4000, "TPM": 600000, "RPM": 5000},
                        "gpt-4o-mini": {"max_tokens": 4000, "TPM": 160000, "RPM": 5000},
                        "gpt-4-0314": {"max_tokens": 8000, "TPM": 80000, "RPM": 5000},
                        "gpt-4-0613": {"max_tokens": 8000, "TPM": 80000, "RPM": 5000},
                        "gpt-4-turbo": {"max_tokens": 4000, "TPM": 600000, "RPM": 5000},
                        "gpt-4-turbo-preview": {
                            "max_tokens": 4000,
                            "TPM": 300000,
                            "RPM": 5000,
                        },
                        "gpt-4-1106-preview": {
                            "max_tokens": 4000,
                            "TPM": 300000,
                            "RPM": 5000,
                        },
                        "gpt-4-0125-preview": {
                            "max_tokens": 4000,
                            "TPM": 300000,
                            "RPM": 5000,
                        },
                    },
                    "付费账号(等级4)": {
                        "gpt-3.5-turbo": {
                            "max_tokens": 4000,
                            "TPM": 1000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-0301": {
                            "max_tokens": 4000,
                            "TPM": 1000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-0613": {
                            "max_tokens": 4000,
                            "TPM": 1000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-1106": {
                            "max_tokens": 4000,
                            "TPM": 1000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-0125": {
                            "max_tokens": 4000,
                            "TPM": 2000000,
                            "RPM": 50000,
                        },
                        "gpt-3.5-turbo-16k": {
                            "max_tokens": 16000,
                            "TPM": 1000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-16k-0613": {
                            "max_tokens": 16000,
                            "TPM": 1000000,
                            "RPM": 10000,
                        },
                        "gpt-4": {"max_tokens": 8000, "TPM": 300000, "RPM": 10000},
                        "gpt-4o": {"max_tokens": 4000, "TPM": 900000, "RPM": 10000},
                        "gpt-4o-mini": {
                            "max_tokens": 4000,
                            "TPM": 100000,
                            "RPM": 10000,
                        },
                        "gpt-4-0314": {"max_tokens": 8000, "TPM": 300000, "RPM": 10000},
                        "gpt-4-0613": {"max_tokens": 8000, "TPM": 300000, "RPM": 10000},
                        "gpt-4-turbo": {
                            "max_tokens": 4000,
                            "TPM": 900000,
                            "RPM": 10000,
                        },
                        "gpt-4-turbo-preview": {
                            "max_tokens": 4000,
                            "TPM": 450000,
                            "RPM": 10000,
                        },
                        "gpt-4-1106-preview": {
                            "max_tokens": 4000,
                            "TPM": 450000,
                            "RPM": 10000,
                        },
                        "gpt-4-0125-preview": {
                            "max_tokens": 4000,
                            "TPM": 450000,
                            "RPM": 10000,
                        },
                    },
                    "付费账号(等级5)": {
                        "gpt-3.5-turbo": {
                            "max_tokens": 4000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-0301": {
                            "max_tokens": 4000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-0613": {
                            "max_tokens": 4000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-1106": {
                            "max_tokens": 4000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-0125": {
                            "max_tokens": 4000,
                            "TPM": 4000000,
                            "RPM": 20000,
                        },
                        "gpt-3.5-turbo-16k": {
                            "max_tokens": 16000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "gpt-3.5-turbo-16k-0613": {
                            "max_tokens": 16000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "gpt-4": {"max_tokens": 8000, "TPM": 300000, "RPM": 10000},
                        "gpt-4o": {"max_tokens": 4000, "TPM": 1200000, "RPM": 10000},
                        "gpt-4o-mini": {
                            "max_tokens": 4000,
                            "TPM": 15000000,
                            "RPM": 10000,
                        },
                        "gpt-4-0314": {"max_tokens": 8000, "TPM": 300000, "RPM": 10000},
                        "gpt-4-0613": {"max_tokens": 8000, "TPM": 300000, "RPM": 10000},
                        "gpt-4-turbo": {
                            "max_tokens": 4000,
                            "TPM": 1200000,
                            "RPM": 10000,
                        },
                        "gpt-4-turbo-preview": {
                            "max_tokens": 4000,
                            "TPM": 600000,
                            "RPM": 10000,
                        },
                        "gpt-4-1106-preview": {
                            "max_tokens": 4000,
                            "TPM": 600000,
                            "RPM": 10000,
                        },
                        "gpt-4-0125-preview": {
                            "max_tokens": 4000,
                            "TPM": 600000,
                            "RPM": 10000,
                        },
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                    "account",
                ],
            },
            "deepseek": {
                "tag": "deepseek",
                "group": "online",
                "name": "DeepSeek",
                "api_url": "https://api.deepseek.com/v1",
                "api_key": "",
                "api_format": "",
                "model": "deepseek-chat",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "deepseek-chat",
                ],
                "account_datas": {
                    "默认": {
                        "deepseek-chat": {
                            "InputTokenLimit": 32000,
                            "OutputTokenLimit": 4000,
                            "max_tokens": 4000,
                            "TPM": 1000000,
                            "RPM": 3500,
                        },
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                ],
            },
            "anthropic": {
                "tag": "anthropic",
                "group": "online",
                "name": "Anthropic",
                "api_url": "https://api.anthropic.com",
                "api_key": "",
                "api_format": "Anthropic",
                "model": "claude-2.0",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "claude-2.0",
                    "claude-2.1",
                    "claude-3-haiku-20240307",
                    "claude-3-sonnet-20240229",
                    "claude-3-opus-20240229",
                    "claude-3-5-sonnet-20240620",
                ],
                "account_datas": {
                    "免费账号": {"max_tokens": 4000, "TPM": 20000, "RPM": 5},
                    "付费账号(等级1)": {"max_tokens": 4000, "TPM": 50000, "RPM": 50},
                    "付费账号(等级2)": {"max_tokens": 4000, "TPM": 80000, "RPM": 1000},
                    "付费账号(等级3)": {"max_tokens": 4000, "TPM": 160000, "RPM": 2000},
                    "付费账号(等级4)": {"max_tokens": 4000, "TPM": 400000, "RPM": 4000},
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                    "account",
                ],
            },
            "dashscope": {
                "tag": "dashscope",
                "group": "online",
                "name": "DashScope",
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "",
                "api_format": "",
                "model": "qwen-turbo",
                "proxy": "",
                "account": "默认",
                "auto_complete": False,
                "model_datas": [
                    "qwen-turbo",
                    "qwen-plus",
                    "qwen-max",
                    "qwen-long",
                ],
                "account_datas": {
                    "默认": {
                        "qwen-turbo": {"max_tokens": 6000, "TPM": 500000, "RPM": 500},
                        "qwen-plus": {"max_tokens": 30000, "TPM": 200000, "RPM": 200},
                        "qwen-max": {"max_tokens": 6000, "TPM": 100000, "RPM": 60},
                        "qwen-long": {"max_tokens": 28000, "TPM": 1500000, "RPM": 100},
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                ],
            },
            "zhipu": {
                "tag": "zhipu",
                "group": "online",
                "name": "智谱",
                "api_url": "https://open.bigmodel.cn/api/paas/v4",
                "api_key": "",
                "api_format": "",
                "model": "glm-4-flash",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "glm-4-flash",
                    "glm-4-air",
                    "glm-4-airx",
                    "glm-4",
                    "glm-4-0520",
                ],
                "account_datas": {
                    "免费账号": {
                        "glm-4-flash": {"max_tokens": 100000, "TPM": 100000, "RPM": 5},
                        "glm-4-air": {"max_tokens": 100000, "TPM": 100000, "RPM": 5},
                        "glm-4-airx": {"max_tokens": 8000, "TPM": 100000, "RPM": 5},
                        "glm-4": {"max_tokens": 100000, "TPM": 100000, "RPM": 5},
                        "glm-4-0520": {"max_tokens": 100000, "TPM": 100000, "RPM": 5},
                    },
                    "付费账号(等级1)": {
                        "glm-4-flash": {"max_tokens": 100000, "TPM": 100000, "RPM": 10},
                        "glm-4-air": {"max_tokens": 100000, "TPM": 100000, "RPM": 10},
                        "glm-4-airx": {"max_tokens": 8000, "TPM": 100000, "RPM": 10},
                        "glm-4": {"max_tokens": 100000, "TPM": 100000, "RPM": 10},
                        "glm-4-0520": {"max_tokens": 100000, "TPM": 100000, "RPM": 10},
                    },
                    "付费账号(等级2)": {
                        "glm-4-flash": {"max_tokens": 100000, "TPM": 100000, "RPM": 50},
                        "glm-4-air": {"max_tokens": 100000, "TPM": 100000, "RPM": 30},
                        "glm-4-airx": {"max_tokens": 8000, "TPM": 100000, "RPM": 15},
                        "glm-4": {"max_tokens": 100000, "TPM": 100000, "RPM": 20},
                        "glm-4-0520": {"max_tokens": 100000, "TPM": 100000, "RPM": 15},
                    },
                    "付费账号(等级3)": {
                        "glm-4-flash": {
                            "max_tokens": 100000,
                            "TPM": 100000,
                            "RPM": 100,
                        },
                        "glm-4-air": {"max_tokens": 100000, "TPM": 100000, "RPM": 50},
                        "glm-4-airx": {"max_tokens": 8000, "TPM": 100000, "RPM": 20},
                        "glm-4": {"max_tokens": 100000, "TPM": 100000, "RPM": 30},
                        "glm-4-0520": {"max_tokens": 100000, "TPM": 100000, "RPM": 20},
                    },
                    "付费账号(等级4)": {
                        "glm-4-flash": {
                            "max_tokens": 100000,
                            "TPM": 100000,
                            "RPM": 200,
                        },
                        "glm-4-air": {"max_tokens": 100000, "TPM": 100000, "RPM": 100},
                        "glm-4-airx": {"max_tokens": 8000, "TPM": 100000, "RPM": 25},
                        "glm-4": {"max_tokens": 100000, "TPM": 100000, "RPM": 100},
                        "glm-4-0520": {"max_tokens": 100000, "TPM": 100000, "RPM": 25},
                    },
                    "付费账号(等级5)": {
                        "glm-4-flash": {
                            "max_tokens": 100000,
                            "TPM": 100000,
                            "RPM": 300,
                        },
                        "glm-4-air": {"max_tokens": 100000, "TPM": 100000, "RPM": 200},
                        "glm-4-airx": {"max_tokens": 8000, "TPM": 100000, "RPM": 30},
                        "glm-4": {"max_tokens": 100000, "TPM": 100000, "RPM": 200},
                        "glm-4-0520": {"max_tokens": 100000, "TPM": 100000, "RPM": 30},
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                    "account",
                ],
            },
            "yi": {
                "tag": "yi",
                "group": "online",
                "name": "零一万物",
                "api_url": "https://api.lingyiwanwu.com/v1",
                "api_key": "",
                "api_format": "",
                "model": "yi-medium",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "yi-medium",
                    "yi-large-turbo",
                    "yi-large",
                ],
                "account_datas": {
                    "免费账号": {
                        "yi-medium": {"max_tokens": 8000, "TPM": 64000, "RPM": 8},
                        "yi-large-turbo": {"max_tokens": 8000, "TPM": 64000, "RPM": 8},
                        "yi-large": {"max_tokens": 16000, "TPM": 32000, "RPM": 4},
                    },
                    "付费账号(等级1)": {
                        "yi-medium": {"max_tokens": 8000, "TPM": 120000, "RPM": 20},
                        "yi-large-turbo": {
                            "max_tokens": 8000,
                            "TPM": 120000,
                            "RPM": 20,
                        },
                        "yi-large": {"max_tokens": 16000, "TPM": 80000, "RPM": 10},
                    },
                    "付费账号(等级2)": {
                        "yi-medium": {"max_tokens": 8000, "TPM": 240000, "RPM": 80},
                        "yi-large-turbo": {
                            "max_tokens": 8000,
                            "TPM": 240000,
                            "RPM": 80,
                        },
                        "yi-large": {"max_tokens": 16000, "TPM": 120000, "RPM": 40},
                    },
                    "付费账号(等级3)": {
                        "yi-medium": {"max_tokens": 8000, "TPM": 400000, "RPM": 300},
                        "yi-large-turbo": {
                            "max_tokens": 8000,
                            "TPM": 300000,
                            "RPM": 240,
                        },
                        "yi-large": {"max_tokens": 16000, "TPM": 160000, "RPM": 120},
                    },
                    "付费账号(等级4)": {
                        "yi-medium": {"max_tokens": 8000, "TPM": 600000, "RPM": 400},
                        "yi-large-turbo": {
                            "max_tokens": 8000,
                            "TPM": 480000,
                            "RPM": 240,
                        },
                        "yi-large": {"max_tokens": 16000, "TPM": 240000, "RPM": 120},
                    },
                    "付费账号(等级5)": {
                        "yi-medium": {"max_tokens": 8000, "TPM": 1000000, "RPM": 800},
                        "yi-large-turbo": {
                            "max_tokens": 8000,
                            "TPM": 800000,
                            "RPM": 400,
                        },
                        "yi-large": {"max_tokens": 16000, "TPM": 400000, "RPM": 200},
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                    "account",
                ],
            },
            "moonshot": {
                "tag": "moonshot",
                "group": "online",
                "name": "月之暗面",
                "api_url": "https://api.moonshot.cn",
                "api_key": "",
                "api_format": "",
                "model": "moonshot-v1-8k",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [
                    "moonshot-v1-8k",
                    "moonshot-v1-32k",
                    "moonshot-v1-128k",
                ],
                "account_datas": {
                    "免费账号": {
                        "moonshot-v1-8k": {"max_tokens": 4000, "TPM": 32000, "RPM": 3},
                        "moonshot-v1-32k": {
                            "max_tokens": 16000,
                            "TPM": 32000,
                            "RPM": 3,
                        },
                        "moonshot-v1-128k": {
                            "max_tokens": 640000,
                            "TPM": 32000,
                            "RPM": 3,
                        },
                    },
                    "付费账号(等级1)": {
                        "moonshot-v1-8k": {
                            "max_tokens": 4000,
                            "TPM": 128000,
                            "RPM": 200,
                        },
                        "moonshot-v1-32k": {
                            "max_tokens": 16000,
                            "TPM": 128000,
                            "RPM": 200,
                        },
                        "moonshot-v1-128k": {
                            "max_tokens": 640000,
                            "TPM": 128000,
                            "RPM": 200,
                        },
                    },
                    "付费账号(等级2)": {
                        "moonshot-v1-8k": {
                            "max_tokens": 4000,
                            "TPM": 128000,
                            "RPM": 500,
                        },
                        "moonshot-v1-32k": {
                            "max_tokens": 16000,
                            "TPM": 128000,
                            "RPM": 500,
                        },
                        "moonshot-v1-128k": {
                            "max_tokens": 640000,
                            "TPM": 128000,
                            "RPM": 500,
                        },
                    },
                    "付费账号(等级3)": {
                        "moonshot-v1-8k": {
                            "max_tokens": 4000,
                            "TPM": 384000,
                            "RPM": 5000,
                        },
                        "moonshot-v1-32k": {
                            "max_tokens": 16000,
                            "TPM": 384000,
                            "RPM": 5000,
                        },
                        "moonshot-v1-128k": {
                            "max_tokens": 640000,
                            "TPM": 384000,
                            "RPM": 5000,
                        },
                    },
                    "付费账号(等级4)": {
                        "moonshot-v1-8k": {
                            "max_tokens": 4000,
                            "TPM": 768000,
                            "RPM": 5000,
                        },
                        "moonshot-v1-32k": {
                            "max_tokens": 16000,
                            "TPM": 768000,
                            "RPM": 5000,
                        },
                        "moonshot-v1-128k": {
                            "max_tokens": 640000,
                            "TPM": 768000,
                            "RPM": 5000,
                        },
                    },
                    "付费账号(等级5)": {
                        "moonshot-v1-8k": {
                            "max_tokens": 4000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "moonshot-v1-32k": {
                            "max_tokens": 16000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                        "moonshot-v1-128k": {
                            "max_tokens": 640000,
                            "TPM": 2000000,
                            "RPM": 10000,
                        },
                    },
                },
                "key_in_settings": [
                    "api_key",
                    "model",
                    "proxy",
                    "account",
                ],
            },
            "volcengine": {
                "tag": "volcengine",
                "group": "online",
                "name": "火山引擎",
                "api_url": "",
                "api_key": "",
                "api_format": "",
                "model": "",
                "proxy": "",
                "account": "",
                "auto_complete": False,
                "model_datas": [],
                "account_datas": {},
                "key_in_settings": [
                    "api_url",
                    "api_key",
                    "proxy",
                ],
            },
        },
    }

    CUSTOM = {
        "tag": "",
        "group": "custom",
        "name": "",
        "api_url": "",
        "api_key": "",
        "api_format": "",
        "model": "",
        "proxy": "",
        "account": "",
        "auto_complete": True,
        "model_datas": [
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-sonnet-20240620",
        ],
        "format_datas": [
            "OpenAI",
            "Anthropic",
        ],
        "account_datas": {},
        "key_in_settings": [
            "api_url",
            "api_key",
            "api_format",
            "model",
            "proxy",
            "auto_complete",
        ],
    }

    def __init__(self, text: str, window, configurator, background_executor):
        super().__init__(parent = window)

        self.setObjectName(text.replace(" ", "-"))
        self.window = window
        self.configurator = configurator
        self.background_executor = background_executor

        # 载入配置文件
        config = self.load_config()
        config = self.save_config(config)

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_head_widget(self.container, config)
        self.add_body_widget(self.container, config)
        self.add_foot_widget(self.container, config)

        # 填充
        self.container.addStretch(1)

    # 载入配置文件
    def load_config(self) -> dict:
        config = {}

        if os.path.exists(os.path.join(self.configurator.resource_dir, "config.json")):
            with open(os.path.join(self.configurator.resource_dir, "config.json"), "r", encoding = "utf-8") as reader:
                config = json.load(reader)

        return config

    # 保存配置文件
    def save_config(self, new: dict) -> None:
        path = os.path.join(self.configurator.resource_dir, "config.json")
        
        # 读取配置文件
        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                old = json.load(reader)
        else:
            old = {}

        # 修改配置文件中的条目：如果条目存在，这更新值，如果不存在，则设置默认值
        for k, v in self.DEFAULT.items():
            if not k in new.keys():
                old[k] = v
            else:
                old[k] = new[k]

        # 写入配置文件
        with open(path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(old, indent = 4, ensure_ascii = False))

        return old

    # 执行接口测试
    def api_test(self, tag: str):
        # 载入配置文件
        config = self.load_config()
        platform = config.get("platforms").get(tag)

        if self.background_executor.Request_test_switch(self):
            def on_api_test_done(result):
                if result == True:
                    InfoBar.success(
                        title = "",
                        content = "接口测试成功 ...",
                        parent = self,
                        duration = 2500,
                        orient = Qt.Horizontal,
                        position = InfoBarPosition.TOP,
                        isClosable = True,
                    )
                else:
                    InfoBar.error(
                        title = "",
                        content = "接口测试失败 ...",
                        parent = self,
                        duration = 2500,
                        orient = Qt.Horizontal,
                        position = InfoBarPosition.TOP,
                        isClosable = True,
                    )
                    
            self.background_executor(
                "接口测试",
                "",
                "",
                platform.get("tag"),
                platform.get("api_url"),
                platform.get("model"),
                platform.get("api_key"),
                platform.get("proxy"),
                platform.get("api_format"),
                on_api_test_done,
            ).start()
        else:
            InfoBar.warning(
                title = "",
                content = "接口测试正在执行中，请稍后再试 ...",
                parent = self,
                duration = 2500,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

    # 删除平台
    def delete_platform(self, tag: str) -> None:
        # 载入配置文件
        config = self.load_config()
        
        # 删除对应的平台
        del config["platforms"][tag]

        # 保存配置文件
        self.save_config(config)

        # 更新控件
        self.update_custom_platform_widgets(self.flow_card)

    # 生成 UI 描述数据
    def generate_ui_datas(self, platforms: dict, is_custom: bool) -> list:
        ui_datas = []
        
        for k, v in platforms.items():
            if not is_custom:
                ui_datas.append(
                    {
                        "name": v.get("name"),
                        "menus": [
                            (
                                FluentIcon.EDIT,
                                "编辑接口",
                                partial(self.show_api_edit_message_box, k),
                            ),
                            (
                                FluentIcon.SEND,
                                "测试接口",
                                partial(self.api_test, k),
                            ),
                        ],
                    },
                )
            else:
                ui_datas.append(
                    {
                        "name": v.get("name"),
                        "menus": [
                            (
                                FluentIcon.EDIT,
                                "编辑接口",
                                partial(self.show_api_edit_message_box, k),
                            ),
                            (
                                FluentIcon.SEND,
                                "测试接口",
                                partial(self.api_test, k),
                            ),
                            (
                                FluentIcon.DELETE,
                                "删除接口",
                                partial(self.delete_platform, k),
                            ),
                        ],
                    },
                )

        return ui_datas

    # 显示 API 编辑对话框
    def show_api_edit_message_box(self, key: str):
        api_edit_message_box = APIEditMessageBox(self.window, self.configurator, key)
        api_edit_message_box.exec()

    # 初始化下拉按钮
    def init_drop_down_push_button(self, widget, datas):
        for item in datas:
            drop_down_push_button = PrimaryDropDownPushButton(item.get("name"))
            drop_down_push_button.setFixedWidth(192)
            drop_down_push_button.setContentsMargins(4, 0, 4, 0) # 左、上、右、下
            widget.add_widget(drop_down_push_button)

            menu = RoundMenu(drop_down_push_button)
            for k, v in enumerate(item.get("menus")):
                menu.addAction(
                    Action(
                        v[0],
                        v[1],
                        triggered = v[2],
                    )
                )

                # 最后一个菜单不加分割线
                menu.addSeparator() if k != len(item.get("menus")) - 1 else None
            drop_down_push_button.setMenu(menu)

    # 更新自定义平台控件
    def update_custom_platform_widgets(self, widget):
        config = self.load_config()
        platforms = {k:v for k, v in config.get("platforms").items() if v.get("group") == "custom"}

        widget.take_all_widgets()
        self.init_drop_down_push_button(
            widget,
            self.generate_ui_datas(platforms, True)
        )

    # 添加头部
    def add_head_widget(self, parent, config):
        platforms = {k:v for k, v in config.get("platforms").items() if v.get("group") == "local"}
        parent.addWidget(
            FlowCard(
                "本地接口", 
                "管理应用内置的本地大语言模型的接口信息",
                init = lambda widget: self.init_drop_down_push_button(
                    widget,
                    self.generate_ui_datas(platforms, False),
                ),
            )
        )

    # 添加主体
    def add_body_widget(self, parent, config):
        platforms = {k:v for k, v in config.get("platforms").items() if v.get("group") == "online"}
        parent.addWidget(
            FlowCard(
                "在线接口", 
                "管理应用内置的主流大语言模型的接口信息",
                init = lambda widget: self.init_drop_down_push_button(
                    widget,
                    self.generate_ui_datas(platforms, False),
                ),
            )
        )

    # 添加底部
    def add_foot_widget(self, parent, config):

        def message_box_close(widget, text: str):
            # 生成一个随机 TAG
            tag = f"custom_platform_{random.randint(100000, 999999)}"

            # 修改和保存配置
            platform = copy.deepcopy(self.CUSTOM)
            platform["tag"] = tag
            platform["name"] = text.strip()
            config["platforms"][tag] = platform
            self.save_config(config)

            # 更新UI
            self.update_custom_platform_widgets(self.flow_card)

        def on_add_button_clicked(widget):
            message_box = LineEditMessageBox(
                self.window,
                "请输入新的接口名称 ...",
                message_box_close = message_box_close
            )
            
            message_box.exec()

        def init(widget):
            # 添加新增按钮
            add_button = PrimaryPushButton("新增")
            add_button.setIcon(FluentIcon.ADD_TO)
            add_button.setContentsMargins(4, 0, 4, 0)
            add_button.clicked.connect(lambda: on_add_button_clicked(self))
            widget.add_widget_to_head(add_button)

            # 更新控件
            self.update_custom_platform_widgets(widget)

        self.flow_card = FlowCard(
            "自定义接口", 
            "在此添加和管理任何符合 OpenAI 格式或者 Anthropic 格式的大语言模型的接口信息",
            init = init,
        )
        parent.addWidget(self.flow_card)