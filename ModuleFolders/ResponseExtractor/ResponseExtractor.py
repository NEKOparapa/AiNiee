import re

# 回复解析器
class ResponseExtractor():
    def __init__(self):
        pass



    #处理并正则提取翻译内容
    def text_extraction(self,source_text_dict,html_string):

        try:
            # 提取译文结果
            translation_result= ResponseExtractor.extract_translation(self,source_text_dict,html_string)

            # 提取术语表结果
            glossary_result= ResponseExtractor.extract_glossary(self,html_string)

            # 提取禁翻表结果
            NTL_result = NTL_result = ResponseExtractor.extract_ntl(self,html_string)

            return translation_result, glossary_result, NTL_result
        except :
            print("\033[1;33mWarning:\033[0m 回复内容无法正常提取，请反馈\n")
            return {},{},{}


    # 提取翻译结果内容
    def extract_translation(self,source_text_dict,html_string):

        # 提取翻译文本
        text_dict = ResponseExtractor.label_text_extraction(self,html_string)

        if not text_dict:
            return {}  # 如果没有找到标签内容，返回空 JSON

        # 计算原文行数
        newlines_in_dict = ResponseExtractor.count_newlines_in_dict_values(self,source_text_dict)

        # 合并调整翻译文本
        translation_result= ResponseExtractor.generate_text_by_newlines(self,newlines_in_dict,text_dict)


        return translation_result


    # 辅助函数，正则提取标签文本内容(可能需要改进为正则提取)
    def label_text_extraction(self, html_string):
        textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', html_string, re.DOTALL)
        if not textarea_contents:
            return {}  # 如果没有找到 textarea 标签，返回空字典

        output_dict = {}
        line_number = 0

        # 只处理最后一个 textarea 标签的内容
        last_content = textarea_contents[-1]

        def process_multiline(match):
            # lines_attr = match.group(1)
            content = match.group(2)

            # # 提取lines属性的值
            # 已省略行数标记，暂时不需要
            # lines_count = int(re.search(r'lines="(\d+)"', lines_attr).group(1))

            # 分割内容行
            content_lines = content.strip().splitlines()
            # actual_lines = len(content_lines)

            # # 仅当声明行数与实际行数不一致时才输出
            # if lines_count != actual_lines:
            #     print(f"---- 生成行数不一致！multiline标签声明行数: {lines_count}, 实际行数: {actual_lines} ----")

            # 去掉每行前面的数字序号，并提取内容
            processed_lines = []
            for line in content_lines:
                # 匹配 #数字~文本~ 格式
                match = re.search(r'^#\d+\*(.+)\*$', line.strip())
                if match:
                    processed_text = match.group(1)
                    processed_lines.append(processed_text)
                else:
                    # 如果不符合预期格式，返回空行
                    processed_lines.append("")

            # 返回处理后的内容（不包含multi标签）
            return '\n'.join(processed_lines)

        # 处理所有的multiline标签
        processed_content = re.sub(r'\n?<multiline(.*?)>(.*?)</multiline>', process_multiline, last_content,
                                   flags=re.DOTALL)

        lines = processed_content.strip().splitlines()
        for line in lines:
            if line:
                output_dict[str(line_number)] = line
                line_number += 1

        # 如果没有找到任何以数字序号开头的行，则直接返回原始的行号字典（主要是为了兼容Sakura模型接口）
        has_numbered_prefix = False
        for value in output_dict.values():
            if re.match(r'^\d+\.', value):
                has_numbered_prefix = True
                break  # 只要找到一行符合条件就跳出循环

        # 从第一个以数字序号开头的行开始，保留之后的所有行(主要是有些AI会在译文内容前面加点说明)
        if has_numbered_prefix:
            filtered_dict = {}
            found = False
            # 按行号顺序遍历
            for key in sorted(output_dict.keys(), key=lambda k: int(k)):
                value = output_dict[key]
                if not found:
                    if re.match(r'^\d+\.', value):  # 匹配以数字和句点开头的行
                        found = True
                    else:
                        continue
                if found:
                    filtered_dict[key] = value
            return filtered_dict
        else:
            return output_dict  # 如果没有找到数字序号开头的行，则返回原始字典


    # 辅助函数，统计原文中的换行符
    def count_newlines_in_dict_values(self,source_text_dict):
        """
        统计字典中每个文本值内的换行符数量，并生成一个包含换行符统计结果的新字典。

        Args:
            source_text_dict: 输入字典，键为字符串，值为文本字符串。

        Returns:
            一个字典，键与输入字典相同，值为对应文本字符串中的换行符数量。
            例如：
            {'0': 0, '1': 1, '2': 0}
        """
        newline_counts = {}  # 初始化一个空字典用于存储换行符数量

        for key, text in source_text_dict.items():
            newline_count = text.count('\n')  # 使用字符串的count()方法统计换行符数量
            newline_counts[key] = newline_count  # 将统计结果存入新字典，键保持不变

        return newline_counts

    # 辅助函数，根据换行符数量生成最终译文字典，与原文字典进行一一对应
    def generate_text_by_newlines(self, newline_counts_dict, translation_text_dict):
        """
        根据换行符统计字典和源文本字典生成新的字典，并处理多余内容。

        Args:
            newline_counts_dict: 换行符统计字典，键为字符串序号，值为换行符数量。
            translation_text_dict: 源文本字典，键为字符串序号，值为文本内容。

        Returns:
            一个新的字典，键与 newline_counts_dict 相同，值为根据换行符数量从 translation_text_dict
            中提取并拼接的文本内容。如果 translation_text_dict 内容不足，对应值为空字符串。
            如果 translation_text_dict 有剩余内容，将添加新键值对，键为最大原键加1，值为剩余内容按换行拼接。
        """
        result_dict = {}
        translation_keys_sorted = sorted(translation_text_dict.keys(), key=int)
        translation_index = 0

        # 处理每个预定键的行数需求
        for key, newline_count in newline_counts_dict.items():
            extracted_lines = []
            num_lines_to_extract = newline_count + 1 if newline_count > 0 else 1

            for _ in range(num_lines_to_extract):
                if translation_index < len(translation_keys_sorted):
                    current_key = translation_keys_sorted[translation_index]
                    extracted_lines.append(translation_text_dict[current_key])
                    translation_index += 1
                else:
                    break

            if extracted_lines:
                result_dict[key] = '\n'.join(extracted_lines) if newline_count > 0 else extracted_lines[0]
            else:
                result_dict[key] = ''

        # 添加剩余内容为新键值对
        if translation_index < len(translation_keys_sorted):
            if newline_counts_dict:
                max_key = max(map(int, newline_counts_dict.keys()))
            else:
                max_key = 0
            new_key = str(max_key + 1)
            remaining_texts = [translation_text_dict[k] for k in translation_keys_sorted[translation_index:]]
            result_dict[new_key] = '\n'.join(remaining_texts)

        return result_dict

    # 辅助函数，去除数字序号
    def remove_numbered_prefix(self, input_dict):
        """
        遍历字典的值，检查每个值是否以数字加英文句点开头，如果是，则去除第一个匹配项。

        Args:
            input_dict: 输入的字典。

        Returns:
            一个新的字典，其中值已经去除数字前缀（如果存在）。
        """

        # 如果没有找到任何以数字序号开头的行，则直接返回原始的行号字典（主要是为了兼容Sakura模型接口）
        has_numbered_prefix = False
        for value in input_dict.values():
            if re.match(r'^\d+\.', value):
                has_numbered_prefix = True
                break  # 只要找到一行符合条件就跳出循环

        if has_numbered_prefix:
            output_dict = {}
            for key, value in input_dict.items():
                if isinstance(value, str):  # 确保值是字符串类型，避免处理非字符串值时出错
                    # 使用正则表达式匹配以数字和英文句点开头的模式
                    match = re.match(r"^\d+\.\s*", value)  # ^ 表示字符串开头，\d+ 表示一个或多个数字，\. 表示英文句点，\s* 表示零个或多个空白字符（可选）
                    if match:
                        # 如果匹配成功，则去除匹配到的前缀
                        prefix_length = match.end()  # 获取匹配到的前缀的结束位置
                        modified_value = value[prefix_length:]  # 切片字符串，去除前缀部分
                        output_dict[key] = modified_value
                    else:
                        # 如果不匹配，则保持原始值
                        output_dict[key] = value
                else:
                    # 如果值不是字符串，则保持原始值
                    output_dict[key] = value
            return output_dict

        else:
            return input_dict



    # 提取回复中的术语表内容
    def extract_glossary(self, text):
        """
        从文本中提取<glossary>标签内的术语表

        参数：
            text (str): 原始文本内容

        返回：
            list[tuple]: 包含(原文, 译文, 备注)的列表，没有匹配内容时返回空列表
        """
        # 匹配完整的glossary标签内容（支持多行内容）
        glossary_match = re.search(
            r'<glossary[^>]*>(.*?)</glossary>',  # 兼容标签属性
            text,
            re.DOTALL | re.IGNORECASE
        )

        if not glossary_match:
            return []

        content = glossary_match.group(1).strip()
        if not content:
            return []

        # 解析具体条目
        entries = []

        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue  # 跳过空行

            # 使用分隔符拆分字段（最多拆分成3个部分）
            parts = [part.strip() for part in line.split('|', 2)]

            # 有效性检查：至少需要原文和译文两个字段
            if len(parts) < 2:
                continue

            original, translation = parts[0], parts[1]
            comment = parts[2] if len(parts) >= 3 else ""



            # 检查并过滤错误内容
            if ResponseExtractor._is_invalid_glossary_entry(self,original, translation, comment):
                continue
            else:
                entries.append((original, translation, comment))

        return entries



    def _is_invalid_glossary_entry(self, original, translation, info):
        """判断条目是否需要过滤"""
        # 非空检查
        if not original.strip() :
            return True

        # 过滤表头行
        if original.strip().lower() in ("原文", "source", "原名"):
            return True

        # 过滤无翻译行
        if original.strip() == translation.strip():
            return True

        # 过滤提取错行
        if translation.lower() in ("|"):
            return True

        # 过滤过长行
        if len(original) > 40 or len(translation) > 40:
            return True

        # 过滤有点无语的东西
        if original.lower() in ("俺", "俺たち", "姉ちゃん", "彼女", "我", "你", "他", "她"):
            return True

        # 增加过滤检查，过滤下划线+随机英文+下划线文本内容，像“_HERO_”这样的内容
        if re.fullmatch(r'_([a-zA-Z]+)_', original):
            return True

        # 过滤换行符或制表符
        if original == '\n' or original == '\t' or original == '\r':
            return True

        # 过滤纯数字（匹配整数）
        if re.fullmatch(r'^\d+$', original) :
            return True


        return False




    # 提取回复中的禁翻表内容
    def extract_ntl(self, text):
        """
        从文本中提取<code>标签内的术语表

        参数：
            text (str): 原始文本内容

        返回：
            list[tuple]: 包含(原文, 译文, 备注)的列表，没有匹配内容时返回空列表
        """
        # 匹配完整的code>标签内容（支持多行内容）
        code_match = re.search(
            r'<code[^>]*>(.*?)</code>',  # 兼容标签属性
            text,
            re.DOTALL | re.IGNORECASE
        )

        if not code_match:
            return []

        content = code_match.group(1).strip()
        if not content:
            return []

        # 解析具体条目
        entries = []

        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue  # 跳过空行

            # 使用分隔符拆分字段（最多拆分成2个部分）
            parts = [part.strip() for part in line.split('|', 1)]

            # 有效性检查：至少需要原文和译文两个字段
            if len(parts) < 1:
                continue

            original = parts[0]
            info = parts[1] if len(parts) >= 2 else ""


            # 检查并过滤错误内容
            if ResponseExtractor._is_invalid_NTL_entry(self,original, info):
                continue
            else:
                entries.append((original, info))

        return entries


    def _is_invalid_NTL_entry(self, original, info):
        """判断条目是否需要过滤"""
        # 非空检查
        if not original.strip() :
            return True

        # 过滤表头行
        if original.lower() in ("markers", "标记符", "备注","原文", "source"):
            return True

        # 过滤提取错行
        if info.lower() in ("|"):
            return True

        # 过滤常见符号
        if original.strip() in ("#","「","」","『","』","※","★","？","！","～","…","♥","♡","^^","『』","♪","･･･","ー","（ ）","!!","无","\\n"):
            return True

        # 过滤换行符或制表符
        if original.strip() == '\n' or original.strip() == '\t' or original.strip() == '\r':
            return True

        # 过滤纯数字（匹配整数）
        if re.fullmatch(r'^\d+$', original):
            return True

        # 过滤纯英文（匹配大小写字母组合）
        if re.fullmatch(r'^[a-zA-Z]+$', original):
            return True

        # 新增：过滤被方括号/中文括号包围的数字（如[32]、【57】）
        if re.fullmatch(r'^[\[【]\d+[\]】]$', original):
            return True

        # 新增：过滤纯英文字母和数字的组合（如abc123）
        if re.fullmatch(r'^[a-zA-Z0-9]+$', original):
            return True

        return False