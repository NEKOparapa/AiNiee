"""The distributable includes build inputs, never the builder's user data."""

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from Tools import pyinstall


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    for relative in pyinstall.REQUIRED_RESOURCES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixed bundled resource", encoding="utf-8")
    (root / "Resource/Version/version.json").write_text('{"version":"AiNiee 7.2.6"}', encoding="utf-8")
    (root / "Resource/config.json").write_text('{"api_key":"private-builder-key"}', encoding="utf-8")
    (root / "Resource/Updater").mkdir()
    (root / "Resource/Updater/updater.exe").write_bytes(b"old updater")
    (root / "frontend/dist/assets").mkdir(parents=True)
    (root / "frontend/dist/index.html").write_text('<script src="/assets/main.js"></script>', encoding="utf-8")
    (root / "frontend/dist/assets/main.js").write_text("window.fixedBundle = true", encoding="utf-8")
    (root / "frontend/package-lock.json").write_text("{}", encoding="utf-8")
    (root / "LICENSE").write_text("Test license", encoding="utf-8")
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "Resource", "frontend/package-lock.json", "LICENSE"], check=True, capture_output=True)
    subprocess.run([
        "git", "-C", str(root), "-c", "user.name=Packaging test", "-c", "user.email=packaging@example.invalid",
        "commit", "-m", "fixture",
    ], check=True, capture_output=True)
    return root


def test_module_import_has_no_build_or_process_side_effects(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Import must not run commands or load PyInstaller")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setitem(sys.modules, "PyInstaller", None)
    importlib.reload(pyinstall)


def test_payload_uses_tracked_allowlist_and_new_empty_config(checkout):
    private = checkout / "Resource/Prompt/private-note.txt"
    private.write_text("untracked-secret", encoding="utf-8")
    (checkout / "ProjectCache").mkdir()
    (checkout / "ProjectCache/private.json").write_text("private progress", encoding="utf-8")
    paths = pyinstall.create_build_paths(checkout)
    manifest = pyinstall.stage_payload(paths)
    names = {item["path"] for item in manifest}
    assert pyinstall.REQUIRED_RESOURCES <= names
    assert "Resource/Updater/updater.exe" not in names
    assert "Resource/Prompt/private-note.txt" not in names
    assert "ProjectCache/private.json" not in names
    assert "frontend/dist/assets/main.js" in names
    assert json.loads((paths.payload / "Resource/config.json").read_text()) == {}
    assert json.loads((checkout / "Resource/config.json").read_text())["api_key"] == "private-builder-key"
    assert all("private-builder-key" not in path.read_text(encoding="utf-8") for path in paths.payload.rglob("*") if path.is_file())
    for item in manifest:
        assert item["sha256"] == hashlib.sha256((paths.payload / item["path"]).read_bytes()).hexdigest()


def test_missing_git_or_required_resource_fails_instead_of_including_local_files(tmp_path, checkout):
    with pytest.raises(ValueError, match="Git checkout"):
        pyinstall.resource_manifest(tmp_path)
    (checkout / "Resource/Models/mediapipe/language_detector.tflite").unlink()
    with pytest.raises(ValueError, match="missing"):
        pyinstall.resource_manifest(checkout)


def test_each_build_owns_new_paths_and_does_not_overwrite_previous_files(checkout):
    first = pyinstall.create_build_paths(checkout)
    sentinel = first.output / "user.txt"
    sentinel.write_text("previous build must remain", encoding="utf-8")
    second = pyinstall.create_build_paths(checkout)
    assert first.work != second.work and first.output != second.output
    assert sentinel.read_text() == "previous build must remain"
    pyinstall.stage_payload(first)
    with pytest.raises(FileExistsError):
        pyinstall.stage_payload(first)


def test_path_boundaries_reject_escape_and_unexpected_frontend_files(checkout, tmp_path):
    external = tmp_path / "private.txt"
    external.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError, match="stay below"):
        pyinstall._source_file(checkout, external)
    with pytest.raises(ValueError, match="stay below"):
        pyinstall._inside(checkout, checkout / ".." / "outside")
    forged = pyinstall.BuildPaths(checkout, tmp_path / "outside", checkout / "dist/fresh")
    with pytest.raises(ValueError, match="stay below"):
        pyinstall.stage_payload(forged)
    (checkout / "frontend/dist/config.json").write_text('{"token":"secret"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected frontend"):
        pyinstall.frontend_manifest(checkout)


def test_tracked_links_are_rejected_even_when_they_target_inside_resource(checkout, monkeypatch):
    # Exercise this boundary without requiring Windows symlink privileges.
    tracked = checkout / "Resource/Logo/Avatar.png"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == tracked or original(path))
    with pytest.raises(ValueError, match="Linked"):
        pyinstall.resource_manifest(checkout)


