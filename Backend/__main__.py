import argparse
import logging
import os


def main():
    from Backend.core.paths import user_log_dir
    # Only the backend owns this rotating log; child stdout is never another
    # open handle to the same file (which would break rotation on Windows).
    os.environ["AINIEE_LOG_DIR"] = os.environ.get("AINIEE_BACKEND_LOG_DIR", str(user_log_dir() / "backend"))
    from Backend.core.log_system import install
    log_path = install()
    logger = logging.getLogger("AiNiee.backend")
    logger.info("Starting AiNiee backend (PID %s), log file: %s", os.getpid(), log_path)
    parser = argparse.ArgumentParser(description="AiNiee FastAPI backend (single worker)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3389)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("AINIEE_API_TOKEN"):
        parser.error("监听非本机地址时，请设置 AINIEE_API_TOKEN")
    import uvicorn
    from Backend.api.app import app
    # Route server/access logs through the backend handlers, preserving their
    # levels and redaction without a second console-to-file copy.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port, log_level="info", log_config=None))
    app.state.shutdown = lambda: setattr(server, "should_exit", True)
    server.run()


if __name__ == "__main__":
    main()
