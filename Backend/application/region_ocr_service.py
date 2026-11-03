"""Detection-owned coordinates with resumable, region-by-region text recognition.

The detector identifies ink before any paid request. OCR supplies text only;
its response can never move the region used for erasure or layout.
"""
import copy
from dataclasses import asdict
import hashlib
import json
import uuid

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_item import CacheItem, TranslationStatus
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.ocr.dashscope import request_ocr_text, validate_polygon
from Backend.infrastructure.ocr.layout import join_text_lines


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _request_identity(config, source_hash):
    from Backend.infrastructure.ocr.regions import CROP_VERSION, REGIONS_VERSION

    # Layout/reading-order changes can reuse paid recognition. Credentials are
    # never recorded, and provider labels do not change the requested model.
    values = asdict(config)
    values = {key: values[key] for key in ("api_url", "api_format", "model", "max_tokens", "max_pixels")}
    return _digest({"source_sha256": source_hash, "request": values,
                    "regions_version": REGIONS_VERSION, "crop_version": CROP_VERSION})


def _manifest(file, image, config, context):
    from Backend.infrastructure.ocr.regions import MAX_REGIONS
    from Backend.application.image_detection_service import ensure_detection, store_detection

    fingerprint = _request_identity(config, file.source_ref["sha256"])
    previous = file.extra.get("ocr_regions")
    reusable = {}
    if (isinstance(previous, dict) and previous.get("fingerprint") == fingerprint
            and (not config.reocr or previous.get("status") != "complete")):
        records = previous.get("regions")
        if not isinstance(records, list) or len(records) > MAX_REGIONS:
            raise PipelineError("OCR_REGION_CHECKPOINT_INVALID", "分区识别检查点无效，请重新读取图片", 409)
        seen = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("line"), dict):
                raise PipelineError("OCR_REGION_CHECKPOINT_INVALID", "分区识别检查点缺少文字区域", 409)
            if record.get("status") not in ("pending", "failed", "complete"):
                raise PipelineError("OCR_REGION_CHECKPOINT_INVALID", "分区识别检查点状态无效", 409)
            line = record["line"]
            polygon = validate_polygon(line.get("polygon"), *image.size)
            expected = _digest({"fingerprint": fingerprint, "polygon": polygon})
            if record.get("region_id") != expected or expected in seen:
                raise PipelineError("OCR_REGION_CHECKPOINT_INVALID", "分区识别检查点坐标不一致", 409)
            seen.add(expected)
            if record.get("status") == "complete" and (
                    not isinstance(record.get("text"), str) or not record["text"].strip()
                    or len(record["text"]) > 32768):
                raise PipelineError("OCR_REGION_CHECKPOINT_INVALID", "分区识别检查点缺少有效原文", 409)
        reusable = {record["region_id"]: record for record in records}
        if file.extra.get("text_detection") is None:
            # Older paid checkpoints already own local detector coordinates.
            # Promote those rather than rerunning detection and losing recovery.
            store_detection(file, image.size, [record["line"] for record in records])
    detection, _ = ensure_detection(file, image, context)
    lines = detection["regions"]
    if reusable or (isinstance(previous, dict) and previous.get("fingerprint") == fingerprint
                    and not previous.get("regions") and (not config.reocr or previous.get("status") != "complete")):
        current_ids = {_digest({"fingerprint": fingerprint, "polygon": line["polygon"]}) for line in lines}
        if current_ids == set(reusable):
            previous["detection_fingerprint"] = detection["fingerprint"]
            return previous
    records = []
    for line in lines:
        polygon = validate_polygon(line["polygon"], *image.size)
        line = {**line, "polygon": polygon}
        identity = _digest({"fingerprint": fingerprint, "polygon": polygon})
        record = copy.deepcopy(reusable.get(identity, {"region_id": identity, "status": "pending"}))
        record["line"] = line
        records.append(record)
    manifest = {"fingerprint": fingerprint, "source_sha256": file.source_ref["sha256"],
                "detection_fingerprint": detection["fingerprint"], "status": "running", "regions": records}
    file.extra["ocr_regions"] = manifest
    return manifest


