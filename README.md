<div align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png" width=60%>
  </a>
</div>


<div align="center">
  <a href="README_EN.md">English</a> | 简体中文
</div>

---


## 软件介绍🧾 

  
<div align="center">
<strong>AiNiee</strong> 是一款专注于 AI 翻译的工具，<br>一键自动翻译游戏、书籍、字幕、文档等复杂长文本内容。
</div>


* **格式全能，覆盖广泛**
    * 🎮 **游戏翻译**：深度支持 Mtool, Renpy, Translator++, ParaTranzr, VNText, SExtractor 等游戏文本导出工具。
    * 📚 **多样支持**：轻松处理 I18Next/.trans/Po/CSV 数据、Epub/TXT 电子书、Srt/Ass/Vtt/Lrc 字幕、Word/PDF/MD/PPT 文档等。

* **智能高效，省时省心**
    * 🚀 **一键操作**：一拖一点，自动识别文件与语言，无需设置。
    * ⏱️ **极速翻译**：喝杯可乐的工夫，就能拿到译文。

* **长文优化，质量出众**
    * 🎯 **突破局限**：采用轻盈翻译格式、思维链翻译、AI术语表、上下文关联等技术，确保长文本翻译的连贯性与准确性。
    * 💎 **质量追求**：支持 基础提示、角色介绍、背景设定、翻译风格 等提示词调整，拥有 一键AI润色、一键提取术语 等功能，满足对翻译质量有更高要求的用户。

