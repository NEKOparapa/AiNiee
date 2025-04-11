<div align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png" width=60% height=60%>
  </a>
</div>

<div align="center">
  
  **一键解决你99%的烦恼，一键享受丝滑般的翻译**
</div>

---


## 软件介绍🧾 

  
<div align="center">

**AiNiee 是一款专注于 Ai 翻译的工具，一键自动翻译 游戏、小说、字幕、文档 等复杂的长文本内容。**


</div>



* **多格式支持**: 支持 json/xlsx/rpy 数据文件、Epub/TXT 小说、Srt/Vtt/Lrc 字幕、Word/MD 文档等多种格式，满足多样化需求。

* **多平台支持**: 无缝对接 OpenAI、Google、Anthropic、DeepSeek 等国内外主流 AI 平台，灵活选择，快速使用。

* **多语言互译**: 覆盖中文、英文、日文、韩文、俄语、西班牙语、法语、德语等多种语言，打破语言壁垒。

* **强大插件扩展**: 内置 双语对照器、翻译功能检查器、文本过滤器、文本规范器等实用插件，功能更强大。

* **高效批量翻译**: 多文件批量翻译、多线程并行处理、多 Key 轮询机制，效率倍增。

* **长文本专属优化**: 独家实现完美破限、tag翻译格式、思维链翻译、动态 Few-shot、自动术语统一、自动保留代码段、上下文理解、译文自动检查等技术，突破长文本翻译局限，保证译文连贯性。

* **高质量翻译追求**:提供提示词设置、AI 术语表、AI 禁翻表、文本替换、[双子星翻译](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8F%8C%E5%AD%90%E6%98%9F%E7%BF%BB%E8%AF%91%E4%BB%8B%E7%BB%8D)等高级功能，满足对翻译质量有更高要求的用户。

---

## AiNiee三步走 📢

* **第一步：配置接口**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第一步.png">

  - 在线接口：需付费但性价比很高，无显卡要求，全语言支持，[接口设置说明 - DeepSeek](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartDeepSeek)
  - 在线接口：同上，如果Deepseek官网无法正常使用，可换该接口，[接口设置说明 - 火山引擎](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartHuo)
  - SakuraLLM接口：免费，需要 8G+ 显存的 Nvidia 显卡，只支持日中，[接口设置说明 - SakuraLLM](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartSakuraLLM)

* **第二步：项目设置**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第二步.png">
  
  >`接口名称`: 选择你之前设置的接口<br>

  >`项目类型`: 选择待翻译的文件类型，小说、字幕、文档可直接进行翻译，游戏需要文本提取工具进行配合<br>

  >`原文语言`: 选择相应的原文文本语言<br>

  >`译文语言`: 你希望翻译成的语言<br>

  >`输入文件夹`: 把原文件放在这个文件夹内<br>

  >`输出文件夹`: 选择翻译后文件的存储文件夹，请不要和输入文件夹一个路径<br>

