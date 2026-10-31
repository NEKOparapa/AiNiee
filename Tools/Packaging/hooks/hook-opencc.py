"""Preserve OpenCC's dictionary data and Windows wheel DLL directory."""
from PyInstaller.utils.hooks import collect_data_files, collect_delvewheel_libs_directory

datas = collect_data_files("opencc")
datas, binaries = collect_delvewheel_libs_directory("opencc", datas=datas)
