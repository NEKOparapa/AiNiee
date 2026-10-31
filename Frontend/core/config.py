"""Desktop configuration API and local interface translations; no configuration files."""
import os
import traceback

import rapidjson as json
from rich import print


class ConfigMixin:
    remote_client = None
    remote_required = True

    multilingual_interface_dict = {}
    current_interface_language = "简中"

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

    @staticmethod
    def config_backend():
        if ConfigMixin.remote_client is None:
            raise RuntimeError("后端配置服务未连接，无法读取或修改配置")
        return ConfigMixin.remote_client

    def load_config(self) -> dict:
        return self.config_backend().load_config()

    def save_config(self, new: dict, *, _table_update: bool = False) -> dict:
        return self.config_backend().save_config(new, _table_update=_table_update)

    def update_config(self, updater) -> dict:
        return self.config_backend().update_config(updater)

    def get_default_section(self, name: str) -> dict:
        return self.config_backend().get_default_section(name)

    def get_platform_presets(self) -> dict:
        return self.config_backend().get_platform_presets()

    def get_prompt_presets(self, kind: str) -> dict:
        return self.config_backend().get_prompt_presets(kind)

    def get_config_info(self) -> dict:
        return self.config_backend().get_config_info()

    def import_config(self, path: str) -> dict:
        return self.config_backend().import_config(path)

    def export_config(self, directory: str) -> dict:
        return self.config_backend().export_config(directory)

    def initialize_config(self) -> dict:
        return self.load_config()

    def load_config_from_default(self) -> dict:
        return self.load_config()
