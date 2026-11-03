"""Populate image text in the shared model, preserving completed pages."""
from dataclasses import asdict
import hashlib
import io
import json
import math
from pathlib import Path
import uuid
import warnings

from PIL import Image, ImageOps

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.application.read_service import ensure_media_language_metadata
from Backend.domain.config.ocr_config import resolve_ocr_config
from Backend.domain.models.cache_item import CacheItem, TranslationStatus
from Backend.domain.models.intermediate import parse_model
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.ocr.dashscope import MAX_IMAGE_BYTES, request_ocr, request_ocr_text, validate_polygon
from Backend.infrastructure.ocr.layout import bounds as region_bounds, join_text_lines, order_page, panel_regions, reading_order as order_regions
from Backend.infrastructure.ocr.quality import VALIDATION_VERSION, validate_refinement


def _fingerprint(config):
    values = asdict(config)
    # Credentials, scheduling and the explicit rerun switch do not change OCR
    # results. The service/model and geometry/grouping parameters do.
    for key in ("api_key", "request_timeout", "max_retries", "provider_id", "reocr", "refine_text"):
        values.pop(key)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def _image_source(cache_file):
    ref = cache_file.source_ref
    if not ref.get("verified") or not ref.get("path") or not ref.get("sha256"):
        raise PipelineError("OCR_SOURCE_UNVERIFIED", "OCR 需要已校验的图片引用，请先读取图片", 400)
    path = Path(ref["path"])
    if not path.is_file():
        raise PipelineError("OCR_SOURCE_NOT_FOUND", "图片原文件不存在", 400)
    if file_sha256(path).lower() != ref["sha256"].lower():
        raise PipelineError("OCR_SOURCE_CHANGED", "图片原文件已变化，请重新读取", 409)
    width, height = (cache_file.media_metadata.get(key) for key in ("width", "height"))
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise PipelineError("OCR_INVALID_IMAGE", "中间模型缺少有效图片尺寸", 400)
    return path, width, height


