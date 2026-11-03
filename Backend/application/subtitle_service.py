"""Write time-aligned audio segments as subtitles without changing their model."""
import html
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from Backend.application.pipeline_common import PipelineError
from Backend.core.paths import user_data_root
from Backend.domain.models.cache_item import TranslationStatus
from Backend.domain.models.intermediate import parse_model, validate_storage_path


_OPTIONS = {"format", "mode", "bilingual_order", "output_dir", "suffix", "overwrite"}
_INVALID_NAME = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED_NAME = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)


def _directory_path(value):
    try:
        path = Path(value).expanduser().resolve()
        if any(_INVALID_NAME.search(part) or _RESERVED_NAME.match(part) or part.endswith((".", " "))
               for part in path.parts if part != path.anchor):
            raise PipelineError("INVALID_OUTPUT_PATH", "output_dir 包含非法目录名称", 422)
        for ancestor in (path, *path.parents):
            if ancestor.exists():
                if not ancestor.is_dir():
                    raise PipelineError("INVALID_OUTPUT_PATH", "output_dir 或其父路径是文件", 422)
                break
        return path
    except PipelineError:
        raise
    except (OSError, ValueError, RuntimeError) as error:
        raise PipelineError("INVALID_OUTPUT_PATH", "output_dir 不是有效目录路径", 422) from error


def validate_subtitle_options(options=None) -> dict:
    """Validate options and existing paths without creating directories or files."""
    if options is not None and not isinstance(options, dict):
        raise PipelineError("VALIDATION_ERROR", "字幕 options 必须为对象", 422)
    options = dict(options or {})
    if set(options) - _OPTIONS:
        raise PipelineError("VALIDATION_ERROR", "不支持的字幕输出参数", 422,
                            {"fields": sorted(set(options) - _OPTIONS)})
    normalized = {"format": "srt", "mode": "translated", "bilingual_order": "source_first",
                  "output_dir": None, "suffix": "_subtitles", "overwrite": False, **options}
    for name, allowed in (("format", ("srt", "vtt", "lrc", "ass")),
                          ("mode", ("translated", "source", "bilingual")),
                          ("bilingual_order", ("source_first", "translation_first"))):
        if normalized[name] not in allowed:
            raise PipelineError("VALIDATION_ERROR", f"无效的字幕 {name}", 422)
    if not isinstance(normalized["overwrite"], bool):
        raise PipelineError("VALIDATION_ERROR", "overwrite 必须为布尔值", 422)
    suffix = normalized["suffix"]
    if not isinstance(suffix, str) or _INVALID_NAME.search(suffix) or "/" in suffix or "\\" in suffix:
        raise PipelineError("INVALID_OUTPUT_PATH", "字幕后缀不能包含路径分隔符或非法文件名字符", 422)
    output_dir = normalized["output_dir"]
    if output_dir is not None:
        if not isinstance(output_dir, (str, os.PathLike)) or not str(output_dir).strip() or "\x00" in str(output_dir):
            raise PipelineError("INVALID_OUTPUT_PATH", "output_dir 必须为非空目录路径", 422)
        normalized["output_dir"] = str(_directory_path(output_dir))
    return normalized


def _clean_text(value):
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Empty lines would prematurely terminate an SRT/WebVTT cue.
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def _cue_text(item, options, warnings, file_id):
    source = _clean_text(item.source_text)
    if options["mode"] == "source":
        return source, False
    translated = _clean_text(item.translated_text)
    translated = translated if item.translation_status in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED) else ""
    if not translated:
        warnings.append({"file_id": file_id, "item_id": item.item_id, "code": "UNTRANSLATED_FALLBACK",
                         "message": "片段没有有效译文，已回退原文"})
        return source, True
    if options["mode"] == "translated" or not source:
        return translated, False
    parts = (source, translated) if options["bilingual_order"] == "source_first" else (translated, source)
    return "\n".join(parts), False


