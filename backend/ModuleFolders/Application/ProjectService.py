"""Project loading and browsing extracted from the desktop startup page."""

import os
import filecmp
import shutil
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import config_path, default_input_dir
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject


class ProjectService(ConfigMixin):
    def __init__(self, cache_manager: CacheManager, file_reader) -> None:
        self.cache_manager = cache_manager
        self.file_reader = file_reader

    def get_current(self) -> dict:
        config = self.load_config()
        with self.cache_manager.file_lock:
            project = self.cache_manager.project
            summary = self._summary(project) if project is not None else None
        return {
            "project": summary,
            "supported_project_types": self.file_reader.get_support_project_types(),
            "selected_project_type": config.get("translation_project", "AutoType"),
            "configured_path": config.get("label_input_path", str(default_input_dir())),
        }

    def open_project(self, path: str) -> dict:
        with exclusive_operation():
            source = self._existing_path(path)
            config = self.load_config()
            project_type = config.get("translation_project", "AutoType")
            cache_file = source.is_file() and source.name.startswith("AinieeCacheData") and source.suffix.lower() == ".json"
            restoring = cache_file or project_type == "Ainiee_cache"
            if not restoring and project_type not in self.file_reader.get_support_project_types():
                raise ApplicationError("project_type_unsupported", 400)
            try:
                if cache_file:
                    with self.cache_manager.file_lock:
                        current = self.cache_manager.project
                        if current is not None:
                            self._validate_project_id(current.project_id)
                            current_cache = (Path(CacheManager.get_project_cache_dir(current.project_id)) / CacheManager.CACHE_FILENAME).resolve()
                            if source == current_cache:
                                return self._summary(current)
                    candidate = CacheManager.read_from_file(source)
                else:
                    candidate = self.file_reader.read_files(
                        project_type, str(source), config.get("label_input_exclude_rule", ""),
                    )
            except (PermissionError, OSError) as error:
                raise ApplicationError("project_path_unreadable", 403) from error
            except Exception as error:
                raise ApplicationError("project_load_failed", 400) from error

            if not isinstance(candidate, CacheProject) or candidate.count_items() == 0:
                raise ApplicationError("project_empty", 400)
            CacheManager._ensure_project_metadata(candidate)
            self._validate_project_id(candidate.project_id)
            with self.cache_manager.file_lock:
                current = self.cache_manager.project
                if current is not None:
                    current_directory = Path(CacheManager.get_project_cache_dir(current.project_id)).resolve()
                    candidate_directory = Path(CacheManager.get_project_cache_dir(candidate.project_id)).resolve()
                    if current_directory == candidate_directory:
                        return self._summary(current)
            input_path = candidate.input_path if restoring else str(source)
            if not input_path:
                input_path = config.get("label_input_path", str(default_input_dir()))
            self._install(candidate, input_path)
            summary = self._summary(candidate)
        EventManager.get_singleton().emit(Base.EVENT.PROJECT_CHANGED, {"project_id": candidate.project_id})
        return summary

    def get_history(self) -> list[dict]:
        # CacheManager.list_project_histories removes invalid directories even
        # with prune=False. The web application must not delete from a GET, so
        # reuse its serializers while performing a strictly read-only scan.
        root = Path(CacheManager.get_project_cache_root())
        if not root.exists():
            return []
        histories = []
        try:
            for directory in root.iterdir():
                if not directory.is_dir():
                    continue
                try:
                    self._validate_project_id(directory.name)
                    cache_path = directory / CacheManager.CACHE_FILENAME
                    if not cache_path.is_file():
                        continue
                    stats_path = directory / CacheManager.STATS_FILENAME
                    stats = CacheManager._read_statistics_payload(stats_path)
                    if not isinstance(stats, dict):
                        try:
                            project = CacheManager.read_from_file(cache_path)
                            stats = CacheManager._build_stats_payload(project)
                        except Exception:
                            # Keep unreadable caches on disk and in the list;
                            # opening them reports a safe, explicit load error.
                            stats = {}
                    entry = CacheManager._build_history_entry_from_stats(
                        str(directory), str(cache_path), str(stats_path),
                        {**stats, "project_id": directory.name},
                    )
                    histories.append({key: entry[key] for key in (
                        "project_id", "project_name", "project_create_time", "total_line",
                        "line", "is_complete", "cache_path",
                    )})
                except (ApplicationError, OSError):
                    continue
        except OSError as error:
            raise ApplicationError("project_history_unreadable", 403) from error
        histories.sort(key=lambda entry: (entry["project_create_time"], entry["project_id"]), reverse=True)
        return histories

    def delete_history(self, project_id: str) -> dict:
        with exclusive_operation():
            self._validate_project_id(project_id)
            with self.cache_manager.file_lock:
                current = self.cache_manager.project
                directory = Path(CacheManager.get_project_cache_dir(project_id))
                resolved_directory = directory.resolve()
                if current is not None:
                    current_directory = Path(CacheManager.get_project_cache_dir(current.project_id)).resolve()
                    if resolved_directory == current_directory:
                        # Path equality follows the platform's case semantics;
                        # resolution also catches junction/symlink aliases.
                        raise ApplicationError("project_history_current", 409)
                if directory.is_symlink() or directory.is_junction():
                    raise ApplicationError("project_cache_invalid", 400)
                if not directory.is_dir():
                    raise ApplicationError("project_history_not_found", 404)
                if not CacheManager.delete_project_cache(project_id):
                    raise ApplicationError("project_history_delete_failed", 500)
        EventManager.get_singleton().emit(Base.EVENT.PROJECT_HISTORY_CHANGED, {})
        return {"deleted": True}

    def _install(self, candidate: CacheProject, input_path: str) -> None:
        # The candidate can be an external backup whose ID already has newer
        # history. Preserve both files and config until the whole install has
        # succeeded, including failures between the two legacy cache writes.
        try:
            with self.cache_manager.file_lock, ConfigMixin.CONFIG_FILE_LOCK:
                previous = self.cache_manager.project
                if previous is not None:
                    self._validate_project_id(previous.project_id)
                    CacheManager._write_project_cache_files(previous)
                self._validate_project_id(candidate.project_id)
                directory = Path(CacheManager.get_project_cache_dir(candidate.project_id))
                if directory.is_symlink() or directory.is_junction():
                    raise ApplicationError("project_cache_invalid", 400)
                directory.mkdir(parents=True, exist_ok=True)
                paths = [directory / CacheManager.CACHE_FILENAME, directory / CacheManager.STATS_FILENAME, config_path()]
                try:
                    with self._preserve_files(paths):
                        CacheManager._write_project_cache_files(candidate)
                        self.update_config(lambda config: config.update({"label_input_path": input_path}))
                        self.cache_manager.load_from_project(candidate)
                except Exception:
                    self.cache_manager.project = previous
                    raise
                Base.work_status = Base.STATUS.IDLE
        except ApplicationError:
            raise
        except Exception as error:
            raise ApplicationError("project_save_failed", 500) from error

    @staticmethod
    @contextmanager
    def _preserve_files(paths: list[Path]):
        backups: dict[Path, Path | None] = {}

        def discard_backups():
            for backup in backups.values():
                if backup is not None:
                    try:
                        backup.unlink(missing_ok=True)
                    except OSError:
                        # A leftover backup is preferable to reporting a failed
                        # operation after an otherwise successful installation.
                        pass

        try:
            for path in paths:
                if path.is_symlink():
                    raise ApplicationError("project_cache_invalid", 400)
                if path.exists():
                    handle, filename = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".backup", dir=path.parent)
                    os.close(handle)
                    backup = Path(filename)
                    backups[path] = backup
                    shutil.copyfile(path, backup)
                else:
                    backups[path] = None
        except Exception:
            # No application writes have started; original files are intact.
            discard_backups()
            raise

        try:
            yield
        except Exception as error:
            rollback_errors = []
            for path, backup in backups.items():
                try:
                    if backup is None:
                        path.unlink(missing_ok=True)
                    elif path.is_file() and filecmp.cmp(path, backup, shallow=False):
                        backup.unlink()
                    else:
                        os.replace(backup, path)
                except OSError as rollback_error:
                    # Keep any unrestored backup available for recovery.
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                raise ExceptionGroup("Unable to restore project files", rollback_errors) from error
            raise
        else:
            discard_backups()

    @staticmethod
    def _summary(project: CacheProject) -> dict:
        with project.atomic_scope():
            return {
                "project_id": project.project_id,
                "project_name": project.project_name,
                "project_type": project.project_type,
                "project_create_time": project.project_create_time,
                "input_path": project.input_path,
                "file_count": len(project.files),
                "item_count": project.count_items(),
            }

    def get_files(self) -> list[dict]:
        with self.cache_manager.file_lock:
            project = self._require_project()
            result = []
            with project.atomic_scope():
                for path, file in sorted(project.files.items()):
                    with file.atomic_scope():
                        counts = Counter(item.translation_status for item in file.items)
                        result.append({
                            "path": path,
                            "project_type": file.file_project_type,
                            "encoding": file.encoding,
                            "item_count": len(file.items),
                            "translated_count": counts[TranslationStatus.TRANSLATED],
                            "polished_count": counts[TranslationStatus.POLISHED],
                            "excluded_count": counts[TranslationStatus.EXCLUDED],
                            "questionable_count": counts[TranslationStatus.QUESTIONABLE],
                            "language_stats": [
                                {"language": language, "count": count, "confidence": confidence}
                                for language, count, confidence in file.language_stats
                            ],
                        })
            return result

    def get_stats(self) -> dict:
        with self.cache_manager.file_lock:
            project = self._require_project()
            with project.atomic_scope():
                counts = Counter(item.translation_status for item in project.items_iter())
                stats = project.stats_data.to_dict() if project.stats_data is not None else {}
        known = {
            "untranslated": TranslationStatus.UNTRANSLATED,
            "translated": TranslationStatus.TRANSLATED,
            "polished": TranslationStatus.POLISHED,
            "excluded": TranslationStatus.EXCLUDED,
            "questionable": TranslationStatus.QUESTIONABLE,
        }
        result = {name: counts[status] for name, status in known.items()}
        return {
            "total": sum(counts.values()), **result,
            "other": sum(count for status, count in counts.items() if status not in known.values()),
            "progress": stats,
        }

    def _require_project(self) -> CacheProject:
        if self.cache_manager.project is None:
            raise ApplicationError("project_not_open", 409)
        return self.cache_manager.project

    @staticmethod
    def _validate_project_id(project_id: str) -> None:
        # Cache IDs are path segments, including old IDs that predate UUIDs.
        if (
            not isinstance(project_id, str) or not project_id or project_id in (".", "..")
            or any(character in project_id for character in '/\\:\x00')
        ):
            raise ApplicationError("project_cache_invalid", 400)
        root = Path(CacheManager.get_project_cache_root()).resolve()
        target = (root / project_id).resolve()
        if target.parent != root:
            raise ApplicationError("project_cache_invalid", 400)

    @staticmethod
    def _existing_path(value: str) -> Path:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ApplicationError("project_path_invalid", 400)
        try:
            path = Path(value.strip()).expanduser().resolve(strict=True)
            if not path.is_dir() and not path.is_file():
                raise ApplicationError("project_path_invalid", 400)
            return path
        except FileNotFoundError as error:
            raise ApplicationError("project_path_not_found", 404) from error
        except (PermissionError, OSError) as error:
            raise ApplicationError("project_path_unreadable", 403) from error
        except (ValueError, RuntimeError) as error:
            raise ApplicationError("project_path_invalid", 400) from error

    def list_directory(self, path: str = "") -> dict:
        if not path.strip():
            configured = Path(self.load_config().get("label_input_path", str(default_input_dir())))
            path = str(configured if configured.exists() else Path.home())
        current = self._existing_path(path)
        if current.is_file():
            current = current.parent
        try:
            with os.scandir(current) as iterator:
                entries = []
                for entry in iterator:
                    try:
                        is_directory = entry.is_dir()
                        if is_directory or entry.is_file():
                            entries.append({
                                "name": entry.name, "path": str(current / entry.name),
                                "is_directory": is_directory,
                            })
                    except OSError:
                        # A disappearing or inaccessible child should not make
                        # the rest of the selected directory unusable.
                        continue
            entries.sort(key=lambda entry: (not entry["is_directory"], entry["name"].casefold()))
            roots = os.listdrives() if os.name == "nt" else ["/"]
        except OSError as error:
            raise ApplicationError("project_path_unreadable", 403) from error
        return {
            "path": str(current),
            "parent": str(current.parent) if current.parent != current else None,
            "roots": roots,
            "entries": entries,
        }
