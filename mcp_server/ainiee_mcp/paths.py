"""Resolve AiNiee's config.json path WITHOUT importing AiNiee (stay PyQt-free).

Mirrors ModuleFolders/Config/FilePathConfig.config_path() (the source of truth):
  macOS:                ~/Library/Application Support/AiNiee/config.json
  AINIEE_USER_DATA_DIR: <that dir>/config.json
  otherwise (source):   <repo root>/Resource/config.json
Plus an MCP-only direct override AINIEE_CONFIG.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path

APP_NAME = "AiNiee"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def repo_root() -> Path:
    """AiNiee repo root. Derived from this file's location (<repo>/mcp_server/ainiee_mcp/paths.py)
    or overridden via AINIEE_REPO."""
    override = os.environ.get("AINIEE_REPO")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def user_data_root() -> Path:
    override = os.environ.get("AINIEE_USER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if _is_macos():
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return repo_root()


def config_path() -> Path:
    """Absolute path to the live config.json AiNiee reads/writes."""
    direct = os.environ.get("AINIEE_CONFIG")
    if direct:
        return Path(direct).expanduser().resolve()
    if _is_macos() or os.environ.get("AINIEE_USER_DATA_DIR"):
        return user_data_root() / "config.json"
    return repo_root() / "Resource" / "config.json"
