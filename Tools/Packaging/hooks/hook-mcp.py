"""Collect the MCP runtime without importing its optional development CLI."""
from PyInstaller.utils.hooks import collect_submodules

# mcp.cli exits during import when the optional mcp[cli] dependencies are absent.
# Filter before recursion; excluding it after collect_submodules is too late.
hiddenimports = collect_submodules(
    "mcp", filter=lambda name: name != "mcp.cli" and not name.startswith("mcp.cli.")
)
excludedimports = ["mcp.cli"]
