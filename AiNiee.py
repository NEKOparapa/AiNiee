"""启动仅监听本机的 AiNiee API 服务。"""

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
from urllib.parse import urlencode

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
    parser.add_argument("--port", type=_port, default=8000, help="listen port; 0 selects a free port")
    parser.add_argument("--token", type=_token, help="Bearer token; omitted to generate a random token")
    parser.add_argument("--dev", action="store_true", help="open the frontend development server after startup")
    return parser.parse_args(argv)


def development_url(port: int, token: str) -> str:
    fragment = urlencode({"api": f"http://{HOST}:{port}", "token": token})
    return f"{DEV_ORIGIN}/#{fragment}"


def _open_browser(url: str) -> None:
    try:
        opened = webbrowser.open(url)
    except Exception:
        # 异常文本可能包含带有凭证的完整 URL，因此只记录通用诊断。
        logging.getLogger(__name__).warning("无法自动打开前端，请手动打开前端开发地址")
        return
    if not opened:
        logging.getLogger(__name__).warning("未找到可用浏览器，请手动打开前端开发地址")


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
    args = parse_args(argv)
    multiprocessing.freeze_support()

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
        return 0
    migrate_config_if_needed()

    generated_token = args.token is None
    token = args.token if args.token is not None else secrets.token_urlsafe(32)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind((HOST, args.port))
        except OSError:
            logger.error("无法监听 %s:%s，请检查端口是否被占用", HOST, args.port)
            return 1
        port = listener.getsockname()[1]
        origin = f"http://{HOST}:{port}"

        def request_shutdown() -> None:
            server.should_exit = True

        def on_ready() -> None:
            if generated_token:
                print(f"TOKEN {token}", file=protocol_stdout, flush=True)
            print(f"READY {port}", file=protocol_stdout, flush=True)
            if args.dev:
                asyncio.get_running_loop().run_in_executor(None, _open_browser, development_url(port, token))

        app = create_app(
            token,
            allowed_origins=(*DEV_ORIGINS, origin),
            shutdown_callback=request_shutdown,
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
        server.run(sockets=[listener])
        return 0 if server.started else 1


if __name__ == "__main__":
    raise SystemExit(main())
