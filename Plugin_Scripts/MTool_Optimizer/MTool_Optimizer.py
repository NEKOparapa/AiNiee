import math

from tqdm import tqdm
from rich import print

from ..Plugin_Base.Plugin_Base import PluginBase

class MTool_Optimizer(PluginBase):

    def __init__(self):
        super().__init__()
        self.name = "MTool_Optimizer"
        self.description = "MTool_Optimizer"

    def load(self):
        print(f"[INFO]  [green]{self.name}[/] 已加载，至多可提升 [green]40%[/] 的翻译速度，理论上也会提升翻译质量并减少 Token 消耗 ...")

    def on_event(self, event_name, configuration_information, event_data):
        if event_name == "preproces_text":
            self.on_preproces_text(configuration_information, event_data)

        if event_name == "postprocess_text":
            self.on_postprocess_text(configuration_information, event_data)

    # 文本预处理事件
    def on_preproces_text(self, configuration_information, event_data):
        # 检查数据有效性
        if event_data == None or len(event_data) < 2:
            return

        # 检查项目类型
        project = event_data[0]
        if not project.get("project_type", "") == "Mtool":
            return

        # 获取文本条目的列表
        items = event_data[1:]

        # 检查需要移除的条目
        # 将包含换行符的长句拆分，然后查找与这些拆分后得到的短句相同的句子并移除它们
        print(f"")
        print(f"[MTool_Optimizer] 开始执行预处理 ...")
        print(f"")

        orginal_length = len([v for v in items if v.get("translation_status", 0) == 7])
        texts_to_delete = set()

        for v in tqdm(items):
            results = set(v.strip() for v in v.get("source_text", "").split("\n"))
            texts_to_delete.update(results) if len(results) > 1 else None

        for v in tqdm(items):
            v["translation_status"] = 7 if v.get("source_text", "").strip() in texts_to_delete else v.get("translation_status", 0)
        
        counts = len([v for v in items if v.get("translation_status", 0) == 7]) - orginal_length

        print(f"")
        print(f"[MTool_Optimizer] 预处理执行成功，已移除 {counts} 个重复的条目 ...")
        print(f"")

    # 文本后处理事件
    def on_postprocess_text(self, configuration_information, event_data):
        # 检查数据有效性
        if event_data == None or len(event_data) < 2:
            return

        # 检查项目类型
        project = event_data[0]
        if not project.get("project_type", "") == "Mtool":
            return

        # 获取文本条目的列表
        items = event_data[1:]

        # 尝试将包含换行符的长句还原回短句
        print(f"")
        print(f"[MTool_Optimizer] 开始执行后处理 ...")
        print(f"")

        seen = set()
        self.generate_short_sentence(
            [v for v in items if "\n" in v.get("source_text", "")], 
            seen, 
            event_data
        )
        
        counts = len(seen)

        print(f"")
        print(f"[MTool_Optimizer] 后处理执行成功，已还原 {counts} 个条目 ...")
        print(f"")

    # 按长度切割字符串
    def split_string_by_length(self, string, length):
        return [string[i:i+length] for i in range(0, len(string), length)]

    # 生成短句
    def generate_short_sentence(self, items, seen, event_data):
        for v in tqdm(items):
            # 获取原文和译文并按行切分
            source_text = v.get("source_text", "").strip()
            translated_text = v.get("translated_text", "").strip()
            lines_source = source_text.splitlines()
            lines_translated = translated_text.strip().splitlines()
            
            # 统计包含换行符的原文的所有子句的最大长度
            max_length = max(len(line) for line in lines_source if len(lines_source) > 1)
            
            # 第一种情况：原文和译文行数相等，则为其中的每一行生成一个新的条目
            if len(lines_source) > 1 and len(lines_source) == len(lines_translated):
                for source, translated in zip(lines_source, lines_translated):
                    # 跳过重复的条目
                    if source.strip() in seen:
                        continue
                    else:
                        seen.add(source.strip())

                    item = v.copy()
                    item["text_index"] = len(event_data) + 1
                    item["source_text"] = source.strip()
                    item["translated_text"] = translated.strip()
                    event_data.append(item)
                    
            # 兜底情况：原文和译文行数不相等，且不满足以上所有的条件，则按固定长度切割
            elif len(lines_source) > 1 and len(lines_source) != len(lines_translated):
                # 切分前，先将译文中的换行符移除，避免重复换行，切分长度为子句最大长度 - 2
                lines_translated = self.split_string_by_length(translated_text.replace("\n", ""), max_length - 2)
                
                for k, source in enumerate(lines_source):
                    translated = lines_translated[k] if k < len(lines_translated) else ""

                    # 跳过重复的条目
                    if source.strip() in seen:
                        continue
                    else:
                        seen.add(source.strip())

                    item = v.copy()
                    item["text_index"] = len(event_data) + 1
                    item["source_text"] = source.strip()
                    item["translated_text"] = translated.strip()
                    event_data.append(item)