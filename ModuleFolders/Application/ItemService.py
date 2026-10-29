"""Project item queries and manual edits, independent of a UI or HTTP server."""

import json
import re

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager


class ItemService:
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager

    @staticmethod
    def item_id(file: str, index: int) -> str:
        return json.dumps([file, index], ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def serialize(cls, file, item, position):
        return {
            "id": cls.item_id(file, item.text_index), "file": file,
            "index": item.text_index, "position": position,
            "source_text": item.source_text or "", "translated_text": item.translated_text or "",
            "translation_status": item.translation_status, "model": item.model or "",
            "flagged": bool((item.extra or {}).get("language_mismatch_translation", False)),
        }

    def list_items(self, file=None, status=None, q="", regex=False, flagged=None, page=1, size=100):
        try:
            pattern = re.compile(q) if regex and q else None
        except re.error as error:
            raise ApplicationError("item_regex_invalid", 400) from error
        if page < 1 or not 1 <= size <= 1000:
            raise ApplicationError("item_pagination_invalid", 400)
        with self.cache_manager.file_lock:
            project = self.cache_manager.project
            if project is None:
                raise ApplicationError("project_not_open", 409)
            rows = []
            total = 0
            start = (page - 1) * size
            for path, cache_file in project.files.items():
                if file is not None and path != file:
                    continue
                for position, item in enumerate(cache_file.items):
                    is_flagged = bool((item.extra or {}).get("language_mismatch_translation", False))
                    if status is not None and item.translation_status != status:
                        continue
                    if flagged is not None and is_flagged != flagged:
                        continue
                    source, translation = item.source_text or "", item.translated_text or ""
                    if q and not (pattern.search(source) or pattern.search(translation) if pattern else q in source or q in translation):
                        continue
                    if start <= total < start + size:
                        rows.append(self.serialize(path, item, position))
                    total += 1
            return {"project_id": project.project_id, "items": rows, "total": total, "page": page, "size": size}

    def patch_item(self, file, index, changes, project_id=None):
        with exclusive_operation():
            with self.cache_manager.file_lock:
                project = self.cache_manager.project
                if project is None:
                    raise ApplicationError("project_not_open", 409)
                if project_id is not None and project.project_id != project_id:
                    raise ApplicationError("project_changed", 409)
                cache_file = project.files.get(file)
                if cache_file is None:
                    raise ApplicationError("item_not_found", 404)
                try:
                    item = cache_file.get_item(index)
                except KeyError as error:
                    raise ApplicationError("item_not_found", 404) from error
            if not changes or set(changes) - {"source_text", "translated_text"}:
                raise ApplicationError("item_patch_invalid", 400)
            if "source_text" in changes and not changes["source_text"].strip():
                raise ApplicationError("item_source_empty", 400)
            original = (item.source_text, item.translated_text, item.translation_status)
            # The legacy manager owns a non-reentrant file lock. Its public
            # editing/saving methods acquire it themselves; the operation guard
            # keeps the project and task stable across those calls.
            for field, value in changes.items():
                self.cache_manager.update_item_text(file, index, field, value)
            try:
                self.cache_manager.save_to_file()
            except OSError as error:
                with self.cache_manager.file_lock:
                    item.source_text, item.translated_text, item.translation_status = original
                raise ApplicationError("item_save_failed", 500) from error
            result = self.serialize(file, item, cache_file.index_of(index))
            project_id = project.project_id
        EventManager.get_singleton().emit(Base.EVENT.TABLE_UPDATE, {"project_id": project_id, "file": file, "index": index})
        return result