def _publish_items(project, file, manifest, image, config, *, preserve_existing=False):
    from Backend.application.ocr_service import _block, _group_lines

    lines = [{**record["line"], "text": record.get("text", "") if record["status"] == "complete" else "",
              "recognition_status": record["status"], "region_id": record["region_id"],
              "coordinates_source": "local_detector"} for record in manifest["regions"]]
    # Direction voting and grouping must not depend on which paid responses
    # have arrived. A square glyph next to a vertical column stays in that
    # sentence even while the column's OCR is still pending.
    grouping_lines = []
    for line in lines:
        xs, ys = zip(*line["polygon"])
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        glyph_count = max(1, min(200, round(max(width, height) / max(1, min(width, height)))))
        grouping_lines.append({**line, "text": "?" * glyph_count})
    groups, notices = _group_lines(grouping_lines, image, config.group_lines, config.reading_order)
    actual = {line["region_id"]: line for line in lines}
    groups = [[{**line, "text": actual[line["region_id"]]["text"]} for line in group] for group in groups]
    previous = {item.item_id: item for item in file.items}
    next_index = max((item.text_index for item in project.items_iter()), default=-1) + 1
    items = []
    for index, group in enumerate(groups):
        block = _block(group)
        identity = ":".join(sorted(line["region_id"] for line in group))
        item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ainiee:region-ocr:{file.file_id}:{identity}").hex
        complete = all(line["recognition_status"] == "complete" for line in group)
        # Never translate an incomplete sentence assembled from only the
        # successful columns. The paid fragments remain in the checkpoint.
        recognized = join_text_lines(group) if complete else ""
        old = previous.get(item_id)
        old_ocr = (old.extra.get("ocr") or {}) if old else {}
        old_recognized = old_ocr.get("recognized_text", "\n".join(line.get("text", "") for line in old_ocr.get("lines", [])))
        keep_edits = bool(preserve_existing and old and complete and old_ocr.get("status") == "complete"
                          and old_recognized == recognized)
        source = old.source_text if keep_edits else recognized
        unchanged = old is not None and old.source_text == source
        text_index = old.text_index if old else next_index
        if old is None:
            next_index += 1
        extra = copy.deepcopy(old.extra) if unchanged else {}
        extra["ocr"] = {**(old_ocr if keep_edits else {}), "provider_id": config.provider_id, "model": config.model,
                        "recognition_scope": "region", "coordinates_source": "local_detector", "recognized_text": recognized,
                        "status": "complete" if complete else "pending", "lines": group}
        if not keep_edits:
            extra["layout"] = {"polygon": block["polygon"], "direction": block["direction"], "reading_order": index}
        locator = copy.deepcopy(old.locator) if keep_edits else {
            "kind": "image", "page_index": 0, "polygon": block["polygon"], "coordinate_space": "pixel",
            "rotation": group[0].get("rotation", 0) if len(group) == 1 else 0}
        locator["index"] = index
        items.append(CacheItem(
            item_id=item_id, text_index=text_index, source_text=source,
            translated_text=old.translated_text if unchanged else "",
            translation_status=old.translation_status if unchanged else TranslationStatus.UNTRANSLATED,
            model=old.model if unchanged else "", lang_code=old.lang_code if unchanged else None,
            locator=locator,
            extra=extra,
        ))
    file.items = items
    file.__dict__.pop("items_index_dict", None)
    file.language_stats, file.lc_language_stats = [], []
    pipeline = file.extra.setdefault("image_pipeline", {})
    for stage in ("repair", "render"):
        pipeline.pop(stage, None)
    project.stats_data = None
    return notices


