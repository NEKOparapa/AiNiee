"""业务操作完成后的事件通知与数据回写。"""


class OperationDispatcher:
    def __init__(self, cache, update_config_fn, notify_fn):
        self._cache = cache
        self._update_config = update_config_fn
        self._notify = notify_fn

    def commit_table_result(self, data, view):
        for index, text in data.get("updated_items", {}).items():
            self._cache.update_generated_translation(
                data["file_path"], int(index), text, data.get("translation_status", 1),
            )
        self._cache.save_to_file()
        self._notify("table.updated", {**data, "view": view})

    def commit_glossary_result(self, request, result):
        if result.get("status") not in ("success", "partial", "cancelled", "stopped"):
            return
        original_rows = {
            row["src"]: row
            for row in request.get("prompt_dictionary_data", [])
            if row.get("src") and not row.get("dst")
        }
        translations = {
            row["src"]: row["dst"]
            for row in result.get("updated_data", []) or []
            if row.get("src") and row.get("dst")
        }
        if not translations:
            return

        def update(config):
            table = next(
                (table for table in config.get("prompt_dictionary_tables", [])
                 if table["id"] == request.get("table_id")), None,
            )
            if table is not None:
                for row in table["rows"]:
                    source = row.get("src")
                    if source in translations and row == original_rows.get(source):
                        row["dst"] = translations[source]

        self._update_config(update)

    def notify_completion(self, name, request, result, *, job=None, has_error=False):
        # Persistence has finished before any completion reaches the desktop.
        # Runtime owns the error state; it only supplies the completion guard.
        payload = {key: value for key, value in result.items() if key != "model"}

        def notify(event, data):
            self._notify(event, data, job=job)

        if name == "translation":
            notify("translation.stopped", payload)
            output = result.get("output")
            output_succeeded = not isinstance(output, dict) or output.get("status") == "success"
            if result.get("status") in ("success", "partial") and not has_error and output_succeeded:
                notify("translation.completed", payload)
            if isinstance(output, dict):
                notify("project.export.completed", {"files": [], "report": {}, **output})
        elif name == "analysis":
            notify("analysis.completed", {"analysis_data": None, **payload})
        elif name.startswith("table."):
            notify("table.completed", {
                "file_path": request.get("file_path"), "updated_item_count": 0,
                "operation": name.split(".", 1)[1],
                **payload, "view": request.get("view", "basic"),
            })
        elif name == "glossary.translate":
            notify("glossary.completed", {
                "updated_data": None, **payload, "table_id": request.get("table_id"),
                "request_id": request.get("request_id"),
            })
        elif name == "api_test":
            failure = (
                [result.get("message") or "接口测试未完成"]
                if result.get("status") in ("error", "failed", "cancelled") else []
            )
            notify("api_test.completed", {"success": [], "failure": failure, **payload})
        elif name == "project.export":
            notify("project.export.completed", {"files": [], "report": {}, **payload})
