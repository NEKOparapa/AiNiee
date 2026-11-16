"""Publish a completed export using the destination's Windows permissions."""
import ctypes
from ctypes import wintypes
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


_replace_file = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
_replace_file.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                          wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID)
_replace_file.restype = wintypes.BOOL


def _replace_preserving_acl(destination, replacement, backup=None):
    # Zero flags: if Windows cannot preserve the DACL, report the error.
    if not _replace_file(str(destination), str(replacement), backup, 0, None, None):
        raise ctypes.WinError(ctypes.get_last_error())


def _replace_existing(destination, replacement):
    # Supplying a backup keeps the old content recoverable even if ReplaceFileW
    # fails between moving the original and installing the replacement.
    backup = destination.with_name(f".ainiee-backup-{uuid4().hex}.tmp")
    try:
        _replace_preserving_acl(destination, replacement, str(backup))
    except OSError as error:
        if error.winerror == 1177:  # ERROR_UNABLE_TO_MOVE_REPLACEMENT_2
            try:
                backup.rename(destination)
            except OSError as restore_error:
                raise OSError(f"无法还原输出文件，原文件保存在 {backup}") from restore_error
        raise
    backup.unlink()


def publish_file(staged: Path, destination: Path, overwrite: bool):
    # ReplaceFileW resolves inherited entries against the replacement's parent.
    # Move the completed file out of the private writer directory first. Windows
    # rename keeps its private ACL and refuses to clobber a name collision.
    sibling = destination.with_name(f".ainiee-write-{uuid4().hex}.tmp")
    staged.rename(sibling)
    try:
        if overwrite:
            try:
                _replace_existing(destination, sibling)
                return
            except FileNotFoundError:
                pass  # First export with overwrite enabled.

        # A new, empty sibling has exactly the permissions a new output should
        # receive, including file-only inheritance and creator-specific entries.
        with NamedTemporaryFile(dir=destination.parent, prefix=".ainiee-write-",
                                suffix=".tmp", delete=False) as empty:
            inheriting = Path(empty.name)
        try:
            _replace_preserving_acl(inheriting, sibling)
            try:
                inheriting.rename(destination)
            except FileExistsError:
                if not overwrite:
                    raise
                # Another export created the destination while we were writing.
                _replace_existing(destination, inheriting)
        finally:
            inheriting.unlink(missing_ok=True)
    finally:
        sibling.unlink(missing_ok=True)
