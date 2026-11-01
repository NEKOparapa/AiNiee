"""Named backend notifications adapted to desktop-only UI events."""
from Frontend.core.base import Base

PROTOCOL_VERSION = 2
E = Base.EVENT
TABLE_VIEW_EVENTS = {
    "basic": (E.TABLE_BASIC_UPDATE, E.TABLE_BASIC_DONE),
    "search": (E.TABLE_SEARCH_UPDATE, E.TABLE_SEARCH_DONE),
    "language_check": (E.TABLE_LANGUAGE_CHECK_UPDATE, E.TABLE_LANGUAGE_CHECK_DONE),
    "rule_check": (E.TABLE_RULE_CHECK_UPDATE, E.TABLE_RULE_CHECK_DONE),
    "terminology_check": (E.TABLE_TERMINOLOGY_CHECK_UPDATE, E.TABLE_TERMINOLOGY_CHECK_DONE),
}
NOTIFICATION_EVENTS = {
    "translation.progress": E.TASK_UPDATE,
    "translation.stopped": E.TASK_STOP_DONE,
    "translation.completed": E.TASK_COMPLETED,
    "analysis.progress": E.ANALYSIS_TASK_UPDATE,
    "analysis.completed": E.ANALYSIS_TASK_DONE,
    "api_test.completed": E.API_TEST_DONE,
    "glossary.completed": E.GLOSS_TASK_DONE,
    "project.saved": E.CACHE_FILE_AUTO_SAVE,
    "project.export.completed": E.PROJECT_EXPORT_DONE,
}


def to_wire(value):
    if hasattr(value, "to_dict"):
        return to_wire(value.to_dict())
    if isinstance(value, dict):
        return {str(k): to_wire(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_wire(v) for v in value]
    return value


def notification_event(name, data):
    """Resolve a known notification; numeric IDs never cross the API boundary."""
    if name in ("table.updated", "table.completed"):
        events = TABLE_VIEW_EVENTS.get(data.get("view"))
        if events is None:
            return None
        event = events[0 if name == "table.updated" else 1]
    else:
        event = NOTIFICATION_EVENTS.get(name)
        if event is None:
            return None
    # JSON object keys are strings. Table widgets index their rows with integers.
    if "updated_items" in data:
        data = {**data, "updated_items": {int(k): v for k, v in data["updated_items"].items()}}
    return event, data

def request_failure(operation, data, message):
    """Local terminal callback when an explicit HTTP operation is rejected."""
    payload = {"status": "error", "message": message}
    if operation == "analysis":
        return E.ANALYSIS_TASK_DONE, {**payload, "analysis_data": None}
    if operation == "glossary.translate":
        return E.GLOSS_TASK_DONE, {**payload, "table_id": data.get("table_id"), "request_id": data.get("request_id"), "updated_data": None}
    if operation == "api_test":
        return E.API_TEST_DONE, {**payload, "success": [], "failure": [message]}
    if operation == "translation":
        return E.TASK_STOP_DONE, payload
    if operation in ("table.translate", "table.polish", "table.proofread"):
        events = TABLE_VIEW_EVENTS.get(data.get("view"))
        if events:
            return events[1], {
                **payload, "operation": operation.split(".", 1)[1],
                "file_path": data.get("file_path"), "updated_item_count": 0,
                "updated_file_count": 0,
            }
    return None



class TaskType:

    TRANSLATION = 1000

class PromptBuilderEnum:

    COMMON = 100
    COT = 200
    LOCAL = 400
    CUSTOM = 1000

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
