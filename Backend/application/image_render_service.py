"""Independent, resumable repair, text composition and export operations.

Repair stores an unlettered image and a validated typography plan. Rendering
only composes that plan; export only copies/transcodes a verified rendered image.
All intermediate artifacts are content-addressed below the output's .ainiee.
"""
import copy
import hashlib
import io
import json
import os
from pathlib import Path

from PIL import Image

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.application.image_workflow import record_image_stage
from Backend.application.image_write_service import (
    _atomic_bytes, _calibrate_file_geometry, _directory, _image_bytes, _plan, _target,
    validate_image_options,
)
from Backend.core.log_system import redact
from Backend.core.protocol import to_wire
from Backend.domain.models.intermediate import parse_model
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.images import render as renderer
from Backend.infrastructure.images.source import verified_image


IMAGE_STAGE_VERSION = "independent-image-stages-v1"
STYLE_KEYS = ("font_path", "font_size", "min_font_size", "max_font_size", "font_color",
              "text_direction", "padding", "erase_mode")


def image_stage_fingerprint(file, options):
    """Identity of every input used by repair/preflight and text composition."""
    font = renderer.find_font(options.get("font_path"))
    items = []
    for item in file.items:
        extra = item.extra or {}
        ocr = extra.get("ocr") or {}
        items.append({"item_id": item.item_id, "source_text": item.source_text,
                      "translated_text": item.translated_text, "translation_status": item.translation_status,
                      "locator": item.locator, "layout": extra.get("layout"),
                      "ocr": {key: ocr.get(key) for key in
                              ("lines", "status", "recognition_scope", "coordinates_source")}})
    identity = {"version": IMAGE_STAGE_VERSION, "source_sha256": file.source_ref.get("sha256"),
                "size": [file.media_metadata.get("width"), file.media_metadata.get("height")],
                "items": items, "options": {key: options.get(key) for key in STYLE_KEYS},
                "font": {"path": str(font), "sha256": file_sha256(font)}}
    # None and an explicit path resolving to the same default font are equivalent.
    identity["options"]["font_path"] = str(font)
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _effective_options(file, values, provided, previous_stage):
    previous = ((file.extra.get("image_pipeline") or {}).get(previous_stage) or {}).get("options") or {}
    inherited = {key: previous[key] for key in STYLE_KEYS if key not in provided and key in previous}
    return validate_image_options({**values, **inherited})


def _artifact(path, data, root, sources):
    _atomic_bytes(path, data, True, root, sources)
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def _read_artifact(value, code):
    try:
        path = Path(value["path"])
        if not path.is_file() or path.stat().st_size > 512 * 1024 * 1024:
            raise ValueError("missing or oversized artifact")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != value["sha256"]:
            raise ValueError("artifact hash mismatch")
        return data
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise PipelineError(code, "图片阶段产物缺失或已变化，请重新执行对应阶段", 409) from error


def _load_pixels(value, size, code, mode=None):
    try:
        data = _read_artifact(value, code)
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or image.size != tuple(size) or getattr(image, "n_frames", 1) != 1:
                raise ValueError("invalid stage image")
            if mode and image.mode != mode:
                raise ValueError("invalid stage image mode")
            image.load()
            return image.copy()
    except PipelineError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise PipelineError(code, "图片阶段产物格式或尺寸无效，请重新生成", 409) from error


def _save_plan(plan, fingerprint, base, root, sources):
    entries = []
    for index, entry in enumerate(plan["items"]):
        ink = _artifact(_target(root, f"{base}/ink_{index}.png"), _image_bytes(entry["ink"], "png"), root, sources)
        entries.append({"item_id": entry["item_id"], "box": list(entry["box"]),
                        "color": entry["color"], "ink": ink})
    payload = {"version": IMAGE_STAGE_VERSION, "fingerprint": fingerprint, "size": list(plan["size"]),
               "source_mode": plan["source_mode"], "items": entries, "report": plan["report"]}
    return _artifact(_target(root, f"{base}/plan.json"),
                     json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(), root, sources)


