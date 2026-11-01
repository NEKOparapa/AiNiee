"""Render translated image models and persist reproducible JSON checkpoints."""
import io
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from PIL import ImageColor

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.log_system import redact
from Backend.core.protocol import to_wire
from Backend.domain.models.intermediate import parse_model, validate_storage_path
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.images.render import find_font, render_image
from Backend.infrastructure.images.source import verified_image

_OPTIONS = {"output_dir", "format", "suffix", "overwrite", "font_path", "font_size", "min_font_size",
            "max_font_size", "font_color", "text_direction", "padding", "erase_mode", "save_model", "debug_overlay"}
_INVALID = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def _directory(value):
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip() or "\x00" in str(value):
        raise PipelineError("INVALID_OUTPUT_PATH", "output_dir 必须为非空目录路径", 422)
    try:
        path = Path(value).expanduser().resolve()
        if any(_INVALID.search(p) or _RESERVED.match(p) or p.endswith((".", " "))
               for p in path.parts if p != path.anchor):
            raise ValueError("invalid directory")
        for ancestor in (path, *path.parents):
            if ancestor.exists():
                if not ancestor.is_dir():
                    raise ValueError("not a directory")
                break
        return path
    except (OSError, ValueError, RuntimeError) as error:
        raise PipelineError("INVALID_OUTPUT_PATH", "output_dir 不是有效目录路径", 422) from error


def validate_image_options(options=None):
    if not isinstance(options, dict):
        raise PipelineError("VALIDATION_ERROR", "图片输出 options 必须为对象", 422)
    if set(options) - _OPTIONS:
        raise PipelineError("VALIDATION_ERROR", "不支持的图片输出参数", 422,
                            {"fields": sorted(set(options) - _OPTIONS)})
    values = {"output_dir": None, "format": "png", "suffix": "_translated", "overwrite": False,
              "font_path": None, "font_size": None, "min_font_size": 12, "max_font_size": 48,
              "font_color": None, "text_direction": "auto", "padding": 2, "erase_mode": "auto",
              "save_model": True, "debug_overlay": False, **options}
    values["output_dir"] = str(_directory(values["output_dir"]))
    for key, allowed in (("format", ("png", "jpeg", "webp")),
                         ("text_direction", ("auto", "horizontal", "vertical")),
                         ("erase_mode", ("auto", "solid", "inpaint"))):
        if values[key] not in allowed:
            raise PipelineError("VALIDATION_ERROR", f"图片 {key} 无效", 422)
    for key in ("overwrite", "save_model", "debug_overlay"):
        if type(values[key]) is not bool:
            raise PipelineError("VALIDATION_ERROR", f"{key} 必须是布尔值", 422)
    for key in ("min_font_size", "max_font_size", "font_size", "padding"):
        value = values[key]
        if key == "font_size" and value is None:
            continue
        low, high = (0, 100) if key == "padding" else (6, 512)
        if type(value) is not int or not low <= value <= high:
            raise PipelineError("VALIDATION_ERROR", f"{key} 必须是 {low} 至 {high} 的整数", 422)
    if values["min_font_size"] > values["max_font_size"]:
        raise PipelineError("VALIDATION_ERROR", "最小字号不能大于最大字号", 422)
    if values["font_size"] is not None and not values["min_font_size"] <= values["font_size"] <= values["max_font_size"]:
        raise PipelineError("VALIDATION_ERROR", "指定字号必须位于最小与最大字号之间", 422)
    if values["font_color"] is not None:
        if not isinstance(values["font_color"], str):
            raise PipelineError("VALIDATION_ERROR", "font_color 必须是颜色字符串", 422)
        try:
            ImageColor.getcolor(values["font_color"], "RGBA")
        except (ValueError, TypeError) as error:
            raise PipelineError("VALIDATION_ERROR", "font_color 不是有效颜色", 422) from error
    if values["font_path"] is not None:
        if not isinstance(values["font_path"], str) or not values["font_path"].strip():
            raise PipelineError("VALIDATION_ERROR", "font_path 必须是字体文件路径", 422)
        values["font_path"] = str(find_font(values["font_path"]))
    suffix = values["suffix"]
    if not isinstance(suffix, str) or _INVALID.search(suffix) or "/" in suffix or "\\" in suffix:
        raise PipelineError("INVALID_OUTPUT_PATH", "图片输出后缀不能包含路径分隔符或非法字符", 422)
    return values


