"""Backend-owned configuration persistence and migration."""
import os
import threading

import rapidjson as json
from rich import print

from Backend.core.paths import config_path
from Backend.infrastructure.config.migration import migrate_config_if_needed, migrate_retired_project_type
from Backend.domain.text.regex import RegexSwitchHelper
from Backend.domain.config.tables import TableConfigHelper
from Backend.domain.config.prompt_selection import TranslationPromptConfigHelper
from Backend.domain.config.media_task_config import migrate_media_task_settings, validate_media_task_settings
from Backend.domain.config.transcription_config import validate_transcription_platform
from Backend.domain.config.ocr_config import validate_ocr_platform
from Backend.domain.config.image_generation_config import validate_image_generation_platform
from Backend.domain.config.request_defaults import normalize_request_timeouts


class ConfigStore:
    CONFIG_FILE_LOCK = threading.RLock()
    CONFIG_PATH = None
    RETIRED_SETTINGS = frozenset((
        "http_server_enable", "http_listen_address", "http_callback_url",
        "response_conversion_toggle", "opencc_preset",
        "polishing_pre_line_counts", "label_polish_output_path",
    ))

    def initialize_config(self):
        from Backend.infrastructure.config.defaults import get_defaults
        with self.CONFIG_FILE_LOCK:
            return self.save_config(self.fill_config(ConfigStore.load_config(self), get_defaults()))

    @staticmethod
    def get_default_section(name):
        from Backend.infrastructure.config.defaults import get_default_section
        try:
            return get_default_section(name)
        except KeyError as error:
            raise ValueError("未知配置分组") from error

    @staticmethod
    def get_platform_presets():
        from Backend.core.paths import platform_preset_path
        with open(platform_preset_path(), "r", encoding="utf-8") as reader:
            return json.load(reader)

    def get_prompt_presets(self, kind):
        from Backend.domain.prompts.prompt_builder_enum import PromptBuilderEnum
        if kind == "translation":
            from Backend.domain.prompts.prompt_builder import PromptBuilder
            config = self.load_config()
            config.setdefault("target_language", "chinese_simplified")
            return {
                str(preset): PromptBuilder.get_system_default(config, preset)
                for preset in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT, PromptBuilderEnum.LOCAL)
            }
        if kind == "polishing":
            from Backend.domain.prompts.prompt_builder_polishing import PromptBuilderPolishing
            return {str(PromptBuilderEnum.POLISH_COMMON): PromptBuilderPolishing.get_system_default(self.load_config())}
        if kind == "extraction":
            from Backend.domain.prompts.prompt_builder_extraction import PromptBuilderExtraction
            return {stage: PromptBuilderExtraction.get_system_default(stage) for stage in PromptBuilderExtraction.STAGES}
        raise ValueError("未知提示词类型")

    @staticmethod
    def get_config_info():
        return {"path": str(config_path().resolve())}

    @staticmethod
    def _validate_mcp_settings(config):
        if "mcp_enable" in config and type(config["mcp_enable"]) is not bool:
            raise ValueError("配置字段 mcp_enable 必须是布尔值")

    @staticmethod
    def _validate_profile(profile):
        if not isinstance(profile, dict):
            raise ValueError("配置文件的根节点必须是 JSON 对象")
        ConfigStore._validate_mcp_settings(profile)
        validate_media_task_settings(profile)
        for key in ("platforms", "api_settings", "response_check_switch", "transcription_platforms", "ocr_platforms", "image_generation_platforms"):
            if key in profile and not isinstance(profile[key], dict):
                raise ValueError(f"配置字段 {key} 必须是 JSON 对象")
        if any(not isinstance(value, dict) for value in profile.get("platforms", {}).values()):
            raise ValueError("接口配置必须是 JSON 对象")
        if "active_transcription_platform" in profile and not isinstance(profile["active_transcription_platform"], str):
            raise ValueError("配置字段 active_transcription_platform 必须是字符串")
        for identifier, platform in profile.get("transcription_platforms", {}).items():
            validate_transcription_platform(identifier, platform)
        if "active_ocr_platform" in profile and not isinstance(profile["active_ocr_platform"], str):
            raise ValueError("配置字段 active_ocr_platform 必须是字符串")
        for identifier, platform in profile.get("ocr_platforms", {}).items():
            validate_ocr_platform(identifier, platform)
        if "active_image_generation_platform" in profile and not isinstance(profile["active_image_generation_platform"], str):
            raise ValueError("配置字段 active_image_generation_platform 必须是字符串")
        for identifier, platform in profile.get("image_generation_platforms", {}).items():
            validate_image_generation_platform(identifier, platform)
        for kind in TableConfigHelper.KINDS:
            key = f"{kind}_tables"
            if key not in profile:
                continue
            tables = profile[key]
            if not isinstance(tables, list) or any(
                not isinstance(table, dict) or not isinstance(table.get("rows", []), list)
                or any(not isinstance(row, dict) for row in table.get("rows", []))
                for table in tables
            ):
                raise ValueError(f"配置字段 {key} 必须是有效的表格列表")

    def import_config(self, path):
        from pathlib import Path
        try:
            with Path(path).expanduser().open("r", encoding="utf-8-sig") as reader:
                profile = json.load(reader)
        except (OSError, ValueError) as error:
            raise ValueError("无法在后端读取配置文件，请检查文件路径和 JSON 格式") from error
        self._validate_profile(profile)
        # Apply explicitly imported table collections as well as ordinary settings.
        # update_config holds the lock across read/normalization/atomic replacement.
        return self.update_config(lambda config: config.update(profile))

    def export_config(self, directory):
        from pathlib import Path
        import tempfile
        destination = Path(directory).expanduser().resolve()
        if not destination.is_dir():
            raise ValueError("后端无法访问配置导出目录")
        output = destination / "ainiee_profile.json"
        temporary = None
        try:
            with self.CONFIG_FILE_LOCK:
                config = self.load_config()
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination, suffix=".tmp", delete=False) as writer:
                    temporary = writer.name
                    writer.write(json.dumps(config, indent=4, ensure_ascii=False))
                os.replace(temporary, output)
                temporary = None
        except OSError as error:
            raise ValueError("后端无法保存配置备份") from error
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        return {"path": str(output)}

    def load_config(self) -> dict:
        config = {}

        with ConfigStore.CONFIG_FILE_LOCK:
            migrate_config_if_needed()
            ConfigStore.CONFIG_PATH = config_path()
            needs_write = False
            if os.path.exists(ConfigStore.CONFIG_PATH):
                try:
                    with open(ConfigStore.CONFIG_PATH, "r", encoding="utf-8") as reader:
                        config = json.load(reader)
                    if not isinstance(config, dict):
                        raise ValueError("config root is not a JSON object")
                except (json.JSONDecodeError, OSError, ValueError) as error:
                    print(f"[[red]WARNING[/]] Config unreadable, using defaults: {error}")
                    try:
                        os.replace(ConfigStore.CONFIG_PATH, f"{ConfigStore.CONFIG_PATH}.corrupt")
                    except OSError:
                        pass
                    config = {}

                # Invalid persisted booleans must not silently turn a disabled
                # MCP endpoint on through Python's truthiness or default fill.
                self._validate_mcp_settings(config)
                needs_write = any(key in config for key in self.RETIRED_SETTINGS)
                for key in self.RETIRED_SETTINGS:
                    config.pop(key, None)
                needs_write = migrate_retired_project_type(config) or needs_write
                needs_write = RegexSwitchHelper.normalize_config(config) or needs_write
                needs_write = TableConfigHelper.normalize_config(config) or needs_write
                needs_write = TranslationPromptConfigHelper.normalize_config(config) or needs_write

                # 旧版 DeepSeek 配置临时兼容块。
                # 当旧版内置配置不再需要自动修复时，可直接删除此块。
                platforms = config.get("platforms")
                deepseek_platform = platforms.get("deepseek") if isinstance(platforms, dict) else None
                if isinstance(deepseek_platform, dict) and deepseek_platform.get("tag") == "deepseek":
                    if deepseek_platform.get("think_switch") is False and deepseek_platform.get("think_depth") == "low":
                        deepseek_platform["think_switch"] = True
                        deepseek_platform["think_depth"] = "high"
                        needs_write = True

            else:
                print("[[red]WARNING[/]] Config file does not exist ...")

            # Migrate before initialize_config merges defaults, so saved provider
            # options seed the new task settings rather than being overwritten.
            needs_write = migrate_media_task_settings(config) or needs_write
            needs_write = normalize_request_timeouts(config) or needs_write
            if needs_write:
                os.makedirs(os.path.dirname(ConfigStore.CONFIG_PATH), exist_ok=True)
                tmp_path = f"{ConfigStore.CONFIG_PATH}.tmp"
                with open(tmp_path, "w", encoding="utf-8") as writer:
                    writer.write(json.dumps(config, indent=4, ensure_ascii=False))
                os.replace(tmp_path, ConfigStore.CONFIG_PATH)

        if config:
            from Backend.core.paths import (
                default_input_dir,
                default_output_dir,
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

        return config

    def save_config(self, new: dict, *, _table_update: bool = False) -> dict:
        self._validate_mcp_settings(new)
        with ConfigStore.CONFIG_FILE_LOCK:
            migrate_config_if_needed()
            ConfigStore.CONFIG_PATH = config_path()
            old = {}
            if os.path.exists(ConfigStore.CONFIG_PATH):
                try:
                    with open(ConfigStore.CONFIG_PATH, "r", encoding="utf-8") as reader:
                        old = json.load(reader)
                    if not isinstance(old, dict):
                        old = {}
                except (json.JSONDecodeError, OSError):
                    old = {}

            retired = any(key in old for key in self.RETIRED_SETTINGS)
            for key in self.RETIRED_SETTINGS:
                old.pop(key, None)
            new = {key: value for key, value in new.items() if key not in self.RETIRED_SETTINGS}
            unchanged = old == new

            table_keys = {
                f"{kind}_{suffix}"
                for kind in TableConfigHelper.KINDS
                for suffix in ("tables", "active_table_id")
            }
            for key, value in new.items():
                # Settings/task initialization may save an old full config snapshot.
                # Existing tables can only be changed through the atomic edit API.
                if not _table_update and key in table_keys and key in old:
                    continue
                old[key] = value

            self._validate_mcp_settings(old)
            media_changed = migrate_media_task_settings(old)
            timeout_changed = normalize_request_timeouts(old)
            validate_media_task_settings(old)
            prompt_changed = TranslationPromptConfigHelper.normalize_config(old)
            project_type_changed = migrate_retired_project_type(old)
            if unchanged and not media_changed and not timeout_changed and not prompt_changed and not project_type_changed and not retired:
                return old

            os.makedirs(os.path.dirname(ConfigStore.CONFIG_PATH), exist_ok=True)
            tmp_path = f"{ConfigStore.CONFIG_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as writer:
                writer.write(json.dumps(old, indent=4, ensure_ascii=False))
            os.replace(tmp_path, ConfigStore.CONFIG_PATH)

        return old

    def update_config(self, updater) -> dict:
        """Apply an edit to the latest config under one lock, including table edits by ID."""
        with ConfigStore.CONFIG_FILE_LOCK:
            # Explicit edits always use persisted settings, including when the
            # caller is a ConfigMixin operating within a task read snapshot.
            config = ConfigStore.load_config(self)
            TableConfigHelper.normalize_config(config)
            updater(config)
            TableConfigHelper.normalize_config(config)
            return self.save_config(config, _table_update=True)

    def fill_config(self, old: dict, new: dict) -> dict:
        for key, value in new.items():
            # Provider IDs form a user-owned collection. Once initialized, an
            # intentionally deleted default provider must not return at startup.
            if key in ("transcription_platforms", "ocr_platforms", "image_generation_platforms") and key in old:
                continue
            if isinstance(value, dict) and isinstance(old.get(key), dict):
                old[key] = self.fill_config(old[key], value)
            elif key not in old:
                old[key] = value

        return old

