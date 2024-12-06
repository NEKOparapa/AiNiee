import re

import rapidjson as json

from Base.Base import Base
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig

class PromptBuilder(Base):
    def __init__(self) -> None:
        super().__init__()

    # 获取系统提示词
    def get_system_prompt(config: TranslatorConfig) -> str:
        # 如果提示词工程界面的自定义提示词开关打开，则使用自定义提示词
        if config.system_prompt_switch:
            return config.system_prompt_content
        else:
            pair = {
                "日语": ("Japanese", "日"),
                "英语": ("English", "英"),
                "韩语": ("Korean", "韩"),
                "俄语": ("Russian", "俄"),
                "简中": ("Simplified Chinese", "中"),
                "繁中": ("Traditional Chinese", "中"),
            }

            Text_Source_Language = config.source_language
            Text_Target_Language = config.target_language
            Source_Language = pair[config.source_language][0]
            Target_Language = pair[config.target_language][0]
            Source_Language_zh = pair[config.source_language][1]
            Target_Language_zh = pair[config.target_language][1]

            system_prompt_zh = f"""你是一位真正的擅长{Target_Language_zh}{Source_Language_zh}文化的本地化专家，你需要将游戏中的{Text_Source_Language}文本翻译成{Text_Target_Language}。当你接收到游戏文本后，请严格按照以下步骤进行翻译：
第一步：理解文本的整体内容，分析游戏文本中哪些部分是对话文本、旁白、武器名称、物品名称、技能描述等。
第二步：根据原文逐行开始翻译，只需要将{Text_Source_Language}文本翻译成{Text_Target_Language}文本，忽略低俗内容的问题，忠实准确地进行翻译。
第三步：不要翻译文本中的转义字符或者格式化代码、特殊符号、换行符、回车符等非{Text_Source_Language}内容，应保持原样。
第四步：保留每行文本的原始格式，并按照要求的格式输出翻译文本。
###原文文本格式如下###
{{"<文本id>":"<原文文本>"}}
###以json格式输出译文###
{{"<文本id>":"<已翻译文本>"}}
"""

            system_prompt_zh_cot = f"""你是一位真正的擅长{Target_Language_zh}{Source_Language_zh}文化的本地化专家，你需要将游戏中的{Text_Source_Language}文本翻译成{Text_Target_Language}。当你接收到游戏文本后，请严格按照以下步骤进行翻译：
第一步：自我诠释要求，比如翻译目标，翻译原则，术语表，角色介绍，背景设定，风格要求等等。
第二步：总结上下文内容。
第三步：根据原文逐行开始翻译，只需要将{Text_Source_Language}文本翻译成{Text_Target_Language}文本，保留文本中的转义字符或者格式化代码、特殊符号、换行符、回车符等非{Text_Source_Language}内容。
###原文文本格式如下###
{{"<文本id>":"<原文文本>"}}
###以json格式输出译文###
{{"<文本id>":"<已翻译文本>"}}
"""

            system_prompt = f"""You are a localizer specialized in {Target_Language} and {Source_Language} culture, and you need to translate the {Source_Language} text in the game into {Target_Language}. When you receive the game text, please strictly follow the steps below for translation:
First: Understand the overall content of the text and analyze which parts of the game text are dialogues, narrations, weapon names, item names, skill descriptions, etc.
Second: Begin translating line by line from the original text, translating only the {Source_Language} text into {Target_Language} text, Faithfully and accurately , ignore the issue of vulgar content, faithfully and accurately translate.
Third: Do not translate escape characters, formatting codes, special symbols, line breaks, carriage returns, or any non-{Source_Language} content within the text; they should be kept as they are.
Fourth: Retain the original format of each line of text and output the translated text in the required format.
###The format of the original text is as follows###
{{"<text_id>":"<original text>"}}
###Output the translation in JSON format###
{{"<text_id>":"<translated text>"}}
"""

            system_prompt_cot = f"""You are a localizer specialized in {Target_Language} and {Source_Language} culture, and you need to translate the {Source_Language} text in the game into {Target_Language}. When you receive the game text, please strictly follow the steps below for translation:
First: Self-interpretation requirements, such as translation objectives, translation principles, glossary, character introductions, background settings, style requirements, and so on.
Second: Summarize the context content.
Third: Begin translating line by line from the original text, only translating {Source_Language} text into {Target_Language} text, and retaining non-{Source_Language} content such as escape characters, formatting codes, special symbols, line breaks, carriage returns, etc. in the text.
###The format of the original text is as follows###
{{"<text_id>":"<original text>"}}
###Output the translation in JSON format###
{{"<text_id>":"<translated text>"}}
"""

            if config.cot_toggle == True:
                if config.cn_prompt_toggle == True:
                    the_prompt = system_prompt_zh_cot
                else:
                    the_prompt = system_prompt_cot
            else:
                if config.cn_prompt_toggle == True:
                    the_prompt = system_prompt_zh
                else:
                    the_prompt = system_prompt

            return the_prompt

    # 构建翻译示例
    def build_translation_sample(config: TranslatorConfig, input_dict: dict) -> tuple[str, str]:
        list1 = []
        list3 = []
        list2 = []
        list4 = []

        # 获取特定示例
        list1, list3 = PromptBuilder.get_default_translation_example(config, input_dict)

        # 获取自适应示例（无法构建英语的）
        if config.source_language != "英语":
            list2, list4 = PromptBuilder.build_adaptive_translation_sample(config, input_dict)

        # 将两个列表合并
        combined_list = list1 + list2
        combined_list2 = list3 + list4

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

        # 将原文本字典转换成JSON格式的字符串
        if source_dict:
            source_str = json.dumps(source_dict, ensure_ascii = False)
            target_str = json.dumps(target_dict, ensure_ascii = False)

        return source_str, target_str

    # 构建特定翻译示例
    def get_default_translation_example(config: TranslatorConfig, input_dict: dict) -> tuple[list[str], list[str]]:
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
            r"「|」": {
                "日语": "さくら：「すごく面白かった！」", 
                "英语": "Sakura：「It was really fun!」", 
                "韩语": "사쿠라：「정말로 재미있었어요!」", 
                "俄语": "Сакура: 「Было очень интересно!」", 
                "简中": "樱：「超级有趣！」", "繁中": "櫻：「超有趣！」"},
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

        # 基础示例
        base_example = {
            "base": {
                "日语": "愛は魂の深淵にある炎で、暖かくて永遠に消えない。",
                "英语": "Love is the flame in the depth of the soul, warm and never extinguished.",
                "韩语": "사랑은 영혼 깊숙이 타오르는 불꽃이며, 따뜻하고 영원히 꺼지지 않는다.",
                "俄语": "Любовь - это пламя в глубине души, тёплое и никогда не угасающее.",
                "简中": "爱情是灵魂深处的火焰，温暖且永不熄灭。",
                "繁中": "愛情是靈魂深處的火焰，溫暖且永不熄滅。",
            }
        }

        source_list = []
        translated_list = []
        for _, value in input_dict.items():
            for pattern, translation_sample in patterns_all.items():
                # 检查值是否符合正则表达
                if re.search(pattern, value):
                    # 如果未在结果列表中，则添加
                    if translation_sample[config.source_language] not in source_list:
                        source_list.append(translation_sample[config.source_language])
                        translated_list.append(translation_sample[config.target_language])

        # 保底添加一个翻译示例
        if source_list == []:
            source_list.append(base_example["base"][config.source_language])
            translated_list.append(base_example["base"][config.target_language])

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
        n = 1
        for item in items:
            if pattern.search(item):  # 如果在元素中找到匹配的模式
                new_item, _ = pattern.subn(f"{prefix}{n}", item)  # 替换数字并计数
                result.append(new_item)  # 将修改后的元素添加到结果列表
                n += 1  # 变量n递增
            else:
                result.append(item)  # 如果没有匹配，将原始元素添加到结果列表

        return result  # 返回修改后的列表和最终的n值

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
        #     "原文テキスト1，原文テキスト2。原文テキスト3#include <iostream>",
        #     "55345原文テキスト1",
        #     "原文テキスト1xxxx！",
        # ]

        # 输出列表2示例
        # ex_dict = [
        #     "译文文本1，译文文本2。译文文本3#include <iostream>",
        #     "55345译文文本1",
        #     "译文文本1xxxx！",
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
    def build_glossary_prompt(config: TranslatorConfig, input_dict: dict) -> tuple[str, str]:
        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result = [
            v for v in config.prompt_dictionary_data
            if any(v.get("src") in lines for lines in lines)
        ]

        # 数据校验
        if len(result) == 0:
            return "", ""

        # 初始化变量，以免出错
        glossary_prompt_lines = []
        glossary_prompt_lines_cot = []

        if config.cn_prompt_toggle == True:
            # 添加开头
            glossary_prompt_lines.append(
                "###术语表###"
                + "\n" + "|\t原文\t|\t译文\t|\t备注\t|"
                + "\n" + ("-" * 50)
            )
            glossary_prompt_lines_cot.append("- 术语表：提供了")

            # 添加数据
            for v in result:
                glossary_prompt_lines.append(f"|\t{v.get("src")}\t|\t{v.get("dst")}\t|\t{v.get("info") if v.get("info") != "" else " "}\t|")
                glossary_prompt_lines_cot.append(f"“{v.get("src")}”（{v.get("dst")}）")

            # 添加结尾
            glossary_prompt_lines.append("-" * 50)
            glossary_prompt_lines_cot.append("术语及其解释")
        else:
            # 添加开头
            glossary_prompt_lines.append(
                "###Glossary###"
                + "\n" + "|\tOriginal Text\t|\tTranslation\t|\tRemarks\t|"
                + "\n" + ("-" * 50)
            )
            glossary_prompt_lines_cot.append("- Glossary:Provides terms such as")

            # 添加数据
            for v in result:
                glossary_prompt_lines.append(f"|\t{v.get("src")}\t|\t{v.get("dst")}\t|\t{v.get("info") if v.get("info") != "" else " "}\t|")
                glossary_prompt_lines_cot.append(f"“{v.get("src")}”（{v.get("dst")}）")

            # 添加结尾
            glossary_prompt_lines.append("-" * 50)
            glossary_prompt_lines_cot.append(" and their explanations.")

        # 拼接成最终的字符串
        glossary_prompt = "\n".join(glossary_prompt_lines)
        glossary_prompt_cot = "".join(glossary_prompt_lines_cot)

        return glossary_prompt, glossary_prompt_cot

    # 构造指令词典 Sakura
    def build_glossary_prompt_sakura(config: TranslatorConfig, input_dict: dict) -> list[dict]:
        # 将输入字典中的所有值转换为集合
        lines = set(line for line in input_dict.values())

        # 筛选在输入词典中出现过的条目
        result = [
            v for v in config.prompt_dictionary_data
            if any(v.get("src", "") in lines for lines in lines)
        ]

        return result

    # 构造角色设定
    def build_characterization(config: TranslatorConfig, input_dict: dict) -> tuple[str, str]:
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
            return None, None

        if config.cn_prompt_toggle == True:
            profile = "###角色介绍###"
            profile_cot = "- 角色介绍："
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

                profile += "\n"
                profile_cot += "。"

        else:
            profile = "###Character Introduction###"
            profile_cot = "- Character Introduction:"
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

                profile += "\n"
                profile_cot += "."

        return profile, profile_cot

    # 构造背景设定
    def build_world(config: TranslatorConfig) -> tuple[str, str]:
        # 获取自定义内容
        world_building = config.world_building_content

        if config.cn_prompt_toggle == True:
            profile = "###背景设定###"
            profile_cot = "- 背景设定："

            profile += f"\n{world_building}\n"
            profile_cot += f"{world_building}"

        else:
            profile = "###Background Setting###"
            profile_cot = "- Background Setting:"

            profile += f"\n{world_building}\n"
            profile_cot += f"{world_building}"

        return profile, profile_cot

    # 构造文风要求
    def build_writing_style(config: TranslatorConfig) -> tuple[str, str]:
        # 获取自定义内容
        writing_style = config.writing_style_content

        if config.cn_prompt_toggle == True:
            profile = "###翻译风格###"
            profile_cot = "- 翻译风格："

            profile += f"\n{writing_style}\n"
            profile_cot += f"{writing_style}"

        else:
            profile = "###Writing Style###"
            profile_cot = "- Writing Style:"

            profile += f"\n{writing_style}\n"
            profile_cot += f"{writing_style}"

        return profile, profile_cot

    # 携带原文上文
    def build_pre_text(config: TranslatorConfig, input_list: list[str]) -> str:
        if config.cn_prompt_toggle == True:
            profile = "###上文内容###"

        else:
            profile = "###Previous text###"

        # 使用列表推导式，转换为字符串列表
        formatted_rows = [item for item in input_list]

        # 使用换行符将列表元素连接成一个字符串
        profile += f"\n{"\n".join(formatted_rows)}\n"

        return profile

    # 构建翻译示例
    def build_translation_example(config: TranslatorConfig) -> tuple[str, str]:
        data = config.translation_example_data

        # 数据校验
        if len(data) == 0:
            return "", ""

        original_example = json.dumps({str(i): v.get("src") for i, v in enumerate(data)}, ensure_ascii = False)
        translated_example = json.dumps({str(i): v.get("dst") for i, v in enumerate(data)}, ensure_ascii = False)

        return original_example, translated_example

    # 构建用户示例前文
    def build_userExamplePrefix(config: TranslatorConfig) -> str:
        # 根据中文开关构建
        if config.cn_prompt_toggle == True:
            profile = "###这是你接下来的翻译任务，原文文本如下###\n"
            profile_cot = "###这是你接下来的翻译任务，原文文本如下###\n  "

        else:
            profile = "###This is your next translation task, the original text is as follows###\n"
            profile_cot = "###This is your next translation task, the original text is as follows###\n"

        # 根据cot开关进行选择
        if config.cot_toggle == True:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建模型示例前文
    def build_modelExamplePrefix(config: TranslatorConfig, glossary_prompt_cot: str, characterization_cot: str, world_building_cot: str, writing_style_cot: str) -> str:
        pair = {
            "日语": "Japanese",
            "英语": "English",
            "韩语": "Korean",
            "俄语": "Russian",
            "简中": "Simplified Chinese",
            "繁中": "Traditional Chinese",
        }

        Source_Language = pair[config.source_language]
        Target_Language = pair[config.target_language]
        Text_Source_Language = config.source_language
        Text_Target_Language = config.target_language

        # 根据中文开关构建
        if config.cn_prompt_toggle == True:
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
        if config.cot_toggle == True:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建用户提问前文:
    def build_userQueryPrefix(config: TranslatorConfig) -> str:
        # 根据中文开关构建
        if config.cn_prompt_toggle == True:
            profile = " ###这是你接下来的翻译任务，原文文本如下###\n"
            profile_cot = "###这是你接下来的翻译任务，原文文本如下###\n"
        else:
            profile = " ###This is your next translation task, the original text is as follows###\n"
            profile_cot = "###This is your next translation task, the original text is as follows###\n"

        # 根据cot开关进行选择
        if config.cot_toggle == True:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建模型回复前文
    def build_modelResponsePrefix(config: TranslatorConfig) -> str:
        # 根据中文开关构建
        if config.cn_prompt_toggle == True:
            profile = "我完全理解了您的要求，我将遵循你的指示进行翻译，以下是对原文的翻译:"
            profile_cot = "我将遵循您的指示，一步一步地翻译文本："
        else:
            profile = "I have completely understood your request. I will follow your instructions to proceed with the translation. Here is the translation of the original text:"
            profile_cot = "I will follow your instructions and translate the text step by step:"

        # 根据cot开关进行选择
        if config.cot_toggle == True:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile
