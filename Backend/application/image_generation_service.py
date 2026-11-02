"""Serial image-to-image translation with durable, fee-aware recovery."""
import copy
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.paths import project_cache_root
from Backend.domain.config.image_generation_config import resolve_image_generation_config
from Backend.domain.models.intermediate import parse_model
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.images.source import verified_image
from Backend.infrastructure.image_generation.artifacts import (
    atomic_bytes, atomic_json, generation_artifact_current, verified_generated_image,
)
from Backend.infrastructure.image_generation.dashscope import request_generation, download_image, safe_message
from Backend.infrastructure.image_generation.prompts import prepare_generation


def _state_directory(project, file):
    root = (project_cache_root() / "ImageGeneration").resolve()
    destination = (root / project.project_id / file.file_id).resolve()
    if not destination.is_relative_to(root):
        raise PipelineError("IMAGE_GENERATION_STORAGE_FAILED", "生成缓存目录越界", 400)
    destination.mkdir(parents=True, exist_ok=True)
    return root, destination


def _read_state(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError):
        raise PipelineError("IMAGE_GENERATION_JOURNAL_INVALID", "生成请求记录无法读取，未重新发送付费请求", 409) from None


def _output(file, state):
    return {"file_id": file.file_id, "path": state["artifact"]["path"], "format": "png",
            "artifacts": {"image": copy.deepcopy(state["artifact"])}, "request_id": state.get("request_id", "")}


def _accumulate_usage(report, usage):
    # Dimensions and billing tier labels describe one image, not additive usage.
    for key, value in usage.items():
        if type(value) in (int, float) and key not in ("width", "height", "input_width", "input_height", "output_width", "output_height"):
            report["usage"][key] = report["usage"].get(key, 0) + value