* **第三步：开始翻译**

  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第三步.png">

  - 点击开始按钮，剩下等待任务的完成。

  - [AiNiee下载地址](https://github.com/NEKOparapa/AiNiee/releases)

---

##  接口简介[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#接口简介)
   

 * **`🤖AI调用平台`**

      |支持平台|模型|白嫖情况|模型价格|限制情况|
      |:-----:|:-----:|:-----:|:-----:|:-----:|
      |[OpenAI](https://platform.openai.com/)|ChatGPT系列|现无免费额度|贵|用途广泛|
      |[GooGle](https://makersuite.google.com/app/apikey?hl=zh-cn)|Gemini系列|免费账号可白嫖，速度缓慢|贵|用途广泛|
      |[Cohere](https://dashboard.cohere.com/)|Command系列|免费账号可白嫖，速度一般|一般|用途广泛|
      |[Anthropic](https://console.anthropic.com/dashboard)|Claude系列|免费账号绑卡可白嫖少量额度，速度缓慢|贵|用途广泛|
      |[Deepseek](https://platform.deepseek.com/usage)|Deepseek系列|注册送少量免费额度，速度极快|便宜|用途广泛|
      |[Amazon Bedrock](https://aws.amazon.com/cn/bedrock/)|Claude或其他系列|速度极快|贵|安全限制|
      |[月之暗面](https://platform.moonshot.cn/console/info)|Moonshot系列|注册送少量免费额度|一般|用途广泛|
      |[零一万物](https://platform.lingyiwanwu.com/playground)|Yi系列|注册送少量免费额度|一般|安全限制|
      |[智谱清言](https://open.bigmodel.cn/overview)|GLM系列|注册送少量免费额度|一般|安全限制|
      |[阿里云百炼](https://bailian.console.aliyun.com/) |千问系列|注册送大量免费额度|便宜|安全限制|
      |[火山引擎](https://console.volcengine.com/ark)|豆包系列|注册送大量免费额度，速度极快|便宜|用途广泛|
      |[SakuraLLM](https://github.com/SakuraLLM/SakuraLLM)  |Sakura系列| 本地模型，需显卡  |免费|用途广泛|
      |[本地小模型](https://huggingface.co/models)  |开源模型| 本地模型，需显卡  |免费|用途广泛|


---

<details>
<summary>
  
## 游戏翻译[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#游戏翻译)
</summary>


<details>
<summary> 

### 工具准备
</summary>

 * **`📖游戏文本提取工具`**

      |工具名|介绍|项目类型|
      |:----:|:-----:|:-----:|
      |[Mtool](https://afdian.com/p/d42dd1e234aa11eba42452540025c377)|上手简单，推荐新人使用|Mtool导出文件|
      |[ParaTranzr](https://paratranz.cn/projects)|上手中等，功能强大，推荐大佬使用|ParaTranzr导出文件|
      |[RenPy SDK](https://www.renpy.org/latest.html)|上手中等，功能强大，推荐大佬使用|renpy导出文件|
      |[Translator++](https://dreamsavior.net/download/)|上手中等，功能强大，推荐大佬使用|T++导出文件或Trans工程文件|
      |[SExtractor](https://github.com/satan53x/SExtractor)|上手复杂，功能强大，推荐大佬使用|Mtool或者VNText导出文件|


 * **`📖术语表预提取工具`**

      |工具名|说明|
      |:----:|:-----:|
      |[小说工具箱](https://books.fishhawk.top/workspace/toolbox)|术语表辅助制作工具|
      |[KeywordGacha](https://github.com/neavo/KeywordGacha) |使用 AI 技术来自动生成实体词语表的翻译辅助工具|


 * **`📖本地模型运行工具`**

      |工具名|说明|
      |:----:|:-----:|
      |[Sakura_Launcher_GUI](https://github.com/PiDanShouRouZhouXD/Sakura_Launcher_GUI)|Sakura模型的专属GUI启动器|
      |[OneClickLLAMA](https://github.com/neavo/OneClickLLAMA) |一键运行 Qwen2.5 SakuraLLM 等本地 LLM 模型|
      |[LM Studio](https://lmstudio.ai/download) |一个本地部署大语言模型（LLM）平台，致力于简化LLM的使用和管理。|
      |[ollama](https://ollama.com/) |开源跨平台大模型工具 |


</details>



<details>
<summary>
  
### 翻译教程
</summary>

 * **`📺游戏翻译视频教程`**

      |视频链接|说明|
      |:----:|:-----:|
      |[Mtool教程](https://www.bilibili.com/video/BV1h6421c7MA) |初次使用推荐观看|
      |[Translator++教程](https://www.bilibili.com/video/BV1LgfoYzEaX/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501)|初次使用推荐观看|
      |[Wolf游戏教程](https://www.bilibili.com/video/BV1SnXbYiEjQ/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501)|初次使用推荐观看|


 * **`📺游戏翻译图文教程`**

      |视频链接|说明|
      |:----:|:-----:|
      |[Mtool教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Mtool) |适合新人，懒人翻译RPG,RenPY,Krkr等游戏，进行外挂式翻译|
      |[Translator++教程（工程版）](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Translator--%EF%BC%88%E5%B7%A5%E7%A8%8B%E6%96%87%E4%BB%B6%E7%89%88%EF%BC%89)|适合翻译RPG,RenPY,Krkr等等游戏，进行内嵌式翻译|
      |[Translator++教程（表格版）](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Translator-%EF%BC%88%E7%94%B5%E5%AD%90%E8%A1%A8%E6%A0%BC%E7%89%88%EF%BC%89)|适合翻译RPG,RenPY,Krkr等等游戏，进行内嵌式翻译（旧版教程）|
      |[Paratranz游戏教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Paratranz)|适合翻译各类大型游戏的MOD|
      |[StevExtraction工具教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90StevExtraction)|适合翻译RPGmakerMZ/MZ游戏|

</details>




</details>

---
<details>
<summary>
  
## 功能说明[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#功能说明)  
</summary>

<details>
<summary>

### 接口管理
</summary>

*  OpenAI官方配置示例:
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/翻译设置/官方账号设置.png" width="600" height="400"><br>

    > `模型选择`: 请自行了解模型之间的区别后再进行更改。<br>
  
    >`API KEY`: 填入由OpenAi账号生成的api_key<br>
  

*  自定义平台配置示例:
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/翻译设置/代理账号设置.png" width="600" height="400"><br> 
    
    >`请求地址`: 填入中转平台提供的请求地址,示例：`https://api.XXXXX.com` ,不要在后面单带一个`/`

    >`自动补全`: 会在上面输入的请求地址自动补全“v1”
    
    >`请求格式`: 根据中转能够支持的请求格式进行选择，一般是openai格式

    >`模型选择`: 可下拉选择，也可以自行填入模型名字<br>

    >`API KEY`: 填入中转平台给你生成的API KEY<br>


    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/翻译设置/代理账号速率价格设置.png" width="600" height="400"><br> 

  
    >`每分钟请求数`: RPM (requests per minute)每分钟向模型接口发送的翻译任务数量
  
    >`每分钟tokens数`: TPM (tokens per minute)每分钟向模型接口发送的tokens总数（类似字符总数）


</details>
  



<details>
<summary> 

### 项目设置
</summary>

*   配置示例:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/翻译设置/基础设置.png" width="600" height="400"><br>
    
    >`项目类型`: 需要翻译的原文文件类型<br>

    >`接口名称`: 翻译文本时希望使用的接口平台<br>

    >`原文语言`: 选择相应的原文文本语言<br>

    >`译文语言`: 你希望翻译成的语言<br>
  
    >`输入文件夹`: 选择你需要翻译的原文文件,把原文尽量放在一个干净的文件夹内，文件夹内没有其他文件，因为会读取该文件夹内所有相同的的文件类型，包括子文件<br>
  
    >`输出文件夹`: 选择翻译后文件的存储文件夹，请不要和输入文件夹一个路径<br>

</details>


<details>
<summary> 

### 提示词设置
</summary>

*   基础提示词:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/基础提示词设置.png" width="600" height="400"><br>
    
    >`通用`: 综合通用，花费最少，兼容各种模型，完美破限<br>

    >`思维链`: 融入翻译三步法，提升思考深度，极大增加输出内容，极大增加消耗，提升文学质量，适合普通模型，完美破限<br>

    >`推理模型`: 精简流程，为 DeepSeek-R1 等推理模型优化，释放推理模型的思考能力，获得最佳翻译质量<br>

    >`自定义提示词`: 系统提示词将更改为你所写内容<br>
    
</details>





<details>
<summary>
  
### 插件说明
</summary>

- [插件 - 标点修复器](https://github.com/NEKOparapa/AiNiee/wiki/PunctuationFixer)
- [插件 - 语言过滤器](https://github.com/NEKOparapa/AiNiee/wiki/LanguageFilter)
- [插件 - 文本规范器](https://github.com/NEKOparapa/AiNiee/wiki/TextNormalizer)
- [插件 - MTool 优化器](https://github.com/NEKOparapa/AiNiee/wiki/MToolOptimizer)
</details>





<details>
<summary> 

### 其他说明
</summary>

* ` 多key轮询`
  >如果想使用多个key来分担消耗压力，根据key数量进行加速翻译，请使用同类型账号的key，而且输入时在每个key中间加上英文逗号，不要换行。例如：key1,key2,key3

* ` 批量文件翻译`
  >把所有相同类型的文件放在输入文件夹即可，也支持多文件夹结构

* ` 配置迁移`
  >配置信息都会存储在resource的config.json中，下载新版本可以把它复制到新版本的resource中。
  
* `缓存文件`
   >当翻译遇到问题时，可以之后更改翻译项目为缓存文件，并在输入文件夹选择该缓存文件所在的文件夹进行继续翻译。当继续翻译Epub与word文件时，还需要把原来的文件和缓存文件放在同一个文件夹里面。

* `双子星翻译`
   >[详细介绍链接](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8F%8C%E5%AD%90%E6%98%9F%E7%BF%BB%E8%AF%91%E4%BB%8B%E7%BB%8D) 双请求结构的翻译流程，大佬们探索AI可能性的新玩具。

</details>


</details>



---

<details>
<summary>

## 贡献指南[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#贡献指南)  
</summary>


* **`开发增强插件`**: 请根据[插件编写指南](https://github.com/NEKOparapa/AiNiee/blob/main/PluginScripts/README.md)进行开发更强功能插件

* **`改进或增加支持文件`**: 需要有一定的代码编程能力，拉取源码进行改进。文件具体读取代码在ModuleFolders\FileReader与FileOutputer文件夹中。[读写器系统编写指南](https://github.com/NEKOparapa/AiNiee/blob/main/ModuleFolders/FileAccessor/README.md)。UI支持在UserInterface\Setting的ProjectSettingsPage。

* **`完善正则库`**: 正则库的完备将极大帮助游戏内嵌工作的进行，并利好下一次游戏翻译工作和造福其他翻译用户，正则库在[Resource\Regex](https://github.com/NEKOparapa/AiNiee/blob/main/Resource/Regex/regex.json)文件夹中

* **`改进翻译流程`**: [翻译文本测试项目](https://github.com/NEKOparapa/AiNiee-Test-Dataset)里面包含常用场景的一些数据文本，可以改进测试数据，或者以测试数据表现改进AiNiee翻译流程

* **`改进界面翻译`**: 多语言界面的UI文本可能翻译不够准确合适，可以提交你的修改意见，或者直接进行修改。本地化文本在[Resource\Localization](https://github.com/NEKOparapa/AiNiee/tree/main/Resource/Localization)文件夹中

</details>


---

## 特别声明[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#特别声明)   
AiNiee能够不断发展迭代至今，其关键功能框架均源于项目创立以来的持续个人研发、用户反馈建议以及大佬们PR的共同努力与创造。
这是两年以来一个不断摸索、持续改进、共同构筑的过程，才形成了AiNiee如今相对成熟和完整的AI翻译体系。

该款AI翻译工具仅供个人合法用途,任何使用该工具进行直接或者间接非法盈利活动的行为,均不属于授权范围,也不受到任何支持和认可。

* **`交♂交流群`**:  QQ交流群(主要，答案：github)：8216248九零，备用TG群：https://t.me/+JVHbDSGo8SI2Njhl ,

---



## 赞助💖
[![xxxx](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/徽章.png)](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/赞赏码.png)

