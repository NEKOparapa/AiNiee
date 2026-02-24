@echo off
set "PYTHON_EXEC=python"
if exist "venv\Scripts\python.exe" set "PYTHON_EXEC=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXEC=.venv\Scripts\python.exe"

%PYTHON_EXEC% GlossaryTool/main.py
pause