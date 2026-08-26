"""HttpBackend — Phase A. The ONLY module that knows AiNiee is reached over HTTP.

Maps each AiNieeBackend method to the HTTP contract implemented by
ModuleFolders/Service/HttpService/HttpService.py. Error responses may carry a
machine-readable `code` ("busy" | "no_project" | ...) which we map to typed errors.
"""
from __future__ import annotations

import httpx

from .. import settings
from ..errors import AiNieeBusy, AiNieeError, AiNieeUnavailable, NoProjectLoaded, ValidationError
from .base import AiNieeBackend
from .models import AnalysisResult, ApiTestResult, CacheItemView, GlossaryResult, TaskStatus


def _clean(body: dict) -> dict:
    """Drop None values so optional params are omitted."""
    return {k: v for k, v in body.items() if v is not None}


class HttpBackend(AiNieeBackend):
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self._base_url = (base_url or settings.base_url()).rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout if timeout is not None else settings.http_timeout(),
        )

    # --- low level ---
    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        try:
            if method == "GET":
                resp = self._client.get(path)
            else:
                resp = self._client.post(path, json=(body or {}))
        except httpx.RequestError as e:
            raise AiNieeUnavailable(self._base_url) from e

        try:
            data = resp.json()
        except Exception:
            data = {"status": "error", "message": resp.text}
        if not isinstance(data, dict):
            data = {"data": data}

        if resp.status_code >= 400:
            code = data.get("code")
            msg = data.get("message", f"HTTP {resp.status_code}")
            if code == "busy":
                raise AiNieeBusy(msg)
            if code == "no_project":
                raise NoProjectLoaded()
            if resp.status_code == 400:
                raise ValidationError(msg)
            raise AiNieeError(msg)
        return data

    @staticmethod
    def _poll_payload(data: dict):
        """Result endpoints return {has_result, result, running, ...}. None until ready."""
        if data.get("has_result") and data.get("result"):
            return data["result"]
        return None

    # --- liveness ---
    def ping(self) -> bool:
        try:
            self._request("GET", "/api/status")
            return True
        except AiNieeUnavailable:
            return False

    # --- group 1 ---
    def get_status(self) -> TaskStatus:
        return TaskStatus.from_response(self._request("GET", "/api/status"))

    def start_task(self, mode: str, continue_: bool = False,
                   input_folder: str | None = None,
                   output_folder: str | None = None) -> dict:
        return self._request("POST", "/api/task/start", _clean({
            "mode": mode, "continue": continue_,
            "input_folder": input_folder, "output_folder": output_folder,
        }))

    def stop_task(self) -> dict:
        return self._request("GET", "/api/stop")

    def load_project(self, translation_project: str | None = None,
                     input_folder: str | None = None,
                     exclude_rule: str | None = None) -> dict:
        return self._request("POST", "/api/project/load", _clean({
            "translation_project": translation_project,
            "input_folder": input_folder,
            "exclude_rule": exclude_rule,
        }))

    # --- group 4 ---
    def start_analysis(self) -> dict:
        return self._request("POST", "/api/analysis/start")

    def get_analysis_result(self) -> AnalysisResult | None:
        payload = self._poll_payload(self._request("GET", "/api/analysis/result"))
        return AnalysisResult.from_payload(payload) if payload else None

    def get_analysis_data(self) -> AnalysisResult | None:
        data = self._request("GET", "/api/analysis/data")
        if not data.get("has_analysis"):
            return None
        return AnalysisResult.from_payload(data)

    def start_glossary(self) -> dict:
        return self._request("POST", "/api/glossary/translate")

    def get_glossary_result(self) -> GlossaryResult | None:
        payload = self._poll_payload(self._request("GET", "/api/glossary/result"))
        return GlossaryResult.from_payload(payload) if payload else None

    def test_api(self, tag: str) -> dict:
        return self._request("POST", "/api/apitest", {"tag": tag})

    def get_apitest_result(self) -> ApiTestResult | None:
        payload = self._poll_payload(self._request("GET", "/api/apitest/result"))
        return ApiTestResult.from_payload(payload) if payload else None

    def export(self, export_path: str) -> dict:
        return self._request("POST", "/api/export", {"export_path": export_path})

    def save_cache(self) -> dict:
        return self._request("POST", "/api/cache/save")

    # --- group 3: universal cache correction ---
    def cache_search(self, query: str, scope: str = "all", regex: bool = False,
                     flagged_only: bool = False, limit: int = 200) -> list[CacheItemView]:
        data = self._request("POST", "/api/cache/search", {
            "query": query, "scope": scope, "regex": regex,
            "flagged_only": flagged_only, "limit": limit,
        })
        return [CacheItemView.from_dict(it) for it in data.get("items", [])]

    def cache_stats(self) -> dict:
        return self._request("GET", "/api/cache/stats")

    def cache_update(self, edits: list[dict]) -> dict:
        return self._request("POST", "/api/cache/update", {"edits": edits})

    def cache_replace(self, rules: list[dict], dry_run: bool = True) -> dict:
        return self._request("POST", "/api/cache/replace", {"rules": rules, "dry_run": dry_run})
