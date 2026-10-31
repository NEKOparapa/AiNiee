"""HTTP commands and reconnecting WebSocket notifications, independent of Qt."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, urlunsplit

import httpx
from websockets.sync.client import connect

from Frontend.services.protocol import COMMANDS, event_data_from_wire, to_wire


class BackendError(RuntimeError):
    pass

class BackendClient:
    def __init__(self, url, token=""):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.http = httpx.Client(base_url=self.url, headers=self.headers, trust_env=False, timeout=60)
        self.stopping = threading.Event()
        self.commands = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backend-commands")
        self.ws = None
        self.ws_thread = None
        self.on_message = lambda message: None
        self.cache = None
        self.backend_process = None
        self._closed = False

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

    def send_event(self, event, data):
        if event not in COMMANDS:
            return False
        payload = to_wire(data)

        def send():
            try:
                # State updates arrive in order on the WebSocket. An HTTP response
                # can arrive after completion and must not restore a stale busy state.
                self.request("POST", "/api/commands", json={"event": event, "data": payload})
            except Exception as error:
                status = None
                try:
                    status = self.request("GET", "/api/status")
                except BackendError:
                    pass
                message = {"type": "command_rejected", "event": event, "data": payload, "message": str(error)}
                if status is not None:
                    message["status"] = status
                self.on_message(message)
        self.commands.submit(send)
        return True

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
                    for raw in ws:
                        if self.stopping.is_set():
                            break
                        message = json.loads(raw)
                        if message["type"] in ("connected", "settled"):
                            message["project"] = self.request("GET", "/api/project")["project"]
                        if message["type"] == "event":
                            message["data"] = event_data_from_wire(message["data"])
                        self.on_message(message)
                        delay = 1
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
        self.commands.shutdown(wait=True, cancel_futures=True)
        self.http.close()
