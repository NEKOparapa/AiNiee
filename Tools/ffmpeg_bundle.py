"""Validate and collect the native media tools produced by build_ffmpeg.sh."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def target_key(arch=None):
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform)
    cpu = (arch or platform.machine()).lower()
    cpu = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(cpu, cpu)
    if (system, cpu) not in (("windows", "x86_64"), ("macos", "x86_64"), ("macos", "arm64")):
        raise RuntimeError(f"Unsupported FFmpeg release target: {system}-{cpu}")
    return f"{system}-{cpu}"


def stage_directory(arch=None):
    return ROOT / "build" / "media-tools" / target_key(arch)


def validate_stage(directory):
    spec = json.loads((ROOT / "Tools" / "ffmpeg-source.json").read_text(encoding="utf-8"))
    names = ["ffmpeg", "ffprobe"]
    if sys.platform == "win32":
        names = [name + ".exe" for name in names]
    required = [*names, "COPYING.LGPLv2.1", "LICENSE.md", "BUILD-INFO.txt", "ffmpeg-source.json",
                "prepare_ffmpeg.py", "build_ffmpeg.sh", f"ffmpeg-{spec['version']}.tar.xz"]
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise RuntimeError(f"Incomplete bundled FFmpeg in {directory}: {', '.join(missing)}. "
                           "Run Tools/prepare_ffmpeg.py and Tools/scripts/build_ffmpeg.sh first.")
    staged = json.loads((directory / "ffmpeg-source.json").read_text(encoding="utf-8"))
    if staged != spec:
        raise RuntimeError("The staged FFmpeg is from an older source manifest; rebuild it")
    from Tools.prepare_ffmpeg import file_sha256
    if file_sha256(directory / f"ffmpeg-{spec['version']}.tar.xz") != spec["sha256"]:
        raise RuntimeError("The staged FFmpeg source archive is corrupted")
    from Backend.core.media_tools_check import check_media_tools
    result = check_media_tools(*(directory / name for name in names))
    if any(f"version {spec['version']}" not in version for version in result["versions"].values()):
        raise RuntimeError("FFmpeg binaries do not match the pinned source version")
    return names


def pyinstaller_media_args(arch=None):
    directory = stage_directory(arch)
    names = validate_stage(directory)
    result = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            kind = "binary" if path.name in names else "data"
            result.append(f"--add-{kind}={path}{os.pathsep}media-tools")
    return result


def check_release(destination):
    executable = (destination / "Contents" / "MacOS" / "AiNieeBackend" if sys.platform == "darwin"
                  else destination / "AiNieeBackend.exe")
    # No local source tree, user configuration or service startup is needed.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix="ainiee release check ") as working:
        subprocess.run([str(executable.resolve()), "--check-media-tools"], cwd=working,
                       env={**os.environ, "PATH": ""}, check=True, timeout=120,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-arch")
    arguments = parser.parse_args()
    validate_stage(stage_directory(arguments.target_arch))
    print("Bundled FFmpeg/ffprobe passed the offline smoke check")
