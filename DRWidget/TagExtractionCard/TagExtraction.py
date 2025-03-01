import re
from Base.Base import Base

class TagExtractor(Base):

    def extract_tag(self, text, settings):
            """
            提取字符串中最后一个指定标签的内容
            :param text: 要处理的原始字符串
            :param tag: 要提取的HTML标签名（如div、p等）
            :return: 最后一个标签内容（无标签则返回空）
            """
            # 提取标签文本
            tag = settings["extract_rule"]

            if not tag:
                return ""

            # 安全处理标签名，防止正则注入
            sanitized_tag = re.escape(tag)
            
            # 构建动态正则表达式
            pattern = rf'<{sanitized_tag}[^>]*>(.*?)</{sanitized_tag}>'
            
            # 查找所有匹配项（非贪婪模式）
            matches = re.findall(pattern, text, flags=re.DOTALL)
            
            if matches:
                # 返回最后一个匹配项并去除首尾空白
                return matches[-1].strip()
            else:
                # 没有匹配项返回空
                return ""