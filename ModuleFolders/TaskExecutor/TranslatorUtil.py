import langcodes

from ModuleFolders.Cache.CacheProject import CacheProject

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
        "zh-Hans": "chinese_simplified",
        "zh-tw": "chinese_traditional",
        "yue": "chinese_traditional",
        "zh-Hant": "chinese_traditional",
        "en": "english",
        "es": "spanish",
        "fr": "french",
        "de": "german",
        "ko": "korean",
        "ru": "russian",
        "ja": "japanese"
    }
    return mapping.get(language_code, language_code)


def map_language_name_to_code(language_name: str) -> str:
    """将语言名称映射回语言代码"""
    mapping = {
        "chinese_simplified": "zh",
        "chinese_traditional": "zh-Hant",  # 单独映射到繁中代码
        "english": "en",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "korean": "ko",
        "russian": "ru",
        "japanese": "ja"
    }
    return mapping.get(language_name, language_name)


def get_language_display_names(source_lang, target_lang):
    """
    获取源语言和目标语言的显示名称
    Args:
        source_lang: 源语言代码
        target_lang: 目标语言代码
    Returns:
        tuple: ((英文源语言名, 中文源语言名), (英文目标语言名, 中文目标语言名))
    """
    # 转换语言代码
    conv_source_lang = map_language_name_to_code(source_lang)
    # 处理源语言
    langcodes_lang = langcodes.Language.get(conv_source_lang)
    if langcodes_lang:
        en_source_lang = langcodes_lang.display_name()
        source_language = langcodes_lang.display_name('zh-Hans')
    else:
        # 处理特殊情况
        if conv_source_lang == 'un':
            en_source_lang = 'UnspecifiedLanguage'
            source_language = '未指定的语言'
        elif conv_source_lang == 'auto':
            en_source_lang = 'Auto Detect'
            source_language = '自动检测'
        else:
            en_source_lang = pair_en[conv_source_lang]
            source_language = pair[conv_source_lang]

    # 处理目标语言
    en_target_language = pair_en[target_lang]
    target_language = pair[target_lang]

    return en_source_lang, source_language, en_target_language, target_language


def get_most_common_language(cache_proj: CacheProject) -> str:
    """
    计算项目中出现次数最多的语言
    Args:
        cache_proj: 项目属性
    Returns:
        出现次数最多的语言代码
    """
    # 语言计数字典
    language_counts = {}

    # 遍历所有文件的语言统计信息
    for path, file in cache_proj.files.items():
        if file.language_stats:
            for lang_stat in file.language_stats:
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

# 确定主语言，通过文件语言统计信息与配置信息计算
def get_source_language_for_file(source_language,target_language, language_stats) -> str:
    """
    为文件确定适当的源语言
    Args:
        storage_path: 文件存储路径
    Returns:
        确定的源语言代码
    """
    # 获取配置文件中预置的源语言配置
    config_s_lang = source_language
    config_t_lang = target_language

    # 如果源语言配置不是自动配置，则直接返回源语言配置，否则使用下面获取到的lang_code
    if config_s_lang != 'auto':
        return config_s_lang

    # 获取文件的语言统计信息
    language_stats = language_stats

    # 如果没有语言统计信息，返回'un'
    if not language_stats:
        return 'un'

    # 获取第一种语言
    first_source_lang = language_stats[0][0]

    # 将first_source_lang转换为与target_lang相同格式的语言名称，方便比较
    first_source_lang_name = map_language_code_to_name(first_source_lang)

    # 检查第一语言是否与目标语言一致
    if first_source_lang_name == config_t_lang:
        # 如果一致，尝试使用第二种语言
        if len(language_stats) > 1:
            return language_stats[1][0]  # 返回第二种语言
        else:
            # 没有第二种语言，返回'un'
            return 'un'
    else:
        # 如果不一致，直接使用第一种语言
        return first_source_lang
