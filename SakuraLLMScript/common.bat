@echo off
@chcp 65001 > nul

setlocal enableextensions enabledelayedexpansion

if /i "%label%"=="" (
	echo 不可以直接调用这个脚本
	goto quit
)

@title %label%

set n=0
for /f "delims=" %%i in ('where .:*.gguf') do (
	set models[!n!].path=%%i
	set models[!n!].name=%%~ni
	set /a n+=1
)

if %n% equ 0 goto no-model
if %n% equ 1 goto one-model
goto many-model

:no-model
echo 没有检测到gguf模型文件,请确定将模型文件放到了当前文件夹
goto quit

:one-model
set model.name=%models[0].name%
set model.path=%models[0].path%
goto launch

:many-model
set /a end=%n%-1

echo 请输入数字来选择要使用的模型,默认选择0
for /l %%i in (0,1,%end%) do (
	echo %%i. !models[%%i].name!
)
echo.
:choice-model
set choice=
set /p choice= 请选择:
if /i "%choice%"=="" set choice=0
for /l %%i in (0,1,%end%) do (
	if /i "%choice%"=="%%i" (
		set model.name=!models[%%i].name!
		set model.path=!models[%%i].path!
		goto launch
	)
)
echo 选择⽆效,请重新输⼊
goto choice-model

:launch
@title %label%-%model.name%
echo.
echo 模型名称：%model.name%
echo 模型路径：%model.path%
echo.
echo 准备启动Sakura服务器...

REM 检查 llama-server.exe 是否存在
if exist ".\llama\llama-server.exe" (
	@echo on
    .\llama\llama-server.exe -m .\%model.name%.gguf -fa --no-mmap -cb -np %np% -c %ctx% -ngl %ngl% -a %model.name% --host 127.0.0.1
	@echo off
) 

REM 检查 server.exe 是否存在
if exist ".\llama\server.exe" (
	@echo on
    .\llama\server.exe -m .\%model.name%.gguf -fa --no-mmap -cb -np %np% -c %ctx% -ngl %ngl% -a %model.name% --host 127.0.0.1
	@echo off
) else (
	goto quit
)

:quit
echo.
echo 按任意键退出
pause > nul
exit