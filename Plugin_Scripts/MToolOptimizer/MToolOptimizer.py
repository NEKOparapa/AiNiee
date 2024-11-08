from tqdm import tqdm
from rich import print

from Plugin_Scripts.PluginBase import PluginBase

class MToolOptimizer(PluginBase):

    def __init__(self):
        super().__init__()
        self.name = "MToolOptimizer"

        self.description = (
            "MTool 优化器，优化翻译流程，提升翻译质量，减少 Token 消耗，至多可提升 40% 的翻译速度"
            + "\n" + "兼容性：仅支持 英文、日文、韩文；支持全部模型；仅支持 MTool 文本；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.NORMAL)
        self.add_event("preproces_text", PluginBase.PRIORITY.NORMAL)
        self.add_event("postprocess_text", PluginBase.PRIORITY.NORMAL)

    def load(self):
        pass

    def on_event(self, event, configurator, data):
        # 检查数据有效性
        if event == None or len(event) <= 1:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 限制语言
        if configurator.source_language not in ("英语", "日语", "韩语"):
            return

        # 限制文本格式
        if "mtool" not in project.get("project_type", "").lower():
            return

        if event == "preproces_text":
            self.on_preproces_text(items, project, event, configurator, data)

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(items, project, event, configurator, data)

    # 文本预处理事件
    def on_preproces_text(self, items, project, event, configurator, data):
        # 检查数据是否已经被插件处理过
        if project.get("mtool_optimizer_processed", False) == True:
            return

        # 检查需要移除的条目
        # 将包含换行符的长句拆分，然后查找与这些拆分后得到的短句相同的句子并移除它们
        print("")
        print("[MToolOptimizer] 开始执行预处理 ...")
        print("")

        orginal_length = len([v for v in items if v.get("translation_status", 0) == 7])
        texts_to_delete = set()

        for v in tqdm(items):
            # 备份原文
            v["source_backup"] = v.get("source_text", "")

            # 找到需要移除的重复条目
            results = [v.strip() for v in v.get("source_text", "").splitlines() if v.strip() != ""]
            texts_to_delete.update(results) if len(results) > 1 else None

        # 移除长句中的换行符，移除重复的短句条目
        for v in tqdm(items):
            if len(v.get("source_text").splitlines()) > 1:
                v["source_text"] = v.get("source_text", "").replace("\r\n", "").replace("\n", "")
            else:
                v["translation_status"] = 7 if v.get("source_text", "").strip() in texts_to_delete else v.get("translation_status", 0)

        print("")
        print(f"[MToolOptimizer] 预处理执行成功，已移除 {len([v for v in items if v.get("translation_status", 0) == 7]) - orginal_length} 个重复的条目 ...")
        print("")

        # 设置处理标志
        project["mtool_optimizer_processed"] = True

    # 文本后处理事件
    def on_postprocess_text(self, items, project, event, configurator, data):
        # 检查数据是否已经被插件处理过
        if project.get("mtool_optimizer_processed", False) == False:
            return

        print("")
        print("[MToolOptimizer] 开始执行后处理 ...")
        print("")

        # 尝试将包含换行符的长句还原回短句
        seen = self.generate_short_sentence(
            items,
            data,
            configurator.source_language
        )

        print("")
        print(f"[MToolOptimizer] 后处理执行成功，已还原 {len(seen)} 个条目 ...")
        print("")

    # 按长度切割字符串
    def split_string_by_length(self, string, length):
        return [string[i:i+length] for i in range(0, len(string), length)]

    # 生成短句
    def generate_short_sentence(self, items, data, language):
        # 记录实际处理的条目
        seen = set()

        for v in tqdm(items):
            # 从备份中恢复原文文本
            if v.get("source_backup", "") != v.get("source_text", ""):
                v["source_text"] = v.get("source_backup", "")

            # 获取原文和译文按行切分，并移除空条目以避免连续换行带来的影响
            source_text = v.get("source_text", "").strip()
            translated_text = v.get("translated_text", "").strip()
            lines_source = [v.strip() for v in source_text.splitlines() if v.strip() != ""]
            lines_translated = [v.strip() for v in translated_text.splitlines() if v.strip() != ""]

            # 第一种情况：原文和译文行数相等，则为其中的每一行生成一个新的条目
            if len(lines_source) > 1 and len(lines_source) == len(lines_translated):
                for source, translated in zip(lines_source, lines_translated):
                    # 跳过重复的条目
                    if source.strip() in seen:
                        continue
                    else:
                        seen.add(source.strip())

                    item = v.copy()
                    item["text_index"] = len(data) + 1
                    item["source_text"] = source.strip()
                    item["translated_text"] = translated.strip()
                    data.append(item)

            # 兜底情况：原文和译文行数不相等，且不满足以上所有的条件，则按固定长度切割
            elif len(lines_source) > 1 and len(lines_source) != len(lines_translated):
                # 统计包含换行符的原文的所有子句的最大长度
                max_length = max(len(line) for line in lines_source)

                # 如果为英语项目（半角字符），则最大长度减半并向下取整
                if language == "英语":
                    max_length = max_length // 2

                # 切分前，先将译文中的换行符移除，避免重复换行，切分长度为子句最大长度 - 1
                lines_translated = self.split_string_by_length(translated_text.replace("\n", ""), max(1, max_length - 1))

                for k, source in enumerate(lines_source):
                    # 尝试获取对应位置的译文，如果没有则使用一个全角空格，空字符串有时候会被忽略
                    translated = lines_translated[k] if k < len(lines_translated) else "　"

                    # 跳过重复的条目
                    if source.strip() in seen:
                        continue
                    else:
                        seen.add(source.strip())

                    item = v.copy()
                    item["text_index"] = len(data) + 1
                    item["source_text"] = source.strip()
                    item["translated_text"] = translated.strip()
                    data.append(item)

        return seen