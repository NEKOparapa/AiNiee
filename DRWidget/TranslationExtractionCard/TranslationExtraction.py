import re
from Base.Base import Base

class TranslationExtraction(Base):
    def extract_tag(self,text):
        """
        提取字符串中最后一个textarea标签内容
        如果没有textarea标签则返回原字符串
        """
        # 使用正则表达式查找所有textarea标签内容（非贪婪模式）
        textarea = re.findall(r'<textarea[^>]*>(.*?)</textarea>', text, flags=re.DOTALL)
        
        if textarea:
            # 返回最后一个span标签内容
            return textarea[-1].strip()
        else:
            # 没有找到则返回空
            return ""