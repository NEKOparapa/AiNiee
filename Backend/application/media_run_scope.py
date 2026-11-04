"""Isolate a media file for processing and merge every checkpoint into its project."""
import copy

from Backend.application.pipeline_common import PipelineError
from Backend.core.protocol import to_wire


class MediaRunScope:
    def __init__(self, workspace, stage, file_id=None):
        self.stage = stage
        self.original = workspace["model"]
        self.path = None
        self.partial = False
        self.model = self.original
        if file_id is None:
            return
        if stage not in ("recognize", "translate", "generate"):
            raise PipelineError("INVALID_MEDIA_STAGE", "单文件处理仅支持转录、翻译或生成译图", 422)
        self.path = next((path for path, file in self.original["files"].items()
                          if file["file_id"] == file_id), None)
        if self.path is None:
            raise PipelineError("MEDIA_FILE_NOT_FOUND", "所选文件不属于此媒体项目，请刷新后重试", 404)
        file = self.original["files"][self.path]
        if stage == "translate" and not any(str(item.get("source_text") or "").strip()
                                             for item in file.get("items", [])):
            raise PipelineError("MEDIA_TRANSCRIPT_REQUIRED", "所选文件尚无可翻译字幕，请先完成转录", 409)
        self.partial = len(self.original["files"]) > 1
        self.model = {key: copy.deepcopy(value) for key, value in self.original.items() if key != "files"}
        self.model["files"] = {self.path: copy.deepcopy(file)}

    def configure(self, config):
        if self.partial and self.stage == "translate":
            target = self.original.get("translation_context", {}).get("target_language")
            if target:
                if config.get("target_language", target) != target:
                    raise PipelineError("TARGET_LANGUAGE_CONFLICT", "单文件重译需使用项目当前目标语言；更换语言请执行整个项目的翻译", 409)
                # An omitted target must not silently inherit a different global default.
                config = {**config, "target_language": target}
        return config

    def merge(self, model):
        result = to_wire(model)
        if not self.partial:
            return result
        if (set(result["files"]) != {self.path}
                or result["files"][self.path]["file_id"] != self.original["files"][self.path]["file_id"]):
            raise PipelineError("MEDIA_MODEL_MISMATCH", "单文件处理结果与所选文件不匹配", 409)
        merged = copy.deepcopy(self.original)
        file = copy.deepcopy(result["files"][self.path])
        merged["files"][self.path] = file
        if self.stage == "generate":
            project_options = self.original.get("extra", {}).get("image_generation_options", {})
            settings = result.get("extra", {}).get("image_generation_options", {})
            if settings != project_options:
                # A new prompt for one image must not invalidate other previews.
                file.setdefault("extra", {})["image_generation_selection"] = {
                    "project_options": copy.deepcopy(project_options), "settings": copy.deepcopy(settings),
                }
        elif self.stage == "translate":
            if not merged.get("translation_context", {}).get("target_language"):
                merged["translation_context"] = copy.deepcopy(result.get("translation_context", {}))
            # Per-operation counts describe only this file, not the full project.
            merged["stats_data"] = None
        elif self.stage == "recognize":
            # ASR allocates new indices within its isolated model. Keep existing
            # indices where possible and move collisions beyond the project range.
            occupied = {item["text_index"] for path, entry in self.original["files"].items()
                        if path != self.path for item in entry.get("items", [])}
            next_index = max(occupied | {item["text_index"] for item in file.get("items", [])}, default=-1) + 1
            for item in file.get("items", []):
                if item["text_index"] in occupied:
                    item["text_index"] = next_index
                    next_index += 1
                occupied.add(item["text_index"])
            merged["stats_data"] = None
        return merged
