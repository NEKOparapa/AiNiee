"""MCP tool catalog. Tools depend only on a backend (AiNieeBackend) + ConfigStore.

This module is intentionally httpx-free: the backend is injected. `register_all`
returns the registered (wrapped) callables keyed by name so they can be unit-tested
without going through the MCP protocol.
"""
from __future__ import annotations

import copy
import functools
from typing import Any

from .backend.base import AiNieeBackend
from .config_store import ConfigStore
from .enums import PROJECT_TYPES
from .errors import AiNieeError, ValidationError

_SECRET_KEYS = ("api_key", "access_key", "secret_key")


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AiNieeError as e:
            return {"status": "error", "message": e.user_message}
    return wrapper


def _redact(cfg: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    for p in (cfg.get("platforms") or {}).values():
        for k in _SECRET_KEYS:
            if p.get(k):
                p[k] = "***"
    return cfg


def _pending(name: str) -> dict:
    return {"status": "pending", "message": f"任务尚未完成，请稍后再次调用 {name}"}


def register_all(mcp, backend: AiNieeBackend, store: ConfigStore) -> dict[str, Any]:
    registered: dict[str, Any] = {}

    def tool(fn):
        wrapped = _safe(fn)
        mcp.tool()(wrapped)
        registered[fn.__name__] = wrapped
        return wrapped

    # ===================== Group 1: translation control =====================
    @tool
    def ainiee_status() -> dict:
        """Get AiNiee's current status: app state (IDLE/TASKING/STOPPING/STOPPED),
        whether a project is loaded, translation progress, and async-task flags.
        Call this first to confirm AiNiee is reachable."""
        return backend.get_status().to_dict()

    @tool
    def ainiee_translate(continue_: bool = False, input_folder: str = "",
                         output_folder: str = "") -> dict:
        """Start a TRANSLATION task on the loaded/configured project. continue_=True
        resumes an interrupted run. Optional folders override config first.
        Fire-and-forget: poll ainiee_status() until progress.is_complete."""
        return backend.start_task("translate", continue_,
                                  input_folder or None, output_folder or None)

    @tool
    def ainiee_polish(continue_: bool = False) -> dict:
        """Start a POLISH task over already-translated text. Poll ainiee_status()."""
        return backend.start_task("polish", continue_)

    @tool
    def ainiee_stop() -> dict:
        """Stop the current task."""
        return backend.stop_task()

    @tool
    def ainiee_load_project(translation_project: str = "", input_folder: str = "",
                            exclude_rule: str = "") -> dict:
        """Load a project into AiNiee from disk. translation_project is a project type
        (AutoType, Txt, Epub, Mtool, Renpy, Po, Srt, Xlsx, ...); empty keeps config.
        Required before translating a new project (unless continuing)."""
        if translation_project and translation_project not in PROJECT_TYPES:
            raise ValidationError(f"unknown translation_project {translation_project!r}",
                                  allowed=PROJECT_TYPES)
        return backend.load_project(translation_project or None,
                                    input_folder or None, exclude_rule or None)

    # ===================== Group 4: extended tasks =====================
    @tool
    def ainiee_analysis_start() -> dict:
        """Start full-text analysis (extracts characters / terms / non-translate items).
        Requires a loaded project and idle app. Poll ainiee_analysis_result()."""
        return backend.start_analysis()

    @tool
    def ainiee_analysis_result() -> dict:
        """Poll the latest analysis result (characters/terms/non_translate/stats).
        Returns status 'pending' until done."""
        r = backend.get_analysis_result()
        return r.to_dict() if r else _pending("ainiee_analysis_result")

    @tool
    def ainiee_get_analysis(kind: str = "") -> dict:
        """Read the LOADED project's persisted analysis tables (previously extracted
        characters / terms / non_translate + stats) straight from its cache — no re-run
        needed, unlike ainiee_analysis_start. Requires a project loaded in AiNiee.
        Optional `kind` in {characters,terms,non_translate,stats} returns just that slice
        (handy since the tables can be large)."""
        r = backend.get_analysis_data()
        if r is None:
            return {"status": "empty", "has_analysis": False,
                    "message": "当前已加载项目没有已保存的分析结果；可先运行 ainiee_analysis_start 生成"}
        d = r.to_dict()
        if kind:
            if kind not in ("characters", "terms", "non_translate", "stats"):
                return {"status": "error",
                        "message": "kind 必须为 characters/terms/non_translate/stats 之一"}
            return {"status": "success", "has_analysis": True, "kind": kind, "value": d.get(kind)}
        return {"status": "success", "has_analysis": True, **d}

    @tool
    def ainiee_glossary_translate(terms: list[dict] | None = None) -> dict:
        """Auto-translate the glossary's empty entries. If `terms` ([{src,dst?,info?}])
        is given it replaces config.prompt_dictionary_data first. Poll
        ainiee_glossary_result(), then persist with ainiee_set_glossary()."""
        if terms is not None:
            store.set_resource_list("prompt_dictionary_data", terms,
                                    "prompt_dictionary_switch", True)
        return backend.start_glossary()

    @tool
    def ainiee_glossary_result() -> dict:
        """Poll glossary-translation result (updated_data/success_count/total_count).
        Returns status 'pending' until done."""
        r = backend.get_glossary_result()
        return r.to_dict() if r else _pending("ainiee_glossary_result")

    @tool
    def ainiee_api_test(tag: str) -> dict:
        """Test an API platform by its config tag (see ainiee_list_platforms). Loads the
        platform's url/key/model from config and pings it. Poll ainiee_api_test_result()."""
        return backend.test_api(tag)

    @tool
    def ainiee_api_test_result() -> dict:
        """Poll API-test result ({success:[keys], failure:[keys]}). 'pending' until done."""
        r = backend.get_apitest_result()
        return r.to_dict() if r else _pending("ainiee_api_test_result")

    @tool
    def ainiee_export(export_path: str) -> dict:
        """Export current translation results to a folder. Fire-and-forget (no completion
        event); confirm via the filesystem or ainiee_status."""
        return backend.export(export_path)

    @tool
    def ainiee_save_cache() -> dict:
        """Force AiNiee to flush its in-memory project cache to disk."""
        return backend.save_cache()

    # ===================== Group 2: config & resources =====================
    @tool
    def ainiee_get_config(section: str = "") -> dict:
        """Read config.json (whole, or one top-level key via `section`). API keys are
        redacted. Safe while AiNiee runs."""
        cfg = _redact(store.load())
        if section:
            return {"status": "success", "section": section, "value": cfg.get(section)}
        return {"status": "success", "config": cfg}

    @tool
    def ainiee_list_platforms() -> dict:
        """List API platforms (tag -> name/api_format/model/has_key, keys redacted) and
        the api_settings role bindings (active/translate/polish/extract/proofread)."""
        return {"status": "success", "platforms": store.list_platforms_redacted(),
                "api_settings": store.get_api_settings()}

    @tool
    def ainiee_set_platform(tag: str, name: str = "", api_url: str = "", api_key: str = "",
                            model: str = "", api_format: str = "", rpm_limit: int = 0) -> dict:
        """Create/update an API platform by tag. Only non-empty fields are written.
        api_key may be comma-separated for multi-key rotation."""
        fields = {"name": name or None, "api_url": api_url or None, "api_key": api_key or None,
                  "model": model or None, "api_format": api_format or None,
                  "rpm_limit": rpm_limit or None}
        p = store.upsert_platform(tag, fields)
        return {"status": "success", "tag": tag, "name": p.get("name"), "model": p.get("model")}

    @tool
    def ainiee_set_active_api(role: str, tag: str) -> dict:
        """Bind a platform tag to a role: active|translate|polish|extract|proofread."""
        return {"status": "success", "api_settings": store.set_api_role(role, tag)}

    @tool
    def ainiee_set_languages(source: str = "", target: str = "") -> dict:
        """Set source/target language (english, japanese, chinese_simplified, ...)."""
        return {"status": "success",
                **store.set_languages(source or None, target or None)}

    @tool
    def ainiee_set_io_paths(input_path: str = "", output_path: str = "",
                            exclude_rule: str = "") -> dict:
        """Set input/output folders and the input exclude rule."""
        return {"status": "success",
                **store.set_io_paths(input_path or None, output_path or None,
                                     exclude_rule if exclude_rule else None)}

    @tool
    def ainiee_set_project_type(translation_project: str) -> dict:
        """Set the project type (AutoType, Mtool, Renpy, Epub, Srt, Xlsx, ...)."""
        store.set_project_type(translation_project)
        return {"status": "success", "translation_project": translation_project}

    @tool
    def ainiee_set_glossary(data: list[dict], switch: bool = True) -> dict:
        """Replace the AI glossary (prompt_dictionary_data: [{src,dst,info}]) and toggle it."""
        store.set_resource_list("prompt_dictionary_data", data,
                                "prompt_dictionary_switch", switch)
        return {"status": "success", "count": len(data), "enabled": switch}

    @tool
    def ainiee_set_exclusions(data: list[dict], switch: bool = True) -> dict:
        """Replace the do-not-translate list (exclusion_list_data: [{markers,info,regex}])."""
        store.set_resource_list("exclusion_list_data", data, "exclusion_list_switch", switch)
        return {"status": "success", "count": len(data), "enabled": switch}

    @tool
    def ainiee_set_pre_post_replacements(pre: list[dict] | None = None,
                                         post: list[dict] | None = None) -> dict:
        """Set pre/post-translation text replacement rules ([{src,dst,info}])."""
        updated = []
        if pre is not None:
            store.set_resource_list("pre_translation_data", pre, "pre_translation_switch", True)
            updated.append("pre_translation_data")
        if post is not None:
            store.set_resource_list("post_translation_data", post, "post_translation_switch", True)
            updated.append("post_translation_data")
        return {"status": "success", "updated": updated}

    @tool
    def ainiee_set_characters(data: list[dict], switch: bool = True) -> dict:
        """Replace the character sheet (characterization_data: [{original_name,
        translated_name,gender,age,personality,speech_style,additional_info}])."""
        store.set_resource_list("characterization_data", data, "characterization_switch", switch)
        return {"status": "success", "count": len(data), "enabled": switch}

    @tool
    def ainiee_set_world_style(world_building: str = "", writing_style: str = "") -> dict:
        """Set world-building and/or writing-style prompt text (enables the matching switch)."""
        patch: dict = {}
        if world_building:
            patch.update({"world_building_content": world_building, "world_building_switch": True})
        if writing_style:
            patch.update({"writing_style_content": writing_style, "writing_style_switch": True})
        if patch:
            store.merge_save(patch)
        return {"status": "success", "updated": list(patch.keys())}

    # ============ Group 3: universal translation correction (live cache) ============
    @tool
    def ainiee_cache_search(query: str = "", scope: str = "all", regex: bool = False,
                            flagged_only: bool = False, limit: int = 200) -> dict:
        """Search the loaded project's cache (works while AiNiee runs). scope:
        all|source_text|translated_text. Returns matching items with storage_path +
        text_index (use those with ainiee_cache_update)."""
        items = backend.cache_search(query, scope, regex, flagged_only, limit)
        return {"status": "success", "count": len(items), "items": [i.to_dict() for i in items]}

    @tool
    def ainiee_cache_stats() -> dict:
        """Counts of cache items by translation status (untranslated/translated/polished/excluded)."""
        return backend.cache_stats()

    @tool
    def ainiee_cache_update(edits: list[dict]) -> dict:
        """Apply precise per-item edits to the live cache and save. Each edit:
        {storage_path, text_index, field:"translated_text"|"source_text", new_text}.
        Requires AiNiee running, project loaded, not actively translating."""
        return backend.cache_update(edits)

    @tool
    def ainiee_cache_replace(rules: list[dict], dry_run: bool = True) -> dict:
        """Universal find/replace over the live cache (any text). Each rule:
        {find, replace, regex?, source_requires?, source_excludes?, skip_if_followed_by?}.
        source_requires (str or list): only replace when the item's SOURCE matches (any of) these.
        source_excludes (str or list): skip the item when its SOURCE matches (any of) these.
        skip_if_followed_by: skip an occurrence when followed by one of these strings.
        dry_run=True (default) returns a preview without writing. Run dry_run first,
        review, then dry_run=False to apply."""
        return backend.cache_replace(rules, dry_run)

    return registered
