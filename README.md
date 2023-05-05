# AiNiee-chatgpt

***

基于mtool导出的json文件，chatgpt自动批量翻译工具，主要是用来翻译各种RPG游戏。

教程视频：https://www.bilibili.com/video/BV12V4y1R7PG


### **依赖环境要求**
---


##### **运行必备工具**

* 代理环境：自己得弄个好的代理环境，设置全局代理或者其他方式，不然api接口会频繁报错无法连接，错误代码443或者一直没有回复。

* mtool工具：https://afdian.net/a/AdventCirno  免费版本就可以,如果有条件也希望支持一下，此工具也有chatgpt翻译功能，更快更简单。

* API_Key：新建一个,并且最好在使用期间不要和其他程序一起使用，不然容易达到请求次数限制



##### **（可选）自行编译环境**

* pyhone环境：到官网https://www.python.org/downloads/windows/ 下载合适的版本安装，我编程时是3.10.7版本，所以也建议安装3.10.7，其他不是太老应该也没有问题

* IDE软件：能运行python的IDE软件如vscode https://code.visualstudio.com/    pycharm等等 。

* AI相关库和UI相关库：打开cmd，分别输入下面每行代码后回车。
```python
pip install openai                       
```
```python
pip3 install PyQt5
```
```python
pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
```




### **工具使用说明**
---
* #### **第一步：首先利用mtool软件打开你喜欢的rpg游戏，并将在翻译功能界面，选择导出需要被翻译的文本，将ManualTransFile.json文件导出。**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/1-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/1-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   打开mtool的翻译界面            |   导出游戏内文本文件            |





* #### **第二步：右键管理员运行AiNiee-chatgpt3.exe程序,然后填写配置信息。**


##### **1.配置示例**

<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/2-1.png" width="400" height="300"> 


##### **2.配置说明**


【  账号类型 】是你账号类型，免费用户基本只能并发两三个线程翻译任务，而付费用户可以并发几十个，大幅缩减翻译时间。

【  模型选择 】默认都是GPT3.5,如果你的账号获得了GPT4的使用资格，请选择付费账号（48h后）和模型gpt-4来进行翻译，并且可以把Lines设置为80。

【  API KEY  】填入你的api_key

【  代理地址  】如果需要设置代理，则填入http://<代理ip>:<代理端口>，示例：http://127.0.0.1:10081

【  Lines    】是每次请求翻译的文本行数。行数设置越大，整体的翻译效果会更好，上下文更加流畅，但每次请求回复速度会越慢，回复的内容越容易出错，建议gpt3.5模型不要设置超过50，gpt4模型不超过90。

【  Prompt   】是系统提示词，用于告诉chatgpt任务目标的命令语。希望大家有空去探索一下Prompt的写法，如果写得越好，AI酱就能更能准确回复译文格式，以你想要的写作风格进行翻译。只要在Prompt里加上"以json文件格式回复译文"，程序就能够处理。

【  文件位置  】是选择你需要翻译的原文文件，也是ManualTransFile.json文件

【  输出文件夹】是选择翻译后文件的存储文件夹


* #### **第三步：配置好代理环境，点击【测试请求】按钮，测试当前网络环境**
<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/3-1.png" width="400" height="300"> 

* #### **第四步：点击【开始翻译】按钮，看控制台输出日志或者进度条。之后等待翻译进度到百分百，自动生成翻译好的文件Tradata.json在输出文件夹中。**


##### **正在进行翻译**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-1-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-1-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   控制台输出的日志            |     UI界面显示情况            |


这个过程比较煎熬，通常我翻译1mb的json文件，就得花一个小时左右，免费玩家就是这样的，而付费玩家，使用多线程功能，可以基本在20分钟左右翻译完成。



##### **已经完成翻译**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-2-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-2-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   控制台输出的日志            |   UI界面显示情况            |




* #### **第五步：回到mtool工具，依然在翻译功能界面，选择加载翻译文件，选择Tradata.json文件即可。**
<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/5-1.png" width="400" height="300"> 


### **工具功能说明**
---
* 仅仅支持mtool导出的json文件格式的json文件自动翻译，如果其他json文件格式一致，可以考虑使用。

* 如果希望翻译从其他语言到中文，可以尝试修改Prompt词，把“日语”换成源语言，英语除外，因为已经被设置过滤了。


### **常见问题建议**
---

* 经过几个版本的优化，从以前的翻译1mb大小json文件花费3刀左右，已经减少到1.5刀左右，所以大家在进行翻译前，掂量一下自己的账号余额。

### **个人BB**
---
* 虽然有点编程基础，但还是第一次用python写程序，不是相关从业者，写法奇奇怪怪莫要怪。后续我不知道有没有时间去更新维护。既然已经开源了，就交给其他大佬了

* AI酱实在太厉害啦，一边写一边问她，什么都能回答，帮我写，帮我改bug，heart，heart，heart。

* 建了一个QQ交流群821624890，群里只用于反应bug，功能建议，以及prompt词交流，不要分享各种游戏资源，发黄键镇

### **感谢**
---
如果没有这么好看的UI控件，我也不会写图形界面
https://github.com/zhiyiYo/PyQt-Fluent-Widgets
