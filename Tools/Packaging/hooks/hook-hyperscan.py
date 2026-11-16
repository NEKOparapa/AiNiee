from PyInstaller.utils.hooks import collect_delvewheel_libs_directory

# The Windows wheel loads its renamed runtime DLLs from the sibling .libs directory.
datas, binaries = collect_delvewheel_libs_directory("hyperscan")
