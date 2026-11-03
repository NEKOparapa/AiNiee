"""Derive media workflow states from snapshots without scheduling any work."""


def _object(value):
    return value if isinstance(value, dict) else {}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _items(file):
    values = file.get("items", [])
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def _files(workspace, kind):
    values = _object(_object(_object(workspace).get("model")).get("files"))
    return [file for file in values.values() if isinstance(file, dict)
            and file.get("media_type", kind) in ("", kind)]


def _assets(workspace):
    values = _object(workspace).get("files", [])
    return {entry.get("file_id"): entry for entry in values
            if isinstance(entry, dict) and isinstance(entry.get("file_id"), str)} if isinstance(values, list) else {}


def _has_checkpoint(file):
    return isinstance(_object(file.get("extra")).get("transcription_checkpoint"), dict)


def _recognized(file, kind):
    extra = _object(file.get("extra"))
    if kind == "audio" and _has_checkpoint(file):
        return False
    record = _object(extra.get("ocr" if kind == "image" else "transcription"))
    source_hash = _object(file.get("source_ref")).get("sha256")
    complete = (record.get("status") == "complete" and _text(source_hash)
                and record.get("source_sha256") == source_hash)
    # Older audio models can have usable segments without transcription metadata.
    return complete or (kind == "audio" and any(_text(item.get("source_text")) for item in _items(file)))


def _empty_recognized(file, kind):
    return _recognized(file, kind) and not any(_text(item.get("source_text")) for item in _items(file))


def _translated(item):
    return item.get("translation_status") in (1, 2) and _text(item.get("translated_text"))


def _renderable(item):
    locator = _object(item.get("locator"))
    polygon = locator.get("polygon")
    return (_translated(item) and locator.get("kind") == "image"
            and isinstance(polygon, list) and len(polygon) >= 3)


def _step(status, detail):
    return {"status": status, "detail": detail, "active": False}


def _detected(file):
    record = _object(_object(file.get("extra")).get("text_detection"))
    source_hash = _object(file.get("source_ref")).get("sha256")
    return (record.get("status") == "complete" and _text(source_hash)
            and record.get("source_sha256") == source_hash)


def _artifact_ready(file, assets, stage):
    record = _object(_object(_object(file.get("extra")).get("image_pipeline")).get(stage))
    artifact = _object(_object(record.get("artifacts")).get("image"))
    source_hash = _object(file.get("source_ref")).get("sha256")
    url = "repaired_url" if stage == "repair" else "translated_url"
    return (record.get("status") in ("complete", "partial") and _text(assets.get(file.get("file_id"), {}).get(url))
            and _text(artifact.get("path")) and _text(artifact.get("sha256"))
            and _text(source_hash) and record.get("source_sha256") == source_hash)


def _repair_state(files, assets):
    ready = [file for file in files if _artifact_ready(file, assets, "repair")]
    partial = sum(_object(_object(_object(file.get("extra")).get("image_pipeline")).get("repair")).get("status") == "partial"
                  for file in ready)
    detail = f"已修复 {len(ready)} / {len(files)} 个文件"
    if partial:
        detail += f"；{partial} 个文件仍有区域需要复核"
    translatable = any(_empty_recognized(file, "image") or any(_renderable(item) for item in _items(file)) for file in files)
    status = ("待复核" if partial else "已完成" if len(ready) == len(files) else "部分完成" if ready
              else "待修复" if translatable else "待翻译")
    return _step(status, detail)