def _target(root, relative):
    validate_storage_path(relative)
    parts = Path(relative.replace("\\", "/")).parts
    if any(_INVALID.search(p) or _RESERVED.match(p) or p.endswith((".", " ")) for p in parts):
        raise PipelineError("INVALID_OUTPUT_PATH", "图片输出文件名无效", 422)
    destination = (root / Path(*parts)).resolve()
    if not destination.is_relative_to(root):
        raise PipelineError("INVALID_OUTPUT_PATH", "图片输出路径不能越界", 422)
    return destination


def _plan(project, options):
    root = _directory(options["output_dir"])
    sources = {os.path.normcase(str(Path(f.source_ref["path"]).resolve()))
               for f in project.files.values() if f.source_ref.get("path")}
    plans, targets = [], []
    for file in project.files.values():
        if file.media_type != "image":
            continue
        relative = Path(file.storage_path.replace("\\", "/"))
        output = relative.with_name(relative.stem + options["suffix"] + "." + options["format"]).as_posix()
        asset = f"_image_assets/{project.project_id}/{file.file_id}"
        destinations = {"image": _target(root, output), "mask": _target(root, asset + "_mask.png")}
        if options["debug_overlay"]:
            destinations["debug"] = _target(root, asset + "_debug.png")
        plans.append((file, destinations))
        targets.extend(destinations.values())
    model_path = _target(root, f"{project.project_id}_image_model.json") if options["save_model"] else None
    if model_path:
        targets.append(model_path)
    if not plans:
        raise PipelineError("NO_IMAGE_FILES", "模型中没有图片文件")
    seen = set()
    for target in targets:
        key = os.path.normcase(str(target))
        if key in sources:
            raise PipelineError("INVALID_OUTPUT_PATH", "图片输出不能覆盖任何模型源文件", 422)
        if key in seen:
            raise PipelineError("OUTPUT_COLLISION", "多个产物指向同一输出文件", 409)
        seen.add(key)
        _directory(target.parent)
        if target.exists() and (not target.is_file() or not options["overwrite"]):
            raise PipelineError("OUTPUT_EXISTS", f"输出目标已存在: {target}", 409)
    return root, plans, model_path, sources


def validate_image_targets(model, options=None):
    values = validate_image_options(options)
    project = parse_model(model)
    root, _, _, _ = _plan(project, values)
    # Resolve a font before a paid operation even if OCR has not produced items yet.
    values["font_path"] = str(find_font(values["font_path"]))
    return {**values, "output_dir": str(root)}


def _atomic_bytes(destination, data, overwrite, root, sources):
    destination.parent.mkdir(parents=True, exist_ok=True)
    resolved = destination.resolve()
    if not resolved.is_relative_to(root) or os.path.normcase(str(resolved)) in sources:
        raise PipelineError("INVALID_OUTPUT_PATH", "输出路径发生变化或指向源文件", 422)
    temporary = None
    try:
        with NamedTemporaryFile("wb", prefix=".ainiee-image-", suffix=".tmp", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, destination)
        elif os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    except FileExistsError as error:
        raise PipelineError("OUTPUT_EXISTS", f"输出目标已存在: {destination}", 409) from error
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def _image_bytes(pixels, format_):
    stream = io.BytesIO()
    if format_ == "jpeg" and pixels.mode == "RGBA":
        from PIL import Image
        background = Image.new("RGB", pixels.size, "white")
        background.paste(pixels, mask=pixels.getchannel("A"))
        pixels = background
    kwargs = {"quality": 95} if format_ == "jpeg" else {"lossless": True} if format_ == "webp" else {}
    pixels.save(stream, format=format_.upper(), **kwargs)
    return stream.getvalue()


