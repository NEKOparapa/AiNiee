import re
from tqdm import tqdm
from rich import print

from Plugin_Scripts.PluginBase import PluginBase
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig

class PunctuationFixer(PluginBase):

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

    # 替换项
    REPLACE_ITEMS = (
        ("「", "‘", "“"),
        ("」", "’", "”"),
    )

    # 圆圈数字修复，开头加个空字符来对齐索引和数值
    CIRCLED_NUMBERS = ("", "①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩", "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳")

    def __init__(self) -> None:
        super().__init__()

        self.name = "PunctuationFixer"
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
        print("[PunctuationFixer] 开始执行后处理 ...")
        print("")

        # 依次检查已翻译的条目
        logs = list()
        target_items = [v for v in items if v.get("translation_status", 0) == 1]
        for item in tqdm(target_items):
            # 检查并替换
            diff = self.check_and_replace(item.get("source_text"), item.get("translated_text"))

            # 如果有变化，则更新
            if diff != item.get("translated_text"):
                logs.append(f"\n{item.get("source_text")}\n[green]->[/]\n{item.get("translated_text")}\n[green]->[/]\n{diff}\n")
                item["translated_text"] = diff

        # 输出结果
        print("")
        print(f"[PunctuationFixer] 标点修复已完成，修复标点 {len(logs)}/{len(target_items)} 条 ...")
        print("")

    # 检查并替换
    def check_and_replace(self, src: str, dst: str) -> str:
        for target in PunctuationFixer.CHECK_ITEMS:
            if self.check(src, dst, target) == True:
                dst = self.replace(dst, target)

        # 找出 src 与 dst 中的圆圈数字
        src_circled_nums = re.findall(r"[①-⑳]", src)
        dst_circled_nums = re.findall(r"[①-⑳]", dst)

        # 如果有圆圈数字，并且两者的数量不一致（避免误判），则尝试修复
        if len(src_circled_nums) > 0 and src_circled_nums != dst_circled_nums:
            # 找到 dst 中在有效值范围内的数字
            nums = [int(v) for v in re.findall(r"[0-9]+", dst) if 0 < int(v) < len(PunctuationFixer.CIRCLED_NUMBERS)]

            # 筛选出出现次数一样的数字
            nums = [
                v for v in nums
                if nums.count(v) == src_circled_nums.count(PunctuationFixer.CIRCLED_NUMBERS[v])
            ]

            # 遍历数字列表，将数字替换为对应的圆圈数字
            for num in nums:
                dst = re.sub(
                    r"[0-9]+",
                    lambda m: self.restore_circled_numbers(m = m, num = num),
                    dst,
                )

        for target in PunctuationFixer.REPLACE_ITEMS:
            dst = self.replace(dst, target)

        return dst

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

    # 圆圈数字修复
    def restore_circled_numbers(self, m: re.Match, num: int) -> None:
        if num != int(m.group(0)):
            return m.group(0)
        else:
            return PunctuationFixer.CIRCLED_NUMBERS[num]