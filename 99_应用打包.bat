@echo off

@REM 设置工作目录
set ROOT=%~dp0

@REM 清理环境
powershell -Command "Remove-Item -Path 'dist' -Recurse -Force -ErrorAction SilentlyContinue"
powershell -Command "Remove-Item -Path 'build' -Recurse -Force -ErrorAction SilentlyContinue"
powershell -Command "Remove-Item -Path 'AiNiee.spec' -Recurse -Force -ErrorAction SilentlyContinue"

@REM 更新环境
python -m pip install --upgrade pip
python -m pip install --upgrade setuptools
python -m pip install -r requirements.txt
python -m pip cache purge

@REM 打包
python .\Tools\pyinstall.py

@REM 复制资源文件
powershell -Command "Copy-Item -Path 'Resource' -Destination 'dist\Resource' -Recurse -Force"
powershell -Command "Copy-Item -Path 'StevExtraction' -Destination 'dist\StevExtraction' -Recurse -Force"
powershell -Command "Copy-Item -Path 'Plugin_Scripts' -Destination 'dist\Plugin_Scripts' -Recurse -Force"

pause