import re
from Base.Base import Base


class RegexExtractor(Base):
    def extract_rex(self, text, settings):
        """
        通用正则表达式内容提取方法
        :param text: 要处理的原始文本
        :param pattern: 正则表达式模式字符串
        :param mode: 处理方式 
            'last' - 返回最后一个匹配项
            'join' - 用换行符拼接所有匹配项
        :return: 处理后的字符串
        """

        pattern = settings["extract_rule"]
        mode = settings["repetitive_processing"]

        if not pattern:
            return ""

        matches = re.findall(pattern, text, flags=re.DOTALL)

        if not matches:
            return ""
            
        if mode == 'last':
            return str(matches[-1]).strip()
        elif mode == 'join':
            return '\n'.join([str(m).strip() for m in matches])
