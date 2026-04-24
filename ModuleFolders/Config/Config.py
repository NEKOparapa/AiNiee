import os
import threading
import traceback

import rapidjson as json
from rich import print

from ModuleFolders.Infrastructure.Platform.PlatformPaths import (
    config_path,
    migrate_config_if_needed,
    resource_path,
)


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
                with open(ConfigMixin.CONFIG_PATH, "r", encoding="utf-8") as reader:
                    config = json.load(reader)
            else:
                print("[[red]WARNING[/]] Config file does not exist ...")

        return config

    def save_config(self, new: dict) -> dict:
        old = {}

        with ConfigMixin.CONFIG_FILE_LOCK:
            migrate_config_if_needed()
            ConfigMixin.CONFIG_PATH = config_path()
            if os.path.exists(ConfigMixin.CONFIG_PATH):
                with open(ConfigMixin.CONFIG_PATH, "r", encoding="utf-8") as reader:
                    old = json.load(reader)

        if old == new:
            return old

        for key, value in new.items():
            old[key] = value

        with ConfigMixin.CONFIG_FILE_LOCK:
            os.makedirs(os.path.dirname(ConfigMixin.CONFIG_PATH), exist_ok=True)
            with open(ConfigMixin.CONFIG_PATH, "w", encoding="utf-8") as writer:
                writer.write(json.dumps(old, indent=4, ensure_ascii=False))

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