def _preview_states(files, assets, mode):
    if mode == "generation":
        return _step("不适用", "当前使用整图生成流程，无需 OCR 回填。")
    complete = partial = stale = 0
    for file in files:
        render = _object(_object(_object(file.get("extra")).get("image_pipeline")).get("render"))
        artifact = _object(_object(render.get("artifacts")).get("image"))
        source_hash = _object(file.get("source_ref")).get("sha256")
        registered = _text(assets.get(file.get("file_id"), {}).get("translated_url"))
        usable = (registered and _text(artifact.get("path")) and _text(artifact.get("sha256"))
                  and _text(source_hash) and render.get("source_sha256") == source_hash)
        complete += bool(usable and render.get("status") == "complete")
        partial += bool(usable and render.get("status") == "partial")
        stale += bool(render and not usable)
    detail = f"已完成 {complete} / {len(files)} 个文件"
    if partial:
        detail += f"；{partial} 个文件已有预览，部分文字仍需复核"
    if stale:
        detail += f"；{stale} 个文件的预览需要更新或恢复"
    if complete == len(files):
        status = "已完成"
    elif partial:
        status = "待复核"
    elif complete:
        status = "部分完成"
    elif stale:
        status = "待更新"
    else:
        ready = any(_empty_recognized(file, "image") or any(_renderable(item) for item in _items(file))
                    for file in files)
        status = "待回填" if ready else "待翻译"
    return _step(status, detail)


def _generation_state(files, assets, generation_states):
    states = []
    for file in files:
        identifier = file.get("file_id")
        if isinstance(generation_states, dict):
            state = generation_states.get(identifier, "pending")
        else:
            state = assets.get(identifier, {}).get("generation_status", "pending")
        states.append(state)
    complete = states.count("complete")
    detail = f"已完成 {complete} / {len(files)} 页"
    if complete == len(files):
        status = "已完成"
    elif "stale" in states:
        status = "待更新"
        detail += "；部分译图与当前要求不一致"
    elif any(state in ("unknown", "request_in_flight") for state in states):
        status = "待确认"
        detail += "；存在结果尚未确认的生成请求"
    elif any(state in ("generated_pending_download", "download_failed", "unavailable") for state in states):
        status = "待恢复"
        detail += "；部分译图需要继续下载或恢复"
    elif "failed" in states:
        status = "待重试"
    else:
        status = "部分完成" if complete else "待生成"
    return _step(status, detail)


def workflow_states(workspace, kind, mode="ocr", generation_states=None):
    """Describe existing results; callers own active-stage and unsaved-edit overrides.

    ``generation_states`` maps file IDs to the caller's verified generation state.
    Preview URLs attest to registered snapshot results, not current disk health.
    Locally edited OCR rows must invalidate the caller's preview-step display until
    a fresh saved snapshot arrives. No status here instructs callers to skip work.
    """
    files = _files(workspace, kind)
    if not files:
        return {stage: _step("待导入", "请先导入媒体文件。")
                for stage in ("read", "detect", "recognize", "translate", "repair", "render", "export", "preview", "generate")}
    recognized = sum(_recognized(file, kind) for file in files)
    resumable = (any(_has_checkpoint(file) for file in files) if kind == "audio" else
                 any(_object(_object(file.get("extra")).get("ocr_regions")).get("status") in ("pending", "partial", "running", "cancelled", "failed")
                     for file in files))
    recognition_status = ("已完成" if recognized == len(files) else "部分完成" if recognized
                          else "待继续" if resumable else "待开始")
    recognition_detail = f"已识别 {recognized} / {len(files)} 个文件"
    if resumable:
        recognition_detail += "；未完成的音频分片可继续处理" if kind == "audio" else "；未完成文字区域可继续识别"
    items = [item for file in files for item in _items(file)]
    source_items = [item for item in items if _text(item.get("source_text"))]
    candidates = [item for item in source_items if item.get("translation_status", 0) in (0, 1, 2)]
    completed = sum(_translated(item) for item in candidates)
    review = sum(item.get("translation_status") == 8 for item in items)
    excluded = sum(item.get("translation_status") == 7 for item in items)
    all_excluded = bool(source_items) and all(item.get("translation_status") == 7 for item in source_items)
    unread = sum(not _recognized(file, kind) and not any(_text(item.get("source_text")) for item in _items(file))
                 for file in files)
    if review:
        translation_status = "待复核"
    elif candidates:
        translation_status = ("已完成" if completed == len(candidates) and not unread else
                              "部分完成" if completed else "待翻译")
    else:
        translation_status = "待识别" if unread else "全部已排除" if all_excluded else "无需翻译"
    translation_detail = f"已完成 {completed} / {len(candidates)} 条"
    if excluded:
        translation_detail += f"；已排除 {excluded} 条"
    if review:
        translation_detail += f"；待复核 {review} 条"
    if unread:
        translation_detail += f"；{unread} 个文件尚无识别结果"
    elif not candidates and not review:
        translation_detail += ("；已有原文，但全部已排除，当前无可翻译条目" if all_excluded
                               else "；没有待翻译原文")
    assets = _assets(workspace)
    result = {
        "recognize": _step(recognition_status, recognition_detail),
        "translate": _step(translation_status, translation_detail),
        "preview": (_preview_states(files, assets, mode) if kind == "image" else
                    _step("不适用", "字幕可直接校润和导出，无需图片回填。")),
        "generate": (_generation_state(files, assets, generation_states) if kind == "image" else
                     _step("不适用", "音频项目不使用图像生成。")),
    }
    if kind == "image" and mode != "generation":
        detected = sum(_detected(file) for file in files)
        regions = sum(len(_object(_object(file.get("extra")).get("text_detection")).get("regions", []))
                      for file in files if _detected(file))
        result["read"] = _step("已完成", f"已导入 {len(files)} 张图片")
        result["detect"] = _step("已完成" if detected == len(files) else "部分完成" if detected else "待检测",
                                  f"已检测 {detected} / {len(files)} 张图片，共 {regions} 个文字区域")
        result["repair"] = _repair_state(files, assets)
        result["render"] = dict(result["preview"])
        if result["render"]["status"] in ("待回填", "待翻译"):
            result["render"]["status"] = "待渲染" if any(_artifact_ready(file, assets, "repair") for file in files) else "待修复"
        model = _object(_object(workspace).get("model"))
        workflow = _object(_object(model.get("extra")).get("media_workflow"))
        stage = _object(workflow.get("stages"))
        for name in ("read", "detect", "recognize", "translate", "repair", "render"):
            outcome = _object(stage.get(name)).get("status")
            if outcome in ("failed", "cancelled", "partial") and (name == "read" or result[name]["status"] != "已完成"):
                result[name]["status"] = {"failed": "待重试", "cancelled": "待继续", "partial": "部分完成"}[outcome]
        exported = _object(stage.get("export")).get("status")
        rendered = sum(_artifact_ready(file, assets, "render") for file in files)
        status = ("已完成" if exported == "success" and rendered == len(files) else
                  "部分完成" if exported == "partial" and rendered else "待导出" if rendered else "待渲染")
        result["export"] = _step(status, "导出已渲染的译图；修改译文后请先重新修复和渲染。")
    return result


