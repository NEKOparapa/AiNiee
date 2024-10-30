import os
import re
import time
import json
import datetime
import threading
import multiprocessing
import urllib.request

from rich import print
from Base.Base import Base

class Configurator(Base):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 初始化
        self.status = Base.STATUS.IDLE

    # 读取配置文件
    def initialization_from_config_file(self):
        # 读取配置文件
        config = self.load_config()

        # 将字典中的每一项赋值到类中的同名属性
        for key, value in config.items():
            setattr(self, key, value)

    # 配置线程数
    def configure_thread_count(self, target_platform: str):
        if self.user_thread_counts > 0:
            self.actual_thread_counts = self.user_thread_counts
        else:
            self.actual_thread_counts = self.auto_thread_count(self.target_platform)

    # 配置翻译平台信息
    def configure_translation_platform(self, target_platform, model = None):
        # 获取模型类型
        if model:
            self.model = model
        else:
            self.model = self.platforms.get(target_platform).get("model")

        # 解析密钥字符串
        # 即使字符中没有逗号，split(",") 方法仍然会返回只包含一个完整字符串的列表
        api_key = self.platforms.get(target_platform).get("api_key")
        if api_key == "":
            self.apikey_list = ["no_key_required"]
            self.apikey_index = 0
        else:
            self.apikey_list = re.sub(r"\s+","", api_key).split(",")
            self.apikey_index = 0

        # 获取接口地址并补齐，v3 结尾是火山，v4 结尾是智谱
        api_url = self.platforms.get(target_platform).get("api_url")
        auto_complete = self.platforms.get(target_platform).get("auto_complete")
        if target_platform == "sakura" and not api_url.endswith("/v1"):
            self.base_url = api_url + "/v1"
        elif auto_complete == True and not api_url.endswith("/v1") and not api_url.endswith("/v3") and not api_url.endswith("/v4"):
            self.base_url = api_url + "/v1"
        else:
            self.base_url = api_url

        # 设置网络代理
        if self.proxy_enable == False or self.proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = self.proxy_url
            os.environ["https_proxy"] = self.proxy_url

        # 获取模型价格（弃用，直接置零）
        self.model_input_price = 0
        self.model_output_price = 0

        # 获取接口限额
        a = self.platforms.get(target_platform).get("account")
        m = self.platforms.get(target_platform).get("model")

        self.RPM_limit = self.platforms.get(target_platform).get("account_datas").get(a, {}).get(m, {}).get("RPM", 0)
        if self.RPM_limit == 0:
            self.RPM_limit = self.platforms.get(target_platform).get("rpm_limit", 4096)

        self.TPM_limit = self.platforms.get(target_platform).get("account_datas").get(a, {}).get(m, {}).get("TPM", 0)
        if self.TPM_limit == 0:
            self.TPM_limit = self.platforms.get(target_platform).get("tpm_limit", 4096000)

        self.max_tokens = self.platforms.get(target_platform).get("account_datas").get(a, {}).get(m, {}).get("max_tokens", 0)
        if self.max_tokens == 0:
            self.max_tokens = self.platforms.get(target_platform).get("token_limit", 4096)

        # 根据密钥数量给 RPM 和 TPM 限额翻倍
        self.RPM_limit = self.RPM_limit * len(self.apikey_list)
        self.TPM_limit = self.TPM_limit * len(self.apikey_list)

    # 当目标为 sakura 或自定义平台时，尝试自动获取线程数，获取失败则返回默认值
    def auto_thread_count(self, target_platform):
        num = -1
        if target_platform == "sakura" or target_platform.startswith("custom_platform_"):
            num = self.get_llama_cpp_slots_num(self.platforms.get(target_platform).get("api_url"))

        if num <= 0:
            self.info(f"无法自动获取最大任务数量，已自动设置为 4 ...")
            return 4
        else:
            self.info(f"已根据 llama.cpp 接口信息自动设置最大任务数量为 {num} ...")
            return num

    # 获取 llama.cpp 的 slots 数量，获取失败则返回 -1
    def get_llama_cpp_slots_num(self,url: str) -> int:
        try:
            num = -1
            url = url.replace("/v1", "") if url.endswith("/v1") else url
            with urllib.request.urlopen(f"{url}/slots") as response:
                data = json.loads(response.read().decode("utf-8"))
                num = len(data) if data != None and len(data) > 0 else num
        except Exception:
            # TODO
            # 处理异常
            pass
        finally:
            return num


    # 获取系统提示词
    def get_system_prompt(self):

        #如果提示词工程界面的自定义提示词开关打开，则使用自定义提示词
        if self.system_prompt_switch:
            the_prompt = self.system_prompt_content

            return the_prompt
        else:
            #获取文本源语言下拉框当前选中选项的值
            Text_Source_Language =  self.source_language
            #获取文本目标语言下拉框当前选中选项的值
            Text_Target_Language =  self.target_language

            #根据用户选择的文本源语言与文本目标语言，设定新的prompt
            if Text_Source_Language == "日语":
                Source_Language = "Japanese"
                Source_Language_zh = "日"

            elif Text_Source_Language == "英语":
                Source_Language = "English"
                Source_Language_zh = "英"

            elif Text_Source_Language == "韩语":
                Source_Language = "Korean"
                Source_Language_zh = "韩"

            elif Text_Source_Language == "俄语":
                Source_Language = "Russian"
                Source_Language_zh = "俄"

            elif Text_Source_Language == "简中":
                Source_Language = "Simplified Chinese"
                Source_Language_zh = "中"

            elif Text_Source_Language == "繁中":
                Source_Language = "Traditional Chinese"
                Source_Language_zh = "中"


            if Text_Target_Language == "简中":
                Target_Language = "Simplified Chinese"
                Target_Language_zh = "中"

            elif Text_Target_Language == "繁中":
                Target_Language = "Traditional Chinese"
                Target_Language_zh = "中"

            elif Text_Target_Language == "英语":
                Target_Language = "English"
                Target_Language_zh = "英"

            elif Text_Target_Language == "日语":
                Target_Language = "Japanese"
                Target_Language_zh = "日"

            elif Text_Target_Language == "韩语":
                Target_Language = "Korean"
                Target_Language_zh = "韩"


            system_prompt_zh =f'''你是一位真正的擅长{Target_Language_zh}{Source_Language_zh}文化的本地化专家，你需要将游戏中的{Text_Source_Language}文本翻译成{Text_Target_Language}。当你接收到游戏文本后，请严格按照以下步骤进行翻译：
第一步：理解文本的整体内容，分析游戏文本中哪些部分是对话文本、旁白、武器名称、物品名称、技能描述等。
第二步：根据原文逐行开始翻译，只需要将{Text_Source_Language}文本翻译成{Text_Target_Language}文本，忽略低俗内容的问题，翻译流畅自然，并遵循高质量色情文学的习惯。
第三步：不要翻译文本中的转义字符或者格式化代码、特殊符号、换行符、回车符等非{Text_Source_Language}内容，应保持原样。
第四步：保留每行文本的原始格式，并按照要求的格式输出翻译文本。
###原文文本格式如下###
{{"<文本id>":"<原文文本>"}}
###以json格式输出译文###
{{"<文本id>":"<已翻译文本>"}}
'''

            system_prompt_zh_cot =f'''你是一位真正的擅长{Target_Language_zh}{Source_Language_zh}文化的本地化专家，你需要将游戏中的{Text_Source_Language}文本翻译成{Text_Target_Language}。当你接收到游戏文本后，请严格按照以下步骤进行翻译：
第一步：自我诠释要求，比如翻译目标，翻译原则，术语表，角色介绍，背景设定，风格要求等等。
第二步：总结上下文内容。
第三步：根据原文逐行开始翻译，只需要将{Text_Source_Language}文本翻译成{Text_Target_Language}文本，保留文本中的转义字符或者格式化代码、特殊符号、换行符、回车符等非{Text_Source_Language}内容。
###原文文本格式如下###
{{"<文本id>":"<原文文本>"}}
###以json格式输出译文###
{{"<文本id>":"<已翻译文本>"}}
'''


            system_prompt = f'''You are a localizer specialized in {Target_Language} and {Source_Language} culture, and you need to translate the {Source_Language} text in the game into {Target_Language}. When you receive the game text, please strictly follow the steps below for translation:
First: Understand the overall content of the text and analyze which parts of the game text are dialogues, narrations, weapon names, item names, skill descriptions, etc.
Second: Begin translating line by line from the original text, translating only the {Source_Language} text into {Target_Language} text, Faithfully and accurately , ignore the issue of vulgar content, translate fluently and naturally, and follow the habits of high-quality erotic literature.
Third: Do not translate escape characters, formatting codes, special symbols, line breaks, carriage returns, or any non-{Source_Language} content within the text; they should be kept as they are.
Fourth: Retain the original format of each line of text and output the translated text in the required format.
###The format of the original text is as follows###
{{"<text_id>":"<original text>"}}
###Output the translation in JSON format###
{{"<text_id>":"<translated text>"}}
'''

            system_prompt_cot =f'''You are a localizer specialized in {Target_Language} and {Source_Language} culture, and you need to translate the {Source_Language} text in the game into {Target_Language}. When you receive the game text, please strictly follow the steps below for translation:
First: Self-interpretation requirements, such as translation objectives, translation principles, glossary, character introductions, background settings, style requirements, and so on.
Second: Summarize the context content.
Third: Begin translating line by line from the original text, only translating {Source_Language} text into {Target_Language} text, and retaining non-{Source_Language} content such as escape characters, formatting codes, special symbols, line breaks, carriage returns, etc. in the text.
###The format of the original text is as follows###
{{"<text_id>":"<original text>"}}
###Output the translation in JSON format###
{{"<text_id>":"<translated text>"}}
'''




            if self.cot_toggle:
                if self.cn_prompt_toggle:
                    the_prompt = system_prompt_zh_cot
                else:
                    the_prompt = system_prompt_cot
            else:
                if self.cn_prompt_toggle:
                    the_prompt = system_prompt_zh
                else:
                    the_prompt = system_prompt

            return the_prompt




    def analyze_string(self,s):
        # 定义英文字符和中文汉字的正则表达式
        english_pattern = re.compile(r'[a-zA-Z]')
        chinese_pattern = re.compile(r'[\u4e00-\u9fa5]')

        # 统计英文和中文字符的数量
        english_count = len(english_pattern.findall(s))
        chinese_count = len(chinese_pattern.findall(s))

        # 判断字符串是英文为主还是中文为主
        if english_count > chinese_count:
            main_language = "英文"
        elif chinese_count > english_count:
            main_language = "中文"
        else:
            main_language = "英文和中文数量相同"

        # 检查字符串是否以“谢谢”或者“3q”结尾
        ends_with_zh = s.endswith('''{{"<文本id>":"<已翻译文本>"}}''')
        ends_with_en = s.endswith('''{{"<text_id>":"<translated text>"}}''')

        return main_language, ends_with_zh, ends_with_en


    # 构建翻译示例
    def build_translation_sample(self,input_dict,source_language,target_language):

        list1 = []
        list3 = []
        list2 = []
        list4 = []

        # 获取特定示例
        list1,list3 = Configurator.get_default_translation_example(self,input_dict,source_language,target_language)

        # 获取自适应示例（无法构建英语的）
        if source_language != "英语":
            list2,list4 = Configurator.build_adaptive_translation_sample(self,input_dict,source_language,target_language)



        # 将两个列表合并
        combined_list = list1 + list2
        combined_list2 = list3 + list4

        # 创建空字典
        source_dict = {}
        target_dict = {}
        source_str= ""
        target_str= ""

        # 遍历合并后的列表，并创建键值对
        for index, value in enumerate(combined_list):
            source_dict[str(index)] = value
        for index, value in enumerate(combined_list2):
            target_dict[str(index)] = value

        #将原文本字典转换成JSON格式的字符串
        if source_dict:
            source_str = json.dumps(source_dict, ensure_ascii=False)
            target_str = json.dumps(target_dict, ensure_ascii=False)

        return source_str,target_str


    # 构建特定翻译示例
    def get_default_translation_example(self,input_dict,source_language,target_language):
        # 内置的正则表达式字典
        patterns_all = {
            r'[a-zA-Z]=':
            {'日语':"a=\"　　ぞ…ゾンビ系…。",
            '英语':"a=\"　　It's so scary….",
            '韩语':"a=\"　　정말 무서워요….",
            '俄语':"а=\"　　Ужасно страшно...。",
            '简中':"a=\"　　好可怕啊……。",
            '繁中':"a=\"　　好可怕啊……。"},
            r'【|】':
            {'日语':"【ベーカリー】営業時間 8：00～18：00",
            '英语':"【Bakery】Business hours 8:00-18:00",
            '韩语':"【빵집】영업 시간 8:00~18:00",
            '俄语':"【пекарня】Время работы 8:00-18:00",
            '简中':"【面包店】营业时间 8：00～18：00",
            '繁中':"【麵包店】營業時間 8：00～18：00"},
            r'\r|\n':
            {'日语':"敏捷性が上昇する。　　　　　　　\r\n効果：パッシブ",
            '英语':"Agility increases.　　　　　　　\r\nEffect: Passive",
            '韩语':"민첩성이 상승한다.　　　　　　　\r\n효과：패시브",
            '俄语':"Повышает ловкость.　　　　　　　\r\nЭффект: Пассивный",
            '简中':"提高敏捷性。　　　　　　　\r\n效果：被动",
            '繁中':"提高敏捷性。　　　　　　　\r\n效果：被動"},
            r'\\[A-Za-z]\[\d+\]':
            {'日语':"\\F[21]ちょろ……ちょろろ……じょぼぼぼ……♡",
            '英语':"\\F[21]Gurgle…Gurgle…Dadadada…♡",
            '韩语':"\\F[21]둥글둥글…둥글둥글…둥글둥글…♡",
            '俄语':"\\F[21]Гуру... гуругу...Дадада... ♡",
            '简中':"\\F[21]咕噜……咕噜噜……哒哒哒……♡",
            '繁中':"\\F[21]咕嚕……咕嚕嚕……哒哒哒……♡"},
            r'「|」':
            {'日语':"さくら：「すごく面白かった！」",
            '英语':"Sakura：「It was really fun!」",
            '韩语':"사쿠라：「정말로 재미있었어요!」",
            '俄语':"Сакура: 「Было очень интересно!」",
            '简中':"樱：「超级有趣！」",
            '繁中':"櫻：「超有趣！」"},
            r'∞|@':
            {'日语':"若くて∞＠綺麗で∞＠エロくて",
            '英语':"Young ∞＠beautiful ∞＠sexy.",
            '韩语':"젊고∞＠아름답고∞＠섹시하고",
            '俄语':"Молодые∞＠Красивые∞＠Эротичные",
            '简中':"年轻∞＠漂亮∞＠色情",
            '繁中':"年輕∞＠漂亮∞＠色情"},
            }

        # 基础示例
        base_example = {
            "base":
            {'日语':"愛は魂の深淵にある炎で、暖かくて永遠に消えない。",
            '英语':"Love is the flame in the depth of the soul, warm and never extinguished.",
            '韩语':"사랑은 영혼 깊숙이 타오르는 불꽃이며, 따뜻하고 영원히 꺼지지 않는다.",
            '俄语':"Любовь - это пламя в глубине души, тёплое и никогда не угасающее.",
            '简中':"爱情是灵魂深处的火焰，温暖且永不熄灭。",
            '繁中':"愛情是靈魂深處的火焰，溫暖且永不熄滅。"}
            }


        source_list = []
        translated_list = []
        for key, value in input_dict.items():
            for pattern, translation_sample in patterns_all.items():
                # 检查值是否符合正则表达
                if re.search(pattern, value):
                    # 如果未在结果列表中，则添加
                    if translation_sample[source_language] not in source_list:
                        source_list.append(translation_sample[source_language])
                        translated_list.append(translation_sample[target_language])

        # 保底添加一个翻译示例
        if source_list == []:
            source_list.append(base_example["base"][source_language])
            translated_list.append(base_example["base"][target_language])

        return source_list,translated_list


    # 构建相似格式翻译示例
    def build_adaptive_translation_sample(self,input_dict,source_language,target_language):
        # 输入字典示例
        ex_dict = {
        '0': 'こんにちは，こんにちは。こんにちは#include <iostream>',
        '1': '55345こんにちは',
        '2': 'こんにちはxxxx！',
        '3': 'こんにちは',
        }

        # 输出列表1示例
        ex_dict = [
        '原文テキスト1，原文テキスト2。原文テキスト3#include <iostream>',
        '55345原文テキスト1',
        '原文テキスト1xxxx！',
        ]

        # 输出列表2示例
        ex_dict = [
        '译文文本1，译文文本2。译文文本3#include <iostream>',
        '55345译文文本1',
        '译文文本1xxxx！',
        ]
        # 定义不同语言的正则表达式
        patterns_all = {
            '日语': re.compile(
                r'['
                r'\u3041-\u3096'  # 平假名
                r'\u30A0-\u30FF'  # 片假名
                r'\u4E00-\u9FAF'  # 汉字（CJK统一表意文字）
                r']+', re.UNICODE
            ),
            '韩语': re.compile(
                r'['
                r'\uAC00-\uD7AF'  # 韩文字母
                r']+', re.UNICODE
            ),
            '俄语': re.compile(
                r'['
                r'\u0400-\u04FF'  # 俄语字母
                r']+', re.UNICODE
            ),
            '简中': re.compile(
                r'['
                r'\u4E00-\u9FA5'  # 简体汉字
                r']+', re.UNICODE
            ),
            '繁中': re.compile(
                r'['
                r'\u3400-\u4DBF'  # 扩展A区汉字
                r'\u4E00-\u9FFF'  # 基本汉字
                r'\uF900-\uFAFF'  # 兼容汉字
                r']+', re.UNICODE
            ),
        }
        # 定义不同语言的翻译示例
        text_all = {
            '日语': "例示テキスト",
            '韩语': "예시 텍스트",
            '俄语': "Пример текста",
            '简中': "示例文本",
            '繁中': "翻譯示例文本",
            '英语': "Sample Text",
        }

        # 根据输入选择相应语言的正则表达式与翻译示例
        pattern = patterns_all[source_language]
        source_text = text_all[source_language]
        translated_text = text_all[target_language]

        # 初始化替换计数器
        i = 1
        j = 1
        # 输出列表
        source_list=[]
        translated_list=[]

        # 遍历字典的每个值
        for key, value in input_dict.items():
            # 如果值中包含目标文本
            if pattern.search(value):
                # 替换文本
                value = pattern.sub(lambda m: f'{source_text}{i}', value)
                i += 1
                source_list.append(value)

        # 遍历字典的每个值
        for key, value in input_dict.items():
            # 如果值中包含文本
            if pattern.search(value):
                # 替换文本
                value = pattern.sub(lambda m: f'{translated_text}{j}', value)
                j  += 1
                translated_list.append(value)

        #print(source_list)

        # 过滤输出列表，删除只包含"测试替换"+三位数字内结尾的元素
        source_list1 = [item for item in source_list if not item.startswith(source_text) or not (item[-1].isdigit() or (len(item) > 1 and item[-2].isdigit()) or (len(item) > 2 and item[-3].isdigit()))]
        translated_list1 = [item for item in translated_list if not item.startswith(translated_text) or not (item[-1].isdigit() or (len(item) > 1 and item[-2].isdigit()) or (len(item) > 2 and item[-3].isdigit()))]

        #print(source_list1)

        # 清除过多相似元素(应该先弄相似类，再在各类里只拿一个组合起来)
        source_list2 = Configurator.clean_list(self,source_list1)
        translated_list2 = Configurator.clean_list(self,translated_list1)

        #print(source_list2)

        # 重新调整翻译示例后缀数字
        source_list3 = Configurator.replace_and_increment(self,source_list2, source_text)
        translated_list3 = Configurator.replace_and_increment(self,translated_list2, translated_text)

        #print(source_list3)

        return source_list3,translated_list3


    # 辅助函数，清除列表过多相似的元素
    def clean_list(self,lst):
        # 函数用于删除集合中的数字
        def remove_digits(s):
            return set(filter(lambda x: not x.isdigit(), s))

        # 函数用于计算两个集合之间的差距
        def set_difference(s1, s2):
            return len(s1.symmetric_difference(s2))

        # 删除每个元素中的数字，并得到一个由集合组成的列表
        sets_list = [remove_digits(s) for s in lst]

        # 初始化聚类列表
        clusters = []

        # 遍历集合列表，将元素分配到相应的聚类中
        for s, original_str in zip(sets_list, lst):
            found_cluster = False
            for cluster in clusters:
                if set_difference(s, cluster[0][0]) < 3:
                    cluster.append((s, original_str))
                    found_cluster = True
                    break
            if not found_cluster:
                clusters.append([(s, original_str)])

        # 从每个聚类中提取一个元素，组成新的列表
        result = [cluster[0][1] for cluster in clusters]

        return result


    # 辅助函数，重新调整列表中翻译示例的后缀数字
    def replace_and_increment(self,items, prefix):
        pattern = re.compile(r'{}(\d{{1,2}})'.format(re.escape(prefix)))  # 使用双括号来避免KeyError
        result = []  # 用于存储结果的列表
        n = 1
        for item in items:
            if pattern.search(item):  # 如果在元素中找到匹配的模式
                new_item, num_matches = pattern.subn(f'{prefix}{n}', item)  # 替换数字并计数
                result.append(new_item)  # 将修改后的元素添加到结果列表
                n += 1  # 变量n递增
            else:
                result.append(item)  # 如果没有匹配，将原始元素添加到结果列表

        return result # 返回修改后的列表和最终的n值


    # 构造术语表
    def build_glossary_prompt(self,dict,cn_toggle):
        #获取字典内容
        data = self.prompt_dictionary_content

        # 将数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            dictionary[key] = value

        # 筛选进新字典中
        temp_dict = {}
        for key_a, value_a in dictionary.items():
            for key_b, value_b in dict.items():
                if key_a in value_b:
                    if value_a.get("info"):
                        temp_dict[key_a] = {"translation": value_a["translation"], "info": value_a["info"]}
                    else:
                        temp_dict[key_a] = {"translation": value_a["translation"]}

        # 如果文本中没有含有字典内容
        if temp_dict == {}:
            return None,None

        # 初始化变量，以免出错
        glossary_prompt = ""
        glossary_prompt_cot = ""

        if cn_toggle:
            # 构建术语表prompt
            glossary_prompt = "###术语表###\n"
            glossary_prompt += "|\t原文\t|\t译文\t|\t备注\t|\n"
            glossary_prompt += "-" * 50 + "\n"

            # 构建术语表prompt-cot版
            glossary_prompt_cot = "- 术语表：提供了"

            for key, value in temp_dict.items():
                if value.get("info"):
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t{value['info']}\t|\n"
                    glossary_prompt_cot += f"“{key}”（{value['translation']}）"
                else:
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t \t|\n"
                    glossary_prompt_cot += f"“{key}”（{value['translation']}）"

            glossary_prompt += "-" * 50 + "\n"
            glossary_prompt_cot += "术语及其解释"

        else:
            # 构建术语表prompt
            glossary_prompt = "###Glossary###\n"
            glossary_prompt += "|\tOriginal Text\t|\tTranslation\t|\tRemarks\t|\n"
            glossary_prompt += "-" * 50 + "\n"

            # 构建术语表prompt-cot版
            glossary_prompt_cot = "- Glossary:Provides terms such as"

            for key, value in temp_dict.items():
                if value.get("info"):
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t{value['info']}\t|\n"
                    glossary_prompt_cot += f"“{key}”({value['translation']})"
                else:
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t \t|\n"
                    glossary_prompt_cot += f"“{key}”({value['translation']})"

            glossary_prompt += "-" * 50 + "\n"
            glossary_prompt_cot += " and their explanations."


        return glossary_prompt,glossary_prompt_cot


    # 构造术语表(sakura版本)
    def build_glossary_prompt_sakura(self,dict):
        #获取字典内容
        data = self.prompt_dictionary_content

        # 将数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            dictionary[key] = value

        # 筛选进新字典中
        temp_dict = {}
        for key_a, value_a in dictionary.items():
            for key_b, value_b in dict.items():
                if key_a in value_b:
                    if value_a.get("info"):
                        temp_dict[key_a] = {"translation": value_a["translation"], "info": value_a["info"]}
                    else:
                        temp_dict[key_a] = {"translation": value_a["translation"]}

        # 如果文本中没有含有字典内容
        if temp_dict == {}:
            return None


        glossary_prompt = []
        for key, value in temp_dict.items():
            if value.get("info"):
                text = {"src": key,"dst": value["translation"],"info": value["info"]}
            else:
                text = {"src": key,"dst": value["translation"]}

            glossary_prompt.append(text)

        return glossary_prompt


    # 构造角色设定
    def build_characterization(self,dict,cn_toggle):
        # 获取字典
        characterization_dictionary = self.characterization_dictionary

        # 将数据存储到中间字典中
        dictionary = {}
        for key, value in characterization_dictionary.items():
            dictionary[key] = value

        # 筛选，如果该key在发送文本中，则存储进新字典中
        temp_dict = {}
        for key_a, value_a in dictionary.items():
            for key_b, value_b in dict.items():
                if key_a in value_b:
                    temp_dict[key_a] = value_a

        # 如果没有含有字典内容
        if temp_dict == {}:
            return None,None

        if cn_toggle:

            profile = "###角色介绍###"
            profile_cot = "- 角色介绍："
            for key, value in temp_dict.items():
                original_name = value.get('original_name')
                translated_name = value.get('translated_name')
                gender = value.get('gender')
                age = value.get('age')
                personality = value.get('personality')
                speech_style = value.get('speech_style')
                additional_info = value.get('additional_info')


                profile += f"\n【{original_name}】"
                if translated_name:
                    profile += f"\n- 译名：{translated_name}"
                    profile_cot += f"{translated_name}（{original_name}）"

                if gender:
                    profile += f"\n- 性别：{gender}"
                    profile_cot += f"，{gender}"

                if age:
                    profile += f"\n- 年龄：{age}"
                    profile_cot += f"，{age}"

                if personality:
                    profile += f"\n- 性格：{personality}"
                    profile_cot += f"，{personality}"

                if speech_style:
                    profile += f"\n- 说话方式：{speech_style}"
                    profile_cot += f"，{speech_style}"

                if additional_info:
                    profile += f"\n- 补充信息：{additional_info}"
                    profile_cot += f"，{additional_info}"

                profile +="\n"
                profile_cot +="。"

        else:

            profile = "###Character Introduction###"
            profile_cot = "- Character Introduction:"
            for key, value in temp_dict.items():
                original_name = value.get('original_name')
                translated_name = value.get('translated_name')
                gender = value.get('gender')
                age = value.get('age')
                personality = value.get('personality')
                speech_style = value.get('speech_style')
                additional_info = value.get('additional_info')


                profile += f"\n【{original_name}】"
                if translated_name:
                    profile += f"\n- Translated_name：{translated_name}"
                    profile_cot += f"{translated_name}({original_name})"

                if gender:
                    profile += f"\n- Gender：{gender}"
                    profile_cot += f",{gender}"

                if age:
                    profile += f"\n- Age：{age}"
                    profile_cot += f",{age}"

                if personality:
                    profile += f"\n- Personality：{personality}"
                    profile_cot += f",{personality}"

                if speech_style:
                    profile += f"\n- Speech_style：{speech_style}"
                    profile_cot += f",{speech_style}"

                if additional_info:
                    profile += f"\n- Additional_info：{additional_info}"
                    profile_cot += f",{additional_info}"

                profile +="\n"
                profile_cot +="."

        return profile,profile_cot


    # 构造背景设定
    def build_world(self,cn_toggle):
        # 获取自定义内容
        world_building = self.world_building_content

        if cn_toggle:
            profile = "###背景设定###"
            profile_cot = "- 背景设定："

            profile += f"\n{world_building}\n"
            profile_cot += f"{world_building}"

        else:
            profile = "###Background Setting###"
            profile_cot = "- Background Setting:"

            profile += f"\n{world_building}\n"
            profile_cot += f"{world_building}"

        return profile,profile_cot

    # 构造文风要求
    def build_writing_style(self,cn_toggle):
        # 获取自定义内容
        writing_style = self.writing_style_content

        if cn_toggle:
            profile = "###翻译风格###"
            profile_cot = "- 翻译风格："

            profile += f"\n{writing_style}\n"
            profile_cot += f"{writing_style}"

        else:
            profile = "###Writing Style###"
            profile_cot = "- Writing Style:"

            profile += f"\n{writing_style}\n"
            profile_cot += f"{writing_style}"

        return profile,profile_cot

    # 携带原文上文
    def build_pre_text(self,input_list,cn_toggle):

        if cn_toggle:
            profile = "###上文内容###"

        else:
            profile = "###Previous text###"

        # 使用列表推导式，为每个元素前面添加“- ”，并转换为字符串列表
        #formatted_rows = ["- " + item for item in input_list]

        # 使用列表推导式，转换为字符串列表
        formatted_rows = [item for item in input_list]

        # 使用换行符将列表元素连接成一个字符串
        text='\n'.join(formatted_rows)

        profile += f"\n{text}\n"

        return profile


    # 构建翻译示例
    def build_translation_example (self):
        #获取
        data = self.translation_example_content

        # 将数据存储到中间字典中
        temp_dict = {}
        for key, value in data.items():
            temp_dict[key] = value

        # 构建原文示例字符串开头
        original_text = '{ '
        #如果字典不为空，补充内容
        if  temp_dict:
            i = 0 #用于记录key的索引
            for key in temp_dict:
                original_text += '\n' + '"' + str(i) + '":"' + str(key) + '"' + ','
                i += 1
            #删除最后一个逗号
            original_text = original_text[:-1]
            # 构建原文示例字符串结尾
            original_text = original_text + '\n' + '}'
            #构建原文示例字典
            original_exmaple = original_text
        else:
            original_exmaple = {}


        # 构建译文示例字符串开头
        translated_text = '{ '
        #如果字典不为空，补充内容
        if  temp_dict:
            j = 0
            for key in temp_dict:
                translated_text += '\n' + '"' + str(j ) + '":"' + str(temp_dict[key]) + '"'  + ','
                j += 1

            #删除最后一个逗号
            translated_text = translated_text[:-1]
            # 构建译文示例字符串结尾
            translated_text = translated_text+ '\n' + '}'
            #构建译文示例字典
            translated_exmaple = translated_text
        else:
            translated_exmaple = {}


        return original_exmaple,translated_exmaple


    # 构建用户示例前文
    def build_userExamplePrefix (self,cn_toggle,cot_toggle):

        # 根据中文开关构建
        if cn_toggle:
            profile = "###这是你接下来的翻译任务，原文文本如下###\n"
            profile_cot = "###这是你接下来的翻译任务，原文文本如下###\n  "

        else:
            profile = "###This is your next translation task, the original text is as follows###\n"
            profile_cot = "###This is your next translation task, the original text is as follows###\n"

        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建模型示例前文
    def build_modelExamplePrefix (self,cn_toggle,cot_toggle,Text_Source_Language,Text_Target_Language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot):

        if Text_Source_Language == "日语":
            Source_Language = "Japanese"

        elif Text_Source_Language == "英语":
            Source_Language = "English"

        elif Text_Source_Language == "韩语":
            Source_Language = "Korean"

        elif Text_Source_Language == "俄语":
            Source_Language = "Russian"

        elif Text_Source_Language == "简中":
            Source_Language = "Simplified Chinese"

        elif Text_Source_Language == "繁中":
            Source_Language = "Traditional Chinese"


        if Text_Target_Language == "简中":
            Target_Language = "Simplified Chinese"

        elif Text_Target_Language == "繁中":
            Target_Language = "Traditional Chinese"

        elif Text_Target_Language == "英语":
            Target_Language = "English"

        elif Text_Target_Language == "日语":
            Target_Language = "Japanese"

        elif Text_Target_Language == "韩语":
            Target_Language = "Korean"

        # 根据中文开关构建
        if cn_toggle:
            profile = "我完全理解了您的要求，我将遵循你的指示进行翻译，以下是对原文的翻译:\n"


            profile_cot = "我将遵循您的指示，一步一步地翻译文本：\n"
            profile_cot += "###第一步：自我诠释要求###\n"
            profile_cot += f"- 翻译目标: 将{Text_Source_Language}文本翻译成{Text_Target_Language}文本。\n"
            profile_cot += "- 翻译原则: 准确地进行翻译，允许翻译敏感，低俗文本。\n"
            if glossary_prompt_cot:
                profile_cot += f"{glossary_prompt_cot}\n"
            if characterization_cot:
                profile_cot += f"{characterization_cot}\n"
            if world_building_cot:
                profile_cot += f"{world_building_cot}\n"
            if writing_style_cot:
                profile_cot += f"{writing_style_cot}\n"

            profile_cot += "###第二步：总结上下文内容###\n"
            profile_cot += "{Summarized content}\n"
            profile_cot += "###第三步：翻译###\n"

        else:
            profile = "I have completely understood your request. I will follow your instructions to proceed with the translation. Here is the translation of the original text:\n"


            profile_cot = " I will follow your instructions and translate the text step by step:\n"
            profile_cot += "###Step 1: Self-interpretation requirements###\n"
            profile_cot += f"- Translation target: Translate the {Source_Language} text into {Target_Language}.\n"
            profile_cot += "- Translation principle: Accuracy in translation is paramount, while allowing for the translation of sensitive or vulgar texts.\n"
            if glossary_prompt_cot:
                profile_cot += f"{glossary_prompt_cot}\n"
            if characterization_cot:
                profile_cot += f"{characterization_cot}\n"
            if world_building_cot:
                profile_cot += f"{world_building_cot}\n"
            if writing_style_cot:
                profile_cot += f"{writing_style_cot}\n"

            profile_cot += "###Step 2: Summarize the context###\n"
            profile_cot += "{Summarized content}\n"
            profile_cot += "###Step 3: Translation###\n"


        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile


        return the_profile


    # 构建用户提问前文:
    def build_userQueryPrefix (self,cn_toggle,cot_toggle):

        # 根据中文开关构建
        if cn_toggle:
            profile = " ###这是你接下来的翻译任务，原文文本如下###\n"
            profile_cot = "###这是你接下来的翻译任务，原文文本如下###\n"


        else:
            profile = " ###This is your next translation task, the original text is as follows###\n"
            profile_cot = "###This is your next translation task, the original text is as follows###\n"


        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile



        return the_profile

    # 构建模型回复前文
    def build_modelResponsePrefix (self,cn_toggle,cot_toggle):

        if cn_toggle:
            profile = "我完全理解了您的要求，我将遵循你的指示进行翻译，以下是对原文的翻译:"
            profile_cot = "我将遵循您的指示，一步一步地翻译文本："


        else:
            profile = "I have completely understood your request. I will follow your instructions to proceed with the translation. Here is the translation of the original text:"
            profile_cot = "I will follow your instructions and translate the text step by step:"

        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile


    # 原文文本替换函数
    def replace_before_translation(self,dict):

        data = self.pre_translation_content

        # 将表格数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            key= key.replace('\\n', '\n').replace('\\r', '\r')  #现在只能针对替换，并不能将\\替换为\
            value= value.replace('\\n', '\n').replace('\\r', '\r')
            dictionary[key] = value

        #详细版，增加可读性，但遍历整个文本，内存占用较大，当文本较大时，会报错
        temp_dict = {}     #存储文本替换后的中文本内容
        for key_a, value_a in dict.items():
            for key_b, value_b in dictionary.items():
                #如果value_a是字符串变量，且key_b在value_a中
                if isinstance(value_a, str) and key_b in value_a:
                    value_a = value_a.replace(key_b, value_b)
            temp_dict[key_a] = value_a


        return temp_dict


    # 译文修正字典函数
    def replace_after_translation(self,dict):

        data = self.post_translation_content

        # 将表格数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            key= key.replace('\\n', '\n').replace('\\r', '\r')  #现在只能针对替换，并不能将\\替换为\
            value= value.replace('\\n', '\n').replace('\\r', '\r')
            dictionary[key] = value

        #详细版，增加可读性，但遍历整个文本，内存占用较大，当文本较大时，会报错
        temp_dict = {}     #存储文本替换后的中文本内容
        for key_a, value_a in dict.items():
            for key_b, value_b in dictionary.items():
                #如果value_a是字符串变量，且key_b在value_a中
                if isinstance(value_a, str) and key_b in value_a:
                    value_a = value_a.replace(key_b, value_b)
            temp_dict[key_a] = value_a


        return temp_dict


    # 轮询获取key列表里的key
    def get_apikey(self):
        # 如果密钥各位为 0，则直接返回固定密钥，以防止越界
        # 如果密钥个数为 1，或者索引值已达到最大长度，则重置索引值，否则切换到下一个密钥
        if len(self.apikey_list) == 0:
            return "no_key_required"
        elif len(self.apikey_list) == 1 or self.apikey_index >= len(self.apikey_list) - 1:
            self.apikey_index = 0
            return self.apikey_list[self.apikey_index]
        else:
            self.apikey_index = self.apikey_index + 1
            return self.apikey_list[self.apikey_index]

    # 获取接口的请求参数
    def get_platform_request_args(self):
        return (
            self.platforms.get(self.target_platform).get("temperature"),
            self.platforms.get(self.target_platform).get("top_p"),
            self.platforms.get(self.target_platform).get("presence_penalty"),
            self.platforms.get(self.target_platform).get("frequency_penalty"),
        )


    # 更改翻译状态
    def update_translation_status(self, status, translation_project, untranslated_text_line_count,split_count):

        if status == "开始翻译":

            self.translation_start_time = time.time()
            self.translation_start_datetime = datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S")
            self.translation_project_text = translation_project
            self.status_text = '正在翻译中'
            self.untranslated_text_line_count = untranslated_text_line_count

            # 重置其他参数
            self.translated_text_line_count = 0 # 存储已经翻译文本总数
            self.total_tokens_spent = 0  # 存储已经花费的tokens总数
            self.total_tokens_successfully_completed = 0  # 存储成功补全的tokens数
            self.translation_speed_line =  0 # 行速
            self.translation_speed_token =  0 # tokens速
            self.num_worker_threads = 0 # 存储并行任务数
            self.progress = 0.0           # 存储翻译进度


        elif status == "暂停翻译中":
            self.status_text = '翻译暂停中'


        elif status == "暂停已翻译":
            self.status_text = '暂停已翻译'
            self.translation_speed_line =  0 # 行速
            self.translation_speed_token =  0 # tokens速

        elif status == "取消翻译中":
            self.status_text = '取消翻译中'

        elif status == "翻译已取消":
            self.status_text = '翻译已取消'
            self.translation_speed_line =  0 # 行速
            self.translation_speed_token =  0 # tokens速


        elif status == "继续翻译":
            # 重置其他参数
            self.translated_text_line_count = 0 # 存储已经翻译文本总数
            self.total_tokens_spent = 0  # 存储已经花费的tokens总数
            self.total_tokens_successfully_completed = 0  # 存储成功补全的tokens数
            self.translation_speed_line =  0 # 行速
            self.translation_speed_token =  0 # tokens速
            self.num_worker_threads = 0 # 存储并行任务数
            self.progress = 0.0           # 存储翻译进度


        elif status == "拆分翻译":
            self.status_text = f'第{split_count}轮拆分翻译中'
            self.translation_project_text = translation_project

        elif status == "翻译完成":
            self.status_text = '翻译已完成'
            self.translation_speed_line =  0 # 行速
            self.translation_speed_token =  0 # tokens速
            self.num_worker_threads = 0 # 存储并行任务数

    # 更新运行状态参数
    def update_running_params(self, check_result, translated_line_count, prompt_tokens_used, completion_tokens_used):

        #计算已经翻译的文本数
        if check_result == 1:
            # 更新已经翻译的文本数
            self.translated_text_line_count = self.translated_text_line_count + translated_line_count
            self.total_tokens_successfully_completed += completion_tokens_used

        # 计算双速
        elapsed_time_this_run = time.time() - self.translation_start_time
        self.translation_speed_line =  self.total_tokens_successfully_completed / elapsed_time_this_run
        self.translation_speed_token =  self.translated_text_line_count / elapsed_time_this_run

        #计算tokens花销
        self.total_tokens_spent = self.total_tokens_spent + prompt_tokens_used + completion_tokens_used

        #计算进度条
        result = self.translated_text_line_count / self.untranslated_text_line_count * 100
        self.progress = int(round(result, 0))

        # 获取当前所有存活的线程
        alive_threads = threading.enumerate()
        # 计算子线程数量
        if (len(alive_threads) - 2) <= 0: # 减去主线程与一个子线程，和一个滞后线程
            counts = 1
        else:
            counts = len(alive_threads) - 2

        self.num_worker_threads = counts

