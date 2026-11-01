"""Read files into a self-contained text model with verified source references."""
import fnmatch
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_project import CacheProject, ProjectType
from Backend.domain.models.intermediate import normalize_project, RETIRED_PROJECT_TYPES
from Backend.domain.models.cache_item import CacheItem
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.files.readers.file_reader import FileReader


def _validate_options(options, allowed):
    options = dict(options or {})
    unknown = set(options) - set(allowed)
    if unknown:
        raise PipelineError("VALIDATION_ERROR", f"不支持的读取参数: {', '.join(sorted(unknown))}")
    if not isinstance(options.get("exclude_rule", ""), str):
        raise PipelineError("VALIDATION_ERROR", "exclude_rule 必须为字符串")
    return options


def _make_reader(project_type, root, *, include_pdf=False, pages=None):
    if project_type in RETIRED_PROJECT_TYPES:
        raise PipelineError("FORMAT_REMOVED", "Office 转换格式已移除；PDF 请重新使用 BabelDOC 读取，DOC 请先转换为 DOCX")
    registry = FileReader()
    if not include_pdf:
        registry.reader_factory_dict.pop(ProjectType.BABELDOC_PDF, None)
    if project_type not in registry.reader_factory_dict:
        raise PipelineError("UNSUPPORTED_FORMAT", f"不支持的文件格式: {project_type}")
    entry = registry.reader_factory_dict[project_type]
    params = registry._get_reader_init_params(project_type, str(root))
    if project_type == ProjectType.BABELDOC_PDF:
        params["parse_options"] = {"pages": pages} if pages else {}
    return entry.resolve_factory()(**params)


def _language_stats(cache_file):
    from Backend.infrastructure.files.readers import reader_util
    stats = defaultdict(lambda: [0, 0.0])
    texts = []
    valid_count = 0
    for item in cache_file.items:
        if item.lang_code:
            language, confidence = item.lang_code[:2]
            stats[language][0] += 1
            stats[language][1] += confidence
            valid_count += 1
            detected = reader_util.make_final_detect_text(item)
            if detected:
                texts.append(detected)
    ordered = sorted(
        ((language, count, confidence / count) for language, (count, confidence) in stats.items()),
        key=lambda value: (value[1], value[2]), reverse=True,
    )
    high_threshold = max(valid_count * 0.1, min(valid_count, 3))
    mid_threshold = max(valid_count * 0.05, min(valid_count, 2))
    low_threshold = max(valid_count * 0.01, 1)
    high = [(language, count, confidence) for language, count, confidence in ordered if
            count >= high_threshold and confidence >= 0.82 or
            count >= mid_threshold and confidence >= 0.92 or
            count >= low_threshold and confidence >= 0.96]
    high_languages = {value[0] for value in high}
    if not high and texts:
        language, confidence, _ = reader_util.detect_language_with_mediapipe(
            [CacheItem(source_text="\n".join(texts))], 0, None,
        )[0]
        if confidence >= 0.82:
            high = [(language, len(texts), confidence)]
            high_languages.add(language)
    cache_file.language_stats = high or [("un", 0, -1.0)]
    cache_file.lc_language_stats = [value for value in ordered if value[0] not in high_languages]


