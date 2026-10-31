"""API adapters for server-owned editing rules; no local business implementation."""
import copy
import json
import threading
from collections import OrderedDict

from Frontend.core.config import ConfigMixin

_validation = OrderedDict()
_lock = threading.RLock()


def _key(operation, args, kwargs):
    return (id(ConfigMixin.config_backend()), operation, json.dumps([args, kwargs], sort_keys=True, ensure_ascii=False))


def _remember(key, result):
    with _lock:
        _validation[key] = result
        _validation.move_to_end(key)
        while len(_validation) > 8192:
            _validation.popitem(last=False)


def call_editor(operation, *args, **kwargs):
    key = _key(operation, args, kwargs)
    with _lock:
        if key in _validation:
            return copy.deepcopy(_validation[key])
    response = ConfigMixin.config_backend().request(
        "POST", f"/api/editor/{operation}", json={"args": args, "kwargs": kwargs},
    )
    for item in response.get("validation", []):
        row = item["row"]
        _remember(_key("glossary.get_row_state", [row], {}), item["state"])
        for field in ("src", "markers"):
            _remember(_key("regex.is_valid_re_pattern", [row, field], {}), item[field])
    if operation.startswith("model.") or operation in ("glossary.get_row_state", "regex.is_valid_re_pattern"):
        _remember(key, response["result"])
    return response["result"]


def _method(operation):
    return staticmethod(lambda *args, **kwargs: call_editor(operation, *args, **kwargs))


class TableConfigHelper:
    KINDS = ("prompt_dictionary", "exclusion_list", "pre_translation", "post_translation")
    get_tables = _method("table.get_tables")
    new_table = _method("table.new_table")
    normalize_rows = _method("table.normalize_rows")
    merge_edited_rows = _method("table.merge_edited_rows")
    normalize_match_options = _method("table.normalize_match_options")


class RegexSwitchHelper:
    normalize_exclusion_rows = _method("regex.normalize_exclusion_rows")
    normalize_replacement_rows = _method("regex.normalize_replacement_rows")
    is_valid_re_pattern = _method("regex.is_valid_re_pattern")


class GlossaryHelper:
    STATE_INVALID = "invalid"
    normalize_rows = _method("glossary.normalize_rows")
    get_row_state = _method("glossary.get_row_state")

    @classmethod
    def is_row_valid(cls, row):
        return cls.get_row_state(row) != cls.STATE_INVALID


class CharacterHelper:
    VALID_KEY = "is_valid"
    normalize_rows = _method("character.normalize_rows")


class ModelConfigHelper:
    get_thinking_level_options = _method("model.get_thinking_level_options")
    is_gemini_3_or_newer = _method("model.is_gemini_3_or_newer")


class PromptBuilderExtraction:
    BASIC = "basic"
    JUDGMENT = "judgment"
    STAGES = {
        BASIC: {"selection_key": "extract_prompt_selection", "user_data_key": "extract_user_prompt_data", "preset_id": 30001},
        JUDGMENT: {"selection_key": "extract_judgment_prompt_selection", "user_data_key": "extract_judgment_user_prompt_data", "preset_id": 30002},
    }
    get_user_prompts = _method("extraction.get_user_prompts")
    get_selected_user_prompt = _method("extraction.get_selected_user_prompt")


def normalize_extra_headers(raw):
    return call_editor("headers.normalize", raw)


def parse_extra_headers(text):
    return call_editor("headers.parse", text)
