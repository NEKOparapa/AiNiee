import os
import time
import shutil
import zipfile
import argparse

# 判断文件是否被锁定
def is_file_locked(filepath) -> bool:
    try:
        with open(filepath, "r+b"):
            pass
        return False
    except IOError:
        return True

def main(src: str, dst: str) -> None:
    error = None

    print("")
    for i in range(60):
        if not is_file_locked("AiNiee.exe"):
            break
        else:
            print(f"准备中 {"…" * (i + 1)}")
            print(f"Preparing {"…" * (i + 1)}")
            print("")
            time.sleep(1)

    try:
        # 解压文件
        with zipfile.ZipFile(src) as zip_file:
            zip_file.extractall(dst)

        # 移动文件
        extracted_folder = f"{dst}/AiNiee/"
        shutil.copytree(extracted_folder, dst, dirs_exist_ok=True)
        shutil.rmtree(extracted_folder, ignore_errors = True)
    except Exception as e:
        error = e

    # 删除源文件
    try:
        os.remove(src)
    except Exception:
        pass

    # 打印结果
    if error is None:
        print("文件更新成功 …")
        print("File Update Success …")
        print("")
    else:
        print(f"文件更新失败 … {error}")
        print(f"File Update Failure … {error}")
        print("")


    print("10 秒后自动关闭本窗口 …")
    print("This window will automatically close in 10 seconds …")
    time.sleep(10)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "将文件从源文件更新到目标目录。")
    parser.add_argument("src", type = str, help = "源文件路径")
    parser.add_argument("dst", type = str, help = "目标目录路径")
    args = parser.parse_args()

    main(args.src, args.dst)