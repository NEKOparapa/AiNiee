import unicodedata
from itertools import zip_longest

from tqdm import tqdm
from rich import print

from PluginScripts.PluginBase import PluginBase
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig

class MToolOptimizer(PluginBase):

    def __init__(self) -> None:
        super().__init__()

        self.name = "MToolOptimizer"
        self.description = (
            "MTool 优化器，优化翻译流程，提升翻译质量，至多可减少 40% 的 翻译时间 与 Token 消耗"
            + "\n" + "但可能会带来稳定性下降，翻译错行，翻译不通畅等问题，请酌情开启"
            + "\n" + "兼容性：支持全部语言；支持全部模型；仅支持 MTool 文本；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.NORMAL)
        self.add_event("preproces_text", PluginBase.PRIORITY.NORMAL)
        self.add_event("postprocess_text", PluginBase.PRIORITY.NORMAL)

    def on_event(self, event: str, config: TranslatorConfig, data: list[dict]) -> None:
        # 检查数据有效性
        if isinstance(data, list) == False or len(data) < 2:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 限制文本格式
        if "Mtool" not in project.get("file_project_types", ()):
            return

        if event == "preproces_text":
            mtool_items = [line for line in data if line.get("file_project_type") == 'Mtool']
            self.on_preproces_text(event, config, data, mtool_items, project)

        if event in ("manual_export", "postprocess_text"):
            mtool_items = [line for line in data if line.get("file_project_type") == 'Mtool']
            self.on_postprocess_text(event, config, data, mtool_items, project)

    # 文本预处理事件
    def on_preproces_text(self, event: str, config: TranslatorConfig, data: list[dict], items: list[dict], project: dict) -> None:
        # 检查数据是否已经被插件处理过
        if project.get("mtool_optimizer_processed", False) == True:
            return

        # 检查需要移除的条目
        # 将包含换行符的长句拆分，然后查找与这些拆分后得到的短句相同的句子并移除它们
        print("")
        print("[MToolOptimizer] 开始执行预处理 ...")
        print("")

        # 记录处理前的条目数量
        orginal_length = len([v for v in items if v.get("translation_status", 0) == 7])

        # 找到重复短句条目
        texts_to_delete = set()
        for v in tqdm(items):
            # 备份原文
            v["source_backup"] = v.get("source_text", "")

            # 找到需要移除的重复条目
            if v.get("source_text", "").count("\n") > 0:
                texts_to_delete.update(
                    [v.strip() for v in v.get("source_text", "").splitlines() if v.strip() != ""]
                )

        # 移除重复短句条目
        for v in tqdm(items):
            if v.get("source_text", "").strip() in texts_to_delete:
                v["translation_status"] = 7

        print("")
        print(f"[MToolOptimizer] 预处理执行成功，已移除 {len([v for v in items if v.get("translation_status", 0) == 7]) - orginal_length} 个重复的条目 ...")
        print("")

        # 设置处理标志
        project["mtool_optimizer_processed"] = True

    # 文本后处理事件
    def on_postprocess_text(self, event: str, config: TranslatorConfig, data: list[dict], items: list[dict], project: dict) -> None:
        # 检查数据是否已经被插件处理过
        if project.get("mtool_optimizer_processed", False) == False:
            return

        print("")
        print("[MToolOptimizer] 开始执行后处理 ...")
        print("")

        # 记录实际处理的条目
        seen = set()

        # 尝试将包含换行符的长句还原回短句
        for v in tqdm(items):
            # 从备份中恢复原文文本
            v["source_text"] = v.get("source_backup", "")

            # 获取原文和译文按行切分，并移除空条目以避免连续换行带来的影响
            source_text = v.get("source_text", "").strip()
            translated_text = v.get("translated_text", "").strip()
            lines_source = [v.strip() for v in source_text.splitlines() if v.strip() != ""]
            lines_translated = [v.strip() for v in translated_text.splitlines() if v.strip() != ""]

            # 跳过原文只有一行的条目
            if len(lines_source) <= 1:
                continue

            # 统计原文和译文的最大单行显示长度
            max_length_source = max(self.get_display_length(v) for v in lines_source) if len(lines_source) > 0 else 0
            max_length_translated = max(self.get_display_length(v) for v in lines_translated) if len(lines_translated) > 0 else 0

            # 第一种情况：原文和译文行数相等
            if len(lines_source) == len(lines_translated):
                data, seen = self.update_data(v, data, lines_source, lines_translated, seen)
            # 第二种情况：原文行数大于译文行数，且原文最大显示长度不少于译文最大显示长度
            elif len(lines_source) > len(lines_translated) and max_length_source >= max_length_translated:
                data, seen = self.update_data(v, data, lines_source, lines_translated, seen)
            # 兜底的情况
            else:
                # 切分前，先将译文中的换行符移除，避免重复换行，切分长度为子句最大长度 - 2
                lines_translated = self.split_string_by_display_length(
                    translated_text.replace("\r", "").replace("\n", ""),
                    max(20, max_length_source - 2)
                )

                data, seen = self.update_data(v, data, lines_source, lines_translated, seen)

        print("")
        print(f"[MToolOptimizer] 后处理执行成功，已还原 {len(seen)} 个条目 ...")
        print("")

    # 更新数据
    def update_data(self, target: dict, data: list[dict], lines_s: list[str], lines_t: list[str], seen: set) -> tuple[list[dict], set]:
        # 按照数据对处理译文，长度不足时，则补齐长度
        for source, translated in zip_longest(lines_s, lines_t, fillvalue = ""):
            # 跳过重复的条目
            if source.strip() in seen:
                continue
            else:
                seen.add(source.strip())

            item = target.copy()
            item["text_index"] = len(data) + 1
            item["source_text"] = source.strip() if source.strip() != "" else "　"                  # 注意，空字符串的条目会被忽略，所以使用全角空格填充
            item["translated_text"] = translated.strip() if translated.strip() != "" else "　"      # 注意，空字符串的条目会被忽略，所以使用全角空格填充
            data.append(item)

        return data, seen

    # 按显示长度切割字符串
    def split_string_by_display_length(self, string: str, display_length: int) -> list[str]:
        result = []
        current_length = 0
        current_chunk = []

        for char in string:
            char_length = self.get_display_length(char)
            if current_length + char_length > display_length:
                result.append(''.join(current_chunk))
                current_chunk = []
                current_length = 0

            current_chunk.append(char)
            current_length += char_length

        if current_chunk:
            result.append(''.join(current_chunk))

        return result

    # 计算字符串的显示长度
    def get_display_length(self, text: str) -> int:
        # unicodedata.east_asian_width(c) 返回字符 c 的东亚洲宽度属性。
        # NaH 表示窄（Narrow）、中立（Neutral）和半宽（Halfwidth）字符，这些字符通常被认为是半角字符。
        # 其他字符（如全宽字符）的宽度属性为 W 或 F，这些字符被认为是全角字符。
        return sum(1 if unicodedata.east_asian_width(c) in "NaH" else 2 for c in text)