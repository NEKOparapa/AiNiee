@ECHO OFF
@CHCP 65001
rem 设置命令不显示和设置编码格式为U-8

SET BASE_DIR=%cd%

rem 获取当前目录路径为BASE_DIR

ECHO 正在初始化 ........
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 请先【安装python】 !!!!
ECHO !! 如果您在安装的过程出现错误，可以重新启动此脚本    !!!!
ECHO !! 如果您遇到问题，可以在交流群 【821624890】 询问  !!!!
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

ECHO 尝试安装依赖库中............




python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，则pip库已升级完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!



pip install openai -i https://pypi.tuna.tsinghua.edu.cn/simple
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，OpenAI库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


pip install numpy -i https://pypi.tuna.tsinghua.edu.cn/simple
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，numpy库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


pip install openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，openpyxl库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


pip3 install PyQt5 -i https://pypi.tuna.tsinghua.edu.cn/simple
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，PyQt5库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!



pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，PyQt-Fluent-Widgets库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


pip install opencc -i https://pypi.org/simple/
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，opencc库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

pip install tiktoken -i https://pypi.org/simple/
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，tiktoken库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO !!
ECHO !! 如果没有报错，全部依赖库已安装完成
ECHO !!
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


PAUSE
rem 设置命令行窗口停止，方便以后DEBUG

