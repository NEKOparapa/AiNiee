import os
import PyInstaller.__main__

cmd = [
    "./AiNiee.py",
    "--icon=./Resource/Avatar.png", # FILE.ico: apply the icon to a Windows executable.
    "--clean", # Clean PyInstaller cache and remove temporary files before building.
    "--onefile", # Create a one-file bundled executable.
    "--noconfirm", # Replace output directory (default: SPECPATH/dist/SPECNAME) without asking for confirmation
]

if os.path.exists("./requirements.txt"):
    with open("./requirements.txt", "r", encoding = "utf-8") as reader:
        for line in reader:
            if "#" not in line:
                cmd.append("--hidden-import=" + line.strip())

    PyInstaller.__main__.run(cmd)