"""Rule-table configuration normalization, migration and runtime snapshots."""

from copy import deepcopy
from uuid import NAMESPACE_URL, uuid4, uuid5

from ModuleFolders.Domain.RegexSwitchHelper import RegexSwitchHelper


class TableConfigHelper:
    KINDS = ("prompt_dictionary", "exclusion_list", "pre_translation", "post_translation")
    MATCH_OPTIONS = ("case_sensitive", "whole_word", "split_match")
    _NORMALIZERS = {
        "prompt_dictionary": RegexSwitchHelper.normalize_glossary_rows,
        "exclusion_list": RegexSwitchHelper.normalize_exclusion_rows,
        "pre_translation": RegexSwitchHelper.normalize_replacement_rows,
        "post_translation": RegexSwitchHelper.normalize_replacement_rows,
    }

    @staticmethod
    def _get(config, key, default=None):
        return config.get(key, default) if isinstance(config, dict) else getattr(config, key, default)

    @staticmethod
    def _has(config, key):
        return key in config if isinstance(config, dict) else hasattr(config, key)

    @classmethod
    def normalize_rows(cls, kind: str, rows) -> list[dict]:
        return cls._NORMALIZERS[kind](deepcopy(rows))

    @classmethod
    def normalize_match_options(cls, options=None) -> dict[str, bool]:
        options = options if isinstance(options, dict) else {}
        return {key: RegexSwitchHelper._normalize_bool(options.get(key, False)) for key in cls.MATCH_OPTIONS}

    @classmethod
    def new_table(cls, kind: str, name: str = "新建表", rows=None,
                  enabled: bool = True, match_options=None) -> dict:
        table = {
            "id": str(uuid4()),
            "name": str(name or "").strip() or "新建表",
            "enabled": bool(enabled),
            "rows": cls.normalize_rows(kind, rows),
        }
        if kind == "prompt_dictionary":
            table["match_options"] = cls.normalize_match_options(match_options)
        return table

    @classmethod
    def _normalize_tables(cls, kind: str, tables, enabled_only: bool = False) -> list[dict]:
        result = []
        seen_ids = set()
        for table in tables if isinstance(tables, list) else []:
            if not isinstance(table, dict):
                continue
            table_id = str(table.get("id") or "").strip()
            if not table_id or table_id in seen_ids:
                table_id = str(uuid4())
            seen_ids.add(table_id)
            enabled = RegexSwitchHelper._normalize_bool(table.get("enabled", True))
            if enabled_only and not enabled:
                continue
            normalized = {
                "id": table_id,
                "name": str(table.get("name") or "").strip() or "未命名表",
                "enabled": enabled,
                "rows": cls.normalize_rows(kind, table.get("rows", [])),
            }
            if kind == "prompt_dictionary":
                normalized["match_options"] = cls.normalize_match_options(table.get("match_options"))
            result.append(normalized)
        return result

    @classmethod
    def _legacy_table(cls, config, kind: str, default_enabled: bool) -> dict:
        options = None
        if kind == "prompt_dictionary":
            options = {
                "case_sensitive": cls._get(config, "prompt_dictionary_match_case_sensitive", False),
                "whole_word": cls._get(config, "prompt_dictionary_match_whole_word", False),
                "split_match": cls._get(config, "prompt_dictionary_match_split", False),
            }
        table = cls.new_table(
            kind, "默认表", cls._get(config, f"{kind}_data", []),
            enabled=cls._get(config, f"{kind}_switch", default_enabled),
            match_options=options,
        )
        # Stable even for callers using old in-memory config objects without persistence.
        table["id"] = str(uuid5(NAMESPACE_URL, f"AiNiee/tables/{kind}/legacy"))
        return table

    @classmethod
    def get_tables(cls, config, kind: str, enabled_only: bool = False) -> list[dict]:
        key = f"{kind}_tables"
        if cls._has(config, key):
            tables = cls._normalize_tables(kind, cls._get(config, key), enabled_only=enabled_only)
        else:
            if enabled_only and not bool(cls._get(config, f"{kind}_switch", True)):
                return []
            tables = [cls._legacy_table(config, kind, default_enabled=True)]
        return [table for table in tables if table["enabled"]] if enabled_only else tables

    @classmethod
    def get_enabled_rows(cls, config, kind: str) -> list[dict]:
        return [row for table in cls.get_tables(config, kind, enabled_only=True) for row in table["rows"]]

    @classmethod
    def has_enabled_tables(cls, config, kind: str) -> bool:
        # Prompt gating only needs switches; avoid copying every row in large tables.
        key = f"{kind}_tables"
        if cls._has(config, key):
            tables = cls._get(config, key)
            if not isinstance(tables, list):
                return False
            return any(
                isinstance(table, dict) and RegexSwitchHelper._normalize_bool(table.get("enabled", True))
                for table in tables
            )
        return bool(cls._get(config, f"{kind}_switch", True))

    @classmethod
    def normalize_config(cls, config: dict) -> bool:
        """Migrate only absent collections; an explicitly empty collection stays empty."""
        if not isinstance(config, dict):
            return False
        changed = False
        for kind in cls.KINDS:
            key = f"{kind}_tables"
            if key in config:
                tables = cls._normalize_tables(kind, config[key])
            else:
                tables = [cls._legacy_table(config, kind, default_enabled=False)]
            if config.get(key) != tables:
                config[key] = tables
                changed = True
            active_key = f"{kind}_active_table_id"
            table_ids = {table["id"] for table in tables}
            active_id = config.get(active_key)
            if active_id not in table_ids:
                active_id = tables[0]["id"] if tables else None
            if active_key not in config or config[active_key] != active_id:
                config[active_key] = active_id
                changed = True
        return changed

    @classmethod
    def apply_runtime_snapshot(cls, config) -> None:
        """Freeze table data and derive old task attributes from enabled tables only."""
        for kind in cls.KINDS:
            tables = cls.get_tables(config, kind)
            values = {
                f"{kind}_tables": tables,
                f"{kind}_data": [deepcopy(row) for table in tables if table["enabled"] for row in table["rows"]],
                f"{kind}_switch": any(table["enabled"] for table in tables),
            }
            if isinstance(config, dict):
                config.update(values)
            else:
                for key, value in values.items():
                    setattr(config, key, value)
