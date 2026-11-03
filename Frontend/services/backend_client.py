"""Explicit HTTP operations and reconnecting notifications, independent of Qt."""
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from websockets.sync.client import connect

from Frontend.services.protocol import PROTOCOL_VERSION, to_wire
from Frontend.services.operation_types import (
    ApiTestRequest, GlossaryTranslateRequest, TablePolishRequest,
    TableProofreadRequest, TableTranslateRequest,
)


class BackendError(RuntimeError):
    pass


class BackendProtocolError(BackendError):
    """The listening service cannot speak this desktop's protocol."""


class BackendClient:
    def __init__(self, url, token=""):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.http = httpx.Client(base_url=self.url, headers=self.headers, trust_env=False, timeout=60)
        self.stopping = threading.Event()
        self.operations = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backend-requests")
        self.controls = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backend-controls")
        self.ws = None
        self.ws_thread = None
        self.on_message = lambda message: None
        self.cache = None
        self.backend_process = None
        self._closed = False

    @property
    def mcp_url(self) -> str:
        """MCP shares the backend listener, including any reverse-proxy prefix."""
        parts = urlsplit(self.url)
        return urlunsplit((
            parts.scheme, parts.netloc.rsplit("@", 1)[-1],
            parts.path.rstrip("/") + "/mcp", "", "",
        ))

    def request(self, method, path, **kwargs):
        try:
            response = self.http.request(method, path, **kwargs)
            if response.is_error:
                try:
                    detail = response.json().get("detail", response.reason_phrase)
                except ValueError:
                    detail = response.reason_phrase
                if response.status_code == 400 and path.startswith("/api/editor/"):
                    raise ValueError(str(detail))
                raise BackendError(f"后端请求失败 ({response.status_code}): {detail}")
            return response.json()
        except httpx.HTTPError as error:
            raise BackendError(f"无法连接后端 {self.url}: {type(error).__name__}") from error

    def check_health(self, timeout=5):
        """Validate both initial connections and WebSocket reconnections."""
        try:
            health = self.request("GET", "/health", timeout=timeout)
        except ValueError as error:
            raise BackendProtocolError("连接地址未返回有效的 AiNiee 后端信息") from error
        if not isinstance(health, dict) or health.get("service") != "AiNiee":
            raise BackendProtocolError("连接地址不是 AiNiee 后端服务")
        actual = health.get("protocol")
        if type(actual) is not int or actual != PROTOCOL_VERSION:
            raise BackendProtocolError(
                f"连接协议不兼容：桌面要求版本 {PROTOCOL_VERSION}，后端返回 {actual!r}。"
                "请配套更新前后端并重启。"
            )

    def load_config(self):
        return self.request("GET", "/api/config")["config"]

    def shutdown(self):
        """Request service shutdown only after the desktop user confirms exit."""
        # Finish the WebSocket close handshake before asking the server to exit.
        # Simultaneous client/server closes can interrupt server lifespan cleanup.
        self.stopping.set()
        if self.ws:
            self.ws.close()
        if self.ws_thread:
            self.ws_thread.join(timeout=5)
        try:
            return self.request("POST", "/api/shutdown", timeout=5)
        except BackendError:
            # The window remains open when shutdown is refused; resume events.
            self.stopping.clear()
            if self.ws_thread and not self.ws_thread.is_alive():
                self.start_events(self.on_message)
            raise

    def save_config(self, values, *, _table_update=False):
        return self.request("PATCH", "/api/config", json={"values": values, "table_update": _table_update})["config"]

    def get_default_section(self, name):
        from urllib.parse import quote
        return self.request("GET", f"/api/config/defaults/{quote(name, safe='')}")

    def get_platform_presets(self):
        return self.request("GET", "/api/config/platform-presets")

    def get_prompt_presets(self, kind):
        from urllib.parse import quote
        return self.request("GET", f"/api/config/prompt-presets/{quote(kind, safe='')}")

    def get_config_info(self):
        return self.request("GET", "/api/config/info")

    def import_config(self, path):
        return self.request("POST", "/api/config/import", json={"path": str(path)})["config"]

    def export_config(self, directory):
        return self.request("POST", "/api/config/export", json={"path": str(directory)})

    def update_config(self, updater):
        # Compare-and-swap: a callable cannot be sent across the wire.
        document = self.request("GET", "/api/config")
        config = document["config"]
        updater(config)
        return self.request("PATCH", "/api/config", json={
            "values": config, "revision": document["revision"], "table_update": True,
        })["config"]

    def start_translation(self, continue_status: bool = False) -> Future:
        return self._submit_operation("translation", "/api/tasks/translation", {"continue_status": continue_status})

    def start_analysis(self) -> Future:
        return self._submit_operation("analysis", "/api/tasks/analysis", {})

    def translate_table(self, data: TableTranslateRequest) -> Future:
        return self._submit_operation("table.translate", "/api/tasks/table/translate", data)

    def polish_table(self, data: TablePolishRequest) -> Future:
        return self._submit_operation("table.polish", "/api/tasks/table/polish", data)

    def proofread_table(self, data: TableProofreadRequest) -> Future:
        return self._submit_operation("table.proofread", "/api/tasks/table/proofread", data)

    def translate_glossary(self, data: GlossaryTranslateRequest) -> Future:
        return self._submit_operation("glossary.translate", "/api/tasks/glossary/translate", data)

    def test_api(self, data: ApiTestRequest) -> Future:
        return self._submit_operation("api_test", "/api/tasks/api-test", data)

    def export_project(self, export_path: str | None = None) -> Future:
        payload = {"export_path": export_path} if export_path is not None else {}
        return self._submit_operation("project.export", "/api/project/export", payload)

    def stop_task(self) -> Future:
        return self._submit_operation("stop", "/api/tasks/stop", {}, control=True)

    def save_project(self) -> Future:
        return self._submit_operation("project.save", "/api/project/save", {})

    def save_project_sync(self) -> dict[str, Any]:
        """For project-loading workers that must finish persistence before continuing."""
        return self.request("POST", "/api/project/save", json={}, timeout=600)

    def _submit_operation(self, operation: str, path: str, data: dict, *, control=False) -> Future:
        # Snapshot UI-owned lists before the worker starts serializing them.
        payload = to_wire(data)

        def send():
            try:
                # State updates arrive in order on the WebSocket. An HTTP response
                # can arrive after completion and must not restore a stale busy state.
                result = self.request("POST", path, json=payload, timeout=10 if control else 600)
                if operation == "project.save":
                    self.on_message({"type": "request_completed", "operation": operation})
                return result
            except Exception as error:
                status = None
                try:
                    status = self.request("GET", "/api/status")
                except BackendError:
                    pass
                message = {"type": "request_rejected", "operation": operation, "data": payload, "message": str(error)}
                if status is not None:
                    message["status"] = status
                self.on_message(message)
        # A save/export request can wait for queued work on the backend. Stop
        # must reach HTTP independently so it can cancel that preceding work.
        executor = self.controls if control else self.operations
        return executor.submit(send)

    def start_events(self, callback):
        self.on_message = callback
        self.ws_thread = threading.Thread(target=self._listen, name="backend-events", daemon=True)
        self.ws_thread.start()

    def _listen(self):
        import json
        parts = urlsplit(self.url)
        url = urlunsplit(("wss" if parts.scheme == "https" else "ws", parts.netloc, parts.path + "/ws/events", "", ""))
        delay = 1
        while not self.stopping.is_set():
            try:
                with connect(url, additional_headers=self.headers, open_timeout=5, close_timeout=2, max_size=16 * 1024 * 1024, proxy=None) as ws:
                    self.ws = ws
                    # A restarted backend may be a different version. Do not
                    # read its project or dispatch events before checking it.
                    self.check_health()
                    for raw in ws:
                        if self.stopping.is_set():
                            break
                        message = json.loads(raw)
                        if message["type"] in ("connected", "settled"):
                            message["project"] = self.request("GET", "/api/project")["project"]
                        self.on_message(message)
                        delay = 1
            except BackendProtocolError as error:
                if not self.stopping.is_set():
                    self.on_message({"type": "disconnected", "message": str(error)})
            except Exception as error:
                if not self.stopping.is_set():
                    self.on_message({"type": "disconnected", "message": f"后端连接断开，正在重连：{type(error).__name__}"})
            finally:
                self.ws = None
            self.stopping.wait(delay)
            delay = min(delay * 2, 30)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.stopping.set()
        if self.ws:
            self.ws.close()
        if self.ws_thread:
            self.ws_thread.join(timeout=5)
        self.controls.shutdown(wait=True, cancel_futures=True)
        self.operations.shutdown(wait=True, cancel_futures=True)
        self.http.close()
