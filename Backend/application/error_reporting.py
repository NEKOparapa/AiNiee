"""Turn terminal task reports into readable logs without dumping model content."""
import logging

from Backend.core.log_system import redact


_ERROR_KEYS = ("errors", "operation_errors", "failed_items")
_STAGES = {"read": "读取", "recognize": "转录", "transcription": "转录",
           "translate": "翻译", "translation": "翻译", "generate": "生成译图",
           "generation": "生成译图", "preview": "预览", "export": "导出", "write": "导出"}
_LANES = {"document": "文本", "image": "图片", "audio": "音频", "video": "视频"}


def _errors(report, stage=""):
    if not isinstance(report, dict):
        return
    stage = report.get("stage") or stage
    for key in _ERROR_KEYS:
        values = report.get(key, [])
        for error in values if isinstance(values, list) else [values]:
            if error:
                yield stage, error
    # Pipeline reports nest their per-stage reports. Never traverse models,
    # provider configs, raw replies, subtitles, or arbitrary request data.
    for key in (*_STAGES, "report", "output"):
        if isinstance(report.get(key), dict):
            yield from _errors(report[key], key if key in _STAGES else stage)


def _detail(stage, error):
    if not isinstance(error, dict):
        return redact(str(error))
    code = str(error.get("code") or "")
    if code == "CANCELLED" or code.endswith("_CANCELLED"):
        return ""
    stage = error.get("stage") or stage
    context = []
    if stage:
        context.append(f"阶段={_STAGES.get(stage, stage)}")
    for key, label in (("path", "文件"), ("file_id", "文件ID"), ("item_id", "条目ID"), ("text_index", "条目序号")):
        value = error.get(key)
        if isinstance(value, (str, int)) and value != "":
            context.append(f"{label}={value}")
    message = error.get("message") or error.get("reason") or "处理未完成"
    return redact(" ".join([*context, f"[{code}]" if code else "", str(message)]).strip())


def log_job_errors(job):
    result = job.get("result")
    result = result if isinstance(result, dict) else {}
    # An error may occur after useful work, even when the task is partial or
    # subsequently cancelled. Preserve all actual failures, deduplicating copies.
    stage = job["name"].rsplit("/", 1)[-1]
    lines = list(dict.fromkeys(line for stage, error in _errors(result, stage)
                              if (line := _detail(stage, error))))
    if not lines and job["state"] == "failed":
        detail = job.get("error") or {"message": result.get("message") or "任务未成功完成"}
        if line := _detail("", detail):
            lines.append(line)
    if not lines:
        return
    kind = _LANES.get(job["lane"], job["lane"])
    # One event per report avoids overflowing the WebSocket queue on large
    # failures. The existing GUI limit keeps display bounded; file logs keep all.
    logging.getLogger("AiNiee.backend").error(redact(
        f"后端任务错误：{kind} / {job['name']}（任务ID={job['id']}）\n" + "\n".join(lines)
    ))
