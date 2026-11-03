"""Export an explicit intermediate model without changing its source files."""
import json
import os
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory

from Backend.application.pipeline_common import PipelineError
from Backend.core.paths import user_data_root
from Backend.domain.languages import map_language_name_to_code, get_most_common_language
from Backend.domain.models.cache_item import TranslationStatus
from Backend.domain.models.cache_project import ProjectType
from Backend.domain.models.intermediate import parse_model, RETIRED_PROJECT_TYPES
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.files.writers.file_outputer import FileOutputer
from Backend.infrastructure.files.writers.base_writer import (
    BaseTranslationWriter, BilingualOrder, OutputConfig, OutputLanguageConfig, TranslationOutputConfig,
)


_SOURCE_REQUIRED = {ProjectType.DOCX, ProjectType.EPUB, ProjectType.PPTX, ProjectType.RENPY,
                    ProjectType.TRANS, ProjectType.WOLF_XLSX, ProjectType.BABELDOC_PDF}
_OPTIONS = {"output_dir", "mode", "translated_suffix", "bilingual_suffix", "bilingual_order",
            "keep_original_encoding", "overwrite", "source_language", "target_language"}


def _relative_path(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise PipelineError("INVALID_OUTPUT_PATH", "storage_path 必须为非空相对路径")
    windows_path = PureWindowsPath(value)
    path = Path(value.replace("\\", "/"))
    if windows_path.drive or windows_path.is_absolute() or path.is_absolute() or ".." in path.parts:
        raise PipelineError("INVALID_OUTPUT_PATH", f"输出路径越界: {value}")
    return path


def _json_equal(first, second):
    return json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(second, ensure_ascii=False, sort_keys=True)


def _verify_legacy_source(cache_file, source):
    """An unversioned cache cannot establish identity by hashing a same-named file."""
    from Backend.application.read_service import _make_reader
    pages = cache_file.extra.get("pdf", {}).get("parse_options", {}).get("pages")
    with _make_reader(cache_file.file_project_type, source.parent, pages=pages) as reader:
        fresh = reader.on_read_source(source, reader.pre_read_source(source))
    if not fresh or len(fresh.items) != len(cache_file.items):
        raise PipelineError("SOURCE_MISMATCH", "旧缓存与源文件的条目数量不一致，请重新读取源文件")
    for original, current in zip(cache_file.items, fresh.items):
        if original.source_text != current.source_text:
            raise PipelineError("SOURCE_MISMATCH", "旧缓存与源文件原文或顺序不一致，请重新读取源文件")
        for key, value in original.extra.items():
            if key not in current.extra or not _json_equal(value, current.extra[key]):
                raise PipelineError("SOURCE_MISMATCH", f"旧缓存格式定位不一致: {key}")
        # Earlier caches can omit metadata now required by a faithful writer.
        original.extra = {**current.extra, **original.extra}
    for key, value in cache_file.extra.items():
        if key == "pdf":
            continue
        if key not in fresh.extra or not _json_equal(value, fresh.extra[key]):
            raise PipelineError("SOURCE_MISMATCH", f"旧缓存文件格式信息不一致: {key}")
    cache_file.extra = {**fresh.extra, **cache_file.extra}


def _source_path(cache_file, warnings):
    reference = cache_file.source_ref or {}
    raw_path = reference.get("path")
    required = cache_file.file_project_type in _SOURCE_REQUIRED
    if not raw_path:
        if required:
            raise PipelineError("SOURCE_NOT_FOUND", "该格式导出需要原始文件，请补充 source_ref.path")
        return None
    source = Path(raw_path).expanduser().resolve()
    if not source.is_file():
        if required or reference.get("sha256"):
            raise PipelineError("SOURCE_NOT_FOUND", f"源文件不存在: {source}")
        warnings.append({"file_id": cache_file.file_id, "code": "SOURCE_NOT_REQUIRED", "message": "原文件不可用，使用完整缓存导出"})
        return None
    actual = file_sha256(source)
    expected = reference.get("sha256")
    if expected and actual.lower() != expected.lower():
        raise PipelineError("SOURCE_CHANGED", f"源文件内容已变化: {source}")
    if not expected or not reference.get("verified", False):
        _verify_legacy_source(cache_file, source)
        if file_sha256(source) != actual:
            raise PipelineError("SOURCE_CHANGED", "校验期间源文件发生变化")
        cache_file.source_ref = {"path": str(source), "sha256": actual, "verified": True}
        warnings.append({"file_id": cache_file.file_id, "code": "LEGACY_SOURCE_VERIFIED", "message": "已通过原文和格式信息核对旧缓存源文件"})
    return source


def _commit_output(temporary, destination, overwrite):
    if overwrite:
        os.replace(temporary, destination)
    elif os.name == "nt":
        # Windows rename is atomic and refuses an existing destination. It also
        # works on removable drives/filesystems without hard-link support.
        try:
            os.rename(temporary, destination)
        except FileExistsError as exc:
            raise PipelineError("OUTPUT_EXISTS", f"输出文件已存在: {destination}", 409) from exc
    else:
        # A same-filesystem hard link publishes a complete file and never replaces
        # a destination created by another process between checking and publishing.
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise PipelineError("OUTPUT_EXISTS", f"输出文件已存在: {destination}", 409) from exc
        temporary.unlink()


def write_model(model, options=None):
    model = parse_model(model)
    options = dict(options or {})
    if set(options) - _OPTIONS:
        raise PipelineError("VALIDATION_ERROR", f"不支持的输出参数: {', '.join(sorted(set(options) - _OPTIONS))}")
    mode = options.get("mode", "translated")
    if mode not in ("translated", "bilingual", "both"):
        raise PipelineError("VALIDATION_ERROR", "mode 必须为 translated、bilingual 或 both")
    for name in ("overwrite", "keep_original_encoding"):
        if name in options and not isinstance(options[name], bool):
            raise PipelineError("VALIDATION_ERROR", f"{name} 必须为布尔值")
    try:
        bilingual_order = BilingualOrder(options.get("bilingual_order", "source_first"))
    except ValueError as exc:
        raise PipelineError("VALIDATION_ERROR", "无效的双语顺序") from exc
    suffixes = {"translated": options.get("translated_suffix", "_translated"),
                "bilingual": options.get("bilingual_suffix", "_bilingual")}
    if any(not isinstance(value, str) or any(character in value for character in '/\\:\x00') for value in suffixes.values()):
        raise PipelineError("INVALID_OUTPUT_PATH", "文件名后缀不能包含路径分隔符")
    if any(cache_file.media_type in ("image", "audio") for cache_file in model.files.values()):
        raise PipelineError("MEDIA_WRITE_NOT_IMPLEMENTED", "图片和音频正式输出尚未实现", 501)
    project_component = _relative_path(model.project_id)
    if len(project_component.parts) != 1:
        raise PipelineError("INVALID_OUTPUT_PATH", "project_id 不能包含路径")
    output_root = Path(options.get("output_dir") or user_data_root() / "Outputs" / project_component).expanduser().resolve()
    context = model.translation_context or {}
    source_language = options.get("source_language") or context.get("source_language")
    if source_language == "auto":
        source_language = get_most_common_language(model)
        if source_language == "un":
            source_language = None
    target_language = options.get("target_language") or context.get("target_language")
    languages = OutputLanguageConfig(
        source_lang_code=map_language_name_to_code(source_language) if source_language and source_language != "auto" else None,
        target_lang_code=map_language_name_to_code(target_language) if target_language else None,
    )
    registry = FileOutputer()
    report = {"errors": [], "warnings": [], "written_files": 0, "untranslated_items": 0}
    generated = []
    seen_destinations = set()
    all_sources = {Path(value.source_ref["path"]).expanduser().resolve() for value in model.files.values() if value.source_ref.get("path")}
    requested_modes = ("translated", "bilingual") if mode == "both" else (mode,)
    for cache_file in model.files.values():
        try:
            relative = _relative_path(cache_file.storage_path)
            project_type = cache_file.file_project_type
            if project_type in RETIRED_PROJECT_TYPES:
                raise PipelineError("FORMAT_REMOVED", "Office 转换格式已移除；PDF 请重新使用 BabelDOC 读取，DOC 请先转换为 DOCX")
            if project_type not in registry.writer_factory_dict or project_type == ProjectType.AUTO_TYPE:
                raise PipelineError("UNSUPPORTED_FORMAT", f"不支持的写出格式: {project_type}")
            source = _source_path(cache_file, report["warnings"])
            for item in cache_file.items:
                if item.translation_status not in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED):
                    item.translated_text = ""
                    report["untranslated_items"] += 1
            configuration = OutputConfig(
                translated_config=TranslationOutputConfig(True, suffixes["translated"], output_root),
                bilingual_config=TranslationOutputConfig(True, suffixes["bilingual"], output_root),
                input_root=source.parent if source else None, bilingual_order=bilingual_order,
                language_config=languages, keep_original_encoding=options.get("keep_original_encoding", False),
            )
            factory = registry.writer_factory_dict[project_type].resolve_factory()
            with factory(output_config=configuration) as writer:
                for output_mode in requested_modes:
                    enum_mode = BaseTranslationWriter.TranslationMode.TRANSLATED if output_mode == "translated" else BaseTranslationWriter.TranslationMode.BILINGUAL
                    if not writer.can_write(enum_mode):
                        if mode == "both":
                            report["warnings"].append({"file_id": cache_file.file_id, "code": "OUTPUT_MODE_UNSUPPORTED", "mode": output_mode})
                            continue
                        raise PipelineError("OUTPUT_MODE_UNSUPPORTED", f"{project_type} 不支持 {output_mode}")
                    name = relative.with_name(relative.stem + suffixes[output_mode] + relative.suffix)
                    destination = (output_root / name).resolve()
                    if not destination.is_relative_to(output_root) or destination in all_sources:
                        raise PipelineError("INVALID_OUTPUT_PATH", "输出不能越界或覆盖任何源文件")
                    if destination in seen_destinations:
                        raise PipelineError("OUTPUT_COLLISION", f"多个输出指向同一文件: {destination}")
                    seen_destinations.add(destination)
                    if destination.exists() and not options.get("overwrite", False):
                        raise PipelineError("OUTPUT_EXISTS", f"输出文件已存在: {destination}", 409)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with TemporaryDirectory(prefix=".ainiee-write-", dir=destination.parent) as scratch:
                        staged = Path(scratch) / destination.name
                        write = getattr(writer, enum_mode.write_method)
                        write(staged, cache_file, source)
                        if not staged.is_file():
                            raise PipelineError("WRITE_FAILED", "写出器没有生成目标文件")
                        if source and file_sha256(source) != cache_file.source_ref["sha256"]:
                            raise PipelineError("SOURCE_CHANGED", "写出期间源文件发生变化")
                        _commit_output(staged, destination, options.get("overwrite", False))
                    generated.append({"path": str(destination), "format": project_type, "mode": output_mode, "file_id": cache_file.file_id})
        except Exception as exc:
            report["errors"].append({"file_id": cache_file.file_id, "path": cache_file.storage_path,
                                     "code": getattr(exc, "code", "WRITE_FAILED"), "message": str(exc)})
    report["written_files"] = len(generated)
    status = "partial" if generated and report["errors"] else "failed" if report["errors"] or not generated else "success"
    return {"status": status, "files": generated, "report": report}
