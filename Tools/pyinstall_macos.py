import argparse
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "AiNiee"
BUNDLE_ID = "com.nekoparapa.AiNiee"
VALID_TARGET_ARCHES = {"arm64", "x86_64"}


def target_arch(explicit_arch: str | None = None) -> str:
    # CI 和本地命令可能使用不同架构名，统一成 PyInstaller 支持的值。
    arch = explicit_arch or os.environ.get("AINIEE_MACOS_ARCH") or platform.machine()
    normalized_arch = arch.strip().lower()
    aliases = {
        "aarch64": "arm64",
        "amd64": "x86_64",
        "x64": "x86_64",
    }
    normalized_arch = aliases.get(normalized_arch, normalized_arch)
    if normalized_arch not in VALID_TARGET_ARCHES:
        supported = ", ".join(sorted(VALID_TARGET_ARCHES))
        raise ValueError(f"Unsupported macOS target architecture: {arch}. Supported: {supported}")
    return normalized_arch


def app_version() -> str:
    version_file = ROOT / "Frontend" / "resources" / "version" / "version.json"
    if not version_file.exists():
        return "0.0.0"

    match = re.search(r"\d+(?:\.\d+){1,3}", version_file.read_text(encoding="utf-8"))
    return match.group(0) if match else "0.0.0"


def build_icns() -> Path:
    source_png = ROOT / "Frontend" / "resources" / "icons" / "Avatar.png"
    output_icns = ROOT / "build" / "macos" / "AiNiee.icns"
    if output_icns.exists():
        return output_icns

    if sys.platform != "darwin" or not shutil.which("sips") or not shutil.which("iconutil"):
        # 非 macOS 环境无法生成 icns，保留 png 便于测试命令构造。
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
            [
                "sips",
                "-s",
                "format",
                "png",
                "-z",
                str(size),
                str(size),
                str(source_png),
                "--out",
                str(iconset / filename),
            ],
            check=True,
        )
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output_icns)], check=True)
    return output_icns


def patch_info_plist() -> None:
    plist_path = ROOT / "dist" / f"{APP_NAME}.app" / "Contents" / "Info.plist"
    if not plist_path.exists():
        return

    with plist_path.open("rb") as reader:
        plist = plistlib.load(reader)
    plist.update(
        {
            "CFBundleDisplayName": "AiNiee",
            "CFBundleName": "AiNiee",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleShortVersionString": app_version(),
            "CFBundleVersion": app_version(),
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Copyright © AiNiee contributors. All rights reserved.",
        }
    )
    with plist_path.open("wb") as writer:
        plistlib.dump(plist, writer)

    # The service is a nested app for code-signing, but has no UI or Dock icon.
    # Patch its metadata before sign_app_bundle() signs both app bundles.
    backend_plist = plist_path.parent / "Helpers" / "AiNieeBackend.app" / "Contents" / "Info.plist"
    with backend_plist.open("rb") as reader:
        backend_info = plistlib.load(reader)
    backend_info["LSBackgroundOnly"] = True
    with backend_plist.open("wb") as writer:
        plistlib.dump(backend_info, writer)


def sign_app_bundle() -> None:
    app_path = ROOT / "dist" / f"{APP_NAME}.app"
    if sys.platform != "darwin" or not app_path.exists() or not shutil.which("codesign"):
        return

    # 没有证书时使用 ad-hoc 签名；有证书时启用 hardened runtime 以便公证。
    identity = os.environ.get("CODESIGN_IDENTITY") or os.environ.get("MACOS_CODESIGN_IDENTITY", "-")
    cmd = ["codesign", "--force", "--deep", "--sign", identity]
    entitlements = ROOT / "Tools" / "Packaging" / "macOS" / "entitlements.plist"
    if entitlements.exists():
        cmd.extend(["--entitlements", str(entitlements)])
    if identity != "-":
        cmd.extend(["--options", "runtime"])
    cmd.append(str(app_path))
    subprocess.run(cmd, check=True)


def pyinstaller_command(icon_path: Path, arch: str | None = None) -> list[str]:
    macos_arch = target_arch(arch)
    return [
        "./AiNiee.py",
        f"--name={APP_NAME}",
        "--windowed",
        "--clean",
        "--noconfirm",
        f"--target-arch={macos_arch}",
        f"--osx-bundle-identifier={BUNDLE_ID}",
        f"--icon={icon_path}",
        "--add-data=Frontend/resources:Frontend/resources",
        "--collect-all=qfluentwidgets",
        "--collect-all=darkdetect",
        "--collect-all=rich",
        "--collect-all=openpyxl",
        "--collect-all=objc",
        "--collect-all=Foundation",
        "--collect-all=AppKit",
        "--hidden-import=websockets.sync.client",
        "--exclude-module=Backend",
        "--exclude-module=win32com",
        "--exclude-module=pythoncom",
    ]


def main() -> None:
    import PyInstaller.__main__
    parser = argparse.ArgumentParser(description="Build the AiNiee macOS app bundle.")
    parser.add_argument(
        "--target-arch",
        choices=sorted(VALID_TARGET_ARCHES),
        default=None,
        help="PyInstaller target architecture. Defaults to AINIEE_MACOS_ARCH or arm64.",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    icon_path = build_icns()
    PyInstaller.__main__.run(pyinstaller_command(icon_path, args.target_arch))
    from Tools.pyinstall_backend import build_backend
    build_backend(ROOT / "dist" / f"{APP_NAME}.app" / "Contents" / "Helpers" / "AiNieeBackend.app", target_arch(args.target_arch))
    patch_info_plist()
    sign_app_bundle()


if __name__ == "__main__":
    main()
