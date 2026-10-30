"""Manual analysis editing and table interchange extracted from AnalysisPage."""

import base64
import binascii
from copy import deepcopy
import json

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Application.TableService import TableService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager


class AnalysisService:
    VIEWS = ("characters", "terms", "non_translate")
    DEFAULTS = {
        "characters": {"source": "", "recommended_translation": "", "gender": "其他", "occurrence_count": 1, "note": ""},
        "terms": {"source": "", "recommended_translation": "", "category_path": "Other", "occurrence_count": 1, "note": ""},
        "non_translate": {"marker": "", "category": "Other", "occurrence_count": 1, "note": ""},
    }
    CATEGORIES = {"characters": "gender", "terms": "category_path", "non_translate": "category"}

    def __init__(self, cache_manager):
        self.cache_manager = cache_manager

    @staticmethod
    def _text(value):
        return "" if value is None else str(value).strip()

    @staticmethod
    def _count(value):
        try:
            return max(1, int(value))
        except (TypeError, ValueError, OverflowError):
            return 1

    @classmethod
    def _category(cls, value, default):
        return " ".join(cls._text(value).split()) or default

    @staticmethod
    def _identity_field(view):
        return "marker" if view == "non_translate" else "source"

    @classmethod
    def _validate_view(cls, view):
        if view not in cls.VIEWS:
            raise ApplicationError("analysis_view_invalid", 404)

    def _project(self, project_id=None):
        project = self.cache_manager.project
        if project is None:
            raise ApplicationError("project_not_open", 409)
        if project_id is not None and project_id != project.project_id:
            raise ApplicationError("project_changed", 409)
        return project

    @classmethod
    def _document(cls, project, data):
        result = {"project_id": project.project_id, "metadata": {key: deepcopy(value) for key, value in data.items() if key not in cls.VIEWS}}
        for view in cls.VIEWS:
            rows = []
            for row in data.get(view, []) or []:
                if not isinstance(row, dict):
                    continue
                record = deepcopy(row)
                for key, default in cls.DEFAULTS[view].items():
                    value = record.get(key, default)
                    record[key] = cls._count(value) if key == "occurrence_count" else cls._text(value)
                    if key == cls.CATEGORIES[view]:
                        record[key] = cls._category(value, default)
                rows.append(record)
            result[view] = rows
        return result

    def get(self):
        with self.cache_manager.file_lock:
            project = self._project()
            with project.atomic_scope():
                return self._document(project, self.cache_manager.get_analysis_data())

    @classmethod
    def _sync_stats(cls, data):
        stats = deepcopy(data.get("stats", {})) if isinstance(data.get("stats"), dict) else {}
        for view, name in (("characters", "character_count"), ("terms", "term_count"), ("non_translate", "non_translate_count")):
            stats[name] = len(data.get(view, []))
        stats["total_hits"] = stats["character_count"] + stats["term_count"] + stats["non_translate_count"]
        data["stats"] = stats

    def _save(self, project, data):
        self._sync_stats(data)
        with self.cache_manager.file_lock:
            original = deepcopy(self.cache_manager.get_analysis_data())
            self.cache_manager.set_analysis_data(data)
        try:
            # The manager owns a non-reentrant lock; it must acquire it itself.
            self.cache_manager.save_to_file()
        except Exception as error:
            with self.cache_manager.file_lock:
                self.cache_manager.set_analysis_data(original)
            raise ApplicationError("analysis_save_failed", 500) from error
        EventManager.get_singleton().emit(Base.EVENT.ANALYSIS_DATA_CHANGED, {"project_id": project.project_id})
        return self._document(project, data)

    def put(self, document):
        with exclusive_operation():
            with self.cache_manager.file_lock:
                project = self._project(document["project_id"])
                existing = deepcopy(self.cache_manager.get_analysis_data())
            data = {**existing, **deepcopy(document.get("metadata", {}))}
            for view in self.VIEWS:
                identity = self._identity_field(view)
                previous = {self._text(row.get(identity)) or self._text(row.get("_row_key")): row for row in existing.get(view, []) if isinstance(row, dict)}
                rows = []
                for row in document.get(view, []):
                    key = self._text(row.get(identity)) or self._text(row.get("_row_key"))
                    # Unknown metadata is retained for an existing row even if
                    # a client only returns editable fields.
                    rows.append({**deepcopy(previous.get(key, {})), **deepcopy(row)})
                data[view] = rows
            return self._save(project, data)

    @classmethod
    def _normalize_file_rows(cls, view, rows):
        normalized, skipped = {}, 0
        identity_field = cls._identity_field(view)
        for row in rows:
            if not isinstance(row, dict):
                skipped += 1
                continue
            record = {}
            for key, default in cls.DEFAULTS[view].items():
                value = row.get(key, default)
                if key == "occurrence_count":
                    record[key] = cls._count(value)
                elif value is None or isinstance(value, (str, int, float, bool)):
                    record[key] = cls._text(value)
                    if key == cls.CATEGORIES[view] and not record[key]:
                        record[key] = default
                else:
                    break
            else:
                identity = record.get(identity_field)
                if identity:
                    normalized[identity] = record
                    continue
            skipped += 1
        return list(normalized.values()), skipped

    def import_rows(self, view, content_base64, project_id):
        self._validate_view(view)
        try:
            data = json.loads(base64.b64decode(content_base64, validate=True).decode("utf-8-sig"))
        except (ValueError, UnicodeError, binascii.Error) as error:
            raise ApplicationError("analysis_import_invalid", 400) from error
        if not isinstance(data, list):
            raise ApplicationError("analysis_import_invalid", 400)
        incoming, skipped = self._normalize_file_rows(view, data)
        with exclusive_operation():
            with self.cache_manager.file_lock:
                project = self._project(project_id)
                saved = deepcopy(self.cache_manager.get_analysis_data())
            identity = self._identity_field(view)
            keyed = {row[identity]: row for row in incoming}
            merged, replaced = [], set()
            for row in saved.get(view, []) or []:
                key = self._text(row.get(identity))
                if key in keyed:
                    if key not in replaced:
                        merged.append(keyed[key])
                        replaced.add(key)
                else:
                    merged.append(row)
            merged.extend(row for key, row in keyed.items() if key not in replaced)
            saved[view] = merged
            document = self._save(project, saved) if incoming else self._document(project, saved)
            return {"document": document, "added": len(keyed) - len(replaced), "replaced": len(replaced), "skipped": skipped}

    def export_rows(self, view, category=None, q="", project_id=None):
        self._validate_view(view)
        with self.cache_manager.file_lock:
            project = self._project(project_id)
            document = self._document(project, self.cache_manager.get_analysis_data())
        rows = document[view]
        if category is not None:
            rows = [row for row in rows if row.get(self.CATEGORIES[view]) == category]
        if q:
            query = q.casefold()
            rows = [row for row in rows if any(query in str(row.get(key, "")).casefold() for key in self.DEFAULTS[view])]
        rows, _ = self._normalize_file_rows(view, rows)
        return {"filename": f"analysis-{view}.json", "media_type": "application/json", "content_base64": base64.b64encode(json.dumps(rows, ensure_ascii=False, indent=4).encode("utf-8")).decode("ascii")}

    @classmethod
    def _public_row(cls, view, row):
        identity = cls._text(row.get(cls._identity_field(view)))
        if not identity:
            return None
        category = cls._category(row.get(cls.CATEGORIES[view]), cls.DEFAULTS[view][cls.CATEGORIES[view]])
        info = f"{'性别' if view == 'characters' else '分类'}: {category}；备注: {cls._text(row.get('note'))}"
        if view == "non_translate":
            return {"markers": identity, "info": info, "regex": False}
        return {"src": identity, "dst": cls._text(row.get("recommended_translation")), "info": info, "regex": False}

    def publish(self, view, project_id, table_id=None, identities=None):
        self._validate_view(view)
        with exclusive_operation():
            with self.cache_manager.file_lock:
                project = self._project(project_id)
                document = self._document(project, self.cache_manager.get_analysis_data())
            selected = None if identities is None else set(identities)
            rows = [self._public_row(view, row) for row in document[view] if selected is None or self._text(row.get(self._identity_field(view))) in selected]
            rows = [row for row in rows if row is not None]
            service = TableService()
            name = "exclusion" if view == "non_translate" else "glossary"
            before = sum(len(table["rows"]) for table in service.get(name)["tables"])
            collection = service.append_rows(name, rows, table_id)
            after = sum(len(table["rows"]) for table in collection["tables"])
            return {"collection": collection, "added": after - before}

    def move(self, view, project_id, target, category, identities):
        if view not in ("characters", "terms") or target not in ("characters", "terms") or target == view:
            raise ApplicationError("analysis_move_invalid", 400)
        with exclusive_operation():
            with self.cache_manager.file_lock:
                project = self._project(project_id)
                data = deepcopy(self.cache_manager.get_analysis_data())
            source_rows = data.get(view, []) or []
            target_rows = list(data.get(target, []) or [])
            moved = set()
            for identity in identities:
                identity = self._text(identity)
                if not identity or identity in moved:
                    continue
                row = next((row for row in source_rows if self._text(row.get("source")) == identity), None)
                if row is None:
                    continue
                source_category = self._category(row.get(self.CATEGORIES[view]), self.DEFAULTS[view][self.CATEGORIES[view]])
                note = "；".join(part for part in (self._text(row.get("note")), f"原分类: {source_category}") if part)
                converted = {
                    "source": identity, "recommended_translation": self._text(row.get("recommended_translation")),
                    "occurrence_count": self._count(row.get("occurrence_count")), "note": note,
                    self.CATEGORIES[target]: self._category(category, self.DEFAULTS[target][self.CATEGORIES[target]]),
                }
                target_index = next((index for index, candidate in enumerate(target_rows) if self._text(candidate.get("source")) == identity), None)
                if target_index is None:
                    target_rows.append(converted)
                else:
                    # The desktop cross-table move explicitly overwrites the
                    # existing target and then removes the source row.
                    target_rows[target_index] = converted
                moved.add(identity)
            if moved:
                data[target] = target_rows
                data[view] = [row for row in source_rows if self._text(row.get("source")) not in moved]
                return self._save(project, data)
            return self._document(project, data)
