import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "AiNiee_MacOS"
BUNDLE_ID = "com.beautifulrem.AiNieeMacOS"


def build_icns() -> Path:
    source_png = ROOT / "Resource" / "Logo" / "Avatar.png"
    output_icns = ROOT / "build" / "macos" / "AiNiee.icns"
    if output_icns.exists():
        return output_icns

    if sys.platform != "darwin" or not shutil.which("sips") or not shutil.which("iconutil"):
        return source_png

    iconset = ROOT / "build" / "macos" / "AiNiee.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    icon_specs = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    for size, filename in icon_specs:
        subprocess.run(
            ["sips", "-z", str(size), str(size), str(source_png), "--out", str(iconset / filename)],
            check=True,
        )
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output_icns)], check=True)
    return output_icns


def add_hidden_imports_from_requirements(cmd: list[str], path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        package = raw_line.strip()
        if not package or package.startswith("#") or package.startswith("-r "):
            continue
        if any(token in package for token in ("[", "=", "<", ">", "~", ";")):
            continue
        cmd.append("--hidden-import=" + package)


def patch_info_plist() -> None:
    plist_path = ROOT / "dist" / f"{APP_NAME}.app" / "Contents" / "Info.plist"
    if not plist_path.exists():
        return

    with plist_path.open("rb") as reader:
        plist = plistlib.load(reader)
    plist.update(
        {
            "CFBundleDisplayName": "AiNiee MacOS",
            "CFBundleName": "AiNiee MacOS",
            "CFBundleIdentifier": BUNDLE_ID,
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
        }
    )
    with plist_path.open("wb") as writer:
        plistlib.dump(plist, writer)


def main() -> None:
    os.chdir(ROOT)
    icon_path = build_icns()
    cmd = [
        "./AiNiee.py",
        f"--name={APP_NAME}",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--target-arch=arm64",
        f"--osx-bundle-identifier={BUNDLE_ID}",
        f"--icon={icon_path}",
        "--add-data=Resource:Resource",
        "--add-data=StevExtraction:StevExtraction",
        "--hidden-import=babeldoc",
        "--hidden-import=sklearn",
        "--collect-all=babeldoc",
        "--collect-all=chardet",
        "--collect-all=sklearn",
        "--collect-all=rich",
        "--collect-all=bitstring",
        "--exclude-module=jaxlib",
        "--exclude-module=win32com",
        "--exclude-module=pythoncom",
    ]
    add_hidden_imports_from_requirements(cmd, ROOT / "requirements.txt")
    PyInstaller.__main__.run(cmd)
    patch_info_plist()


if __name__ == "__main__":
    main()
