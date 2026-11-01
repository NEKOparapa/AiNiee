"""Serial audio workflow; translation retains its existing batch workers."""
from dataclasses import replace

from Backend.application.audio_read_service import read_audio
from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.application.subtitle_service import validate_subtitle_options, validate_subtitle_targets, write_subtitles
from Backend.application.transcription_service import transcribe_model
from Backend.application.translation_service import resolve_translation_config, translate_model
from Backend.core.log_system import redact
from Backend.domain.config.transcription_config import resolve_transcription_config


def translate_audio(path, *, read_options=None, transcription=None, translation=None,
                    output=None, context=None):
    """Read -> transcribe -> translate -> export, returning every stage's report.

    No global project or configuration is changed. A failed later stage returns
    the last usable model, allowing clients to resume without paying for ASR again.
    Admission and lifecycle remain the HTTP runtime's responsibility.
    """
    context = context or ExecutionContext()
    # Reject invalid provider/output settings before making a paid request.
    asr_config = resolve_transcription_config(transcription)
    translation_config = resolve_translation_config(translation)
    output_options = validate_subtitle_options(output)
    read_result = read_audio(path, read_options)
    project = read_result["model"]
    # The audio file list is enough to plan destinations, even before ASR fills
    # items. Known collisions must not incur provider charges.
    output_options = validate_subtitle_targets(project, output_options)
    reports = {"read": read_result["report"]}
    outcomes = {"read": read_result["status"]}
    files = []

    def response(status, stage):
        return {"status": status, "model": project, "files": files,
                "report": {"stage": stage, "stage_status": outcomes, **reports}}

    def progress_context(stage):
        callback = context.on_progress
        return replace(context, on_progress=(
            (lambda progress: callback({**progress, "stage": stage})) if callback else None
        ))

    for stage in ("transcription", "translation", "write"):
        if context.is_cancelled():
            return response("cancelled", stage)
        try:
            if stage == "transcription":
                result = transcribe_model(project, asr_config, context=progress_context(stage))
                project = result["model"]
            elif stage == "translation":
                result = translate_model(project, translation_config, context=progress_context(stage))
                project = result["model"]
            else:
                result = write_subtitles(project, output_options)
                files = result["files"]
            reports[stage] = result["report"]
            outcomes[stage] = result["status"]
            # A failed progress/result callback may also set the shared cancel
            # event. Preserve the actual stage failure instead of relabelling
            # it as a user cancellation at the next loop iteration.
            if result["report"].get("operation_errors"):
                return response(result["status"] if result["status"] in ("partial", "failed") else "failed", stage)
            if result["status"] in ("cancelled", "failed"):
                return response(result["status"], stage)
        except Exception as error:
            # Only stage inputs/configuration fail before reading. Afterwards,
            # retain the completed transcript/translations with a safe error.
            detail = {"code": error.code if isinstance(error, PipelineError) else "AUDIO_STAGE_FAILED",
                      "message": redact(str(error))}
            reports[stage] = {"errors": [detail]}
            outcomes[stage] = "failed"
            return response("failed", stage)

    status = "success" if all(value == "success" for value in outcomes.values()) else "partial"
    return response(status, "completed")
