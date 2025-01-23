import itertools
import unicodedata

class Normalizer:

    # 自定义规则
    CUSTOM_RULE = {}

    # 全角转半角
    CUSTOM_RULE.update({chr(i): chr(i - 0xFEE0) for i in itertools.chain(
        range(0xFF21, 0xFF3A + 1),   # 全角 A-Z 转换为 半角 A-Z
        range(0xFF41, 0xFF5A + 1),   # 全角 a-z 转换为 半角 a-z
        range(0xFF10, 0xFF19 + 1),   # 全角 0-9 转换为 半角 0-9
    )})

    # 全角转半角 - 片假名
    CUSTOM_RULE.update({
        "ｱ": "ア",
        "ｲ": "イ",
        "ｳ": "ウ",
        "ｴ": "エ",
        "ｵ": "オ",
        "ｶ": "カ",
        "ｷ": "キ",
        "ｸ": "ク",
        "ｹ": "ケ",
        "ｺ": "コ",
        "ｻ": "サ",
        "ｼ": "シ",
        "ｽ": "ス",
        "ｾ": "セ",
        "ｿ": "ソ",
        "ﾀ": "タ",
        "ﾁ": "チ",
        "ﾂ": "ツ",
        "ﾃ": "テ",
        "ﾄ": "ト",
        "ﾅ": "ナ",
        "ﾆ": "ニ",
        "ﾇ": "ヌ",
        "ﾈ": "ネ",
        "ﾉ": "ノ",
        "ﾊ": "ハ",
        "ﾋ": "ヒ",
        "ﾌ": "フ",
        "ﾍ": "ヘ",
        "ﾎ": "ホ",
        "ﾏ": "マ",
        "ﾐ": "ミ",
        "ﾑ": "ム",
        "ﾒ": "メ",
        "ﾓ": "モ",
        "ﾔ": "ヤ",
        "ﾕ": "ユ",
        "ﾖ": "ヨ",
        "ﾗ": "ラ",
        "ﾘ": "リ",
        "ﾙ": "ル",
        "ﾚ": "レ",
        "ﾛ": "ロ",
        "ﾜ": "ワ",
        "ｦ": "ヲ",
        "ﾝ": "ン",
        "ｧ": "ァ",
        "ｨ": "ィ",
        "ｩ": "ゥ",
        "ｪ": "ェ",
        "ｫ": "ォ",
        "ｬ": "ャ",
        "ｭ": "ュ",
        "ｮ": "ョ",
        "ｯ": "ッ",
        "ｰ": "ー",
        "ﾞ": "゛",  # 浊音符号
        "ﾟ": "゜",  # 半浊音符号
    })

    # 替换
    CUSTOM_RULE.update({k: " " for k in (
        "\u3000",                       # \u3000 全角空格
    )})

    # 移除
    CUSTOM_RULE.update({chr(i): "" for i in (
        0x007F,                         # DEL 删除字符 \u007F
        0xFEFF,                         # BOM 零宽度无断空格 \uFEFF
    )})

    # 移除-会移除到回车符与换行符，和影响文本排版
    CUSTOM_RULE.update({chr(i): "" for i in itertools.chain(
        #range(0x0000, 0x001F + 1),      # C0 控制字符，0x0000 - 0x001F，如 NULL 等
        #range(0x0080, 0x009F + 1),      # C1 控制字符，0x0080 - 0x009F，如 Padding Character 等
        #range(0x00A0, 0x00AD + 1),      # 额外的控制字符和特殊符号，0x00A0 - 0x00AD，如 不换行空格 等
        #range(0x2000, 0x200F + 1),      # 零宽度符号 0x2000 - 0x200F，如 零宽度空格 等
        #range(0x2028, 0x202F + 1),      # 非文本排版样式符号 0x2028 - 0x202F，如 LS 行分隔符 等
        #range(0x2060, 0x206F + 1),      # 不可见的格式控制字符 0x2060 - 0x206F，如 零宽度连字符等
        range(0xFFF0, 0xFFFF + 1),      # 特殊用途的不可见字符 0xFFF0 - 0xFFFF，如 LS 中断注解符 等
    )})

    # 规范化
    def normalize(text: str, merge_space: bool) -> str:
        # NFC（Normalization Form C）：将字符分解后再合并成最小数量的单一字符（合成字符）。
        # NFD（Normalization Form D）：将字符分解成组合字符（即一个字母和附加的重音符号等）。
        # NFKC（Normalization Form KC）：除了合成与分解外，还会进行兼容性转换，例如将全角字符转换为半角字符。
        # NFKD（Normalization Form KD）：除了分解外，还会进行兼容性转换。
        text = unicodedata.normalize("NFC", text)

        # 应用自定义的规则
        text = "".join([Normalizer.CUSTOM_RULE.get(char, char) for char in text])

        # 将多个空格替换为单个空格
        if merge_space == True:
            text = " ".join(text.split())

        return text.strip()