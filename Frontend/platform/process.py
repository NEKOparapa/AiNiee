"""Launch the desktop consistently from script, module and frozen entry points."""
import os
import subprocess
import sys

from Frontend.core.paths import executable_root, repo_root


def desktop_command():
    arguments = sys.argv[1:]
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, str(repo_root() / "AiNiee.py"), *arguments]


def launch_desktop():
    return subprocess.Popen(
        desktop_command(),
        cwd=str(executable_root()),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
