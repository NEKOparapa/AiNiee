"""Desktop project snapshots and API proxies; persistence belongs to the backend."""
import threading
import copy
import os
from collections import defaultdict
from dataclasses import fields

from Frontend.services.protocol import to_wire
from Frontend.models.project import CacheProject


def merge_project(current, incoming):
    """Preserve item identities retained by existing Qt table pages."""
    if incoming is None or current is None or current.project_id != incoming.project_id:
        return incoming
    for field in fields(incoming):
        if field.name != "files":
            setattr(current, field.name, getattr(incoming, field.name))
    for path in list(current.files):
        if path not in incoming.files:
            del current.files[path]
    for path, new_file in incoming.files.items():
        old_file = current.files.get(path)
        if old_file is None:
            current.files[path] = new_file
            continue
        old_items = {item.text_index: item for item in old_file.items}
        items = []
        for new_item in new_file.items:
            old_item = old_items.get(new_item.text_index)
            if old_item:
                for field in fields(new_item):
                    setattr(old_item, field.name, getattr(new_item, field.name))
                items.append(old_item)
            else:
                items.append(new_item)
        for field in fields(new_file):
            setattr(old_file, field.name, items if field.name == "items" else getattr(new_file, field.name))
        old_file.__dict__.pop("items_index_dict", None)
    current.__dict__.pop("file_project_types", None)
    return current

class RemoteCacheManager:
    """A UI read model. All persistence and business mutations go to FastAPI."""
    def __init__(self, client):
        # Deliberately do not register CacheManager's local autosave/event handlers.
        self.client = client
        self.client.cache = self
        self.project = None
        self.file_lock = threading.RLock()
        self.apply_snapshot(client.request("GET", "/api/project")["project"])

    def apply_snapshot(self, data):
        project = CacheProject.from_dict(data) if data is not None else None
        with self.file_lock:
            self.project = merge_project(self.project, project)

    def _call(self, method, *args, **kwargs):
        response = self.client.request("POST", f"/api/cache/{method}", json={
            "args": to_wire(args), "kwargs": to_wire(kwargs),
            "project_id": self.project.project_id if self.project else None,
        }, timeout=600)
        if method != "list_project_histories":
            # A delayed read-only history refresh must not replace a newer
            # project loaded by another request or WebSocket notification.
            self.apply_snapshot(response["project"])
        return response["result"]

    def load_from_project(self, project):
        # RemoteFileReader already loaded and persisted this exact project server-side.
        self.apply_snapshot(project.to_dict())

    def load_from_project_id(self, project_id):
        return self._call("load_from_project_id", project_id)

    def load_from_file(self, output_path=""):
        return self._call("load_from_file", output_path)

    def list_project_histories(self, limit=None, prune=False):
        # None delegates the history retention limit to the backend.
        options = {"prune": prune}
        if limit is not None:
            options["limit"] = limit
        return self._call("list_project_histories", **options)

    def delete_project_cache(self, project_id):
        return self._call("delete_project_cache", project_id)

    def save_to_file(self):
        return self._call("save_to_file")

    def require_save_to_file(self, output_path=None):
        return self.save_to_file()

    def reset_project_status(self, task_mode):
        return self._call("reset_project_status", task_mode)

    def set_analysis_data(self, analysis_data):
        return self._call("set_analysis_data", analysis_data)

    def clear_analysis_data(self):
        return self._call("clear_analysis_data")

    def update_item_text(self, storage_path, text_index, field_name, new_text):
        return self._call("update_item_text", storage_path, text_index, field_name, new_text)

    def update_generated_translation(self, storage_path, text_index, new_text, translation_status):
        # The backend persists generated results before emitting a table update.
        # Updating this read model must never send the event back over HTTP.
        with self.file_lock:
            file = self.project.get_file(storage_path) if self.project else None
            if file is not None:
                item = file.get_item(text_index)
                item.translated_text = new_text
                item.translation_status = translation_status if new_text and new_text.strip() else 0

    def get_item_count(self):
        return self.project.count_items() if self.project else 0

    def get_item_count_by_status(self, status):
        return self.project.count_items(status) if self.project else 0

    def get_file_hierarchy(self):
        hierarchy = defaultdict(list)
        for path in self.project.files if self.project else ():
            directory, name = os.path.split(path)
            hierarchy[directory or "."].append(name)
        return {path: sorted(names) for path, names in hierarchy.items()}

    def get_analysis_data(self):
        return copy.deepcopy(self.project.extra.get("analysis_v1", {})) if self.project else {}

    def search_items(self, query, scope, is_regex, search_flagged):
        result = self._call("search_items", query, scope, is_regex, search_flagged)
        return [(path, row, self.project.get_file(path).get_item(item["text_index"])) for path, row, item in result]

    def run_check(self, kind, params):
        response = self.client.request("POST", f"/api/check/{kind}", json=params, timeout=600)
        self.apply_snapshot(response["project"])
        return response["result"]

class RemoteFileReader:
    def __init__(self, client):
        self.client = client

    def get_support_project_types(self):
        return self.client.request("GET", "/api/project/types")

    def read_files(self, translation_project, label_input_path, exclude_rule_str):
        result = self.client.request("POST", "/api/project/load", json={
            "project_type": translation_project, "input_path": label_input_path,
            "exclude_rule": exclude_rule_str,
        }, timeout=600)
        return CacheProject.from_dict(result["project"])
