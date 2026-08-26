"""Atomic read-merge-write of AiNiee's config.json (backend-agnostic).

Mirrors ConfigMixin.load_config/save_config semantics (top-level shallow merge),
but never imports AiNiee. Writes atomically (temp + os.replace) and re-reads before
each merge so it composes with the GUI's own edits. Safe to use while AiNiee runs:
AiNiee re-reads config at task start and keeps no cached copy.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import paths
from .enums import API_ROLES, LANGUAGES, PROJECT_TYPES
from .errors import ValidationError


class ConfigStore:
    def __init__(self, config_path: str | os.PathLike | None = None):
        self._path = Path(config_path) if config_path is not None else paths.config_path()

    @property
    def path(self) -> Path:
        return self._path

    # --- raw IO ---
    def load(self) -> dict:
        if not self._path.is_file():
            return {}
        with open(self._path, "r", encoding="utf-8") as r:
            return json.load(r)

    def _atomic_write(self, cfg: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as w:
                json.dump(cfg, w, ensure_ascii=False, indent=4)
            os.replace(tmp, self._path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def merge_save(self, patch: dict) -> dict:
        """Re-read, shallow-merge top-level keys (like save_config), atomic write."""
        cfg = self.load()
        cfg.update(patch)
        self._atomic_write(cfg)
        return cfg

    # --- reads ---
    def get_platforms(self) -> dict:
        return self.load().get("platforms", {}) or {}

    def get_api_settings(self) -> dict:
        return self.load().get("api_settings", {}) or {}

    def list_platforms_redacted(self) -> dict:
        out = {}
        for tag, p in self.get_platforms().items():
            out[tag] = {
                "name": p.get("name"),
                "api_format": p.get("api_format"),
                "model": p.get("model"),
                "has_key": bool(p.get("api_key")),
            }
        return out

    # --- writes (validated) ---
    def set_api_role(self, role: str, tag: str) -> dict:
        if role not in API_ROLES:
            raise ValidationError(f"unknown api role {role!r}", allowed=API_ROLES)
        cfg = self.load()
        platforms = cfg.get("platforms", {}) or {}
        if tag not in platforms:
            raise ValidationError(f"unknown platform tag {tag!r}", allowed=platforms.keys())
        api = dict(cfg.get("api_settings", {}) or {})
        api[role] = tag
        self.merge_save({"api_settings": api})
        return api

    def upsert_platform(self, tag: str, fields: dict) -> dict:
        cfg = self.load()
        platforms = dict(cfg.get("platforms", {}) or {})
        p = dict(platforms.get(tag, {}))
        p.update({k: v for k, v in fields.items() if v is not None})
        p.setdefault("tag", tag)
        platforms[tag] = p
        self.merge_save({"platforms": platforms})
        return p

    def set_languages(self, source: str | None = None, target: str | None = None) -> dict:
        patch: dict = {}
        if source is not None:
            if source not in LANGUAGES:
                raise ValidationError(f"unknown source_language {source!r}", allowed=LANGUAGES)
            patch["source_language"] = source
        if target is not None:
            if target not in LANGUAGES:
                raise ValidationError(f"unknown target_language {target!r}", allowed=LANGUAGES)
            patch["target_language"] = target
        if patch:
            self.merge_save(patch)
        return patch

    def set_project_type(self, translation_project: str) -> dict:
        if translation_project not in PROJECT_TYPES:
            raise ValidationError(
                f"unknown translation_project {translation_project!r}", allowed=PROJECT_TYPES)
        return self.merge_save({"translation_project": translation_project})

    def set_io_paths(self, input_path: str | None = None, output_path: str | None = None,
                     exclude_rule: str | None = None) -> dict:
        patch: dict = {}
        if input_path is not None:
            p = os.path.abspath(os.path.expanduser(input_path))
            if not os.path.isdir(p):
                raise ValidationError(f"input_path does not exist or is not a directory: {p}")
            patch["label_input_path"] = p
        if output_path is not None:
            patch["label_output_path"] = os.path.abspath(os.path.expanduser(output_path))
        if exclude_rule is not None:
            patch["label_input_exclude_rule"] = exclude_rule
        if patch:
            self.merge_save(patch)
        return patch

    def set_resource_list(self, key: str, data: list, switch_key: str | None = None,
                          switch: bool | None = None) -> dict:
        patch: dict = {key: data}
        if switch_key is not None and switch is not None:
            patch[switch_key] = switch
        self.merge_save(patch)
        return patch
