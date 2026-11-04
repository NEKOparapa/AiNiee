"""Derive media workflow states from snapshots without scheduling any work."""


def _object(value):
    return value if isinstance(value, dict) else {}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def file_workspace(workspace, file_id=None):
    """Restrict prerequisite checks to a selected file without editing the snapshot."""
    if file_id is None:
        return workspace
    model = _object(_object(workspace).get("model"))
    return {**_object(workspace), "model": {**model, "files": {
        path: file for path, file in _object(model.get("files")).items()
        if file.get("file_id") == file_id
    }}, "files": [asset for asset in _object(workspace).get("files", [])
                  if asset.get("file_id") == file_id]}


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
    if kind in ("audio", "video") and _has_checkpoint(file):
        return False
    record = _object(extra.get("transcription"))
    source_hash = _object(file.get("source_ref")).get("sha256")
    complete = (record.get("status") == "complete" and _text(source_hash)
                and record.get("source_sha256") == source_hash)
    # Older audio models can have usable segments without transcription metadata.
    return complete or (kind in ("audio", "video") and any(_text(item.get("source_text")) for item in _items(file)))


def _empty_recognized(file, kind):
    return _recognized(file, kind) and not any(_text(item.get("source_text")) for item in _items(file))


def _translated(item):
    return item.get("translation_status") in (1, 2) and _text(item.get("translated_text"))


def _step(status, detail):
    return {"status": status, "detail": detail, "active": False}


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


def workflow_states(workspace, kind, mode=None, generation_states=None):
    """Describe generated pages or audio subtitles without scheduling work."""
    files = _files(workspace, kind)
    stages = ("generate", "export") if kind == "image" else ("recognize", "translate")
    if not files:
        return {stage: _step("待导入", "请先导入媒体文件。") for stage in stages}
    assets = _assets(workspace)
    if kind == "image":
        ready = sum(_text(assets.get(file.get("file_id"), {}).get("translated_url")) for file in files)
        return {"generate": _generation_state(files, assets, generation_states),
                "export": _step("待导出" if ready else "待生成", f"已有 {ready} / {len(files)} 页译图可导出。")}
    recognized = sum(_recognized(file, kind) for file in files)
    resumable = any(_has_checkpoint(file) for file in files)
    recognition_status = ("已完成" if recognized == len(files) else "部分完成" if recognized
                          else "待继续" if resumable else "待开始")
    recognition_detail = f"已识别 {recognized} / {len(files)} 个文件"
    if resumable:
        recognition_detail += "；未完成的音频分片可继续处理"
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
    return {"recognize": _step(recognition_status, recognition_detail),
            "translate": _step(translation_status, translation_detail)}


def prerequisite_message(workspace, kind, mode, stages):
    """Explain missing inputs without starting implicit upstream work."""
    files = _files(workspace, kind)
    if not files:
        return "请先导入媒体文件。"
    selected = set(stages)
    if kind == "image":
        if selected - {"generate", "preview", "export"}:
            return "图片翻译仅支持单步生成译图。"
        if "export" in selected and "generate" not in selected:
            if not any(_text(asset.get("translated_url")) for asset in _assets(workspace).values()):
                return "尚无有效译图，请先生成译图后再导出。"
        return ""
    items = [item for file in files for item in _items(file)]
    source_ready = any(_text(item.get("source_text")) for item in items)
    empty_ready = any(_empty_recognized(file, kind) for file in files)
    if "translate" in selected and "recognize" not in selected and not (source_ready or empty_ready):
        return "尚无可翻译字幕，请先转录字幕或勾选“转录”步骤。"
    return ""
