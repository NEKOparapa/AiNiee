"""The explicit command/event contract shared by the server and desktop client."""
from Backend.core.base import Base

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

