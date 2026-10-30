"""Platform configuration and provider operations extracted from the Qt pages."""

import json
import re
import secrets
from copy import deepcopy

import httpx

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import platform_preset_path
from ModuleFolders.Config.RequestHeaders import normalize_extra_headers
from ModuleFolders.Infrastructure.LLMRequester.ModelConfigHelper import ModelConfigHelper
from ModuleFolders.Log.LogSystem import sensitive_values


ROLES = ("active", "extract", "translate", "polish", "proofread")
MIGRATION_KEY = "_active_follow_migration_done"
EDITABLE_FIELDS = {
    "name", "model", "api_url", "api_key", "api_format", "auto_complete",
    "region", "access_key", "secret_key", "rpm_limit", "temperature",
    "think_switch", "think_depth", "thinking_budget", "thinking_level",
    "tls_switch", "extra_body", "extra_headers", "model_datas",
}
VIEW_DEFAULTS = {
    "name": "", "model": "", "api_url": "", "api_key": "", "group": "custom",
    "api_format": "OpenAI", "auto_complete": False, "region": "", "access_key": "",
    "secret_key": "", "rpm_limit": 4096, "temperature": 1.0, "think_switch": False,
    "think_depth": "low", "thinking_budget": -1, "thinking_level": "high",
    "tls_switch": False, "extra_body": {}, "extra_headers": {}, "model_datas": [],
    "format_datas": ["OpenAI", "Anthropic", "Google"], "region_datas": [],
    "key_in_settings": [],
}


