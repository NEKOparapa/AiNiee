"""Start the local API and, optionally, the bundled browser workbench."""

import argparse
import asyncio
import logging
import multiprocessing
import os
import secrets
import socket
import sys
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlencode

# Frozen multiprocessing children must be dispatched before parsing application
# arguments or importing the server and its scientific-library dependencies.
if __name__ == "__main__":
    multiprocessing.freeze_support()

import uvicorn


HOST = "127.0.0.1"
DEV_ORIGIN = "http://127.0.0.1:5173"
DEV_ORIGINS = (DEV_ORIGIN, "http://localhost:5173")


def _port(value: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 0 <= result <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return result


def _token(value: str) -> str:
    if not value or any(not 33 <= ord(character) <= 126 for character in value):
        raise argparse.ArgumentTypeError("token must contain non-space printable ASCII characters")
    return value


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AiNiee local API server")
    parser.add_argument("--host", choices=(HOST,), default=HOST, help="only the loopback address is allowed")
    parser.add_argument("--port", type=_port, default=0 if getattr(sys, "frozen", False) else 8000,
                        help="listen port; 0 selects a free port (default in packaged builds)")
    parser.add_argument("--token", type=_token, help="Bearer token; omitted to generate a random token")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dev", action="store_true", help="open the frontend development server after startup")
    mode.add_argument("--web", action="store_true", help="serve frontend/dist and open the browser (default in packaged builds)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser or show native startup dialogs")
    args = parser.parse_args(argv)
    args.web = args.web or (getattr(sys, "frozen", False) and not args.dev)
    return args


def frontend_directory() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / "frontend" / "dist"


def development_url(port: int, token: str) -> str:
    return browser_url(port, token, development=True)


def browser_url(port: int, token: str, *, development: bool = False) -> str:
    origin = DEV_ORIGIN if development else f"http://{HOST}:{port}"
    fragment = urlencode({"api": f"http://{HOST}:{port}", "token": token})
    return f"{origin}/#{fragment}"


def _open_browser(url: str) -> bool:
    try:
        opened = webbrowser.open(url)
    except Exception:
        # 异常文本可能包含带有凭证的完整 URL，因此只记录通用诊断。
        logging.getLogger(__name__).warning("无法自动打开前端，请检查默认浏览器设置")
        return False
    if not opened:
        logging.getLogger(__name__).warning("未找到可用浏览器，请检查默认浏览器设置")
    return opened


def _notify_startup(key: str) -> None:
    """A windowed executable needs a visible, credential-free startup failure."""
    if os.name != "nt":
        return
    from Server.launcher_messages import startup_message
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, startup_message(key), "AiNiee", 0x40)
    except Exception:
        logging.getLogger(__name__).warning("无法显示启动提示 / Unable to display startup notification")


def _write_ready(stream, port: int, token: str, generated: bool) -> None:
    # In a windowed EXE stream is None. print(file=None) would fall back to the
    # installed stdout log bridge and leak the token to a file/WS subscriber.
    if stream is None:
        return
    try:
        if generated:
            print(f"TOKEN {token}", file=stream, flush=True)
        print(f"READY {port}", file=stream, flush=True)
    except (OSError, ValueError):
        logging.getLogger(__name__).warning("启动终端不可写 / Startup output is unavailable")


def _protect_server_logs() -> None:
    # WebSocket 握手信息使用 uvicorn.error，而非可关闭的 access logger。
    from ModuleFolders.Log.LogSystem import SensitiveFilter

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, SensitiveFilter) for item in logger.filters):
            logger.addFilter(SensitiveFilter())


class ReadyServer(uvicorn.Server):
    """只有 lifespan 和监听 socket 都就绪后，才发出启动完成通知。"""

    def __init__(self, config: uvicorn.Config, on_ready: Callable[[], None]) -> None:
        super().__init__(config)
        self._on_ready = on_ready

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        if self.started and not self.should_exit:
            self._on_ready()


def main(argv: Sequence[str] | None = None) -> int:
    multiprocessing.freeze_support()
    args = parse_args(argv)
    interactive = getattr(sys, "frozen", False) and not args.no_browser
    try:
        return run(args, interactive=interactive)
    except Exception:
        # Startup exceptions may include third-party configuration details;
        # existing logging filters redact them, while dialogs stay generic.
        logging.getLogger(__name__).exception("AiNiee 启动失败 / AiNiee startup failed")
        if interactive:
            _notify_startup("startup_failed")
        return 1


def run(args: argparse.Namespace, *, interactive: bool = False) -> int:

    from ModuleFolders.Infrastructure.Platform.RuntimeSetup import (
        migrate_config_if_needed,
        prepare_working_directory,
    )
    from ModuleFolders.Infrastructure.Platform.SingleInstance import acquire_app_mutex
    from ModuleFolders.Log.LogSystem import install
    from Server.app import create_app

    # 启动协议必须写入原始 stdout，避免 token 经日志桥进入文件或推送通道。
    protocol_stdout = sys.stdout
    os.chdir(prepare_working_directory())
    install()
    logger = logging.getLogger(__name__)
    if not acquire_app_mutex() and os.environ.get("AINIEE_ALLOW_MULTI_INSTANCE") != "1":
        logger.warning("AiNiee 已在运行，本次启动退出（设 AINIEE_ALLOW_MULTI_INSTANCE=1 可绕过）")
        if interactive:
            _notify_startup("already_running")
        return 0
    migrate_config_if_needed()

    generated_token = args.token is None
    token = args.token if args.token is not None else secrets.token_urlsafe(32)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind((HOST, args.port))
        except OSError:
            logger.error("无法监听 %s:%s，请检查端口是否被占用", HOST, args.port)
            if interactive:
                _notify_startup("port_busy")
            return 1
        port = listener.getsockname()[1]
        origin = f"http://{HOST}:{port}"

        def request_shutdown() -> None:
            server.should_exit = True

        browser_failed = False

        async def launch_browser() -> None:
            nonlocal browser_failed
            opened = await asyncio.to_thread(_open_browser, browser_url(port, token, development=args.dev))
            if not opened and interactive:
                # Do not leave an inaccessible invisible service behind when
                # the OS has no browser. Shutdown still waits for final saves.
                browser_failed = True
                request_shutdown()
                await asyncio.to_thread(_notify_startup, "browser_failed")

        browser_task = None

        def on_ready() -> None:
            nonlocal browser_task
            _write_ready(protocol_stdout, port, token, generated_token)
            if (args.dev or args.web) and not args.no_browser:
                browser_task = asyncio.create_task(launch_browser())

        app = create_app(
            token,
            allowed_origins=(*DEV_ORIGINS, origin),
            shutdown_callback=request_shutdown,
            frontend_dir=frontend_directory() if args.web else None,
        )
        config = uvicorn.Config(
            app,
            host=HOST,
            port=port,
            access_log=False,
            proxy_headers=False,
            log_level="info",
        )
        _protect_server_logs()
        server = ReadyServer(config, on_ready)
        try:
            server.run(sockets=[listener])
        except SystemExit as error:
            if error.code not in (None, 0):
                if interactive:
                    _notify_startup("startup_failed")
                return 1
        if not server.started and interactive:
            _notify_startup("startup_failed")
        return 0 if server.started and not browser_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
