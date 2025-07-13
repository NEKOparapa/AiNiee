<div align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png" width=60% >
  </a>
</div>


---


## Introduction🧾 

  
<div align="center">
<strong>AiNiee</strong> is a tool specializing in AI translation,<br>enabling one-click automatic translation of complex long-text content such as games, books, subtitles, and documents.
</div>

*   **All-in-One Format Support, Broad Coverage**
    *   🎮 **Game Translation**: In-depth support for game text export tools like Mtool, Renpy, Translator++, ParaTranzr, VNText, and SExtractor.
    *   📚 **Diverse Support**: Effortlessly processes I18Next data, Epub/TXT e-books, Srt/Vtt/Lrc subtitles, Word/PDF/MD documents, and more.

*   **Smart & Efficient, Saves Time & Effort**
    *   🚀 **One-Click Operation**: Simply drag and drop; automatically identifies files and languages, no setup required.
    *   ⏱️ **Rapid Translation**: Get your translated text in the time it takes to enjoy a cup of tea.

*   **Optimized for Long Texts, Exceptional Quality**
    *   🎯 **Overcoming Limitations**: Employs techniques like streamlined translation formats, chain-of-thought translation, AI glossaries, and contextual awareness to ensure coherence and accuracy in long-text translations.

    *   💎 **Quality Focus**: Supports prompt adjustments for basic instructions, character introductions, background settings, translation styles, etc. Equipped with features such as one-click AI refinement, one-click AI formatting, and AI terminology extraction, it caters to users who demand higher translation quality.

---

## Three Steps to Use AiNiee 📢

* **Step 1: Configure Interface**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/Step1.png">

  - Online Interface: Paid but cost-effective, no GPU requirements, full language support, [Interface Setup Guide - DeepSeek](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartDeepSeek)
  - Online Interface: Same as above, if DeepSeek official website is not accessible, you can use this alternative, [Interface Setup Guide - Volcano Engine](https://github.com/NEKOparapa/AiNiee/wiki/QuickStartHuo)
  
* **Step 2: Drag into the folder**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/Step2.png">

  - Target Language: In the translation settings, change the target language to the one you need.<br>

  - Input Folder: Place the original files in this folder; novels, subtitles, documents can be translated directly, games require text extraction tools<br>

* **Step 3: Start Translation**

  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/Step3.png">

  - Click the start button and wait for the task to complete.

  - [AiNiee Download Link](https://github.com/NEKOparapa/AiNiee/releases)

---

<details>
<summary>

## Feature Description[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#feature-description)
</summary>



<details>
<summary>

### Settings Description
</summary>

- [Feature - API Management](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8A%9F%E8%83%BD%E2%80%90%E6%8E%A5%E5%8F%A3%E7%AE%A1%E7%90%86)
- [Feature - Gemini Translation](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8F%8C%E5%AD%90%E6%98%9F%E7%BF%BB%E8%AF%91%E4%BB%8B%E7%BB%8D)

</details>



<details>
<summary>

### Table Description
</summary>

- [Table - AI Glossary](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E6%9C%AF%E8%AF%AD%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [Table - AI Do Not Translate List](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E7%A6%81%E7%BF%BB%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [Table - Text Replacement](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90%E6%96%87%E6%9C%AC%E6%9B%BF%E6%8D%A2%E4%BB%8B%E7%BB%8D)

</details>




<details>
<summary>

### Plugin Description
</summary>

- [Plugin - Language Filter](https://github.com/NEKOparapa/AiNiee/wiki/%E6%8F%92%E4%BB%B6%E2%80%90LanguageFilter)
- [Plugin - Text Normalizer](https://github.com/NEKOparapa/AiNiee/wiki/%E6%8F%92%E4%BB%B6%E2%80%90TextNormalizer)

</details>



<details>
<summary>

### Other Notes
</summary>

* `Multiple Key Rotation`
  > If you want to use multiple keys to distribute the load and speed up translation based on the number of keys, please use keys from the same account type. When inputting, add an English comma between each key, without line breaks. For example: key1,key2,key3

* `Batch File Translation`
  > Simply place all files that need translation into the input folder. It also supports multi-folder structures.

* `Configuration Migration`
  > Configuration information is stored in `resource/config.json`. When you download a new version, you can copy this file to the `resource` folder of the new version.

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
