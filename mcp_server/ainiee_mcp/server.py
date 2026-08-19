"""ainiee-mcp entry point. Builds the FastMCP server and runs it over stdio."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .backend import get_backend
from .config_store import ConfigStore
from .tools import register_all


def build_server() -> FastMCP:
    mcp = FastMCP("ainiee")
    register_all(mcp, get_backend(), ConfigStore())
    return mcp


def main() -> None:
    build_server().run()  # stdio transport by default


if __name__ == "__main__":
    main()
