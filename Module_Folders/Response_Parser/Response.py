import re
import json

# 回复解析器
class Response_Parser():
    def __init__(self):
        pass


    #处理并正则提取翻译内容
    def text_extraction(self,input_str):

        # 尝试直接转换为json字典
        try:
            response_dict = json.loads(input_str)
            return response_dict
        except :
            pass


        # 尝试正则提取
        try:

            # 使用正则表达式匹配字符串中的所有键值对
            parsed_dict = {}
            key = None
            key_pattern = r'("\d+?"\s*:\s*)'
            lines = re.split(key_pattern, input_str)
            for line in lines:
                if re.match(key_pattern, line):
                    key = re.findall(r'\d+', line)[0]
                    continue
                if not key: continue
                value = re.findall(r'"([\S\s]+)"(?=,|}|\n)', line)
                if value:
                    if key not in parsed_dict:
                        parsed_dict[key] = value[0]
                key = None


            return parsed_dict
        except :
            print("\033[1;33mWarning:\033[0m 回复内容无法正常提取，请反馈\n")
            return {}


    # 将Raw文本恢复根据行数转换成json文本
    def convert_str_to_json_str(self,row_count, input_str):

        # 当发送文本为1行时，就不分割了，以免切错
        if row_count == 1:
            result = {"0": input_str}
            return  json.dumps(result, ensure_ascii=False)

        else:
            str_list = input_str.split("\n")
            ret_json = {}
            for idx, text in enumerate(str_list):
                ret_json[f"{idx}"] = f"{text}"
            return json.dumps(ret_json, ensure_ascii=False)



    # 检查回复内容是否存在问题
    def check_response_content(self,reply_check_switch,response_str,response_dict,source_text_dict,source_language):
        # 存储检查结果
        check_result = False
        # 存储错误内容
        error_content = "0"


        # 检查接口是否拒绝翻译
        if Response_Parser.contains_special_chars(self,response_str):
            pass
        else:
            check_result = False
            # 存储错误内容
            error_content = "模型已拒绝翻译，回复内容：" + "\n" + str(response_str)
            return check_result,error_content



        # 检查模型是否退化，出现高频词
        if 'Model Degradation Check' in reply_check_switch and reply_check_switch['Model Degradation Check']:
            if Response_Parser.model_degradation_detection(self,response_str):
                pass

            else:
                check_result = False
                # 存储错误内容
                error_content = "模型退化"
                return check_result,error_content


        # 检查文本行数
        if Response_Parser.check_text_line_count(self,source_text_dict,response_dict):
            pass
        else:
            check_result = False
            # 存储错误内容
            error_content = "原文与译文行数不一致"
            return check_result,error_content


        # 检查文本空行
        if Response_Parser.check_empty_response(self,response_dict):
            pass
        else:
            check_result = False
            # 存储错误内容
            error_content = "译文中有未翻译的空行"
            return check_result,error_content


        # 检查是否回复了原文
        if 'Return to Original Text Check' in reply_check_switch and reply_check_switch['Return to Original Text Check']:
            if Response_Parser.check_dicts_equal(self,source_text_dict,response_dict):
                pass
            else:
                check_result = False
                # 存储错误内容
                error_content = "译文与原文完全相同"
                return check_result,error_content

        # 检查是否残留部分原文
        if 'Residual Original Text Check' in reply_check_switch and reply_check_switch['Residual Original Text Check']:
            if Response_Parser.detecting_remaining_original_text(self,source_text_dict,response_dict,source_language):
                pass
            else:
                check_result = False
                # 存储错误内容
                error_content = "译文中残留部分原文"
                return check_result,error_content


        # 如果检查都没有问题
        check_result = True
        # 存储错误内容
        error_content = "检查无误"
        return check_result,error_content


    # 检查两个字典是否完全相同，即返回了原文
    def check_dicts_equal(self,dict1, dict2):
        if len(dict1) >=3 :
            i = 0
            s = 0
            for key, value in dict1.items():
                value2 = dict2[key]

                # 将字符串转换为集合形式
                set1 = set(value)
                set2 = set(value2)

                # 计算交集和并集的大小
                intersection_size = len(set1.intersection(set2))
                union_size = len(set1.union(set2))

                # 计算Jaccard相似系数
                similarity = intersection_size / union_size

                #累加与累计
                i = i + 1
                s = s + similarity

            result = s/i

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
        special_chars = ['{', '"""', ':', '}']
        return any(char in s for char in special_chars)


    # 模型退化检测，高频语气词
    def model_degradation_detection(self, s, count=80):
        """
        检查字符串中是否存在任何字符连续出现指定次数。

        :param s: 输入的字符串
        :param count: 需要检查的连续次数，默认为80
        :return: 如果存在字符连续出现指定次数，则返回False，否则返回True
        """
        for i in range(len(s) - count + 1):
            if len(set(s[i:i+count])) == 1:
                return False
        return True


    # 检查残留原文的算法
    def detecting_remaining_original_text(self,dictA, dictB, language):

        # 使用复制变量，避免影响到原变量
        dict1 = dictA.copy()
        dict2 = dictB.copy()

        # 考量到代码文本，英语不作检查
        if language == "英语" or language == "俄语":
            return True

        # 不同语言的标点符号字符集
        punctuation_sets = {
            '日语': r'[\u3000-\u303F\uFF01-\uFF9F]',  # 日文标点符号
            '韩语': r'[\u314F-\u3163\uFF61-\uFF9F]',  # 韩文标点符号和半角标点符号
            '俄语': r'[\u0400-\u04FF\u0500-\u052F]',  # 俄语字母和扩展字符（含标点）
            '简中': r'[\u3000-\u303F]',  # 中文标点符号
            '繁中': r'[\u3000-\u303F]',  # 中文标点符号
        }
        # 定义不同语言的文本字符集对应的正则表达式
        patterns_all = {
            '日语': re.compile(
                r'['
                r'\u3041-\u3096'  # 平假名
                r'\u30A0-\u30FF'  # 片假名
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
        # 根据语言选择合适的正则表达式
        pattern = patterns_all.get(language)
        punctuation_pattern = punctuation_sets.get(language)
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
                # 移除字典2值中的标点符号
                text2_clean = re.sub(punctuation_pattern, '', value2)
                # 提取字典2值中的指定语言的文本
                text2 = pattern.findall(text2_clean)
                # 将列表转换为字符串
                text2_str = ''.join(text2)
                # 如果字典2中的残留文本在字典1中的文本中出现，则计数加1
                if text2_str and (text2_str in text1):
                    count_results += 1

        # 避免检查单或者少行字典
        if len(dict2) >5 :
            if  count_results >=2:
                return False

        return True