def _collect_cues(cache_file, options, report):
    cues = []
    for item in cache_file.items:
        locator = item.locator or {}
        start, end = locator.get("start_ms"), locator.get("end_ms")
        if locator.get("kind") not in ("audio", "video") or type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise PipelineError("INVALID_AUDIO_TIMESTAMPS", "字幕片段必须提供有效的 audio.start_ms/end_ms",
                                details={"item_id": item.item_id})
        text, fallback = _cue_text(item, options, report["warnings"], cache_file.file_id)
        if fallback:
            report["untranslated_items"] += 1
        if not text:
            report["warnings"].append({"file_id": cache_file.file_id, "item_id": item.item_id,
                                       "code": "EMPTY_SUBTITLE_TEXT", "message": "空文本片段未写出"})
            continue
        cues.append({"start_ms": start, "end_ms": end, "text": text,
                     "speaker": locator.get("speaker_id") or "", "item_id": item.item_id})
    if not cues:
        raise PipelineError("NO_SUBTITLE_TEXT", "音频尚无带时间戳的字幕文本，请先完成转录")
    # Sorting a new list preserves the model's segment order and stable identities.
    cues.sort(key=lambda cue: (cue["start_ms"], cue["end_ms"]))
    if any(cue["start_ms"] < previous["end_ms"] for previous, cue in zip(cues, cues[1:])):
        report["warnings"].append({"file_id": cache_file.file_id, "code": "OVERLAPPING_CUES",
                                   "message": "片段时间存在重叠，已保留原始时间区间"})
    return cues


def _milliseconds(value, separator):
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{milliseconds:03d}"


def _ass_time(value, *, end=False):
    centiseconds = (value + 9) // 10 if end else value // 10
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{fraction:02d}"


def _serialize(cues, format_):
    if format_ in ("srt", "vtt"):
        separator = "," if format_ == "srt" else "."
        entries = [f"{index}\n{_milliseconds(cue['start_ms'], separator)} --> {_milliseconds(cue['end_ms'], separator)}\n"
                   f"{html.escape(cue['text'], quote=False)}\n" for index, cue in enumerate(cues, 1)]
        return ("WEBVTT\n\n" if format_ == "vtt" else "") + "\n".join(entries) + "\n"
    if format_ == "lrc":
        lines = []
        for cue in cues:
            minutes, remainder = divmod(cue["start_ms"], 60_000)
            seconds, milliseconds = divmod(remainder, 1000)
            # LRC has no standard literal timestamp escape or multiline payload.
            text = cue["text"].replace("[", "［").replace("]", "］").replace("\n", " / ")
            lines.append(f"[{minutes:02d}:{seconds:02d}.{milliseconds // 10:02d}]{text}")
        return "\n".join(lines) + "\n"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,30,30,30,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        # ASS has no portable escape for override braces. Full-width punctuation
        # keeps literal user text visible and prevents injected drawing/style tags.
        text = cue["text"].replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N")
        speaker = _clean_text(cue["speaker"]).replace(",", " ").replace("\n", " ")
        lines.append(f"Dialogue: 0,{_ass_time(cue['start_ms'])},{_ass_time(cue['end_ms'], end=True)},Default,{speaker},0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def _destination(root, cache_file, options):
    validate_storage_path(cache_file.storage_path)
    relative = Path(cache_file.storage_path.replace("\\", "/"))
    relative = relative.with_name(relative.stem + options["suffix"] + "." + options["format"])
    if any(_INVALID_NAME.search(part) or _RESERVED_NAME.match(part) or part.endswith((".", " ")) for part in relative.parts):
        raise PipelineError("INVALID_OUTPUT_PATH", "字幕输出包含非法文件名")
    destination = (root / relative).resolve()
    if not destination.is_relative_to(root):
        raise PipelineError("INVALID_OUTPUT_PATH", "字幕输出路径不能越界")
    return destination


def _atomic_write(destination, content, overwrite):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", prefix=".ainiee-subtitles-",
                                suffix=".tmp", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, destination)
        elif os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    except FileExistsError as error:
        raise PipelineError("OUTPUT_EXISTS", f"字幕输出已存在: {destination}", 409) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _plan_targets(project, options):
    """Read-only destination planning shared by preflight and partial writes."""
    root = _directory_path(options["output_dir"] or user_data_root() / "Outputs" / project.project_id)
    candidates, planned, errors, skipped, destinations = [], [], [], [], {}
    source_paths = {os.path.normcase(str(Path(file.source_ref["path"]).expanduser().resolve()))
                    for file in project.files.values() if file.source_ref.get("path")}
    for cache_file in project.files.values():
        if cache_file.media_type not in ("audio", "video"):
            skipped.append({"file_id": cache_file.file_id, "path": cache_file.storage_path, "reason": "not_audio"})
            continue
        try:
            destination = _destination(root, cache_file, options)
            key = os.path.normcase(str(destination))
            if key in source_paths:
                raise PipelineError("INVALID_OUTPUT_PATH", "字幕输出不能覆盖任何模型源文件")
            destinations.setdefault(key, []).append(cache_file)
            candidates.append((cache_file, destination, key))
        except Exception as error:
            errors.append((cache_file, error))
    for cache_file, destination, key in candidates:
        try:
            if len(destinations[key]) > 1:
                raise PipelineError("OUTPUT_COLLISION", f"多个音频指向同一字幕文件: {destination}", 409)
            _directory_path(destination.parent)
            if destination.exists() and not destination.is_file():
                raise PipelineError("INVALID_OUTPUT_PATH", f"字幕输出目标不是文件: {destination}", 422)
            if destination.exists() and not options["overwrite"]:
                raise PipelineError("OUTPUT_EXISTS", f"字幕输出已存在: {destination}", 409)
            planned.append((cache_file, destination))
        except Exception as error:
            errors.append((cache_file, error))
    return root, planned, errors, skipped, source_paths


