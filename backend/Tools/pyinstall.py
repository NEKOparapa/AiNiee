"""Build a Windows portable folder and ZIP without copying local user data.

Run with Python 3.12 from a Git checkout. Each invocation owns new build/output
directories; it never overwrites a previous package or a running installation.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
RESOURCE_DIRECTORIES = frozenset({
    "Localization", "Logo", "Models", "platforms", "Prompt", "Regex", "Version",
})
REQUIRED_RESOURCES = frozenset({
    "Resource/Logo/Avatar.png",
    "Resource/Models/mediapipe/language_detector.tflite",
    "Resource/Models/tiktoken/9b5ad71b2ce5302211f9c61530b329a4922fc6a4",
    "Resource/Models/tiktoken/fb374d419588a4632f3f557e76b4b70aebbca790",
    "Resource/platforms/preset.json",
    "Resource/Prompt/Translate/common_system_zh.txt",
    "Resource/Regex/check_regex.json",
    "Resource/Version/version.json",
})
FRONTEND_SUFFIXES = frozenset({
    ".html", ".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".webp",
    ".gif", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".avif", ".webmanifest",
})
PACKAGE_ROOT_ENTRIES = frozenset({
    "AiNiee.exe", "_internal", "portable.txt", "README.txt", "LICENSE", "build-info.json",
})
COLLECT_ALL = (
    "babeldoc", "chardet", "sklearn", "rich", "bitstring", "opencc", "magika", "mediapipe",
)
COLLECT_SUBMODULES = (
    "ModuleFolders.Domain.FileReader", "ModuleFolders.Domain.FileOutputer", "uvicorn",
)


@dataclass(frozen=True)
class BuildPaths:
    root: Path
    work: Path
    output: Path

    @property
    def payload(self) -> Path:
        return self.work / "payload"

    @property
    def package(self) -> Path:
        return self.output / "AiNiee"


def _inside(parent: Path, child: Path) -> Path:
    parent = parent.resolve()
    resolved = child.resolve()
    if resolved == parent or not resolved.is_relative_to(parent):
        raise ValueError(f"Path must stay below {parent.name}: {child.name}")
    return resolved


def _source_file(base: Path, path: Path) -> Path:
    """Reject links, missing files and directory traversal before copying."""
    base = base.resolve()
    candidate = _inside(base, path)
    if not path.is_file():
        raise ValueError(f"Required package file is missing: {path.name}")
    # Reject links that point within the tree too: a tracked link must not turn
    # an unrelated local file into a distributable resource.
    current = path.absolute()
    while current != base:
        if current.is_symlink() or current.is_junction():
            raise ValueError(f"Linked files/directories are not package inputs: {path.name}")
        if current.parent == current:
            raise ValueError("Package input has no expected parent")
        current = current.parent
    return candidate


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Packaging requires Git and a complete Git checkout") from error
    return result.stdout


def resource_manifest(root: Path) -> list[Path]:
    """Return backend-relative paths using an allowlist and Git tracking."""
    backend = root / "backend"
    selected = []
    names = _git(backend, "ls-files", "-z", "--", "Resource").decode("utf-8").split("\0")
    for name in names:
        if not name:
            continue
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Invalid resource path in Git index")
        if len(relative.parts) < 3 or relative.parts[0] != "Resource":
            continue
        if relative.parts[1] not in RESOURCE_DIRECTORIES:
            continue
        source = backend.joinpath(*relative.parts)
        _source_file(backend / "Resource", source)
        selected.append(Path(*relative.parts))
    missing = REQUIRED_RESOURCES - {path.as_posix() for path in selected}
    if missing:
        raise ValueError("Required tracked resources are missing: " + ", ".join(sorted(missing)))
    return sorted(selected)


def frontend_manifest(root: Path) -> list[Path]:
    base = root / "frontend" / "dist"
    _source_file(base, base / "index.html")
    selected = []
    for source in sorted(base.rglob("*")):
        if source.is_dir():
            if source.is_symlink() or source.is_junction():
                raise ValueError("Linked frontend directories cannot be packaged")
            continue
        _source_file(base, source)
        relative = source.relative_to(base)
        if source.suffix.lower() not in FRONTEND_SUFFIXES or any(part.startswith(".") for part in relative.parts):
            raise ValueError(f"Unexpected frontend build file: {relative.as_posix()}")
        selected.append(relative)
    if not any(path.suffix == ".js" and path.parts[0] == "assets" for path in selected):
        raise ValueError("Frontend build has no JavaScript assets; run npm run build")
    return selected


def create_build_paths(root: Path = ROOT) -> BuildPaths:
    root = root.resolve()
    build_id = "windows-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    work = _inside(root, root / "build" / build_id)
    output = _inside(root, root / "dist" / build_id)
    work.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    return BuildPaths(root, work, output)


def stage_payload(paths: BuildPaths) -> list[dict[str, str]]:
    resources = resource_manifest(paths.root)
    frontend = frontend_manifest(paths.root)
    _inside(paths.root / "build", paths.payload)
    paths.payload.mkdir(parents=True, exist_ok=False)
    staged = []
    inputs = [(paths.root / "backend" / path, path) for path in resources]
    inputs += [(paths.root / "frontend" / "dist" / path, Path("frontend/dist") / path) for path in frontend]
    for source, relative in inputs:
        target = _inside(paths.payload, paths.payload / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        staged.append({"path": relative.as_posix(), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    # Never read Resource/config.json: it may contain the builder's API keys.
    default_config = paths.payload / "Resource" / "config.json"
    default_config.write_text("{}\n", encoding="utf-8")
    staged.append({"path": "Resource/config.json", "sha256": hashlib.sha256(default_config.read_bytes()).hexdigest()})
    return staged


def package_version(root: Path) -> str:
    document = json.loads((root / "backend" / "Resource" / "Version" / "version.json").read_text(encoding="utf-8"))
    match = re.fullmatch(r"(?:AiNiee\s+)?(\d+(?:\.\d+){1,3})", document["version"])
    if not match:
        raise ValueError("Version must contain a numeric dotted release version")
    return match.group(1)


def build_metadata(root: Path, staged: list[dict[str, str]], *, console: bool) -> dict:
    packages = {}
    for distribution in ("pyinstaller", "pyinstaller-hooks-contrib", "fastapi", "uvicorn", "mediapipe", "BabelDOC"):
        try:
            packages[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            packages[distribution] = "not-installed"
    return {
        "application": "AiNiee", "version": package_version(root),
        "platform": "windows-x64", "python": platform.python_version(),
        "console": console, "built_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": _git(root, "rev-parse", "HEAD").decode("ascii").strip(),
        "source_dirty": bool(_git(root, "status", "--porcelain", "--untracked-files=no")),
        "frontend_lock_sha256": hashlib.sha256((root / "frontend" / "package-lock.json").read_bytes()).hexdigest(),
        "packages": packages, "payload": staged,
    }


def pyinstaller_command(paths: BuildPaths, *, console: bool = False) -> list[str]:
    command = [
        str(paths.root / "backend" / "AiNiee.py"), "--name=AiNiee", "--onedir", "--contents-directory=_internal",
        "--console" if console else "--windowed", "--noupx",
        f"--icon={paths.payload / 'Resource' / 'Logo' / 'Avatar.png'}",
        f"--paths={paths.root / 'backend'}", f"--distpath={paths.output}",
        f"--workpath={paths.work / 'pyinstaller'}", f"--specpath={paths.work}",
        f"--add-data={paths.payload / 'Resource'}{os.pathsep}Resource",
        f"--add-data={paths.payload / 'frontend' / 'dist'}{os.pathsep}frontend/dist",
        "--hidden-import=tiktoken_ext.openai_public", "--collect-data=language_data",
        "--exclude-module=jaxlib",
    ]
    command += [f"--collect-all={name}" for name in COLLECT_ALL]
    command += [f"--collect-submodules={name}" for name in COLLECT_SUBMODULES]
    return command


def finish_package(paths: BuildPaths, metadata: dict) -> tuple[Path, str]:
    _inside(paths.root / "dist", paths.output)
    package = _inside(paths.output, paths.package)
    for name in ("AiNiee.exe", "_internal/frontend/dist/index.html", "_internal/Resource/config.json"):
        _source_file(package, package / name)
    if json.loads((package / "_internal/Resource/config.json").read_text(encoding="utf-8")) != {}:
        raise ValueError("The bundled default config must be empty")
    if {path.name for path in package.iterdir()} - PACKAGE_ROOT_ENTRIES:
        raise ValueError("Unexpected files in package root; refusing to archive possible user data")
    (package / "portable.txt").write_text("Portable data stays beside AiNiee.exe when writable.\n", encoding="utf-8")
    (package / "README.txt").write_text(
        "AiNiee Windows 便携版 / Windows portable edition\n\n"
        "完整解压此文件夹，双击 AiNiee.exe。就绪后会自动打开默认浏览器。\n"
        "请保留 _internal 和 portable.txt；不要从 ZIP 内直接运行。\n"
        "关闭网页不会退出服务；请使用页面的退出应用按钮等待保存后退出。\n"
        "用户配置在 Resource/config.json，项目进度在 ProjectCache，日志在 Logs。\n"
        "升级前备份这些用户数据，勿以默认配置覆盖。\n\n"
        "Extract the entire folder, then double-click AiNiee.exe. Keep _internal\n"
        "and portable.txt. A browser opens once the local service is ready.\n"
        "Closing the browser does not stop the service; use Exit application.\n"
        "Back up Resource/config.json and ProjectCache before upgrading.\n",
        encoding="utf-8",
    )
    license_path = _source_file(paths.root, paths.root / "LICENSE")
    shutil.copyfile(license_path, package / "LICENSE")
    (package / "build-info.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive = _inside(paths.output, paths.output / f"AiNiee-{metadata['version']}-windows-x64.zip")
    if archive.exists():
        raise FileExistsError("Refusing to overwrite an existing package ZIP")
    partial = archive.with_suffix(".zip.partial")
    with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(package.rglob("*")):
            if path.is_symlink() or path.is_junction():
                raise ValueError("Package output contains links")
            if path.is_file():
                _source_file(package, path)
                bundle.write(path, Path("AiNiee") / path.relative_to(package))
    partial.rename(archive)
    with archive.open("rb") as reader:
        digest = hashlib.file_digest(reader, "sha256").hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return archive, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--console", action="store_true", help="build a visible diagnostic console instead of the default windowed executable")
    parser.add_argument("--skip-frontend-build", action="store_true", help="reuse an already-built frontend/dist (still validated)")
    args = parser.parse_args(argv)
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"} or sys.version_info[:2] != (3, 12):
        parser.error("Build using Windows x64 Python 3.12")
    if not args.skip_frontend_build:
        npm = shutil.which("npm.cmd")
        if not npm:
            parser.error("Node.js/npm are required; run npm ci in frontend first")
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    paths = create_build_paths()
    staged = stage_payload(paths)
    metadata = build_metadata(paths.root, staged, console=args.console)
    # Importing this module is safe for tests and documentation tools.
    if str(ROOT / "backend") not in sys.path:
        sys.path.insert(0, str(ROOT / "backend"))
    import PyInstaller.__main__

    PyInstaller.__main__.run(pyinstaller_command(paths, console=args.console))
    archive, digest = finish_package(paths, metadata)
    print(f"EXECUTABLE {paths.package / 'AiNiee.exe'}")
    print(f"PACKAGE {archive}")
    print(f"SHA256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
