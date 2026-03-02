# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_all
import os
import sys

# 获取当前项目的绝对路径
project_root = os.path.abspath(os.getcwd())

datas = [
    ('Resource', 'Resource'),          
    ('ModuleFolders', 'ModuleFolders'), 
    ('PluginScripts', 'PluginScripts'), 
]
binaries = []
hiddenimports = ['rich._unicode_data', 'tiktoken_ext.openai_public', 'mediapipe', 'babeldoc']

# 自动收集 rich 的所有依赖 
hiddenimports += collect_submodules('rich')
tmp_ret = collect_all('rich')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    ['AiNiee.py'],
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
    icon=['Resource/logo.icns']
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
    icon='Resource/logo.icns', 
    bundle_identifier='com.ainiee.app', 
)
