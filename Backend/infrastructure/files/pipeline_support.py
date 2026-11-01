"""Small shared helpers for explicit-model file operations."""
import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_sequence_digest(texts) -> str:
    data = json.dumps(list(texts), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
