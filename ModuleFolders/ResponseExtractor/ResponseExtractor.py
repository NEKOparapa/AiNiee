import re
from typing import Dict, List

import rich
from rich.markup import escape


# 回复解析器
class ResponseExtractor:

    # 多行文本数字匹配格式
    # 目前有两个匹配组，第一个为标准数字序号部分，第二个为可能出现的多余引号组（常见于deepseek-v3）
    multiline_number_prefix = r'(\d+\.\d+\.)(")?[,，\s]?(?(2)"|)?'
    # 多行文本段结束后缀
    multiline_quote_suffix = r'(?:\n["“”][,，]|["“”]\n[,，]|["“”]?[,，]?)$'

    # 判断多行文本开始的正则
    multiline_start_reg = re.compile(rf'^\s*["“”]\s*{multiline_number_prefix}')
    # 提取多行文本边界的正则
    boundary_pattern_reg = re.compile(f'["“”][^"“”]*?{multiline_number_prefix}')
    # 提取规范数字序号与正文的正则
    extract_num_text_reg = re.compile(f'["“”][^"“”]*?{multiline_number_prefix}(.*?){multiline_quote_suffix}')

    def __init__(self):
        pass

    # 处理并正则提取翻译内容
    def text_extraction(self, source_text_dict, response_content):

        try:
            # 提取译文结果
            translation_result= ResponseExtractor.extract_translation(self,source_text_dict,response_content)

            return translation_result
        except Exception as e:
            print(f"\033[1;33mWarning:\033[0m 回复内容无法正常提取，请反馈\n错误信息: {str(e)}")
            return {},{},{}

    # 提取翻译结果内容
    def extract_translation(self,source_text_dict,html_string):

        # 提取翻译文本
        text_dict = ResponseExtractor.label_text_extraction(self,source_text_dict,html_string)

        if not text_dict:
            return {}  # 如果没有找到标签内容，返回空 JSON

        # 计算原文行数
        newlines_in_dict = ResponseExtractor.count_newlines_in_dict_values(self,source_text_dict)

        # 合并调整翻译文本
        translation_result= ResponseExtractor.generate_text_by_newlines(self,newlines_in_dict,text_dict)

        return translation_result

    # 辅助函数，正则提取标签文本内容
    def label_text_extraction(self,source_text_dict, html_string):

        # 只提取最后一个 textarea 标签的内容
        textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', html_string, re.DOTALL)
        if not textarea_contents:
            return {}  # 如果没有找到 textarea 标签，返回空字典
        last_content = textarea_contents[-1]

        # 提取文本存储到字典中
        output_dict = ResponseExtractor.extract_text_to_dict(self,last_content)

        # 如果原文是一行，则跳过过滤，主要是本地模型兼容
        if len(source_text_dict) == 1 :
             return output_dict 

        # 从第一个以数字序号开头的行开始，保留之后的所有行(主要是有些AI会在译文内容前面加点说明)
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

    # 提取文本为字典
    def extract_text_to_dict(self, input_string: str) -> Dict[str, str]:
        """
        从特定格式的字符串中提取内容并存入字典 。
        （目前因为AI偶尔会合并翻译，回复的列表块最后一个元素内容是这样的:"3.1."或者"3.1.[换行符]文本内容"，所以后期会检查出换行符不一致）
        Args:
            input_string: 输入的字符串。

        Returns:
            一个字典，键是'0', '1', '2'...，值是提取到的文本行。
        """
        # 1. 初步分割: 按主序号分割成块
        blocks = re.split(r'\n(?=\d+\.)', input_string.strip())

        extracted_items = []

        # 2. 处理每个块
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # 3. 尝试匹配列表块模式 (N.[ ... ])
            # re.DOTALL 使 '.' 可以匹配换行符
            list_block_match = re.match(r'^\d+\.\s*\[(.*)]$', block, re.DOTALL)
            if list_block_match:
                list_content = list_block_match.group(1).strip()
                # 再次判断是否是列表块内容(通过以特定模式开始作为判断)
                if list_content and ResponseExtractor.multiline_start_reg.match(list_content):
                    items = ResponseExtractor.extract_multiline_content(self, list_content)
                    extracted_items.extend(items)
                else:
                    # 如果方括号内的内容不像带引号列表 (例如 "9.[社团活动后]")
                    # 将整个原始块（包括 N.[...] ）视为一个单独的文本项。
                    extracted_items.append(block)
            else:
                # 4.2 文本块: 不是 N.[...] 格式，直接添加整个块内容
                extracted_items.append(block)

        # 5. 生成最终字典
        result_dict = {str(i): item for i, item in enumerate(extracted_items)}
        return result_dict

    def extract_multiline_content(self, text: str) -> List[str]:
        """
        从文本中提取引号包围的内容，处理嵌套引号。

        Args:
            text: 要处理的文本

        Returns:
            提取出的内容列表
            从捕获组1获取标准序号`n.n.`，然后从捕获组3获取正文，随后组装这两个组（以英文逗号分隔）并返回
        """
        result = []

        # 首先尝试找到所有可能的列表项边界
        # 这个模式匹配：引号 + 可能的空白 + 数字.数字.,
        boundaries = [m.start() for m in ResponseExtractor.boundary_pattern_reg.finditer(text)]

        # 如果找不到边界，返回空列表
        if not boundaries:
            return []

        # 添加文本结束作为最后一个边界
        boundaries.append(len(text))

        # 逐对处理边界
        for i in range(len(boundaries) - 1):
            segment = text[boundaries[i]:boundaries[i + 1]].strip()

            # 目前的 `multiline_number_prefix` 中有两个匹配组：
            # 第一个匹配数字序号n.n. 第二个匹配可能出现的多余引号
            # 因此这里的 `extract_num_text_reg` 使用第三个匹配组进行正文获取
            match = ResponseExtractor.extract_num_text_reg.search(segment)

            if match:
                try:
                    # 提取第1组(数字)和第3组(文本)
                    number_part = match.group(1)
                    text_part = match.group(3)

                    # 确保两个组都被成功捕获
                    if number_part is not None and text_part is not None:
                        # 去除`text_part`中可能出现的`number_part`
                        cleaned_text_part = text_part.replace(number_part, '').replace(number_part.rstrip('.'), '')
                        # 组合数字和文本，保留匹配到的 `text_part` 原始文本
                        assembled_content = f"{number_part},{cleaned_text_part}"
                        result.append(assembled_content)
                    else:
                        # 更详细地指明哪个部分为空
                        missing_parts = []
                        if number_part is None:
                            missing_parts.append("数字部分")
                        if text_part is None:
                            missing_parts.append("文本部分")

                        # 输出更详细的警告信息
                        rich.print(
                            f"[[red]WARNING[/]] 多行文本 提取失败：{', '.join(missing_parts)}为空。"
                            f"原始文本：{escape(match.group(0))[:50]}{'...' if len(match.group(0)) > 50 else ''} "
                        )
                except IndexError as e:
                    # 处理组不存在的情况，添加更详细的错误信息
                    rich.print(
                        f"[[red]WARNING[/]] 多行文本 提取索引错误：{str(e)}。无法从匹配中提取预期组。"
                        f"原始文本：{escape(match.group(0))[:50]}{'...' if len(match.group(0)) > 50 else ''} "
                    )
            else:
                # 添加未匹配情况的日志
                if segment and len(segment.strip()) > 0:  # 只记录非空段落
                    rich.print(
                        f"[[red]WARNING[/]] 多行文本 未找到匹配段落：{escape(segment[:50])}{'...' if len(segment) > 50 else ''} "
                    )

        return result

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


    # 去除数字序号及括号
    def remove_numbered_prefix(self, translation_text_dict):
        """
        去除翻译文本中的数字序号前缀。
        
        处理两个步骤：
        1. 去除各种变形序号（包括特殊前缀字符 + 数字序号 + 特殊后缀标点）
        2. 循环去除开头剩余的简单数字序号
        
        Args:
            translation_text_dict: 翻译文本字典
            
        Returns:
            处理后的文本字典
        """
        output_dict = {}
        for key, value in translation_text_dict.items():

            if not isinstance(value, str):
                output_dict[key] = value
                continue
                
            translation_lines = value.split('\n')
            cleaned_lines = []
            
            for i, line in enumerate(translation_lines):
                temp_line = line
                
                # 第一步：去除各种变形序号
                # 匹配模式：[可选空白][可选特殊前缀][数字序号][可选标点后缀][可选空白]
                # - 特殊前缀：「『【……□ 等引号、省略号、方框等字符
                # - 数字序号：支持 1. 或 1.2. 或 1.2.3. 等多级序号
                # - 标点后缀：, ， 、等中英文标点
                temp_line = re.sub(
                    r'^\s*[「『【（\(……□\s]*\d+(\.\d+)*\.[,，、]?\s*',
                    '',
                    temp_line
                )
                
                # 第二步：循环去除开头剩余的 数字. 格式
                # 处理可能存在的嵌套或多余的数字序号
                max_iterations = 2  # 设置最大迭代次数，防止意外无限循环
                for iteration in range(max_iterations):
                    new_line = re.sub(r'^\s*\d+\.\s*', '', temp_line)
                    # 如果没有变化，说明已经清理完毕
                    if new_line == temp_line:
                        break
                    temp_line = new_line
                
                cleaned_lines.append(temp_line)

            processed_text = '\n'.join(cleaned_lines)

            # 移除尾部的 "/n] 或 /n] (及其前面的空格)
            final_text = re.sub(r'\s*"?\n]$', '', processed_text)
            output_dict[key] = final_text
            
        return output_dict