def _error_record(cache_file, error):
    return {"file_id": cache_file.file_id, "path": cache_file.storage_path,
            "code": getattr(error, "code", "SUBTITLE_WRITE_FAILED"), "message": str(error)}


def validate_subtitle_targets(model, options=None) -> dict:
    """Reject any predictable target failure before paid transcription/translation.

    Empty audio item lists are valid here. The returned normalized options freeze
    the absolute output directory; no source/model/output file is modified.
    Filesystem state can still change later, so write_subtitles repeats the checks.
    """
    options = validate_subtitle_options(options)
    project = parse_model(model)
    root, planned, errors, _, _ = _plan_targets(project, options)
    if errors:
        error = errors[0][1]
        raise PipelineError(getattr(error, "code", "INVALID_OUTPUT_PATH"), str(error),
                            getattr(error, "status_code", 422),
                            {"errors": [_error_record(cache_file, failure) for cache_file, failure in errors]})
    if not planned:
        raise PipelineError("NO_AUDIO_FILES", "模型中没有音频文件")
    return {**options, "output_dir": str(root)}


def write_subtitles(model, options=None) -> dict:
    options = validate_subtitle_options(options)
    project = parse_model(model)
    root, planned, errors, skipped, source_paths = _plan_targets(project, options)
    report = {"errors": [_error_record(cache_file, error) for cache_file, error in errors],
              "warnings": [], "skipped_files": skipped, "written_files": 0,
              "subtitle_items": 0, "untranslated_items": 0}
    outputs = []
    for cache_file, destination in planned:
        try:
            cues = _collect_cues(cache_file, options, report)
            content = _serialize(cues, options["format"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.resolve().is_relative_to(root) or os.path.normcase(str(destination.resolve())) in source_paths:
                raise PipelineError("INVALID_OUTPUT_PATH", "字幕输出路径发生变化或指向源文件")
            _atomic_write(destination, content, options["overwrite"])
            if options["format"] == "lrc":
                report["warnings"].append({"file_id": cache_file.file_id, "code": "LRC_END_TIMES_UNSUPPORTED",
                                           "message": "LRC 只保存开始时间，结束时间保留在中间模型中"})
            outputs.append({"path": str(destination), "format": options["format"], "mode": options["mode"],
                            "file_id": cache_file.file_id, "item_count": len(cues)})
            report["subtitle_items"] += len(cues)
        except Exception as error:
            report["errors"].append(_error_record(cache_file, error))
    if not planned and not report["errors"]:
        report["errors"].append({"code": "NO_AUDIO_FILES", "message": "模型中没有音频文件"})
    report["written_files"] = len(outputs)
    status = "partial" if outputs and report["errors"] else "failed" if report["errors"] or not outputs else "success"
    return {"status": status, "files": outputs, "report": report}
