"""Reusable local image detection, independent of OCR credentials and billing."""
import copy
import hashlib
import json
import uuid

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.application.image_workflow import record_image_stage
from Backend.core.log_system import redact
from Backend.domain.models.cache_item import CacheItem, TranslationStatus
from Backend.domain.models.intermediate import parse_model
from Backend.infrastructure.images.source import verified_image
from Backend.infrastructure.ocr.dashscope import _line, validate_polygon
from Backend.infrastructure.ocr.regions import MAX_REGIONS, REGIONS_VERSION


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def store_detection(file, image_size, regions):
    """Store provider-independent geometry; reading order is not cache identity."""
    if not isinstance(regions, list) or len(regions) > MAX_REGIONS:
        raise PipelineError("IMAGE_DETECTION_INVALID", "图片检测区域数量无效", 409)
    lines, seen = [], set()
    for region in regions:
        if not isinstance(region, dict):
            raise PipelineError("IMAGE_DETECTION_INVALID", "图片检测区域格式无效", 409)
        polygon = validate_polygon(region.get("polygon"), *image_size)
        identity = _digest({"version": REGIONS_VERSION, "polygon": polygon})
        if identity in seen:
            raise PipelineError("IMAGE_DETECTION_INVALID", "图片检测区域重复", 409)
        seen.add(identity)
        geometry = _line({"text": "?", "polygon": polygon}, *image_size)
        lines.append({**copy.deepcopy(region), **geometry, "text": "", "region_id": identity,
                      "coordinates_source": "local_detector"})
    manifest = {"status": "complete", "version": REGIONS_VERSION,
                "source_sha256": file.source_ref["sha256"], "image_size": list(image_size),
                "regions": lines, "region_count": len(lines), "empty": not lines}
    manifest["fingerprint"] = _digest({key: manifest[key] for key in ("version", "source_sha256", "image_size")}
                                      | {"regions": sorted(seen)})
    file.extra["text_detection"] = manifest
    return manifest


def ensure_detection(file, image, context=None):
    """Reuse read-time detection; only old projects with no record detect lazily."""
    previous = file.extra.get("text_detection")
    if previous is None:
        return run_detection(file, image, context), False
    if not isinstance(previous, dict) or previous.get("status") != "complete":
        raise PipelineError("IMAGE_DETECTION_REQUIRED", "图片文本检测未完成，请重新检测后再进行 OCR", 409)
    if (previous.get("version") != REGIONS_VERSION or previous.get("source_sha256") != file.source_ref["sha256"]
            or previous.get("image_size") != list(image.size)):
        raise PipelineError("IMAGE_DETECTION_STALE", "图片文本检测已过期，请重新检测后再进行 OCR", 409)
    # Validate persisted geometry and identity without accepting a corrupted
    # checkpoint as an empty page or silently issuing a new detection.
    probe = copy.copy(file)
    probe.extra = {}
    checked = store_detection(probe, image.size, previous.get("regions"))
    if (checked["fingerprint"] != previous.get("fingerprint")
            or checked["region_count"] != previous.get("region_count")):
        raise PipelineError("IMAGE_DETECTION_INVALID", "图片检测检查点不一致，请重新检测", 409)
    return previous, True


def run_detection(file, image, context=None):
    """Explicitly run local detection, retaining an honest failure/cancel state."""
    from Backend.infrastructure.ocr.regions import plan_regions

    context = context or ExecutionContext()
    state = {"status": "running", "version": REGIONS_VERSION,
             "source_sha256": file.source_ref["sha256"], "image_size": list(image.size),
             "regions": [], "region_count": 0, "empty": False}
    file.extra["text_detection"] = state
    try:
        if context.is_cancelled():
            raise PipelineError("OCR_CANCELLED", "图片文本检测已取消", 409)
        regions = plan_regions(image, reading_order="auto", context=context)
        if context.is_cancelled():
            raise PipelineError("OCR_CANCELLED", "图片文本检测已取消", 409)
        return store_detection(file, image.size, regions)
    except Exception as error:
        cancelled = context.is_cancelled() or getattr(error, "code", "") == "OCR_CANCELLED"
        if cancelled:
            context.cancel()
        state.update(status="cancelled" if cancelled else "failed",
                     error={"code": getattr(error, "code", "IMAGE_DETECTION_FAILED"), "message": redact(str(error))})
        file.extra["text_detection"] = state
        raise


