"""Build the independent Windows desktop client."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pyinstaller_command():
    return [
        "./AiNiee.py", "--name=AiNiee", "--windowed", "--clean", "--noconfirm",
        "--icon=./Frontend/resources/icons/Avatar.png",
        f"--add-data=Frontend/resources{os.pathsep}Frontend/resources",
        "--collect-all=qfluentwidgets", "--collect-all=darkdetect",
        "--collect-all=rich", "--collect-all=openpyxl",
        "--hidden-import=websockets.sync.client",
        "--exclude-module=Backend",
    ]


def main():
    import PyInstaller.__main__
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    PyInstaller.__main__.run(pyinstaller_command())


if __name__ == "__main__":
    main()
