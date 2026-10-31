"""Defaults shared by the headless service and the desktop settings pages."""
import copy
import json
from functools import lru_cache

from Backend.core.paths import (
    default_input_dir, default_output_dir, default_polish_output_dir, backend_resource_path,
)


@lru_cache(maxsize=1)
def _sections():
    return json.loads(backend_resource_path("defaults.json").read_text(encoding="utf-8"))


def get_default_section(name):
    result = copy.deepcopy(_sections()[name])
    if name == "StartupPage":
        result["label_input_path"] = str(default_input_dir())
    elif name == "OutputSettingsPage":
        result["label_output_path"] = str(default_output_dir())
        result["label_polish_output_path"] = str(default_polish_output_dir())
    elif name == "AppFluentWindow":
        result["accent_color"] = "#808b9d"
    return result


def get_defaults():
    result = {}
    for name in _sections():
        result.update(get_default_section(name))
    from Backend.domain.prompts.prompt_builder_enum import PromptBuilderEnum
    result["translation_prompt_selection"] = {"last_selected_id": PromptBuilderEnum.COMMON, "prompt_content": ""}
    result["polishing_prompt_selection"] = {"last_selected_id": PromptBuilderEnum.POLISH_COMMON, "prompt_content": ""}
    return result
