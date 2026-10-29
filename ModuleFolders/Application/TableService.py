"""Public tables extracted from the Qt editors, without UI dependencies."""

import base64
from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile

import openpyxl

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.JsonValidation import reject_json_constant, validate_finite_json
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Application.PublicTableFileHelper import PublicTableFileHelper
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.TableConfigHelper import TableConfigHelper
from ModuleFolders.Domain.PromptBuilder.CharacterHelper import CharacterHelper


class TableService(ConfigMixin):
    KINDS = {"glossary": "prompt_dictionary", "exclusion": "exclusion_list", "replace_a": "pre_translation", "replace_b": "post_translation"}
    KEYS = {
        "glossary": ("src", "dst", "info", "regex"),
        "exclusion": ("markers", "info", "regex"),
        "replace_a": ("src", "dst", "regex"),
        "replace_b": ("src", "dst", "regex"),
        "characters": ("original_name", "translated_name", "gender", "age", "personality", "speech_style", "additional_info"),
    }

    def _validate_name(self, name):
        if name not in self.KEYS:
            raise ApplicationError("table_kind_invalid", 404)

    def _collection(self, name, config):
        self._validate_name(name)
        if name == "characters":
            return {"tables": [{"id": "characters", "name": "characters", "enabled": bool(config.get("characterization_switch", False)), "rows": CharacterHelper.normalize_rows(config.get("characterization_data", []))}], "active_table_id": "characters"}
        kind = self.KINDS[name]
        tables = TableConfigHelper.get_tables(config, kind)
        return {"tables": tables, "active_table_id": config.get(f"{kind}_active_table_id", tables[0]["id"] if tables else None)}

    def get(self, name):
        return self._collection(name, self.load_config())

    def _normalize_rows(self, name, rows):
        try:
            validate_finite_json(rows)
        except ValueError as error:
            raise ApplicationError("table_invalid") from error
        rows = CharacterHelper.normalize_rows(rows) if name == "characters" else TableConfigHelper.normalize_rows(self.KINDS[name], rows)
        return [row for row in rows if row.get(self.KEYS[name][0])]

    def _save_collection(self, name, document, config):
        self._validate_name(name)
        tables = deepcopy(document.get("tables", []))
        ids = [table.get("id") for table in tables]
        if len(ids) != len(set(ids)) or any(not table.get("id") or not str(table.get("name", "")).strip() for table in tables):
            raise ApplicationError("table_invalid")
        active = document.get("active_table_id")
        if active is not None and active not in ids:
            raise ApplicationError("table_not_found", 404)
        if name == "characters":
            if len(tables) != 1 or ids != ["characters"]:
                raise ApplicationError("table_invalid")
            config["characterization_switch"] = tables[0].get("enabled", False)
            config["characterization_data"] = self._normalize_rows(name, tables[0].get("rows", []))
        else:
            kind = self.KINDS[name]
            existing = {table["id"]: table for table in config.get(f"{kind}_tables", [])}
            saved = []
            for table in tables:
                table = {**deepcopy(existing.get(table["id"], {})), **table}
                table["name"] = table["name"].strip()
                table["rows"] = self._normalize_rows(name, table.get("rows", []))
                saved.append(table)
            config[f"{kind}_tables"] = saved
            config[f"{kind}_active_table_id"] = active or (ids[0] if ids else None)

    def put(self, name, document):
        try:
            validate_finite_json(document)
        except ValueError as error:
            raise ApplicationError("table_invalid") from error
        with exclusive_operation():
            config = self.update_config(lambda config: self._save_collection(name, document, config))
        Base().emit(Base.EVENT.TABLES_CHANGED, {"name": name})
        return self._collection(name, config)

    def _legacy_rows(self, path, name):
        keys = self.KEYS[name]
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_json_constant)
            validate_finite_json(payload)
            if isinstance(payload, dict):
                payload = [{keys[0]: str(key), keys[1]: str(value) if value is not None else ""} for key, value in payload.items()]
            if not isinstance(payload, list):
                raise ValueError("invalid JSON rows")
            rows = []
            for row in payload:
                if isinstance(row, dict):
                    row = deepcopy(row)
                    if "src" in keys and not row.get("src") and row.get("srt"):
                        row["src"] = row["srt"]
                    rows.append(row)
            return self._normalize_rows(name, rows)
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=False)
        try:
            return self._normalize_rows(name, PublicTableFileHelper._read_sheet_rows(workbook.active, keys))
        finally:
            workbook.close()

    def _decode_file(self, name, request):
        self._validate_name(name)
        suffix = Path(request["filename"]).suffix.lower()
        if suffix not in (".json", ".xlsx"):
            raise ApplicationError("table_import_invalid")
        try:
            raw = base64.b64decode(request["content_base64"], validate=True)
            if len(raw) > 20 * 1024 * 1024:
                raise ApplicationError("table_file_too_large", 413)
            with tempfile.TemporaryDirectory(prefix="ainiee-table-") as temporary:
                path = Path(temporary) / ("upload" + suffix)
                path.write_bytes(raw)
                tables = PublicTableFileHelper.load_bundle(path, self.KINDS[name], self.KEYS[name]) if name != "characters" else None
                if tables is None:
                    rows = self._legacy_rows(path, name)
                    if not rows:
                        raise ApplicationError("table_import_empty")
                    tables = [{"name": Path(request["filename"]).stem, "enabled": True, "rows": rows}]
                return [{**table, "id": f"import-{index}"} for index, table in enumerate(tables)]
        except ApplicationError:
            raise
        except Exception as error:
            # Spreadsheet parsers expose several archive/XML exception classes;
            # report one stable UI error without echoing uploaded contents.
            raise ApplicationError("table_import_invalid") from error

    def import_file(self, name, request):
        tables = self._decode_file(name, request)
        selected_ids = request.get("selected_table_ids")
        if selected_ids is not None:
            if any(value not in {table["id"] for table in tables} for value in selected_ids):
                raise ApplicationError("table_import_invalid")
            tables = [table for table in tables if table["id"] in selected_ids]
        if not tables:
            raise ApplicationError("table_import_empty")
        if request.get("preview", False):
            return {"tables": tables, "active_table_id": tables[0]["id"]}
        if request.get("mode", "new") == "merge" or name == "characters":
            return self.append_rows(name, [row for table in tables for row in table["rows"]], request.get("target_table_id"))
        def update(config):
            kind = self.KINDS[name]
            existing = config.setdefault(f"{kind}_tables", [])
            names = {table["name"] for table in existing}
            first_id = None
            for incoming in tables:
                original = incoming["name"]
                label, number = original, 2
                while label in names:
                    label = f"{original} ({number})"
                    number += 1
                names.add(label)
                table = TableConfigHelper.new_table(kind, label, incoming["rows"], enabled=incoming["enabled"], match_options=incoming.get("match_options"))
                existing.append(table)
                first_id = first_id or table["id"]
            config[f"{kind}_active_table_id"] = first_id
        with exclusive_operation():
            config = self.update_config(update)
        Base().emit(Base.EVENT.TABLES_CHANGED, {"name": name})
        return self._collection(name, config)

    def export_file(self, name, table_ids=None, format="json", bundle=False):
        collection = self.get(name)
        selected = set(table_ids or ([collection["active_table_id"]] if not bundle else [table["id"] for table in collection["tables"]]))
        tables = [table for table in collection["tables"] if table["id"] in selected]
        if not tables or len(tables) != len(selected):
            raise ApplicationError("table_not_found", 404)
        if format not in ("json", "xlsx") or (not bundle and len(tables) != 1):
            raise ApplicationError("table_export_invalid")
        label = name if bundle else tables[0]["name"]
        filename = (re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", label).strip(" .") or name) + "." + format
        try:
            with tempfile.TemporaryDirectory(prefix="ainiee-export-table-") as temporary:
                path = Path(temporary) / ("export." + format)
                if bundle and name != "characters":
                    PublicTableFileHelper.save_bundle(path, self.KINDS[name], tables, self.KEYS[name], self.KEYS[name])
                elif format == "json":
                    path.write_text(json.dumps(tables[0]["rows"], indent=4, ensure_ascii=False), encoding="utf-8")
                else:
                    workbook = openpyxl.Workbook()
                    try:
                        sheet = workbook.active
                        for column, key in enumerate(self.KEYS[name], 1):
                            PublicTableFileHelper._write_cell(sheet, 1, column, key)
                        for number, row in enumerate(tables[0]["rows"], 2):
                            for column, key in enumerate(self.KEYS[name], 1):
                                PublicTableFileHelper._write_cell(sheet, number, column, row.get(key, ""))
                        workbook.save(path)
                    finally:
                        workbook.close()
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        except (ValueError, TypeError, OSError) as error:
            raise ApplicationError("table_export_invalid") from error
        return {"filename": filename, "media_type": "application/json" if format == "json" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "content_base64": encoded}

    def append_rows(self, name, rows, table_id=None):
        """Merge analysis results using the old editor's keep-existing policy."""
        self._validate_name(name)
        incoming = self._normalize_rows(name, rows)
        key = self.KEYS[name][0]
        def update(config):
            if name == "characters":
                if table_id not in (None, "characters"):
                    raise ApplicationError("table_not_found", 404)
                target_rows = config.setdefault("characterization_data", [])
            else:
                kind = self.KINDS[name]
                tables = config.setdefault(f"{kind}_tables", [])
                target_id = table_id or config.get(f"{kind}_active_table_id")
                target = next((table for table in tables if table["id"] == target_id), None)
                if target is None:
                    if table_id is not None:
                        raise ApplicationError("table_not_found", 404)
                    if tables:
                        target = tables[0]
                    else:
                        target = TableConfigHelper.new_table(kind, "默认表")
                        tables.append(target)
                    config[f"{kind}_active_table_id"] = target["id"]
                target_rows = target["rows"]
            existing = {row.get(key) for row in target_rows}
            for row in incoming:
                if row[key] not in existing:
                    target_rows.append(deepcopy(row))
                    existing.add(row[key])
        with exclusive_operation():
            config = self.update_config(update)
        Base().emit(Base.EVENT.TABLES_CHANGED, {"name": name})
        return self._collection(name, config)
