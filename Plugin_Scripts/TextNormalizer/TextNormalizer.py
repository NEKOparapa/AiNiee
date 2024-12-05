import jaconv
import unicodedata

from Plugin_Scripts.PluginBase import PluginBase
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig

class TextNormalizer(PluginBase):

    def __init__(self) -> None:
        super().__init__()

        self.name = "TextNormalizer"
        self.description = (
            "文本规范器，在翻译开始前，根据原文语言对文本中不规范的字符（例如半角片假名）进行修正以提升翻译质量"
            + "\n"
            + "兼容性：支持英语、日语；支持全部模型；支持全部文本格式；"
        )

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = True  # 默认启用状态

        self.add_event("normalize_text", PluginBase.PRIORITY.NORMAL)

    def on_event(self, event: str, config: TranslatorConfig, data: dict) -> None:
        if event in ("normalize_text",):
            self.on_normalize_text(event, config, data)

    # 文本规范化事件
    def on_normalize_text(self, event: str, config: TranslatorConfig, data: dict) -> None:
        if config.source_language == "英语":
            for k in data.keys():
                data[k] = unicodedata.normalize("NFKC", data.get(k, ""))
        elif config.source_language == "日语":
            for k in data.keys():
                # Convert Half-width (Hankaku) Katakana to Full-width (Zenkaku) Katakana
                # kana (bool) – Either converting Kana or not.
                # ascii (bool) – Either converting ascii or not.
                # digit (bool) – Either converting digit or not.
                text = jaconv.hankaku2zenkaku(data.get(k, ""), kana=True, ascii=False, digit=False)

                # Convert Full-width (Zenkaku) Katakana to Half-width (Hankaku) Katakana
                # kana (bool) – Either converting Kana or not.
                # ascii (bool) – Either converting ascii or not.
                # digit (bool) – Either converting digit or not.
                text = jaconv.zenkaku2hankaku(text, kana=False, ascii=True, digit=True)

                # 注意，不再直接使用 jaconv.normalize 方法，以避免部分符号被错误的转换
                # https://github.com/ikegami-yukino/jaconv?tab=readme-ov-file
                data[k] = text
