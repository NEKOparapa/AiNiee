"""Explicit media workspace operations shared by the two independent pages."""
from urllib.parse import quote


class MediaClient:
    def __init__(self, backend):
        self.backend = backend

    @property
    def headers(self):
        return dict(self.backend.headers)

    def asset_url(self, path):
        if not path:
            return ""
        if not path.startswith("/api/v2/media/"):
            raise ValueError("媒体预览地址无效")
        return self.backend.url + path

    def history(self, kind):
        return self.backend.request("GET", "/api/v2/media", params={"kind": kind})

    def load(self, workspace_id):
        return self.backend.request("GET", "/api/v2/media/" + quote(workspace_id, safe=""))

    def delete(self, workspace_id):
        return self.backend.request("DELETE", "/api/v2/media/" + quote(workspace_id, safe=""), timeout=None)

    def import_files(self, kind, paths, operation_id=None):
        payload = {"kind": kind, "paths": paths}
        if operation_id:
            payload["operation_id"] = operation_id
        return self.backend.request("POST", "/api/v2/media/import", json=payload, timeout=None)

    def save(self, workspace_id, model):
        return self.backend.request("POST", f"/api/v2/media/{quote(workspace_id, safe='')}/model",
                                    json={"model": model}, timeout=120)

    def run(self, workspace_id, stage, operation_id, config=None, options=None, *, file_id=None):
        payload = {
            "stage": stage, "operation_id": operation_id, "config": config or {}, "options": options or {},
        }
        if file_id is not None:
            payload["file_id"] = file_id
        return self.backend.request("POST", f"/api/v2/media/{quote(workspace_id, safe='')}/run",
                                    json=payload, timeout=None)

    def job(self, operation_id):
        return self.backend.request("GET", f"/api/jobs/{quote(operation_id, safe='')}", timeout=3)["job"]

    def stop(self, operation_id):
        return self.backend.request("POST", f"/api/v2/media/operations/{quote(operation_id, safe='')}/stop", timeout=10)
