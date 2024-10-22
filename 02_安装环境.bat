@echo off

	set ROOT=%~dp0
	pip install -r %ROOT:~0,-1%\requirements.txt

pause