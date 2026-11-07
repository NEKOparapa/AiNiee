"""Build the updater from source so releases never ship an obsolete binary."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build_updater():
    target = ROOT / "build" / "rust-updater"
    subprocess.run([
        "cargo", "build", "--release", "--locked", "--manifest-path",
        str(ROOT / "Tools" / "rust_updater" / "Cargo.toml"), "--target-dir", str(target),
    ], check=True, cwd=ROOT)
    destination = ROOT / "Frontend" / "resources" / "updater" / "updater.exe"
    shutil.copy2(target / "release" / "updater.exe", destination)
    return destination


if __name__ == "__main__":
    build_updater()