* ✨ **项目推荐**
    * [**ReaDreamAI**](https://github.com/NEKOparapa/ReaDreamAI)（作者：NEKOparapa） - 阅你所想，绘你所梦，从一个想法到一本完整的精彩小说。ReaDreamAI为你包办写作、插图与视频。
    * [**AiNiee-Next**](https://github.com/ShadowLoveElysia/AiNiee-Next)（作者：ShadowLoveElysia） - 针对 AiNiee 核心逻辑进行工程化重构的命令行版本，引入 uv 与运行时稳定性优化，适合长时间挂机、服务器部署及自动化工作流。
    * [**ainiee-translate-skill**](https://github.com/xuanji86/ainiee-translate-skill)（作者：xuanji86） - 独立、Agent 原生的小说翻译系统（任意源 → 目标语言，不限中译）

---

## AiNiee三步走 📢

* **第一步：配置接口**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第一步.png">

  - 在线接口：需付费但性价比很高，无显卡要求，全语言支持，[接口设置说明 - DeepSeek](https://github.com/NEKOparapa/AiNiee/wiki/%E5%9C%A8%E7%BA%BF%E6%8E%A5%E5%8F%A3%E2%80%90Deepseek)


* **第二步：拖入文件夹**
  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第二步.png">
  
  - 输入文件夹：将原文文件单独放置新的文件夹，并将该文件夹拖入框内。小说、字幕、文档可直接进行翻译，游戏需要文本提取工具进行配合。<br>


* **第三步：开始翻译**

  > <img src="https://raw.githubusercontent.com/NEKOparapa/AiNiee/main/Example%20image/三步走/第三步.png">

  - 点击开始按钮，剩下等待任务的完成。

  - [AiNiee下载地址](https://github.com/dustheart25/AiNiee/releases)

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
      |[Translator++](https://dreamsavior.net/download/)|上手复杂，功能强大，推荐大佬使用|T++导出文件或Trans工程文件|
      |[ParaTranz](https://paratranz.cn/projects)|上手中等，功能强大，推荐大佬使用|ParaTranz导出文件|
      |[RenPy SDK](https://www.renpy.org/latest.html)|上手中等，功能强大，推荐大佬使用|renpy导出文件|

 * **`🧰本地模型运行工具`**

      |工具名|说明|
      |:----:|:-----:|
      |[Sakura_Launcher_GUI](https://github.com/PiDanShouRouZhouXD/Sakura_Launcher_GUI)|Sakura模型的专属GUI启动器|
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
      |[人名读取教程](https://www.bilibili.com/video/BV1j1VyzqERD/?share_source=copy_web&vd_source=b0eede35fc5eaa5c382509c6040d6501)|进阶翻译推荐观看|

 * **`🎫游戏翻译图文教程`**

      |文章链接|说明|
      |:----:|:-----:|
      |[Mtool教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Mtool) |适合新人，懒人翻译RPG,RenPY,Krkr等游戏，进行外挂式翻译|
      |[Translator++教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Translator--%EF%BC%88%E5%B7%A5%E7%A8%8B%E6%96%87%E4%BB%B6%E7%89%88%EF%BC%89)|适合翻译RPG,RenPY,Krkr等等游戏，进行内嵌式翻译|
      |[Paratranz教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90Paratranz)|适合翻译各类大型游戏的MOD|
      |[StevExtraction教程](https://github.com/NEKOparapa/AiNiee/wiki/%E6%B8%B8%E6%88%8F%E7%BF%BB%E8%AF%91%E2%80%90StevExtraction)|适合翻译RPGmakerMZ/MZ游戏|
      |[Unity翻译教程](https://zhuanlan.zhihu.com/p/1894065679927313655)|适合翻译unity游戏|
      |[综合游戏翻译超详细教程](https://www.notion.so/AI-1d43d31f89b280f6bd61e12580652ce5?pvs=4)|适合翻译各类游戏，制作高质量的内嵌补丁|

</details>


</details>

---

<details>
<summary>
  
## 功能说明[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#功能说明)  
</summary>



<details>
<summary>
  
### 设置说明
</summary>

- [功能 ‐ 接口管理](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8A%9F%E8%83%BD%E2%80%90%E6%8E%A5%E5%8F%A3%E7%AE%A1%E7%90%86)

</details>

  

<details>
<summary> 

### 表格说明
</summary>

- [表格 - AI术语表](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E6%9C%AF%E8%AF%AD%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [表格 - AI禁翻表](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E7%A6%81%E7%BF%BB%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [表格 - 文本替换](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90%E6%96%87%E6%9C%AC%E6%9B%BF%E6%8D%A2%E4%BB%8B%E7%BB%8D)
    
</details>


<details>
<summary> 

### 其他说明
</summary>

* ` 多key轮询`
  >如果想使用多个key来分担消耗压力，根据key数量进行加速翻译，请使用同类型账号的key，而且输入时在每个key中间加上英文逗号，不要换行。例如：key1,key2,key3

* ` 批量文件翻译`
  >把所有需要翻译的文件放在输入文件夹即可，也支持多文件夹结构

* ` 配置迁移`
  >配置信息都会存储在resource的config.json中，下载新版本可以把它复制到新版本的resource中。

</details>


</details>



---

<details>
<summary>

## 贡献指南[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#贡献指南)  
</summary>



* **`改进或增加支持文件`**: 需要有一定的代码编程能力，拉取源码进行改进。文件具体读取代码在ModuleFolders\FileReader与FileOutputer文件夹中。[读写器系统编写指南](https://github.com/NEKOparapa/AiNiee/blob/main/ModuleFolders/Domain/FileAccessor/README.md)。UI支持在UserInterface\Setting的ProjectSettingsPage。

* **`完善正则库`**: 正则库的完备将极大帮助游戏内嵌工作的进行，并利好下一次游戏翻译工作和造福其他翻译用户，正则库在[Resource\Regex](https://github.com/NEKOparapa/AiNiee/blob/main/Resource/Regex/regex.json)文件夹中

* **`改进界面翻译`**: 多语言界面的UI文本可能翻译不够准确合适，可以提交你的修改意见，或者直接进行修改。本地化文本在[Resource\Localization](https://github.com/NEKOparapa/AiNiee/tree/main/Resource/Localization)文件夹中

</details>


## 最近更新 🚀 (生物医药 IND 级文档翻译优化)
为了满足严格的生物医药 IND 申报法规资料（如递交 FDA）的翻译排版要求，本项目对 Word 和 PDF 读写引擎以及底层兼容性进行了全面升级优化：
1. **Word 智能合并 adjacent runs**：智能宽松合并具有相同关键样式（粗体、斜体、下划线、上下标）的相邻 runs，自动消除了 70.53% 由于中英文字体差异、语种标记差异引起的无意义切碎，大幅减少发给大模型的条目，降低 Token 消耗。
2. **段落级/表格单元格级标签化翻译**：将普通段落与表格单元格视为独立翻译单元，利用 `<t id="x">` 标签保护格式边界。确保翻译时能看到完整的上下文本，大模型能自动完成自适应语序调整，Word 原有复杂格式（如上标、下标、表格等）**100% 完好无损保留**。
3. **Word 标签防丢兜底重构**：若大模型翻译后的标签被破坏（匹配成功率低于 50%），自动采用正则降级退化（将纯文本合并写回第一个 run 并清空其余 run），保证数据完整性且绝不漏词。
4. **PDF 翻译标签自动剥离**：在 PDF 回写流程中，自动检测并正则剥离由于翻译缓存混用或大模型自行脑补产生的所有 `<t id="x">` 标签，避免 XML 标签作为纯文本印到 PDF 页面上。
5. **Python 3.10 兼容性与防闪退**：重构了高版本 Python 特有的 PEP 695 泛型声明语法和 `reprlib.Repr` 传参，完美兼容低版本 Python（如 3.10.11）本地运行。同时添加了 PDF 读写器（`BabeldocPdf`）可选依赖库缺失时的启动防闪退保护。
6. **目录导入失败 Bug 修复**：使用全版本通用的 `os.walk` 重构了目录遍历逻辑，彻底修复了 `pathlib.Path.walk()` 在 Python 3.10 本地环境下缺失导致导入文件夹时毫无反应的严重 Bug。

---

## 💡 推荐的生物医药/法规申报翻译提示词 (Recommended Prompts)

为了支持严谨的 FDA / IND 申报文档翻译，本项目推荐针对 Word 和 PDF 格式使用不同的翻译提示词，以达到最完美的排版效果：

### 1. Word (Docx) 专用翻译提示词 (含格式标签保护)
该提示词能够驱使大模型配合 Word 的标签保护技术，在保证上下标、加粗、斜体 100% 不丢失的基础上，完成专业医学和法规术语翻译：
*(下拉展开复制)*
<details>
<summary>👉 点击展开复制 Word 提示词</summary>

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

### 2. PDF 专用翻译提示词 (纯文本翻译 + 章节号层级强制还原)
该提示词能确保大模型以纯文本输出（防止脑补 HTML 标签），同时利用最高优先级的“绝对铁律”指令，强制将 PDF 版面提取时产生的 `【2】6.1.4` 或 `[2] 6.1.4` 等格式自动拼回并逆向还原为标准的四级章节号 `2.6.1.4`，防止大模型擅自简写或省略章节序号：
*(下拉展开复制)*
<details>
<summary>👉 点击展开复制 PDF 提示词</summary>

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

## 打包与本地开发说明 🧰

### 1. 本地运行
如果您需要在本地使用源码直接启动测试（要求 Python 3.10 及以上）：
1. 安装项目的主要依赖包：
   ```powershell
   pip install -r requirements.txt
   ```
2. 安装特定无依赖包（包括可选的 Babeldoc PDF OCR 支持，由于软件内置了防闪退容错，如因 `cv2.pyd` 被占用被拒也可以选择跳过）：
   ```powershell
   pip install -r requirements_no_deps.txt
   ```
3. 启动软件：
   ```powershell
   python AiNiee.py
   ```

### 2. 项目打包成 EXE
在 Windows 环境下，直接在项目根目录下执行以下打包命令即可生成精简压缩版（已排除庞大的 torch 库，包体积瘦身至 600MB 以内）：
```powershell
python Tools/pyinstall.py
```
打包成功后，可执行程序和其相关的依赖项将保存在 `dist/AiNiee/` 文件夹下，双击 `dist/AiNiee/AiNiee.exe` 即可独立运行。

---

## 特别声明[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#特别声明)   

该款AI翻译工具仅供个人合法用途,任何使用该工具进行直接或者间接非法盈利活动的行为,均不属于授权范围,也不受到任何支持和认可。

* 关于开发者 @neavo 合作说明: 在AiNiee v5.2版本，已退出AiNiee的开发工作。我们对他在此期间(2024-09至2025-02)，特别是在V5版本的UI改良美化所付出的努力表示非常感谢。[详细说明](https://github.com/NEKOparapa/AiNiee/releases/tag/AiNiee6.2.3)

* **`交♂交流群`**:  Q群(技术交流)：7296101五零，Q群(聊天吹水)：8216248九零，入群答案：github。备用TG群：https://t.me/+JVHbDSGo8SI2Njhl ,

---



## 赞助💖
[![xxxx](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/徽章.png)](https://raw.githubusercontent.com/NEKOparapa/AiNiee-chatgpt/main/Example%20image/Sponsor/赞赏码.png)

