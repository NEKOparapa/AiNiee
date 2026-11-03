"""Serial read -> image generation -> export, sharing the public model services."""
from dataclasses import replace
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.log_system import redact
from Backend.core.paths import project_cache_root
from Backend.core.protocol import to_wire


def _checkpoint(model):
    model = to_wire(model)
    root = (project_cache_root() / "ImageGeneration").resolve()
    destination = (root / model["project_id"] / "progress-model.json").resolve()
    if not destination.is_relative_to(root) or destination.parent == root:
        raise PipelineError("IMAGE_GENERATION_CHECKPOINT_FAILED", "生图中间模型路径无效", 422)
    temporary = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, suffix=".tmp", delete=False) as writer:
            temporary = Path(writer.name)
            json.dump(model, writer, ensure_ascii=False, indent=2)
        temporary.replace(destination)
    except OSError as error:
        raise PipelineError("IMAGE_GENERATION_CHECKPOINT_FAILED", "无法保存生图中间模型", 500) from error
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return str(destination)


def generate_with_checkpoint(model, config=None, context=None):
    from Backend.application.image_generation_service import generate_image_model
    context = context or ExecutionContext()
    latest = {"model": model, "path": None}

    def prepared(project):
        latest["model"] = project
        latest["path"] = _checkpoint(project)
        if context.on_model_prepared:
            context.on_model_prepared(project)

    def completed(*args):
        latest["path"] = _checkpoint(latest["model"])
        if context.on_batch_complete:
            context.on_batch_complete(*args)

    scoped = replace(context, on_model_prepared=prepared, on_batch_complete=completed)
    result = generate_image_model(model, config, context=scoped)
    try:
        result["model_path"] = _checkpoint(result["model"])
    except PipelineError as error:
        result["model_path"] = None
        result["status"] = "failed"
        result["report"].setdefault("operation_errors", []).append({"code": error.code, "message": error.message})
    return result


def translate_image_generation(path, *, read_options=None, generation=None, output=None, context=None):
    from Backend.application.image_read_service import read_image
    from Backend.application.generated_image_write_service import (
        validate_generated_image_options, validate_generated_image_targets, write_generated_images,
    )
    from Backend.domain.config.image_generation_config import resolve_image_generation_config
    context = context or ExecutionContext()
    config = resolve_image_generation_config(generation)
    options = validate_generated_image_options(output)
    read = read_image(path, read_options, context=context)
    project = read["model"]
    reports, statuses = {"read": read["report"]}, {"read": read["status"]}
    files, model_path = [], _checkpoint(project)

    def response(status, stage):
        return {"status": status, "model": project, "files": files, "model_path": model_path,
                "report": {"stage": stage, "stage_status": statuses, **reports}}

    if read["status"] == "cancelled":
        return response("cancelled", "read")
    if read["report"].get("operation_errors") or not project.files:
        return response("failed", "read")
    options = validate_generated_image_targets(project, options)

    for stage in ("generation", "write"):
        if context.is_cancelled():
            return response("cancelled", stage)
        try:
            if stage == "generation":
                result = generate_with_checkpoint(project, config, context=context)
            else:
                result = write_generated_images(project, options, context=context)
            files = result.get("files", [])
            project = result["model"]
            model_path = result.get("model_path") if stage == "generation" else result.get("model_path") or model_path
            reports[stage], statuses[stage] = result["report"], result["status"]
            if result["report"].get("operation_errors"):
                return response("failed", stage)
            if result["status"] in ("cancelled", "failed"):
                return response(result["status"], stage)
        except Exception as error:
            reports[stage] = {"errors": [{"code": getattr(error, "code", "IMAGE_GENERATION_STAGE_FAILED"),
                                          "message": redact(str(error))}]}
            statuses[stage] = "failed"
            return response("failed", stage)
    return response("success" if all(value == "success" for value in statuses.values()) else "partial", "completed")
