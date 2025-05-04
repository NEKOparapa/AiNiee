<div align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png" width=60% height=60%>
  </a>
</div>

<div align="center">
  
  **One-click solution for 99% of your translation troubles, enjoy smooth translation experience**
</div>

---


## Introduction🧾 

  
<div align="center">

**AiNiee is a tool focused on AI translation, offering one-click automatic translation for games, novels, subtitles, documents, and other complex long-text content.**


</div>



* **Multi-format Support**: Supports various formats including json/xlsx/rpy data files, Epub/TXT novels, Srt/Vtt/Lrc subtitles, Word/MD documents, meeting diverse needs.

* **Multi-platform Support**: Seamlessly integrates with mainstream AI platforms both domestic and international, such as OpenAI, Google, Anthropic, DeepSeek, offering flexible choices and quick usage.

* **Multi-language Translation**: Covers Chinese, English, Japanese, Korean, Russian, Spanish, French, German, and many other languages, breaking down language barriers.

* **Powerful Plugin Extensions**: Built-in useful plugins such as Bilingual Comparator, Translation Function Checker, Text Filter, Text Normalizer, enhancing functionality.

* **Efficient Batch Translation**: Multi-file batch translation, multi-threaded parallel processing, multi-key polling mechanism, greatly improving efficiency.

* **Long Text Optimization**: Exclusive technologies including perfect limit breaking, tag translation format, chain-of-thought translation, dynamic few-shot, automatic terminology unification, automatic code segment preservation, context understanding, and automatic translation checking, breaking through long text translation limitations and ensuring translation coherence.

* **High-quality Translation Pursuit**: Provides advanced features such as prompt settings, AI terminology table, AI do-not-translate list, text replacement, [Gemini Translation](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8F%8C%E5%AD%90%E6%98%9F%E7%BF%BB%E8%AF%91%E4%BB%8B%E7%BB%8D) for users with higher translation quality requirements.

---

## Three Steps to Use AiNiee 📢

* **Step 1: Configure Interface**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第一步.png">

  - Online Interface: Paid but cost-effective, no GPU requirements, full language support, [Interface Setup Guide - DeepSeek](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartDeepSeek)
  - Online Interface: Same as above, if DeepSeek official website is not accessible, you can use this alternative, [Interface Setup Guide - Volcano Engine](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartHuo)
  - SakuraLLM Interface: Free, requires Nvidia GPU with 8GB+ VRAM, only supports Japanese-Chinese translation, [Interface Setup Guide - SakuraLLM](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartSakuraLLM)

* **Step 2: Project Settings**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第二步.png">
  
  >`Interface Name`: Select the interface you configured earlier<br>

  >`Project Type`: Select the file type to be translated; novels, subtitles, documents can be translated directly, games require text extraction tools<br>

  >`Source Language`: Select the language of the original text<br>

  >`Target Language`: The language you want to translate to<br>

  >`Input Folder`: Place the original files in this folder<br>

  >`Output Folder`: Select a folder to store the translated files, please use a different path from the input folder<br>

