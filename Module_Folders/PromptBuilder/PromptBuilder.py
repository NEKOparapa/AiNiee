import re
from types import SimpleNamespace

import rapidjson as json

from Base.Base import Base
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig
from Module_Folders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum

class PromptBuilder(Base):
    def __init__(self) -> None:
        super().__init__()

    # 获取默认系统提示词，优先从内存中读取，如果没有，则从文件中读取
    def get_system_default(config: TranslatorConfig) -> str:
        if getattr(PromptBuilder, "common_system_zh", None) == None:
            with open("./Resource/Prompt/common_system_zh.txt", "r", encoding = "utf-8") as reader:
                PromptBuilder.common_system_zh = reader.read().strip()
        if getattr(PromptBuilder, "common_system_en", None) == None:
            with open("./Resource/Prompt/common_system_en.txt", "r", encoding = "utf-8") as reader:
                PromptBuilder.common_system_en = reader.read().strip()
        if getattr(PromptBuilder, "cot_system_zh", None) == None:
            with open("./Resource/Prompt/cot_system_zh.txt", "r", encoding = "utf-8") as reader:
                PromptBuilder.cot_system_zh = reader.read().strip()
        if getattr(PromptBuilder, "cot_system_en", None) == None:
            with open("./Resource/Prompt/cot_system_en.txt", "r", encoding = "utf-8") as reader:
                PromptBuilder.cot_system_en = reader.read().strip()


        # 如果输入的是字典，则转换为命名空间
        if isinstance(config, dict):
            namespace = SimpleNamespace()
            for key, value in config.items():
                setattr(namespace, key, value)
            config = namespace

        # 构造结果
        if config == None:
            result = PromptBuilder.common_system_zh
        elif config.prompt_preset == PromptBuilderEnum.COMMON and config.target_language in ("简中", "繁中"):
            result = PromptBuilder.common_system_zh
        elif config.prompt_preset == PromptBuilderEnum.COMMON and config.target_language not in ("简中", "繁中"):
            result = PromptBuilder.common_system_en
        elif config.prompt_preset == PromptBuilderEnum.COT and config.target_language in ("简中", "繁中"):
            result = PromptBuilder.cot_system_zh
        elif config.prompt_preset == PromptBuilderEnum.COT and config.target_language not in ("简中", "繁中"):
            result = PromptBuilder.cot_system_en

        return result

    # 获取系统提示词
    def build_system(config: TranslatorConfig) -> str:
        PromptBuilder.get_system_default(config)

        pair = {
            "日语": "Japanese",
            "英语": "English",
            "韩语": "Korean", 
            "俄语": "Russian",
            "简中": "Simplified Chinese",
            "繁中": "Traditional Chinese"
        }

        source_language = config.source_language
        target_language = config.target_language
        # 构造结果
        if config == None:
            result = PromptBuilder.common_system_zh
        elif config.prompt_preset == PromptBuilderEnum.COMMON and config.target_language in ("简中", "繁中"):
            result = PromptBuilder.common_system_zh
        elif config.prompt_preset == PromptBuilderEnum.COMMON and config.target_language not in ("简中", "繁中"):
            result = PromptBuilder.common_system_en
            source_language = pair[config.source_language]
            target_language = pair[config.target_language]
        elif config.prompt_preset == PromptBuilderEnum.COT and config.target_language in ("简中", "繁中"):
            result = PromptBuilder.cot_system_zh
        elif config.prompt_preset == PromptBuilderEnum.COT and config.target_language not in ("简中", "繁中"):
            result = PromptBuilder.cot_system_en
            source_language = pair[config.source_language]
            target_language = pair[config.target_language]

        return result.replace("{source_language}", source_language).replace("{target_language}", target_language).strip()

    # 构建翻译示例
    def build_translation_sample(config: TranslatorConfig, input_dict: dict) -> tuple[str, str]:
        list1 = []
        list3 = []
        list2 = []
        list4 = []

        # 获取特定示例
        #list1, list3 = PromptBuilder.get_default_translation_example(config, input_dict)

        # 获取自适应示例（无法构建英语的）
        if config.source_language in ["日语","韩语","俄语","简中","繁中"]:
            list2, list4 = PromptBuilder.build_adaptive_translation_sample(config, input_dict)

        # 将两个列表合并
        combined_list = list1 + list2
        combined_list2 = list3 + list4

        # 如果都没有示例则添加基础示例
        if not combined_list:
            base_example = {
                "base": {
                    "日语": "例示テキスト",
                    "韩语": "예시 텍스트",
                    "俄语": "Пример текста",
                    "简中": "示例文本",
                    "繁中": "翻譯示例文本",
                    "英语": "Sample Text",
                }
            }

            combined_list.append(base_example["base"][config.source_language])
            combined_list2.append(base_example["base"][config.target_language])

        # 限制示例总数量为3个，如果多了，则从最后往前开始削减
        if len(combined_list) > 3:
            combined_list = combined_list[:3]
            combined_list2 = combined_list2[:3]


        # 创建空字典
        source_dict = {}
        target_dict = {}
        source_str = ""
        target_str = ""

        # 遍历合并后的列表，并创建键值对
        for index, value in enumerate(combined_list):
            source_dict[str(index)] = value
        for index, value in enumerate(combined_list2):
            target_dict[str(index)] = value

        # 将原文本字典转换成行文本，并加上数字序号
        if source_dict:

            source_numbered_lines = []
            for index_s, line in enumerate(source_dict.values()):
                source_numbered_lines.append(f"{index_s + 1}. {line}") # 添加序号和 "." 分隔符

            target_numbered_lines = []
            for index_t, line in enumerate(target_dict.values()):
                target_numbered_lines.append(f"{index_t + 1}. {line}") # 添加序号和 "." 分隔符

            source_str = "\n".join( source_numbered_lines)
            target_str = "\n".join( target_numbered_lines)

        return source_str, target_str

    # 辅助函数，构建特定翻译示例
    def get_default_translation_example(config: TranslatorConfig, input_dict: dict) -> tuple[list[str], list[str]]:
        # 内置的正则表达式字典
        source_list = []
        translated_list = []

        # 内置的正则表达式字典
        patterns_all = {
            r"[a-zA-Z]=": {
                "日语": 'a="　　ぞ…ゾンビ系…。',
                "英语": "a=\"　　It's so scary….",
                "韩语": 'a="　　정말 무서워요….',
                "俄语": 'а="　　Ужасно страшно...。',
                "简中": 'a="　　好可怕啊……。',
                "繁中": 'a="　　好可怕啊……。'},
            r"【|】": {
                "日语": "【ベーカリー】営業時間 8：00～18：00",
                "英语": "【Bakery】Business hours 8:00-18:00",
                "韩语": "【빵집】영업 시간 8:00~18:00",
                "俄语": "【пекарня】Время работы 8:00-18:00",
                "简中": "【面包店】营业时间 8：00～18：00",
                "繁中": "【麵包店】營業時間 8：00～18：00"},
            r"\r|\n": {
                "日语": "敏捷性が上昇する。　　　　　　　\r\n効果：パッシブ",
                "英语": "Agility increases.　　　　　　　\r\nEffect: Passive",
                "韩语": "민첩성이 상승한다.　　　　　　　\r\n효과：패시브",
                "俄语": "Повышает ловкость.　　　　　　　\r\nЭффект: Пассивный",
                "简中": "提高敏捷性。　　　　　　　\r\n效果：被动",
                "繁中": "提高敏捷性。　　　　　　　\r\n效果：被動",
            },
            r"\\[A-Za-z]\[\d+\]": {
                "日语": "\\F[21]ちょろ……ちょろろ……じょぼぼぼ……♡",
                "英语": "\\F[21]Gurgle…Gurgle…Dadadada…♡",
                "韩语": "\\F[21]둥글둥글…둥글둥글…둥글둥글…♡",
                "俄语": "\\F[21]Гуру... гуругу...Дадада... ♡",
                "简中": "\\F[21]咕噜……咕噜噜……哒哒哒……♡",
                "繁中": "\\F[21]咕嚕……咕嚕嚕……哒哒哒……♡"},
            r"「|」":{
                    "日语": "キャラクターA：「すごく面白かった！」",
                    "英语": "Character A：「It was really fun!」",
                    "韩语": "캐릭터 A：「정말로 재미있었어요!」",
                    "俄语": "Персонаж A: 「Было очень интересно!」",
                    "简中": "角色A：「超级有趣！」",
                    "繁中": "角色A：「超有趣！」"
                    },
            r"∞|@": {
                "日语": "若くて∞＠綺麗で∞＠エロくて",
                "英语": "Young ∞＠beautiful ∞＠sexy.",
                "韩语": "젊고∞＠아름답고∞＠섹시하고",
                "俄语": "Молодые∞＠Красивые∞＠Эротичные",
                "简中": "年轻∞＠漂亮∞＠色情",
                "繁中": "年輕∞＠漂亮∞＠色情"},
            r"↓": {
                "日语": "若くて↓綺麗で↓↓エロくて",
                "英语": "Young ↓beautiful ↓↓sexy.",
                "韩语": "젊고↓아름답고↓↓섹시하고",
                "俄语": "Молодые↓Красивые↓↓Эротичные",
                "简中": "年轻↓漂亮↓↓色情",
                "繁中": "年輕↓漂亮↓↓色情"},
        }

        for _, value in input_dict.items():
            for pattern, translation_sample in patterns_all.items():
                # 检查值是否符合正则表达
                if re.search(pattern, value):
                    # 如果未在结果列表中，则添加
                    if translation_sample[config.source_language] not in source_list:
                        source_list.append(translation_sample[config.source_language])
                        translated_list.append(translation_sample[config.target_language])


        return source_list, translated_list

    # 辅助函数，清除列表过多相似的元素
    def clean_list(lst) -> list[str]:
        # 函数用于删除集合中的数字
        def remove_digits(s) -> set:
            return set(filter(lambda x: not x.isdigit(), s))

        # 函数用于计算两个集合之间的差距
        def set_difference(s1, s2) -> int:
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
    def replace_and_increment(items, prefix) -> list[str]:
        pattern = re.compile(r"{}(\d{{1,2}})".format(re.escape(prefix)))  # 使用双括号来避免KeyError
        result = []  # 用于存储结果的列表
        n = 0
        p = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']

        for item in items:
            if pattern.search(item):  # 如果在元素中找到匹配的模式
                new_item = item
                j = 1  # 初始化 j
                while True:

                    # 正则匹配
                    match = pattern.search(new_item)

                    # 如果没有匹配到，退出
                    if not match:
                        break

                    # 防止列表循环越界
                    if n >= 24:
                        #print("bug")
                        n = 0

                    # 替换示例文本后缀
                    new_item = new_item[:match.start()] + f"{prefix}{p[n]}-{j}" + new_item[match.end():]

                    # 在每次替换后递增 j
                    j += 1

                # 替换完之后添加进结果列表
                result.append(new_item)

                # 变量n递增
                n += 1
            else:
                result.append(item)  # 如果没有匹配，将原始元素添加到结果列表

        return result  # 返回修改后的列表

    # 构建相似格式翻译示例
    def build_adaptive_translation_sample(config: TranslatorConfig, input_dict: dict) -> tuple[list[str], list[str]]:
        # 输入字典示例
        # ex_dict = {
        #     "0": "こんにちは，こんにちは。こんにちは#include <iostream>",
        #     "1": "55345こんにちは",
        #     "2": "こんにちはxxxx！",
        #     "3": "こんにちは",
        # }

        # 输出列表1示例
        # ex_dict = [
        #     "原文テキストA-1，原文テキストA-2。原文テキストA-3#include <iostream>",
        #     "55345原文テキストB-1",
        #     "原文テキストC-1xxxx！",
        # ]

        # 输出列表2示例
        # ex_dict = [
        #     "译文文本A-1，译文文本A-2。译文文本A-3#include <iostream>",
        #     "55345译文文本B-1",
        #     "译文文本C-1xxxx！",
        # ]

        # 定义不同语言的正则表达式
        patterns_all = {
            "日语": re.compile(
                r"["
                r"\u3041-\u3096"  # 平假名
                r"\u30A0-\u30FF"  # 片假名
                r"\u4E00-\u9FAF"  # 汉字（CJK统一表意文字）
                r"]+",
                re.UNICODE,
            ),
            "韩语": re.compile(
                r"["
                r"\uAC00-\uD7AF"  # 韩文字母
                r"]+",
                re.UNICODE,
            ),
            "俄语": re.compile(
                r"["
                r"\u0400-\u04FF"  # 俄语字母
                r"]+",
                re.UNICODE,
            ),
            "简中": re.compile(
                r"["
                r"\u4E00-\u9FA5"  # 简体汉字
                r"]+",
                re.UNICODE,
            ),
            "繁中": re.compile(
                r"["
                r"\u3400-\u4DBF"  # 扩展A区汉字
                r"\u4E00-\u9FFF"  # 基本汉字
                r"\uF900-\uFAFF"  # 兼容汉字
                r"]+",
                re.UNICODE,
            ),
        }

        # 定义不同语言的翻译示例
        text_all = {
            "日语": "例示テキスト",
            "韩语": "예시 텍스트",
            "俄语": "Пример текста",
            "简中": "示例文本",
            "繁中": "翻譯示例文本",
            "英语": "Sample Text",
        }

        # 根据输入选择相应语言的正则表达式与翻译示例
        pattern = patterns_all[config.source_language]
        source_text = text_all[config.source_language]
        translated_text = text_all[config.target_language]

        # 输出列表
        source_list = []
        translated_list = []

        # 初始化
        i = 1
        j = 1

        # 遍历字典的每个值
        for _, value in input_dict.items():
            if pattern.search(value):
                # 替换文本
                source_value = pattern.sub(lambda m: f"{source_text}{i}", value)
                translated_value = pattern.sub(lambda m: f"{translated_text}{j}", value)
                i += 1
                j += 1
                source_list.append(source_value)
                translated_list.append(translated_value)

        # 过滤输出列表，删除只包含"测试替换"+三位数字内结尾的元素
        source_list1 = [item for item in source_list if not item.startswith(source_text) or not (item[-1].isdigit() or (len(item) > 1 and item[-2].isdigit()) or (len(item) > 2 and item[-3].isdigit()))]
        translated_list1 = [item for item in translated_list if not item.startswith(translated_text) or not (item[-1].isdigit() or (len(item) > 1 and item[-2].isdigit()) or (len(item) > 2 and item[-3].isdigit()))]

        # 清除过多相似元素
        source_list2 = PromptBuilder.clean_list(source_list1)
        translated_list2 = PromptBuilder.clean_list(translated_list1)

        # 重新调整翻译示例后缀数字
        source_list3 = PromptBuilder.replace_and_increment(source_list2, source_text)
        translated_list3 = PromptBuilder.replace_and_increment(translated_list2, translated_text)

        return source_list3, translated_list3

    # 构造术语表
    def build_glossary_prompt(config: TranslatorConfig, input_dict: dict) -> str:
        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result = [
            v for v in config.prompt_dictionary_data
            if any(v.get("src") in lines for lines in lines)
        ]

        # 数据校验
        if len(result) == 0:
            return ""

        # 初始化变量，以免出错
        glossary_prompt_lines = []

        if config.target_language in ("简中", "繁中"):
            # 添加开头
            glossary_prompt_lines.append(
                "\n###术语表"
                + "\n" + "原文|译文|备注"
            )

            # 添加数据
            for v in result:
                glossary_prompt_lines.append(f"{v.get("src")}|{v.get("dst")}|{v.get("info") if v.get("info") != "" else " "}")

        else:
            # 添加开头
            glossary_prompt_lines.append(
                "\n###Glossary"
                + "\n" + "Original Text|Translation|Remarks"
            )

            # 添加数据
            for v in result:
                glossary_prompt_lines.append(f"{v.get("src")}|{v.get("dst")}|{v.get("info") if v.get("info") != "" else " "}")


        # 拼接成最终的字符串
        glossary_prompt = "\n".join(glossary_prompt_lines)

        return glossary_prompt

    # 构造提取术语表要求
    def build_glossary_extraction_criteria(config: TranslatorConfig) -> str:

        if config.target_language in ("简中", "繁中"):
            profile = "\n\n###提取文本中角色名，以glossary标签返回\n"
            profile += "<glossary>\n"
            profile += "原文|译文|备注\n"
            profile += "</glossary>\n"
        else:
            profile = "\n\n### Extract character names from the text and return them using glossary tags\n"
            profile += "<glossary>\n"
            profile += "Original Text|Translation|Remarks\n"
            profile += "</glossary>\n"

        return profile

    # 构造禁翻表
    def build_ntl_prompt(config: TranslatorConfig, source_text_dict) -> str:

        # 获取禁翻表内容
        exclusion_list_data = config.exclusion_list_data.copy()


        exclusion_dict = {}  # 用字典存储并自动去重
        texts = list(source_text_dict.values())
        
        # 处理正则匹配
        for element in exclusion_list_data:
            regex = element.get("regex", "").strip()
            info = element.get("info", "")
            
            if regex:
                try:
                    pattern = re.compile(regex)
                    for text in texts:
                        for match in pattern.finditer(text):
                            markers = match.group(0)
                            if markers not in exclusion_dict:
                                exclusion_dict[markers] = info
                except re.error:
                    pass
        
        # 处理示例检查
        for element in exclusion_list_data:
            markers = element.get("markers", "").strip()
            info = element.get("info", "")
            
            if markers:
                # 检查示例是否存在于任意文本中
                found = any(markers in text for text in texts)
                if found and markers not in exclusion_dict:
                    exclusion_dict[markers] = info
        
        # 检查内容是否为空
        if not exclusion_dict :
            return ""

        # 构建结果字符串
        if config.target_language in ("简中", "繁中"):
            result = "\n###禁翻表"
        else:
            result = "\n###Non-Translation List"

        for markers, info in exclusion_dict.items():
            result += f"\n{markers}|{info}" if info else f"\n{markers}|"
        
        return result

    # 构造提取禁翻表要求
    def build_ntl_extraction_criteria(config: TranslatorConfig) -> str:

        if config.target_language in ("简中", "繁中"):
            profile = "\n\n###提取文本中标记符，如 {name}, //F[N1],以code标签返回\n"
            profile += "<code>\n"
            profile += "标记符|备注\n"
            profile += "</code>\n"
        else:
            profile = "\n\n### Extract markers from the text, such as {name}, //F[N1], and return them within `code` tags\n"
            profile += "<code>\n"
            profile += "Marker|Remarks\n"
            profile += "</code>\n"

        return profile

    # 构造角色设定
    def build_characterization(config: TranslatorConfig, input_dict: dict) -> str:
        # 将数据存储到中间字典中
        dictionary = {}
        for v in config.characterization_data:
            dictionary[v.get("original_name", "")] = v

        # 筛选，如果该key在发送文本中，则存储进新字典中
        temp_dict = {}
        for key_a, value_a in dictionary.items():
            for _, value_b in input_dict.items():
                if key_a in value_b:
                    temp_dict[key_a] = value_a

        # 如果没有含有字典内容
        if temp_dict == {}:
            return ""

        if config.target_language in ("简中", "繁中"):
            profile = "\n###角色介绍"
            for key, value in temp_dict.items():
                original_name = value.get("original_name")
                translated_name = value.get("translated_name")
                gender = value.get("gender")
                age = value.get("age")
                personality = value.get("personality")
                speech_style = value.get("speech_style")
                additional_info = value.get("additional_info")

                profile += f"\n【{original_name}】"
                if translated_name:
                    profile += f"\n- 译名：{translated_name}"

                if gender:
                    profile += f"\n- 性别：{gender}"

                if age:
                    profile += f"\n- 年龄：{age}"

                if personality:
                    profile += f"\n- 性格：{personality}"

                if speech_style:
                    profile += f"\n- 说话方式：{speech_style}"

                if additional_info:
                    profile += f"\n- 补充信息：{additional_info}"

                profile += "\n"

        else:
            profile = "\n###Character Introduction"
            for key, value in temp_dict.items():
                original_name = value.get("original_name")
                translated_name = value.get("translated_name")
                gender = value.get("gender")
                age = value.get("age")
                personality = value.get("personality")
                speech_style = value.get("speech_style")
                additional_info = value.get("additional_info")

                profile += f"\n【{original_name}】"
                if translated_name:
                    profile += f"\n- Translated_name：{translated_name}"

                if gender:
                    profile += f"\n- Gender：{gender}"

                if age:
                    profile += f"\n- Age：{age}"

                if personality:
                    profile += f"\n- Personality：{personality}"

                if speech_style:
                    profile += f"\n- Speech_style：{speech_style}"

                if additional_info:
                    profile += f"\n- Additional_info：{additional_info}"

                profile += "\n"

        return profile

    # 构造背景设定
    def build_world_building(config: TranslatorConfig) -> str:
        # 获取自定义内容
        world_building = config.world_building_content

        if config.target_language in ("简中", "繁中"):
            profile = "\n###背景设定"

            profile += f"\n{world_building}\n"

        else:
            profile = "\n###Background Setting"

            profile += f"\n{world_building}\n"

        return profile

    # 构造文风要求
    def build_writing_style(config: TranslatorConfig) -> str:
        # 获取自定义内容
        writing_style = config.writing_style_content

        if config.target_language in ("简中", "繁中"):
            profile = "\n###翻译风格"

            profile += f"\n{writing_style}\n"

        else:
            profile = "\n###Writing Style"

            profile += f"\n{writing_style}\n"

        return profile

    # 构建翻译示例
    def build_translation_example(config: TranslatorConfig) -> str:
        data = config.translation_example_data

        # 数据校验
        if len(data) == 0:
            return ""

        # 构建翻译示例字符串
        if config.target_language in ("简中", "繁中"):
            translation_example = "\n###翻译示例\n"

        else:
            translation_example = "\n###Translation Example\n"

        for index, pair in enumerate(data, start=1):
            # 使用解构赋值提升可读性
            original = pair.get("src", "")
            translated = pair.get("dst", "")

            # 添加换行符（首行之后才添加）
            if index > 1:
                translation_example += "\n"

            # 使用更严谨的字符串格式化
            if config.target_language in ("简中", "繁中"):
                translation_example += f"  -原文{index}：{original}\n  -译文{index}：{translated}"

            else:
                translation_example += f"  -Original {index}: {original}\n  -Translation {index}: {translated}"

        return translation_example

    # 携带原文上文
    def build_pre_text(config: TranslatorConfig, input_list: list[str]) -> str:
        if config.target_language in ("简中", "繁中"):
            profile = "###上文内容\n"
            profile += "<previous>\n"

        else:
            profile = "###Previous text\n"
            profile += "<previous>\n"

        # 使用列表推导式，转换为字符串列表
        formatted_rows = [item for item in input_list]

        # 使用换行符将列表元素连接成一个字符串
        profile += f"{"\n".join(formatted_rows)}\n"

        profile += "</previous>\n"

        return profile

    # 构建用户请求翻译的示例前文
    def build_userExamplePrefix(config: TranslatorConfig) -> str:
        # 根据中文开关构建
        if config.target_language in ("简中", "繁中"):
            profile = "###这是你接下来的翻译任务，原文文本如下\n"
            profile_cot = "###这是你接下来的翻译任务，原文文本如下\n  "

        else:
            profile = "###This is your next translation task, the original text is as follows\n"
            profile_cot = "###This is your next translation task, the original text is as follows\n"

        # 根据cot开关进行选择
        if config.prompt_preset == PromptBuilderEnum.COT:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建模型回复示例前文
    def build_modelExamplePrefix(config: TranslatorConfig) -> str:

        # 根据中文开关构建
        if config.target_language in ("简中", "繁中"):

            # 非cot的构建
            profile = "我完全理解了翻译的要求与原则，我将遵循您的指示进行翻译，以下是对原文的翻译:\n"


            # cot的构建
            profile_cot = "我完全理解了翻译的步骤与原则，我将遵循您的指示进行翻译，并深入思考和解释:\n"

            profile_cot += "###第一步：初步直译\n"
            profile_cot += """{直译内容}\n"""

            profile_cot += "###第二步：深入校正\n"
            profile_cot += """{校正内容}\n"""

            profile_cot += "###第三步：最终意译与润色\n"


        else:
            # Non-CoT prompt construction
            profile = "I have fully understood the translation requirements and principles. I will follow your instructions to perform the translation. Below is my translation of the original text:\n"

            # Construction of COT
            profile_cot = "I have fully understood the steps and principles of translation. I will follow your instructions to perform the translation and provide in-depth thinking and explanations:\n"

            profile_cot += "### Step 1: Initial Literal Translation\n"
            profile_cot += """{literal_content}\n"""

            profile_cot += "### Step 2: In-depth Polishing\n"
            profile_cot += """{polished_content}\n"""

            profile_cot += "### Step 3: Final Liberal Translation and Polishing\n"


        # 根据cot开关进行选择
        if config.prompt_preset == PromptBuilderEnum.COT:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建用户请求翻译的原文前文:
    def build_userQueryPrefix(config: TranslatorConfig) -> str:
        # 根据中文开关构建
        if config.target_language in ("简中", "繁中"):
            profile = " ###这是你接下来的翻译任务，原文文本如下\n"
            profile_cot = "###这是你接下来的翻译任务，原文文本如下\n"
        else:
            profile = " ###This is your next translation task, the original text is as follows\n"
            profile_cot = "###This is your next translation task, the original text is as follows\n"

        # 根据cot开关进行选择
        if config.prompt_preset == PromptBuilderEnum.COT:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建模型预输入回复的前文
    def build_modelResponsePrefix(config: TranslatorConfig) -> str:
        # 根据中文开关构建
        if config.target_language in ("简中", "繁中"):
            profile = "我完全理解了翻译的要求与原则，我将遵循您的指示进行翻译，以下是对原文的翻译:"
            profile_cot = "我完全理解了翻译的步骤与原则，我将遵循您的指示进行翻译，并深入思考和解释:"
        else:
            profile = "I have fully understood the translation requirements and principles. I will follow your instructions to perform the translation. Below is my translation of the original text:"
            profile_cot = "I have fully understood the steps and principles of translation. I will follow your instructions to perform the translation and provide in-depth thinking and explanations:"

        # 根据cot开关进行选择
        if config.prompt_preset == PromptBuilderEnum.COT:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建用户请求翻译的示例前文
    def build_userExamplePrefix(config: TranslatorConfig) -> str:
        # 根据中文开关构建
        if config.target_language in ("简中", "繁中"):
            profile = "###这是你接下来的翻译任务，原文文本如下\n"
            profile_cot = "###这是你接下来的翻译任务，原文文本如下\n  "

        else:
            profile = "###This is your next translation task, the original text is as follows\n"
            profile_cot = "###This is your next translation task, the original text is as follows\n"

        # 根据cot开关进行选择
        if config.prompt_preset == PromptBuilderEnum.COT:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile
    

        profile = ""

        if input_list:
            # 使用列表推导式，转换为字符串列表
            formatted_rows = [item for item in input_list]

            # 使用换行符将列表元素连接成一个字符串
            profile += f"\n{"\n".join(formatted_rows)}\n"

        return profile