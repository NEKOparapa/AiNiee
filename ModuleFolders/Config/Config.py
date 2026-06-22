import os
import threading
import traceback

import rapidjson as json
from rich import print

from ModuleFolders.Config.FilePathConfig import (
    config_path,
    resource_path,
)
from ModuleFolders.Infrastructure.Platform.RuntimeSetup import migrate_config_if_needed


class ConfigMixin:
    CONFIG_PATH = config_path()
    CONFIG_FILE_LOCK = threading.Lock()

    multilingual_interface_dict = {}
    current_interface_language = "简中"
    translation_json_file = resource_path("Localization")

    @classmethod
    def tra(cls, text):
        translation = ConfigMixin.multilingual_interface_dict.get(text)
        if translation:
            translation_text = translation.get(ConfigMixin.current_interface_language)
            if translation_text:
                return translation_text
        return text

    @classmethod
    def load_translations(cls, folder_path):
        combined_data = {}

        if not os.path.isdir(folder_path):
            print(f"[[red]WARNING[/]] Translation folder does not exist: {folder_path}")
            return combined_data

        for filename in os.listdir(folder_path):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(folder_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    for top_level_key in data:
                        for key, value in data[top_level_key].items():
                            combined_data[key] = value
            except Exception as error:
                print(f"[red]Error loading translation file {filename}: {error}[/red]")
                traceback.print_exc()

        return combined_data

    def load_config(self) -> dict:
        config = {}

        with ConfigMixin.CONFIG_FILE_LOCK:
            migrate_config_if_needed()
            ConfigMixin.CONFIG_PATH = config_path()
            if os.path.exists(ConfigMixin.CONFIG_PATH):
                try:
                    with open(ConfigMixin.CONFIG_PATH, "r", encoding="utf-8") as reader:
                        config = json.load(reader)
                    if not isinstance(config, dict):
                        raise ValueError("config root is not a JSON object")
                except (json.JSONDecodeError, OSError, ValueError) as error:
                    print(f"[[red]WARNING[/]] Config unreadable, using defaults: {error}")
                    try:
                        os.replace(ConfigMixin.CONFIG_PATH, f"{ConfigMixin.CONFIG_PATH}.corrupt")
                    except OSError:
                        pass
                    config = {}

                # 旧版 DeepSeek 配置临时兼容块。
                # 当旧版内置配置不再需要自动修复时，可直接删除此块。
                platforms = config.get("platforms")
                deepseek_platform = platforms.get("deepseek") if isinstance(platforms, dict) else None
                if isinstance(deepseek_platform, dict) and deepseek_platform.get("tag") == "deepseek":
                    if deepseek_platform.get("think_switch") is False and deepseek_platform.get("think_depth") == "low":
                        deepseek_platform["think_switch"] = True
                        deepseek_platform["think_depth"] = "high"
                        tmp_path = f"{ConfigMixin.CONFIG_PATH}.tmp"
                        with open(tmp_path, "w", encoding="utf-8") as writer:
                            writer.write(json.dumps(config, indent=4, ensure_ascii=False))
                        os.replace(tmp_path, ConfigMixin.CONFIG_PATH)
            else:
                print("[[red]WARNING[/]] Config file does not exist ...")

        if config:
            from ModuleFolders.Config.FilePathConfig import (
                default_input_dir,
                default_output_dir,
                default_polish_output_dir,
                resolve_user_dir,
            )
            if "label_input_path" in config:
                config["label_input_path"] = resolve_user_dir(
                    config["label_input_path"],
                    default_input_dir(),
                    ("./input", "input"),
                )
            if "label_output_path" in config:
                config["label_output_path"] = resolve_user_dir(
                    config["label_output_path"],
                    default_output_dir(),
                    ("./output", "output"),
                )
            if "label_polish_output_path" in config:
                config["label_polish_output_path"] = resolve_user_dir(
                    config["label_polish_output_path"],
                    default_polish_output_dir(),
                    ("./polish_output", "polish_output"),
                )

        return config

    def save_config(self, new: dict) -> dict:
        with ConfigMixin.CONFIG_FILE_LOCK:
            migrate_config_if_needed()
            ConfigMixin.CONFIG_PATH = config_path()
            old = {}
            if os.path.exists(ConfigMixin.CONFIG_PATH):
                try:
                    with open(ConfigMixin.CONFIG_PATH, "r", encoding="utf-8") as reader:
                        old = json.load(reader)
                    if not isinstance(old, dict):
                        old = {}
                except (json.JSONDecodeError, OSError):
                    old = {}

            if old == new:
                return old

            for key, value in new.items():
                old[key] = value

            os.makedirs(os.path.dirname(ConfigMixin.CONFIG_PATH), exist_ok=True)
            tmp_path = f"{ConfigMixin.CONFIG_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as writer:
                writer.write(json.dumps(old, indent=4, ensure_ascii=False))
            os.replace(tmp_path, ConfigMixin.CONFIG_PATH)

        return old

    def fill_config(self, old: dict, new: dict) -> dict:
        for key, value in new.items():
            if isinstance(value, dict) and key in old:
                old[key] = self.fill_config(old[key], value)
            elif key not in old:
                old[key] = value

        return old

    def load_config_from_default(self) -> dict:
        config = self.load_config()
        return self.fill_config(config, getattr(self, "default", {}))
