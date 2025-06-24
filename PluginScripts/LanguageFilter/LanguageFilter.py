from tqdm import tqdm
from rich import print

from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.TaskExecutor import TranslatorUtil
from PluginScripts.PluginBase import PluginBase
from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig


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
        "\u30FB"  # ・ 在片假名 ["\u30A0", "\u30FF"] 范围内
    )

    # 拉丁字符
    LATIN_1 = ("\u0041", "\u005A")  # 大写字母 A-Z
    LATIN_2 = ("\u0061", "\u007A")  # 小写字母 a-z
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
    CYRILLIC_BASIC = ("\u0410", "\u044F")  # 基本俄文字母 (大写字母 А-Я, 小写字母 а-я)
    CYRILLIC_SUPPLEMENT = ("\u0500", "\u052F")  # 俄文字符扩展区（补充字符，包括一些历史字母和其他斯拉夫语言字符）
    CYRILLIC_EXTENDED_A = ("\u2C00", "\u2C5F")  # 扩展字符 A 区块（历史字母和一些东斯拉夫语言字符）
    CYRILLIC_EXTENDED_B = ("\u0300", "\u04FF")  # 扩展字符 B 区块（更多历史字母）
    CYRILLIC_SUPPLEMENTAL = ("\u1C80", "\u1C8F")  # 俄文字符补充字符集，包括一些少见和历史字符
    CYRILLIC_SUPPLEMENTAL_EXTRA = ("\u2DE0", "\u2DFF")  # 其他扩展字符（例如：斯拉夫语言的一些符号）
    CYRILLIC_OTHER = ("\u0500", "\u050F")  # 其他字符区块（包括斯拉夫语系其他语言的字符，甚至一些特殊符号）

    def __init__(self) -> None:
        super().__init__()

        self.name = "LanguageFilter"
        self.description = (
                "语言过滤器，在翻译开始前，根据原文语言对文本中的无效条目进行过滤以节约 翻译时间 与 Token 消耗"
                + "\n"
                + "兼容性：支持全部语言；支持全部模型；支持全部文本格式；支持翻译润色流程；"
        )

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = True  # 默认启用状态

        self.add_event("text_filter", PluginBase.PRIORITY.NORMAL)

    def on_event(self, event: str, config: TaskConfig, data: CacheProject) -> None:

        if event == "text_filter":
            self.on_text_filter(event, config, data)

    # 文本后处理事件
    def on_text_filter(self, event: str, config: TaskConfig, data: CacheProject) -> None:
        print("")
        print("[LanguageFilter] 开始执行预处理 ...")

        target = []  # 存储需要排除的条目

        # 自动检测语言模式
        if config.source_language == "auto":
            print("[LanguageFilter] 使用自动检测语言模式...")

            # 计算项目中出现次数最多的语言
            most_common_language = TranslatorUtil.get_most_common_language(data)
            # 获取可读更强的名称
            en_source_lang, source_language, _, _ = TranslatorUtil.get_language_display_names(most_common_language, 'chinese_simplified')
            print(f"[LanguageFilter] 项目主要使用语言: {most_common_language} - {en_source_lang}/{source_language}")

            # 处理每个文件中的条目
            for path, file in data.files.items():
                # 获取语言信息
                language_stats = file.language_stats
                # 原文片段列表
                file_items = file.items

                # 确定使用的语言
                if not language_stats:
                    print(
                        f"[[red]WARNING[/]] [LanguageFilter] 文件 {path} 没有检测到语言信息，使用项目主要语言 {most_common_language}"
                    )
                    first_language = most_common_language
                else:
                    first_language = language_stats[0][0]
                    if first_language != 'un':
                        print(
                            f"[[green]INFO[/]] [LanguageFilter] 文件 {path} 主要语言为 {first_language}"
                        )

                # 根据不同情况分别处理
                if TranslatorUtil.map_language_code_to_name(first_language) == config.target_language:
                    target.extend(self._filter_target_language_match(path, file_items, first_language))
                elif first_language == 'un':
                    target.extend(self._filter_unknown_language(path, file_items))
                else:
                    target.extend(self._filter_normal_language(file, file_items, first_language))

        # 指定原文语言模式
        else:
            print("[LanguageFilter] 使用指定语言模式...")
            print(f"[LanguageFilter] 项目主要使用语言: {config.source_language}")
            for path, file in data.files.items():
                # 原文片段列表
                file_items = file.items

                # 原有的非自动检测模式，优化为使用统一的函数
                #target.extend(self._filter_normal_language(file, data.items_iter(), config.source_language)) # 性能更好
                target.extend(self._filter_normal_language(file, file_items, config.source_language))

        print("")
        for item in tqdm(target):
            item.translation_status = TranslationStatus.EXCLUDED

        # 输出结果
        print(f"[LanguageFilter] 语言过滤已完成，共过滤 {len(target)} 个不包含目标语言的条目 ...")
        print("")

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
                or LanguageFilter.CYRILLIC_SUPPLEMENTAL_EXTRA[0] <= char <= LanguageFilter.CYRILLIC_SUPPLEMENTAL_EXTRA[
                    1]
                or LanguageFilter.CYRILLIC_OTHER[0] <= char <= LanguageFilter.CYRILLIC_OTHER[1]
        )

    # 判断字符是否为日文（含汉字）字符
    def is_japanese(self, char: str) -> bool:
        return (
                LanguageFilter.CJK[0] <= char <= LanguageFilter.CJK[1]
                or LanguageFilter.KATAKANA[0] <= char <= LanguageFilter.KATAKANA[1]
                or LanguageFilter.HIRAGANA[0] <= char <= LanguageFilter.HIRAGANA[1]
                or LanguageFilter.KATAKANA_HALF_WIDTH[0] <= char <= LanguageFilter.KATAKANA_HALF_WIDTH[1]
                or LanguageFilter.KATAKANA_PHONETIC_EXTENSIONS[0] <= char <=
                LanguageFilter.KATAKANA_PHONETIC_EXTENSIONS[1]
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
        print(f"[[red]WARNING[/]] [LanguageFilter] 文件 {path} 未知的语言代码 {language_code}，无法使用内置语言过滤函数")
        return None

    def _filter_target_language_match(self, path, file_items, language):
        """处理检测语言与目标语言相同的情况"""
        print(f"[LanguageFilter] 文件 {path} 检测到的主要语言 {language} 与译文语言相同，将只翻译不符合该语言特征的文本")

        has_any = self.get_filter_function(language, path)
        if has_any is not None:
            return [item for item in file_items
                    if item.translation_status == TranslationStatus.EXCLUDED or
                    not isinstance(item.source_text, str) or
                    not item.lang_code or
                    (has_any(item.source_text) and
                     item.lang_code[0] == language and
                     item.lang_code[1] > 0.92)]
        else:
            # 过滤原文检测语言与行语言相同的行
            return [item for item in file_items
                    if item.translation_status == TranslationStatus.EXCLUDED or
                    not isinstance(item.source_text, str) or
                    not item.lang_code or
                    (item.lang_code[0] == language and
                     item.lang_code[1] > 0.92)]

    def _filter_unknown_language(self, path, file_items):
        """处理未知语言的文件"""
        print(f"[LanguageFilter] 文件 {path} 未检测到具体语言，将只翻译置信度较高（大于0.82）的文本行")

        return [item for item in file_items
                if item.translation_status == TranslationStatus.EXCLUDED or
                not isinstance(item.source_text, str) or
                not item.lang_code or
                item.lang_code[1] < 0.82]

    def _filter_normal_language(self, file, file_items, language):
        """处理一般语言情况"""
        # 将Ainiee内置语言代码映射为ISO标准语言代码
        main_source_lang = TranslatorUtil.map_language_name_to_code(language)
        # 如果返回的代码是繁中，重新映射回zh代码
        if main_source_lang == 'zh-Hant':
            main_source_lang = 'zh'
        # 获取语言处理函数
        has_any = self.get_filter_function(main_source_lang, file.file_name)

        # 获取当前文件的低置信度语言统计
        lc_languages = set()
        if file.lc_language_stats:
            lc_languages = {lang for lang, _, _ in file.lc_language_stats}

        filtered_items = []
        for item in file_items:
            # 如果item已经被标记为排除，直接添加
            if item.translation_status == TranslationStatus.EXCLUDED:
                filtered_items.append(item)
                continue

            if not isinstance(item.source_text, str):
                filtered_items.append(item)
                continue

            lang_info = item.get_lang_code(default_lang=main_source_lang)
            detected_lang, confidence = lang_info[0], lang_info[1]
            other_langs = lang_info[2] if len(lang_info) > 2 else []

            # 判断是否不需要过滤:
            # 1. 检测语言与主要源语言不同
            # 2. 检测语言出现在低置信度语言统计中
            # 3. 其他语言列表中包含主要源语言
            not_filter_for_lc = (
                    detected_lang != main_source_lang and
                    detected_lang in lc_languages and
                    main_source_lang in other_langs
            )

            if not_filter_for_lc:
                continue

            # 原有的过滤逻辑
            if has_any is not None:
                if not has_any(item.source_text) or (detected_lang != main_source_lang and confidence > 0.92):
                    filtered_items.append(item)
            else:
                if detected_lang != main_source_lang and confidence > 0.92:
                    filtered_items.append(item)

        return filtered_items