def prerequisite_message(workspace, kind, mode, stages):
    """Explain a missing selected step's inputs, allowing usable partial results."""
    files = _files(workspace, kind)
    if not files:
        return "请先导入媒体文件。"
    selected = set(stages)
    items = [item for file in files for item in _items(file)]
    source_ready = any(_text(item.get("source_text")) for item in items)
    empty_ready = any(_empty_recognized(file, kind) for file in files)
    assets = _assets(workspace)
    if kind == "image" and mode != "generation" and "recognize" in selected and "detect" not in selected:
        if not any(_detected(file) for file in files):
            return "尚无文本检测结果，请勾选“文本检测”后继续；新导入图片会自动检测。"
    if "translate" in selected and "recognize" not in selected and not (source_ready or empty_ready):
        return ("尚无可翻译原文，请先识别原文或勾选“识别”步骤。" if kind == "image" else
                "尚无可翻译字幕，请先转录字幕或勾选“转录”步骤。")
    if kind == "image" and mode != "generation" and selected.intersection(("repair", "preview")) and "translate" not in selected:
        if not any(_renderable(item) for item in items) and not empty_ready:
            return "尚无可处理的译文，请先完成翻译或勾选“AI 翻译”步骤。"
    if kind == "image" and mode != "generation" and "render" in selected and "repair" not in selected:
        if not any(_artifact_ready(file, assets, "repair") for file in files):
            return "尚无有效修复图，请先完成图像修复或勾选“图像修复”步骤。"
    if kind == "image" and mode != "generation" and "export" in selected and not selected.intersection(("render", "preview")):
        if not any(_artifact_ready(file, assets, "render") for file in files):
            return "尚无有效译图，请先完成图像修复和文字渲染，再导出。"
    return ""
