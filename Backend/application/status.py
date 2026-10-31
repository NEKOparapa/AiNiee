"""Project progress exposed by the FastAPI service."""
import time

from Backend.core.base import Base


def get_app_status() -> str:
    """获取当前应用任务状态字符串。"""
    if Base.work_status == Base.STATUS.TASKING:
        return "TASKING"
    if Base.work_status == Base.STATUS.STOPING:
        return "STOPPING"
    if Base.work_status == Base.STATUS.TASKSTOPPED:
        return "STOPPED"
    return "IDLE"


def _parse_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_status_response(cache_manager) -> dict:
    """构建当前应用状态与翻译任务进度响应。"""
    project = getattr(cache_manager, "project", None) if cache_manager else None
    has_project = project is not None
    project_id = getattr(project, "project_id", "") if has_project else ""
    project_name = getattr(project, "project_name", "") if has_project else ""

    stats = {}
    stats_data = getattr(project, "stats_data", None) if has_project else None
    if stats_data is not None:
        if hasattr(stats_data, "to_dict"):
            stats = stats_data.to_dict()
        elif isinstance(stats_data, dict):
            stats = stats_data

    total_line = _parse_int(stats.get("total_line", 0))
    line = _parse_int(stats.get("line", 0))
    remaining_line = max(0, total_line - line)
    percent = round(line / total_line * 100, 2) if total_line > 0 else 0.0
    is_complete = total_line > 0 and line >= total_line

    start_time = _parse_float(stats.get("start_time", 0))
    recorded_time = _parse_float(stats.get("time", 0))
    if Base.work_status in (Base.STATUS.TASKING, Base.STATUS.STOPING) and start_time > 0:
        elapsed_seconds = int(max(0, time.time() - start_time))
    else:
        elapsed_seconds = int(max(0, recorded_time))

    return {
        "status": "success",
        "app_status": get_app_status(),
        "work_status_code": Base.work_status,
        "has_project": has_project,
        "project_id": project_id,
        "project_name": project_name,
        "progress": {
            "total_line": total_line,
            "line": line,
            "remaining_line": remaining_line,
            "percent": percent,
            "is_complete": is_complete,
            "total_requests": _parse_int(stats.get("total_requests", 0)),
            "error_requests": _parse_int(stats.get("error_requests", 0)),
            "token": _parse_int(stats.get("token", 0)),
            "total_completion_tokens": _parse_int(stats.get("total_completion_tokens", 0)),
            "elapsed_seconds": elapsed_seconds,
        },
    }
