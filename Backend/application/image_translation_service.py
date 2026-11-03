"""Seven-stage image workflow with recoverable, independently usable outputs."""
from dataclasses import replace
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.application.image_workflow import record_image_stage
from Backend.core.log_system import redact
from Backend.core.protocol import to_wire


def _checkpoint(project, options, stage):
    """Persist recoverable stage models separately from final rendered exports."""
    if not options["save_model"]:
        return None
    root = Path(options["output_dir"]).resolve()
    destination = root / ".ainiee" / "checkpoints" / project.project_id / f"{stage}.json"
    temporary = None
    try:
        if not destination.resolve().is_relative_to(root):
            raise ValueError("checkpoint escaped output directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.resolve().is_relative_to(root):
            raise ValueError("checkpoint escaped output directory")
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                suffix=".tmp", delete=False) as writer:
            temporary = Path(writer.name)
            json.dump(to_wire(project), writer, ensure_ascii=False, indent=2)
        temporary.replace(destination)
    except (OSError, ValueError) as error:
        raise PipelineError("IMAGE_CHECKPOINT_FAILED", "无法保存图片处理中间模型", 400) from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return str(destination)


def translate_image(path, *, read_options=None, ocr=None, translation=None, output=None, context=None):
    from Backend.application.image_read_service import read_image
    from Backend.application.ocr_service import ocr_model
    from Backend.application.image_write_service import validate_image_options, validate_image_targets
    from Backend.application.image_render_service import repair_images, render_images, export_images
    from Backend.application.translation_service import resolve_translation_config, translate_model
    from Backend.domain.config.ocr_config import resolve_ocr_config

    context = context or ExecutionContext()
    # Validate credentials, destination collisions and checkpoint access before
    # issuing any paid request. Configuration itself is never stored in models.
    ocr_config = resolve_ocr_config(ocr)
    translation_config = resolve_translation_config(translation)
    options = validate_image_options(output)
    read_result = read_image(path, read_options, context=context)
    project = read_result["model"]
    read_report = read_result["report"]
    reports = {"read": read_report, "detect": read_report.get("detection", {})}
    initial = read_report.get("stage_status", {})
    outcomes = {"read": initial.get("read", read_result["status"]),
                "detect": initial.get("detect", read_result["status"]),
                **{stage: "pending" for stage in ("ocr", "translation", "repair", "render", "export")}}
    checkpoints = {}
    checkpoint_errors = []
    checkpoint = _checkpoint(project, options, "detect")
    if checkpoint:
        checkpoints["read"] = checkpoints["detect"] = checkpoint
    files, model_path = [], checkpoint

    def response(status, stage):
        return {"status": status, "model": project, "files": files, "model_path": model_path,
                "report": {"stage": stage, "stage_status": outcomes,
                           "checkpoints": checkpoints, "checkpoint_errors": checkpoint_errors, **reports}}

    if read_result["status"] in ("cancelled", "failed"):
        return response(read_result["status"], "detect")
    if read_report.get("operation_errors"):
        return response("failed", "detect")
    options = validate_image_targets(project, options)

    def stage_context(stage):
        callback = context.on_progress
        scoped = replace(context, on_progress=(
            (lambda progress: callback({**progress, "stage": stage})) if callback else None
        ))
        if stage in ("ocr", "translation", "repair", "render"):
            prepared_model = {}

            def prepared(model):
                nonlocal project
                project = model
                prepared_model["model"] = model
                if context.on_model_prepared:
                    context.on_model_prepared(model)

            def completed(*args):
                nonlocal model_path
                if "model" in prepared_model:
                    try:
                        progress_path = _checkpoint(prepared_model["model"], options, stage + "-progress")
                    except PipelineError as error:
                        checkpoint_errors.append({"stage": stage, "code": error.code,
                                                  "message": error.message})
                        raise
                    if progress_path:
                        checkpoints[stage + "-progress"] = progress_path
                        model_path = progress_path
                if context.on_batch_complete:
                    context.on_batch_complete(*args)

            scoped = replace(scoped, on_model_prepared=prepared, on_batch_complete=completed)
        return scoped

    for stage in ("ocr", "translation", "repair", "render", "export"):
        if context.is_cancelled():
            outcomes[stage] = "cancelled"
            return response("cancelled", stage)
        try:
            record_image_stage(project, stage, "running")
            if stage == "ocr":
                result = ocr_model(project, ocr_config, context=stage_context(stage))
            elif stage == "translation":
                result = translate_model(project, translation_config, context=stage_context(stage))
            else:
                service = {"repair": repair_images, "render": render_images, "export": export_images}[stage]
                result = service(project, options, context=stage_context(stage))
                if stage == "export":
                    files = result["files"]
                    model_path = result.get("model_path") or model_path
            project = result["model"]
            record_image_stage(project, stage, result["status"])
            reports[stage], outcomes[stage] = result["report"], result["status"]
            if stage != "export":
                checkpoint = _checkpoint(project, options, stage)
                if checkpoint:
                    checkpoints[stage] = checkpoint
                    model_path = checkpoint
            if result["report"].get("operation_errors"):
                return response("failed" if result["status"] == "success" else result["status"], stage)
            if result["status"] in ("cancelled", "failed"):
                return response(result["status"], stage)
        except Exception as error:
            detail = {"code": getattr(error, "code", "IMAGE_STAGE_FAILED"), "message": redact(str(error))}
            if detail["code"] == "IMAGE_CHECKPOINT_FAILED":
                # A paid stage already returned successfully. Preserve its
                # usage/report and newest in-memory model for client recovery.
                checkpoint_errors.append({"stage": stage, **detail})
            else:
                reports[stage] = {"errors": [detail]}
                outcomes[stage] = "failed"
                record_image_stage(project, stage, "failed")
            return response("failed", stage)
    status = "success" if all(value == "success" for value in outcomes.values()) else "partial"
    return response(status, "completed")
