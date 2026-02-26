# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_all
import os
import sys

# 获取当前项目的绝对路径
project_root = os.path.abspath(os.getcwd())

datas = [
    ('Resource', 'Resource'),          # 包含图标、配置等资源
    ('ModuleFolders', 'ModuleFolders'), # 包含核心代码逻辑文件夹
    ('PluginScripts', 'PluginScripts'), # 包含插件脚本
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
    pathex=[project_root], # 关键：告诉程序去哪里找 ModuleFolders
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
    strip=False,
    upx=True,
    console=False, # 设为 False 运行不带黑窗口 [cite: 3]
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AiNiee',
)

app = BUNDLE(
    coll,
    name='AiNiee.app',
    icon=None,
    bundle_identifier=None,
)