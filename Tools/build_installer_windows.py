"""调用 Inno Setup Compiler 打包 AiNiee Windows 安装程序。

前置条件：
  1. dist\\AiNiee\\ 已由 Tools/pyinstall.py 生成
  2. Inno Setup 6 已安装（CI: choco install innosetup -y）
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ISS_SCRIPT = REPO_ROOT / "Tools" / "Installer" / "ainiee.iss"
DIST_ROOT = REPO_ROOT / "dist" / "AiNiee"
VERSION_FILE = REPO_ROOT / "Resource" / "Version" / "version.json"

ISCC_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
)


def _resolve_iscc() -> Path:
    found = shutil.which("ISCC.exe") or shutil.which("ISCC")
    if found:
        return Path(found)
    for candidate in ISCC_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "ISCC.exe 未找到。请安装 Inno Setup 6 或执行: choco install innosetup -y"
    )


def _read_version() -> str:
    if not VERSION_FILE.exists():
        return "0.0.0"
    raw = json.loads(VERSION_FILE.read_text(encoding="utf-8")).get("version", "0.0.0")
    for token in raw.split():
        if any(c.isdigit() for c in token):
            return token
    return "0.0.0"


def main() -> int:
    if not DIST_ROOT.exists():
        raise SystemExit(
            f"dist 目录不存在: {DIST_ROOT}\n请先运行 python Tools/pyinstall.py"
        )

    iscc = _resolve_iscc()
    version = _read_version()
    print(f"[installer] ISCC: {iscc}")
    print(f"[installer] Version: {version}")
    print(f"[installer] Script: {ISS_SCRIPT}")

    cmd = [str(iscc), f"/DMyAppVersion={version}", str(ISS_SCRIPT)]
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())
