import re
from ..PluginBase import PluginBase


class General_Text_Filtering(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "General_Text_Filtering_Plugin"
        self.description = "This is an example plugin."

        self.visibility = False # 是否在插件设置中显示
        self.default_enable = True # 默认启用状态

        self.add_event('text_filter', PluginBase.PRIORITY.HIGH)

    def load(self):
        print(f"[INFO] {self.name} loaded!")


    def on_event(self, event_name, config, event_data):

        # 文本预处理事件触发
        if event_name == "text_filter":

            self.filter_text(event_data)

            print(f"[INFO] Text has been routinely filtered")



    # 忽视空值内容和将整数型，浮点型数字变换为字符型数字函数，且改变翻译状态为7,因为T++读取到整数型数字时，会报错，明明是自己导出来的...
    def filter_text(self,cache_list):
        for entry in cache_list:

            storage_path = entry.get('storage_path')

            if storage_path:
                source_text = entry.get('source_text')

                # 检查文本是否为数值变量
                if  isinstance(source_text, (int, float)) :
                    entry['source_text'] = str(source_text)
                    entry['translation_status'] = 7
                    continue

                # 检查文本是否为字符型数字
                if (isinstance(source_text, str) and source_text.isdigit()):
                    entry['source_text'] = str(source_text)
                    entry['translation_status'] = 7
                    continue

                # 检查文本是否为空
                if source_text == "":
                    entry['translation_status'] = 7
                    continue

                # 检查文本是否为空
                if source_text == None:
                    entry['translation_status'] = 7
                    continue

                # 检查文本是仅换行符
                if source_text in ("\n","\\n","\r","\\r"):
                    entry['translation_status'] = 7
                    continue

                # 检查是否仅含标点符号的文本组合
                if isinstance(source_text, str) and self.is_punctuation_string(source_text):
                    entry['translation_status'] = 7
                    continue


                #加个检测后缀为MP3，wav，png，这些文件名的文本，都是纯代码文本，所以忽略掉
                if isinstance(source_text, str) and any(source_text.lower().endswith(ext) for ext in ['.mp3', '.wav', '.png', '.jpg', '.gif', '.rar', '.zip', '.json', '.ogg']):
                    entry['translation_status'] = 7
                    continue


                # 同上
                if isinstance(source_text, str) and any(source_text.lower().endswith(ext) for ext in ['.txt', '.wav', '.webp']):
                    entry['translation_status'] = 7
                    continue


                # 检查开头的
                if isinstance(source_text, str) and any(source_text.lower().startswith(ext) for ext in ['MapData/', 'SE/', 'BGS', '0=', 'BGM/', 'FIcon/', '<input type=', 'width:', '<div ']):
                    entry['translation_status'] = 7
                    continue


                # 检查开头的
                if isinstance(source_text, str) and any(source_text.lower().startswith(ext) for ext in ['EV0']):
                    entry['translation_status'] = 7
                    continue

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

                    continue


    # 检查字符串是否只包含常见的标点符号
    def is_punctuation_string(self,s: str) -> bool:
        """检查字符串是否只是标点符号与双种空格组合"""
        punctuation = set(" " " " "!" '"' "#" "$" "%" "&" "'" "(" ")" "*" "+" "," "-" "." "/" "，" "。"
                        ":" ";" "<" "=" ">" "?" "@" "[" "\\" "]" "^" "_" "`" "{" "|" "}" "~" "—" "・")
        return all(char in punctuation for char in s)
