import re
from ..Plugin_Base.Plugin_Base import PluginBase


class General_Text_Filtering(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "General_Text_Filtering_Plugin"
        self.description = "This is an example plugin."

    def load(self):
        print(f"[INFO]  {self.name} loaded!")


    def on_event(self, event_name, configuration_information, event_data):

        # 文本预处理事件触发
        if event_name == "preproces_text":

            self.filter_text(event_data)

            print(f"[INFO]  Text has been routinely filtered")



    # 忽视空值内容和将整数型，浮点型数字变换为字符型数字函数，且改变翻译状态为7,因为T++读取到整数型数字时，会报错，明明是自己导出来的...
    def filter_text(self,cache_list):
        for entry in cache_list:
            
            storage_path = entry.get('storage_path')

            if storage_path:
                source_text = entry.get('source_text')

                # 检查文本是否为数值变量
                if  isinstance(source_text, (int, float)) or (isinstance(source_text, str) and source_text.isdigit()):
                    entry['source_text'] = str(source_text)
                    entry['translation_status'] = 7
                    return

                # 检查文本是否为空
                if source_text == "":
                    entry['translation_status'] = 7
                    return

                # 检查文本是否为空
                if source_text == None:
                    entry['translation_status'] = 7
                    return

                # 检查是否仅含标点符号的文本组合
                if isinstance(source_text, str) and self.is_punctuation_string(source_text):
                    entry['translation_status'] = 7
                    return


                #加个检测后缀为MP3，wav，png，这些文件名的文本，都是纯代码文本，所以忽略掉
                if source_text.endswith('.mp3') or source_text.endswith('.wav') or source_text.endswith('.png') or source_text.endswith('.jpg'):
                    entry['translation_status'] = 7
                    return

                
                # 检查文本是否为空
                if source_text:
                    # 正则表达式匹配<sg ?: ?>>格式的文本
                    pattern = r'<SG[^>]*>'
                    matches = re.findall(pattern, source_text)

                    # 检查是否有匹配项
                    if matches:
                        entry['translation_status'] = 7
                        for match in matches:
                            # 查找冒号的位置
                            colon_index = match.find(':')
                            if colon_index != -1: # 如果文本中存在冒号
                                # 分割冒号左边的内容和冒号右边直到>的内容
                                left = match[:colon_index].split('<SG')[-1].strip()
                                right = match[colon_index+1:].split('>')[0].strip()
                                # 检查右边字符量是否比左边字符量大N倍
                                if len(right) > len(left) * 15:
                                    entry['translation_status'] = 0
                                    
                    return


    # 检查字符串是否只包含常见的标点符号
    def is_punctuation_string(self,s: str) -> bool:
        """检查字符串是否只包含标点符号"""
        punctuation = set("!" '"' "#" "$" "%" "&" "'" "(" ")" "*" "+" "," "-" "." "/" "，" "。"  
                        ":" ";" "<" "=" ">" "?" "@" "[" "\\" "]" "^" "_" "`" "{" "|" "}" "~" "—" "・")
        return all(char in punctuation for char in s)
