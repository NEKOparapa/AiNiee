"""Exercise the real Windows bundle using only Python's standard library.

Run after building: python backend/Tools/smoke_package.py --bundle <package-folder>
The executable is copied to a temporary Unicode path. It receives only normal
CLI/API requests; a loopback OpenAI server supplies fixed model responses.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit


TOKEN = "ainiee-packaged-smoke-fixed-token"
MODEL_KEY = "ainiee-packaged-smoke-fixed-model-key"
ANSWERS = {
    "Hello, world!": "你好！",
    "This is a headless translation test.": "这是一次无界面翻译测试。",
    "The story continues here.": "故事在这里继续。",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class FixedModelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), FixedModelHandler)
        self.requests: list[str] = []
        self.errors: list[str] = []
        self.second_received = threading.Event()
        self.release_second = threading.Event()
        self.stopping = threading.Event()
        self.lock = threading.Lock()

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server_port}"


class FixedModelHandler(BaseHTTPRequestHandler):
    server: FixedModelServer

    def log_message(self, format, *args):
        pass

    def send_json(self, status, body):
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/v1/models":
            self.send_json(200, {"object": "list", "data": [{"id": "fixed-mock-model", "object": "model"}]})
        else:
            self.reject_unexpected()

    def do_CONNECT(self):
        self.reject_unexpected()

    def reject_unexpected(self):
        self.server.errors.append(f"Unexpected outbound request: {self.command} {self.path}")
        self.send_json(403, {"error": "Only the loopback fixed model fixture is allowed"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.reject_unexpected()
            return
        try:
            require(self.headers.get("Authorization") == f"Bearer {MODEL_KEY}", "Unexpected model credentials")
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            require(body.get("model") == "fixed-mock-model", "Unexpected model")
            content = next((item.get("content", "") for item in reversed(body["messages"])
                            if item.get("role") == "user"), "")
            rows = re.findall(r"^(\d+)\.(.+)$", content, re.MULTILINE)
            require(len(rows) == 1 and rows[0][1] in ANSWERS, "Unexpected model prompt")
            index, source = rows[0]
            with self.server.lock:
                self.server.requests.append(source)
                number = len(self.server.requests)
            if number == 2:
                self.server.second_received.set()
                require(self.server.release_second.wait(90), "The stop test did not release the second request")
            self.send_json(200, {
                "id": f"fixed-completion-{number}", "object": "chat.completion", "created": 1,
                "model": "fixed-mock-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content":
                    f"<textarea>\n{index}.{ANSWERS[source]}\n</textarea>"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 16, "completion_tokens": 8, "total_tokens": 24},
            })
        except (ConnectionError, BrokenPipeError) as error:
            # The real SDK may cancel the in-flight second HTTP request when
            # stopping. Its source remains untranslated and must be retried.
            if not (locals().get("number") == 2 and self.server.stopping.is_set()):
                self.server.errors.append(str(error))
        except Exception as error:
            self.server.errors.append(str(error))
            self.send_json(400, {"error": str(error)})


@contextmanager
def fixed_model():
    server = FixedModelServer()
    thread = threading.Thread(target=server.serve_forever, name="fixed-model", daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.release_second.set()
        server.shutdown()
        server.server_close()
        thread.join(5)


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def isolated_environment(mock_origin, sandbox=None):
    environment = {key: value for key, value in os.environ.items() if not (
        key.upper().startswith(("AINIEE_", "PYTHON", "CONDA_"))
        or key.upper() in ("VIRTUAL_ENV", "TIKTOKEN_CACHE_DIR", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
    )}
    # Neither Python, Node nor the repository are needed in the child PATH.
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment["PATH"] = os.pathsep.join((str(windows / "System32"), str(windows)))
    environment["AINIEE_ALLOW_MULTI_INSTANCE"] = "1"
    if sandbox is not None:
        profile = sandbox / "隔离 用户"
        profile.mkdir()
        environment["USERPROFILE"] = str(profile)
        environment["LOCALAPPDATA"] = str(profile / "AppData" / "Local")
        environment["APPDATA"] = str(profile / "AppData" / "Roaming")
    # The only configured model URL is loopback. Environment-aware accidental
    # external downloads also hit this fixture and fail instead of the internet.
    environment.update(HTTP_PROXY=mock_origin, HTTPS_PROXY=mock_origin, ALL_PROXY=mock_origin,
                       NO_PROXY="127.0.0.1,localhost")
    return environment


class PackagedProcess:
    def __init__(self, bundle, cwd, environment, startup_timeout):
        self.bundle = bundle
        self.cwd = cwd
        self.environment = environment
        self.startup_timeout = startup_timeout
        self.process = None
        self.port = 0
        self.token = TOKEN

    def request(self, method, path, body=None, *, authenticated=True, headers=None, expected=200, timeout=30):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        values = {"Authorization": f"Bearer {self.token}"} if authenticated else {}
        values.update(headers or {})
        payload = None
        if body is not None:
            values["Content-Type"] = "application/json"
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        try:
            connection.request(method, path, body=payload, headers=values)
            response = connection.getresponse()
            content = response.read()
            require(response.status == expected,
                    f"{method} {path}: expected {expected}, received {response.status}: {content[:500]!r}")
            if response.getheader("Content-Type", "").startswith("application/json"):
                return json.loads(content)
            return content
        finally:
            connection.close()

    def start(self):
        require(self.process is None, "Package is already running")
        self.token = TOKEN
        self.port = free_port()
        self.process = subprocess.Popen(
            [str(self.bundle / "AiNiee.exe"), "--no-browser", "--port", str(self.port), "--token", TOKEN],
            cwd=self.cwd, env=self.environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Package exited before ready ({self.process.returncode})")
            try:
                require(self.request("GET", "/health", authenticated=False, timeout=1) == {"status": "ok"},
                        "Unexpected health response")
                self.request("GET", "/api/v1/version")
                return
            except (OSError, http.client.HTTPException):
                time.sleep(0.15)
        raise TimeoutError("Packaged service did not become ready")

    def wait_task(self, status, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = self.request("GET", "/api/v1/tasks/current")
            if current["status"] == status:
                return current
            require(current["status"] != "failed", f"Packaged task failed: {current.get('last_error')}")
            time.sleep(0.1)
        raise TimeoutError(f"Packaged task did not reach {status}; last state: {current}")

    def stop(self):
        require(self.process is not None, "No running package to stop")
        self.request("POST", "/api/v1/shutdown", expected=202)
        code = self.process.wait(timeout=90)
        require(code == 0, f"Packaged shutdown exit code: {code}")
        self.process = None

    def terminate(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.process = None


def websocket_handshake(port, authenticated):
    key = base64.b64encode(b"fixed-smoke-test").decode("ascii")
    path = "/api/v1/ws" + (f"?token={TOKEN}" if authenticated else "")
    with socket.create_connection(("127.0.0.1", port), timeout=5) as stream:
        stream.sendall((f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                        f"Origin: http://127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode("ascii"))
        headers = b""
        while b"\r\n\r\n" not in headers:
            chunk = stream.recv(4096)
            require(bool(chunk) and len(headers) < 65536, "Invalid WebSocket handshake")
            headers += chunk
        status = int(headers.split(b" ", 2)[1])
        if authenticated:
            require(status == 101, f"Authenticated WebSocket failed with {status}")
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
            require(accept in headers, "Incorrect WebSocket accept key")
            # A masked normal-close frame; no application message is sent.
            stream.sendall(b"\x88\x82\x01\x02\x03\x04\x02\xea")
        else:
            require(status == 403, f"Unauthenticated WebSocket was not rejected: {status}")


def translation_config(source, output, model_origin):
    return {
        "accent_color": "#123456", "translation_project": "AutoType",
        "label_input_path": str(source), "label_output_path": str(output),
        "label_polish_output_path": str(output / "polish"), "auto_set_output_path": False,
        "output_filename_suffix": "_translated", "bilingual_text_order": "translation_first",
        "keep_original_encoding": False, "response_conversion_toggle": False,
        "translation_result_check_switch": False, "source_language": "english",
        "target_language": "chinese_simplified", "language_filter_switch": False,
        "code_filter_switch": False, "lines_limit_switch": True, "tokens_limit_switch": False,
        "lines_limit": 1, "tokens_limit": 1024, "user_thread_counts": 1, "request_timeout": 60,
        "round_limit": 1, "pre_line_counts": 0, "few_shot_and_example_switch": False,
        "translation_example_switch": False, "auto_process_text_code_segment": False,
        "text_symbol_repair_switch": False,
        "platforms": {"custom_platform_mock": {
            "tag": "custom_platform_mock", "name": "Fixed packaged test", "api_format": "OpenAI",
            "api_url": model_origin + "/v1", "api_key": MODEL_KEY, "model": "fixed-mock-model",
            "rpm_limit": 4096, "tls_switch": False,
        }},
        "api_settings": {"active": "custom_platform_mock"},
    }


def validate_assets(application, bundle):
    frontend = bundle / "_internal" / "frontend" / "dist"
    require((frontend / "index.html").is_file(), "Bundled frontend index is missing")
    index = application.request("GET", "/", authenticated=False)
    require(index == (frontend / "index.html").read_bytes(), "Served index differs from bundled file")
    require(application.request("GET", "/settings/task", authenticated=False,
                                headers={"Accept": "text/html"}) == index, "SPA deep link failed")
    urls = set(re.findall(r'(?:src|href)="(/assets/[^"?#]+)"', index.decode("utf-8")))
    require(any(url.endswith(".js") for url in urls), "Built index has no JavaScript entry")
    require(any(url.endswith(".css") for url in urls), "Built index has no stylesheet")
    urls.add("/favicon.svg")
    for url in urls:
        payload = application.request("GET", url, authenticated=False)
        require(payload == (frontend / url.lstrip("/")).read_bytes(), f"Bundled asset mismatch: {url}")
    return len(urls)


def browser_capture_command(sandbox):
    """Use standard BROWSER instrumentation, without changing an OS setting.

    On Windows webbrowser.get parses commands containing %s with shlex.split,
    and its GenericBrowser invokes that argv directly. Forward slashes and
    shlex.join preserve spaces, Unicode and Windows drive prefixes correctly.
    pythonw avoids opening a helper console from the windowed application.
    """
    interpreter = Path(sys.executable).with_name("pythonw.exe")
    require(interpreter.is_file(), "Browser capture requires this Python installation's pythonw.exe")
    capture = sandbox / "浏览器 启动地址.txt"
    helper = sandbox / "捕获 浏览器.py"
    helper.write_text(
        "import os, sys\n"
        "from pathlib import Path\n"
        "try:\n"
        "    target = Path(sys.argv[1])\n"
        "    temporary = target.with_suffix('.tmp')\n"
        "    temporary.write_text(sys.argv[2], encoding='utf-8')\n"
        "    temporary.replace(target)\n"
        "except BaseException:\n"
        "    pass\n"
        "# Always succeed: never fall through to the user's actual browser.\n"
        "os._exit(0)\n", encoding="utf-8",
    )
    command = shlex.join([interpreter.as_posix(), helper.as_posix(), capture.as_posix(), "%s"])
    # Exercise command parsing and the helper once before the EXE launch.
    require(webbrowser.get(command).open("http://127.0.0.1:1/#capture-probe"), "Browser capture command failed")
    require(capture.read_text(encoding="utf-8") == "http://127.0.0.1:1/#capture-probe", "Browser capture probe failed")
    capture.unlink()
    return command, capture


def validate_default_launch(bundle, cwd, environment, sandbox, startup_timeout, checks, redactions):
    command, capture = browser_capture_command(sandbox)
    application = PackagedProcess(bundle, cwd, {**environment, "BROWSER": command}, startup_timeout)
    try:
        # No mode, port, token or browser flag: this is the actual double-click
        # path. Only the external browser command is instrumented by BROWSER.
        application.process = subprocess.Popen(
            [str(bundle / "AiNiee.exe")], cwd=cwd, env=application.environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        deadline = time.monotonic() + startup_timeout
        while not capture.is_file():
            require(application.process.poll() is None, "Default package exited before opening the browser")
            require(time.monotonic() < deadline, "Default package did not open the browser")
            time.sleep(0.1)
        url = urlsplit(capture.read_text(encoding="utf-8"))
        fragment = parse_qs(url.fragment)
        generated = fragment.get("token", [""])[0]
        if generated:
            redactions.append(generated)
        require(url.scheme == "http" and url.hostname == "127.0.0.1" and url.port,
                "Default browser handoff must use an assigned loopback port")
        require(url.path == "/" and not url.query and not url.username and not url.password,
                "Default browser handoff must keep credentials out of the query and authority")
        require(set(fragment) == {"api", "token"} and len(fragment["api"]) == len(fragment["token"]) == 1,
                "Default browser handoff has an unexpected fragment contract")
        require(fragment["api"][0] == f"http://127.0.0.1:{url.port}", "Frontend and backend are not served from the same origin")
        require(len(generated) >= 32 and generated != TOKEN, "Default package did not generate a random token")
        application.port, application.token = url.port, generated
        require(application.request("GET", "/health", authenticated=False) == {"status": "ok"},
                "Default package health check failed")
        application.request("GET", "/api/v1/version", authenticated=False, expected=401)
        application.request("GET", "/api/v1/version")
        validate_assets(application, bundle)
        application.stop()
        for path in (bundle / "Logs").glob("*.log*"):
            require(generated not in path.read_text(encoding="utf-8", errors="replace"),
                    "Default generated token leaked into packaged logs")
        checks["no_argument_browser_handoff"] = True
        checks["no_argument_browser_port"] = url.port
        checks["generated_token_not_logged"] = True
    finally:
        application.terminate()


def run_workflow(application, bundle, sandbox, model, checks):
    application.start()
    checks["assets_verified"] = validate_assets(application, bundle)
    for path in ("/api/v1/config", "/api/v1/version", "/api/v1/projects/current", "/openapi.json"):
        application.request("GET", path, authenticated=False, expected=401)
    application.request("POST", "/api/v1/shutdown", authenticated=False, expected=401)
    application.request("GET", "/api/v1/version", headers={"Authorization": "Bearer wrong"}, expected=401)
    websocket_handshake(application.port, False)
    websocket_handshake(application.port, True)
    checks["auth_http_websocket"] = True

    source, output = sandbox / "故事 输入", sandbox / "翻译 输出"
    source.mkdir()
    (source / "story.txt").write_text("\n".join(ANSWERS) + "\n", encoding="utf-8")
    application.request("PATCH", "/api/v1/config", translation_config(source, output, model.origin))
    application.request("PUT", "/api/v1/tables/glossary", {
        "tables": [{"id": "fixed-smoke-glossary", "name": "固定验收术语", "enabled": True,
                    "rows": [{"src": "world", "dst": "世界", "info": "", "regex": False}]}],
        "active_table_id": "fixed-smoke-glossary",
    })
    project = application.request("POST", "/api/v1/projects/open", {"path": str(source)}, timeout=90)
    require(project["item_count"] == 3, f"Expected three real reader items: {project}")
    files = application.request("GET", "/api/v1/projects/current/files")
    require(len(files) == 1 and files[0]["item_count"] == 3, "Incorrect real project file tree")
    checks["auto_detect_real_text_project"] = True

    application.request("POST", "/api/v1/tasks/translate", {"continue": False})
    require(model.second_received.wait(90), "Packaged OpenAI client did not reach the second fixed request")
    try:
        model.stopping.set()
        application.request("POST", "/api/v1/tasks/stop")
    finally:
        model.release_second.set()
    stopped = application.wait_task("stopped")
    require(stopped["can_continue"], "Stopped package does not offer continue")
    stats = application.request("GET", "/api/v1/projects/current/stats")
    require(0 < stats["translated"] < 3, f"Stop failed to retain a partially translated project: {stats}")
    saved_items = application.request("GET", "/api/v1/projects/current/items")["items"]
    remaining = [item["source_text"] for item in saved_items if item["translation_status"] == 0]
    require(len(remaining) == 3 - stats["translated"], "Saved item states disagree with partial statistics")
    requests_before_restart = len(model.requests)
    application.request("POST", "/api/v1/cache/save")
    history = application.request("GET", "/api/v1/projects/history")
    entry = next(item for item in history if item["project_id"] == project["project_id"])
    cache_path = Path(entry["cache_path"]).resolve()
    require(cache_path.is_relative_to(bundle / "ProjectCache") and cache_path.is_file(),
            "Cache did not persist beside the executable")
    config_path = bundle / "Resource" / "config.json"
    require(json.loads(config_path.read_text(encoding="utf-8"))["accent_color"] == "#123456",
            "Portable configuration did not persist beside the executable")
    application.stop()
    checks["stop_save_shutdown"] = True

    application.start()
    require(application.request("GET", "/api/v1/config")["accent_color"] == "#123456",
            "Configuration was not restored after a real executable restart")
    restored = application.request("POST", "/api/v1/projects/open", {"path": str(cache_path)})
    require(restored["project_id"] == project["project_id"], "Cache restore changed the project identity")
    require(application.request("GET", "/api/v1/projects/current/stats")["translated"] == stats["translated"],
            "Saved translation progress was lost across executable restart")
    application.request("POST", "/api/v1/tasks/translate", {"continue": True})
    application.wait_task("completed")
    require(model.requests[requests_before_restart:] == remaining,
            f"Resume did not request exactly the unsaved items: {model.requests[requests_before_restart:]}")
    checks["restart_restore_continue"] = True

    issues = application.request("POST", "/api/v1/checks/terminology", {})["issues"]
    require(len(issues) == 1 and issues[0]["source"] == "Hello, world!",
            f"Expected the fixed missing-term issue, received: {issues}")
    issue = issues[0]
    application.request("PATCH", f"/api/v1/projects/current/items/{quote(issue['file'], safe='')}/{issue['index']}",
                        {"project_id": project["project_id"], "translated_text": "你好，世界！"})
    require(not application.request("POST", "/api/v1/checks/terminology", {})["issues"], "Edited terminology still fails")
    result = application.request("POST", "/api/v1/export", {"output_path": str(output)})
    require(Path(result["output_path"]).resolve() == output.resolve(), "Export used an unexpected directory")
    translated = ["你好，世界！", ANSWERS["This is a headless translation test."], ANSWERS["The story continues here."]]
    expected = (os.linesep.join(translated) + os.linesep).encode("utf-8")
    require((output / "story_translated.txt").read_bytes() == expected, "Translated export bytes differ")
    bilingual = [line for pair in zip(translated, ANSWERS) for line in pair]
    require((output / "bilingual_auto" / "story_bilingual.txt").read_bytes()
            == (os.linesep.join(bilingual) + os.linesep).encode("utf-8"), "Bilingual export bytes differ")
    checks["check_edit_export_bytes"] = True
    checks["translated_sha256"] = hashlib.sha256(expected).hexdigest()
    application.stop()
    checks["clean_shutdown"] = True
    require(not model.errors, f"Mock endpoint detected unexpected requests: {model.errors}")
    for path in (bundle / "Logs").glob("*.log*"):
        text = path.read_text(encoding="utf-8", errors="replace")
        require(TOKEN not in text and MODEL_KEY not in text, "Credentials leaked into packaged application logs")
    checks["logs_redact_credentials"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="Built onedir folder containing AiNiee.exe")
    parser.add_argument("--report", type=Path, default=Path("build/package-smoke.json"))
    parser.add_argument("--startup-timeout", type=float, default=90)
    args = parser.parse_args(argv)
    require(sys.platform == "win32", "The executable smoke test requires Windows")
    source_bundle = args.bundle.resolve(strict=True)
    require((source_bundle / "AiNiee.exe").is_file(), "Bundle has no AiNiee.exe")
    require((source_bundle / "portable.txt").is_file(), "Bundle must include its portable marker")
    require(not any(path.is_symlink() or path.is_junction() for path in source_bundle.rglob("*")),
            "Bundle must not link to external source or user files")
    report = {"success": False, "checks": {}, "bundle": str(source_bundle),
              "executable_sha256": hashlib.sha256((source_bundle / "AiNiee.exe").read_bytes()).hexdigest()}
    started = time.monotonic()
    redactions = [TOKEN, MODEL_KEY]

    def redact(value):
        for secret in redactions:
            value = value.replace(secret, "[REDACTED]")
        return value
    with tempfile.TemporaryDirectory(prefix="AiNiee 打包验收 ") as temporary:
        sandbox = Path(temporary)
        bundle = sandbox / "可移动 应用" / "AiNiee"
        shutil.copytree(source_bundle, bundle)
        cwd = sandbox / "其他 工作目录"
        cwd.mkdir()
        with fixed_model() as model:
            application = PackagedProcess(bundle, cwd, isolated_environment(model.origin, sandbox), args.startup_timeout)
            try:
                run_workflow(application, bundle, sandbox, model, report["checks"])
                validate_default_launch(bundle, cwd, application.environment, sandbox,
                                        args.startup_timeout, report["checks"], redactions)
                report["success"] = True
            except Exception as error:
                report["error"] = redact(str(error))
                report["diagnostics"] = {
                    path.name: redact(path.read_text(encoding="utf-8", errors="replace")[-12000:])
                    for path in (bundle / "Logs").glob("*.log*")
                }
            finally:
                model.release_second.set()
                application.terminate()
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "report": str(args.report.resolve()),
                      "elapsed_seconds": report["elapsed_seconds"]}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
