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
        ("<", "＜", "《"),
        (">", "＞", "》"),
        ("＜", "<", "《"),
        ("＞", ">", "》"),
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

    # 圆圈数字列表
    CIRCLED_NUMBERS = tuple(chr(i) for i in range(0x2460, 0x2474))                                      # ①-⑳
    CIRCLED_NUMBERS_CJK_01 = tuple(chr(i) for i in range(0x3251, 0x3260))                               # ㉑-㉟
    CIRCLED_NUMBERS_CJK_02 = tuple(chr(i) for i in range(0x32B1, 0x32C0))                               # ㊱-㊿
    CIRCLED_NUMBERS_ALL = ("",) + CIRCLED_NUMBERS + CIRCLED_NUMBERS_CJK_01 + CIRCLED_NUMBERS_CJK_02     # 开头加个空字符来对齐索引和数值

    # 预设编译正则
    PATTERN_ALL_NUM = re.compile(r"\d+|[①-⑳㉑-㉟㊱-㊿]", re.IGNORECASE)
    PATTERN_CIRCLED_NUM = re.compile(r"[①-⑳㉑-㉟㊱-㊿]", re.IGNORECASE)

    def __init__(self) -> None:
        super().__init__()

        self.name = "PunctuationFixer"
        self.description = (
            "标点修复器，在翻译完成后，检查译文中的标点符号是否与原文一致，并尝试修复不一致的标点符号"
            + "\n"
            + "兼容性：支持全部语言；支持全部模型；支持全部文本格式；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = True     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.HIGH)
        self.add_event("postprocess_text", PluginBase.PRIORITY.HIGH)

    def on_event(self, event: str, config: TranslatorConfig, data: list[dict]) -> None:
        # 检查数据有效性
        if isinstance(data, list) == False or len(data) < 2:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 如果指令词典未启用，则跳过
        if config.prompt_dictionary_switch == False:
            return

         # 如果指令词典无内容，则跳过
        if config.prompt_dictionary_data == None or len(config.prompt_dictionary_data) == 0:
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
        print(f"[PunctuationFixer] 标点修复已完成，已修复 {len(logs)} 个标点错误的条目 ...")
        print("")

    # 检查并替换
    def check_and_replace(self, src: str, dst: str) -> str:
        # 修复标点符号
        for target in PunctuationFixer.CHECK_ITEMS:
            if self.check(src, dst, target) == True:
                dst = self.replace(dst, target)

        # 修复圆圈数字
        dst = self.fix_circled_numbers(src, dst)

        # 处理替换项目
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
        # 然后，原文中目标符号和错误符号的数量不应相等，否则无法确定哪个符号是正确的
        # 然后，原文中的目标符号的数量应大于译文中的目标符号的数量，否则表示没有需要修复的标点
        # 最后，如果原文中目标符号的数量等于译文中目标符号与错误符号的数量之和，则判断为需要修复
        return num_s_x > 0 and num_s_x != num_s_y and num_s_x > num_t_x  and num_s_x == num_t_x + num_t_y

    # 替换
    def replace(self, dst: str, target: tuple) -> str:
        for t in target[1:]:
            dst = dst.replace(t, target[0])

        return dst

    # 安全转换字符串为整数
    def safe_int(self, s: str) -> int:
        result = -1

        try:
            result = int(s)
        except Exception as e:
            pass

        return result

    # 修复圆圈数字
    def fix_circled_numbers(self, src: str, dst: str) -> str:
        # 找出 src 与 dst 中的圆圈数字
        src_nums = PunctuationFixer.PATTERN_ALL_NUM.findall(src)
        dst_nums = PunctuationFixer.PATTERN_ALL_NUM.findall(dst)
        src_circled_nums = PunctuationFixer.PATTERN_CIRCLED_NUM.findall(src)
        dst_circled_nums = PunctuationFixer.PATTERN_CIRCLED_NUM.findall(dst)

        # 如果原文中没有圆圈数字，则跳过
        if len(src_circled_nums) == 0:
            return dst

        # 如果原文和译文中数字（含圆圈数字）的数量不一致，则跳过
        if len(src_nums) != len(dst_nums):
            return dst

        # 如果原文中的圆圈数字数量少于译文中的圆圈数字数量，则跳过
        if len(src_circled_nums) < len(dst_circled_nums):
            return dst

        # 遍历原文与译文中的数字（含圆圈数字），尝试恢复
        for i in range(len(src_nums)):
            src_num_srt = src_nums[i]
            dst_num_srt = dst_nums[i]
            dst_num_int = self.safe_int(dst_num_srt)

            # 如果原文中该位置不是圆圈数字，则跳过
            if src_num_srt not in PunctuationFixer.CIRCLED_NUMBERS_ALL:
                continue

            # 如果译文中该位置数值不在有效范围，则跳过
            if dst_num_int < 0 or dst_num_int >= len(PunctuationFixer.CIRCLED_NUMBERS_ALL):
                continue

            # 如果原文、译文中该位置的圆圈数字不一致，则跳过
            if src_num_srt != PunctuationFixer.CIRCLED_NUMBERS_ALL[dst_num_int]:
                continue

            # 尝试恢复
            dst = self.fix_circled_numbers_by_index(dst, i, src_num_srt)

        return dst

    # 通过索引修复圆圈数字
    def fix_circled_numbers_by_index(self, dst: str, target_i: int, target_str: str) -> str:
        # 用于标识目标位置
        i = [0]

        def repl(m: re.Match) -> str:
            if i[0] == target_i:
                i[0] = i[0] + 1
                return target_str
            else:
                i[0] = i[0] + 1
                return m.group(0)

        return PunctuationFixer.PATTERN_ALL_NUM.sub(repl, dst)