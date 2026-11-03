"""Render translated image models and persist reproducible JSON checkpoints."""
import copy
import io
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from PIL import ImageColor

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.intermediate import parse_model, validate_storage_path
from Backend.infrastructure.images.render import find_font

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


def _calibrate_file_geometry(pixels, file, context):
    """Align provider boxes locally, retaining text, IDs and custom layouts.

    Every OCR line participates in matching so another block cannot claim its
    detector box. Only untouched, automatically derived item layouts are moved.
    The original provider polygon stays on each corrected line for inspection.
    """
    from Backend.infrastructure.ocr.geometry import calibrate_lines

    def block_polygon(lines):
        if len(lines) == 1:
            return lines[0]["polygon"]
        xs, ys = zip(*(point for line in lines for point in line["polygon"]))
        return [[min(xs), min(ys)], [max(xs), min(ys)],
                [max(xs), max(ys)], [min(xs), max(ys)]]

    def same_polygon(first, second):
        # Schema validation uses tuples for locator points; opaque OCR/layout
        # metadata keeps JSON lists. Their coordinates are still identical.
        return first is not None and second is not None and tuple(map(tuple, first)) == tuple(map(tuple, second))

    lines, entries = [], []
    for item in file.items:
        ocr = item.extra.get("ocr") or {}
        if ocr.get("coordinates_source") == "local_detector":
            continue  # Detection-first OCR already owns these coordinates.
        original = ocr.get("lines")
        if not isinstance(original, list) or not original:
            continue
        polygon = block_polygon(original)
        layout = item.extra.get("layout") or {}
        eligible = (same_polygon(item.locator.get("polygon"), polygon)
                    and same_polygon(layout.get("polygon", polygon), polygon)
                    and item.locator.get("rotation", 0) == (original[0].get("rotation", 0) if len(original) == 1 else 0))
        entries.append((item, len(lines), len(original), eligible))
        lines.extend(original)
    if not lines or context.is_cancelled():
        return []
    calibrated, _ = calibrate_lines(pixels, lines, context=context)
    if context.is_cancelled():
        return []
    updates = []
    for item, offset, count, eligible in entries:
        replacement = calibrated[offset:offset + count]
        original = lines[offset:offset + count]
        if not eligible or all(a["polygon"] == b["polygon"] for a, b in zip(original, replacement)):
            continue
        polygon = block_polygon(replacement)
        extra, locator = copy.deepcopy(item.extra), copy.deepcopy(item.locator)
        extra["ocr"]["lines"] = copy.deepcopy(replacement)
        locator["polygon"] = copy.deepcopy(polygon)
        if count == 1:
            locator["rotation"] = replacement[0].get("rotation", 0)
        layout = extra.get("layout") or {}
        layout["polygon"] = copy.deepcopy(polygon)
        extra["layout"] = layout
        updates.append((item, locator, extra))
    # Calibration is optional: a failed preparation must leave every original
    # item intact so the fallback really does render the provider coordinates.
    for item, locator, extra in updates:
        item.locator, item.extra = locator, extra
    return [item.item_id for item, _, _ in updates]


def write_images(model, options=None, context=None):
    """Compatibility entry point; independently cache repair, render and export."""
    from Backend.application.image_render_service import repair_images, render_images, export_images

    context = context or ExecutionContext()
    values = validate_image_options(options)
    # Preserve the old fail-before-work behavior for output collisions.
    validate_image_targets(model, values)
    internal = {**values, "save_model": False}
    repair = repair_images(model, internal, context)
    if repair["status"] in ("cancelled", "failed") or repair["report"].get("operation_errors"):
        return repair
    rendered = render_images(repair["model"], internal, context)
    if rendered["status"] in ("cancelled", "failed") or rendered["report"].get("operation_errors"):
        return rendered
    result = export_images(rendered["model"], values, context)
    result["report"]["stages"] = {"repair": repair["report"], "render": rendered["report"]}
    return result
