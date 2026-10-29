import asyncio
import http.client
import json
import io
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import uvicorn

import AiNiee


def test_cli_defaults_and_random_port():
    args = AiNiee.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.token is None
    assert args.dev is False
    args = AiNiee.parse_args(["--port", "0", "--token", "fixed-test-token", "--dev"])
    assert args.port == 0
    assert args.token == "fixed-test-token"
    assert args.dev is True


def test_packaged_defaults_host_the_web_app_on_a_random_port(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    args = AiNiee.parse_args([])
    assert args.port == 0
    assert args.web and not args.dev and not args.no_browser
    args = AiNiee.parse_args(["--dev", "--port", "9123", "--no-browser"])
    assert args.dev and not args.web and args.no_browser and args.port == 9123


def test_source_web_mode_is_explicit_and_conflicts_with_dev():
    args = AiNiee.parse_args(["--web", "--no-browser"])
    assert args.web and args.no_browser
    with pytest.raises(SystemExit):
        AiNiee.parse_args(["--web", "--dev"])


def test_bundled_frontend_path_uses_internal_resources(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "_internal"), raising=False)
    assert AiNiee.frontend_directory() == tmp_path / "_internal" / "frontend" / "dist"


def test_windowed_readiness_never_falls_back_to_logging_stdout(capsys, caplog):
    AiNiee._write_ready(None, 51234, "private-windowed-token", True)
    assert "private-windowed-token" not in capsys.readouterr().out + caplog.text
    stream = io.StringIO()
    AiNiee._write_ready(stream, 51234, "private-windowed-token", True)
    assert stream.getvalue() == "TOKEN private-windowed-token\nREADY 51234\n"
    stream = io.StringIO()
    AiNiee._write_ready(stream, 51234, "private-windowed-token", False)
    assert stream.getvalue() == "READY 51234\n"


@pytest.mark.parametrize("interactive", [True, False])
def test_duplicate_instance_notifies_only_an_interactive_launch(monkeypatch, tmp_path, interactive):
    from ModuleFolders.Infrastructure.Platform import RuntimeSetup, SingleInstance
    from ModuleFolders.Log import LogSystem

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(RuntimeSetup, "prepare_working_directory", lambda: tmp_path)
    monkeypatch.setattr(SingleInstance, "acquire_app_mutex", lambda: False)
    monkeypatch.setattr(LogSystem, "install", lambda: None)
    monkeypatch.delenv("AINIEE_ALLOW_MULTI_INSTANCE", raising=False)
    notices = []
    monkeypatch.setattr(AiNiee, "_notify_startup", notices.append)
    assert AiNiee.run(AiNiee.parse_args([]), interactive=interactive) == 0
    assert notices == (["already_running"] if interactive else [])


@pytest.mark.parametrize("arguments,expected_notice", [([], True), (["--no-browser"], False)])
def test_packaged_startup_failure_exits_and_respects_noninteractive_mode(monkeypatch, arguments, expected_notice):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(AiNiee.multiprocessing, "freeze_support", lambda: None)
    def failed_run(*args, **kwargs):
        raise FileNotFoundError("missing bundled frontend")
    monkeypatch.setattr(AiNiee, "run", failed_run)
    notices = []
    monkeypatch.setattr(AiNiee, "_notify_startup", notices.append)
    assert AiNiee.main(arguments) == 1
    assert notices == (["startup_failed"] if expected_notice else [])


def test_failed_browser_launch_stops_invisible_service_and_returns_failure(monkeypatch, tmp_path):
    from ModuleFolders.Infrastructure.Platform import RuntimeSetup, SingleInstance
    from ModuleFolders.Log import LogSystem
    from Server import app as server_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(RuntimeSetup, "prepare_working_directory", lambda: tmp_path)
    monkeypatch.setattr(RuntimeSetup, "migrate_config_if_needed", lambda: None)
    monkeypatch.setattr(SingleInstance, "acquire_app_mutex", lambda: True)
    monkeypatch.setattr(LogSystem, "install", lambda: None)
    monkeypatch.setattr(server_app, "create_app", lambda *args, **kwargs: object())
    monkeypatch.setattr(AiNiee, "_open_browser", lambda url: False)
    notices = []
    monkeypatch.setattr(AiNiee, "_notify_startup", notices.append)

    class StartupStub:
        def __init__(self, config, on_ready):
            self.started, self.should_exit, self.on_ready = True, False, on_ready

        def run(self, sockets):
            async def scenario():
                self.on_ready()
                async def wait_for_shutdown():
                    while not self.should_exit or not notices:
                        await asyncio.sleep(0.01)
                await asyncio.wait_for(wait_for_shutdown(), 2)
            asyncio.run(scenario())

    monkeypatch.setattr(AiNiee, "ReadyServer", StartupStub)
    assert AiNiee.run(AiNiee.parse_args(["--web", "--port", "0", "--token", "fixed"]), interactive=True) == 1
    assert notices == ["browser_failed"]


@pytest.mark.parametrize("host", ["0.0.0.0", "localhost", "::1", "192.168.1.2"])
def test_cli_rejects_other_bind_addresses(host):
    with pytest.raises(SystemExit) as error:
        AiNiee.parse_args(["--host", host])
    assert error.value.code == 2


@pytest.mark.parametrize("port", ["-1", "65536", "abc"])
def test_cli_rejects_invalid_ports(port):
    with pytest.raises(SystemExit) as error:
        AiNiee.parse_args(["--port", port])
    assert error.value.code == 2


