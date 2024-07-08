
# coding:utf-8               
import json
import re







# 回复解析器
class Response_Parser():
    def __init__(self):
        pass
    

    #处理并正则提取翻译内容
    def process_content(self,input_str):

        # 尝试直接转换为json字典
        try:
            response_dict = json.loads(input_str) 
            return response_dict
        except :
            # 对格式进行修复       
            input_str = Response_Parser.repair_double_quotes(self,input_str)
            input_str = Response_Parser.repair_double_quotes_2(self,input_str)  
            #input_str = Response_Parser.repair_double_quotes_3(self,input_str)       


        # 再次尝试直接转换为json字典
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


    # 修复value前面的双引号
    def repair_double_quotes(self,text):
        # 消除文本中的空格
        text = text.replace(" ", "")
        # 正则表达式匹配双引号后跟冒号，并捕获第三个字符
        pattern = r'[\"]:(.)'
        # 使用finditer来找到所有匹配项
        matches = re.finditer(pattern, text)
        # 存储所有修改的位置
        modifications = [(match.start(1), match.group(1)) for match in matches]

        # 从后往前替换文本，这样不会影响后续匹配的位置
        for start, char in reversed(modifications):
            if char != '"':
                text = text[:start] + '"' + text[start:]

        return text

    # 修复value后面的双引号
    def repair_double_quotes_2(self,text):
        # 消除文本中的空格
        text = text.replace(" ", "")

        # 正则表达式匹配逗号后面跟换行符（可选）,再跟双引号的模式
        pattern = r',(?:\n)?\"'
        matches = re.finditer(pattern, text)
        result = []

        last_end = 0
        for match in matches:
            # 获取逗号前的字符
            quote_position = match.start()
            before_quote = text[quote_position - 1]
            
            # 检查逗号前的字符是否是双引号
            if before_quote == '"':
                # 如果是双引号，将这一段文本加入到结果中
                result.append(text[last_end:quote_position])
            else:
                # 如果不是双引号，将前一个字符换成'"'
                result.append(text[last_end:quote_position - 1] + '"')
            
            # 更新最后结束的位置
            last_end = quote_position

        # 添加剩余的文本
        result.append(text[last_end:])

        # 将所有片段拼接起来
        return ''.join(result)

    # 修复大括号前面的双引号
    def repair_double_quotes_3(self,text):
        # 消除文本中的空格
        text = text.replace(" ", "")

        # 正则表达式匹配逗号后面紧跟双引号的模式
        pattern = r'(?:\n)?}'
        matches = re.finditer(pattern, text)
        result = []

        last_end = 0
        for match in matches:
            # 获取逗号前的字符
            quote_position = match.start()
            before_quote = text[quote_position - 1]
            
            # 检查逗号前的字符是否是双引号
            if before_quote == '"':
                # 如果是双引号，将这一段文本加入到结果中
                result.append(text[last_end:quote_position])
            else:
                # 如果不是双引号，将前一个字符换成'"'
                result.append(text[last_end:quote_position - 1] + '"')
            
            # 更新最后结束的位置
            last_end = quote_position

        # 添加剩余的文本
        result.append(text[last_end:])

        # 将所有片段拼接起来
        return ''.join(result)

    # 检查回复内容是否存在问题
    def check_response_content(self,response_str,response_dict,source_text_dict,source_language):
        # 存储检查结果
        check_result = False
        # 存储错误内容
        error_content = "0"


        # 检查模型是否退化，出现高频词（只检测中日）
        if Response_Parser.model_degradation_detection(self,response_str):
            pass

        else:
            check_result = False
            # 存储错误内容
            error_content = "AI回复内容出现高频词,并重新翻译"
            return check_result,error_content


        # 检查文本行数
        if Response_Parser.check_text_line_count(self,source_text_dict,response_dict):
            pass
        else:
            check_result = False
            # 存储错误内容
            error_content = "提取到的文本行数与原来数量不符合,将进行重新翻译"
            return check_result,error_content


        # 检查文本空行
        if Response_Parser.check_empty_response(self,response_dict):
            pass
        else:
            check_result = False
            # 存储错误内容
            error_content = "AI回复内容中有未进行翻译的空行,将进行重新翻译"
            return check_result,error_content

        
        # 检查是否回复了原文
        if Response_Parser.check_dicts_equal(self,source_text_dict,response_dict):
            pass
        else:
            check_result = False
            # 存储错误内容
            error_content = "AI回复内容与原文相同，未进行翻译，将重新翻译"
            return check_result,error_content

        # 检查是否残留部分原文
        if Response_Parser.detecting_remaining_original_text(self,source_text_dict,response_dict,source_language):
            pass
        else:
            check_result = False
            # 存储错误内容
            error_content = "AI回复内容残留部分原文，未进行翻译，将重新翻译"
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

            if (result>= 0.80):
                return False
            else:
                return True

        else:
            return True
 
    # 检查回复内容的文本行数
    def check_text_line_count(self,source_text_dict,response_dict): 
        """
        检查字典d中是否包含从'0'到'(N-1)'的字符串键

        :param d: 输入的字典
        :param N: 数字N
        :return: 如果字典包含从'0'到'(N-1)'的所有字符串键，则返回True，否则返回False
        """
        N = len(source_text_dict) 
        return all(str(key) in response_dict for key in range(N))

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
    def detecting_remaining_original_text(self,dict1, dict2, language):

        # 考量到代码文本，英语不作检查
        if language == "英语":
            return True

        # 定义不同语言的正则表达式
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
                # 提取字典2值中的指定语言的文本
                text2 = pattern.findall(value2)
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