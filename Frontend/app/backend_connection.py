"""Reuse a healthy service or start a local backend in a separate process."""
import ipaddress
import logging
import os
import subprocess
import time
from urllib.parse import urlsplit

import httpx

from Frontend.platform.backend_process import backend_port_available, backend_startup_lock, launch_backend
from Frontend.services.backend_client import BackendClient, BackendError


def _local_endpoint(url):
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.path not in ("", "/") or parts.query or parts.fragment:
        return None
    host = parts.hostname
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                return None
        except ValueError:
            return None
    return host, parts.port or 80


def _check_health(client, timeout):
    try:
        health = client.request("GET", "/health", timeout=timeout)
    except ValueError as error:
        raise BackendError("连接地址未返回有效的 AiNiee 后端信息") from error
    if not isinstance(health, dict) or health.get("service") != "AiNiee":
        raise BackendError("连接地址不是 AiNiee 后端服务")
    if health.get("protocol") != 1:
        raise BackendError("后端协议版本不兼容")


def _not_ready(error):
    return isinstance(error.__cause__, (httpx.ConnectError, httpx.TimeoutException))


def connect_backend(url=None, *, startup_timeout=60):
    url = url or os.environ.get("AINIEE_BACKEND_URL", "http://127.0.0.1:3389")
    client = BackendClient(url, os.environ.get("AINIEE_API_TOKEN", ""))
    process = None
    deadline = time.monotonic() + startup_timeout
    try:
        try:
            _check_health(client, timeout=min(5, startup_timeout))
            return client
        except BackendError as error:
            endpoint = _local_endpoint(url)
            if not _not_ready(error) or endpoint is None:
                raise

        host, port = endpoint
        with backend_startup_lock(port, deadline):
            # Recheck under the cross-process lock: another desktop may have
            # started the service while we were waiting for this lock.
            while True:
                if time.monotonic() >= deadline:
                    detail = f"，后端日志：{log_path}" if process is not None else ""
                    raise BackendError(f"等待后端就绪超时：{url}{detail}")
                try:
                    _check_health(client, timeout=max(0.1, min(1, deadline - time.monotonic())))
                    client.backend_process = process
                    return client
                except BackendError as error:
                    if not _not_ready(error):
                        raise
                    # A slow listener must be given time to become ready. On
                    # Windows even an unused port can cause ConnectTimeout.
                    if (process is None
                            and isinstance(error.__cause__, (httpx.ConnectError, httpx.ConnectTimeout))
                            and backend_port_available(host, port)):
                        logging.getLogger("AiNiee.bootstrap").info("正在启动独立 FastAPI 后端：%s", url)
                        process, log_path = launch_backend(host, port)
                if process is not None and process.poll() is not None:
                    raise BackendError(f"后端启动失败（退出码 {process.returncode}），请检查依赖和日志：{log_path}")
                time.sleep(0.15)
    except Exception:
        # Clean up only the failed launch owned by this attempt; never terminate
        # a pre-existing service. Normal confirmed exit uses the HTTP API.
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        client.close()
        raise