def _load_plan(state, size, fingerprint):
    code = "IMAGE_REPAIR_STALE"
    try:
        plan = json.loads(_read_artifact(state["artifacts"]["plan"], code))
        if (plan["version"] != IMAGE_STAGE_VERSION or plan["fingerprint"] != fingerprint
                or tuple(plan["size"]) != tuple(size) or plan["source_mode"] not in ("RGB", "RGBA")
                or not isinstance(plan["items"], list) or len(plan["items"]) > 10000):
            raise ValueError("invalid repair plan")
        for entry in plan["items"]:
            box = entry["box"]
            if (len(box) != 4 or any(type(n) is not int for n in box)
                    or not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1])):
                raise ValueError("invalid text layer bounds")
            entry["ink"] = _load_pixels(entry["ink"], (box[2] - box[0], box[3] - box[1]), code, "L")
        return plan
    except PipelineError:
        raise
    except (TypeError, KeyError, ValueError) as error:
        raise PipelineError(code, "文字排版预检计划无效，请重新执行图片修复", 409) from error


def _require_state(file, stage, fingerprint, size):
    state = (file.extra.get("image_pipeline") or {}).get(stage)
    label = "REPAIR" if stage == "repair" else "RENDER"
    if not isinstance(state, dict):
        raise PipelineError(f"IMAGE_{label}_REQUIRED", "请先完成图片修复" if stage == "repair" else "请先完成文字渲染", 409)
    if (state.get("fingerprint") != fingerprint or state.get("source_sha256") != file.source_ref.get("sha256")
            or state.get("status") not in ("complete", "partial")):
        raise PipelineError(f"IMAGE_{label}_STALE", "原文、译文、坐标或排版设置已变化，请重新生成图片阶段产物", 409)
    artifacts = state.get("artifacts") or {}
    for key in ("image", "mask", "debug"):
        _read_artifact(artifacts.get(key), f"IMAGE_{label}_STALE")
    return state


def valid_image_stage(file, stage):
    """Read-only check used when exposing a repaired/rendered preview URL."""
    try:
        state = (file.extra.get("image_pipeline") or {}).get(stage) or {}
        options = validate_image_options(state.get("options"))
        pixels, _ = verified_image(file)
        fingerprint = image_stage_fingerprint(file, options)
        _require_state(file, stage, fingerprint, pixels.size)
        if stage == "repair":
            _load_plan(state, pixels.size, fingerprint)
        return True
    except (PipelineError, OSError, ValueError, TypeError):
        return False


def _report(stage):
    return {"stage": stage, "errors": [], "warnings": [], "operation_errors": [], "written_files": 0, "reused_files": 0,
            "repaired_items": 0, "rendered_items": 0, "skipped_items": 0, "preserved_items": 0,
            "cancelled": False, "skipped_files": []}


def _status(report, outputs, context):
    report["cancelled"], report["written_files"] = context.is_cancelled() and not report["operation_errors"], len(outputs)
    if report["operation_errors"]:
        return "partial" if outputs else "failed"
    if report["cancelled"]:
        return "cancelled"
    if report["errors"] or report["skipped_items"]:
        return "partial" if outputs else "failed"
    return "success" if outputs else "failed"


def _notify(context, project, file, report, stage, total):
    try:
        if context.on_batch_complete:
            context.on_batch_complete(file.items, file.storage_path, {"operation": f"image_{stage}"})
        if context.on_progress and not context.is_cancelled():
            context.on_progress({"phase": stage, "stage": stage, "file_id": file.file_id,
                                 "completed_files": report["written_files"], "total_files": total})
    except Exception:
        error = {"file_id": file.file_id, "code": "IMAGE_CALLBACK_FAILED", "message": "图片阶段进度保存失败，已停止处理"}
        report["errors"].append(error)
        report["operation_errors"].append(error)
        context.cancel()


