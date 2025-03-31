import re

# 回复解析器
class ResponseChecker():
    def __init__(self):
        pass


    # 检查回复内容是否存在问题
    def check_response_content(self,config,target_platform,response_str,response_dict,source_text_dict):
        # 存储检查结果
        check_result = False
        error_content = "0"

        # 获取需要的配置信息
        source_language = config.source_language
        response_check_switch = config.response_check_switch

        # 检查接口是否拒绝翻译
        if ResponseChecker.contains_special_chars(self,response_str):
            pass
        else:
            check_result = False
            error_content = "模型已拒绝翻译或格式错误，回复内容：" + "\n" + str(response_str)
            return check_result,error_content


        # 检查模型是否退化，出现高频词
        if 'model_degradation_check' in response_check_switch and response_check_switch['model_degradation_check']:
            if ResponseChecker.model_degradation_detection(self,source_text_dict,response_str):
                pass

            else:
                check_result = False
                error_content = "模型出现退化现象"
                return check_result,error_content


        # 检查文本行数
        if ResponseChecker.check_text_line_count(self,source_text_dict,response_dict):
            pass
        else:
            check_result = False
            error_content = "回复文本行数不一致"
            return check_result,error_content


        # 检查文本空行
        if ResponseChecker.check_empty_response(self,response_dict):
            pass
        else:
            check_result = False
            error_content = "原文与译文行数无法对应"
            return check_result,error_content

        # 检查数字序号是否正确
        if target_platform != "sakura":
            if ResponseChecker.check_dict_order(self,source_text_dict,response_dict):
                pass
            else:
                check_result = False
                error_content = "译文文本出现错行串行"
                return check_result,error_content

        # 检查多行文本块是否回复正确行数
        if target_platform != "sakura":
            if ResponseChecker.check_multiline_text(self, source_text_dict, response_dict):
                pass
            else:
                check_result = False
                error_content = "译文多行文本行数不一致"
                return check_result, error_content

        # 检查是否回复了原文
        if 'return_to_original_text_check' in response_check_switch and response_check_switch['return_to_original_text_check']:
            if ResponseChecker.check_dicts_equal(self,source_text_dict,response_dict):
                pass
            else:
                check_result = False
                error_content = "译文与原文完全相同"
                return check_result,error_content


        # 检查是否残留部分原文
        if 'residual_original_text_check' in response_check_switch and response_check_switch['residual_original_text_check']:
            if ResponseChecker.detecting_remaining_original_text(self,source_text_dict,response_dict,source_language):
                pass
            else:
                check_result = False
                error_content = "译文中残留部分原文"
                return check_result,error_content


        # 如果检查都没有问题
        check_result = True
        # 存储错误内容
        error_content = "检查无误"
        return check_result,error_content


    # 检查数字序号是否正确
    def check_dict_order(self,source_text_dict,input_dict):
        """
        检查输入的字典，字典的key是从零开始增加的字符数字，值是文本。
        顺序检查每个值的开头是否是以数字序号+英文句点开头，并且是从1开始增加的数字序号，
        全部检查通过返回真，反之返回假。

        Args:
            input_dict (dict): 输入的字典，key为字符数字，value为文本。

        Returns:
            bool: 检查全部通过返回True，否则返回False。
        """
        if (len(source_text_dict) == 1) and (len(input_dict) == 1):
            return True  # 一行就不检查了


        expected_num = 1  # 期望的起始序号
        keys = sorted(input_dict.keys(), key=int)  # 获取排序后的key，确保按数字顺序检查

        for key in keys:
            value = input_dict[key]
            prefix = str(expected_num) + "."
            if not value.startswith(prefix):
                return False  # 值没有以期望的序号开头
            expected_num += 1  # 序号递增

        return True  # 所有检查都通过

    # 检查多行文本回复内容行数是否正确
    def check_multiline_text(self, source_text_dict, input_dict):
        """
        检查输入字典中的多行文本块是否正确翻译，包括行数和每行内容的完整性。

        Args:
            source_text_dict (dict): 源文本字典，key为字符数字，value为文本。
            input_dict (dict): 输入的字典，key为字符数字，value为文本。

        Returns:
            bool: 所有多行文本块检查通过返回True，否则返回False。
        """
        # 获取排序后的key，确保按数字顺序检查
        keys = sorted(source_text_dict.keys(), key=int)

        for key in keys:
            # 检查key是否存在于输入字典中
            if key not in input_dict:
                return False

            source_text = source_text_dict[key]
            input_text = input_dict[key]

            # 如果源文本包含换行符，则需要检查每一行
            if '\n' in source_text:
                # 分割成行
                source_lines = source_text.split('\n')
                input_lines = input_text.split('\n')

                # 检查行数是否匹配
                if len(source_lines) != len(input_lines):
                    return False

                # 检查每一行是否都有实际内容（除了序号和格式标记外）
                for i, line in enumerate(input_lines):
                    # 移除序号部分（如"1.2..."）
                    content_after_prefix = re.sub(r'^\s*\d+\.(\d+(?:\.{3}|…{1,2}))?\s*', '', line).strip()

                    # 如果回复行为空
                    if not content_after_prefix:
                        # 检查对应的源文本行是否也为空
                        if not source_lines[i].strip():
                            continue
                        else:
                            # 源文本有内容但翻译没有，不通过检查
                            return False

        return True  # 所有检查都通过

    # 检查两个字典是否完全相同，即返回了原文
    def check_dicts_equal(self,dict1, dict2):

        # 不检测双行及以下
        if len(dict1) >=3 :
            i = 0
            s = 0
            for key, value in dict1.items():
                value2 = dict2[key]

                # 将字符串转换为集合形式
                set1 = set(value)
                set2 = set(value2)

                
               # 定义日本汉字的Unicode范围（这是一个大致范围，可能需要调整）
                kanji_start = 0x4E00
                kanji_end = 0x9FFF
                # 剔除原文集合中的汉字
                set1_test = {char for char in set1 if not (kanji_start <= ord(char) <= kanji_end)}
                #set2 = {char for char in set2 if not (kanji_start <= ord(char) <= kanji_end)}
                # 如果原文集合为空，说明原文全是汉字，则跳过此行的计算
                if not set1_test:
                    continue


                # 计算交集和并集的大小
                intersection_size = len(set1.intersection(set2))
                union_size = len(set1.union(set2))

                # 计算单个文本行的Jaccard相似系数
                similarity = intersection_size / union_size

                #累加与累计
                i = i + 1
                s = s + similarity

            # 计算总体相似度，并防止除到0
            result = s / i if i != 0 else 0

            if (result>= 0.85):
                return False
            else:
                return True

        else:
            return True


    # 检查回复内容的文本行数
    def check_text_line_count(self, source_dict, response_dict):
        return (
            len(source_dict) > 0 and len(response_dict) > 0 # 数据不为空
            and len(source_dict) == len(response_dict) # 原文与译文行数一致
            and all(str(key) in response_dict for key in range(len(source_dict))) # 译文的 Key 的值为从 0 开始的连续数值字符
        )

    # 检查翻译内容是否有空值
    def check_empty_response(self,response_dict):
        for value in response_dict.values():
            #检查value是不是None，因为AI回回复null，但是json.loads()会把null转化为None
            if value is None:
                return False

            # 检查value是不是空字符串，因为AI回回复空字符串，但是json.loads()会把空字符串转化为""
            if value == "":
                return False

        return True

    # 检查接口是否拒绝翻译，而返回一段话
    def contains_special_chars(self,s: str) -> bool:
        special_chars = ['<', '>', '/']
        return any(char in s for char in special_chars)


    # 模型退化检测，高频语气词
    def model_degradation_detection(self,source_text_dict, s, count=80):
        """
        检查字符串中是否存在任何字符连续出现指定次数。

        :param s: 输入的字符串
        :param count: 需要检查的连续次数，默认为80
        :return: 如果存在字符连续出现指定次数，则返回False，否则返回True
        """

        # 不检测单行
        if len(source_text_dict) ==1 :
           return True


        for i in range(len(s) - count + 1):
            if len(set(s[i:i+count])) == 1:
                return False
        return True


    # 检查残留原文的算法
    def detecting_remaining_original_text(self,dictA, dictB, language):

        # 使用复制变量，避免影响到原变量
        dict1 = dictA.copy()
        dict2 = dictB.copy()

        # 考量到代码文本，不支持的语言不作检查
        if language not in ("japanese","korean","chinese_simplified","chinese_traditional"):
            return True

        # 避免检查单或者少行字典
        if len(dict1) <=5 :
            return True

        # 不同语言的标点符号字符集
        punctuation_sets = re.compile(
            r'['
            r'\u3000-\u303F'   # CJK符号和标点
            r'\uFF01-\uFF9F'   # 全角ASCII、半角片假名和日文标点
            r'\u314F-\u3163'   # 韩文标点符号
            r'\u0400-\u04FF'   # 俄语字母
            r'\u0500-\u052F'   # 俄语扩展字符（含标点）
            r']+', re.UNICODE  # 使用 + 来匹配一个或多个字符
        )

        # 特定的无法过滤的标点符号集
        punctuation_list_A = ['(', ')', '・', '?', '？', '『', '』', '（', '）', '＜', '＞', '·', '～', 'ー', '@', '＠', '·', '.', '♡', '…', '。', '！', '、', '，']  

        # 定义不同语言的文本字符集对应的正则表达式
        patterns_all = {
            'japanese': re.compile(
                r'['
                r'\u3041-\u3096'  # 平假名
                r'\u30A0-\u30FF'  # 片假名
                r']+', re.UNICODE
            ),
            'korean': re.compile(
                r'['
                r'\uAC00-\uD7AF'  # 韩文字母
                r']+', re.UNICODE
            ),
            'chinese_simplified': re.compile(
                r'['
                r'\u4E00-\u9FA5'  # 简体汉字
                r']+', re.UNICODE
            ),
            'chinese_traditional': re.compile(
                r'['
                r'\u3400-\u4DBF'  # 扩展A区汉字
                r'\u4E00-\u9FFF'  # 基本汉字
                r'\uF900-\uFAFF'  # 兼容汉字
                r']+', re.UNICODE
            ),
        }
        # 根据语言选择合适的正则表达式
        pattern = patterns_all.get(language)
        punctuation_pattern = punctuation_sets
        if not pattern:
            raise ValueError("Unsupported language")

        # 存储计数结果的字典
        count_results = 0

        # 遍历字典2中的每个键值对
        for key2, value2 in dict2.items():
            # 检查字典1中是否有对应的键
            if key2 in dict1:
                # 提取字典1值中的文本
                text1 = dict1[key2]
                # 移除字典2值中的各种通用的标点符号
                text2_clean1 = re.sub(punctuation_pattern, '', value2)
                # 移除字典2值中的特定的标点符号
                text2_clean2 = ResponseChecker.remove_punctuation(self,text2_clean1, punctuation_list_A)
                # 提取字典2值中的指定语言的文本
                text2 = pattern.findall(text2_clean2)
                # 提取为空内容，则跳过
                if text2 =='':
                    continue
                # 将列表转换为字符串
                text2_str = ''.join(text2)
                # 如果字典2中的残留文本在字典1中的文本中出现，则计数加1
                if text2_str and (text2_str in text1):
                    count_results += 1

        # 根据出现次数判断结果
        if  count_results >=2:
            return False

        return True
    
    # 辅助函数
    def remove_punctuation(self,input_string, punctuation_list):
        """
        移除输入字符串中所有属于标点符号列表的字符。

        :param input_string: 要移除标点的字符串。
        :param punctuation_list: 需要移除的标点符号列表。
        :return: 移除了指定标点的新字符串。
        """
        result = ''.join(char for char in input_string if char not in punctuation_list)
        return result