class PlatformService(ConfigMixin):
    @staticmethod
    def _presets() -> dict:
        with open(platform_preset_path(), encoding="utf-8") as source:
            return json.load(source)["platforms"]

    @staticmethod
    def _normalize_bindings(config: dict) -> dict:
        """Keep the existing active-interface migration and role fallback rules."""
        platforms = config.setdefault("platforms", {})
        settings = config.setdefault("api_settings", {})
        active = settings.get("active")
        if active not in platforms:
            active = next((settings.get(role) for role in ROLES[1:] if settings.get(role) in platforms), None)
        settings["active"] = active
        if not settings.get(MIGRATION_KEY):
            if active is not None and all(settings.get(role) == active for role in ROLES[1:]):
                for role in ROLES[1:]:
                    settings[role] = None
            settings[MIGRATION_KEY] = True
        for role in ROLES[1:]:
            if settings.get(role) not in platforms:
                settings[role] = None
        return {role: settings.get(role) for role in ROLES}

    @staticmethod
    def _metadata(platform_id: str, platform: dict) -> dict:
        """The old edit-page visibility rules belong to the application layer."""
        settings = set(platform.get("key_in_settings") or [])
        fields = {"name", "model", "model_datas"}
        fields.update(settings & {"api_url", "api_key", "api_format", "region", "access_key", "secret_key"})
        if "api_url" in settings:
            fields.add("auto_complete")
        fields.update(settings & {"extra_body", "rpm_limit", "temperature", "think_switch"})
        tag = str(platform.get("tag") or platform_id).lower()
        url = str(platform.get("api_url") or "").lower()
        is_volcengine = tag.startswith("volcengine") or "volces.com" in url or "volcengine" in url
        if platform_id == "custom" or platform_id.startswith("custom_"):
            fields.add("extra_headers")
        if is_volcengine:
            fields.add("think_switch")
        api_format = platform.get("api_format", "OpenAI")
        if ("think_depth" in settings or is_volcengine) and api_format in ("OpenAI", "Anthropic"):
            fields.add("think_depth")
        if api_format == "Google":
            if ModelConfigHelper.is_gemini_3_or_newer(platform.get("model", "")):
                fields.add("thinking_level")
            elif "thinking_budget" in settings:
                fields.add("thinking_budget")
        if "tls_switch" in settings or api_format == "OpenAI":
            fields.add("tls_switch")
        return {
            "fields": sorted(fields),
            "think_depth_options": ["low", "medium", "high", "xhigh"] + ([] if tag.startswith("xai") or "api.x.ai" in url else ["max"]),
            "thinking_level_options": ModelConfigHelper.get_thinking_level_options(platform.get("model", "")),
        }

    def _view(self, platform_id: str, raw: dict, presets: dict | None = None) -> dict:
        presets = self._presets() if presets is None else presets
        preset_id = next((key for key in presets if platform_id == key or platform_id.startswith(key + "_")), "custom")
        # Fill missing fields only in the response, leaving the saved config intact.
        result = {**deepcopy(VIEW_DEFAULTS), **deepcopy(presets.get(preset_id, {})), **deepcopy(raw)}
        result.update(id=platform_id, tag=platform_id)
        result["metadata"] = self._metadata(platform_id, result)
        return result

    @staticmethod
    def _get(config: dict, platform_id: str) -> dict:
        platform = config.get("platforms", {}).get(platform_id)
        if not isinstance(platform, dict):
            raise ApplicationError("platform_not_found", 404)
        return platform

    @staticmethod
    def _validate_changes(changes: dict) -> dict:
        if not set(changes).issubset(EDITABLE_FIELDS):
            raise ApplicationError("invalid_platform", 422)
        result = deepcopy(changes)
        for key in ("name", "model"):
            if key in result:
                result[key] = result[key].strip()
                if not result[key]:
                    raise ApplicationError("invalid_platform", 422)
        for key in ("api_url", "api_key", "region", "access_key", "secret_key"):
            if key in result:
                result[key] = result[key].strip()
        if "extra_headers" in result:
            try:
                result["extra_headers"] = normalize_extra_headers(result["extra_headers"])
            except ValueError:
                raise ApplicationError("invalid_headers", 422) from None
        return result

    def list_platforms(self) -> dict:
        config = self.load_config()
        bindings = self._normalize_bindings(config)
        presets = self._presets()
        return {
            "platforms": [self._view(key, value, presets) for key, value in config["platforms"].items()],
            "presets": [self._view(key, value, presets) for key, value in presets.items()],
            "bindings": bindings,
        }

    def create_platform(self, data: dict) -> dict:
        presets = self._presets()
        values = deepcopy(data)
        preset_id = values.pop("preset_id")
        if preset_id not in presets:
            raise ApplicationError("platform_preset_not_found", 422)
        changes = self._validate_changes(values)
        platform = {**deepcopy(presets[preset_id]), **changes}
        if preset_id == "custom" and not platform.get("api_url"):
            raise ApplicationError("platform_url_required", 422)
        if preset_id == "amazonbedrock" and any(not platform.get(key) for key in ("region", "access_key", "secret_key")):
            raise ApplicationError("platform_credentials_required", 422)
        models = platform.setdefault("model_datas", [])
        if platform["model"] not in models:
            models.append(platform["model"])
        with exclusive_operation():
            def update(config):
                self._normalize_bindings(config)
                platform_id = f"{preset_id}_{secrets.randbelow(900000) + 100000}"
                while platform_id in config["platforms"]:
                    platform_id = f"{preset_id}_{secrets.randbelow(900000) + 100000}"
                platform["tag"] = platform_id
                config["platforms"][platform_id] = platform
            self.update_config(update)
        self._notify_changed()
        return self._view(platform["tag"], platform, presets)

    def update_platform(self, platform_id: str, values: dict) -> dict:
        changes = self._validate_changes(values)
        with exclusive_operation():
            def update(config):
                platform = self._get(config, platform_id)
                platform.update(changes)
                if "model" in changes:
                    models = platform.setdefault("model_datas", [])
                    if platform["model"] not in models:
                        models.append(platform["model"])
                self._normalize_bindings(config)
            config = self.update_config(update)
        self._notify_changed()
        return self._view(platform_id, config["platforms"][platform_id])

    def delete_platform(self, platform_id: str) -> dict:
        with exclusive_operation():
            def update(config):
                self._get(config, platform_id)
                self._normalize_bindings(config)
                for role in ROLES:
                    if config["api_settings"].get(role) == platform_id:
                        config["api_settings"][role] = None
                del config["platforms"][platform_id]
                self._normalize_bindings(config)
            self.update_config(update)
        self._notify_changed()
        return {"deleted": True}

    def update_bindings(self, bindings: dict) -> dict:
        with exclusive_operation():
            def update(config):
                self._normalize_bindings(config)
                for role, platform_id in bindings.items():
                    if role not in ROLES or (platform_id is not None and platform_id not in config["platforms"]):
                        raise ApplicationError("invalid_platform_binding", 422)
                config["api_settings"].update(bindings)
                self._normalize_bindings(config)
            config = self.update_config(update)
        self._notify_changed()
        return {role: config["api_settings"].get(role) for role in ROLES}

    @staticmethod
    def _notify_changed() -> None:
        EventManager.get_singleton().emit(Base.EVENT.PLATFORMS_CHANGED, {})

    def test_platform(self, platform_id: str) -> dict:
        """Run the existing test prompt for each key without exposing key values.

        Calling the requester directly avoids the legacy executor's plaintext
        failure-key log and its asynchronous state ownership. The process-wide
        operation guard restores the prior task state even when a provider raises.
        """
        from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester

        with exclusive_operation(status=Base.STATUS.API_TEST):
            platform = self._view(platform_id, self._get(self.load_config(), platform_id))
            api_url = self._test_url(platform_id, platform)
            api_keys = re.sub(r"\s+", "", platform["api_key"]).split(",")
            results = []
            with sensitive_values(self._secrets(platform)):
                for index, api_key in enumerate(api_keys, start=1):
                    config = deepcopy(platform)
                    config.update(
                        target_platform=platform_id, api_url=api_url,
                        api_key=api_key, model_name=platform["model"],
                    )
                    try:
                        skipped, _, _, _, _ = LLMRequester().sent_request(
                            [{"role": "user", "content": "小可爱，你在干嘛"}],
                            "你接下来要扮演我的女朋友，名字叫欣雨，请你以女朋友的方式回复我。",
                            config,
                        )
                        success = skipped is False
                    except Exception:
                        # Provider exceptions can contain the key or reflected
                        # request headers. Only a stable code crosses this boundary.
                        success = False
                    results.append({
                        "key_index": index, "success": success,
                        "error_code": None if success else "platform_test_failed",
                    })
            success_count = sum(item["success"] for item in results)
            result = {
                "platform_id": platform_id, "success_count": success_count,
                "failure_count": len(results) - success_count, "results": results,
            }
        # Consumers fetching /tasks/current after this event must see the restored
        # status, not the transient API_TEST status.
        EventManager.get_singleton().emit(Base.EVENT.API_TEST_DONE, result)
        return result

    @staticmethod
    def _test_url(platform_id: str, platform: dict) -> str:
        """Reuse the URL completion rules of SimpleExecutor.api_test."""
        api_url = platform["api_url"].strip().rstrip("/")
        if not api_url:
            return api_url
        for suffix in ("/chat/completions", "/completions", "/chat"):
            if api_url.endswith(suffix):
                api_url = api_url[:-len(suffix)].rstrip("/")
                break
        versions = tuple(f"/v{version}" for version in range(1, 7))
        if (platform_id.startswith("anthropic") or platform["api_format"].lower() == "anthropic") and platform["auto_complete"]:
            for suffix in versions:
                if api_url.endswith(suffix):
                    api_url = api_url[:-len(suffix)].rstrip("/")
                    break
        elif platform_id.startswith(("sakura", "LocalLLM")) or platform["auto_complete"]:
            if not api_url.endswith(versions):
                api_url += "/v1"
        return api_url

    def get_models(self, platform_id: str) -> dict:
        platform = self._view(platform_id, self._get(self.load_config(), platform_id))
        try:
            with sensitive_values(self._secrets(platform)):
                models = self._fetch_models(platform_id, platform)
        except ApplicationError:
            raise
        except Exception:
            # Provider errors may contain credentials or reflected request headers.
            raise ApplicationError("model_fetch_failed", 502) from None
        return {"platform_id": platform_id, "models": sorted(set(models))}

    @staticmethod
    def _secrets(platform: dict) -> list[str]:
        values = [platform.get("access_key", ""), platform.get("secret_key", "")]
        values.extend(re.sub(r"\s+", "", platform.get("api_key", "")).split(","))
        for value in (platform.get("extra_headers") or {}).values():
            values.append(value)
            if isinstance(value, str) and value.lower().startswith("bearer "):
                values.append(value[7:])
        return values

    @staticmethod
    def _fetch_models(platform_id: str, platform: dict) -> list[str]:
        headers = normalize_extra_headers(platform.get("extra_headers"))
        api_format = platform["api_format"]
        if api_format == "Google":
            from ModuleFolders.Infrastructure.LLMRequester.LLMClientFactory import LLMClientFactory

            client = LLMClientFactory().get_google_client(platform)
            return [
                model.name.split("/")[-1] for model in client.models.list()
                if model.name and any(kind in model.name for kind in ("gemini", "gemma"))
                and not any(word in model.name for word in ("native-audio", "image", "tts", "live"))
            ]
        if api_format == "Amazon Bedrock":
            raise ApplicationError("model_fetch_unsupported", 422)
        base_url = platform["api_url"].rstrip("/")
        keys = re.sub(r"\s+", "", platform["api_key"])
        if api_format == "Anthropic":
            if platform["auto_complete"]:
                base_url = re.sub(r"/v\d+$", "", base_url)
            url = f"{base_url}/v1/models"
            auth_headers = {"anthropic-version": "2023-06-01"}
            if keys:
                auth_headers["x-api-key"] = keys.split(",")[0]
        else:
            if (platform_id.startswith("sakura") and not base_url.endswith("/v1")) or (
                platform["auto_complete"] and not re.search(r"/v[1-9]$", base_url)
            ):
                base_url += "/v1"
            url = f"{base_url}/models"
            auth_headers = {"authorization": f"Bearer {keys.split(',')[0]}"} if keys else {}
        auth_headers.update(headers)
        with httpx.Client(http2=True, timeout=10.0) as client:
            response = client.get(url, headers=auth_headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        entries = data.get("data", []) if isinstance(data, dict) else data
        models = []
        if isinstance(entries, list):
            for entry in entries:
                model = (entry.get("id") or entry.get("model")) if isinstance(entry, dict) else entry
                if isinstance(model, str) and model and "image" not in model.lower():
                    models.append(model)
        return models
