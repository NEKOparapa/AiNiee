import zipfile
from pathlib import Path


def decompress_zip_to_path(zip_file_path: Path, decompress_path: Path):
    decompress_path.mkdir(exist_ok=True)
    # 解压docx文件到暂存文件夹中
    with zipfile.ZipFile(zip_file_path, 'r') as zipf:
        # 提取所有文件
        zipf.extractall(decompress_path)


def compress_to_zip_file(compress_path: Path, zip_file_path: Path):
    if compress_path.is_dir():
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 遍历文件夹中的所有文件和子文件夹
            for root, _, files in compress_path.walk():
                for file in files:
                    file_path = root / file
                    # 获取文件在压缩文件中的相对路径
                    relative_file_path = file_path.relative_to(compress_path)
                    # 将文件添加到压缩文件中
                    zipf.write(file_path, relative_file_path)
    else:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(compress_path)


def replace_in_zip_file(
    src_zip_file_path: Path, dst_zip_file_path: Path,
    content: dict[str, str],
):
    with (
        zipfile.ZipFile(src_zip_file_path, 'r') as zin,
        zipfile.ZipFile(dst_zip_file_path, 'w') as zout,
    ):
        # 遍历原始 ZIP 中的所有文件
        for item in zin.infolist():
            # 如果是目标文件，替换为新内容
            if item.filename in content:
                zout.writestr(item, content[item.filename])
            else:  # 否则直接复制
                zout.writestr(item, zin.read(item.filename))
