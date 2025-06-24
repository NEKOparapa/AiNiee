from collections import defaultdict
import unicodedata
from itertools import zip_longest

from tqdm import tqdm
from rich import print

from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Cache.CacheProject import CacheProject, ProjectType
from PluginScripts.PluginBase import PluginBase
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig

class MToolOptimizer(PluginBase):

    def __init__(self) -> None:
        super().__init__()

        self.name = "MToolOptimizer"
        self.description = (
            "MTool 优化器，优化翻译流程，提升翻译质量，至多可减少 40% 的 翻译时间 与 Token 消耗"
            + "\n" + "但可能会带来稳定性下降，翻译错行，翻译不通畅等问题，请酌情开启"
            + "\n" + "兼容性：支持全部语言；支持全部模型；仅支持 MTool 文本；仅支持翻译流程；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.NORMAL)
        self.add_event("preproces_text", PluginBase.PRIORITY.NORMAL)
        self.add_event("postprocess_text", PluginBase.PRIORITY.NORMAL)

    def on_event(self, event: str, config: TaskConfig, data: CacheProject) -> None:

        # 限制文本格式
        if ProjectType.MTOOL not in data.file_project_types:
            return

        if event == "preproces_text":
            # 检查数据是否已经被插件处理过
            if data.get_extra("mtool_optimizer_processed", False):
                return
            mtool_items = list(data.items_iter(ProjectType.MTOOL))
            self.on_preproces_text(event, config, mtool_items)
            data.set_extra("mtool_optimizer_processed", True)

        if event in ("manual_export", "postprocess_text"):
            # 检查数据是否已经被插件处理过
            if not data.get_extra("mtool_optimizer_processed", False):
                return
            mtool_items = list(data.items_iter(ProjectType.MTOOL))
            self.on_postprocess_text(event, config, mtool_items)

    # 文本预处理事件
    def on_preproces_text(self, event: str, config: TaskConfig, items: list[CacheItem]) -> None:

        # 检查需要移除的条目
        # 将包含换行符的长句拆分，然后查找与这些拆分后得到的短句相同的句子并移除它们
        print("")
        print("[MToolOptimizer] 开始执行预处理 ...")
        print("")

        # 记录处理前的条目数量
        orginal_length = len([v for v in items if v.translation_status == TranslationStatus.EXCLUDED])

        # 找到重复短句条目
        texts_to_delete = set()
        for v in tqdm(items):

            # 找到需要移除的重复条目
            if v.source_text.find("\n") >= 0:
                texts_to_delete.update(
                    v.strip() for v in v.source_text.splitlines() if v.strip() != ""
                )

        # 移除重复短句条目
        for v in tqdm(items):
            if v.source_text.strip() in texts_to_delete:
                v.translation_status = TranslationStatus.EXCLUDED

        print("")
        print(f"[MToolOptimizer] 预处理执行成功，已移除 {len([v for v in items if v.translation_status == TranslationStatus.EXCLUDED]) - orginal_length} 个重复的条目 ...")
        print("")

    # 文本后处理事件
    def on_postprocess_text(self, event: str, config: TaskConfig, items: list[CacheItem]) -> None:

        print("")
        print("[MToolOptimizer] 开始执行后处理 ...")
        print("")

        # 记录实际处理的条目
        seen = set()

        # 找到短句，并按原文分组
        source_text_mapping = defaultdict[str, list[CacheItem]](list)
        for item in items:
            if item.source_text.find("\n") == -1:
                source_text_mapping[item.source_text.strip()].append(item)

        # 尝试将包含换行符的长句还原回短句
        for v in tqdm(items):

            # 获取原文和译文按行切分，并移除空条目以避免连续换行带来的影响
            source_text = v.source_text.strip()
            translated_text = v.translated_text.strip()
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
                self.update_data(lines_source, lines_translated, seen, source_text_mapping)
            # 第二种情况：原文行数大于译文行数，且原文最大显示长度不少于译文最大显示长度
            elif len(lines_source) > len(lines_translated) and max_length_source >= max_length_translated:
                self.update_data(lines_source, lines_translated, seen, source_text_mapping)
            # 兜底的情况
            else:
                # 切分前，先将译文中的换行符移除，避免重复换行，切分长度为子句最大长度 - 2
                lines_translated = self.split_string_by_display_length(
                    translated_text.replace("\r", "").replace("\n", ""),
                    max(20, max_length_source - 2)
                )

                self.update_data(lines_source, lines_translated, seen, source_text_mapping)

        print("")
        print(f"[MToolOptimizer] 后处理执行成功，已还原 {len(seen)} 个条目 ...")
        print("")

    # 更新数据
    def update_data(self, lines_s: list[str], lines_t: list[str], seen: set, source_text_mapping: defaultdict[str, list[CacheItem]]):
        # 按照数据对处理译文，长度不足时，则补齐长度
        for source, translated in zip_longest(lines_s, lines_t, fillvalue = ""):
            # 跳过重复的条目
            if source.strip() in seen:
                continue
            else:
                seen.add(source.strip())

            # 更新短句的译文
            for item in source_text_mapping.get(source.strip(), ()):
                item.translated_text = translated.strip() if translated.strip() != "" else "　"
                item.translation_status = TranslationStatus.TRANSLATED

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