def generate_image_model(model, config=None, context=None):
    project = parse_model(model)
    resolved = resolve_image_generation_config(config)
    context = context or ExecutionContext()
    files = [file for file in project.files.values() if file.media_type == "image"]
    if not files:
        raise PipelineError("IMAGE_GENERATION_NO_IMAGES", "中间模型中没有图片", 400)
    selected = {row["file_id"] for row in resolved.replacements}
    if selected - {file.file_id for file in files}:
        raise PipelineError("IMAGE_GENERATION_CONFIG_ERROR", "替换清单含不属于此模型的file_id", 422)
    project.extra["image_translation_mode"] = "generation"
    settings = {key: getattr(resolved, key) for key in ("source_language", "target_language", "text_mode", "prompt")}
    project.extra["image_generation_options"] = dict(settings)
    report = {"total": len(files), "succeeded": 0, "skipped": 0, "failed": 0, "cancelled": False,
              "cancelled_files": 0, "files": [], "errors": [], "warnings": [], "operation_errors": [],
              "usage": {"requests": 0, "downloads": 0}}
    outputs = []
    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception as error:
            report["operation_errors"].append({"code": "IMAGE_GENERATION_CHECKPOINT_FAILED", "message": safe_message(error, resolved.api_key)})
            return {"status": "failed", "model": project, "report": report, "files": outputs}
    protected = {os.path.normcase(str(Path(file.source_ref["path"]).resolve())) for file in project.files.values() if file.source_ref.get("path")}
    processed = 0
    for file in files:
        if context.is_cancelled():
            break
        identity = {"file_id": file.file_id, "path": file.storage_path}
        if resolved.text_mode == "specified" and selected and file.file_id not in selected:
            report["skipped"] += 1
            report["files"].append({**identity, "status": "skipped", "reason": "not_selected"})
            processed += 1
            continue
        state, ledger, root = {}, None, None
        paid_started = False

        def checkpoint(*, notify=True):
            state["updated_at_ns"] = time.time_ns()
            file.extra["image_generation"] = state
            try:
                atomic_json(ledger, state, root=root)
            except Exception as error:
                raise PipelineError("IMAGE_GENERATION_CHECKPOINT_FAILED", "无法持久保存生成请求记录，已停止继续处理", 500) from error
            if notify and context.on_batch_complete:
                try:
                    context.on_batch_complete(file.items, file.storage_path, {"operation": "image_generation", "status": state["status"], "usage": dict(report["usage"])})
                except Exception as error:
                    report["operation_errors"].append({"code": "IMAGE_GENERATION_CHECKPOINT_FAILED", "message": safe_message(error, resolved.api_key)})
                    context.cancel()
                    raise PipelineError("IMAGE_GENERATION_CHECKPOINT_FAILED", "生成结果已记录，但工作区保存回调失败", 500) from error

        try:
            image, source = verified_image(file)
            try:
                prepared = prepare_generation(file, image, resolved)
            finally:
                image.close()
            root, directory = _state_directory(project, file)
            ledger = directory / "state.json"
            persisted = _read_state(ledger)
            in_model = file.extra.get("image_generation", {})
            candidates = [s for s in (persisted, in_model) if isinstance(s, dict) and s.get("source_sha256") == file.source_ref["sha256"]]
            latest = max(candidates, key=lambda s: s.get("updated_at_ns", 0), default={})
            if not resolved.regenerate and latest.get("status") in ("request_in_flight", "unknown"):
                state = copy.deepcopy(latest)
                file.extra["image_generation"] = state
                raise PipelineError("IMAGE_GENERATION_UNKNOWN", "上次生成结果未知；为避免重复计费，需检查请求记录后显式重新生成", 409)
            matches = [s for s in candidates if s.get("fingerprint") == prepared["fingerprint"]]
            previous = max(matches, key=lambda s: s.get("updated_at_ns", 0), default={})
            if not resolved.regenerate and previous.get("status") == "complete":
                state = copy.deepcopy(previous)
                file.extra["image_generation"] = state
                try:
                    pixels, _ = verified_generated_image(file)
                    pixels.close()
                    report["skipped"] += 1
                    outputs.append(_output(file, state))
                    report["files"].append({**identity, "status": "skipped", "reason": "cached", "request_id": state.get("request_id", "")})
                    processed += 1
                    continue
                except PipelineError:
                    if not previous.get("result_url"):
                        raise
            reusable = (not resolved.regenerate and previous.get("result_url")
                        and previous.get("status") in ("complete", "generated_pending_download", "download_failed"))
            if reusable:
                state = copy.deepcopy(previous)
                state["status"] = "generated_pending_download"
                state.pop("error", None)
            else:
                state = {"status": "prepared", "fingerprint": prepared["fingerprint"],
                         "identity": prepared["identity"], "settings": prepared["settings"],
                         "text_source": prepared["text_source"], "text_identity": prepared["text_identity"],
                         "source_sha256": file.source_ref["sha256"], "provider_id": resolved.provider_id,
                         "model": resolved.model, "text_mode": resolved.text_mode, "attempt_id": uuid.uuid4().hex,
                         "request_id": "", "usage": {}}
                if latest.get("artifact"):
                    state["previous_artifact"] = copy.deepcopy(latest["artifact"])
                # Save a non-paid checkpoint first. A stop or callback failure
                # here leaves a safe resumable state and sends no POST.
                checkpoint()
                if context.is_cancelled():
                    break
                if file_sha256(source) != file.source_ref["sha256"]:
                    raise PipelineError("SOURCE_CHANGED", "提交生图前原图发生变化", 409)
                state["status"] = "request_in_flight"
                checkpoint(notify=False)
                if context.is_cancelled():
                    state["status"] = "prepared"
                    checkpoint()
                    break
                paid_started = True
                report["usage"]["requests"] += 1
                result = request_generation(prepared["data"], prompt=prepared["prompt"], size=prepared["size"], config=resolved.to_request_config())
                state.update(result)
                state["status"] = "generated_pending_download"
                _accumulate_usage(report, result.get("usage", {}))
                # Persist the signed result URL before any download attempt.
                checkpoint()
            # Cancellation after the paid POST does not discard its result.
            # Finish this file's download, then stop before sending another page.
            report["usage"]["downloads"] += 1
            downloaded = download_image(state["result_url"])
            destination = directory / state["fingerprint"] / f"{state['attempt_id']}.png"
            atomic_bytes(destination, downloaded["data"], root=root, protected=protected)
            artifact = {"path": str(destination), "sha256": hashlib.sha256(downloaded["data"]).hexdigest(),
                        "width": downloaded["width"], "height": downloaded["height"], "format": "png"}
            state.update(status="complete", artifact=artifact)
            state.pop("error", None)
            checkpoint()
            if file_sha256(source) != file.source_ref["sha256"]:
                report["warnings"].append({**identity, "code": "SOURCE_CHANGED", "message": "生成期间原图发生变化，已保留生成产物，请重新读取原图后处理"})
            if (artifact["width"], artifact["height"]) != (file.media_metadata["width"], file.media_metadata["height"]):
                report["warnings"].append({**identity, "code": "IMAGE_GENERATION_SIZE_CHANGED", "message": "生成图尺寸与原图不同，已分别保留尺寸信息"})
            report["succeeded"] += 1
            outputs.append(_output(file, state))
            report["files"].append({**identity, "status": "success", "request_id": state.get("request_id", ""), "resumed_download": bool(reusable)})
        except Exception as error:
            code = getattr(error, "code", "IMAGE_GENERATION_FAILED")
            detail = {"code": code, "message": safe_message(error, resolved.api_key)}
            if state and ledger is not None:
                if code == "IMAGE_GENERATION_UNKNOWN" or (paid_started and state.get("status") == "request_in_flight"):
                    state["status"] = "failed" if code == "IMAGE_GENERATION_REJECTED" else "unknown"
                elif state.get("result_url") and state.get("status") != "complete":
                    state["status"] = "download_failed"
                elif code != "IMAGE_GENERATION_CHECKPOINT_FAILED" and state.get("status") not in ("complete", "unknown"):
                    state["status"] = "failed"
                state["error"] = detail
                details = getattr(error, "details", None) or {}
                if isinstance(details, dict):
                    if details.get("request_id"):
                        state["request_id"] = details["request_id"]
                    if details.get("usage"):
                        state["usage"] = details["usage"]
                        _accumulate_usage(report, details["usage"])
                try:
                    checkpoint()
                except Exception:
                    if not report["operation_errors"]:
                        report["operation_errors"].append({"code": "IMAGE_GENERATION_CHECKPOINT_FAILED", "message": "无法保存生成状态，请保留返回的中间模型"})
                    context.cancel()
            report["failed"] += 1
            report["errors"].append({**identity, **detail})
            report["files"].append({**identity, "status": "failed", **detail})
        processed += 1
        if context.on_progress:
            try:
                context.on_progress({"operation": "image_generation", "current": processed, "total": len(files),
                                     "succeeded": report["succeeded"], "skipped": report["skipped"], "failed": report["failed"]})
            except Exception as error:
                report["operation_errors"].append({"code": "IMAGE_GENERATION_CALLBACK_FAILED", "message": safe_message(error, resolved.api_key)})
                context.cancel()
    report["cancelled"] = context.is_cancelled() and not report["operation_errors"]
    report["cancelled_files"] = max(0, len(files) - processed) if context.is_cancelled() else 0
    status = ("cancelled" if report["cancelled"] else "partial" if (report["failed"] or report["operation_errors"]) and (report["succeeded"] or report["skipped"])
              else "failed" if report["failed"] or report["operation_errors"] else "success")
    return {"status": status, "model": project, "files": outputs, "report": report}
