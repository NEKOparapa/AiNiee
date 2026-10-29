"""Real application launcher with fixed external-provider boundaries for E2E.

This module is only used by Playwright; production entry points do not import
it or accept a test mode. User configuration remains isolated by the fixture.
"""

import ipaddress
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import httpx


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def fixed_models(self, url, *args, **kwargs):
    if str(url) != "https://llm.invalid/v1/models":
        raise AssertionError("E2E only permits the fixed mock model endpoint")
    return httpx.Response(
        200,
        json={"data": [{"id": "fixed-mock-model"}, {"id": "fixed-second-model"}]},
        request=httpx.Request("GET", url),
    )


def fixed_llm(self, messages, system_prompt, platform_config):
    return False, "", "This is a fixed mock response.", 8, 4


def only_loopback(original):
    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else ""
        try:
            allowed = host == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = False
        if not allowed:
            raise AssertionError("E2E must not connect to external services")
        return original(self, address)
    return guarded


def main():
    from ModuleFolders.Infrastructure.Tokener.TiktokenLoader import initialize_tiktoken

    initialize_tiktoken()
    from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
    from AiNiee import main as application_main

    with (
        patch.object(httpx.Client, "get", fixed_models),
        patch.object(LLMRequester, "sent_request", fixed_llm),
        patch.object(socket.socket, "connect", only_loopback(socket.socket.connect)),
        patch.object(socket.socket, "connect_ex", only_loopback(socket.socket.connect_ex)),
    ):
        return application_main()


if __name__ == "__main__":
    raise SystemExit(main())