def _add_file(report, outputs, file, state, stage, reused):
    counts = state["report"]
    amount = counts["rendered_items"]
    report["repaired_items" if stage == "repair" else "rendered_items"] += amount
    report["skipped_items"] += counts["skipped_items"]
    report["preserved_items"] += counts["preserved_items"]
    report["warnings"].extend({"file_id": file.file_id, **warning} for warning in counts["warnings"])
    report["reused_files"] += int(reused)
    outputs.append({"file_id": file.file_id, "path": state["artifacts"]["image"]["path"], "format": "png",
                    "variant": "repaired" if stage == "repair" else "translated", "reused": reused,
                    "repaired_items": amount if stage == "repair" else 0,
                    "rendered_items": amount if stage == "render" else 0,
                    "skipped_items": counts["skipped_items"], "preserved_items": counts["preserved_items"],
                    "artifacts": copy.deepcopy(state["artifacts"])})
    report["written_files"] = len(outputs)


def _save_stage_model(project, values, stage, status, root, sources, report):
    if not values["save_model"]:
        return None, status
    try:
        target = _target(root, f".ainiee/image-stages/{project.project_id}/{stage}_model.json")
        _atomic_bytes(target, json.dumps(to_wire(project), ensure_ascii=False, indent=2).encode(), True, root, sources)
        return str(target), status
    except Exception as error:
        report["errors"].append({"code": getattr(error, "code", "IMAGE_MODEL_SAVE_FAILED"), "message": redact(str(error))})
        return None, "cancelled" if status == "cancelled" else "partial" if report["written_files"] else "failed"


