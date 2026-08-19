"""The AiNieeBackend interface — the single seam between MCP tools and AiNiee.

Tools depend ONLY on this. Phase A: HttpBackend. Phase B: InProcessBackend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AnalysisResult, ApiTestResult, CacheItemView, GlossaryResult, TaskStatus


class AiNieeBackend(ABC):
    # --- liveness ---
    @abstractmethod
    def ping(self) -> bool:
        """True if AiNiee is reachable/usable."""

    # --- group 1: translation control ---
    @abstractmethod
    def get_status(self) -> TaskStatus: ...

    @abstractmethod
    def start_task(self, mode: str, continue_: bool = False,
                   input_folder: str | None = None,
                   output_folder: str | None = None) -> dict:
        """mode in {'translate','polish'}. Loads project if needed (non-continue)."""

    @abstractmethod
    def stop_task(self) -> dict: ...

    @abstractmethod
    def load_project(self, translation_project: str | None = None,
                     input_folder: str | None = None,
                     exclude_rule: str | None = None) -> dict: ...

    # --- group 4: extended tasks (start -> poll result) ---
    @abstractmethod
    def start_analysis(self) -> dict: ...

    @abstractmethod
    def get_analysis_result(self) -> AnalysisResult | None:
        """None while still running / no result yet."""

    @abstractmethod
    def get_analysis_data(self) -> AnalysisResult | None:
        """The loaded project's persisted analysis tables (read from its cache, no
        re-run). None if no project has saved analysis data."""

    @abstractmethod
    def start_glossary(self) -> dict:
        """Translate config.prompt_dictionary_data's empty entries."""

    @abstractmethod
    def get_glossary_result(self) -> GlossaryResult | None: ...

    @abstractmethod
    def test_api(self, tag: str) -> dict: ...

    @abstractmethod
    def get_apitest_result(self) -> ApiTestResult | None: ...

    @abstractmethod
    def export(self, export_path: str) -> dict: ...

    @abstractmethod
    def save_cache(self) -> dict: ...

    # --- group 3: universal translation correction (live in-memory cache) ---
    @abstractmethod
    def cache_search(self, query: str, scope: str = "all", regex: bool = False,
                     flagged_only: bool = False, limit: int = 200) -> list[CacheItemView]: ...

    @abstractmethod
    def cache_stats(self) -> dict: ...

    @abstractmethod
    def cache_update(self, edits: list[dict]) -> dict:
        """edits: [{storage_path, text_index, field, new_text}]."""

    @abstractmethod
    def cache_replace(self, rules: list[dict], dry_run: bool = True) -> dict:
        """rules: [{find, replace, regex?, scope?, source_requires?, skip_if_followed_by?}]."""
