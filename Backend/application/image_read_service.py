"""Read static image metadata and original bytes, without model calls."""
import fnmatch
from pathlib import Path
import re

from Backend.application.pipeline_common import PipelineError
from Backend.application.execution_context import ExecutionContext
from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_project import CacheProject
from Backend.domain.models.intermediate import normalize_project
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.images.source import IMAGE_EXTENSIONS, load_image


def _natural_key(path):
    return tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                 for part in re.split(r"(\d+)", str(path)))


def read_image(path, options=None, context=None):
    context = context or ExecutionContext()
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
    project = normalize_project(CacheProject(project_type="Image", project_name=source_path.stem, input_path=str(source_path)))
    project.extra["image_translation_mode"] = "generation"
    report = {"stage": "read", "read_files": 0, "item_count": 0, "errors": [], "operation_errors": [], "warnings": [], "skipped_files": [], "cancelled": False}
    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception as error:
            report["operation_errors"].append({"code": "IMAGE_READ_CALLBACK_FAILED", "message": str(error)})
            report["stage_status"] = {"read": "failed"}
            return {"status": "failed", "model": project, "report": report}
    patterns = [rule.strip().replace("\\", "/") for rule in options.get("exclude_rule", "").split(",") if rule.strip()]
    for source in sources:
        if context.is_cancelled():
            break
        if not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        reason = "excluded" if any(fnmatch.fnmatch(relative if "/" in rule else source.name, rule)
                                   for rule in patterns) else "unsupported_format" if source.suffix.lower() not in IMAGE_EXTENSIONS else None
        if reason:
            report["skipped_files"].append({"path": relative, "reason": reason})
            continue
        pixels = None
        stage = "read"
        try:
            fingerprint = file_sha256(source)
            pixels, metadata = load_image(source)
            if file_sha256(source) != fingerprint:
                raise PipelineError("SOURCE_CHANGED", "读取期间图片源文件发生变化")
            file = CacheFile(storage_path=relative, file_project_type="Image", media_type="image",
                source_ref={"path": str(source.resolve()), "sha256": fingerprint, "verified": True},
                media_metadata=metadata, items=[], extra={})
            project.files[relative] = file
            normalize_project(project)
            report["read_files"] += 1
        except Exception as error:
            if context.is_cancelled():
                break
            report["errors"].append({"path": relative, "stage": stage, "code": getattr(error, "code", "IMAGE_READ_FAILED"),
                                     "message": str(error)})
        finally:
            if pixels is not None:
                pixels.close()
        try:
            if context.on_batch_complete and relative in project.files:
                context.on_batch_complete(project.files[relative].items, relative, {"operation": "image_read"})
            if context.on_progress:
                context.on_progress({"operation": "image_read", "path": relative,
                                     "read_files": report["read_files"]})
        except Exception as error:
            report["operation_errors"].append({"code": "IMAGE_READ_CALLBACK_FAILED", "message": str(error)})
            break
    report["cancelled"] = context.is_cancelled()
    if not project.files and not report["cancelled"] and not report["operation_errors"]:
        code = report["errors"][0]["code"] if len(report["errors"]) == 1 else "NO_READABLE_IMAGES"
        raise PipelineError(code, "没有成功读取的图片", 400, report)
    status = ("cancelled" if report["cancelled"] else "partial" if report["read_files"] and
              (report["errors"] or report["operation_errors"]) else "failed" if report["errors"] or report["operation_errors"] else "success")
    report["stage_status"] = {"read": status}
    project.extra.setdefault("media_workflow", {}).setdefault("stages", {})["read"] = {"status": status}
    return {"status": status, "model": normalize_project(project), "report": report}
