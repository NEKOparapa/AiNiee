from Plugin_Scripts.PluginBase import PluginBase
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig
from Plugin_Scripts.TextNormalizer.Normalizer import Normalizer

class TextNormalizer(PluginBase):

    def __init__(self) -> None:
        super().__init__()

        self.name = "TextNormalizer"
        self.description = (
            "文本规范器，对文本中不规范的字符（例如半角片假名）进行修正，按需开启"
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
        for k in data.keys():
            data[k] = Normalizer.normalize(data.get(k, ""), merge_space = False)