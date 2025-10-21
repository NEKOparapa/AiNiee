import os
import spacy
import sudachipy
import sudachidict_core
import threading
from Base.Base import Base

class NERProcessor(Base):
    # 将过滤器关键字提升为类常量，方便管理

    FILTER_KEYWORDS = ('-', '…', '一','―','？', '©', '章　', 'ー', 'http', '！', '=', '"', '＋', '：', '『', 'ぃ', '～', '♦', '〇',
                    '└', "'", "/", "｢", "）", "（", "♥", "●", "!", "】", "【", "<", ">", "*", "〜", "EV", "♪", "^", "★", "※", ".",
                        "|","ｰ","%","if","Lv","(","\\","]","[","◆",":","_","ｗｗｗ","、","ぁぁ","んえ","んんん",
                    )

    def __init__(self):
        super().__init__()
        self.nlp_models = {}
        # 锁用于确保在多线程环境中模型只被加载一次
        self.nlp_lock = threading.Lock()

    def _load_model(self, model_name: str):
        """
        按需加载 spaCy 模型，确保线程安全。
        这是一个内部方法。
        """
        if not model_name:
            self.error(f"未提供模型名称。")
            return None

        # 使用锁来安全地检查和加载模型
        with self.nlp_lock:
            if model_name in self.nlp_models:
                return self.nlp_models[model_name]

            model_path = os.path.join('.', 'Resource', 'Models', 'ner', model_name)

            if not os.path.exists(model_path):
                self.error(f"模型路径不存在: {model_path}")
                return None

            self.info(f"正在加载 spaCy 模型: {model_name}...")

            # 只加载ner组件，禁用其他所有组件
            nlp = spacy.load(
                model_path,
                exclude=["parser", "tagger", "lemmatizer", "attribute_ruler", "tok2vec"]
            )
            self.nlp_models[model_name] = nlp
            self.info(f"模型 {model_name} 加载成功。")
            return nlp

    def _deduplicate_results(self, results: list) -> list:
        """
        对提取的术语列表进行去重。
        去重逻辑: 基于小写的术语文本和实体类型。
        """
        self.info(f"初步提取到 {len(results)} 个实体。正在去重...")

        unique_items = {}
        for res in results:
            # 使用小写术语和类型作为唯一标识符
            identifier = (res["term"].lower(), res["type"])
            if identifier not in unique_items:
            # 首次遇到，存入完整结果并初始化次数为1
                unique_items[identifier] = res.copy() # 使用copy避免修改原始列表
                unique_items[identifier]['count'] = 1
            else:
            # 已存在，次数加1
                unique_items[identifier]['count'] += 1

    # 从字典的值中构建最终列表
        unique_results = list(unique_items.values())

        self.info(f"去重后得到 {len(unique_results)} 个独立术语。")
        return unique_results

    def _filter_results(self, results: list) -> list:
        """
        根据一系列规则过滤术语列表。
        """
        self.info("正在根据规则过滤术语...")

        # 规则 1: 过滤包含特定禁用关键字的术语
        results_after_keywords = [
            res for res in results
            if not any(keyword in res["term"] for keyword in self.FILTER_KEYWORDS)
        ]
        self.info(f"过滤关键字后剩余 {len(results_after_keywords)} 个术语。")

        # 规则 2 & 3: 过滤纯数字和英文数字组合
        final_filtered_results = []
        for res in results_after_keywords:
            term = res["term"]
            # 创建一个用于检查的临时版本，移除所有半角和全角空格
            term_for_check = term.replace(" ", "").replace("\u3000", "")

            # 规则 2: 如果移除空格后是纯数字，则过滤
            if term_for_check.isdigit():
                continue

            # 规则 3: 如果移除空格后是字母和数字的组合，则过滤
            # 条件: (只包含字母和数字) 并且 (不全是字母)
            if term_for_check.isalnum() and not term_for_check.isalpha():
                continue

            # 如果通过所有检查，则保留该术语
            final_filtered_results.append(res)

        self.info(f"过滤数字与字母数字组合后剩余 {len(final_filtered_results)} 个术语。")
        return final_filtered_results

    def _sort_results(self, results: list) -> list:
        """
        按实体类型对结果列表进行排序。
        """
        self.info("正在按类型对术语进行排序...")
        return sorted(results, key=lambda item: item['type'])

    def extract_terms(self, items_data: list, model_name: str, entity_types: list) -> list:
        """
        从提供的原文数据列表中提取、去重、过滤和排序命名实体。

        Args:
            items_data (list): 包含待处理数据的列表。
            model_name (str): 要使用的模型名称 (文件夹名)。
            entity_types (list): 需要提取的实体类型标签列表。

        Returns:
            list: 包含最终处理结果的字典列表。
        """
        nlp = self._load_model(model_name)
        if not nlp:
            return []

        total_items = len(items_data)
        self.info(f"开始对 {total_items} 条原文进行实体识别...")

        raw_results = []
        processed_count = 0

        # 步骤 1: 从文本中提取原始实体
        for item_data in items_data:
            source_text = item_data.get("source_text")
            file_path = item_data.get("file_path")

            if not source_text or not source_text.strip():
                continue

            doc = nlp(source_text)
            for ent in doc.ents:
                if ent.label_ in entity_types:
                    raw_results.append({
                        "term": ent.text,
                        "type": ent.label_,
                        "context": source_text,
                        "file_path": file_path,
                    })

            processed_count += 1
            if processed_count % 50 == 0 or processed_count == total_items:
                self.info(f"实体识别进度: {processed_count}/{total_items}...")

        # 步骤 2: 对提取结果进行去重
        unique_results = self._deduplicate_results(raw_results)

        # 步骤 3: 对去重后的结果进行过滤
        filtered_results = self._filter_results(unique_results)

        # 步骤 4: 对过滤后的结果进行排序
        sorted_results = self._sort_results(filtered_results)

        self.info(f"处理完成，最终返回 {len(sorted_results)} 个术语。")
        return sorted_results