"""Generated-image identities, safe paths and atomic artifact writes."""
import hashlib
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from Backend.application.pipeline_common import PipelineError
from Backend.core.protocol import to_wire
from Backend.domain.models.intermediate import validate_storage_path
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.images.source import load_image

_INVALID = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def item_text_identity(file):
    file = to_wire(file)
    return digest([{key: item.get(key) for key in ("item_id", "source_text", "translated_text", "locator")}
                   for item in file.get("items", [])])


def generation_artifact_current(file):
    """Logical freshness only; exports separately verify pixels and disk hashes."""
    file = to_wire(file)
    state = file.get("extra", {}).get("image_generation", {})
    artifact = state.get("artifact") if isinstance(state, dict) else None
    if (not isinstance(state, dict) or state.get("status") != "complete" or not isinstance(artifact, dict)
            or state.get("source_sha256") != file.get("source_ref", {}).get("sha256")
            or not artifact.get("path") or not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256", "")))
            or artifact.get("format") != "png"
            or not isinstance(state.get("identity"), dict) or digest(state["identity"]) != state.get("fingerprint")):
        return False
    if state.get("text_source") == "items" and state.get("text_identity") != item_text_identity(file):
        return False
    return True


def output_directory(value):
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip() or "\x00" in str(value):
        raise PipelineError("INVALID_OUTPUT_PATH", "输出目录必须为非空路径", 422)
    try:
        path = Path(value).expanduser().resolve()
        if any(_INVALID.search(p) or _RESERVED.match(p) or p.endswith((".", " ")) for p in path.parts if p != path.anchor):
            raise ValueError()
        for ancestor in (path, *path.parents):
            if ancestor.exists():
                if not ancestor.is_dir():
                    raise ValueError()
                break
        return path
    except (ValueError, OSError, RuntimeError):
        raise PipelineError("INVALID_OUTPUT_PATH", "输出目录无效", 422) from None


def safe_target(root, relative):
    try:
        validate_storage_path(relative)
        parts = Path(relative.replace("\\", "/")).parts
        if any(_INVALID.search(p) or _RESERVED.match(p) or p.endswith((".", " ")) for p in parts):
            raise ValueError()
        destination = (root / Path(*parts)).resolve()
        if not destination.is_relative_to(root):
            raise ValueError()
        return destination
    except (ValueError, OSError, RuntimeError):
        raise PipelineError("INVALID_OUTPUT_PATH", "输出文件名或相对路径无效", 422) from None


def atomic_bytes(destination, content, *, root, overwrite=True, protected=()):
    destination.parent.mkdir(parents=True, exist_ok=True)
    resolved = destination.resolve()
    if not resolved.is_relative_to(root) or os.path.normcase(str(resolved)) in protected:
        raise PipelineError("INVALID_OUTPUT_PATH", "输出路径越界或指向源文件", 422)
    temporary = None
    try:
        with NamedTemporaryFile("wb", dir=destination.parent, suffix=".tmp", delete=False) as writer:
            temporary = Path(writer.name)
            writer.write(content)
            writer.flush()
            os.fsync(writer.fileno())
        if overwrite:
            os.replace(temporary, destination)
        elif os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    except FileExistsError:
        raise PipelineError("OUTPUT_EXISTS", "输出文件已存在", 409) from None
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def atomic_json(path, value, *, root):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode(), root=root)


def verified_generated_image(file):
    if not generation_artifact_current(file):
        raise PipelineError("IMAGE_GENERATION_REQUIRED", "图片尚未生成，或原文/译文变化后需要重新生成", 409)
    state = file.extra["image_generation"] if hasattr(file, "extra") else file["extra"]["image_generation"]
    artifact = state["artifact"]
    try:
        path = Path(artifact["path"]).resolve(strict=True)
        if not path.is_file() or file_sha256(path) != artifact["sha256"]:
            raise ValueError()
        image, metadata = load_image(path)
        if (metadata["width"], metadata["height"]) != (artifact["width"], artifact["height"]) or metadata["format"] != "png" or file_sha256(path) != artifact["sha256"]:
            image.close()
            raise ValueError()
        return image, path
    except (OSError, ValueError, KeyError, TypeError):
        raise PipelineError("IMAGE_GENERATION_ARTIFACT_CHANGED", "生成图片不存在、已改变或元数据不匹配", 409) from None
