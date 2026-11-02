"""Export completed generated images directly; no OCR, text layout or fonts."""
import io
import json
import os
from pathlib import Path

from PIL import Image

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.protocol import to_wire
from Backend.domain.models.intermediate import parse_model
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.image_generation.artifacts import (
    output_directory, safe_target, atomic_bytes, verified_generated_image,
)
from Backend.infrastructure.image_generation.dashscope import safe_message


def validate_generated_image_options(options=None):
    if not isinstance(options, dict) or set(options) - {"output_dir", "format", "suffix", "overwrite", "save_model"}:
        raise PipelineError("VALIDATION_ERROR", "生成图片导出参数无效", 422)
    values = {"output_dir": None, "format": "png", "suffix": "_translated", "overwrite": False, "save_model": True, **options}
    values["output_dir"] = str(output_directory(values["output_dir"]))
    if values["format"] not in ("png", "jpeg", "webp"):
        raise PipelineError("VALIDATION_ERROR", "图片输出格式需为png、jpeg或webp", 422)
    for key in ("overwrite", "save_model"):
        if type(values[key]) is not bool:
            raise PipelineError("VALIDATION_ERROR", f"{key}需为布尔值", 422)
    if not isinstance(values["suffix"], str) or any(c in values["suffix"] for c in '/\\<>:"|?*\x00'):
        raise PipelineError("INVALID_OUTPUT_PATH", "输出后缀不能包含路径分隔符或非法字符", 422)
    return values


def _plan(project, options):
    root = output_directory(options["output_dir"])
    protected = {os.path.normcase(str(Path(file.source_ref["path"]).resolve())) for file in project.files.values() if file.source_ref.get("path")}
    # A canonical generated artifact is a source too: formal export must never
    # silently overwrite the recovery copy, even if overwrite=true.
    for file in project.files.values():
        artifact = file.extra.get("image_generation", {}).get("artifact", {})
        if isinstance(artifact, dict) and artifact.get("path"):
            protected.add(os.path.normcase(str(Path(artifact["path"]).resolve())))
    plans = []
    for file in project.files.values():
        if file.media_type != "image":
            continue
        relative = Path(file.storage_path.replace("\\", "/"))
        target = safe_target(root, relative.with_name(relative.stem + options["suffix"] + "." + options["format"]).as_posix())
        plans.append((file, target))
    if not plans:
        raise PipelineError("NO_IMAGE_FILES", "模型中没有图片文件", 400)
    model_path = safe_target(root, f"{project.project_id}_image_model.json") if options["save_model"] else None
    targets = [target for _, target in plans] + ([model_path] if model_path else [])
    seen = set()
    for target in targets:
        key = os.path.normcase(str(target))
        if key in protected:
            raise PipelineError("INVALID_OUTPUT_PATH", "导出不能覆盖原图或生成缓存产物", 422)
        if key in seen:
            raise PipelineError("OUTPUT_COLLISION", "多个输出指向同一文件", 409)
        seen.add(key)
        output_directory(target.parent)
        if target.exists() and (not target.is_file() or not options["overwrite"]):
            raise PipelineError("OUTPUT_EXISTS", "图片导出目标已存在", 409)
    return root, plans, model_path, protected


def validate_generated_image_targets(model, options=None):
    values = validate_generated_image_options(options)
    _plan(parse_model(model), values)
    return values


def write_generated_images(model, options=None, context=None):
    project = parse_model(model)
    values = validate_generated_image_options(options)
    root, plans, model_path, protected = _plan(project, values)
    context = context or ExecutionContext()
    report = {"written_files": 0, "errors": [], "warnings": [], "operation_errors": [], "cancelled": False}
    outputs = []
    if context.on_model_prepared:
        context.on_model_prepared(project)
    for ordinal, (file, target) in enumerate(plans):
        if context.is_cancelled():
            break
        try:
            requested = project.extra.get("image_generation_options", {})
            saved = file.extra.get("image_generation", {}).get("settings", {})
            if (not isinstance(requested, dict) or not isinstance(saved, dict)
                    or any(requested.get(key) != saved.get(key) for key in
                           ("source_language", "target_language", "text_mode", "prompt"))):
                raise PipelineError("IMAGE_GENERATION_REQUIRED", "生图选项已变化，请重新生成后导出", 409)
            pixels, source = verified_generated_image(file)
            try:
                if values["format"] == "png":
                    content = source.read_bytes()
                else:
                    if values["format"] == "jpeg" and pixels.mode == "RGBA":
                        background = Image.new("RGB", pixels.size, "white")
                        background.paste(pixels, mask=pixels.getchannel("A"))
                        pixels.close()
                        pixels = background
                        report["warnings"].append({"file_id": file.file_id, "code": "JPEG_ALPHA_FLATTENED", "message": "JPEG不支持透明度，已使用白色背景"})
                    buffer = io.BytesIO()
                    pixels.save(buffer, format=values["format"].upper(), **({"quality": 95} if values["format"] == "jpeg" else {"lossless": True}))
                    content = buffer.getvalue()
                if file_sha256(source) != file.extra["image_generation"]["artifact"]["sha256"]:
                    raise PipelineError("IMAGE_GENERATION_ARTIFACT_CHANGED", "导出期间生成图片发生变化", 409)
                atomic_bytes(target, content, root=root, overwrite=values["overwrite"], protected=protected)
                artifact = {"path": str(target), "sha256": file_sha256(target), "width": pixels.width, "height": pixels.height, "format": values["format"]}
            finally:
                pixels.close()
            file.extra["image_generation"]["last_export"] = artifact
            outputs.append({"file_id": file.file_id, "path": str(target), "format": values["format"], "artifacts": {"image": artifact}})
            report["written_files"] += 1
            if context.on_batch_complete:
                context.on_batch_complete(file.items, file.storage_path, {"operation": "write_generated_image"})
            if context.on_progress:
                context.on_progress({"operation": "write_generated_image", "current": ordinal + 1, "total": len(plans)})
        except Exception as error:
            report["errors"].append({"file_id": file.file_id, "path": file.storage_path,
                                     "code": getattr(error, "code", "IMAGE_WRITE_FAILED"), "message": safe_message(error)})
    report["cancelled"] = context.is_cancelled()
    status = "cancelled" if report["cancelled"] else "partial" if report["errors"] and outputs else "failed" if report["errors"] else "success"
    saved_model_path = None
    if model_path:
        try:
            project.extra["image_generation_export"] = {"model_path": str(model_path), "status": status}
            atomic_bytes(model_path, json.dumps(to_wire(project), ensure_ascii=False, indent=2).encode(),
                         root=root, overwrite=values["overwrite"], protected=protected)
            saved_model_path = str(model_path)
        except Exception as error:
            report["errors"].append({"code": getattr(error, "code", "IMAGE_MODEL_SAVE_FAILED"), "message": safe_message(error)})
            if status != "cancelled":
                status = "partial" if outputs else "failed"
    return {"status": status, "model": project, "files": outputs, "model_path": saved_model_path, "report": report}
