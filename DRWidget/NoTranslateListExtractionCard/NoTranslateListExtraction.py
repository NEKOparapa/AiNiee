import re
from Base.Base import Base

class NoTranslateListExtraction(Base):
    def extract_tag(self,text):
        """
        提取字符串中最后一个span标签内容
        如果没有span标签则返回原字符串
        """
        # 使用正则表达式查找所有span标签内容（非贪婪模式）
        spans = re.findall(r'<code[^>]*>(.*?)</code>', text, flags=re.DOTALL)
        
        if spans:
            # 返回最后一个span标签内容
            return spans[-1].strip()
        else:
            # 没有找到则返回空
            return ""