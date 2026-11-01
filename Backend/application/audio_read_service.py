"""Read local audio files into the shared model; transcription is a separate step."""
import fnmatch
from pathlib import Path

from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_project import CacheProject
from Backend.domain.models.intermediate import normalize_project
from Backend.infrastructure.files.audio_probe import AUDIO_EXTENSIONS, probe_audio
from Backend.infrastructure.files.pipeline_support import file_sha256


def read_audio(path, options=None) -> dict:
    if options is not None and not isinstance(options, dict):
        raise PipelineError("VALIDATION_ERROR", "音频读取 options 必须为对象", 422)
    options = dict(options or {})
    if set(options) - {"exclude_rule"} or not isinstance(options.get("exclude_rule", ""), str):
        raise PipelineError("VALIDATION_ERROR", "音频读取仅支持字符串 exclude_rule", 422)
    if isinstance(path, str) and not path.strip():
        raise PipelineError("INVALID_INPUT", "音频输入路径不能为空")
    try:
        input_path = Path(path).expanduser().resolve(strict=True)
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise PipelineError("INPUT_NOT_FOUND", "音频输入路径不可访问") from error
    if not input_path.is_file() and not input_path.is_dir():
        raise PipelineError("INVALID_INPUT", "音频输入必须为本地文件或目录")
    root = input_path if input_path.is_dir() else input_path.parent
    try:
        sources = sorted(input_path.rglob("*")) if input_path.is_dir() else [input_path]
    except OSError as error:
        raise PipelineError("INPUT_NOT_READABLE", "音频目录无法遍历") from error
    project = CacheProject(project_type="Audio", project_name=input_path.stem, input_path=str(input_path))
    report = {"read_files": 0, "item_count": 0, "total_duration_ms": 0,
              "skipped_files": [], "errors": [], "warnings": []}
    patterns = [rule.strip().replace("\\", "/") for rule in options.get("exclude_rule", "").split(",") if rule.strip()]
    error_statuses = []
    for source in sources:
        if not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(relative if "/" in rule else source.name, rule) for rule in patterns):
            report["skipped_files"].append({"path": relative, "reason": "excluded"})
            continue
        if source.suffix.lower() not in AUDIO_EXTENSIONS:
            report["skipped_files"].append({"path": relative, "reason": "unsupported_format"})
            continue
        try:
            before_hash = file_sha256(source)
            metadata = probe_audio(source)
            if file_sha256(source) != before_hash:
                raise PipelineError("SOURCE_CHANGED", "探测期间音频源文件发生变化")
            project.files[relative] = CacheFile(
                storage_path=relative, file_project_type="Audio", media_type="audio",
                source_ref={"path": str(source.resolve()), "sha256": before_hash, "verified": True},
                media_metadata=metadata, items=[],
            )
            report["read_files"] += 1
            report["total_duration_ms"] += metadata["duration_ms"]
        except Exception as error:
            report["errors"].append({"path": relative, "code": getattr(error, "code", "AUDIO_READ_FAILED"), "message": str(error)})
            error_statuses.append(getattr(error, "status_code", 400))
    if not project.files:
        errors = report["errors"]
        code = errors[0]["code"] if len(errors) == 1 else "NO_READABLE_AUDIO"
        if input_path.is_file() and not errors and input_path.suffix.lower() not in AUDIO_EXTENSIONS:
            code = "UNSUPPORTED_AUDIO_FORMAT"
        raise PipelineError(code, "没有成功读取的音频文件", error_statuses[0] if len(error_statuses) == 1 else 400, report)
    return {"status": "partial" if report["errors"] else "success", "model": normalize_project(project), "report": report}
