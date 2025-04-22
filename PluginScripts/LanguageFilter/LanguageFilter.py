import langcodes
from tqdm import tqdm
from rich import print

from PluginScripts.PluginBase import PluginBase
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig


pair_en = {
    "japanese": "Japanese",
    "english": "English",
    "korean": "Korean",
    "russian": "Russian",
    "chinese_simplified": "Simplified Chinese",
    "chinese_traditional": "Traditional Chinese",
    "french": "French",
    "german": "German",
    "spanish": "Spanish",
}

pair = {
    "japanese": "日语",
    "english": "英语",
    "korean": "韩语",
    "russian": "俄语",
    "chinese_simplified": "简体中文",
    "chinese_traditional": "繁体中文",
    "french": "法语",
    "german": "德语",
    "spanish": "西班牙语",
}


def map_language_code_to_name(language_code: str) -> str:
    """将语言代码映射到语言名称"""
    mapping = {
        "zh": "chinese_simplified",
        "zh-cn": "chinese_simplified",
        "zh-tw": "chinese_traditional",
        "yue": "chinese_traditional",
        "en": "english",
        "es": "spanish",
        "fr": "french",
        "de": "german",
        "ko": "korean",
        "ru": "russian",
        "ja": "japanese"
    }
    return mapping.get(language_code, language_code)


def get_language_display_names(source_lang, target_lang):
    """
    获取源语言和目标语言的显示名称

    Args:
        source_lang: 源语言代码
        target_lang: 目标语言代码

    Returns:
        tuple: ((英文源语言名, 中文源语言名), (英文目标语言名, 中文目标语言名))
    """
    # 处理源语言
    langcodes_lang = langcodes.Language.get(source_lang)
    if langcodes_lang:
        en_source_lang = langcodes_lang.display_name()
        source_language = langcodes_lang.display_name('zh-Hans')
    else:
        # 处理特殊情况
        if source_lang == 'un':
            en_source_lang = 'UnspecifiedLanguage'
            source_language = '未指定的语言'
        elif source_lang == 'auto':
            en_source_lang = 'Auto Detect'
            source_language = '自动检测'
        else:
            en_source_lang = pair_en[source_lang]
            source_language = pair[source_lang]

    # 处理目标语言
    en_target_language = pair_en[target_lang]
    target_language = pair[target_lang]

    return en_source_lang, source_language, en_target_language, target_language


def get_most_common_language(file_props: dict) -> str:
    """
    计算项目中出现次数最多的语言

    Args:
        file_props: 项目中所有文件的属性字典

    Returns:
        出现次数最多的语言代码
    """
    # 语言计数字典
    language_counts = {}

    # 遍历所有文件的语言统计信息
    for path, props in file_props.items():
        if "language_stats" in props and props["language_stats"]:
            for lang_stat in props["language_stats"]:
                if len(lang_stat) >= 2 and lang_stat[0] != 'un':  # 跳过未知语言
                    lang_code = lang_stat[0]
                    count = lang_stat[1] if len(lang_stat) > 1 else 1

                    if lang_code in language_counts:
                        language_counts[lang_code] += count
                    else:
                        language_counts[lang_code] = count

    # 如果没有找到任何语言，返回未知语言作为默认值
    if not language_counts:
        print(
            f"[[red]WARNING[/]] [LanguageFilter] 当前项目没有检测到主要语言信息"
        )
        return "un"

    # 找出出现次数最多的语言
    most_common_lang = max(language_counts.items(), key=lambda x: x[1])[0]

    return most_common_lang


class LanguageFilter(PluginBase):

    # 平假名
    HIRAGANA = ("\u3040", "\u309F")

    # 片假名
    KATAKANA = ("\u30A0", "\u30FF")

    # 半角片假名（包括半角浊音、半角拗音等）
    KATAKANA_HALF_WIDTH = ("\uFF65", "\uFF9F")

    # 片假名语音扩展
    KATAKANA_PHONETIC_EXTENSIONS = ("\u31F0", "\u31FF")

    # 濁音和半浊音符号
    VOICED_SOUND_MARKS = ("\u309B", "\u309C")

    # 韩文字母 (Hangul Jamo)
    HANGUL_JAMO = ("\u1100", "\u11FF")

    # 韩文字母扩展-A (Hangul Jamo Extended-A)
    HANGUL_JAMO_EXTENDED_A = ("\uA960", "\uA97F")

    # 韩文字母扩展-B (Hangul Jamo Extended-B)
    HANGUL_JAMO_EXTENDED_B = ("\uD7B0", "\uD7FF")

    # 韩文音节块 (Hangul Syllables)
    HANGUL_SYLLABLES = ("\uAC00", "\uD7AF")

    # 韩文兼容字母 (Hangul Compatibility Jamo)
    HANGUL_COMPATIBILITY_JAMO = ("\u3130", "\u318F")

    # 中日韩统一表意文字
    CJK = ("\u4E00", "\u9FFF")

    # 中日韩通用标点符号
    GENERAL_PUNCTUATION = ("\u2000", "\u206F")
    CJK_SYMBOLS_AND_PUNCTUATION = ("\u3000", "\u303F")
    HALFWIDTH_AND_FULLWIDTH_FORMS = ("\uFF00", "\uFFEF")
    OTHER_CJK_PUNCTUATION = (
        "\u30FB"    # ・ 在片假名 ["\u30A0", "\u30FF"] 范围内
    )

    # 拉丁字符
    LATIN_1 = ("\u0041", "\u005A") # 大写字母 A-Z
    LATIN_2 = ("\u0061", "\u007A") # 小写字母 a-z
    LATIN_EXTENDED_A = ("\u0100", "\u017F")
    LATIN_EXTENDED_B = ("\u0180", "\u024F")
    LATIN_SUPPLEMENTAL = ("\u00A0", "\u00FF")

    # 拉丁标点符号
    LATIN_PUNCTUATION_BASIC_1 = ("\u0020", "\u002F")
    LATIN_PUNCTUATION_BASIC_2 = ("\u003A", "\u0040")
    LATIN_PUNCTUATION_BASIC_3 = ("\u005B", "\u0060")
    LATIN_PUNCTUATION_BASIC_4 = ("\u007B", "\u007E")
    LATIN_PUNCTUATION_GENERAL = ("\u2000", "\u206F")
    LATIN_PUNCTUATION_SUPPLEMENTAL = ("\u2E00", "\u2E7F")

    # 俄文字符
    CYRILLIC_BASIC = ("\u0410", "\u044F")               # 基本俄文字母 (大写字母 А-Я, 小写字母 а-я)
    CYRILLIC_SUPPLEMENT = ("\u0500", "\u052F")          # 俄文字符扩展区（补充字符，包括一些历史字母和其他斯拉夫语言字符）
    CYRILLIC_EXTENDED_A = ("\u2C00", "\u2C5F")          # 扩展字符 A 区块（历史字母和一些东斯拉夫语言字符）
    CYRILLIC_EXTENDED_B = ("\u0300", "\u04FF")          # 扩展字符 B 区块（更多历史字母）
    CYRILLIC_SUPPLEMENTAL = ("\u1C80", "\u1C8F")        # 俄文字符补充字符集，包括一些少见和历史字符
    CYRILLIC_SUPPLEMENTAL_EXTRA = ("\u2DE0", "\u2DFF")  # 其他扩展字符（例如：斯拉夫语言的一些符号）
    CYRILLIC_OTHER = ("\u0500", "\u050F")               # 其他字符区块（包括斯拉夫语系其他语言的字符，甚至一些特殊符号）

    def __init__(self) -> None:
        super().__init__()

        self.name = "LanguageFilter"
        self.description = (
            "语言过滤器，在翻译开始前，根据原文语言对文本中的无效条目进行过滤以节约 翻译时间 与 Token 消耗"
            + "\n"
            + "兼容性：支持全部语言；支持全部模型；支持全部文本格式；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = True      # 默认启用状态

        self.add_event("text_filter", PluginBase.PRIORITY.NORMAL)

    def on_event(self, event: str, config: TranslatorConfig, data: list[dict]) -> None:
        # 检查数据有效性
        if not isinstance(data, list) or len(data) < 2:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        if event == "text_filter":
            self.on_text_filter(event, config, data, items, project)

    # 文本后处理事件
    def on_text_filter(self, event: str, config: TranslatorConfig, data: list[dict], items: list[dict], project: dict) -> None:
        print("")
        print("[LanguageFilter] 开始执行预处理 ...")
        print("")

        target = []  # 存储需要排除的条目

        # 自动检测语言模式
        if config.source_language == "auto":
            print("[LanguageFilter] 使用自动检测语言模式...")

            # 获取项目中存储的语言信息
            file_props = project.get("file_props", {})

            # 按文件路径分组
            items_by_path = {}
            for item in items:
                path = str(item.get("storage_path", ""))
                if path not in items_by_path:
                    items_by_path[path] = []
                items_by_path[path].append(item)

            # 计算项目中出现次数最多的语言
            most_common_language = get_most_common_language(file_props)
            # 获取可读更强的名称
            en_source_lang, source_language, _, _ = get_language_display_names(most_common_language, 'chinese_simplified')
            print(f"[LanguageFilter] 项目主要语言: "
                  f"{most_common_language} - {en_source_lang}/{source_language}")
            print("")

            # 处理每个文件中的条目
            for path, file_items in items_by_path.items():
                # 获取当前文件检测到的语言统计信息
                language_stats = []
                if path in file_props and "language_stats" in file_props[path]:
                    language_stats = file_props[path]["language_stats"]

                # 如果没有检测到语言，使用项目中最常见的语言
                if not language_stats:
                    print(f"[[red]WARNING[/]] [LanguageFilter] 文件 {path} 没有检测到语言信息，使用项目主要语言 {most_common_language}")
                    first_language = most_common_language
                    second_language = None
                else:
                    # 获取检测到的第一个语言
                    first_language = language_stats[0][0]
                    # 检测到的第二个语言（如果有的话）
                    second_language = language_stats[1][0] if len(language_stats) > 1 else None

                # 决定使用哪种语言进行过滤
                filter_language = first_language

                # 如果第一个检测到的语言与目标语言相同
                if map_language_code_to_name(first_language) == config.target_language:
                    # 如果没有第二个语言，文件主要是目标语言
                    # 我们需要反转过滤逻辑，使用相反的条件：保留那些不符合目标语言特征的文本
                    print(
                        f"[LanguageFilter] 文件 {path} 检测到的主要语言 {first_language} 与目标语言相同，"
                        f"将只翻译不符合该语言特征的文本"
                    )

                    # 这种情况需要特殊处理，标记所有文本为排除，除非它不包含目标语言的字符
                    has_any = self.get_filter_function(first_language, path)
                    if has_any is not None:
                        # 找出那些包含目标语言字符的文本，将它们标记为排除
                        for item in file_items:
                            text = item.get("source_text", "")
                            if isinstance(text, str) and has_any(text):
                                target.append(item)

                    # 跳过后续处理，因为我们已经直接处理了所有条目
                    continue
                # else:
                #     # 检测到的语言与目标语言不同，使用检测到的第一语言
                #     print(f"[LanguageFilter] 文件 {path} 使用检测到的语言 {filter_language} 过滤")

                # 如果文件检测到的语言未知，则过滤该文件内置信度较低的行
                if first_language == 'un':
                    print(f"[LanguageFilter] 文件 {path} 未检测到具体语言，将只翻译置信度较高的文本行")

                    # 寻找置信度低于0.6的文本行
                    for item in file_items:
                        text: str = item.get("source_text", "")
                        # 获取置信度分数
                        lang_score: float = item.get("lang_code", ["un", 1.0])[1]
                        if not isinstance(text, str) or lang_score < 0.6:
                            target.append(item)

                    # 跳过后续处理，因为我们已经直接处理了所有条目
                    continue

                # 设置过滤函数
                has_any = self.get_filter_function(filter_language, path)

                if has_any is not None:
                    # 筛选出无效条目
                    filtered_items = [
                        item for item in file_items
                        if not isinstance(item.get("source_text", ""), str) or not has_any(item.get("source_text", ""))
                    ]

                    target.extend(filtered_items)
        else:
            # 原有的非自动检测模式
            has_any = None
            if config.source_language in ("chinese_simplified", "chinese_traditional"):
                has_any = self.has_any_cjk
            elif config.source_language in ("english", "spanish", "french", "german"):
                has_any = self.has_any_latin
            elif config.source_language == "korean":
                has_any = self.has_any_korean
            elif config.source_language == "russian":
                has_any = self.has_any_russian
            elif config.source_language == "japanese":
                has_any = self.has_any_japanese

            # 筛选出无效条目并标记为已排除
            if has_any is not None:
                target = [
                    v for v in items
                    if not isinstance(v.get("source_text", ""), str) or not has_any(v.get("source_text", ""))
                ]

        for item in tqdm(target):
            item["translation_status"] = CacheItem.STATUS.EXCLUED

        # 输出结果
        print("")
        print(f"[LanguageFilter] 语言过滤已完成，共过滤 {len(target)} 个不包含目标语言的条目 ...")
        print("")

    def get_filter_function(self, language_code: str, path: str):
        """根据语言代码获取相应的语言过滤函数"""
        # 语言代码到过滤函数的映射
        code_to_function = {
            # 中文
            'zh': self.has_any_cjk,
            'zh-cn': self.has_any_cjk,
            'zh-tw': self.has_any_cjk,
            'yue': self.has_any_cjk,
            # 英语和拉丁语系
            'en': self.has_any_latin,
            'es': self.has_any_latin,
            'fr': self.has_any_latin,
            'de': self.has_any_latin,
            # 韩语
            'ko': self.has_any_korean,
            # 俄语
            'ru': self.has_any_russian,
            # 日语
            'ja': self.has_any_japanese
        }

        # 尝试直接匹配
        if language_code in code_to_function:
            return code_to_function[language_code]

        # 尝试匹配前两个字符
        if language_code and language_code[:2] in code_to_function:
            return code_to_function[language_code[:2]]

        # 未知语言默认使用拉丁文过滤函数
        print(f"[[red]WARNING[/]] [LanguageFilter] 文件 {path} 未知的语言代码 {language_code}，使用默认的拉丁文过滤函数")
        return self.has_any_latin

    # 判断字符是否为汉字（中文）字符
    def is_cjk(self, char: str) -> bool:
        return LanguageFilter.CJK[0] <= char <= LanguageFilter.CJK[1]

    # 判断字符是否为拉丁字符
    def is_latin(self, char: str) -> bool:
        return (
            LanguageFilter.LATIN_1[0] <= char <= LanguageFilter.LATIN_1[1]
            or LanguageFilter.LATIN_2[0] <= char <= LanguageFilter.LATIN_2[1]
            or LanguageFilter.LATIN_EXTENDED_A[0] <= char <= LanguageFilter.LATIN_EXTENDED_A[1]
            or LanguageFilter.LATIN_EXTENDED_B[0] <= char <= LanguageFilter.LATIN_EXTENDED_B[1]
            or LanguageFilter.LATIN_SUPPLEMENTAL[0] <= char <= LanguageFilter.LATIN_SUPPLEMENTAL[1]
        )

    # 判断字符是否为韩文（含汉字）字符
    def is_korean(self, char: str) -> bool:
        return (
            LanguageFilter.CJK[0] <= char <= LanguageFilter.CJK[1]
            or LanguageFilter.HANGUL_JAMO[0] <= char <= LanguageFilter.HANGUL_JAMO[1]
            or LanguageFilter.HANGUL_JAMO_EXTENDED_A[0] <= char <= LanguageFilter.HANGUL_JAMO_EXTENDED_A[1]
            or LanguageFilter.HANGUL_JAMO_EXTENDED_B[0] <= char <= LanguageFilter.HANGUL_JAMO_EXTENDED_B[1]
            or LanguageFilter.HANGUL_SYLLABLES[0] <= char <= LanguageFilter.HANGUL_SYLLABLES[1]
            or LanguageFilter.HANGUL_COMPATIBILITY_JAMO[0] <= char <= LanguageFilter.HANGUL_COMPATIBILITY_JAMO[1]
        )

    # 判断字符是否为俄文字符
    def is_russian(self, char: str) -> bool:
        return (
            LanguageFilter.CYRILLIC_BASIC[0] <= char <= LanguageFilter.CYRILLIC_BASIC[1]
            or LanguageFilter.CYRILLIC_SUPPLEMENT[0] <= char <= LanguageFilter.CYRILLIC_SUPPLEMENT[1]
            or LanguageFilter.CYRILLIC_EXTENDED_A[0] <= char <= LanguageFilter.CYRILLIC_EXTENDED_A[1]
            or LanguageFilter.CYRILLIC_EXTENDED_B[0] <= char <= LanguageFilter.CYRILLIC_EXTENDED_B[1]
            or LanguageFilter.CYRILLIC_SUPPLEMENTAL[0] <= char <= LanguageFilter.CYRILLIC_SUPPLEMENTAL[1]
            or LanguageFilter.CYRILLIC_SUPPLEMENTAL_EXTRA[0] <= char <= LanguageFilter.CYRILLIC_SUPPLEMENTAL_EXTRA[1]
            or LanguageFilter.CYRILLIC_OTHER[0] <= char <= LanguageFilter.CYRILLIC_OTHER[1]
        )

    # 判断字符是否为日文（含汉字）字符
    def is_japanese(self, char: str) -> bool:
        return (
            LanguageFilter.CJK[0] <= char <= LanguageFilter.CJK[1]
            or LanguageFilter.KATAKANA[0] <= char <= LanguageFilter.KATAKANA[1]
            or LanguageFilter.HIRAGANA[0] <= char <= LanguageFilter.HIRAGANA[1]
            or LanguageFilter.KATAKANA_HALF_WIDTH[0] <= char <= LanguageFilter.KATAKANA_HALF_WIDTH[1]
            or LanguageFilter.KATAKANA_PHONETIC_EXTENSIONS[0] <= char <= LanguageFilter.KATAKANA_PHONETIC_EXTENSIONS[1]
            or LanguageFilter.VOICED_SOUND_MARKS[0] <= char <= LanguageFilter.VOICED_SOUND_MARKS[1]
        )

    # 检查字符串是否包含至少一个汉字（中文）字符
    def has_any_cjk(self, text: str) -> bool:
        return any(self.is_cjk(char) for char in text)

    # 检查字符串是否包含至少一个拉丁字符
    def has_any_latin(self, text: str) -> bool:
        return any(self.is_latin(char) for char in text)

    # 检查字符串是否包含至少一个韩文（含汉字）字符
    def has_any_korean(self, text: str) -> bool:
        return any(self.is_korean(char) for char in text)

    # 检查字符串是否包含至少一个俄文字符
    def has_any_russian(self, text: str) -> bool:
        return any(self.is_russian(char) for char in text)

    # 检查字符串是否包含至少一个日文（含汉字）字符
    def has_any_japanese(self, text: str) -> bool:
        return any(self.is_japanese(char) for char in text)