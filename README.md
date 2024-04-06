<p align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png">
  </a>
<p>


**一款专注于Ai翻译的工具，可以用来一键自动翻译RPG SLG游戏，Epub TXT小说，Srt Lrc字幕等等**

*Artificial Intelligence Narrative Interpretation and Exploration Engine？*


  
# 声明🧾 
***
该款AI翻译工具仅供个人合法用途,任何使用该工具进行直接或者间接非法盈利活动的行为,均不属于授权范围,也不受到任何支持和认可。

* **`交♂交流群`**:  QQ交流群：821624890，备用QQ群：729610150，备用TG群：https://t.me/+JVHbDSGo8SI2Njhl ,

#  工具准备🏕️
***
 * **`🟪好用的魔法工具`**:我们**强烈建议**您选择优质稳定的代理工具,不然api接口会频繁报错无法连接或者一直没有回复
 * **`📖文本提取工具`**:[Mtool下载地址](https://afdian.net/a/AdventCirno?tab=feed)  [Translator++下载地址](https://dreamsavior.net/download/)  [SExtractor下载地址](https://github.com/satan53x/SExtractor)
   > 两者免费版本就可以,新人推荐Mtool,如果希望能够自行校正,获得更好的翻译效果,推荐Translator++或者SExtractor
* **`🤖AI平台账号`**: [OpenAI平台](https://platform.openai.com/)    [GooGle平台](https://makersuite.google.com/app/apikey?hl=zh-cn)    [Anthropic平台](https://console.anthropic.com/dashboard)    [Moonshot平台](https://platform.moonshot.cn/console/info)    [智谱平台](https://open.bigmodel.cn/overview)
* **`📡下载地址`**: [AiNiee下载地址](https://github.com/NEKOparapa/AiNiee/releases)
* **`📺视频教程`**: [Mtool教程](https://www.bilibili.com/video/BV1h6421c7MA)      [T++教程](https://www.bilibili.com/video/BV18c411K7WN?p=2)

<details>
<summary><b> 

# 使用方法📝
</b> </summary>



<details>
<summary><b> 

### 账号配置
</b> </summary>

*  OpenAI官方配置示例:
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/官方账号设置.png" width="600" height="400"><br>
  
    >`账号类型`: 新注册的5刀余额账号为免费账号，且每分钟只能翻译3次，每天一共只能翻译200次；付费账号是有过付费记录，且达到一些条件才会升级<br>
  
    > `模型选择`: 默认是GPT3.5模型，请自行了解模型之间的区别后再进行更改。<br>
  
    >`API KEY`: 填入由OpenAi账号生成的api_key<br>
  
    >`代理端口`: 可以不输入,如果需要设置代理时,再则填入http://<代理ip>:<代理端口>,示例：`http://127.0.0.1:10081`<br>

*  OpenAI中转配置示例:
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/代理账号设置.png" width="600" height="400"><br> 
    
    >`请求地址`: 填入国内代理平台提供的请求地址,示例：`https://api.openai-sb.com/v1`
    
    >`模型选择`: 默认是GPT3.5模型，请自行了解模型之间的区别后再进行更改。<br>

    >`API KEY`: 填入国内代理平台给你生成的API KEY<br>

    >`代理端口`: 可以不输入,如果需要设置代理时,再则填入http://<代理ip>:<代理端口>,示例：`http://127.0.0.1:10081`<br>
  
    >`每分钟请求数`: RPM (requests per minute)每分钟向openai发送的翻译任务数量`
  
    >`每分钟tokens数`: TPM (tokens per minute)每分钟向openai发送的tokens总数（类似字符总数）

    >`请求输入价格`: 根据国内代理平台设定的价格进行设置，单位是每1k tokens
    
    >`回复输出价格`: 根据国内代理平台设定的价格进行设置，单位是每1k tokens

*  SakuraLLM配置:
  
    1.Kaggle云平台方法：https://github.com/SakuraLLM/Sakura-13B-Galgame/wiki/%E7%99%BD%E5%AB%96Kaggle%E5%B9%B3%E5%8F%B0%E9%83%A8%E7%BD%B2%E6%95%99%E7%A8%8B

    2.Autodl云平台方法：https://books.fishhawk.top/forum/65719bf16843e12bd3a4dc98#%E5%A6%82%E4%BD%95%E4%BD%BF%E7%94%A8AutoDL%E9%83%A8%E7%BD%B2

    3.部署好模型后，获取接口地址，填入请求地址栏中，注意，接口地址中不要包含`/v1`，否则会报错<br>


</details>
  


<details>
<summary><b> 

### 翻译配置
</b> </summary>

*   配置示例:<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Mtool/翻译设置Mtool.png" width="600" height="400"><br>
    
    >`翻译项目`: 先前导出原文文件的工具<br>

    >`翻译平台`: 翻译文本时希望使用的平台<br>

    >`文本源语言`: 根据你需要翻译游戏的语言选择相应的源语言<br>

    >`文本目标语言`: 你希望翻译成的语言<br>
  
    >`输入文件夹`: 选择你需要翻译的原文文件,把导出的文件尽量放在一个文件夹内，文件夹内没有其他文件，因为会读取该文件夹内所有相关的文件<br>
  
    >`输出文件夹`: 选择翻译后文件的存储文件夹，请不要和输入文件夹一个路径<br>


    >`每次翻译行数`: 每次请求翻译的文本行数。行数设置越大,整体的翻译效果会更好,上下文更加流畅,但每次请求回复速度会越慢,回复的内容越容易出错。根据模型类型来进行设置，建议gpt3.5基础模型不要设置超过40,gpt4基础模型不超过80<br>

    >`最大线程数`: 请根据电脑自身情况设置，线程数越大，越容易吃满Openai的速率限制，翻译速度越快。最大线程数设置上限为999，建议设置100以内<br>

    >`错误重翻最大次数限制`: 就是一段文本，出现错误回复时，最多允许重复翻译的次数<br>  
    
    >`保留换行符`: 该功能尽可能地保留文本中的/r/n，但不总是能够完全保留，仍有小部分位置错乱，消失或者变成其他特殊符号。<br>

    >`简繁体自动转换`: 要求翻译成简体中文或者繁体中文时，将文本不符合要求的文本进行转换<br>

    >`处理首尾非文本字符`: 主要用于T++导出的文本，该工具导出的文本带很多代码文本，可以截取处理了，翻译了，再复原回来<br>



    >`首轮翻译平台`: 文本会首先以当初设置的翻译行数进行翻译， 如果翻译时出现错误回复次数达到限制，则进入下轮次再次翻译<br>

    >`剩余轮翻译平台`: 将之前没能成功翻译的文本拆分翻译，会重新自动计算翻译行数，并更换翻译平台，如果不设置，则沿用上轮设置的翻译平台<br>

    >`翻译流程最大轮次限制`: 翻译流程的整体翻译轮次限制<br>  

</details>





<details>
<summary><b>
  
### 如果使用MTOOL进行游戏翻译
</b> </summary>
*  1.使用Mtool打开游戏,并在翻译功能界面,选择导出游戏原文文件,会在游戏根目录生成：ManualTransFile.json<br>
  
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Mtool/导出原文1.png" width="600" height="400">  |  <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Mtool/导出原文2.png" width="600" height="400">
  <br>
  
*  2.在`翻译设置`界面的`翻译项目`选择`🔵Mtool导出文件`,并配置翻译设置<br>
    >配置示例:<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Mtool/翻译设置Mtool.png" width="600" height="400"><br>
    
  
* 3.🖱️到开始翻译页面，点击**开始翻译**按钮,看控制台输出日志或者进度条。之后等待翻译进度到百分百,自动生成翻译好的文件在输出文件夹中
    > 正在进行翻译<br>
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Mtool/UI界面正在翻译.png"  width="600" height="400">
   

    > 已经完成翻译<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Mtool/UI界面翻译完成.png" width="600" height="400">


* 4.回到`🔵Mtool`工具,依然在翻译功能界面,选择加载翻译文件,选择翻译后的文件即可
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Mtool/导入译文.png" width="600" height="400"> 

</details>




<details>
<summary><b>
  
### 如果使用T++进行游戏翻译
</b> </summary>
  
* 1.🖱️打开`🔴Translator++`,选择“start a new project”,根据你的游戏图标来选择对应的游戏引擎<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/新建工程1.png" width="600" height="400"> | <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/新建工程2.png" width="600" height="400"><br>
    
* 2.选择你的游戏文件,创建新工程,软件会自动解包和导入游戏数据<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/新建工程3.png" width="600" height="400"> | <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/新建工程4.png" width="600" height="400">
    
    > 当弹出提示框,问你：**Do you  also want to load JavaScript files**时,选择**Cancel**,加载脚本里的文本修改容易出错

* 3.🖱️点"Options"按钮,选择"Preferences",选择"UI Language",选择简体中文,方便之后操作<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/汉化设置1.png" width="600" height="400"> | <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/汉化设置2.png" width="600" height="400"><br>
    
* 4.点左上角的导出工程,选择导出格式为XML格式到你指定的文件夹,生成data文件夹<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/导出工程1.png" width="600" height="400"> | <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/导出工程2.png" width="600" height="400">
    
    > 当弹出提示框,问如何处理标记列,就点击红色和选择**Do not process row with selected tag**,或者不设置直接导出,因为这工具暂时存在bug,无法过滤标记内容
    
* 5.在`翻译设置`界面的`翻译项目`选择`🔴T++导出文件`,配置翻译设置<br>
    > 配置示例<br>
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/翻译配置Tpp.png" width="600" height="400"><br>
    > `项目文件夹`: 选择之前`🔴Translator++`导出的项目文件夹data<br>
    > `输出文件夹`: 选择翻译后项目文件夹的存储文件夹<br>

    
* 6.🖱️到开始翻译页面，点**开始翻译**按钮,等待翻译进度到百分百,生成翻译好的data文件夹在输出文件夹中<br>
    > 1.回到`🔴Translator++`+,点击导入工程,选择从电子表格导入翻译,点击“Import Folder”,选择输出文件夹里的data文件夹,点击导入<br>
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/导入工程1.png" width="600" height="400"> | 
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/导入工程2.png" width="600" height="400"><br>

    > 2.🖱️右键左侧区域,移到"全部选择",选择"Create Automation",选择"对每行",复制粘贴下面的代码运行<br>
  
* 7.对**红色标签内容进行修改**,这些内容不能翻译,以免游戏脚本出现错误。
  ```JavaScript
  if (this.tags) {
    if (this.tags.includes("red")) this.cells[1]=this.cells[0];
  }
  ```
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/处理错误1.png" width="600" height="400"> | <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/处理错误2.png" width="600" height="400">
  
   > 3.查看左边文件有哪个没有到达百分百的,寻找到空行并自行翻译
  
* 8.最后选择导出工程,选择导出到文件夹,指定**你的游戏目录里的data文件夹的上一级文件夹**,原文件会被替换,请注意备份原游戏
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/修改游戏1.png" width="600" height="400"> | <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Tpp/修改游戏2.png" width="600" height="400">
</details>


<details>
<summary><b>
 
### 如果使用StevExtraction进行游戏翻译
</b> </summary>

*  0.工具详情功能及介绍：[工具作者页面](https://www.ai2moe.org/topic/10271-jt%EF%BC%8C%E7%9B%AE%E6%A0%87%E6%98%AF%E9%9B%B6%E9%97%A8%E6%A7%9B%E7%9A%84%EF%BC%8C%E5%86%85%E5%B5%8C%E4%BA%86%E5%A4%9A%E4%B8%AA%E8%84%9A%E6%9C%AC%E7%9A%84%E9%9D%92%E6%98%A5%E7%89%88t/) 


*  1.在提取页面进行提取,目前只能适应于RPG Maker MVMZ游戏，能提取到游戏的原文和人物名字
    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Extraction/提取原文.png" width="600" height="400"> <br>
    >`是否日语游戏`: 根据游戏进行选择<br>

    >`是否翻译note类型文本`: # 在翻译ACT游戏时，尝试关闭该选项，否则大概率无法攻击或攻击没有效果<br>

    >`游戏文件夹`: 游戏根目录<br>

    >`原文存储文件夹`: 提取到的游戏原文存储的地方<br>
  
    >`工程存储文件夹`: 关于这个游戏的工程数据存储的地方，后面注入还会用到<br>
  
  
*  2.在`翻译设置`界面的`翻译项目`选择`🔵T++导出文件`,并配置翻译设置


*  3.注入回原文
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Extraction/注入译文.png"  width="600" height="400"> <br>
    
    >`游戏文件夹`: 游戏根目录<br>

    >`译文文件夹`: 之前经过翻译的原文文件<br>
  
    >`工程文件夹`: 之前这个游戏的工程数据存储的地方<br>

    >`存储文件夹`: 注入译文后存储的地方<br>

</details>




<details>
<summary><b>

### 如果使用 Paratranz 进行游戏翻译
</b> </summary>

*  0.工具详情：[官方网站](https://paratranz.cn/) 这是一个专用于业余翻译工作的站点，与 Ainiee 的对接主要用于预先对文本进行机翻，之后可以进行校对。

*  1.在项目的 `文件管理` 界面，对需要进行翻译的原文，执行 `下载原始数据` ，将下载下来的数据复制到 `翻译设置` 中的 `输入文件夹` 目录
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Paratranz/Paratranz_export.png" width="600" height="400"> <br>
*  2.在`翻译设置`界面的`翻译项目`选择`🔵Paratranz导出文件`,并配置翻译设置<br>
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Paratranz/project_type.png" width="600" height="400"> <br>
*  3.🖱️到开始翻译页面，点击**开始翻译**按钮,看控制台输出日志或者进度条。之后等待翻译进度到百分百,自动生成翻译好的文件在输出文件夹中
*  4.回到 `Paratranz`工具,依然在 `文件管理` 界面,选择 `导入译文` ,选择翻译后的 json 文件进行导入即可
</details>




</details>

***

<details>
<summary><b> 

# 功能说明🕹️ 
</b> </summary>

* ` 多key轮询`
  >如果想使用多个key来分担消耗压力，根据key数量进行加速翻译，请使用同类型账号的key，而且输入时在每个key中间加上英文逗号，不要换行。例如：key1,key2,key3
  
* ` 配置迁移`
  >配置信息都会存储在resource的config.json中，下载新版本可以把它复制到新版本的resource中。
  
* `自动备份缓存文件到输出文件夹`
  >当翻译遇到问题时，可以之后更改翻译项目为缓存文件，并在输入文件夹选择该缓存文件所在的文件夹进行继续翻译。当继续翻译Epub小说文件时，还需要把原来的文件和缓存文件放在同一个文件夹里面
  
* `导出当前任务的已翻译文件`
  >会将已经翻译好的内容和未翻译的内容导出，mtool项目会分为两个文件，会带有不同的后缀。T++项目会仍然是同一个文件里，已翻译文本的右边会有内容，未翻译的没有。其他项目都会混合在一个文件里。
  
* `提示字典`
  >用来统一名词的翻译，让AI翻译的人名，物品名词，怪物名词，特殊名词能够翻译成你想要的样子。

* `替换字典`
  >用于翻译前修改原文，翻译后修正译文

* `AI实时调教`
  >用来改变AI的参数设定，控制AI生成内容时的随机性，重复性，通常用来解决语气词重复的问题

* `提示词工程`
  >用于修改prompt与添加翻译示例，帮助AI进行少样本学习，获取更好的翻译效果，但会消耗更多的tokens。
  
</details>

***

<details>
<summary><b> 

# 常见问题🐛 
</b> </summary>

* 【如何反馈自己在使用中遇到的问题】————————将cmd窗口（黑黑的那个框框）的内容完整截图下来，里面有程序运行日志，还有软件界面设置截图，然后将问题描述清晰带上截图到群里或者issue提问。当进一步排除问题，需要到原文本或者翻译后文本时，请压缩并上传。

* 【翻译“卡住”了】————————如果运行日志中，无错误提醒，请耐心等待

* 【翻译游戏到特定进度，就显示错误代码443】————————换质量好的梯子

* 【mtool导入翻译文本后，显示一句原文一句译文，或者全部原文】————————更新mtool到最新版，或者找mtool作者反馈该问题
  
* 【翻译后文本导入到T++不完全，部分未能百分百】————————在非RPGMVZ游戏中，出现该问题比较多，使用最新赞助版T++可以缓解，还可以自己手动打开表格，自己复制粘贴进去

</details>

***

# 赞助💖
[![xxxx](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/徽章.png)](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/赞赏码.png)

