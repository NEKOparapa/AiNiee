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

    def import_files(self, kind, paths):
        return self.backend.request("POST", "/api/v2/media/import", json={"kind": kind, "paths": paths}, timeout=None)

    def save(self, workspace_id, model):
        return self.backend.request("POST", f"/api/v2/media/{quote(workspace_id, safe='')}/model",
                                    json={"model": model}, timeout=120)

    def run(self, workspace_id, stage, operation_id, config=None, options=None):
        return self.backend.request("POST", f"/api/v2/media/{quote(workspace_id, safe='')}/run", json={
            "stage": stage, "operation_id": operation_id, "config": config or {}, "options": options or {},
        }, timeout=None)

    def stop(self, operation_id):
        return self.backend.request("POST", f"/api/v2/media/operations/{quote(operation_id, safe='')}/stop", timeout=10)
