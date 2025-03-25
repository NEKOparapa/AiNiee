import ast
import re
import string

# 回复解析器
class ResponseExtractor():
    def __init__(self):
        pass



    #处理并正则提取翻译内容
    def text_extraction(self, source_text_dict, html_string, target_language):

        try:
            # 提取译文结果
            translation_result= ResponseExtractor.extract_translation(self,source_text_dict,html_string)

            # 提取术语表结果
            glossary_result= ResponseExtractor.extract_glossary(self,html_string, target_language)

            # 提取禁翻表结果
            NTL_result = NTL_result = ResponseExtractor.extract_ntl(self,html_string)

            return translation_result, glossary_result, NTL_result
        except :
            print("\033[1;33mWarning:\033[0m 回复内容无法正常提取，请反馈\n")
            return {},{},{}


    # 提取翻译结果内容
    def extract_translation(self,source_text_dict,html_string):

        # 处理新格式至原始格式
        html_string = ResponseExtractor.convert_array_to_numbered_format(self,html_string)
        # 提取翻译文本
        text_dict = ResponseExtractor.label_text_extraction(self,html_string)

        if not text_dict:
            return {}  # 如果没有找到标签内容，返回空 JSON

        # 计算原文行数
        newlines_in_dict = ResponseExtractor.count_newlines_in_dict_values(self,source_text_dict)

        # 合并调整翻译文本
        translation_result= ResponseExtractor.generate_text_by_newlines(self,newlines_in_dict,text_dict)


        return translation_result

    # 新增函数：处理数组格式的文本
    def convert_array_to_numbered_format(self, html_string):
        """
        处理新的数组格式HTML字符串，转换为原来的格式。

        Args:
            html_string: 包含数组格式的HTML字符串。

        Returns:
            处理后的HTML字符串，格式与原来一致。
        """
        textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', html_string, re.DOTALL)
        if not textarea_contents:
            return html_string  # 如果没有找到 textarea 标签，返回原始字符串

        result_lines = []
        last_content = textarea_contents[-1]
        lines = last_content.strip().splitlines()

        current_line_num = None
        array_content_lines = []

        for line in lines:
            # 检查是否为数组开始行
            array_start_match = re.match(r'^(\d+)\. ?\[$', line.strip())
            if array_start_match:
                current_line_num = array_start_match.group(1)
                array_content_lines = []
                continue

            # 检查是否为数组结束行
            if line.strip() == ']':
                if current_line_num and array_content_lines:
                    try:
                        # 处理收集到的数组内容
                        converted_items = []
                        for i, item in enumerate(array_content_lines):
                            # 提取[n]#(文本)格式
                            text_match = re.match(r'^[\"|“”]#\d+\[(\d+)]\*(.*?)[\"|”“],?$', item.strip())
                            if text_match:
                                item_num = text_match.group(1)
                                text = text_match.group(2)
                                # 如果字符串去除首尾空白字符后为空，则跳过
                                if not text.strip():
                                    continue
                                # 传过来的原始html字符串会发生奇怪的多次转义问题，这里先用ast解析处理一下
                                text = ast.literal_eval('"' + text + '"')
                                converted_items.append(f"{current_line_num}.{item_num}.({text})")

                        # 添加转换后的行
                        result_lines.extend(converted_items)
                    except (SyntaxError, ValueError, IndexError) as e:
                        # 只捕获可能的解析错误类型
                        result_lines.append(f"{current_line_num}.(解析错误: {str(e)})")

                    current_line_num = None
                continue

            # 如果在数组内容中，添加到数组内容行
            if current_line_num is not None:
                array_content_lines.append(line.strip())
            else:
                # 处理普通行，去掉序号后多余的空格
                modified_line = re.sub(r'(\d+\.) ', r'\1', line)
                # 保留处理后的普通行
                result_lines.append(modified_line)

        # 重新构建textarea内容
        return f"<textarea>\n{chr(10).join(result_lines)}\n</textarea>"

    # 辅助函数，正则提取标签文本内容
    def label_text_extraction(self, html_string):
        textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', html_string, re.DOTALL)
        if not textarea_contents:
            return {}  # 如果没有找到 textarea 标签，返回空字典

        output_dict = {}
        line_number = 0

        # 只处理最后一个 textarea 标签的内容
        last_content = textarea_contents[-1]
        lines = last_content.strip().splitlines()
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
            if newline_count == 0:
                newline_counts[key] = newline_count  # 将统计结果存入新字典，键保持不变
            else:
                newline_counts[key] = newline_count
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
    def remove_numbered_prefix(self,source_text_dict,translation_text_dict):
        """
        根据源文本的换行符数量，动态去除输入文本中对应的层级数字序号。
        
        逻辑说明：
        1. 源文本中换行符数量决定了序号层级（m个换行符对应m+1个子行）
        2. 主序号由字典键值+1决定（如键'0'的主序号是1，键'1'的主序号是2）
        3. 根据换行符数量选择匹配模式：
        - 无换行符：匹配"主序号."
        - 有换行符：匹配"主序号.子序号."
        """

        output_dict = {}
        for key, value in translation_text_dict.items():
            if not isinstance(value, str):
                output_dict[key] = value
                continue

            # 获取源文本的换行符数量
            source_text = source_text_dict.get(key, "")
            newline_count = source_text.count("\n")

            # 分割输入文本为多行处理
            lines = value.split("\n")
            cleaned_lines = []

            for line in lines:
                # 根据换行情况构建匹配模式
                if newline_count == 0:
                    # 匹配"主序号."模式（如"1."）
                    pattern = rf"^\d+\.\s*"  # 行首正则
                else:
                    # 匹配"主序号.子序号."模式（如"2.1."）
                    pattern = rf"^\d+\.\d+\.\s*"

                # 执行替换操作
                cleaned_line = re.sub(pattern, "", line)
                cleaned_lines.append(cleaned_line)

            # 重组处理后的文本
            output_dict[key] = "\n".join(cleaned_lines)

        return output_dict

    # 去除数字序号及括号
    def remove_numbered_prefix(self, source_text_dict, translation_text_dict):
        output_dict = {}
        for key, value in translation_text_dict.items():
            if not isinstance(value, str):
                output_dict[key] = value
                continue

            source_text = source_text_dict.get(key, "")
            source_lines = source_text.split('\n')
            translation_lines = value.split('\n')
            cleaned_lines = []

            for i, line in enumerate(translation_lines):

                # 去除数字序号 (只匹配 "1.", "1.2." 等)
                temp_line = re.sub(r'^\s*\d+\.(\d+\.)?\s*', '', line)

                source_line = source_lines[i] if i < len(source_lines) else ""

                # 计算源行开头的左括号数量
                stripped_source = source_line.lstrip()
                leading_source = 0
                for char in stripped_source:
                    if char in ('(', '（'):
                        leading_source += 1
                    else:
                        break

                # 计算源行结尾的右括号数量
                stripped_source_end = source_line.rstrip()
                trailing_source = 0
                for char in reversed(stripped_source_end):
                    if char in (')', '）'):
                        trailing_source += 1
                    else:
                        break

                # 处理译行开头的左括号
                leading_match = re.match(r'^(\s*)([\(\（]*)', temp_line)
                if leading_match:
                    space, brackets = leading_match.groups()
                    adjusted = brackets[:leading_source]
                    remaining = temp_line[len(space) + len(brackets):]
                    temp_line = f"{space}{adjusted}{remaining}"

                # 处理译行结尾的右括号
                trailing_match = re.search(r'([\)\）]*)(\s*)$', temp_line)
                if trailing_match:
                    brackets, space_end = trailing_match.groups()
                    adjusted = brackets[:trailing_source]
                    remaining = temp_line[:-len(brackets + space_end)] if (brackets + space_end) else temp_line
                    temp_line = f"{remaining}{adjusted}{space_end}"

                cleaned_lines.append(temp_line.strip())

            output_dict[key] = '\n'.join(cleaned_lines)

        return output_dict

    # 提取回复中的术语表内容
    def extract_glossary(self, text, target_language):
        """
        从文本中提取<character>标签内的术语表

        参数：
            text (str): 原始文本内容

        返回：
            list[tuple]: 包含(原文, 译文, 备注)的列表，没有匹配内容时返回空列表
        """
        # 匹配完整的character标签内容（支持多行内容）
        glossary_match = re.search(
            r'<character[^>]*>(.*?)</character>',  # 兼容标签属性
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
            if ResponseExtractor._is_invalid_glossary_entry(self,original, translation, comment, target_language):
                continue
            else:
                entries.append((original, translation, comment))

        return entries

    # 术语表过滤规则
    def _is_invalid_glossary_entry(self, original, translation, info, target_language):
        """判断条目是否需要过滤"""
        # 非空检查
        if not original.strip() :
            return True

        # 过滤表头行
        if original.strip().lower() in ("原文", "原名", "名字", "source", "original", "name"):
            return True

        # 过滤提取错行
        if translation.strip() in ("|"):
            return True

        # 过滤提取错行
        if (info) and (info.strip() in ("|")):
            return True

        # 过滤无翻译行
        if original.strip() == translation.strip():
            return True

        # 过滤翻译成罗马音(待改进，可以精简一个输入参数)
        if (target_language != "english") and (ResponseExtractor.is_pure_english_text(self,translation)):
            return True

        # 过滤过长行
        if len(original) > 20 or len(translation) > 20:
            return True

        # 过滤有点无语的东西
        if original.lower() in ("俺", "俺たち", "なし", "姉ちゃん", "彼女", "我", "私", "你", "他", "她"):
            return True

        # 过滤有点无语的东西
        if translation.lower() in ("主人"):
            return True

        # 过滤下划线+随机英文+下划线文本内容，像“_HERO_”这样的内容
        if re.fullmatch(r'_([a-zA-Z]+)_', original):
            return True

        # 过滤换行符或制表符
        if original == '\n' or original == '\t' or original == '\r':
            return True

        # 过滤纯数字（匹配整数）
        if re.fullmatch(r'^\d+$', original) :
            return True


        return False

    # 检查是否纯英文
    def is_pure_english_text(self,text):
        """
        检查给定的文本是否为纯英文字母（允许空格和换行符）。

        Args:
            text: 要检查的文本字符串。

        Returns:
            如果文本是纯英文字母，则返回 True，否则返回 False。
        """
        for char in text:
            if char not in string.ascii_letters and char != ' ' and char != '\n':
                return False
        return True

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

    # 禁翻表过滤规则
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