def ocr_regions_model(project, config, context=None):
    from Backend.application.ocr_service import _fingerprint, _image_source, _notify_batch, _prepare_image, _refine_file
    from Backend.application.read_service import ensure_media_language_metadata
    from Backend.infrastructure.ocr.regions import prepare_region

    context = context or ExecutionContext()
    files = [file for file in project.files.values() if file.media_type == "image"]
    if not files:
        raise PipelineError("OCR_NO_IMAGES", "中间模型中没有图片", 400)
    report = {"total": len(files), "succeeded": 0, "skipped": 0, "failed": 0, "cancelled": False,
              "cancelled_files": 0, "line_count": 0, "block_count": 0, "files": [], "errors": [],
              "warnings": [], "operation_errors": [], "usage": {"requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
              "regions": {"total": 0, "succeeded": 0, "reused": 0, "failed": 0, "pending": 0}}
    report["refinement"] = {"enabled": config.refine_text, "eligible": 0, "succeeded": 0, "skipped": 0,
                            "ineligible": 0, "failed": 0, "rejected": 0, "revalidated": 0, "changed": 0, "items": []}
    fingerprint = _fingerprint(config)
    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception:
            report["operation_errors"].append({"code": "OCR_CALLBACK_FAILED", "message": "OCR 模型回调失败"})
            context.cancel()
    for ordinal, file in enumerate(files):
        if context.is_cancelled():
            report["cancelled_files"] = len(files) - ordinal
            break
        identity = {"file_id": file.file_id, "path": file.storage_path}
        manifest, image = None, None
        try:
            path, width, height = _image_source(file)
            image, _, _ = _prepare_image(path, width, height, config.max_pixels)
            manifest = _manifest(file, image, config, context)
            records = manifest["regions"]
            report["regions"]["total"] += len(records)
            reused = sum(record["status"] == "complete" for record in records)
            report["regions"]["reused"] += reused
            # Save the detected manifest before issuing the first paid request.
            manifest["status"] = "running"
            file.extra["ocr"] = {"status": "running", "source_sha256": file.source_ref["sha256"],
                                 "config_fingerprint": fingerprint, "recognition_mode": "regions"}
            _notify_batch(context, [], file.storage_path, report, "ocr_detection")
            for index, record in enumerate(records):
                if context.is_cancelled():
                    break
                if record["status"] == "complete":
                    continue
                requested = False
                try:
                    if file_sha256(path) != file.source_ref["sha256"]:
                        raise PipelineError("OCR_SOURCE_CHANGED", "分区识别前图片源文件发生变化，请重新读取", 409)
                    data, size, crop_info = prepare_region(image, record["line"], config.max_pixels)
                    requested = True
                    response = request_ocr_text(data, image_width=size[0], image_height=size[1],
                                                config=config.to_request_config(), context=context)
                    report["usage"]["requests"] += response.get("attempts", 1)
                    requested = False
                    for key in ("input_tokens", "output_tokens", "total_tokens"):
                        report["usage"][key] += response.get("usage", {}).get(key, 0)
                    record.update(status="complete", text=response["text"], usage=response.get("usage", {}),
                                  request_id=response.get("request_id", ""), attempts=response.get("attempts", 1), crop=crop_info)
                    record.pop("error", None)
                    report["regions"]["succeeded"] += 1
                    _notify_batch(context, [], file.storage_path, report, "ocr_region")
                    if file_sha256(path) != file.source_ref["sha256"]:
                        raise PipelineError("OCR_SOURCE_CHANGED", "分区识别期间图片源文件发生变化，请重新读取", 409)
                except PipelineError as error:
                    if requested:
                        report["usage"]["requests"] += (error.details or {}).get("attempts", 0)
                    if error.code == "OCR_CANCELLED":
                        context.cancel()
                        break
                    if error.code == "OCR_SOURCE_CHANGED":
                        raise
                    record.update(status="failed", error={"code": error.code, "message": error.message})
                    report["regions"]["failed"] += 1
                    report["errors"].append({**identity, "region_id": record["region_id"], **record["error"]})
                    _notify_batch(context, [], file.storage_path, report, "ocr_region")
                    # An unreadable/noisy detector crop must not starve later
                    # text. Transport/auth failures, however, stop this page
                    # instead of repeating the same failing request everywhere.
                    if error.code not in {"OCR_INVALID_RESPONSE", "OCR_INCOMPLETE_RESPONSE", "OCR_IMAGE_TOO_LARGE"}:
                        break
                if context.on_progress and not context.is_cancelled():
                    try:
                        context.on_progress({"operation": "ocr_region", **identity, "current": ordinal + 1,
                                             "total": len(files), "region_current": index + 1, "region_total": len(records)})
                    except Exception:
                        report["operation_errors"].append({"code": "OCR_CALLBACK_FAILED", "message": "OCR 进度回调失败"})
                        context.cancel()
            complete = all(record["status"] == "complete" for record in records)
            # Retain resumability until every callback and local finalization
            # succeeds, even when cancellation follows the last paid response.
            manifest["status"] = "partial"
            if file_sha256(path) != file.source_ref["sha256"]:
                raise PipelineError("OCR_SOURCE_CHANGED", "发布识别结果前图片源文件发生变化，请重新读取", 409)
            notices = _publish_items(project, file, manifest, image, config, preserve_existing=reused > 0)
            file.extra["ocr"].update(status=manifest["status"], provider_id=config.provider_id, model=config.model,
                                      line_count=len(records), block_count=len(file.items),
                                      uploaded_width=width, uploaded_height=height)
            report["regions"]["pending"] += sum(record["status"] != "complete" for record in records)
            report["line_count"] += sum(record["status"] == "complete" for record in records)
            report["block_count"] += sum((item.extra.get("ocr") or {}).get("status") == "complete" for item in file.items)
            report["warnings"].extend({**identity, **warning} for warning in notices)
            key = "skipped" if complete and reused == len(records) and records else "succeeded" if complete else "failed"
            report[key] += 1
            report["files"].append({**identity, "status": "success" if complete else "partial",
                                    "line_count": len(records), "block_count": len(file.items)})
            if not context.is_cancelled():
                _notify_batch(context, file.items, file.storage_path, report, "ocr")
            if config.refine_text and complete and file.items and not context.is_cancelled():
                _refine_file(file, path, image, config, context, report, project)
            if complete and not context.is_cancelled():
                manifest["status"] = file.extra["ocr"]["status"] = "complete"
        except PipelineError as error:
            if manifest is not None:
                manifest["status"] = "partial"
            if error.code == "OCR_CANCELLED":
                context.cancel()
                break
            report["failed"] += 1
            report["errors"].append({**identity, "code": error.code, "message": error.message})
            report["files"].append({**identity, "status": "failed"})
        except Exception:
            if manifest is not None:
                manifest["status"] = "partial"
            report["failed"] += 1
            report["errors"].append({**identity, "code": "OCR_INTERNAL_ERROR", "message": "分区识别失败，已完成区域保留，可继续识别"})
            report["files"].append({**identity, "status": "failed"})
        finally:
            if image is not None:
                image.close()
        if context.is_cancelled():
            report["cancelled_files"] = len(files) - ordinal
            break
    if not context.is_cancelled():
        try:
            ensure_media_language_metadata(project, media_types=("image",))
        except PipelineError as error:
            report["operation_errors"].append({"code": error.code, "message": error.message})
    report["cancelled"] = context.is_cancelled() and not report["operation_errors"]
    useful = report["succeeded"] or report["skipped"] or report["regions"]["succeeded"] or report["regions"]["reused"]
    if report["operation_errors"]:
        status = "partial" if useful else "failed"
    elif report["cancelled"]:
        status = "cancelled"
    elif report["failed"]:
        status = "partial" if useful else "failed"
    elif report["refinement"]["failed"] or report["refinement"]["rejected"]:
        status = "partial"
    else:
        status = "success"
    return {"status": status, "model": project, "report": report}