* **Step 3: Start Translation**

  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第三步.png">

  - Click the start button and wait for the task to complete.

  - [AiNiee Download Link](https://github.com/NEKOparapa/AiNiee/releases)

---

##  Interface Introduction[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#interface-introduction)
   

 * **`🤖AI Platforms`**

      |Supported Platforms|Models|Free Options|Model Price|Limitations|
      |:-----:|:-----:|:-----:|:-----:|:-----:|
      |[OpenAI](https://platform.openai.com/)|ChatGPT Series|No free quota currently|Expensive|Widely applicable|
      |[Google](https://makersuite.google.com/app/apikey?hl=zh-cn)|Gemini Series|Free accounts available, slow speed|Expensive|Widely applicable|
      |[Cohere](https://dashboard.cohere.com/)|Command Series|Free accounts available, moderate speed|Average|Widely applicable|
      |[Anthropic](https://console.anthropic.com/)|Claude Series|No free quota|Expensive|Widely applicable|
      |[DeepSeek](https://platform.deepseek.com/)|DeepSeek Series|No free quota|Inexpensive|Widely applicable|
      |[Moonshot](https://platform.moonshot.cn/)|Moonshot Series|No free quota|Inexpensive|Widely applicable|
      |[Sakura](https://github.com/SakuraLLM/Sakura-13B-Galgame)|Sakura Series|Free local model|Free|Japanese-Chinese only|
      |[Ollama](https://ollama.com/)|Various Models|Free local model|Free|Limited capabilities|
      |[LM Studio](https://lmstudio.ai/)|Various Models|Free local model|Free|Limited capabilities|
      |[Huoshan](https://www.volcengine.com/)|Huoshan Series|No free quota|Inexpensive|Widely applicable|
      |[Zhipu](https://open.bigmodel.cn/)|GLM Series|No free quota|Inexpensive|Widely applicable|
      |[Baidu](https://cloud.baidu.com/product/wenxinworkshop)|ERNIE Series|No free quota|Inexpensive|Widely applicable|

---

<details>
<summary>

## Game Translation[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#game-translation)
</summary>


<details>
<summary> 

### Tool Preparation
</summary>

 * **`📖Game Text Extraction Tools`**

      |Tool Name|Introduction|Project Type|
      |:----:|:-----:|:-----:|
      |[Mtool](https://afdian.com/p/d42dd1e234aa11eba42452540025c377)|Easy to use, recommended for beginners|Mtool export files|
      |[GalTransl](https://github.com/XD2333/GalTransl)|Comprehensive features, suitable for experienced users|GalTransl export files|
      |[StevExtraction](https://github.com/regomne/chinesize/tree/master/StevExtraction)|Supports RPGmaker MV/MZ games|StevExtraction export files|
      |[Wolf RPG Editor Translator](https://github.com/jctaoo/WolfrpgTranslator)|Supports Wolf RPG Editor games|Wolf RPG export files|
      |[Translator++](https://dreamsavior.net/download/)|Supports multiple game engines|Translator++ export files|
      |[RPGMV-Translator](https://github.com/miaowm5/RPGMV-Translator)|Supports RPGmaker MV games|RPGMV-Translator export files|
      |[Locale Emulator](https://github.com/xupefei/Locale-Emulator)|Solves Japanese game encoding issues|N/A|

 * **`📖Translation Auxiliary Tools`**

      |Tool Name|Description|
      |:----:|:-----:|
      |[Novel Toolbox](https://books.fishhawk.top/workspace/toolbox)|Terminology table creation assistant tool|
      |[KeywordGacha](https://github.com/neavo/KeywordGacha) |AI-powered tool for automatically generating entity term translations|

 * **`📖Local Model Running Tools`**

      |Tool Name|Description|
      |:----:|:-----:|
      |[Sakura_Launcher_GUI](https://github.com/PiDanShouRouZhouXD/Sakura_Launcher_GUI)|Dedicated GUI launcher for Sakura models|
      |[Text-generation-webui](https://github.com/oobabooga/text-generation-webui) |Web UI for running text generation models locally|
      |[LM Studio](https://lmstudio.ai/download) |A local large language model (LLM) platform designed to simplify the use and management of LLMs|
      |[ollama](https://ollama.com/) |Open-source cross-platform large model tool|

</details>



<details>
<summary>
  
### Translation Tutorials
</summary>

 * **`📺Game Translation Video Tutorials`**

      |Video Link|Description|
      |:----:|:-----:|
      |[Mtool Tutorial](https://www.bilibili.com/video/BV1h6421c7MA) |Recommended for first-time users|
      |[GalTransl Tutorial](https://www.bilibili.com/video/BV1Yw411q7Zv/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501) |Recommended for first-time users|
      |[Wolf Game Tutorial](https://www.bilibili.com/video/BV1SnXbYiEjQ/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501)|Recommended for first-time users|

 * **`📺Game Translation Text Tutorials`**

      |Tutorial Link|Description|
      |:----:|:-----:|
      |[Mtool Tool Tutorial](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Mtool)|Suitable for translating RPGmaker MV/MZ games|
      |[GalTransl Tool Tutorial](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90GalTransl)|Suitable for translating Galgame|
      |[Wolf RPG Tool Tutorial](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90WolfRPG)|Suitable for translating Wolf RPG Editor games|
      |[StevExtraction Tool Tutorial](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90StevExtraction)|Suitable for translating RPGmakerMZ/MZ games|

</details>




</details>

---
<details>
<summary>
  
## Feature Description[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#feature-description)  
</summary>

<details>
<summary>

### Interface Management
</summary>

*   Configuration example:<br>
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/翻译设置/接口设置.png" width="600" height="400"><br>
  
    > `Model Selection`: Please understand the differences between models before making changes.<br>
  
    >`API KEY`: Enter the api_key generated by your OpenAI account<br>
  
    >`Base URL`: Enter the API request address, the default is OpenAI's official address<br>
  
    >`Proxy`: Optional, if you need to use a proxy to access the API<br>
  
    >`Organization`: Optional, for OpenAI's organization ID<br>
  
    >`Temperature`: Controls the randomness of the model's output, higher values make the output more random<br>
  
    >`Timeout`: API request timeout in seconds, increase if you experience timeout errors<br>

*  Custom Platform Configuration Example:
    > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/翻译设置/代理账号设置.png" width="600" height="400"><br> 
    
    > `Platform`: Select the AI platform you want to use<br>
  
    > `Model`: Select the model provided by the platform<br>
  
    > `API Key`: Enter the API key for the selected platform<br>
  
    > `Base URL`: Enter the API request address for the selected platform<br>
  
    > `Proxy`: Optional, if you need to use a proxy to access the API<br>
  
    > `Temperature`: Controls the randomness of the model's output<br>
  
    > `Timeout`: API request timeout in seconds<br>
  
    >`Tokens per minute`: TPM (tokens per minute) - total number of tokens sent to the model interface per minute (similar to total character count)



</details>
  



<details>
<summary> 

### Project Settings
</summary>

*   Configuration example:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/翻译设置/基础设置.png" width="600" height="400"><br>
    
    >`Project Type`: Type of original file to be translated<br>

    >`Interface Name`: Select the interface you configured earlier<br>

    >`Source Language`: Select the language of the original text<br>

    >`Target Language`: The language you want to translate to<br>

    >`Input Folder`: Place the original files in this folder<br>
  
    >`Output Folder`: Select a folder to store the translated files, please use a different path from the input folder<br>

</details>


<details>
<summary> 

### Prompt Settings
</summary>

*   Basic Prompts:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/基础提示词设置.png" width="600" height="400"><br>
    
    >`Basic Prompt`: Basic instructions for the AI, telling it how to translate<br>

    >`Background Setting`: Provide background information about the content to be translated<br>

    >`Role Introduction`: Define a specific role for the AI to assume during translation<br>

    >`Translation Style`: Specify the desired style of the translation<br>

    >`Translation Example`: Provide examples of good translations to guide the AI<br>

*   Advanced Settings:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/高级设置.png" width="600" height="400"><br>
    
    >`Translation Threads`: Number of simultaneous translation threads, increase for faster translation but higher API consumption<br>

    >`Context Window`: Number of previous translations to include as context for better consistency<br>

    >`Max Tokens`: Maximum number of tokens the AI can generate in a response<br>

    >`Retry Times`: Number of times to retry when API requests fail<br>

    >`Retry Interval`: Time to wait between retry attempts<br>

    >`Split Length`: Character length at which to split long texts for translation<br>

*   Plugin Settings:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/插件设置.png" width="600" height="400"><br>
    
    > Enable or disable various plugins to enhance the translation process:
    > - Bilingual Comparator: Creates side-by-side bilingual output
    > - Translation Function Checker: Verifies translation quality
    > - Text Filter: Filters out content that doesn't need translation
    > - Text Normalizer: Standardizes text formatting

</details>


<details>
<summary> 

### Text Replacement
</summary>

*   Pre-translation Replacement:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/译前替换.png" width="600" height="400"><br>
    
    > Replace specific text patterns before sending to the AI for translation

*   Post-translation Replacement:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/译后替换.png" width="600" height="400"><br>
    
    > Replace specific text patterns in the translated output

</details>


<details>
<summary> 

### Terminology Management
</summary>

*   Glossary:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/术语表.png" width="600" height="400"><br>
    
    > Define specific terms and their translations to ensure consistency

*   Do Not Translate List:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/禁翻表.png" width="600" height="400"><br>
    
    > Specify terms that should not be translated

</details>


<details>
<summary> 

### Workflow Design
</summary>

*   Gemini Translation:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/双子星翻译.png" width="600" height="400"><br>
    
    > Configure the advanced dual-request translation process for higher quality results

*   Workflow Settings:<br>

    ><img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/提示词设置/流程设计.png" width="600" height="400"><br>
    
    > Customize the translation workflow to suit specific needs

</details>


<details>
<summary> 

### Plugin Introduction
</summary>

* [Plugin - Bilingual Comparator](https://github.com/NEKOparapa/AiNiee/wiki/BilingualComparator)
* [Plugin - Translation Function Checker](https://github.com/NEKOparapa/AiNiee/wiki/TranslationFunctionChecker)
* [Plugin - Language Filter](https://github.com/NEKOparapa/AiNiee/wiki/LanguageFilter)
* [Plugin - Text Normalizer](https://github.com/NEKOparapa/AiNiee/wiki/TextNormalizer)
* [Plugin - MTool Optimizer](https://github.com/NEKOparapa/AiNiee/wiki/MToolOptimizer)
</details>





<details>
<summary> 

### Other Information
</summary>

* ` Multi-key Polling`
  >If you want to use multiple keys to share the consumption pressure and accelerate translation based on the number of keys, please use keys from the same type of account. When inputting, add an English comma between each key without line breaks. For example: key1,key2,key3

* ` Batch File Translation`
  >Simply place all files of the same type in the input folder. Multi-folder structures are also supported.

* ` Configuration Migration`
  >Configuration information is stored in the config.json file in the resource folder. When downloading a new version, you can copy it to the resource folder of the new version.
  
* `Cache Files`
   >When translation encounters problems, you can later change the translation project to cache files and select the folder containing the cache file in the input folder to continue translation. When continuing to translate Epub and Word files, you also need to place the original file and the cache file in the same folder.

* `Gemini Translation`
   >[Detailed introduction link](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8F%8C%E5%AD%90%E6%98%9F%E7%BF%BB%E8%AF%91%E4%BB%8B%E7%BB%8D) A translation process with a dual-request structure, a new tool for experts to explore AI possibilities.

</details>


</details>



---

<details>
<summary>

## Contribution Guidelines[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#contribution-guidelines)  
</summary>


* **`Develop Enhanced Plugins`**: Please follow the [Plugin Development Guide](https://github.com/NEKOparapa/AiNiee/blob/main/PluginScripts/README.md) to develop plugins with stronger functionality

* **`Improve or Add Supported Files`**: Requires some programming ability to pull the source code and make improvements. Specific file reading code is in the ModuleFolders\FileReader and FileOutputer folders. [Reader-Writer System Development Guide](https://github.com/NEKOparapa/AiNiee/blob/main/ModuleFolders/FileAccessor/README.md). UI support is in UserInterface\Setting\ProjectSettingsPage.

* **`Improve the Regex Library`**: A comprehensive regex library will greatly help with in-game embedding work and benefit future game translation work and other translation users. The regex library is in the [Resource\Regex](https://github.com/NEKOparapa/AiNiee/blob/main/Resource/Regex/regex.json) folder

* **`Improve the Translation Process`**: The [Translation Text Test Project](https://github.com/NEKOparapa/AiNiee-Test-Dataset) contains some data texts for common scenarios. You can improve the test data or improve the AiNiee translation process based on test data performance

* **`Improve Interface Translation`**: The UI text for multilingual interfaces may not be translated accurately or appropriately. You can submit your modification suggestions or make changes directly. Localization text is in the [Resource\Localization](https://github.com/NEKOparapa/AiNiee/tree/main/Resource/Localization) folder

</details>


---

## Special Statement[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#special-statement)   
AiNiee's continuous development and iteration to this day is due to ongoing personal research and development of key functional frameworks since the project's inception, user feedback and suggestions, and the joint efforts and creations of contributors through PRs.
This is a process of continuous exploration, improvement, and joint construction over two years, which has formed AiNiee's relatively mature and complete AI translation system today.
Please respect the open-source spirit while using and learning, attribute the source project, and don't forget to give the project a star.

This AI translation tool is for personal legal use only. Any direct or indirect illegal profit-making activities using this tool are not within the scope of authorization and are not supported or endorsed.

* **`Community Groups`**: TG Group: https://t.me/+JVHbDSGo8SI2Njhl

---



## Sponsorship💖
[![xxxx](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/徽章.png)](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/赞赏码.png)
