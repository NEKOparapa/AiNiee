# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_all
import os
import sys

# [关键修复] 使用 PyInstaller 内置的 SPECPATH 向上回退两级，精准锁定根目录
project_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

datas = [
    # [关键修复] 将所有数据源的来源路径绑定到绝对根路径
    (os.path.join(project_root, 'Resource'), 'Resource'),          
    (os.path.join(project_root, 'ModuleFolders'), 'ModuleFolders'), 
    (os.path.join(project_root, 'PluginScripts'), 'PluginScripts'), 
]
binaries = []
hiddenimports = ['rich._unicode_data', 'tiktoken_ext.openai_public', 'mediapipe', 'babeldoc'] # 

# 自动收集 rich 的所有依赖 
hiddenimports += collect_submodules('rich') # 
tmp_ret = collect_all('rich') # 
datas += tmp_ret[0] # 
binaries += tmp_ret[1] # 
hiddenimports += tmp_ret[2] # 

#自动收集 chardet 的所有依赖
# ---------------------------------------------------------
hiddenimports += collect_submodules('chardet')
tmp_ret_chardet = collect_all('chardet')
datas += tmp_ret_chardet[0]
binaries += tmp_ret_chardet[1]
hiddenimports += tmp_ret_chardet[2]
# ---------------------------------------------------------

a = Analysis(
    # [关键修复] 入口文件绑定到绝对根路径
    [os.path.join(project_root, 'AiNiee.py')],
    pathex=[project_root], 
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AiNiee',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=True, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # [关键修复] EXE 的图标路径绑定到绝对根路径
    icon=[os.path.join(project_root, 'Resource/Logo/logo.icns')]
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='AiNiee',
)

app = BUNDLE(
    coll, 
    name='AiNiee.app',
    # [关键修复] BUNDLE 的图标路径绑定到绝对根路径
    icon=os.path.join(project_root, 'Resource/Logo/logo.icns'), 
    bundle_identifier='com.ainiee.app', 
)