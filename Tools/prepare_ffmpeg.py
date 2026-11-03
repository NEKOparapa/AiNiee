"""Fetch the pinned, unmodified FFmpeg source used by the release builders."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "Tools" / "ffmpeg-source.json"


def file_sha256(path):
    with Path(path).open("rb") as reader:
        return hashlib.file_digest(reader, "sha256").hexdigest()


def prepare_source():
    spec = json.loads(MANIFEST.read_text(encoding="utf-8"))
    directory = ROOT / "build" / "ffmpeg-source"
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"ffmpeg-{spec['version']}.tar.xz"
    if not archive.is_file() or file_sha256(archive) != spec["sha256"]:
        temporary = archive.with_suffix(".download")
        try:
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "AiNiee-release-builder"})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as writer:
                shutil.copyfileobj(response, writer)
            if file_sha256(temporary) != spec["sha256"]:
                raise RuntimeError("FFmpeg source checksum mismatch")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    # Overwrite from the verified source so a local modification cannot silently
    # enter the build. Builds use a separate per-platform working directory.
    with tarfile.open(archive) as source:
        source.extractall(directory, filter="data")
    return directory / f"ffmpeg-{spec['version']}"


if __name__ == "__main__":
    print(prepare_source())