def _prepare_image(path, width, height, max_pixels):
    """Normalize EXIF without changing the original; send a bounded image."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as raw:
                if raw.width * raw.height > 100_000_000 or getattr(raw, "n_frames", 1) != 1:
                    raise PipelineError("OCR_INVALID_IMAGE", "OCR 仅支持不超过一亿像素的静态图片", 400)
                normalized = ImageOps.exif_transpose(raw)
                normalized.load()
                if normalized.size != (width, height):
                    raise PipelineError("OCR_IMAGE_DIMENSIONS_CHANGED", "图片规范尺寸与模型不一致，请重新读取", 409)
                if "A" in normalized.getbands() or "transparency" in normalized.info:
                    rgba = normalized.convert("RGBA")
                    image = Image.new("RGB", rgba.size, "white")
                    image.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    image = normalized.convert("RGB")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError):
        raise PipelineError("OCR_INVALID_IMAGE", "无法解码图片或图片过大", 400) from None
    ratio = min(1.0, math.sqrt(max_pixels / (width * height)))
    if width * height < 3136:
        ratio = math.sqrt(3136 / (width * height))
    upload = image.resize((max(1, math.floor(width * ratio)), max(1, math.floor(height * ratio))), Image.Resampling.LANCZOS)
    for attempt in range(12):
        buffer = io.BytesIO()
        upload.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()
        if len(data) >= MAX_IMAGE_BYTES:
            buffer = io.BytesIO()
            upload.save(buffer, format="JPEG", quality=94, subsampling=0)
            data = buffer.getvalue()
        if len(data) < MAX_IMAGE_BYTES:
            return image, data, upload.size
        upload = upload.resize((max(1, int(upload.width * .8)), max(1, int(upload.height * .8))), Image.Resampling.LANCZOS)
    raise PipelineError("OCR_IMAGE_TOO_LARGE", "图片压缩后仍超过 OCR 上传上限", 400)


def _bounds(line):
    xs, ys = zip(*line["polygon"])
    return min(xs), min(ys), max(xs), max(ys)


def _ordered(lines, reading_order):
    # Rows are clustered by vertical overlap instead of sorting each pixel y
    # independently, which could reverse neighbouring text at slightly different
    # heights. Vertical columns use right-to-left manga order.
    vertical = reading_order == "manga_rtl" or (reading_order == "auto" and sum(x["direction"] == "vertical" for x in lines) > len(lines) / 2)
    if vertical:
        return order_regions(lines, rtl=True)
    remaining = sorted(lines, key=lambda line: (_bounds(line)[1], _bounds(line)[0]))
    result = []
    while remaining:
        first = remaining.pop(0)
        a = _bounds(first)
        row, rest = [first], []
        for line in remaining:
            b = _bounds(line)
            overlap = min(a[3], b[3]) - max(a[1], b[1])
            (row if overlap >= .5 * min(a[3] - a[1], b[3] - b[1]) else rest).append(line)
        result.extend(sorted(row, key=lambda line: _bounds(line)[0]))
        remaining = rest
    return result


def _bubble_components(image):
    import cv2
    import numpy as np

    rgb = np.asarray(image)
    bright = (rgb.min(axis=2) >= 225).astype("uint8")
    count, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    height, width = labels.shape
    frames = [region_bounds(panel) for panel in panel_regions(image)]
    valid = set()
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        # An empty panel interior is also a closed white component. It is not
        # evidence that two distant captions belong to the same speech bubble.
        is_panel_background = any(
            max(0, min(x + w, x1) - max(x, x0)) * max(0, min(y + h, y1) - max(y, y0))
            >= .65 * (x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in frames)
        if (x > 0 and y > 0 and x + w < width and y + h < height and area >= 64
                and area / (w * h) >= .6 and not is_panel_background):
            valid.add(label)
    return labels, stats, valid


def _line_component(line, components):
    import cv2
    import numpy as np
    labels, stats, valid = components
    height, width = labels.shape
    x0, y0, x1, y1 = _bounds(line)
    roi = labels[max(0, int(y0)):min(height, math.ceil(y1)), max(0, int(x0)):min(width, math.ceil(x1))]
    ids, counts = np.unique(roi, return_counts=True)
    candidates = [(int(n), int(i)) for i, n in zip(ids, counts) if i in valid]
    selected = max(candidates, default=None)
    if selected and selected[0] >= .5 * roi.size and stats[selected[1], cv2.CC_STAT_AREA] > (x1-x0)*(y1-y0)*1.2:
        return selected[1]
    return None


def _group_lines(lines, image, enabled, reading_order):
    """Only group lines inside the same closed, bright connected component.

    This intentionally leaves document/page backgrounds and ambiguous bubbles
    ungrouped. Nearby boxes alone are insufficient evidence for a shared bubble.
    """
    if not enabled or len(lines) < 2:
        return _order_groups([[line] for line in lines], image, reading_order), []
    components = _bubble_components(image)
    grouped, singles = {}, []
    for line in lines:
        selected = _line_component(line, components)
        if selected is not None:
            grouped.setdefault(selected, []).append(line)
        else:
            singles.append([line])
    direction_groups = []
    for component_lines in grouped.values():
        weights = {direction: sum(len(line["text"]) for line in component_lines if line["direction"] == direction)
                   for direction in ("horizontal", "vertical")}
        dominant = max(weights, key=weights.get) if len(set(weights.values())) > 1 else None
        by_direction = {}
        for line in component_lines:
            x0, y0, x1, y1 = _bounds(line)
            # A single square glyph has no geometric writing direction. Only
            # inside a proven bubble may surrounding multi-character lines
            # supply that direction; preserve how it was inferred.
            if (dominant and line["direction"] != dominant and len(line["text"].strip()) <= 2
                    and .55 <= (x1 - x0) / (y1 - y0) <= 1.8):
                line = {**line, "direction": dominant, "detected_direction": line["direction"], "direction_basis": "bubble_context"}
            by_direction.setdefault(line["direction"], []).append(line)
        direction_groups.extend(by_direction.values())
    groups = [_ordered(group, reading_order) for group in direction_groups] + singles
    groups = _order_groups(groups, image, reading_order)
    notice = [{"code": "OCR_GROUPING_CONSERVATIVE", "message": "仅合并明确处于同一封闭亮背景中的文字行，其余保留为独立区域"}]
    return groups, notice


def _order_groups(groups, image, reading_order):
    blocks = [_block(group) for group in groups]
    rtl = reading_order == "manga_rtl" or (reading_order == "auto" and sum(b["direction"] == "vertical" for b in blocks) > len(blocks) / 2)
    ordered = order_page(blocks, image, rtl=rtl)
    by_id = {id(group): group for group in groups}
    return [by_id[block["group_identity"]] for block in ordered]


def _block(group):
    if len(group) == 1:
        polygon = group[0]["polygon"]
    else:
        points = [p for line in group for p in line["polygon"]]
        xs, ys = zip(*points)
        polygon = [[min(xs), min(ys)], [max(xs), min(ys)], [max(xs), max(ys)], [min(xs), max(ys)]]
    return {"polygon": polygon, "direction": group[0]["direction"], "group_identity": id(group)}


def _refine_crop(item, cache_file, image, components, config):
    lines = item.extra.get("ocr", {}).get("lines")
    if not isinstance(lines, list) or not lines:
        return None, "missing_original_lines"
    validate_polygon(item.locator.get("polygon"), image.width, image.height)
    for line in lines:
        validate_polygon(line.get("polygon"), image.width, image.height)
    labels = {_line_component(line, components) for line in lines}
    if len(labels) != 1 or None in labels:
        return None, "not_closed_bubble"
    x0, y0, x1, y1 = _bounds(_block(lines))
    box = (max(0, math.floor(x0) - 4), max(0, math.floor(y0) - 4),
           min(image.width, math.ceil(x1) + 4), min(image.height, math.ceil(y1) + 4))
    for other in cache_file.items:
        if other is item:
            continue
        for line in other.extra.get("ocr", {}).get("lines", []):
            a, b, c, d = _bounds(line)
            overlap = max(0, min(box[2], c) - max(box[0], a)) * max(0, min(box[3], d) - max(box[1], b))
            if overlap > max(1, .05 * (c - a) * (d - b)):
                return None, "overlapping_other_block"
    crop = image.crop(box)
    scale = min(2, math.sqrt(config.max_pixels / (crop.width * crop.height)))
    crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
    for _ in range(12):
        buffer = io.BytesIO()
        crop.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()
        if len(data) < MAX_IMAGE_BYTES:
            identity = {"version": 1, "source_sha256": cache_file.source_ref["sha256"].lower(),
                        "polygon": item.locator.get("polygon"), "lines": [{"text": line["text"], "polygon": line["polygon"]} for line in lines],
                        "crop": box, "model": config.model, "api_url": config.api_url, "api_format": config.api_format,
                        "max_tokens": config.max_tokens, "max_pixels": config.max_pixels, "task": "multi_lan"}
            fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            return (data, crop.size, box, fingerprint), None
        crop = crop.resize((max(1, int(crop.width * .8)), max(1, int(crop.height * .8))), Image.Resampling.LANCZOS)
    raise PipelineError("OCR_IMAGE_TOO_LARGE", "气泡复核图片超过上传上限", 400)


def _notify_batch(context, items, path, report, operation):
    if context.on_batch_complete:
        try:
            context.on_batch_complete(items, path, {"operation": operation, "usage": dict(report["usage"])})
        except Exception:
            report["operation_errors"].append({"code": "OCR_CALLBACK_FAILED", "message": "OCR 检查点回调失败"})
            context.cancel()


def _refine_file(cache_file, path, image, config, context, report, project):
    """Commit every paid bubble independently; never roll back the main OCR."""
    counts = report["refinement"]
    components = _bubble_components(image)
    changed = False
    for index, item in enumerate(cache_file.items):
        if context.is_cancelled():
            break
        identity = {"file_id": cache_file.file_id, "item_id": item.item_id, "path": cache_file.storage_path}
        ocr = item.extra.setdefault("ocr", {})
        previous = ocr.get("refinement", {})
        previous = previous if isinstance(previous, dict) else {}
        original = previous.get("original_text", item.source_text)
        metadata = {"status": "failed", "original_text": original, "input_text": item.source_text,
                    "provider_id": config.provider_id, "model": config.model, "task": "multi_lan"}
        requested, accounted, stop_file = False, False, False
        try:
            prepared, reason = _refine_crop(item, cache_file, image, components, config)
            if prepared is None:
                counts["ineligible"] += 1
                counts["items"].append({**identity, "status": "ineligible", "reason": reason})
                if reason == "overlapping_other_block":
                    report["warnings"].append({**identity, "code": "OCR_REFINE_SKIPPED", "message": "气泡裁切与其他文字块相交，已跳过原文复核"})
                continue
            data, size, box, fingerprint = prepared
            counts["eligible"] += 1
            validation_fingerprint = hashlib.sha256(f"{fingerprint}:validation:{VALIDATION_VERSION}".encode()).hexdigest()
            same_response = previous.get("fingerprint") == fingerprint
            validated = same_response and previous.get("validation_fingerprint") == validation_fingerprint
            if validated and previous.get("status") in ("complete", "rejected"):
                counts["skipped"] += 1
                if previous.get("status") == "rejected":
                    counts["rejected"] += 1
                    reason = previous.get("validation", {}).get("reason", "unreliable_text")
                    counts["items"].append({**identity, "status": "rejected", "cached": True, "reason": reason})
                    report["warnings"].append({**identity, "code": "OCR_REFINE_REJECTED", "message": "气泡复核结果未通过完整性和列序校验，保留原文", "reason": reason})
                else:
                    counts["items"].append({**identity, "status": "skipped"})
                continue
            metadata.update({"fingerprint": fingerprint, "validation_fingerprint": validation_fingerprint,
                             "crop": list(box), "source_sha256": cache_file.source_ref["sha256"]})
            if context.is_cancelled():
                break
            if file_sha256(path).lower() != cache_file.source_ref["sha256"].lower():
                raise PipelineError("OCR_SOURCE_CHANGED", "气泡复核前图片原文件发生变化，请重新读取", 409)
            old_provider_text = previous.get("provider_text", previous.get("result_text"))
            reused = same_response and previous.get("status") in ("complete", "rejected") and isinstance(old_provider_text, str)
            if reused:
                result = {"text": old_provider_text, "usage": previous.get("usage", {}),
                          "request_id": previous.get("request_id", ""), "attempts": previous.get("attempts", 0)}
                metadata["input_text"] = previous.get("input_text", original)
                metadata["reused_response"] = True
                counts["revalidated"] += 1
            else:
                requested = True
                result = request_ocr_text(data, image_width=size[0], image_height=size[1], config=config.to_request_config(), context=context)
                report["usage"]["requests"] += result.get("attempts", 1)
                accounted = True
                for key in ("input_tokens", "output_tokens", "total_tokens"):
                    report["usage"][key] += result.get("usage", {}).get(key, 0)
            metadata.update({"provider_text": result["text"], "result_text": result["text"], "usage": result.get("usage", {}),
                             "request_id": result.get("request_id", ""), "attempts": result.get("attempts", 1)})
            if file_sha256(path).lower() != cache_file.source_ref["sha256"].lower():
                raise PipelineError("OCR_SOURCE_CHANGED", "气泡复核期间图片原文件发生变化，请重新读取", 409)
            checked = validate_refinement(ocr["lines"], result["text"])
            metadata.update(validation=checked["validation"], result_text=checked["text"])
            accepted = checked["validation"]["status"] == "accepted"
            replacement = join_text_lines([{"text": line} for line in checked["text"].splitlines()]) if accepted else item.source_text
            if accepted:
                metadata["result_text"] = replacement
            if not accepted and reused and item.source_text == previous.get("result_text"):
                replacement = previous.get("input_text", original)
                metadata["restored_legacy_source"] = True
            if item.source_text != replacement:
                item.source_text = replacement
                item.translated_text = ""
                item.translation_status = TranslationStatus.UNTRANSLATED
                item.model = ""
                item.text_to_detect = None
                item.lang_code = None
                counts["changed"] += 1
                changed = True
                project.stats_data = None
                cache_file.extra.pop("image_pipeline", None)
            metadata["status"] = "complete" if accepted else "rejected"
            if accepted:
                counts["succeeded"] += 1
                counts["items"].append({**identity, "status": "success", "request_id": metadata["request_id"]})
            else:
                counts["rejected"] += 1
                reason = checked["validation"]["reason"]
                counts["items"].append({**identity, "status": "rejected", "reason": reason, "request_id": metadata["request_id"]})
                report["warnings"].append({**identity, "code": "OCR_REFINE_REJECTED", "message": "气泡复核结果未通过完整性和列序校验，保留原文", "reason": reason})
        except PipelineError as error:
            if requested and not accounted:
                report["usage"]["requests"] += (error.details or {}).get("attempts", 0)
            if error.code == "OCR_CANCELLED":
                context.cancel()
                break
            metadata.update({"error": {"code": error.code, "message": error.message}, "attempts": metadata.get("attempts", (error.details or {}).get("attempts", 0))})
            stop_file = error.code == "OCR_SOURCE_CHANGED"
            counts["failed"] += 1
            counts["items"].append({**identity, "status": "failed", **metadata["error"]})
        except Exception:
            metadata["error"] = {"code": "OCR_REFINE_FAILED", "message": "气泡原文复核失败"}
            counts["failed"] += 1
            counts["items"].append({**identity, "status": "failed", **metadata["error"]})
        ocr["refinement"] = metadata
        _notify_batch(context, [item], cache_file.storage_path, report, "ocr_refine")
        if stop_file:
            break
        if context.on_progress and not context.is_cancelled():
            try:
                context.on_progress({"operation": "ocr_refine", **identity, "current": index + 1,
                                     "total": len(cache_file.items), "succeeded": counts["succeeded"], "failed": counts["failed"]})
            except Exception:
                report["operation_errors"].append({"code": "OCR_CALLBACK_FAILED", "message": "OCR 复核进度回调失败"})
                context.cancel()
    if changed:
        cache_file.language_stats = []
        cache_file.lc_language_stats = []
    return changed


def ocr_model(model, config=None, context=None):
    project = parse_model(model)
    resolved = resolve_ocr_config(config)
    context = context or ExecutionContext()
    if resolved.recognition_mode == "regions":
        from Backend.application.region_ocr_service import ocr_regions_model
        return ocr_regions_model(project, resolved, context)
    files = [f for f in project.files.values() if f.media_type == "image"]
    if not files:
        raise PipelineError("OCR_NO_IMAGES", "中间模型中没有图片", 400)
    fingerprint = _fingerprint(resolved)
    next_index = max((x.text_index for x in project.items_iter()), default=-1) + 1
    report = {"total": len(files), "succeeded": 0, "skipped": 0, "failed": 0, "cancelled": False,
              "cancelled_files": 0, "line_count": 0, "block_count": 0, "files": [], "errors": [],
              "warnings": [], "operation_errors": [], "usage": {"requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
    report["refinement"] = {"enabled": resolved.refine_text, "eligible": 0, "succeeded": 0, "skipped": 0,
                            "ineligible": 0, "failed": 0, "rejected": 0, "revalidated": 0, "changed": 0, "items": []}
    changed = False
    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception:
            report["operation_errors"].append({"code": "OCR_CALLBACK_FAILED", "message": "OCR 模型回调失败"})
            context.cancel()
    for ordinal, cache_file in enumerate(files):
        if context.is_cancelled():
            report["cancelled_files"] = len(files) - ordinal
            break
        identity = {"file_id": cache_file.file_id, "path": cache_file.storage_path}
        request_started = False
        image = None
        try:
            path, width, height = _image_source(cache_file)
            previous = cache_file.extra.get("ocr", {})
            if not resolved.reocr and isinstance(previous, dict) and previous.get("status") == "complete" and (
                    previous.get("source_sha256") == cache_file.source_ref["sha256"] and previous.get("config_fingerprint") == fingerprint):
                report["skipped"] += 1
                report["files"].append({**identity, "status": "skipped", "block_count": len(cache_file.items)})
            else:
                image, data, upload_size = _prepare_image(path, width, height, resolved.max_pixels)
                if context.is_cancelled():
                    report["cancelled_files"] = len(files) - ordinal
                    break
                request_started = True
                result = request_ocr(data, image_width=upload_size[0], image_height=upload_size[1],
                                     config=resolved.to_request_config(), context=context)
                report["usage"]["requests"] += result.get("attempts", 1)
                request_started = False
                for key in ("input_tokens", "output_tokens", "total_tokens"):
                    report["usage"][key] += result.get("usage", {}).get(key, 0)
                if file_sha256(path).lower() != cache_file.source_ref["sha256"].lower():
                    raise PipelineError("OCR_SOURCE_CHANGED", "OCR 期间图片原文件发生变化，请重新读取", 409)
                lines = []
                for line in result["lines"]:
                    polygon = [[x * width / upload_size[0], y * height / upload_size[1]] for x, y in line["polygon"]]
                    lines.append({**line, "polygon": validate_polygon(polygon, width, height)})
                groups, notices = _group_lines(lines, image, resolved.group_lines, resolved.reading_order)
                items, old_indices = [], [x.text_index for x in cache_file.items]
                for index, group in enumerate(groups):
                    block = _block(group)
                    text_index = old_indices[index] if index < len(old_indices) else next_index
                    if index >= len(old_indices):
                        next_index += 1
                    geometry = json.dumps(block["polygon"], separators=(",", ":"))
                    items.append(CacheItem(
                        item_id=uuid.uuid5(uuid.NAMESPACE_URL, f"ainiee:ocr:{cache_file.file_id}:{index}:{geometry}").hex,
                        text_index=text_index, source_text=join_text_lines(group),
                        translated_text="", translation_status=TranslationStatus.UNTRANSLATED,
                        locator={"kind": "image", "index": index, "page_index": 0,
                                 "polygon": block["polygon"], "coordinate_space": "pixel",
                                 "rotation": group[0].get("rotation", 0) if len(group) == 1 else 0},
                        extra={"ocr": {"provider_id": resolved.provider_id, "model": resolved.model, "lines": group},
                               "layout": {"polygon": block["polygon"], "direction": block["direction"], "reading_order": index}},
                    ))
                # The whole page is valid before any old text/translation is replaced.
                cache_file.items = items
                cache_file.__dict__.pop("items_index_dict", None)
                cache_file.extra["ocr"] = {"status": "complete", "source_sha256": cache_file.source_ref["sha256"],
                                           "config_fingerprint": fingerprint, "provider_id": resolved.provider_id,
                                           "model": resolved.model, "line_count": len(lines), "block_count": len(items),
                                           "uploaded_width": upload_size[0], "uploaded_height": upload_size[1]}
                cache_file.extra.pop("image_pipeline", None)
                cache_file.language_stats = []
                cache_file.lc_language_stats = []
                changed = True
                project.stats_data = None
                report["succeeded"] += 1
                report["line_count"] += len(lines)
                report["block_count"] += len(items)
                report["files"].append({**identity, "status": "success", "line_count": len(lines), "block_count": len(items),
                                        "request_id": result.get("request_id", ""), "attempts": result.get("attempts", 1)})
                report["warnings"].extend({**identity, **warning} for warning in result.get("warnings", []) + notices)
                _notify_batch(context, items, cache_file.storage_path, report, "ocr")
            if resolved.refine_text and cache_file.items and not context.is_cancelled():
                if image is None:
                    image, _, _ = _prepare_image(path, width, height, resolved.max_pixels)
                changed |= _refine_file(cache_file, path, image, resolved, context, report, project)
        except PipelineError as error:
            if request_started:
                report["usage"]["requests"] += (error.details or {}).get("attempts", 0)
            if error.code == "OCR_CANCELLED":
                context.cancel()
                report["cancelled_files"] = len(files) - ordinal
                break
            entry = {**identity, "code": error.code, "message": error.message}
            report["errors"].append(entry)
            report["files"].append({**entry, "status": "failed"})
            report["failed"] += 1
        except Exception:
            entry = {**identity, "code": "OCR_INTERNAL_ERROR", "message": "图片 OCR 处理失败，请检查图片及接口配置"}
            report["errors"].append(entry)
            report["files"].append({**entry, "status": "failed"})
            report["failed"] += 1
        if context.on_progress:
            try:
                context.on_progress({"operation": "ocr", "current": ordinal + 1, "total": len(files),
                                     "succeeded": report["succeeded"], "failed": report["failed"], "skipped": report["skipped"]})
            except Exception:
                report["operation_errors"].append({"code": "OCR_CALLBACK_FAILED", "message": "OCR 进度回调失败"})
                context.cancel()
                report["cancelled_files"] = len(files) - ordinal - 1
                break
    if not context.is_cancelled():
        try:
            # Detect the final source text, including reused OCR and refinements.
            # Returning the model lets callers save paid OCR results even if
            # local language detection fails and blocks the next stage.
            ensure_media_language_metadata(project, media_types=("image",))
        except PipelineError as error:
            report["operation_errors"].append({"code": error.code, "message": error.message})
    if changed:
        project.stats_data = None
    report["cancelled"] = context.is_cancelled() and not report["operation_errors"]
    if report["operation_errors"]:
        status = "partial" if report["succeeded"] or report["skipped"] else "failed"
    elif report["cancelled"]:
        status = "cancelled"
    elif report["failed"]:
        status = "partial" if report["succeeded"] or report["skipped"] else "failed"
    elif report["refinement"]["failed"] or report["refinement"]["rejected"]:
        status = "partial"
    else:
        status = "success"
    return {"status": status, "model": project, "report": report}