def _stage(model, options, context, stage):
    values = validate_image_options(options)
    project = parse_model(model)
    record_image_stage(project, stage, "running")
    context = context or ExecutionContext()
    root = _directory(values["output_dir"])
    sources = {os.path.normcase(str(Path(file.source_ref["path"]).resolve())) for file in project.files.values() if file.source_ref.get("path")}
    files = [file for file in project.files.values() if file.media_type == "image"]
    if not files:
        raise PipelineError("NO_IMAGE_FILES", "模型中没有图片文件")
    outputs, report = [], _report(stage)
    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception:
            error = {"code": "IMAGE_CALLBACK_FAILED", "message": "图片阶段模型回调失败"}
            report["errors"].append(error)
            report["operation_errors"].append(error)
            context.cancel()
    for file in files:
        if context.is_cancelled():
            break
        try:
            effective = _effective_options(file, values, options, "repair") if stage == "render" else values
            pixels, source = verified_image(file)
            if not file.items and (file.extra.get("ocr") or {}).get("status") != "complete":
                raise PipelineError("IMAGE_OCR_REQUIRED", "图片尚未完成 OCR")
            fingerprint = image_stage_fingerprint(file, effective)
            states = file.extra.setdefault("image_pipeline", {})
            reused = False
            if stage == "repair":
                try:
                    state = _require_state(file, "repair", fingerprint, pixels.size)
                    _load_plan(state, pixels.size, fingerprint)
                    reused = True
                except PipelineError:
                    geometry_warnings, corrected = [], []
                    try:
                        corrected = _calibrate_file_geometry(pixels, file, context)
                    except Exception:
                        if context.is_cancelled():
                            break
                        geometry_warnings.append({"code": "IMAGE_GEOMETRY_CALIBRATION_UNAVAILABLE",
                                                  "message": "本地文字定位校准不可用，已使用原 OCR 坐标并检查回填范围"})
                    if context.is_cancelled():
                        break
                    fingerprint = image_stage_fingerprint(file, effective)
                    plan = renderer.prepare_image_plan(pixels, file, effective, context)
                    repaired = renderer.repair_image(pixels, plan, effective, context)
                    if context.is_cancelled():
                        break
                    if file_sha256(source) != file.source_ref["sha256"]:
                        raise PipelineError("SOURCE_CHANGED", "修复期间图片源文件发生变化", 409)
                    plan["report"]["warnings"].extend(geometry_warnings)
                    base = f".ainiee/image-stages/{project.project_id}/{file.file_id}/{fingerprint}"
                    artifacts = {"image": _artifact(_target(root, f"{base}/repaired.png"), _image_bytes(repaired, "png"), root, sources),
                                 "mask": _artifact(_target(root, f"{base}/mask.png"), _image_bytes(plan["mask"], "png"), root, sources),
                                 "debug": _artifact(_target(root, f"{base}/debug.png"), _image_bytes(plan["debug"], "png"), root, sources),
                                 "plan": _save_plan(plan, fingerprint, base, root, sources)}
                    state = {"status": "partial" if plan["report"]["skipped_items"] else "complete",
                             "fingerprint": fingerprint, "source_sha256": file.source_ref["sha256"],
                             "artifacts": artifacts, "report": copy.deepcopy(plan["report"]), "options": dict(effective),
                             "geometry_corrected_items": corrected,
                             "repaired_items": plan["report"]["rendered_items"], "rendered_items": 0,
                             "skipped_items": plan["report"]["skipped_items"], "preserved_items": plan["report"]["preserved_items"],
                             "warnings": plan["report"]["warnings"], "preserved": plan["report"]["preserved"]}
                    states["repair"] = state
                    states.pop("render", None)
            else:
                repair = _require_state(file, "repair", fingerprint, pixels.size)
                plan = _load_plan(repair, pixels.size, fingerprint)
                try:
                    state = _require_state(file, "render", fingerprint, pixels.size)
                    if state.get("repair_fingerprint") != fingerprint:
                        raise PipelineError("IMAGE_RENDER_STALE", "文字渲染对应的修复结果已变化", 409)
                    reused = True
                except PipelineError:
                    repaired = _load_pixels(repair["artifacts"]["image"], pixels.size, "IMAGE_REPAIR_STALE")
                    rendered = renderer.paint_image(repaired, plan, context)
                    if context.is_cancelled():
                        break
                    if file_sha256(source) != file.source_ref["sha256"]:
                        raise PipelineError("SOURCE_CHANGED", "文字渲染期间图片源文件发生变化", 409)
                    base = f".ainiee/image-stages/{project.project_id}/{file.file_id}/{fingerprint}"
                    artifacts = {**copy.deepcopy(repair["artifacts"]),
                                 "image": _artifact(_target(root, f"{base}/rendered.png"), _image_bytes(rendered, "png"), root, sources)}
                    state = {"status": repair["status"], "fingerprint": fingerprint, "repair_fingerprint": fingerprint,
                             "source_sha256": file.source_ref["sha256"], "artifacts": artifacts,
                             "report": copy.deepcopy(plan["report"]), "options": dict(effective),
                             "geometry_corrected_items": repair.get("geometry_corrected_items", []), **copy.deepcopy(plan["report"])}
                    states["render"] = state
            if file_sha256(source) != file.source_ref["sha256"]:
                raise PipelineError("SOURCE_CHANGED", "图片阶段结束前源文件发生变化", 409)
            _add_file(report, outputs, file, state, stage, reused)
            _notify(context, project, file, report, stage, len(files))
        except Exception as error:
            report["errors"].append({"file_id": file.file_id, "path": file.storage_path,
                                     "code": getattr(error, "code", "IMAGE_STAGE_FAILED"), "message": redact(str(error))})
    status = _status(report, outputs, context)
    record_image_stage(project, stage, status)
    model_path, status = _save_stage_model(project, values, stage, status, root, sources, report)
    record_image_stage(project, stage, status)
    return {"status": status, "model": project, "files": outputs, "model_path": model_path, "report": report}


def repair_images(model, options=None, context=None):
    return _stage(model, options, context, "repair")


def render_images(model, options=None, context=None):
    return _stage(model, options, context, "render")


