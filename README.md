# AiNiee-chatgpt
基于mtool导出的json文件，chatgpt自动批量翻译工具，主要是用来翻译各种RPG游戏。

教程视频：https://www.bilibili.com/video/BV12V4y1R7PG


### **———————————————————依赖环境要求——————————————**

1）pyhone环境：到官网https://www.python.org/downloads/windows/ 下载合适的版本安装，我编程时是3.10.7版本，所以也建议安装3.10.7，其他不是太老应该也没有问题

2）AI相关库和UI相关库：打开cmd，分别输入下面每行代码后回车。
```python
pip install openai                       
```
```python
pip install tiktoken
```
```python
pip3 install PyQt5
```
```python
pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
```

3）代理环境：自己得弄个好的代理环境，设置全局代理或者其他方式，不然连不上chatgpt，api接口会频繁报错或者一直没有回复。

4）mtool工具：https://afdian.net/a/AdventCirno  免费版本就可以,如果有条件也希望支持一下，此工具也有chatgpt翻译功能，更快更简单。

5）API_Key：新建一个,并且最好在使用期间不要和其他程序一起使用，不然容易达到请求次数限制

6）IDE软件：能运行python的IDE软件如vscode https://code.visualstudio.com/    pycharm等等 。



### **———————————————————工具使用说明——————————————**

#### **第一步：首先利用mtool软件打开你喜欢的rpg游戏，并将在翻译功能界面，选择导出需要被翻译的文本，将ManualTransFile.json文件导出，放到与程序同一个目录下。**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/1-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/1-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   打开mtool的翻译界面            |   导出游戏内文本文件            |


#### **第二步：填写配置信息。**


##### **1.配置示例**

<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/2-1.png" width="400" height="300"> 


##### **2.配置说明**


【  账号类型 】是你账号类型，免费用户基本只能并发两三个线程翻译任务，而付费用户可以并发几十个，大大缩减翻译时间。

【  API KEY  】填入你的api_key

【  Lines    】是每次请求翻译的文本行数。行数设置越大，AI酱容易回复内容格式错误，消耗额度月多，每次请求回复速度越慢，建议不要设置超过50。

【  Prompt   】是系统提示词，用于告诉chatgpt任务目标的命令语。建议不要修改，如果想改变命令词，记得后面一定要求保留原格式，不然AI酱乱回复就翻译不了了

【  文件位置  】是选择你需要翻译的原文文件，也是ManualTransFile.json文件

【  输出文件夹】是选择翻译好文件的存储文件夹


#### **第三步：配置好代理环境，然后【使用IDE运行AiNiee-chatgpt3.py程序】，点击【测试请求】按钮，测试当前网络环境**
<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/3-1.png" width="400" height="300"> 

#### **第四步：点击【开始翻译】按钮，看控制台输出日志或者进度条。之后等待翻译进度到百分百，自动生成翻译好的文件Tradata.json在输出文件夹中。**


##### **正在进行翻译**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-1-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-1-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   控制台输出的日志            |     UI界面显示情况            |


这个过程比较煎熬，通常我翻译1mb的json文件，就得花一个小时左右，免费玩家就是这样的，而付费玩家，使用多线程功能，可以很快翻译完成。

翻译完成后，一定要进行格式检查，用IDE软件打开Tradata.json看看，有没有标红的地方。特别是在类似游戏道具，技能名，UI文本地方容易出现错误。

未能成功翻译的文本会输出为Failure_to_translate.json文件，打开看看哪里还没有翻译。全英文可以不用理会，一般是程序的注释说明，如果有未能翻译的日文可以去手动翻译，然后在Tradata.json搜索并手动修改。


##### **已经完成翻译**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-2-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-2-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   控制台输出的日志            |   UI界面显示情况            |



#### **第五步：回到mtool工具，依然在翻译功能界面，选择加载翻译文件，选择Tradata.json文件即可。**
<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/5-1.png" width="400" height="300"> 


### **———————————————————工具功能说明——————————————**

1）仅仅支持mtool导出的json文件格式的json文件自动翻译，如果其他json文件格式一致，可以考虑使用。

2）如果希望翻译从其他语言到中文，可以尝试修改Prompt词，把“日语”换成源语言。

3）工具现在能够并发任务处理翻译文本啦，速度大幅度提升，不过由于openai的限制，基本只有付费账号才能享受到。


### **———————————————————程序问题说明——————————————**


1）因为chatgpt回答经常不按格式来，所以你会经常看见同样内容问几次，或者卡在这里一直循环问。建议去裁剪一下原文文本，分成小文件，翻译完成各文件后，再拼接回来。

2）编写软件时，看见最多的红框就是chatgpt的问题了，出现了请求拥挤，掉key，频率限制等问题。所以你也有可能遇到相关的问题。

3）因为没有认真去优化过代码，在VScode运行时，内存占用恐怖，要留下1g左右运行内存哦，避免出现问题

4）关于翻译花费的问题，我还没有细说。因为AI酱容易在翻译时，不按照格式来回答，所以有较高的错误率。按照我的经验大概翻译500kb大小的json文件就花费1刀左右，各位掂量着自己的余额。


### **———————————————————个人BB——————————————**

1）虽然有点编程基础，但还是第一次用python写程序，不是相关从业者，写法奇奇怪怪莫要怪。后续我不知道有没有时间去更新维护。既然已经开源了，就交给其他大佬了

2）AI酱实在太厉害啦，一边写一边问她，什么都能回答，帮我写，帮我改bug，heart，heart，heart。

### **———————————————————感谢——————————————**
如果没有这么好看的UI控件，我也不会写图形界面
https://github.com/zhiyiYo/PyQt-Fluent-Widgets
