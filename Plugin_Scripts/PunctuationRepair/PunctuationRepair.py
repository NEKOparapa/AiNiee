from tqdm import tqdm
from rich import print

from Plugin_Scripts.PluginBase import PluginBase
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig

class PunctuationRepair(PluginBase):

    # 检查项，主要是全半角标点之间的转换
    CHECK_ITEMS = (
        ("：", ":"),
        (":", "："),
        ("·", "・"),
        ("・", "·"),
        ("?", "？"),
        ("？", "?"),
        ("!", "！"),
        ("！", "!"),
        ("\u002d", "\u2014", "\u2015"),                    # 破折号之间的转换，\u002d = - ，\u2014 = ― ，\u2015 = —
        ("\u2014", "\u002d", "\u2015"),                    # 破折号之间的转换，\u002d = - ，\u2014 = ― ，\u2015 = —
        ("\u2015", "\u002d", "\u2014"),                    # 破折号之间的转换，\u002d = - ，\u2014 = ― ，\u2015 = —
        ("「", "‘", "“", "『"),
        ("」", "’", "”", "』"),
        ("『", "‘", "“", "「"),
        ("』", "’", "”", "」"),
        ("(", "（", "「", "‘", "“"),
        (")", "）", "」", "’", "”"),
        ("（", "(", "「", "‘", "“"),
        ("）", ")", "」", "’", "”"),
    )

    REPLACE_ITEMS = (
        ("「", "‘", "“"),
        ("」", "’", "”"),
    )

    def __init__(self) -> None:
        super().__init__()

        self.name = "PunctuationRepair"
        self.description = (
            "标点修复器，在翻译完成后，检查译文中的标点符号是否与原文一致，并尝试修复那些不一致的标点符号"
            + "\n"
            + "兼容性：支持全部语言；支持全部模型；支持全部文本格式；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.LOW)
        self.add_event("postprocess_text", PluginBase.PRIORITY.LOW)

    def on_event(self, event: str, config: TranslatorConfig, data: list[dict]) -> None:
        # 检查数据有效性
        if isinstance(data, list) == False or len(data) < 2:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 如果指令词典未启用或者无内容，则跳过
        if (
            config.prompt_dictionary_switch == False
            or config.prompt_dictionary_data == None
            or len(config.prompt_dictionary_data) == 0
        ):
            return

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(event, config, data, items, project)

    # 文本后处理事件
    def on_postprocess_text(self, event: str, config: TranslatorConfig, data: list[dict], items: list[dict], project: dict) -> None:
        print("")
        print("[PunctuationRepair] 开始执行后处理 ...")
        print("")

        # 一次检查所有已翻译的条目
        counter = set()
        target_items = [v for v in items if v.get("translation_status", 0) == 1]
        for i, item in tqdm(enumerate(target_items), total = len(target_items)):
            for target in PunctuationRepair.CHECK_ITEMS:
                if self.check(item.get("source_text"), item.get("translated_text"), target) == True:
                    counter.add(i)
                    item["translated_text"] = self.replace(item.get("translated_text"), target)

            for target in PunctuationRepair.REPLACE_ITEMS:
                item["translated_text"] = self.replace(item.get("translated_text"), target)

        # 输出结果
        print("")
        print(f"[PunctuationRepair] 标点修复已完成，修复标点 {len(counter)}/{len(target_items)} 条 ...")
        print("")

    # 检查
    def check(self, src: str, dst: str, target: tuple) -> tuple[str, bool]:
        num_s_x = src.count(target[0])
        num_s_y = sum(src.count(t) for t in target[1:])
        num_t_x = dst.count(target[0])
        num_t_y = sum(dst.count(t) for t in target[1:])

        # 首先，原文中的目标符号的数量应大于零，否则表示没有需要修复的标点
        # 然后，原文中的目标符号的数量应不等于译文中的目标符号的数量，否则表示没有需要修复的标点
        # 然后，如果原文中目标符号和错误符号的数量不应相等，否则容易产生误判
        # 最后，如果原文中目标符号的数量等于译文中目标符号与错误符号的数量之和，则判断为需要修复
        return num_s_x > 0 and num_s_x != num_t_x and num_s_x != num_s_y and num_s_x == num_t_x + num_t_y

    # 替换
    def replace(self, dst: str, target: tuple) -> str:
        for t in target[1:]:
            dst = dst.replace(t, target[0])

        return dst