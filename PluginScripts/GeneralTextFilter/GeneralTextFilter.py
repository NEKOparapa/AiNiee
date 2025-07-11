from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.Cache.CacheProject import CacheProject
from PluginScripts.PluginBase import PluginBase


class GeneralTextFilter(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "GeneralTextFilter"
        self.description = "GeneralTextFilter"

        self.visibility = False # 是否在插件设置中显示
        self.default_enable = True # 默认启用状态

        self.add_event('text_filter', PluginBase.PRIORITY.HIGH)

    def load(self):
        pass


    def on_event(self, event_name, config, event_data: CacheProject):

        # 文本预处理事件触发
        if event_name == "text_filter":

            self.filter_text(event_data)

    # 忽视空值内容和将整数型，浮点型数字变换为字符型数字函数，且改变翻译状态为7,因为T++读取到整数型数字时，会报错，明明是自己导出来的...
    def filter_text(self, event_data: CacheProject):
        for entry in event_data.items_iter():

            source_text = entry.source_text

            # 检查文本是否为数值变量
            if isinstance(source_text, (int, float)):
                entry.source_text = str(source_text)
                entry.translation_status = TranslationStatus.EXCLUDED
                continue

            # 检查文本是否为字符型数字
            if (isinstance(source_text, str) and source_text.isdigit()):
                entry.translation_status = TranslationStatus.EXCLUDED
                continue

            # 检查文本是否为空
            if source_text is None or source_text.strip() == "":
                entry.translation_status = TranslationStatus.EXCLUDED
                continue

            # 检查文本是仅换行符
            if source_text.strip() in ("\n", "\\n", "\r", "\\r"):
                entry.translation_status = TranslationStatus.EXCLUDED
                continue

            # 检查是否仅含标点符号的文本组合
            if isinstance(source_text, str) and self.is_punctuation_string(source_text):
                entry.translation_status = TranslationStatus.EXCLUDED
                continue

            #加个检测后缀为MP3，wav，png，这些文件名的文本，都是纯代码文本，所以忽略掉
            if isinstance(source_text, str) and self._get_file_suffix(source_text.rstrip()) in self.EXCLUDE_FILE_SUFFIX:
                entry.translation_status = TranslationStatus.EXCLUDED
                continue

            # 检查开头的
            if isinstance(source_text, str) and any(source_text.startswith(ext) for ext in self.EXCLUDE_PREFIX):
                entry.translation_status = TranslationStatus.EXCLUDED
                continue

    # 检查字符串是否只包含常见的标点符号
    def is_punctuation_string(self,s: str) -> bool:
        """检查字符串是否只是标点符号与双种空格组合"""
        punctuation = set(" " " " "!" '"' "#" "$" "%" "&" "'" "(" ")" "*" "+" "," "-" "." "/" "，" "。"
                        ":" ";" "<" "=" ">" "?" "@" "[" "\\" "]" "^" "_" "`" "{" "|" "}" "~" "—" "・" "？" "↑" "←" "↓" "→" "「" "」" "『" "』" "【" "】" "《" "》"
                        "！" "＂" "＃" "＄" "％" "＆" "＇" "（" "）" "＊" "＋" "，" "－" "．" "／" "：" "；" "＜" "＝" "＞" "？" "＠" )
        return all(char in punctuation for char in s)

    def _get_file_suffix(self, text: str):
        split = text.rsplit(".", 1)
        return f".{split[1]}" if len(split) == 2 else split[0]

    EXCLUDE_PREFIX = ('MapData/', 'SE/', 'BGS', '0=', 'BGM/', 'FIcon/', '<input type=', 'width:', '<div ', 'EV0', '\\img')

    EXCLUDE_FILE_SUFFIX = frozenset([
        '.mp3', '.wav', '.png', '.jpg', '.gif', '.rar', '.zip', '.json', '.ogg', '.txt', '.mps', '.woff',
        '.txt', '.wav', '.webp', '.jpg)', '.txt', '.doc', '.html', '.bmp', '.pic', '.aac', '.flac', '.avi',
        '.py', '.c', '.cpp', '.js', '.java', '.css', '.xml', '.flac', '.jpeg', '.mov', '.mkv', '.flv',
    ])