def test_metadata_contains_versions_and_hashes_not_local_paths_or_credentials(checkout):
    paths = pyinstall.create_build_paths(checkout)
    metadata = pyinstall.build_metadata(checkout, pyinstall.stage_payload(paths), console=False)
    assert metadata["version"] == "7.2.6"
    assert metadata["platform"] == "windows-x64"
    assert metadata["source_dirty"] is False
    assert len(metadata["source_revision"]) == 40
    assert metadata["frontend_lock_sha256"] == hashlib.sha256(b"{}").hexdigest()
    encoded = json.dumps(metadata)
    assert "private-builder-key" not in encoded
    assert str(checkout) not in encoded and checkout.as_posix() not in encoded
    (checkout / "Resource/Version/version.json").write_text('{"version":"../../unsafe"}', encoding="utf-8")
    with pytest.raises(ValueError, match="numeric dotted"):
        pyinstall.package_version(checkout)


def test_command_collects_lazy_modules_and_staged_files_without_overwrite_flag(checkout):
    paths = pyinstall.create_build_paths(checkout)
    command = pyinstall.pyinstaller_command(paths)
    assert "--windowed" in command and "--onedir" in command
    assert "--noconfirm" not in command
    assert "--noupx" in command
    assert "--collect-submodules=ModuleFolders.Domain.FileReader" in command
    assert "--collect-submodules=ModuleFolders.Domain.FileOutputer" in command
    assert "--collect-submodules=uvicorn" in command
    assert "--hidden-import=tiktoken_ext.openai_public" in command
    assert all(str(paths.payload) in arg for arg in command if arg.startswith("--add-data="))
    diagnostic = pyinstall.pyinstaller_command(paths, console=True)
    assert "--console" in diagnostic and "--windowed" not in diagnostic


def make_package(checkout):
    paths = pyinstall.create_build_paths(checkout)
    staged = pyinstall.stage_payload(paths)
    paths.package.mkdir()
    shutil.copytree(paths.payload, paths.package / "_internal")
    (paths.package / "AiNiee.exe").write_bytes(b"test executable placeholder")
    return paths, pyinstall.build_metadata(checkout, staged, console=False)


def test_zip_contains_portable_marker_license_instructions_and_no_user_data(checkout):
    paths, metadata = make_package(checkout)
    archive, digest = pyinstall.finish_package(paths, metadata)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.read("AiNiee/LICENSE") == b"Test license"
        assert bundle.read("AiNiee/portable.txt")
        assert "退出应用" in bundle.read("AiNiee/README.txt").decode("utf-8")
        assert json.loads(bundle.read("AiNiee/_internal/Resource/config.json")) == {}
        assert all(name.startswith("AiNiee/") and ".." not in Path(name).parts for name in bundle.namelist())
        assert not any("Updater/" in name or "ProjectCache/" in name for name in bundle.namelist())
    assert digest == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert archive.with_suffix(".zip.sha256").read_text() == f"{digest}  {archive.name}\n"
    with pytest.raises(FileExistsError, match="overwrite"):
        pyinstall.finish_package(paths, metadata)


def test_zip_refuses_bundles_already_used_with_user_data(checkout):
    paths, metadata = make_package(checkout)
    (paths.package / "Logs").mkdir()
    with pytest.raises(ValueError, match="possible user data"):
        pyinstall.finish_package(paths, metadata)
    assert not list(paths.output.glob("*.zip"))