def _read(path, options, *, kind):
    try:
        input_path = Path(path).expanduser().resolve(strict=True)
    except (OSError, TypeError, ValueError) as exc:
        raise PipelineError("INPUT_NOT_FOUND", f"输入路径不可访问: {path}") from exc
    if not input_path.is_file() and not input_path.is_dir():
        raise PipelineError("INVALID_INPUT", "输入必须为文件或目录")
    root = input_path if input_path.is_dir() else input_path.parent
    project_type = ProjectType.BABELDOC_PDF if kind == "pdf" else options.get("format", ProjectType.AUTO_TYPE)
    if not isinstance(project_type, str):
        raise PipelineError("VALIDATION_ERROR", "format 必须为字符串")
    pages = options.get("pages")
    if pages is not None and (not isinstance(pages, str) or not pages.strip()):
        raise PipelineError("VALIDATION_ERROR", "pages 必须为非空字符串或 null")
    files = sorted(input_path.rglob("*")) if input_path.is_dir() else [input_path]
    project = CacheProject(
        project_type=project_type, project_name=input_path.stem,
        input_path=str(input_path), project_create_time=datetime.now().isoformat(timespec="seconds"),
    )
    report = {"read_files": 0, "item_count": 0, "skipped_files": [], "errors": [], "warnings": []}
    patterns = [value.strip().replace("\\", "/") for value in options.get("exclude_rule", "").split(",") if value.strip()]
    text_index = 1
    try:
        with ExitStack() as stack:
            try:
                reader = stack.enter_context(_make_reader(project_type, root, include_pdf=kind in ("pdf", "legacy"), pages=pages))
            except (ImportError, ModuleNotFoundError) as exc:
                raise PipelineError("CAPABILITY_UNAVAILABLE", f"读取器依赖不可用: {exc}", 503) from exc
            patterns.extend(reader.exclude_rules)
            for source in files:
                if not source.is_file():
                    continue
                relative = source.relative_to(root).as_posix()
                if any(fnmatch.fnmatch(relative if "/" in rule else source.name, rule) for rule in patterns):
                    report["skipped_files"].append({"path": relative, "reason": "excluded"})
                    continue
                if kind == "document" and source.suffix.lower() == ".pdf":
                    report["skipped_files"].append({"path": relative, "reason": "use_read_pdf"})
                    continue
                try:
                    if source.suffix.lower() == ".doc":
                        raise PipelineError("FORMAT_REMOVED", "DOC 的 Office 转换支持已移除，请先转换为 DOCX")
                    if not reader.can_read(source):
                        report["skipped_files"].append({"path": relative, "reason": "unsupported_format"})
                        continue
                    before_hash = file_sha256(source)
                    cache_file = reader.read_source_file(source)
                    if not cache_file or not cache_file.items:
                        report["errors"].append({"path": relative, "code": "NO_TRANSLATABLE_TEXT", "message": "文件没有可读取的文本"})
                        continue
                    if file_sha256(source) != before_hash:
                        raise PipelineError("SOURCE_CHANGED", "读取期间源文件发生变化")
                    cache_file.storage_path = relative
                    if source.suffix.lower() in {".txt", ".md", ".srt", ".ass", ".vtt", ".lrc", ".json", ".trans", ".rpy", ".po", ".csv"}:
                        from Backend.infrastructure.files.readers.reader_util import detect_newlines
                        try:
                            cache_file.line_ending = detect_newlines(source.read_bytes().decode(cache_file.encoding))
                        except (UnicodeError, LookupError):
                            pass  # Keep the reader's metadata for unusual encodings.
                    cache_file.file_project_type = reader.get_file_project_type(source)
                    cache_file.media_type = "pdf" if cache_file.file_project_type == ProjectType.BABELDOC_PDF else "document"
                    cache_file.source_ref = {"path": str(source.resolve()), "sha256": before_hash, "verified": True}
                    for index, item in enumerate(cache_file.items):
                        item.text_index = text_index
                        item.locator = {"kind": cache_file.media_type, "index": index}
                        text_index += 1
                    _language_stats(cache_file)
                    project.files[relative] = cache_file
                    report["read_files"] += 1
                    report["item_count"] += len(cache_file.items)
                except Exception as exc:
                    report["errors"].append({"path": relative, "code": getattr(exc, "code", "READ_FAILED"), "message": str(exc)})
    finally:
        from Backend.infrastructure.files.readers.reader_util import close_lang_detector
        close_lang_detector()
    if not project.files:
        errors = report["errors"]
        code = errors[0]["code"] if len(errors) == 1 else "NO_READABLE_FILES"
        raise PipelineError(code, "没有成功读取的文件", details=report)
    project = normalize_project(project)
    return {"status": "partial" if report["errors"] else "success", "model": project, "report": report}


def read_document(path, options=None):
    return _read(path, _validate_options(options, {"format", "exclude_rule"}), kind="document")


def read_pdf(path, options=None):
    return _read(path, _validate_options(options, {"pages", "exclude_rule"}), kind="pdf")


def read_legacy_project(project_type, path, exclude_rule=""):
    if project_type == ProjectType.BABELDOC_PDF:
        return read_pdf(path, {"exclude_rule": exclude_rule})
    return _read(path, {"format": project_type, "exclude_rule": exclude_rule}, kind="legacy")


def read_image(path, options=None):
    raise PipelineError("IMAGE_READ_NOT_IMPLEMENTED", "图片读取尚未实现", 501)


def read_audio(path, options=None):
    raise PipelineError("AUDIO_READ_NOT_IMPLEMENTED", "音频读取尚未实现", 501)
