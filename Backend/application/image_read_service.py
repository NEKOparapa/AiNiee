"""Read static images without running OCR or changing source files."""
import fnmatch
from pathlib import Path
import re

from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_project import CacheProject
from Backend.domain.models.intermediate import normalize_project
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.images.source import IMAGE_EXTENSIONS, load_image


def _natural_key(path):
    return tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                 for part in re.split(r"(\d+)", str(path)))


def read_image(path, options=None):
    if options is not None and not isinstance(options, dict):
        raise PipelineError("VALIDATION_ERROR", "图片读取 options 必须为对象")
    options = dict(options or {})
    if set(options) - {"exclude_rule"} or not isinstance(options.get("exclude_rule", ""), str):
        raise PipelineError("VALIDATION_ERROR", "图片读取仅支持字符串 exclude_rule")
    try:
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ValueError("empty path")
        source_path = Path(path).expanduser().resolve(strict=True)
        if not source_path.is_file() and not source_path.is_dir():
            raise ValueError("not a regular file or directory")
        root = source_path if source_path.is_dir() else source_path.parent
        sources = sorted(source_path.rglob("*"), key=_natural_key) if source_path.is_dir() else [source_path]
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        raise PipelineError("INPUT_NOT_FOUND", "图片输入文件或目录不可访问") from error
    project = CacheProject(project_type="Image", project_name=source_path.stem, input_path=str(source_path))
    report = {"read_files": 0, "item_count": 0, "errors": [], "warnings": [], "skipped_files": []}
    patterns = [rule.strip().replace("\\", "/") for rule in options.get("exclude_rule", "").split(",") if rule.strip()]
    for source in sources:
        if not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        reason = "excluded" if any(fnmatch.fnmatch(relative if "/" in rule else source.name, rule)
                                   for rule in patterns) else "unsupported_format" if source.suffix.lower() not in IMAGE_EXTENSIONS else None
        if reason:
            report["skipped_files"].append({"path": relative, "reason": reason})
            continue
        try:
            fingerprint = file_sha256(source)
            pixels, metadata = load_image(source)
            pixels.close()
            if file_sha256(source) != fingerprint:
                raise PipelineError("SOURCE_CHANGED", "读取期间图片源文件发生变化")
            project.files[relative] = CacheFile(storage_path=relative, file_project_type="Image", media_type="image",
                source_ref={"path": str(source.resolve()), "sha256": fingerprint, "verified": True},
                media_metadata=metadata, items=[], extra={"image_pipeline": {"read": {"status": "complete"}}})
            report["read_files"] += 1
        except Exception as error:
            report["errors"].append({"path": relative, "code": getattr(error, "code", "IMAGE_READ_FAILED"),
                                     "message": str(error)})
    if not project.files:
        code = report["errors"][0]["code"] if len(report["errors"]) == 1 else "NO_READABLE_IMAGES"
        raise PipelineError(code, "没有成功读取的图片", 400, report)
    return {"status": "partial" if report["errors"] else "success", "model": normalize_project(project), "report": report}
