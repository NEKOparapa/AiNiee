import re

import opencc       # 需要安装库pip install opencc
import tiktoken     # 需要安装库pip install tiktoken


# 缓存管理器
class Cache_Manager():
    """
    缓存数据以列表来存储，分文件头（第一个元素）和文本单元(后续元素)，文件头数据结构如下:
    1.项目类型： "project_type"
    2.项目ID： "project_id"

    文本单元的部分数据结构如下:
    1.翻译状态： "translation_status"   未翻译状态为0，已翻译为1，正在翻译为2，不需要翻译为7
    2.文本索引： "text_index"
    3.名字： "name"
    4.原文： "source_text"
    5.译文： "translated_text"
    6.存储路径： "storage_path"
    7.存储文件名： "storage_file_name"
    8.翻译模型： "model"
    等等

    """
    def __init__(self):
        pass


    # 获取缓存数据中指定行数的翻译状态为0的未翻译文本，且改变翻译状态为2
    def process_dictionary_data_lines(self, translation_lines, cache_list, prefer_translated, previous_lines = 0, following_lines = 0):
        # 输入的数据结构参考
        ex_cache_list = [
            {'project_type': 'Mtool'},
            {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！', 'translated_text': '无'},
            {'text_index': 2, 'text_classification': 0, 'translation_status': 1, 'source_text': '室内カメラ', 'translated_text': '无'},
            {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 4, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 5, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 6, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
        ]
        # 输出的数据结构参考
        ex_translation_list = [
            {'text_index': 4, 'source_text': 'しこトラ！',"name": "xxxxx"},
            {'text_index': 5, 'source_text': '11111'},
            {'text_index': 6, 'source_text': 'しこトラ！'},
        ]
        # 输出的数据结构参考
        ex_previous_list = [
            'しこトラ！'
            '11111',
            'しこトラ！',
        ]
        # 输出的数据结构参考
        ex_following_list = [
            'しこトラ！'
            '11111',
            'しこトラ！',
        ]

        translation_list = []
        previous_list = []
        following_list = []


        # 获取特定行数的待翻译内容
        for entry in cache_list:
            translation_status = entry.get('translation_status')

            # 如果能够获得到翻译状态的键，且翻译状态为0，即未翻译状态，那么将该行数据加入到新列表中
            if translation_status == 0:
                source_text = entry.get('source_text')
                text_index = entry.get('text_index')

                # 判断是否为None
                if source_text is not None and text_index is not None:

                    # 尝试获取name
                    name = entry.get('name')
                    # 如果有名字，则将名字加入到新列表中，否则不加入
                    if name:
                        translation_list.append({ 'text_index': text_index ,'source_text': source_text, 'name': name})
                    else:
                        translation_list.append({ 'text_index': text_index ,'source_text': source_text})

                    entry['translation_status'] = 2

                # 如果新列表中的元素个数达到指定行数，则停止遍历
                if len(translation_list) == translation_lines:
                    break

        # 获取首尾索引
        if translation_list:
            star_index = translation_list[0]['text_index'] - 1  # 减1以获取前一行
            end_index = translation_list[-1]['text_index']

            # 获取前n行原文
            if star_index != 0: # 因为第一个元素是消息表头
                base_storage_path = cache_list[star_index]['storage_path']

            for i in range(previous_lines):
                the_index = star_index - i
                if the_index >= 1 and the_index < len(cache_list): # 确保不超出列表范围
                    translation_status = cache_list[the_index]['translation_status']
                    storage_path = cache_list[the_index]['storage_path']
                    if storage_path ==base_storage_path: # 确保是同一文件里内容
                        # 判断是否需要优先获取已经翻译的文本
                        if prefer_translated == True and translation_status == 1:
                            previous_list.append(cache_list[the_index]['translated_text'])
                        elif translation_status == 7 : # 如果是不需要翻译的文本
                            pass
                        else:
                            previous_list.append(cache_list[the_index]['source_text'])

            # 倒序排列元素,以免上文文本顺序错误
            if  previous_list:
                previous_list.reverse()

            # 获取后n行原文
            base_storage_path = cache_list[end_index]['storage_path']

            for i in range(following_lines):
                the_index = end_index + i
                if the_index >= 1 and the_index < len(cache_list):
                    translation_status = cache_list[the_index]['translation_status']
                    storage_path = cache_list[the_index]['storage_path']
                    if storage_path ==base_storage_path: # 确保是同一文件里内容
                        # 判断是否需要优先获取已经翻译的文本
                        if prefer_translated == True and translation_status == 1:
                            following_list.append(cache_list[the_index]['translated_text'])
                        elif translation_status == 7 : # 如果是不需要翻译的文本
                            pass
                        else:
                            following_list.append(cache_list[the_index]['source_text'])

        return translation_list, previous_list


    # 获取缓存数据中指定tokens数的翻译状态为0的未翻译文本，且改变翻译状态为2
    def process_dictionary_data_tokens(self, tokens_limit, cache_list, prefer_translated, previous_lines = 0):


        translation_list = []
        previous_list = []
        tokens_count = 0
        lines_count = 0  # 保底机制用

        # 获取特定行数的待翻译内容
        for entry in cache_list:
            translation_status = entry.get('translation_status')

            # 如果能够获得到翻译状态的键，且翻译状态为0，即未翻译状态，那么将该行数据加入到新列表中
            if translation_status == 0:
                source_text = entry.get('source_text')
                text_index = entry.get('text_index')

                # 判断是否为None
                if source_text is not None and text_index is not None:

                    # 计算原文tokens
                    tokens = Cache_Manager.num_tokens_from_string(self,source_text)
                    # 检查是否超出tokens限制
                    tokens_count = tokens_count + tokens
                    if (tokens_count >= tokens_limit) and (lines_count >= 1) :
                        break

                    # 尝试获取name
                    name = entry.get('name')
                    # 如果有名字，则将名字加入到新列表中，否则不加入
                    if name:
                        translation_list.append({ 'text_index': text_index ,'source_text': source_text, 'name': name})
                    else:
                        translation_list.append({ 'text_index': text_index ,'source_text': source_text})


                    entry['translation_status'] = 2
                    lines_count = lines_count + 1



        # 获取首尾索引
        if translation_list:
            star_index = translation_list[0]['text_index'] - 1  # 减1以获取前一行

            # 获取前n行原文

            # 获取前n行原文
            if star_index != 0: # 因为第一个元素是消息表头
                base_storage_path = cache_list[star_index]['storage_path']

            for i in range(previous_lines):
                the_index = star_index - i
                if the_index >= 1 and the_index < len(cache_list): # 确保不超出列表范围
                    translation_status = cache_list[the_index]['translation_status']
                    storage_path = cache_list[the_index]['storage_path']
                    if storage_path ==base_storage_path: # 确保是同一文件里内容
                        # 判断是否需要优先获取已经翻译的文本
                        if prefer_translated == True and translation_status == 1:
                            previous_list.append(cache_list[the_index]['translated_text'])
                        elif translation_status == 7 : # 如果是不需要翻译的文本
                            pass
                        else:
                            previous_list.append(cache_list[the_index]['source_text'])
            # 倒序排列元素
            if  previous_list:
                previous_list.reverse()


        return translation_list, previous_list

    # 将未翻译的文本列表，转换成待发送的原文字典,并计算文本实际行数，因为最后一些文本可能达到不了每次翻译行数
    def create_dictionary_from_list(self,data_list):
        #输入示例
        ex_list = [
            {'text_index': 4, 'source_text': 'しこトラ！',"name": "xxxxx"},
            {'text_index': 5, 'source_text': '11111'},
            {'text_index': 6, 'source_text': 'しこトラ！'},
        ]

        # 输出示例
        ex_dict = {
        '0': '测试！',
        '1': '测试1122211',
        '2': '测试xxxx！',
        }

        new_dict = {}
        index_count = 0

        for index, entry in enumerate(data_list):
            source_text = entry.get('source_text')
            name = entry.get('name')

            # 如果有名字，则组合成轻小说的格式，如：小明「测试」， 否则不组合
            if name: # 注意：改成二级处理时，要记得指令词典只会判断原文，不会判断名字
                if source_text[0] == '「':
                    new_dict[str(index_count)] = f"{name}{source_text}"
                else:
                    new_dict[str(index_count)] = f"{name}「{source_text}」"
            else:
                new_dict[str(index_count)] = source_text

            #索引计数
            index_count += 1

        return new_dict, len(data_list)


    # 提取输入文本头尾的非文本字符
    def trim_string(self,input_string):

        # 存储截取的头尾字符
        head_chars = []
        tail_chars = []
        middle_chars = input_string

        # 定义中日文及常用标点符号的正则表达式
        CJK = ("\u4E00", "\u9FFF") # 中日韩统一表意文字
        HIRAGANA = ("\u3040", "\u309F") # 平假名
        KATAKANA = ("\u30A0", "\u30FF") # 片假名
        KATAKANA_HALF_WIDTH = ("\uFF65", "\uFF9F") # 半角片假名（包括半角浊音、半角拗音等）
        KATAKANA_PHONETIC_EXTENSIONS = ("\u31F0", "\u31FF") # 片假名语音扩展
        VOICED_SOUND_MARKS = ("\u309B", "\u309C") # 濁音和半浊音符号

        jp_pattern = re.compile(
            r'['
            + rf'{CJK[0]}-{CJK[1]}'
            + rf'{HIRAGANA[0]}-{HIRAGANA[1]}'
            + rf'{KATAKANA[0]}-{KATAKANA[1]}'
            + rf'{KATAKANA_HALF_WIDTH[0]}-{KATAKANA_HALF_WIDTH[1]}'
            + rf'{KATAKANA_PHONETIC_EXTENSIONS[0]}-{KATAKANA_PHONETIC_EXTENSIONS[1]}'
            + rf'{VOICED_SOUND_MARKS[0]}-{VOICED_SOUND_MARKS[1]}'
            + r']+'
        )
        punctuation = re.compile(r'[。．，、；：？！「」『』【】〔〕（）《》〈〉…—…]+')

        # 从头开始检查并截取
        while middle_chars and not (jp_pattern.match(middle_chars) or punctuation.match(middle_chars)):
            head_chars.append(middle_chars[0])
            middle_chars = middle_chars[1:]

        # 从尾开始检查并截取
        while middle_chars and not (jp_pattern.match(middle_chars[-1]) or punctuation.match(middle_chars[-1])):
            tail_chars.insert(0, middle_chars[-1])  # 保持原始顺序插入
            middle_chars = middle_chars[:-1]

        return head_chars, middle_chars, tail_chars

    # 处理字典内的文本，清除头尾的非文本字符
    def process_dictionary(self,input_dict):
        # 输入字典示例
        ex_dict1 = {
        '0': r'\if(s[114])en(s[115])ハイヒーリング（消費MP5）',
        '1': r'\F[21]\FF[128]ゲオルグ「なにを言う。　僕はおまえを助けに来たんだ。\FF[128]',
        '2': r'少年「ダメか。僕も血が止まらないな……。',
        }

        #输出信息处理记录列表示例
        ex_list1 = [
            {'text_index': '0', "Head:": r'\if(s[114])en(s[115])',"Middle": "ハイヒーリング（消費MP5）"},
            {'text_index': '1', "Head:": r'\F[21]\FF[128]',"Middle": "ゲオルグ「なにを言う。　僕はおまえを助けに来たんだ。", "Tail:": r'\FF[128]'},
            {'text_index': '2', "Middle": "少年「ダメか。僕も血が止まらないな……。"},
        ]

        # 输出字典示例
        ex_dict2 = {
        '0': 'ハイヒーリング（消費MP5）',
        '1': 'ゲオルグ「なにを言う。　僕はおまえを助けに来たんだ。',
        '2': '少年「ダメか。僕も血が止まらないな……。',
        }

        processed_dict = {}
        process_info_list = []
        for key, value in input_dict.items():
            head, middle, tail = Cache_Manager.trim_string(self,value)


            # 这里针对首尾非文本字符是纯数字字符或者类似“R5”组合时,还原回去,否则会影响翻译

            if head: # 避免空列表与列表类型导致错误
                head_str = ''.join(head)
            else:
                head_str = ""

            if head_str.isdigit() or bool(re.match(r'^[a-zA-Z][0-9]{1,2}$', head_str)):
                middle = head_str + middle
                head = []


            if tail: # 避免空列表与列表类型导致错误
                tail_str = ''.join(tail)
            else:
                tail_str = ""

            if tail_str.isdigit() or bool(re.match(r'^[a-zA-Z][0-9]{1,2}$', tail_str)):
                middle = middle + tail_str
                tail = []


            # 将处理后的结果存储在两个不同的结构中：一个字典和一个列表。
            processed_dict[key] = middle
            info = {"text_index": key}
            if head:
                info["Head:"] = ''.join(head)
            if middle:
                info["Middle:"] = middle
            if tail:
                info["Tail:"] = ''.join(tail)
            process_info_list.append(info)
        return processed_dict, process_info_list

    # 复原文本中的头尾的非文本字符
    def update_dictionary(self,original_dict, process_info_list):
        # 输入字典示例
        ex_dict1 = {
        '0': '测试1',
        '1': '测试2',
        '2': '测试3',
        }
        #输入信息处理记录列表示例
        ex_list1 = [
            {'text_index': '0', "Head:": r'\if(s[114])en(s[115])',"Middle": "ハイヒーリング（消費MP5）"},
            {'text_index': '1', "Head:": r'\F[21]\FF[128]',"Middle": "ゲオルグ「なにを言う。　僕はおまえを助けに来たんだ。", "Head:": r'\FF[128]'},
            {'text_index': '2', "Middle": "少年「ダメか。僕も血が止まらないな……。"},
        ]
        # 输出字典示例
        ex_dict2 = {
        '0': r'\if(s[114])en(s[115])测试1',
        '1': r'\F[21]\FF[128]测试2\FF[128]',
        '2': '测试3',
        }

        updated_dict = {}
        for item in process_info_list:
            text_index = item["text_index"]
            head = item.get("Head:", "")
            tail = item.get("Tail:", "")

            # 获取原始字典中的值
            original_value = original_dict.get(text_index, "")

            # 拼接头、原始值、中和尾
            updated_value = head + original_value + tail
            updated_dict[text_index] = updated_value
        return updated_dict


    # 将翻译结果录入缓存函数，且改变翻译状态为1
    def update_cache_data(self, cache_data, source_text_list, response_dict,translation_model):
        # 输入的数据结构参考
        ex_cache_data = [
            {'project_type': 'Mtool'},
            {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！', 'translated_text': '无'},
            {'text_index': 2, 'text_classification': 0, 'translation_status': 1, 'source_text': '室内カメラ', 'translated_text': '无'},
            {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 4, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 5, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 6, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
        ]


        ex_source_text_list = [
            {'text_index': 4, 'source_text': 'しこトラ！','name': 'xxxxx'},
            {'text_index': 5, 'source_text': '11111'},
            {'text_index': 6, 'source_text': 'しこトラ！'},
        ]


        ex_response_dict = {
        '0': '测试！',
        '1': '测试1122211',
        '2': '测试xxxx！',
        }


        # 回复文本的索引
        index = 0

        # 遍历原文本列表
        try:
            for source_text_item in source_text_list:
                # 获取缓存文本中索引值
                text_index = source_text_item['text_index']
                # 根据回复文本的索引值，在回复内容中获取已翻译的文本
                response_value = response_dict[str(index)]
                # 获取人名（如果有）
                name = source_text_item.get('name')

                # 缓存文本中索引值，基本上是缓存文件里元素的位置索引值，所以直接获取并修改
                if name:
                    # 提取人名以及对话文本
                    name_text,text = Cache_Manager.extract_strings(self,response_value)
                    # 如果能够正确提取到人名以及翻译文本
                    if name_text:
                        cache_data[text_index]['translation_status'] = 1
                        cache_data[text_index]['name'] = name_text
                        cache_data[text_index]['translated_text'] = text
                        cache_data[text_index]['model'] = translation_model
                    else:
                        cache_data[text_index]['translation_status'] = 1
                        cache_data[text_index]['translated_text'] = response_value
                        cache_data[text_index]['model'] = translation_model

                else:
                    cache_data[text_index]['translation_status'] = 1
                    cache_data[text_index]['translated_text'] = response_value
                    cache_data[text_index]['model'] = translation_model

                # 增加索引值
                index = index + 1

        except:
            print("[DEBUG] 录入翻译结果出现问题！！！！！！！！！！！！")
            print(text_index)


        return cache_data


    # 统计翻译状态等于0或者2的元素个数，且把等于2的翻译状态改为0.并返回元素个数
    def count_and_update_translation_status_0_2(self, data):
        # 输入的数据结构参考
        ex_cache_data = [
            {'project_type': 'Mtool'},
            {'text_index': 1, 'text_classification': 0, 'translation_status': 0, 'source_text': 'しこトラ！', 'translated_text': '无'},
            {'text_index': 2, 'text_classification': 0, 'translation_status': 1, 'source_text': '室内カメラ', 'translated_text': '无'},
            {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 4, 'text_classification': 0, 'translation_status': 2, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 5, 'text_classification': 0, 'translation_status': 2, 'source_text': '11111', 'translated_text': '无'},
            {'text_index': 6, 'text_classification': 0, 'translation_status': 0, 'source_text': '11111', 'translated_text': '无'},
        ]

        # 计算翻译状态为0或2的条目数量与tokens
        tokens_count = 0
        raw_count = 0
        for item in data:
            if (item.get('translation_status') == 0) or (item.get('translation_status') == 2):
                raw_count += 1

                source_text = item.get('source_text')
                if  source_text:
                    tokens = Cache_Manager.num_tokens_from_string(self,source_text)
                    # 检查是否超出tokens限制
                    tokens_count = tokens_count + tokens

        # 将'translation_status'等于2的元素的'translation_status'改为0
        for item in data:
            if item.get('translation_status') == 2:
                item['translation_status'] = 0

        return raw_count,tokens_count


    # 替换或者还原换行符和回车符函数
    def replace_special_characters(self,dict, mode):
        new_dict = {}
        if mode == "替换":
            for key, value in dict.items():
                #如果value是字符串变量
                if isinstance(value, str):
                    new_value = value.replace("\n", "＠").replace("\r", "∞")
                    new_dict[key] = new_value
        elif mode == "还原":
            for key, value in dict.items():
                #如果value是字符串变量
                if isinstance(value, str):
                    # 先替换半角符号
                    new_value = value.replace("@", "\n")
                    # 再替换全角符号
                    new_value = new_value.replace("＠", "\n").replace("∞", "\r")
                    new_dict[key] = new_value
        else:
            print("请输入正确的mode参数（替换或还原）")

        return new_dict


    # 轻小说格式提取人名与文本
    def extract_strings(self, text):
        # 查找第一个左括号的位置
        left_bracket_pos = text.find('「')

        # 如果找不到左括号，返回原始文本
        if left_bracket_pos == -1:
            return 0,text

        # 提取名字和对话内容
        name = text[:left_bracket_pos].strip()
        dialogue = text[left_bracket_pos:].strip()

        return name, dialogue


    # 将缓存文件里已翻译的文本转换为简体字或繁体字
    def simplified_and_traditional_conversion(self,cache_list, opencc_preset):
        # 缓存数据结构示例
        ex_cache_data = [
        {'project_type': 'Mtool'},
        {'text_index': 1, 'text_classification': 0, 'translation_status': 1, 'source_text': 'しこトラ！', 'translated_text': '谢谢', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json'},
        {'text_index': 2, 'text_classification': 0, 'translation_status': 1, 'source_text': '室内カメラ', 'translated_text': '開心', 'storage_path': 'TrsData.json', 'file_name': 'TrsData.json'},
        {'text_index': 3, 'text_classification': 0, 'translation_status': 0, 'source_text': '111111111', 'translated_text': '歷史', 'storage_path': 'DEBUG Folder\\Replace the original text.json', 'file_name': 'Replace the original text.json'},
        {'text_index': 4, 'text_classification': 0, 'translation_status': 0, 'source_text': '222222222', 'translated_text': '无', 'storage_path': 'DEBUG Folder\\Replace the original text.json', 'file_name': 'Replace the original text.json'},
        ]

        # 确定使用的转换器
        cc = opencc.OpenCC(opencc_preset)  # 创建OpenCC对象，使用t2s参数表示繁体字转简体字

        # 存储结果的列表
        converted_list = []

        # 遍历缓存数据
        for item in cache_list:
            translation_status = item.get('translation_status', 0)
            translated_text = item.get('translated_text', '')

            # 如果'translation_status'为1，进行转换
            if translation_status == 1:
                converted_text = cc.convert(translated_text)
                item_copy = item.copy()  # 防止修改原始数据
                item_copy['translated_text'] = converted_text
                converted_list.append(item_copy)
            else:
                converted_list.append(item)

        return converted_list


    # 计算单个字符串tokens数量函数
    def num_tokens_from_string(self,string):
        """Returns the number of tokens in a text string."""
        if isinstance(string, str):
            encoding = tiktoken.get_encoding("cl100k_base")
            num_tokens = len(encoding.encode(string))
            return num_tokens
        else:
            return 10