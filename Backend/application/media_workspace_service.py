"""Persistent, independent media previews over the public intermediate model."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
from tempfile import NamedTemporaryFile
import threading
import uuid
import zipfile

from Backend.application.pipeline_common import PipelineError
from Backend.core.paths import project_cache_root
from Backend.core.protocol import to_wire
from Backend.domain.models.cache_project import CacheProject
from Backend.domain.models.intermediate import normalize_project, parse_model
from Backend.infrastructure.files.audio_probe import AUDIO_EXTENSIONS
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.images.source import IMAGE_EXTENSIONS


MAX_ARCHIVE_ENTRIES = 10000
MAX_ARCHIVE_BYTES = 8 * 1024 ** 3
MAX_ARCHIVE_FILE_BYTES = 2 * 1024 ** 3
MAX_COMPRESSION_RATIO = 1000
_ID = re.compile(r"[a-f0-9]{32}\Z")
_INVALID_NAME = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _natural(value):
    return tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                 for part in re.split(r"(\d+)", str(value)))


def _atomic_json(path, value):
    temporary = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as writer:
            temporary = Path(writer.name)
            json.dump(value, writer, ensure_ascii=False, indent=2)
            writer.flush()
            os.fsync(writer.fileno())
        temporary.replace(path)
    except OSError as error:
        raise PipelineError("MEDIA_WORKSPACE_SAVE_FAILED", "无法保存媒体工作区", 500) from error
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def _stamp(path):
    info = path.stat()
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns}


def _content_identity(file):
    value = {"source": file["source_ref"], "items": file["items"]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _image_mode(model):
    return model.get("extra", {}).get("image_translation_mode", "ocr")


def _generation_identity(file):
    generation = file.get("extra", {}).get("image_generation", {})
    generation = generation if isinstance(generation, dict) else {}
    value = {"source": file["source_ref"], "fingerprint": generation.get("fingerprint"),
             "artifact": generation.get("artifact")}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _generation_matches(model, file):
    from Backend.application.image_generation_service import generation_artifact_current
    if not generation_artifact_current(file):
        return False
    generation = file.get("extra", {}).get("image_generation", {})
    settings = generation.get("settings", {})
    selected = model.get("extra", {}).get("image_generation_options", {})
    if not isinstance(settings, dict) or not isinstance(selected, dict):
        return False
    return all(selected.get(key) == settings.get(key)
               for key in ("source_language", "target_language", "text_mode", "prompt"))


def _generation_root(model, file):
    base = (project_cache_root() / "ImageGeneration").resolve()
    root = (base / model["project_id"] / file["file_id"]).resolve()
    if not root.is_relative_to(base) or root == base:
        raise PipelineError("MEDIA_INVALID_PREVIEW", "生成图片路径无效", 422)
    return root


def _selected_preview(document, file):
    if _image_mode(document["model"]) == "generation":
        registered = document.get("generation_previews", {}).get(file["file_id"])
        usable = registered and _generation_matches(document["model"], file)
        identity = _generation_identity(file)
    else:
        registered = document.get("previews", {}).get(file["file_id"])
        usable = bool(registered)
        identity = _content_identity(file)
    return registered if usable and registered.get("content_identity") == identity else None


def _preview_root(directory):
    root = (directory / "preview").resolve()
    if not root.is_relative_to(directory.resolve()):
        raise PipelineError("MEDIA_INVALID_PREVIEW", "媒体预览目录不能越出工作区", 409)
    return root


def _zip_relative(name):
    name = name.replace("\\", "/")
    stripped = name[:-1] if name.endswith("/") else name
    parts = stripped.split("/")
    if (not stripped or PureWindowsPath(stripped).drive or PurePosixPath(stripped).is_absolute()
            or any(p in ("", ".", "..") or _INVALID_NAME.search(p) or _RESERVED.match(p)
                   or p.endswith((" ", ".")) for p in parts)):
        raise PipelineError("MEDIA_UNSAFE_ARCHIVE", "ZIP 包含不安全或不兼容的文件路径")
    return PurePosixPath(*parts)


def _extract_archive(source, destination, extensions):
    """Preflight every member before writing; never use extract/extractall."""
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise PipelineError("MEDIA_ARCHIVE_LIMIT", "ZIP 文件数量超过导入上限")
            selected, occupied, total = [], {}, 0
            for info in entries:
                relative = _zip_relative(info.filename)
                key = relative.as_posix().casefold()
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))):
                    raise PipelineError("MEDIA_UNSAFE_ARCHIVE", "ZIP 不支持链接或特殊文件")
                if key in occupied:
                    raise PipelineError("MEDIA_UNSAFE_ARCHIVE", "ZIP 包含重复或大小写冲突路径")
                # A directory entry may precede its children, but a file cannot.
                for parent in relative.parents:
                    if str(parent) != "." and occupied.get(parent.as_posix().casefold()) is False:
                        raise PipelineError("MEDIA_UNSAFE_ARCHIVE", "ZIP 包含文件与目录冲突")
                if not info.is_dir() and any(old.startswith(key + "/") for old in occupied):
                    raise PipelineError("MEDIA_UNSAFE_ARCHIVE", "ZIP 包含文件与目录冲突")
                occupied[key] = info.is_dir()
                if info.is_dir() or relative.suffix.lower() not in extensions:
                    continue
                if info.flag_bits & 1:
                    raise PipelineError("MEDIA_ENCRYPTED_ARCHIVE", "请先解密 ZIP，再导入媒体文件")
                total += info.file_size
                if (info.file_size > MAX_ARCHIVE_FILE_BYTES or total > MAX_ARCHIVE_BYTES
                        or (info.file_size > 1024 ** 2 and info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO)):
                    raise PipelineError("MEDIA_ARCHIVE_LIMIT", "ZIP 展开大小或压缩比超过导入上限")
                selected.append((info, relative))
            if not selected:
                raise PipelineError("MEDIA_EMPTY_ARCHIVE", "ZIP 中没有支持的媒体文件")
            destination.mkdir(parents=True, exist_ok=False)
            expanded = 0
            for info, relative in selected:
                target = destination.joinpath(*relative.parts)
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise PipelineError("MEDIA_UNSAFE_ARCHIVE", "ZIP 路径越界")
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info) as reader, target.open("xb") as writer:
                    while chunk := reader.read(1024 * 1024):
                        written += len(chunk)
                        expanded += len(chunk)
                        if written > info.file_size or written > MAX_ARCHIVE_FILE_BYTES or expanded > MAX_ARCHIVE_BYTES:
                            raise PipelineError("MEDIA_ARCHIVE_LIMIT", "ZIP 实际展开大小超过导入上限")
                        writer.write(chunk)
                if written != info.file_size:
                    raise PipelineError("MEDIA_INVALID_ARCHIVE", "ZIP 文件大小校验失败")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as error:
        if isinstance(error, PipelineError):
            raise
        raise PipelineError("MEDIA_INVALID_ARCHIVE", "ZIP 无法读取或解压") from error


class MediaWorkspaceStore:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("AINIEE_MEDIA_WORKSPACE_DIR") or
                         project_cache_root() / "MediaWorkspaces").expanduser().resolve()
        self.lock = threading.RLock()

    def _directory(self, workspace_id):
        if not isinstance(workspace_id, str) or not _ID.fullmatch(workspace_id):
            raise PipelineError("MEDIA_WORKSPACE_NOT_FOUND", "媒体工作区不存在", 404)
        path = self.root / workspace_id
        if path.resolve().parent != self.root:
            raise PipelineError("MEDIA_WORKSPACE_NOT_FOUND", "媒体工作区路径无效", 404)
        return path

    def _read(self, workspace_id):
        directory = self._directory(workspace_id)
        try:
            document = json.loads((directory / "workspace.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PipelineError("MEDIA_WORKSPACE_NOT_FOUND", "媒体工作区不存在或无法读取", 404) from error
        if document.get("workspace_id") != workspace_id:
            raise PipelineError("MEDIA_WORKSPACE_INVALID", "媒体工作区信息不匹配", 409)
        return directory, document

    def _response(self, directory, document):
        files = []
        for storage_path, file in document["model"]["files"].items():
            preview = _selected_preview(document, file)
            base = f"/api/v2/media/{document['workspace_id']}/files/{file['file_id']}"
            entry = {"file_id": file["file_id"], "storage_path": storage_path,
                     "source_url": base + "/source", "translated_url": base + "/translated" if preview else None}
            if document["kind"] == "image":
                state = file.get("extra", {}).get("image_generation", {})
                state = state if isinstance(state, dict) else {}
                status = state.get("status", "pending")
                if status == "complete":
                    status = ("stale" if not _generation_matches(document["model"], file) else
                              "complete" if document.get("generation_previews", {}).get(file["file_id"]) else "unavailable")
                entry["generation_status"] = status
            files.append(entry)
        return {"status": document.get("status", "success"), "workspace_id": document["workspace_id"],
                "kind": document["kind"], "model": document["model"],
                "model_path": str(directory / "model.json"), "preview_dir": str(directory / "preview"),
                "report": document.get("report", {}), "files": files,
                "created_at": document["created_at"], "updated_at": document["updated_at"], "persisted": True}

    def _commit(self, directory, document):
        # The authoritative document is one atomic transaction, including model
        # and registered previews. model.json is a plain interchange copy.
        _atomic_json(directory / "workspace.json", document)
        _atomic_json(directory / "model.json", document["model"])

    def import_media(self, kind, paths, exclude_rule=""):
        if kind not in ("image", "audio") or not isinstance(paths, list) or not 1 <= len(paths) <= 100:
            raise PipelineError("MEDIA_INVALID_INPUT", "请选择图片或音频，以及 1 至 100 个输入路径", 422)
        if not isinstance(exclude_rule, str):
            raise PipelineError("MEDIA_INVALID_INPUT", "排除规则必须是字符串", 422)
        from Backend.application.image_read_service import read_image
        from Backend.application.audio_read_service import read_audio
        reader = read_image if kind == "image" else read_audio
        extensions = IMAGE_EXTENSIONS if kind == "image" else AUDIO_EXTENSIONS
        workspace_id = uuid.uuid4().hex
        directory = self._directory(workspace_id)
        directory.mkdir(parents=True, exist_ok=False)
        project = CacheProject(project_id=workspace_id, project_type=kind.title(), input_path=str(directory))
        report = {"read_files": 0, "item_count": 0, "errors": [], "warnings": [], "skipped_files": []}
        seen_inputs, seen_sources, used_keys = set(), set(), set()
        try:
            for ordinal, value in enumerate(paths, 1):
                try:
                    if not isinstance(value, str) or not value.strip():
                        raise PipelineError("MEDIA_INVALID_INPUT", "输入路径不能为空")
                    source = Path(value).expanduser().resolve(strict=True)
                    canonical = os.path.normcase(str(source))
                    if canonical in seen_inputs:
                        report["skipped_files"].append({"path": str(source), "reason": "duplicate_input"})
                        continue
                    seen_inputs.add(canonical)
                    is_archive = source.is_file() and source.suffix.lower() == ".zip"
                    target = source
                    if is_archive:
                        target = directory / "imports" / str(ordinal)
                        _extract_archive(source, target, extensions)
                    result = reader(target, {"exclude_rule": exclude_rule})
                    if not project.project_name:
                        project.project_name = source.stem if len(paths) == 1 else f"{len(paths)} 个媒体输入"
                    if len(paths) == 1 and not is_archive:
                        project.input_path = str(source)
                    for entry in result["report"].get("errors", []):
                        report["errors"].append({**entry, "input": str(source)})
                    report["warnings"].extend(result["report"].get("warnings", []))
                    report["skipped_files"].extend(result["report"].get("skipped_files", []))
                    for relative, file in result["model"].files.items():
                        file_source = os.path.normcase(file.source_ref["path"])
                        if file_source in seen_sources:
                            report["skipped_files"].append({"path": relative, "reason": "duplicate_input"})
                            continue
                        seen_sources.add(file_source)
                        prefix = f"{source.stem}/" if len(paths) > 1 and (is_archive or source.is_dir()) else ""
                        storage = prefix + relative
                        if storage.casefold() in used_keys:
                            storage = f"input-{ordinal}/" + storage
                        while storage.casefold() in used_keys:
                            storage = "input/" + storage
                        used_keys.add(storage.casefold())
                        file.storage_path = storage
                        file.file_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ainiee:{workspace_id}:{storage}").hex
                        project.files[storage] = file
                except (PipelineError, OSError, ValueError) as error:
                    report["errors"].append({"path": str(value), "code": getattr(error, "code", "MEDIA_INPUT_UNAVAILABLE"),
                                             "message": str(error)})
            if not project.files:
                code = report["errors"][0]["code"] if len(report["errors"]) == 1 else "NO_READABLE_MEDIA"
                raise PipelineError(code, "没有成功读取的媒体文件", 400, report)
            project.files = dict(sorted(project.files.items(), key=lambda pair: _natural(pair[0])))
            model = to_wire(normalize_project(project))
            report["read_files"] = len(project.files)
            report["total_duration_ms"] = sum(f.media_metadata.get("duration_ms", 0) for f in project.files.values())
            (directory / "preview").mkdir()
            timestamp = _now()
            document = {"workspace_id": workspace_id, "kind": kind, "model": model,
                        "status": "partial" if report["errors"] else "success", "report": report,
                        "created_at": timestamp, "updated_at": timestamp, "previews": {},
                        "sources": {f["file_id"]: {"path": f["source_ref"]["path"], "sha256": f["source_ref"]["sha256"],
                                    "storage_path": name, "stamp": _stamp(Path(f["source_ref"]["path"]))}
                                    for name, f in model["files"].items()}}
            with self.lock:
                self._commit(directory, document)
                return self._response(directory, document)
        except Exception:
            # Only remove the newly allocated directory whose parent was checked.
            if directory.exists() and directory.resolve().parent == self.root and directory.name == workspace_id:
                shutil.rmtree(directory)
            raise

    def load(self, workspace_id):
        with self.lock:
            directory, document = self._read(workspace_id)
            return self._response(directory, document)

    def save_model(self, workspace_id, model, *, preview_files=None, status=None, report=None):
        clean = to_wire(parse_model(model))
        with self.lock:
            directory, document = self._read(workspace_id)
            if (clean["project_id"] != document["model"]["project_id"]
                    or clean["project_type"] != document["model"]["project_type"]):
                raise PipelineError("MEDIA_MODEL_MISMATCH", "中间模型不属于此媒体工作区", 409)
            if document["kind"] == "image":
                if _image_mode(clean) not in ("ocr", "generation"):
                    raise PipelineError("MEDIA_INVALID_MODE", "图片翻译模式无效", 422)
                if not isinstance(clean.get("extra", {}).get("image_generation_options", {}), dict):
                    raise PipelineError("MEDIA_INVALID_MODE", "生图选项必须是对象", 422)
            sources = document["sources"]
            if {f["file_id"] for f in clean["files"].values()} != set(sources):
                raise PipelineError("MEDIA_MODEL_MISMATCH", "不能增加或替换工作区源文件，请重新导入", 409)
            for name, file in clean["files"].items():
                registered = sources[file["file_id"]]
                if document["kind"] == "image" and not isinstance(file.get("extra", {}).get("image_generation", {}), dict):
                    raise PipelineError("MEDIA_INVALID_PREVIEW", "生图状态必须是对象", 422)
                if (file["media_type"] != document["kind"] or name != registered["storage_path"]
                        or file["source_ref"]["path"] != registered["path"]
                        or file["source_ref"]["sha256"] != registered["sha256"]):
                    raise PipelineError("MEDIA_MODEL_MISMATCH", "工作区源文件引用不能被修改", 409)
            if preview_files is not None:
                if not isinstance(preview_files, list):
                    raise PipelineError("MEDIA_INVALID_PREVIEW", "预览产物必须是列表", 422)
                by_id = {f["file_id"]: f for f in clean["files"].values()}
                preview_root = _preview_root(directory)
                for exported in preview_files:
                    file = by_id.get(exported.get("file_id")) if isinstance(exported, dict) else None
                    try:
                        preview = Path(exported["path"]).resolve(strict=True)
                        if (document["kind"] != "image" or file is None or not preview.is_file()
                                or not preview.is_relative_to(preview_root) or preview.suffix.lower() not in IMAGE_EXTENSIONS):
                            raise ValueError("not a workspace preview")
                        render = file.get("extra", {}).get("image_pipeline", {}).get("render", {})
                        artifact = render.get("artifacts", {}).get("image", {})
                        digest = file_sha256(preview)
                        if str(preview) != str(Path(artifact.get("path", "")).resolve()) or digest != artifact.get("sha256"):
                            raise ValueError("not the rendered artifact")
                    except (OSError, TypeError, KeyError, ValueError) as error:
                        raise PipelineError("MEDIA_INVALID_PREVIEW", "预览图片必须是本工作区已渲染的产物", 422) from error
                    document["previews"][file["file_id"]] = {"path": str(preview), "sha256": digest,
                        "stamp": _stamp(preview), "content_identity": _content_identity(file)}
            # Canonical generation artifacts already live in a controlled cache.
            # Register each completed page during checkpoints, independent of the
            # OCR renderer and without copying or re-generating the image.
            if document["kind"] == "image":
                from Backend.application.image_generation_service import generation_artifact_current
                registrations = document.setdefault("generation_previews", {})
                for file in clean["files"].values():
                    if not generation_artifact_current(file):
                        continue
                    artifact = file["extra"]["image_generation"]["artifact"]
                    try:
                        image = Path(artifact["path"]).resolve(strict=True)
                        if not image.is_relative_to(_generation_root(clean, file)) or image.suffix.lower() not in IMAGE_EXTENSIONS:
                            raise PipelineError("MEDIA_INVALID_PREVIEW", "生成预览必须是本项目缓存内的产物", 422)
                        identity = _generation_identity(file)
                        stamp = _stamp(image)
                        previous = registrations.get(file["file_id"], {})
                        if previous.get("content_identity") != identity or previous.get("stamp") != stamp:
                            digest = file_sha256(image)
                            if digest != artifact["sha256"]:
                                registrations.pop(file["file_id"], None)
                                continue
                            registrations[file["file_id"]] = {"path": str(image), "sha256": digest,
                                "stamp": stamp, "content_identity": identity}
                    except PipelineError:
                        raise
                    except (OSError, ValueError, KeyError, TypeError):
                        registrations.pop(file["file_id"], None)
            document["model"] = clean
            document["updated_at"] = _now()
            if status is not None:
                if status not in ("success", "partial", "failed", "cancelled"):
                    raise PipelineError("MEDIA_INVALID_STATUS", "媒体处理状态无效", 422)
                document["status"] = status
            if report is not None:
                if not isinstance(report, dict):
                    raise PipelineError("MEDIA_INVALID_REPORT", "媒体处理报告必须是对象", 422)
                document["report"] = to_wire(report)
            self._commit(directory, document)
            return self._response(directory, document)

    def asset(self, workspace_id, file_id, variant="source"):
        with self.lock:
            directory, document = self._read(workspace_id)
            registered = document["sources"].get(file_id)
            if not registered:
                raise PipelineError("MEDIA_ASSET_NOT_FOUND", "媒体文件不存在", 404)
            if variant == "translated":
                file = next((f for f in document["model"]["files"].values() if f["file_id"] == file_id), None)
                registered = _selected_preview(document, file)
                if not registered:
                    raise PipelineError("MEDIA_PREVIEW_NOT_READY", "译图尚未生成或内容已更新，请重新生成预览", 404)
            elif variant != "source":
                raise PipelineError("MEDIA_ASSET_NOT_FOUND", "媒体预览类型不存在", 404)
            try:
                saved = Path(registered["path"])
                path = saved.resolve(strict=True)
                if path != saved or not path.is_file() or _stamp(path) != registered["stamp"]:
                    raise ValueError("changed registered asset")
                if variant == "translated":
                    allowed = (_generation_root(document["model"], file) if _image_mode(document["model"]) == "generation"
                               else _preview_root(directory))
                    if not path.is_relative_to(allowed):
                        raise ValueError("preview escaped workspace")
            except (OSError, ValueError) as error:
                raise PipelineError("MEDIA_SOURCE_CHANGED", "媒体文件已移动或改变，请重新导入或生成预览", 409) from error
            return path

    def history(self, kind=None, limit=20):
        if kind is not None and kind not in ("image", "audio"):
            raise PipelineError("MEDIA_INVALID_KIND", "媒体类型无效", 422)
        with self.lock:
            results = []
            if not self.root.exists():
                return results
            for directory in self.root.iterdir():
                if not directory.is_dir() or not _ID.fullmatch(directory.name):
                    continue
                try:
                    _, document = self._read(directory.name)
                    if kind is None or document["kind"] == kind:
                        results.append({"workspace_id": document["workspace_id"], "kind": document["kind"],
                            "project_name": document["model"]["project_name"], "file_count": len(document["model"]["files"]),
                            "updated_at": document["updated_at"], "status": document.get("status", "success")})
                except (PipelineError, KeyError, TypeError):
                    continue
            return sorted(results, key=lambda entry: entry["updated_at"], reverse=True)[:limit]


def get_media_store(runtime):
    if getattr(runtime, "media_workspaces", None) is None:
        runtime.media_workspaces = MediaWorkspaceStore()
    return runtime.media_workspaces
