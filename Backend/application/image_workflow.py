"""Persistent stage outcomes shared by the image API and media workspace."""
from datetime import datetime, timezone


IMAGE_STAGES = ("read", "detect", "recognize", "translate", "repair", "render", "export")


def record_image_stage(model, stage, status):
    """Invalidate later UI outcomes whenever an earlier stage is executed."""
    stage = {"ocr": "recognize", "translation": "translate", "preview": "render"}.get(stage, stage)
    if stage not in IMAGE_STAGES:
        return
    extra = model.setdefault("extra", {}) if isinstance(model, dict) else model.extra
    workflow = extra.setdefault("media_workflow", {})
    states = workflow.setdefault("stages", {})
    for dependent in IMAGE_STAGES[IMAGE_STAGES.index(stage) + 1:]:
        states.pop(dependent, None)
    states[stage] = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
