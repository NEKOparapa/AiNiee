"""The explicit command/event contract shared by the server and desktop client."""
from Frontend.core.base import Base

E = Base.EVENT
COMMANDS = frozenset((
    E.TASK_START, E.TASK_STOP, E.TASK_MANUAL_EXPORT, E.TASK_MANUAL_SAVE_CACHE,
    E.ANALYSIS_TASK_START, E.API_TEST_START, E.GLOSS_TASK_START,
    E.TABLE_TRANSLATE_START, E.TABLE_POLISH_START, E.TABLE_PROOFREAD_START,
))
TABLE_UPDATES = frozenset((
    E.TABLE_BASIC_UPDATE, E.TABLE_SEARCH_UPDATE, E.TABLE_LANGUAGE_CHECK_UPDATE,
    E.TABLE_RULE_CHECK_UPDATE, E.TABLE_TERMINOLOGY_CHECK_UPDATE, E.TABLE_UPDATE,
))
TABLE_DONE = frozenset((
    E.TABLE_BASIC_DONE, E.TABLE_SEARCH_DONE, E.TABLE_LANGUAGE_CHECK_DONE,
    E.TABLE_RULE_CHECK_DONE, E.TABLE_TERMINOLOGY_CHECK_DONE,
))
NOTIFICATIONS = frozenset((
    E.API_TEST_DONE, E.TASK_UPDATE, E.TASK_STOP_DONE, E.TASK_COMPLETED,
    E.CACHE_FILE_AUTO_SAVE, E.GLOSS_TASK_DONE, E.ANALYSIS_TASK_UPDATE,
    E.ANALYSIS_TASK_DONE,
)) | TABLE_UPDATES | TABLE_DONE
TERMINAL_EVENTS = TABLE_DONE | frozenset((
    E.API_TEST_DONE, E.GLOSS_TASK_DONE, E.ANALYSIS_TASK_DONE,
    E.TASK_STOP_DONE, E.TASK_COMPLETED,
))


def to_wire(value):
    if hasattr(value, "to_dict"):
        return to_wire(value.to_dict())
    if isinstance(value, dict):
        return {str(k): to_wire(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_wire(v) for v in value]
    return value


def event_data_from_wire(data):
    # JSON object keys are strings. Table widgets index their rows with integers.
    if "updated_items" in data:
        data = {**data, "updated_items": {int(k): v for k, v in data["updated_items"].items()}}
    return data

def command_failure(event, data, message):
    """Terminal notification used when a command cannot finish normally."""
    payload = {"status": "error", "message": message}
    if event == E.ANALYSIS_TASK_START:
        return E.ANALYSIS_TASK_DONE, {**payload, "analysis_data": None}
    if event == E.GLOSS_TASK_START:
        return E.GLOSS_TASK_DONE, {**payload, "table_id": data.get("table_id"), "request_id": data.get("request_id"), "updated_data": None}
    if event == E.API_TEST_START:
        return E.API_TEST_DONE, {**payload, "success": [], "failure": [message]}
    if event == E.TASK_START:
        return E.TASK_STOP_DONE, payload
    if event in (E.TABLE_TRANSLATE_START, E.TABLE_POLISH_START, E.TABLE_PROOFREAD_START):
        done = data.get("done_event")
        if done in TABLE_DONE:
            return done, {**payload, "file_path": data.get("file_path"), "updated_item_count": 0}
    return None



class TaskType:

    TRANSLATION = 1000
    POLISH = 2000

class PromptBuilderEnum:

    COMMON = 100
    COT = 200
    LOCAL = 400
    CUSTOM = 1000

    POLISH_COMMON = 10001

    FORMAT_COMMON = 20001

    EXTRACT_COMMON = 30001
    EXTRACT_JUDGMENT = 30002

    @classmethod
    def normalize_translation_preset(cls, preset_id):
        # 300 was the removed reasoning-model preset in older configurations.
        return cls.COMMON if preset_id in (300, "300") else preset_id


class CheckResult:
    SUCCESS_REPORT = "SUCCESS_REPORT"
    SUCCESS_JUDGE_PASS = "SUCCESS_JUDGE_PASS"
    SUCCESS_JUDGE_FAIL = "SUCCESS_JUDGE_FAIL"
    HAS_RULE_ERRORS = "HAS_RULE_ERRORS"  # 存在需要列表展示的错误
    SUCCESS_LANGUAGE_RESULT = "SUCCESS_LANGUAGE_RESULT"
    SUCCESS_RULE_RESULT = "SUCCESS_RULE_RESULT"
    SUCCESS_TERMINOLOGY_RESULT = "SUCCESS_TERMINOLOGY_RESULT"
    ERROR_CACHE = "ERROR_CACHE"
    ERROR_NO_TRANSLATION = "ERROR_NO_TRANSLATION"
    ERROR_INVALID_LANG = "ERROR_INVALID_LANG"


class TranslationStatus:
    UNTRANSLATED = 0  # 待翻译
    TRANSLATED = 1  # 已翻译
    POLISHED = 2  # 已润色
    EXCLUDED = 7  # 已排除
    QUESTIONABLE = 8  # 存疑（非确定性排除，不参与翻译和润色，但做最后的漏翻检查）