@pytest.mark.parametrize("token", ["", "has space", "new\nline", "中文"])
def test_cli_rejects_invalid_header_tokens(token):
    with pytest.raises(SystemExit) as error:
        AiNiee.parse_args(["--token", token])
    assert error.value.code == 2


def test_dev_url_keeps_connection_details_in_fragment():
    token = "test/with?special=characters&+"
    url = urlsplit(AiNiee.development_url(52345, token))
    assert url.scheme == "http"
    assert url.netloc == "127.0.0.1:5173"
    assert url.query == ""
    assert parse_qs(url.fragment) == {"api": ["http://127.0.0.1:52345"], "token": [token]}


def test_packaged_browser_handoff_uses_the_backend_origin():
    url = urlsplit(AiNiee.browser_url(52345, "fixed/token&value"))
    assert url.netloc == "127.0.0.1:52345"
    assert url.path == "/" and not url.query
    assert parse_qs(url.fragment) == {
        "api": ["http://127.0.0.1:52345"], "token": ["fixed/token&value"],
    }


def test_readiness_callback_waits_for_successful_startup(monkeypatch):
    calls = []

    async def startup(self, sockets=None):
        calls.append("listening")
        self.started = True

    monkeypatch.setattr(uvicorn.Server, "startup", startup)
    server = AiNiee.ReadyServer(uvicorn.Config(None), lambda: calls.append("ready"))
    asyncio.run(server.startup())
    assert calls == ["listening", "ready"]


def test_startup_failure_does_not_emit_ready(monkeypatch):
    calls = []

    async def startup(self, sockets=None):
        self.should_exit = True

    monkeypatch.setattr(uvicorn.Server, "startup", startup)
    server = AiNiee.ReadyServer(uvicorn.Config(None), lambda: calls.append("ready"))
    asyncio.run(server.startup())
    assert calls == []


def test_browser_errors_do_not_log_token(monkeypatch, caplog):
    secret_url = AiNiee.development_url(8000, "should-never-be-logged")

    def failed_open(url):
        raise RuntimeError(url)

    monkeypatch.setattr(AiNiee.webbrowser, "open", failed_open)
    with caplog.at_level(logging.WARNING):
        AiNiee._open_browser(secret_url)
    assert caplog.records
    assert "should-never-be-logged" not in caplog.text


def test_websocket_server_logs_redact_query_tokens(monkeypatch):
    logger = logging.getLogger("uvicorn.error")
    monkeypatch.setattr(logger, "filters", [])
    AiNiee._protect_server_logs()
    record = logger.makeRecord(
        logger.name, logging.INFO, __file__, 1,
        '%s - "WebSocket %s" [accepted]',
        ("127.0.0.1:50000", "/api/v1/ws?token=private-test-token"), None,
    )
    assert logger.filter(record)
    assert "private-test-token" not in record.getMessage()
    assert "REDACTED" in record.getMessage()


def test_real_process_ready_auth_config_websocket_and_shutdown(isolated_app_paths):
    from websockets.sync.client import connect

    root = Path(__file__).resolve().parents[2]
    data_dir = isolated_app_paths / "data"
    data_dir.mkdir()
    (data_dir / "config.json").write_text("{}", encoding="utf-8")
    env = {**os.environ, "AINIEE_ALLOW_MULTI_INSTANCE": "1", "PYTHONIOENCODING": "utf-8"}
    process = subprocess.Popen(
        [sys.executable, str(root / "AiNiee.py"), "--port", "0"],
        cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8",
    )
    lines = []
    incoming = queue.Queue()

    def collect_output():
        for line in process.stdout:
            lines.append(line)
            incoming.put(line)
        incoming.put(None)

    reader = threading.Thread(target=collect_output, daemon=True)
    reader.start()
    try:
        deadline = time.monotonic() + 60
        token = None
        port = None
        while port is None:
            remaining = deadline - time.monotonic()
            assert remaining > 0, "Server did not emit READY within 60 seconds"
            line = incoming.get(timeout=remaining)
            assert line is not None, "Server exited before READY: " + "".join(lines)
            if line.startswith("TOKEN "):
                token = line.removeprefix("TOKEN ").strip()
            if line.startswith("READY "):
                port = int(line.removeprefix("READY ").strip())
        assert token and len(token) >= 32
        assert 0 < port <= 65535

        def request(method, path, body=None, authenticated=True):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            headers = {"Authorization": f"Bearer {token}"} if authenticated else {}
            if body is not None:
                headers["Content-Type"] = "application/json"
            try:
                connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()

        assert request("GET", "/health", authenticated=False)[0] == 200
        assert request("GET", "/api/v1/version", authenticated=False)[0] == 401
        assert request("GET", "/api/v1/version")[0] == 200
        assert request("PATCH", "/api/v1/config", {"accent_color": "#123456"})[0] == 200
        assert request("GET", "/api/v1/config")[1]["accent_color"] == "#123456"
        with connect(f"ws://127.0.0.1:{port}/api/v1/ws?token={token}", proxy=None, open_timeout=5):
            pass
        assert request("POST", "/api/v1/shutdown")[0] == 202
        assert process.wait(timeout=15) == 0
        reader.join(timeout=5)
        assert not reader.is_alive()
        assert token not in "".join(line for line in lines if not line.startswith("TOKEN "))
        for log in (isolated_app_paths / "logs").glob("*.log*"):
            assert token not in log.read_text(encoding="utf-8", errors="replace")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        reader.join(timeout=5)
        process.stdout.close()
