"""Build and place the self-contained service beside the independent desktop."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def pyinstaller_command(arch=None):
    command = [
        str(ROOT / "Tools" / "backend_entry.py"), "--name=AiNieeBackend",
        "--onedir", "--windowed" if sys.platform == "darwin" else "--console",
        "--clean", "--noconfirm", "--noupx",
        f"--paths={ROOT}", f"--distpath={ROOT / 'build' / 'backend-dist'}",
        f"--workpath={ROOT / 'build' / 'backend-work'}", f"--specpath={ROOT / 'build'}",
        f"--additional-hooks-dir={ROOT / 'Tools' / 'Packaging' / 'hooks'}",
        f"--add-data={ROOT / 'Backend' / 'resources'}{os.pathsep}Backend/resources",
        "--collect-submodules=Backend", "--collect-submodules=tiktoken_ext",
        "--collect-submodules=uvicorn", "--copy-metadata=tiktoken",
        "--copy-metadata=pymupdf",
        "--copy-metadata=mcp", "--copy-metadata=mcp-types",
    ]
    for package in ("babeldoc", "mediapipe", "chardet", "sklearn", "rich", "magika"):
        command.append(f"--collect-all={package}")
    for package in ("Frontend", "PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter",
                    "IPython", "pytest", "jax", "jaxlib", "torch", "tensorflow", "skimage"):
        command.append(f"--exclude-module={package}")
    if arch:
        command.append(f"--target-arch={arch}")
    if sys.platform == "darwin":
        command.append("--osx-bundle-identifier=com.nekoparapa.AiNiee.backend")
    return command


def build_backend(destination, arch=None):
    from Tools.ffmpeg_bundle import pyinstaller_media_args
    subprocess.run([sys.executable, "-m", "PyInstaller", *pyinstaller_command(arch),
                    *pyinstaller_media_args(arch)], cwd=ROOT, check=True)
    # A plain onedir tree is not a valid nested macOS bundle: codesign treats
    # dotted data directories (such as *.dist-info) as malformed code bundles.
    # Let PyInstaller's BUNDLE arrange Frameworks/Resources and their symlinks.
    name = "AiNieeBackend.app" if sys.platform == "darwin" else "AiNieeBackend"
    shutil.copytree(ROOT / "build" / "backend-dist" / name, destination, symlinks=True)


def check_release(destination):
    executable = (destination / "Contents" / "MacOS" / "AiNieeBackend" if sys.platform == "darwin"
                  else destination / "AiNieeBackend.exe")
    with TemporaryDirectory(prefix="ainiee release check ") as working:
        for check in ("--check-media-tools", "--check-pdf-runtime"):
            subprocess.run([str(executable.resolve()), check], cwd=working,
                           env={**os.environ, "PATH": ""}, check=True, timeout=120,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--target-arch")
    options = parser.parse_args()
    build_backend(options.destination, options.target_arch)
