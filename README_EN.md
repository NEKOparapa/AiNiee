<div align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png" width=60% >
  </a>
</div>


<div align="center">
  
![GitHub stars](https://img.shields.io/github/stars/NEKOparapa/AiNiee?style=flat)  
![GitHub all releases downloads](https://img.shields.io/github/downloads/NEKOparapa/AiNiee/total?style=flat&color=orange)  
![Yesterday Activity](https://img.shields.io/endpoint?url=https://ai-niee-vercel.vercel.app/api/stats%3Ftype%3Dyesterday) 
![Average Activity](https://img.shields.io/endpoint?url=https://ai-niee-vercel.vercel.app/api/stats%3Ftype%3Daverage)

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

    *   💎 **Quality Focus**: Supports prompt adjustments for basic instructions, character introductions, background settings, translation styles, extraction prompts, etc. Equipped with features such as one-click AI refinement, one-click AI formatting, and AI terminology extraction, it caters to users who demand higher translation quality.

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

  - [AiNiee Download Link](https://github.com/dustheart25/AiNiee/releases)

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



* **`Improve or Add Supported Files`**: Requires some programming ability to pull the source code and make improvements. Specific file reading code is in the ModuleFolders\FileReader and FileOutputer folders. [Reader-Writer System Development Guide](https://github.com/NEKOparapa/AiNiee/blob/main/ModuleFolders/FileAccessor/README.md). UI support is in UserInterface\Setting\ProjectSettingsPage.

* **`Improve the Regex Library`**: A comprehensive regex library will greatly help with in-game embedding work and benefit future game translation work and other translation users. The regex library is in the [Resource\Regex](https://github.com/NEKOparapa/AiNiee/blob/main/Resource/Regex/regex.json) folder

* **`Improve Interface Translation`**: The UI text for multilingual interfaces may not be translated accurately or appropriately. You can submit your modification suggestions or make changes directly. Localization text is in the [Resource\Localization](https://github.com/NEKOparapa/AiNiee/tree/main/Resource/Localization) folder

</details>


---

## Recent Updates 🚀 (Pharmaceutical IND Document Translation Optimization)
To meet the strict translation and typesetting requirements of pharmaceutical IND regulatory submissions (e.g., to the US FDA), this project has comprehensively upgraded and optimized the Word and PDF read/write engines and underlying compatibility:
1. **Word Smart Merging of Adjacent Runs**: Intelligently and loosely merges adjacent runs with identical key styles (bold, italic, underline, superscript, subscript), automatically eliminating 70.53% of meaningless slicing caused by Chinese/English font differences and language tag differences, significantly reducing segments sent to LLM and saving Token consumption.
2. **Paragraph/Table Cell-level Tagged Translation**: Treats normal paragraphs and table cells as independent translation units, protecting formatting boundaries with `<t id="x">` tags. This ensures that the LLM sees the complete context for adaptive word order adjustments, while **100% preserving** complex formatting (superscripts, subscripts, tables, etc.).
3. **Word Tag Protection Fallback**: If the LLM breaks the tags in the translated response (matching success rate below 50%), a regex fallback is automatically used (merging plain text back into the first run and clearing the rest), ensuring data integrity and preventing any text loss.
4. **PDF Translation Tag Stripping**: Automatically detects and strips `<t id="x">` tags in the PDF write-back process to prevent residual XML tags from being rendered onto the PDF page.
5. **Python 3.10 Compatibility & Crash Prevention**: Refactored PEP 695 generic declaration syntax and `reprlib.Repr` parameters to make the project fully compatible with Python 3.10.11. Added crash prevention fallback when optional libraries for the PDF Reader (`BabeldocPdf`) are missing.
6. **Directory Import Failure Fix**: Restructured the directory traversal logic using `os.walk` to completely resolve the issue where `pathlib.Path.walk()` is unavailable in Python 3.10, fixing the bug where dragging in a directory has no response.

---

## 💡 Recommended Pharmaceutical / Regulatory Submissions Translation Prompts

For rigorous FDA / IND regulatory document translation, it is recommended to use different prompts for Word and PDF formats to achieve the best typesetting results:

### 1. Word (Docx) Dedicated Prompt (with Tag Protection)
This prompt guides the LLM to work with Word's tag protection technology to complete professional medical and regulatory terminology translation while ensuring 100% preservation of formatting:
*(Expand below to copy)*
<details>
<summary>👉 Click to expand and copy Word Prompt</summary>

```markdown
你是一名专业的生物医药与法规注册翻译家，专门从事向美国 FDA 递交的 IND（新药临床试验申请）申报资料的翻译工作。请你按照以下流程，将 {source_language} 文本翻译为 {target_language}（通常为专业学术英语）：

### 翻译三步走流程

第一步：初步直译（含标签保护）
    将含有 `<t id="x">...</t>` 标签的文本进行直译。
    你必须【绝对原样保留】所有标签结构及其 id 属性，严禁擅自修改或删除任何标签，也严禁自行创建新标签。将翻译后的文本精准写在对应的标签内。
    保留标签内的所有科学参数（如 EC50, Cmax, AUC0-t）、化学式、数字、单位及参考文献引用（如 [1,2]），不要对其进行修改或英文拼写拆分。

第二步：专业法规校正
    结合 FDA Guidance（指南）和 ICH 规范，对第一步的译文进行医学与法规术语层面的严格分析与校正：
    1. 确保药理、毒理、药代动力学及临床术语高度符合国际公认规范（例如：“受试者”译为 subjects，“给药”译为 administration/dosing，“不良事件”译为 adverse events，“耐受性”译为 tolerability ）。
    2. 确保专业名词与缩写在上下文中的译法高度一致。

第三步：学术意译与法规润色
    整合初步直译和专业校正意见，生成最终的学术译文。
    行文风格必须保持【极其客观、中立、科学严谨且符合法规审查习惯】，语法应自然流畅、符合美式专业医药学术表达。

### 翻译原则
1. 【忠实与科学中立】：行文必须严谨、客观，绝对不带有任何个人感情色彩或艺术性夸张。
2. 【语序自适应】：你可以根据英文的语法和语序调换不同 ID 标签在句子中的物理位置，但【标签数量必须与原文严格一致】，严禁漏掉任何标签。
3. 【标签粘连防护】：标签在拼接时，请注意根据英文书写习惯在标签间保留必要的空格，以防单词粘连。

### 以 textarea 标签输出最终译文（必须包含标签）：
<textarea>
{target_language}文本（必须保留完整的 <t id="x">...</t> 结构）
</textarea>
```
</details>

### 2. PDF Dedicated Prompt (Plain Text Translation + Mandatory Section Number Level Reconstruction)
This prompt ensures that the LLM outputs plain text (avoiding XML/HTML tags) and enforces the "critical rule" to reconstruct section numbers like `【2】6.1.4` back to standard `2.6.1.4`, preventing omission or truncation by the model:
*(Expand below to copy)*
<details>
<summary>👉 Click to expand and copy PDF Prompt</summary>

```markdown
你是一名专业的生物医药与法规注册翻译家，专门从事向美国 FDA 递交的 IND（新药临床试验申请）申报资料的翻译工作。请你把 {source_language} 文本翻译为 {target_language}（通常为专业学术英语）：

[CRITICAL RULE / 绝对必须无条件遵守的铁律]
1. 章节号完整性保护：你必须【无条件且原样保留】输入文本中的所有章节号和数字层级序列，严禁进行任何形式的缩写、省略、截断或数字删减！例如：如果输入为 `【2】6.1.4`，你必须在最终译文中将其严格拼写并还原为完整的四级章节号 `2.6.1.4`，严禁将其缩写为单独的 `4` 或 `4.`，也严禁保留任何中括号标记。
2. 行号与译文空格分界：在大模型的多行译文中，【每行的行号点号后面必须强制保留一个空格，行号和章节号之间严禁粘连】。例如，对于第 8 行，你必须输出为 `8. 2.6.1.4 Proposed...`（注意：行号 8. 与章节号 2.6.1.4 之间必须留有空格），严禁写成 `8.2.6.1.4`，否则系统提取会出错。

### 翻译三步走流程

第一步：初步直译
    将输入的 {source_language} 文本进行直译。
    保留文本中所有的科学参数（如 EC50, Cmax, AUC0-t）、化学式、数字、单位及参考文献引用（如 [1,2]），不要对其进行修改或英文拼写拆分。

第二步：专业法规校正
    结合 FDA Guidance（指南）和 ICH 规范，对第一步的译文进行医学与法规术语层面的严格分析与校正：
    1. 确保药理、毒理、药代动力学及临床术语高度符合国际公认规范（例如：“受试者”译为 subjects，“给药”译为 administration/dosing，“不良事件”译为 adverse events，“耐受性”译为 tolerability ）。
    2. 确保专业名词与缩写在上下文中的译法高度一致。

第三步：学术意译与法规润色
    整合初步直译 and 专业校正意见，生成最终的学术译文。
    行文风格必须保持【极其客观、中立、科学严谨且符合法规审查习惯】，语法应自然流畅、符合美式专业医药学术表达。

### 翻译原则
1. 【忠实与科学中立】：行文必须严谨、客观，绝对不带有任何个人感情色彩或艺术性夸张。
2. 【纯文本译文】：输入的文本不含有任何格式标签，翻译出来的英文也必须是纯净文本。严禁自行生成、模仿或拼造诸如 `<t id="x">` 等任何 XML/HTML 标签。

### 以 textarea 标签输出最终译文：
<textarea>
{target_language}文本
</textarea>
```
</details>

---

## Special Statement[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#special-statement)   
AiNiee's continuous development and iteration to this day is due to ongoing personal research and development of key functional frameworks since the project's inception, user feedback and suggestions, and the joint efforts and creations of contributors through PRs.
This is a process of continuous exploration, improvement, and joint construction over two years, which has formed AiNiee's relatively mature and complete AI translation system today.
Please respect the open-source spirit while using and learning, attribute the source project, and don't forget to give the project a star.

This AI translation tool is for personal legal use only. Any direct or indirect illegal profit-making activities using this tool are not within the scope of authorization and are not supported or endorsed.

* **`Community Groups`**: TG Group: https://t.me/+JVHbDSGo8SI2Njhl

---
