import os
import spacy
import sudachipy
import sudachidict_core
import threading
from Base.Base import Base

class NERProcessor(Base):
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
            
            # 根据传入的模型名动态构建路径
            model_path = os.path.join('.', 'Resource', 'Models', 'NER', model_name)
            
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



    def extract_terms(self, items_data: list, model_name: str, entity_types: list) -> list:
        """
        从提供的原文数据列表中提取命名实体。

        Args:
            items_data (list): 包含待处理数据的列表。
            model_name (str): 要使用的模型名称 (文件夹名)。
            entity_types (list): 需要提取的实体类型标签列表。

        Returns:
            list: 包含结果字典的列表。
        """
        nlp = self._load_model(model_name)
        if not nlp:
            return [] # 如果模型加载失败，返回空列表

        total_items = len(items_data)
        self.info(f"开始对 {total_items} 条原文进行实体识别...")
        results = []
        
        processed_count = 0
        
        for item_data in items_data:
            source_text = item_data.get("source_text")
            file_path = item_data.get("file_path")
            
            if not source_text or not source_text.strip():
                continue

            doc = nlp(source_text)
            for ent in doc.ents:
                if ent.label_ in entity_types:
                    results.append({
                        "term": ent.text,
                        "type": ent.label_,
                        "context": source_text,
                        "file_path": file_path,
                    })

            # 进度反馈
            processed_count += 1
            if processed_count % 50 == 0 or processed_count == total_items:
                self.info(f"实体识别进度: {processed_count}/{total_items}...")


        self.info(f"初步提取到 {len(results)} 个实体。正在去重...")

        # 对结果进行去重
        unique_results = []
        seen = set()
        for res in results:
            identifier = (res["term"].lower(), res["type"])
            if identifier not in seen:
                unique_results.append(res)
                seen.add(identifier)
        
        self.info(f"去重后得到 {len(unique_results)} 个独立术语。")
        return unique_results