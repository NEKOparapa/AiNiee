"""Keep the desktop UI and its dependencies out of the server migration."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_PREFIXES = ("pyqt", "pyside", "qfluent", "qframeless", "userinterface")


def test_application_has_no_ui_or_transport_imports():
    violations = []
    for path in (ROOT / "ModuleFolders" / "Application").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for module in modules:
                root = module.split(".")[0].lower()
                if root.startswith(DESKTOP_PREFIXES) or root in ("fastapi", "starlette"):
                    violations.append(f"{path.name}:{node.lineno}: {module}")
    assert not violations, violations


def test_runtime_sources_and_requirements_remain_headless():
    assert not (ROOT / "UserInterface").exists()
    paths = [ROOT / "AiNiee.py"]
    for directory in ("ModuleFolders", "Server", "StevExtraction"):
        paths.extend((ROOT / directory).rglob("*.py"))
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(module.lower().startswith(DESKTOP_PREFIXES) for module in modules), path
    for name in ("requirements.txt", "requirements_no_deps.txt"):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            assert not line.strip().lower().startswith((*DESKTOP_PREFIXES, "pyobjc")), line
