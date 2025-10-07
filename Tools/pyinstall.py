import os
import PyInstaller.__main__

cmd = [
    "./AiNiee.py",
    "--icon=./Resource/Logo/Avatar.png",  # FILE.ico: apply the icon to a Windows executable.
    "--clean",  # Clean PyInstaller cache and remove temporary files before building.
    #"--onefile",  # Create a one-file bundled executable.
    "--noconfirm",  # Replace output directory (default: SPECPATH/dist/SPECNAME) without asking for confirmation
    "--hidden-import=babeldoc",
    "--hidden-import=sklearn",
    "--collect-all=babeldoc",
    "--collect-all=sklearn",
    # "--distpath=./dist/AiNiee" #指定输出目录
]

# 需要排除的软件包
# 由mediapipe导入，但不需要这些任务，会增加很多大小
MODULES_TO_EXCLUDE = [
    "jaxlib",
]

# 添加显式排除参数
for module_name in MODULES_TO_EXCLUDE:
    cmd.append(f"--exclude-module={module_name}")
    print(f"[INFO] Explicitly excluding module: {module_name}")

if os.path.exists("./requirements.txt"):
    with open("./requirements.txt", "r", encoding="utf-8") as reader:
        for line in reader:
            if "#" not in line:
                cmd.append("--hidden-import=" + line.strip())

    with open("./requirements_no_deps.txt", "r", encoding="utf-8") as reader:
        for line in reader:
            if "#" not in line:
                cmd.append("--hidden-import=" + line.strip())

    PyInstaller.__main__.run(cmd)
