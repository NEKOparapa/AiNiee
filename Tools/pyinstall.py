import os
import sys
sys.setrecursionlimit(5000)
import PyInstaller.__main__

cmd = [
    "./AiNiee.py",
    "--icon=./Resource/Logo/Avatar.png",  # FILE.ico: apply the icon to a Windows executable.
    "--clean",  # Clean PyInstaller cache and remove temporary files before building.
    #"--onefile",  # Create a one-file bundled executable.
    "--noconfirm",  # Replace output directory (default: SPECPATH/dist/SPECNAME) without asking for confirmation
    "--add-data=Resource;Resource",  # Bundle Resource static files (prompts, presets, icons, etc.)
    "--hidden-import=babeldoc",
    "--hidden-import=sklearn",
    "--collect-all=babeldoc",
    # chardet 7.x loads pipeline/__mypyc modules dynamically; collect the whole
    # package so the packaged EXE does not crash on startup.
    "--collect-all=chardet",
    "--collect-all=sklearn",
    "--collect-all=rich",
    "--collect-all=bitstring",
    "--collect-all=darkdetect",
    "--collect-all=opencc",
    # FileReader/FileOutputer use importlib-based lazy loading; collect their
    # submodules so packaged builds can load formats at runtime.
    "--collect-submodules=ModuleFolders.Domain.FileReader",
    "--collect-submodules=ModuleFolders.Domain.FileOutputer",
    "--distpath=./dist_pdf",  # 指定输出目录为 dist_pdf
]

# 需要排除的软件包
# 由mediapipe等导入，但主逻辑不需要，会极大地增加包体积
MODULES_TO_EXCLUDE = [
    "jaxlib",
    "torch",
    "torchvision",
    "tensorboard",
    "triton",
    "notebook",
]

# 添加显式排除参数
for module_name in MODULES_TO_EXCLUDE:
    cmd.append(f"--exclude-module={module_name}")
    print(f"[INFO] Explicitly excluding module: {module_name}")

def _hidden_imports_from(path):
    with open(path, "r", encoding="utf-8") as reader:
        for raw in reader:
            if "#" in raw:
                continue
            line = raw.split(";")[0].strip()
            if line:
                yield line


if os.path.exists("./requirements.txt"):
    for pkg in _hidden_imports_from("./requirements.txt"):
        cmd.append("--hidden-import=" + pkg)
    for pkg in _hidden_imports_from("./requirements_no_deps.txt"):
        cmd.append("--hidden-import=" + pkg)

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    PyInstaller.__main__.run(cmd)
