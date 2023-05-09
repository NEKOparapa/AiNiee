# AiNiee-chatgpt

***

一款基于【mtool】或【Translator++】，chatgpt自动批量翻译工具，主要是用来翻译各种RPG游戏。

教程视频：https://www.bilibili.com/video/BV12V4y1R7PG


## **依赖环境要求**
---


#### **运行必备环境**

* pyhone环境：到官网https://www.python.org/downloads/windows/ 下载合适的版本安装，建议安装3.7以上

* 代理工具：自己得弄个好的代理环境，设置全局代理或者其他方式，不然api接口会频繁报错无法连接，错误代码443或者一直没有回复。

* 【Mtool】或者【Translator++】：   【Mtool】下载地址：https://afdian.net/a/AdventCirno?tab=feed  ··· 【Translator++】 下载地址：https://dreamsavior.net/download/    两者免费版本就可以，新人推荐mtool，如果希望获得更好的效果推荐Translator++

* API_Key：新建一个,并且最好在使用期间不要和其他程序一起使用，不然容易达到请求次数限制



#### **（可选）自行编译环境**

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
```python
pip install openpyxl
```
```python
pip install -U sentence-transformers
```


## **工具使用说明**
---


### **（1）首先双击运行“初始化依赖环境.cmd”，第一次使用该工具，会自动安装上面的依赖库，如果已经安装了，则会很快结束。**

安装过程中如果报错了，可重新运行，还是无法解决，请根据报错内容进行解决，或者手动安装AI相关库和UI相关库。
安装完成后会自动生成一个【启动AiNiee-chatgpt4.cmd】文件在根目录下。


### **（2）双击“启动AiNiee-chatgpt4.cmd”，在账号设置页面配置你的账号信息以及API KEY。**

#### **1.配置示例**

<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/2-1.png" width="400" height="300"> 


#### **2.配置说明**


【  账号类型 】是你账号类型，免费用户基本只能并发两三个线程翻译任务，而付费用户可以并发几十个，大幅缩减翻译时间。

【  模型选择 】默认都是GPT3.5,如果你的账号获得了GPT4的使用资格，请选择付费账号（48h后）和模型gpt-4来进行翻译，并且可以把Lines设置为80。

【  API KEY  】填入你的api_key

【  代理地址  】可以不输入，如果需要设置代理时，再则填入http://<代理ip>:<代理端口>，示例：http://127.0.0.1:10081



### **（3）如果使用Mtool进行翻译请根据以下步骤操作**


* #### **使用Mtool导出游戏原文文件：ManualTransFile.json**

<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/3-1.png" width="400" height="300"> 



* #### **在工具界面选择Mtool项目，并配置翻译设置**

##### **1.配置示例**

<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/2-1.png" width="400" height="300"> 


##### **2.配置说明**

【  Lines    】是每次请求翻译的文本行数。行数设置越大，整体的翻译效果会更好，上下文更加流畅，但每次请求回复速度会越慢，回复的内容越容易出错，建议gpt3.5模型不要设置超过50，gpt4模型不超过90。

【  Prompt   】是系统提示词，用于告诉chatgpt任务目标的命令语。希望大家有空去探索一下Prompt的写法，如果写得越好，AI酱就能更能准确回复译文格式，以你想要的写作风格进行翻译。只要在Prompt里加上"以json文件格式回复译文"，程序就能够处理。

【  文件位置  】是选择你需要翻译的原文文件，也是ManualTransFile.json文件

【  输出文件夹】是选择翻译后文件的存储文件夹



* #### **点击【开始翻译】按钮，看控制台输出日志或者进度条。之后等待翻译进度到百分百，自动生成翻译好的文件Tradata.json在输出文件夹中。**

#### **1.正在进行翻译**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-1-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-1-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   控制台输出的日志            |     UI界面显示情况            |


这个过程比较煎熬，通常我翻译1mb的json文件，就得花一个小时左右，免费玩家就是这样的，而付费玩家，使用多线程功能，可以基本在20分钟左右翻译完成。



#### **2.已经完成翻译**

| <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-2-1.png" width="400" height="300">  | <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/4-2-2.png" width="400" height="300">  |
| :--------------------------: | :--------------------------: |
|   控制台输出的日志            |   UI界面显示情况            |

运行中会实时输出TrsData.json和ManualTransFile.json存储在Backup Folder文件夹里，Backup Folder文件夹里面的ManualTransFile.json是还没有翻译的数据，TrsData.json是现在已经翻译好的数据。如果因为意外中断了，把文件夹里的文件A（TrsData.json）放置其他地方保存，再选择备份文件夹里面的ManualTransFile.json开始翻译，生成新的文件B（TrsData.json）。然后把文件B里的数据复制粘贴到文件A里面。


* #### **回到mtool工具，依然在翻译功能界面，选择加载翻译文件，选择Tradata.json文件即可。**
<img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/5-1.png" width="400" height="300"> 



### **（3）如果使用Translator++进行翻译请根据以下步骤操作**


## **工具功能说明**
---
* 仅仅支持mtool导出的json文件格式的json文件自动翻译，如果其他json文件格式一致，可以考虑使用。

* 如果希望翻译从其他语言到中文，可以尝试修改Prompt词，把“日语”换成源语言，英语除外，因为已经被设置过滤了。


## **常见问题建议**
---

* 经过几个版本的优化，从以前的翻译1mb大小json文件花费3刀左右，已经减少到1.5刀左右，所以大家在进行翻译前，掂量一下自己的账号余额。

* 特别注意，在翻译到最后99%时，因为要处理难翻译的文本，所以要处理蛮长一段时间，输出日志更新很慢，要保持耐心等待。除非频繁报错。

## **个人BB**
---
* 虽然有点编程基础，但还是第一次用python写程序，不是相关从业者，写法奇奇怪怪莫要怪。后续我不知道有没有时间去更新维护。既然已经开源了，就交给其他大佬了

* AI酱实在太厉害啦，一边写一边问她，什么都能回答，帮我写，帮我改bug，heart，heart，heart。

* 建了一个QQ交流群821624890，群里只用于反应bug，功能建议，以及prompt词交流，不要分享各种游戏资源，发黄键镇

## **感谢**
---
如果没有这么好看的UI控件，我也不会写图形界面
https://github.com/zhiyiYo/PyQt-Fluent-Widgets
