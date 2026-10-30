"""Manual export and cache saving extracted from the desktop command bar."""

from pathlib import Path

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Application.SettingsDefaults import fill_setting_defaults
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import auto_output_dir


class ExportService(ConfigMixin):
    def __init__(self, cache_manager, file_writer, task_executor) -> None:
        self.cache_manager = cache_manager
        self.file_writer = file_writer
        self.task_executor = task_executor

    def export(self, output_path: str | None = None) -> dict:
        with exclusive_operation():
            project = self.cache_manager.project
            if project is None:
                raise ApplicationError("project_not_open", 409)
            config = fill_setting_defaults(self.load_config())
            input_path = config.get("label_input_path") or project.input_path
            if not input_path:
                raise ApplicationError("project_input_path_missing", 400)
            selected_path = output_path
            if selected_path is None:
                selected_path = (
                    auto_output_dir(input_path) if config["auto_set_output_path"]
                    else config["label_output_path"]
                )
            if not isinstance(selected_path, str) or not selected_path.strip() or "\x00" in selected_path:
                raise ApplicationError("export_path_invalid", 400)
            try:
                destination = Path(selected_path).expanduser().resolve()
                if destination.exists() and not destination.is_dir():
                    raise ApplicationError("export_path_invalid", 400)
                if config.get("response_conversion_toggle"):
                    if not self.task_executor._convert_translated_text_with_opencc(config.get("opencc_preset")):
                        raise ApplicationError("export_conversion_failed", 500)
                output_config = {
                    "translated_suffix": config.get("output_filename_suffix"),
                    "bilingual_suffix": "_bilingual",
                    "bilingual_order": config.get("bilingual_text_order", "translation_first"),
                    "source_lang_code": self.task_executor._resolve_output_source_language(config.get("source_language")),
                    "target_lang_code": self.task_executor._resolve_output_target_language(config.get("target_language")),
                }
                before = self._file_snapshot(destination)
                self.file_writer.output_translated_content(project, str(destination), input_path, output_config)
                after = self._file_snapshot(destination)
                files = sorted(name for name, stamp in after.items() if before.get(name) != stamp)
                self.cache_manager.save_to_file()
            except ApplicationError:
                raise
            except (PermissionError, OSError, ValueError) as error:
                raise ApplicationError("export_failed", 500) from error
            except Exception as error:
                raise ApplicationError("export_failed", 500) from error
            return {"output_path": str(destination), "files": files}

    def save_cache(self) -> dict:
        with exclusive_operation():
            if self.cache_manager.project is None:
                raise ApplicationError("project_not_open", 409)
            try:
                self.cache_manager.save_to_file()
            except Exception as error:
                raise ApplicationError("cache_save_failed", 500) from error
        return {"saved": True}

    @staticmethod
    def _file_snapshot(directory: Path) -> dict[str, tuple[int, int]]:
        if not directory.exists():
            return {}
        result = {}
        for path in directory.rglob("*"):
            if path.is_file():
                stat = path.stat()
                result[path.relative_to(directory).as_posix()] = (stat.st_mtime_ns, stat.st_size)
        return result
