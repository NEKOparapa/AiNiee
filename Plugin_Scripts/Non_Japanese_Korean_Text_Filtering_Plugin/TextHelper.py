import re

class TextHelper:

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

    # 判断一个字符是否是中日韩标点符号
    @staticmethod
    def is_cjk_punctuation(char):
        return (
            TextHelper.GENERAL_PUNCTUATION[0] <= char <= TextHelper.GENERAL_PUNCTUATION[1]
            or TextHelper.CJK_SYMBOLS_AND_PUNCTUATION[0] <= char <= TextHelper.CJK_SYMBOLS_AND_PUNCTUATION[1]
            or TextHelper.HALFWIDTH_AND_FULLWIDTH_FORMS[0] <= char <= TextHelper.HALFWIDTH_AND_FULLWIDTH_FORMS[1]
            or char in TextHelper.OTHER_CJK_PUNCTUATION
        )

    # 判断一个字符是否是拉丁标点符号
    @staticmethod
    def is_latin_punctuation(char):
        return (
            TextHelper.LATIN_PUNCTUATION_BASIC_1[0] <= char <= TextHelper.LATIN_PUNCTUATION_BASIC_1[1]
            or TextHelper.LATIN_PUNCTUATION_BASIC_2[0] <= char <= TextHelper.LATIN_PUNCTUATION_BASIC_2[1]
            or TextHelper.LATIN_PUNCTUATION_BASIC_3[0] <= char <= TextHelper.LATIN_PUNCTUATION_BASIC_3[1]
            or TextHelper.LATIN_PUNCTUATION_BASIC_4[0] <= char <= TextHelper.LATIN_PUNCTUATION_BASIC_4[1]
            or TextHelper.LATIN_PUNCTUATION_GENERAL[0] <= char <= TextHelper.LATIN_PUNCTUATION_GENERAL[1]
            or TextHelper.LATIN_PUNCTUATION_SUPPLEMENTAL[0] <= char <= TextHelper.LATIN_PUNCTUATION_SUPPLEMENTAL[1]
        )

    # 判断一个字符是否是标点符号
    @staticmethod
    def is_punctuation(char):
        return TextHelper.is_cjk_punctuation(char) or TextHelper.is_latin_punctuation(char)

    # 判断字符是否为日文字符
    @staticmethod
    def is_japanese(ch):
        return (
            TextHelper.CJK[0] <= ch <= TextHelper.CJK[1] 
            or TextHelper.KATAKANA[0] <= ch <= TextHelper.KATAKANA[1]
            or TextHelper.HIRAGANA[0] <= ch <= TextHelper.HIRAGANA[1]
            or TextHelper.KATAKANA_HALF_WIDTH[0] <= ch <= TextHelper.KATAKANA_HALF_WIDTH[1]
            or TextHelper.KATAKANA_PHONETIC_EXTENSIONS[0] <= ch <= TextHelper.KATAKANA_PHONETIC_EXTENSIONS[1]
            or ch in TextHelper.VOICED_SOUND_MARKS
        )

    # 判断字符是否为中日韩汉字
    @staticmethod
    def is_cjk(ch):
        return TextHelper.CJK[0] <= ch <= TextHelper.CJK[1]

    # 判断输入的字符串是否全部由中日韩汉字组成
    @staticmethod
    def is_all_cjk(text):
        return all(TextHelper.is_cjk(char) for char in text)

    # 检查字符串是否包含至少一个中日韩汉字组成
    @staticmethod
    def has_any_cjk(text):
        return any(TextHelper.is_cjk(char) for char in text)

    # 判断字符是否为片假名
    @staticmethod
    def is_katakana(ch):
        return TextHelper.KATAKANA[0] <= ch <= TextHelper.KATAKANA[1]

    # 判断字符串是否全部为片假名
    @staticmethod
    def is_all_katakana(ch):
        return all(TextHelper.is_katakana(ch) for ch in text)

    # 检查字符串是否包含至少一个片假名
    @staticmethod
    def has_any_katakanae(text):
        return any(TextHelper.is_katakana(char) for char in text)

    # 判断字符是否为平假名
    @staticmethod
    def is_hiragana(ch):
        return TextHelper.HIRAGANA[0] <= ch <= TextHelper.HIRAGANA[1]

    # 判断字符串是否全部为平假名
    @staticmethod
    def is_all_hiragana(text):
        return all(TextHelper.is_hiragana(ch) for ch in text)

    # 检查字符串是否包含至少一个平假名
    @staticmethod
    def has_any_hiragana(text):
        return any(TextHelper.is_hiragana(char) for char in text)

    # 判断输入的字符串是否全部由日文字符（含汉字）组成
    @staticmethod
    def is_all_japanese(text):
        return all(TextHelper.is_japanese(char) for char in text)

    # 检查字符串是否包含至少一个日文字符（含汉字）
    @staticmethod
    def has_any_japanese(text):
        return any(TextHelper.is_japanese(char) for char in text)

    # 移除开头结尾的标点符号
    @staticmethod
    def strip_punctuation(text):
        text = text.strip()

        while text and TextHelper.is_punctuation(text[0]):
            text = text[1:]

        while text and TextHelper.is_punctuation(text[-1]):
            text = text[:-1]

        return text.strip()

    # 移除开头结尾的阿拉伯数字
    @staticmethod
    def strip_arabic_numerals(text):
        return re.sub(r'^\d+|\d+$', '', text)

    # 移除开头结尾的非日文字符
    @staticmethod
    def strip_not_japanese(text):
        text = text.strip()

        while text and not TextHelper.is_japanese(text[0]):
            text = text[1:]

        while text and not TextHelper.is_japanese(text[-1]):
            text = text[:-1]

        return text.strip()

    # 移除结尾的汉字字符
    @staticmethod
    def remove_suffix_cjk(text):
        while text and TextHelper.is_cjk(text[-1]):
            text = text[:-1]

        return text

    # 修复不合规的JSON字符串
    @staticmethod
    def fix_broken_json_string(jsonstring):
        # 移除首尾空白符（含空格、制表符、换行符）
        jsonstring = jsonstring.strip()

        # 移除代码标识
        jsonstring = jsonstring.replace("```json", "").replace("```", "").strip()

        # 补上缺失的 }
        jsonstring = jsonstring if jsonstring.endswith("}") else jsonstring + "}"

        # 移除多余的 ,
        jsonstring = jsonstring if not jsonstring.endswith(",}") else jsonstring.replace(",}", "}")
        jsonstring = jsonstring if not jsonstring.endswith(",\n}") else jsonstring.replace(",\n}", "}")

        # 移除单行注释
        jsonstring = re.sub(
            r"//.*(?=,|\s|\}|\n)",
            "",
            jsonstring,
        ).strip()

        # 修正值中错误的单引号
        jsonstring = re.sub(
            r"(?<=:').*?(?=',\n|'\n|'\})",
            lambda matches: matches.group(0).replace("\n", "").replace("\\'", "'").replace("'", "\\'"), 
            jsonstring,
            flags = re.DOTALL
        ).strip()

        # 修正值中错误的双引号
        jsonstring = re.sub(
            r'(?<=:").*?(?=",\n|"\n|"\})',
            lambda matches: matches.group(0).replace('\n', '').replace('\\"', '"').replace('"', '\\"'), 
            jsonstring,
            flags = re.DOTALL
        ).strip()

        # 修正错误的全角引号
        jsonstring = jsonstring.replace('”,\n', '",\n').replace('”\n}', '"\n}').strip()

        return jsonstring

    # 按汉字、平假名、片假名拆开日文短语
    @staticmethod
    def extract_japanese(text):
        return re.findall(
            (
                rf"(?:[{TextHelper.CJK[0]}-{TextHelper.CJK[1]}]+)|" +               # 汉字
                rf"(?:[{TextHelper.HIRAGANA[0]}-{TextHelper.HIRAGANA[1]}]+)|" +     # 平假名
                rf"(?:[{TextHelper.KATAKANA[0]}-{TextHelper.KATAKANA[1]}]+)"        # 片假名
            ), 
            text
        )

    # 移除开头结尾的非汉字字符
    @staticmethod
    def strip_not_cjk(text):
        text = text.strip()

        while text and not TextHelper.is_cjk(text[0]):
            text = text[1:]

        while text and not TextHelper.is_cjk(text[-1]):
            text = text[:-1]

        return text.strip()

    # 判断字符是否为拉丁字符
    @staticmethod
    def is_latin(ch):
        return (
            TextHelper.LATIN_1[0] <= ch <= TextHelper.LATIN_1[1] or
            TextHelper.LATIN_2[0] <= ch <= TextHelper.LATIN_2[1] or
            TextHelper.LATIN_EXTENDED_A[0] <= ch <= TextHelper.LATIN_EXTENDED_A[1] or
            TextHelper.LATIN_EXTENDED_B[0] <= ch <= TextHelper.LATIN_EXTENDED_B[1] or
            TextHelper.LATIN_PUNCTUATION_SUPPLEMENTAL[0] <= ch <= TextHelper.LATIN_PUNCTUATION_SUPPLEMENTAL[1]
        )

    # 判断输入的字符串是否全部由拉丁字符组成
    @staticmethod
    def is_all_latin(text):
        return all(TextHelper.is_latin(ch) for ch in text)

    # 检查字符串是否包含至少一个拉丁字符组成
    @staticmethod
    def has_any_latin(text):
        return any(TextHelper.is_latin(ch) for ch in text)

    # 移除开头结尾的非拉丁字符
    @staticmethod
    def strip_not_latin(text):
        text = text.strip()

        while text and not TextHelper.is_latin(text[0]):
            text = text[1:]

        while text and not TextHelper.is_latin(text[-1]):
            text = text[:-1]

        return text.strip()

    # 判断字符是否为韩文字符
    @staticmethod
    def is_korean(ch):
        return (
            TextHelper.CJK[0] <= ch <= TextHelper.CJK[1] 
            or TextHelper.HANGUL_JAMO[0] <= ch <= TextHelper.HANGUL_JAMO[1]
            or TextHelper.HANGUL_JAMO_EXTENDED_A[0] <= ch <= TextHelper.HANGUL_JAMO_EXTENDED_A[1]
            or TextHelper.HANGUL_JAMO_EXTENDED_B[0] <= ch <= TextHelper.HANGUL_JAMO_EXTENDED_B[1]
            or TextHelper.HANGUL_SYLLABLES[0] <= ch <= TextHelper.HANGUL_SYLLABLES[1]
            or TextHelper.HANGUL_COMPATIBILITY_JAMO[0] <= ch <= TextHelper.HANGUL_COMPATIBILITY_JAMO[1]
        )

    # 判断输入的字符串是否全部由韩文字符组成
    @staticmethod
    def is_all_korean(text):
        return all(TextHelper.is_korean(ch) for ch in text)

    # 检查字符串是否包含至少一个韩文字符组成
    @staticmethod
    def has_any_korean(text):
        return any(TextHelper.is_korean(ch) for ch in text)

    # 移除开头结尾的非韩文字符
    @staticmethod
    def strip_not_korean(text):
        text = text.strip()

        while text and not TextHelper.is_korean(text[0]):
            text = text[1:]

        while text and not TextHelper.is_korean(text[-1]):
            text = text[:-1]

        return text.strip()