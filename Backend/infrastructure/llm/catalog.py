"""Fetch provider model catalogs without importing desktop widgets."""
import httpx


def google_models(platform_config):
    from Backend.infrastructure.llm.llm_client_factory import LLMClientFactory
    client = LLMClientFactory().get_google_client(platform_config)
    excluded = ("native-audio", "image", "tts", "live")
    return [model.name.split("/")[-1] for model in client.models.list()
            if model.name and ("gemini" in model.name or "gemma" in model.name)
            and not any(word in model.name for word in excluded)]


def compatible_models(url, headers):
    with httpx.Client(http2=True, timeout=10) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    entries = data.get("data", []) if isinstance(data, dict) else data
    models = []
    for entry in entries if isinstance(entries, list) else []:
        name = entry if isinstance(entry, str) else (entry.get("id") or entry.get("model")) if isinstance(entry, dict) else None
        if name and "image" not in str(name).lower():
            models.append(str(name))
    return models