def publish_detection_items(project, file, manifest, *, preserve_existing=False):
    """Expose detected boxes before any text is recognized, without fake OCR."""
    next_index = max((item.text_index for item in project.items_iter()), default=-1) + 1
    kept, covered = [], set()
    available = {_digest(line["polygon"]) for line in manifest["regions"]}
    if preserve_existing:
        for item in file.items:
            lines = (item.extra.get("ocr") or {}).get("lines", [])
            keys = {_digest(line.get("polygon")) for line in lines}
            if keys and keys <= available and not keys & covered:
                kept.append(item)
                covered.update(keys)
    file.items = kept + [CacheItem(
        item_id=uuid.uuid5(uuid.NAMESPACE_URL, f"ainiee:detection:{file.file_id}:{line['region_id']}").hex,
        text_index=next_index + index, source_text="", translated_text="",
        translation_status=TranslationStatus.UNTRANSLATED,
        locator={"kind": "image", "index": index, "page_index": 0, "polygon": copy.deepcopy(line["polygon"]),
                 "coordinate_space": "pixel", "rotation": line["rotation"]},
        extra={"ocr": {"status": "pending", "recognition_scope": "region", "coordinates_source": "local_detector",
                       "lines": [copy.deepcopy(line)]},
               "layout": {"polygon": copy.deepcopy(line["polygon"]), "direction": line["direction"], "reading_order": index}},
    ) for index, line in enumerate(manifest["regions"]) if _digest(line["polygon"]) not in covered]
    file.__dict__.pop("items_index_dict", None)
    file.language_stats, file.lc_language_stats = [], []
    file.extra.pop("ocr", None)
    pipeline = file.extra.setdefault("image_pipeline", {})
    for stage in ("repair", "render"):
        pipeline.pop(stage, None)
    pipeline["detect"] = {"status": "complete", "region_count": manifest["region_count"]}
    project.stats_data = None


def detect_images(model, context=None):
    """Explicit re-detection for a model, including previously failed imports."""
    project, context = parse_model(model), context or ExecutionContext()
    record_image_stage(project, "detect", "running")
    report = {"stage": "detect", "detected_files": 0, "region_count": 0, "empty_files": 0,
              "errors": [], "operation_errors": [], "cancelled": False}
    files = [file for file in project.files.values() if file.media_type == "image"]
    if not files:
        raise PipelineError("NO_IMAGE_FILES", "模型中没有图片")
    try:
        if context.on_model_prepared:
            context.on_model_prepared(project)
        for index, file in enumerate(files):
            if context.is_cancelled():
                break
            pixels = None
            try:
                pixels, source = verified_image(file)
                previous = (file.extra.get("text_detection") or {}).get("fingerprint")
                manifest = run_detection(file, pixels, context)
                # A detector pass cannot silently invalidate source verification.
                from Backend.infrastructure.files.pipeline_support import file_sha256
                if file_sha256(source) != file.source_ref["sha256"]:
                    file.extra["text_detection"]["status"] = "failed"
                    raise PipelineError("SOURCE_CHANGED", "文本检测期间图片源文件发生变化")
                if previous != manifest["fingerprint"]:
                    publish_detection_items(project, file, manifest, preserve_existing=True)
                report["detected_files"] += 1
                report["region_count"] += manifest["region_count"]
                report["empty_files"] += int(manifest["empty"])
            except Exception as error:
                if context.is_cancelled():
                    break
                state = file.extra.setdefault("text_detection", {})
                state.update(status="failed", error={"code": getattr(error, "code", "IMAGE_DETECTION_FAILED"),
                                                     "message": redact(str(error))})
                report["errors"].append({"file_id": file.file_id, "path": file.storage_path,
                                         "code": getattr(error, "code", "IMAGE_DETECTION_FAILED"), "message": redact(str(error))})
            finally:
                if pixels is not None:
                    pixels.close()
            if context.on_batch_complete:
                context.on_batch_complete(file.items, file.storage_path, {"operation": "image_detection"})
            if context.on_progress:
                context.on_progress({"operation": "image_detection", "current": index + 1, "total": len(files),
                                     "detected_files": report["detected_files"], "region_count": report["region_count"]})
    except Exception as error:
        report["operation_errors"].append({"code": "IMAGE_DETECTION_CALLBACK_FAILED", "message": redact(str(error))})
    report["cancelled"] = context.is_cancelled()
    status = ("cancelled" if report["cancelled"] else "partial" if report["detected_files"] and
              (report["errors"] or report["operation_errors"]) else "failed" if report["errors"] or report["operation_errors"] else "success")
    record_image_stage(project, "detect", status)
    return {"status": status, "model": project, "report": report}
