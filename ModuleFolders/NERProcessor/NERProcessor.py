import os
import spacy
import sudachipy
import sudachidict_core
import threading
from Base.Base import Base 

class NERProcessor(Base):
    """
    一个专门用于执行命名实体识别（NER）的处理类。
    """
    def __init__(self):
        super().__init__()
        self.nlp_models = {}
        # 锁用于确保在多线程环境中模型只被加载一次
        self.nlp_lock = threading.Lock()

    def _load_model(self, language: str):
        """
        按需加载 spaCy 模型，确保线程安全。
        这是一个内部方法。
        """
        # 模型名称映射，可以扩展以支持更多语言
        model_map = {"Japanese": "ja_core_news_sm"}
        model_name = model_map.get(language)
        if not model_name:
            self.error(f"不支持的语言或未配置模型: {language}")
            return None

        # 使用锁来安全地检查和加载模型
        with self.nlp_lock:
            if model_name in self.nlp_models:
                return self.nlp_models[model_name]
            
            # 定义模型的相对路径
            model_path = os.path.join('.', 'Resource', 'Models', 'NER', 'ja_core_news_sm')
            model_path = os.path.join('.', 'Resource', 'Models', 'NER', 'ja_core_news_md')
            #model_path = os.path.join('.', 'Resource', 'Models', 'NER', 'ja_core_news_lg')

            self.info(f"正在加载 spaCy 模型: {model_name}...")
            nlp = spacy.load(model_path)
            self.nlp_models[model_name] = nlp
            self.info(f"模型 {model_name} 加载成功。")
            return nlp


    def extract_terms(self, items_data: list, language: str, entity_types: list) -> list:
        """
        从提供的原文数据列表中提取命名实体。

        Args:
            items_data (list): 包含待处理数据的列表。
                               每个元素是一个字典，如: {"source_text": "...", "file_path": "..."}
            language (str): 要使用的语言/模型。
            entity_types (list): 需要提取的实体类型标签列表。

        Returns:
            list: 包含结果字典的列表。
        """
        nlp = self._load_model(language)
        if not nlp:
            return [] # 如果模型加载失败，返回空列表

        self.info(f"开始对 {len(items_data)} 条原文进行实体识别...")
        results = []
        
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

        self.info(f"初步提取到 {len(results)} 个实体。正在去重...")

        # 对结果进行去重，只保留唯一的（术语，类型）组合
        unique_results = []
        seen = set()
        for res in results:
            # 将术语转为小写进行比较，可以减少因大小写不同导致的重复
            identifier = (res["term"].lower(), res["type"])
            if identifier not in seen:
                unique_results.append(res)
                seen.add(identifier)
        
        self.info(f"去重后得到 {len(unique_results)} 个独立术语。")
        return unique_results