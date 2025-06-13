

# 检查接口是否拒绝翻译，而返回一段话
def contains_special_chars(s: str) -> bool:
    special_chars = ['<', '>', '/']
    return any(char in s for char in special_chars)

# 检查数字序号是否正确
def check_dict_order(source_text_dict,input_dict):
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

# 检查回复内容的文本行数
def check_text_line_count(source_dict, response_dict):
    return (
        len(source_dict) > 0 and len(response_dict) > 0 # 数据不为空
        and len(source_dict) == len(response_dict) # 原文与译文行数一致
        and all(str(key) in response_dict for key in range(len(source_dict))) # 译文的 Key 的值为从 0 开始的连续数值字符
    )

# 检查翻译内容是否有空值
def check_empty_response(response_dict):
    for value in response_dict.values():
        #检查value是不是None，因为AI回回复null，但是json.loads()会把null转化为None
        if value is None:
            return False

        # 检查value是不是空字符串，因为AI回回复空字符串，但是json.loads()会把空字符串转化为""
        if value == "":
            return False

    return True

