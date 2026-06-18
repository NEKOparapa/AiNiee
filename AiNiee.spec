# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all
import sys
import os
sys.path.insert(0, os.path.abspath(SPECPATH))

datas = [('Resource', 'Resource')]
binaries = []
hiddenimports = ['babeldoc', 'sklearn', 'pyinstaller', 'openai', 'boto3', 'anthropic', 'google-genai', 'tiktoken', 'numpy', 'openpyxl', 'PyQt5', 'PyQt-Fluent-Widgets[full]~=1.10.0', 'pyobjc-framework-Cocoa', 'opencc', 'beautifulsoup4', 'lxml', 'chardet', 'PyYAML', 'requests', 'httpx[http2]', 'curl_cffi', 'python-pptx', 'polib', 'pandas', 'rich', 'tqdm', 'jaconv', 'python-rapidjson', 'protobuf==4.25.7', 'language-data', 'langcodes', 'msgspec', 'absl-py', 'attrs>=19.1.0', 'flatbuffers>=2.0', 'matplotlib', 'sounddevice>=0.4.4', 'bitstring>=4.3.0', 'configargparse>=1.7', 'httpx[socks]>=0.27.0', 'huggingface-hub>=0.27.0', 'numpy>=2.0.2', 'onnx==1.16.1', 'onnxruntime==1.20.1', 'openai>=1.59.3', 'orjson>=3.10.14', 'charset-normalizer>=2.0.0', 'cryptography>=36.0.0', 'peewee>=3.17.8', 'psutil>=7.0.0', 'pymupdf==1.26.7', 'rich>=13.9.4', 'toml>=0.10.2', 'tqdm>=4.67.1', 'xsdata[cli,lxml,soap]>=24.12', 'msgpack>=1.1.0', 'pydantic>=2.10.6', 'tenacity>=9.0.0', 'freetype-py>=2.5.1', 'tiktoken>=0.9.0', 'levenshtein>=0.27.1', 'rapidocr-onnxruntime>=1.4.4', 'pyzstd', 'rtree', 'uharfbuzz>=0.50.2', 'scikit-learn>=1.7.1', 'mediapipe==0.10.14', 'BabelDOC']
hiddenimports += collect_submodules('ModuleFolders.Domain.FileReader')
hiddenimports += collect_submodules('ModuleFolders.Domain.FileOutputer')
tmp_ret = collect_all('babeldoc')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('chardet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sklearn')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('rich')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('bitstring')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('darkdetect')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('opencc')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['AiNiee.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['jaxlib', 'torch', 'torchvision', 'tensorboard', 'triton', 'notebook'],
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Resource\\Logo\\Avatar.png'],
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
