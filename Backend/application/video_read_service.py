"""Read video references without decoding or uploading their audio yet."""
import fnmatch
from pathlib import Path

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_project import CacheProject
from Backend.domain.models.intermediate import normalize_project
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.files.video_probe import VIDEO_EXTENSIONS, probe_video


def read_video(path, options=None, context=None):
    context = context or ExecutionContext()
    if options is not None and not isinstance(options, dict):
        raise PipelineError("VALIDATION_ERROR", "视频读取 options 必须为对象", 422)
    options = dict(options or {})
    if set(options) - {"exclude_rule"} or not isinstance(options.get("exclude_rule", ""), str):
        raise PipelineError("VALIDATION_ERROR", "视频读取仅支持字符串 exclude_rule", 422)
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise PipelineError("INVALID_INPUT", "视频输入路径不能为空")
    try:
        source_path = Path(path).expanduser().resolve(strict=True)
        if not source_path.is_file() and not source_path.is_dir():
            raise ValueError("not file or directory")
        root = source_path if source_path.is_dir() else source_path.parent
        sources = sorted(source_path.rglob("*")) if source_path.is_dir() else [source_path]
    except (OSError, ValueError, RuntimeError) as error:
        raise PipelineError("INPUT_NOT_FOUND", "视频输入路径不可访问") from error
    project = CacheProject(project_type="Video", project_name=source_path.stem, input_path=str(source_path))
    report = {"read_files": 0, "item_count": 0, "total_duration_ms": 0,
              "skipped_files": [], "errors": [], "warnings": []}
    patterns = [p.strip().replace("\\", "/") for p in options.get("exclude_rule", "").split(",") if p.strip()]
    error_statuses = []
    for source in sources:
        if context.is_cancelled():
            break
        if not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        reason = ("excluded" if any(fnmatch.fnmatch(relative if "/" in p else source.name, p) for p in patterns)
                  else "unsupported_format" if source.suffix.lower() not in VIDEO_EXTENSIONS else None)
        if reason:
            report["skipped_files"].append({"path": relative, "reason": reason})
            continue
        try:
            digest = file_sha256(source)
            metadata = probe_video(source)
            if file_sha256(source) != digest:
                raise PipelineError("SOURCE_CHANGED", "探测期间视频源文件发生变化", 409)
            project.files[relative] = CacheFile(
                storage_path=relative, file_project_type="Video", media_type="video",
                source_ref={"path": str(source.resolve()), "sha256": digest, "verified": True},
                media_metadata=metadata,
            )
            report["read_files"] += 1
            report["total_duration_ms"] += metadata["duration_ms"]
        except (PipelineError, OSError, ValueError) as error:
            report["errors"].append({"path": relative, "code": getattr(error, "code", "VIDEO_READ_FAILED"),
                                     "message": str(error)})
            error_statuses.append(getattr(error, "status_code", 400))
    if not project.files and not context.is_cancelled():
        errors = report["errors"]
        code = errors[0]["code"] if len(errors) == 1 else "NO_READABLE_VIDEO"
        if source_path.is_file() and not errors and source_path.suffix.lower() not in VIDEO_EXTENSIONS:
            code = "UNSUPPORTED_VIDEO_FORMAT"
        message = "没有成功读取的视频文件" + (f"：{errors[0]['message']}" if len(errors) == 1 else "")
        raise PipelineError(code, message,
                            error_statuses[0] if len(error_statuses) == 1 else 400, report)
    status = "cancelled" if context.is_cancelled() else "partial" if report["errors"] else "success"
    return {"status": status, "model": normalize_project(project), "report": report}