def export_images(model, options=None, context=None):
    """Export only current verified render artifacts. Never detect, erase or typeset."""
    from Backend.application.image_workflow import record_image_stage

    values = validate_image_options(options)
    project = parse_model(model)
    context = context or ExecutionContext()
    root, plans, model_path, sources = _plan(project, values)
    report, outputs = _report("export"), []
    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception:
            error = {"code": "IMAGE_CALLBACK_FAILED", "message": "图片导出模型回调失败"}
            report["errors"].append(error)
            report["operation_errors"].append(error)
            context.cancel()
    for file, destinations in plans:
        if context.is_cancelled():
            break
        try:
            effective = _effective_options(file, values, options, "render")
            original, source = verified_image(file)
            fingerprint = image_stage_fingerprint(file, effective)
            state = _require_state(file, "render", fingerprint, original.size)
            artifacts = state["artifacts"]
            png = _read_artifact(artifacts["image"], "IMAGE_RENDER_STALE")
            if values["format"] == "png":
                data = png
            else:
                rendered = _load_pixels(artifacts["image"], original.size, "IMAGE_RENDER_STALE")
                data = _image_bytes(rendered, values["format"])
                if values["format"] == "jpeg" and rendered.mode == "RGBA":
                    report["warnings"].append({"file_id": file.file_id, "code": "JPEG_ALPHA_FLATTENED",
                                               "message": "JPEG 不支持透明度，已合成白色背景"})
            if file_sha256(source) != file.source_ref["sha256"]:
                raise PipelineError("SOURCE_CHANGED", "导出前图片源文件发生变化", 409)
            exported = {}
            payloads = {"image": data, "mask": _read_artifact(artifacts["mask"], "IMAGE_RENDER_STALE")}
            if values["debug_overlay"]:
                payloads["debug"] = _read_artifact(artifacts["debug"], "IMAGE_RENDER_STALE")
            for key, payload in payloads.items():
                _atomic_bytes(destinations[key], payload, values["overwrite"], root, sources)
                exported[key] = {"path": str(destinations[key]), "sha256": hashlib.sha256(payload).hexdigest()}
            counts = state["report"]
            report["rendered_items"] += counts["rendered_items"]
            report["skipped_items"] += counts["skipped_items"]
            report["preserved_items"] += counts["preserved_items"]
            report["warnings"].extend({"file_id": file.file_id, **warning} for warning in counts["warnings"])
            report["reused_files"] += 1
            outputs.append({"file_id": file.file_id, "path": str(destinations["image"]), "format": values["format"],
                            "variant": "translated", "artifacts": exported,
                            **{key: counts[key] for key in ("rendered_items", "skipped_items", "preserved_items")}})
            report["written_files"] = len(outputs)
            _notify(context, project, file, report, "export", len(plans))
        except Exception as error:
            report["errors"].append({"file_id": file.file_id, "path": file.storage_path,
                                     "code": getattr(error, "code", "IMAGE_WRITE_FAILED"), "message": redact(str(error))})
    status = _status(report, outputs, context)
    record_image_stage(project, "export", status)
    saved = None
    # A missing/stale render is a failed precondition, not an exported project.
    # Do not consume the final filename and block a later successful export.
    if model_path and outputs:
        try:
            project.extra["image_export"] = {"model_path": str(model_path), "status": status}
            _atomic_bytes(model_path, json.dumps(to_wire(project), ensure_ascii=False, indent=2).encode(), values["overwrite"], root, sources)
            saved = str(model_path)
        except Exception as error:
            report["errors"].append({"code": getattr(error, "code", "IMAGE_MODEL_SAVE_FAILED"), "message": redact(str(error))})
            status = "cancelled" if context.is_cancelled() else "partial" if outputs else "failed"
            record_image_stage(project, "export", status)
    return {"status": status, "model": project, "files": outputs, "model_path": saved, "report": report}