def write_images(model, options=None, context=None):
    values = validate_image_options(options)
    project = parse_model(model)
    context = context or ExecutionContext()
    root, plans, model_path, sources = _plan(project, values)
    report = {"errors": [], "warnings": [], "written_files": 0, "rendered_items": 0,
              "skipped_items": 0, "preserved_items": 0, "cancelled": False,
              "skipped_files": [{"file_id": f.file_id, "path": f.storage_path, "reason": "not_image"}
                                for f in project.files.values() if f.media_type != "image"]}
    outputs = []
    for file, destinations in plans:
        if context.is_cancelled():
            break
        try:
            pixels, source = verified_image(file)
            if not file.items and (file.extra.get("ocr") or {}).get("status") != "complete":
                raise PipelineError("IMAGE_OCR_REQUIRED", "图片尚未完成 OCR")
            rendered, mask, debug, result = render_image(pixels, file, values, context)
            report["warnings"].extend({"file_id": file.file_id, **w} for w in result["warnings"])
            report["skipped_items"] += result["skipped_items"]
            if result["cancelled"]:
                break
            if file_sha256(source) != file.source_ref.get("sha256"):
                raise PipelineError("SOURCE_CHANGED", "渲染期间图片源文件发生变化")
            if values["format"] == "jpeg" and rendered.mode == "RGBA":
                report["warnings"].append({"file_id": file.file_id, "code": "JPEG_ALPHA_FLATTENED", "message": "JPEG 不支持透明度，已合成白色背景"})
            artifacts = {}
            images = {"mask": (mask, "png"), "image": (rendered, values["format"])}
            if values["debug_overlay"]:
                images["debug"] = (debug, "png")
            for kind, (image, format_) in images.items():
                destination = destinations[kind]
                _atomic_bytes(destination, _image_bytes(image, format_), values["overwrite"], root, sources)
                artifacts[kind] = {"path": str(destination), "sha256": file_sha256(destination)}
            state = file.extra.setdefault("image_pipeline", {})
            state["render"] = {"status": "partial" if result["skipped_items"] else "complete",
                               "source_sha256": file.source_ref["sha256"], "artifacts": artifacts,
                               "placements": result["placements"], "preserved": result["preserved"], "options": dict(values)}
            outputs.append({"file_id": file.file_id, "path": str(destinations["image"]),
                            "format": values["format"], "rendered_items": result["rendered_items"],
                            "preserved_items": result["preserved_items"],
                            "skipped_items": result["skipped_items"], "artifacts": artifacts})
            report["rendered_items"] += result["rendered_items"]
            report["preserved_items"] += result["preserved_items"]
            if context.on_progress:
                context.on_progress({"phase": "render", "file_id": file.file_id,
                                     "completed_files": len(outputs), "total_files": len(plans)})
        except Exception as error:
            report["errors"].append({"file_id": file.file_id, "path": file.storage_path,
                                     "code": getattr(error, "code", "IMAGE_WRITE_FAILED"), "message": redact(str(error))})
    report["cancelled"] = context.is_cancelled()
    report["written_files"] = len(outputs)
    status = "cancelled" if report["cancelled"] else "partial" if outputs and (report["errors"] or report["skipped_items"]) else "failed" if report["errors"] or not outputs else "success"
    saved_model_path = None
    if model_path:
        try:
            project.extra["image_export"] = {"model_path": str(model_path), "status": status}
            content = json.dumps(to_wire(project), ensure_ascii=False, indent=2).encode("utf-8")
            _atomic_bytes(model_path, content, values["overwrite"], root, sources)
            saved_model_path = str(model_path)
        except Exception as error:
            report["errors"].append({"code": getattr(error, "code", "IMAGE_MODEL_SAVE_FAILED"), "message": redact(str(error))})
            if status != "cancelled":
                status = "partial" if outputs else "failed"
    return {"status": status, "model": project, "files": outputs, "model_path": saved_model_path, "report": report}
