from ModuleFolders.TaskExecutor import TranslatorUtil

from ModuleFolders.ResponseChecker.BaseChecks import (
    check_text_line_count,
    check_empty_response,
    check_dict_order,
    contains_special_chars
)

from ModuleFolders.ResponseChecker.AdvancedChecks import (
    check_multiline_text, 
    check_dicts_equal, 
    detecting_remaining_original_text, 
    check_placeholders_exist,
    check_reply_format
)

class ResponseChecker():
    def __init__(self):
        pass

    def check_response_content(self, config, placeholder_order, response_str, response_dict, source_text_dict, source_lang):

        source_language = TranslatorUtil.map_language_code_to_name(source_lang)
        response_check_switch = config.response_check_switch

        # 基本检查
        # 检查接口是否拒绝翻译
        if not contains_special_chars(response_str):
            error_content = f"模型已拒绝翻译或格式错误，回复内容：\n{response_str}"
            return False, error_content

        # 检查文本行数    
        if not check_text_line_count(source_text_dict, response_dict):
            return False, "【行数错误】 - 行数不一致"

        # 检查文本空行
        if not check_empty_response(response_dict):
            return False, "【行数错误】 - 行数无法对应"
        
        # 检查数字序号是否正确
        if not check_dict_order(source_text_dict, response_dict):
            return False, "【行数错误】 - 出现错行串行"

        # 进阶检查
        # 多行文本块检查
        if response_check_switch.get('newline_character_count_check', False):
            if not check_multiline_text(source_text_dict, response_dict):
                return False, "【换行符数】 - 译文换行符数量不一致"
        
        # 返回原文检查
        if response_check_switch.get('return_to_original_text_check', False):
            if not check_dicts_equal(source_text_dict, response_dict):
                return False, "【返回原文】 - 译文与原文完全相同"
        
        # 残留原文检查
        if response_check_switch.get('residual_original_text_check', False):
            if not detecting_remaining_original_text(
                source_text_dict, 
                response_dict, 
                source_language,
            ):
                return False, "【翻译残留】 - 译文中残留部分原文"

        # 回复格式检查
        if response_check_switch.get('reply_format_check', False):
            if not check_reply_format(source_text_dict, response_dict):
                return False, "【格式错误】 - 回复格式与原文格式不匹配（单行/多行）"

        # 占位符检查
        if not check_placeholders_exist(placeholder_order, response_dict):
            return False, "【自动处理】 - 未正确保留全部的占位符"

        # 全部检查通过
        return True, "检查无误"


    def check_polish_response_content(self, config, response_str, response_dict, source_text_dict):

        response_check_switch = config.response_check_switch

        # 检查接口是否拒绝翻译
        if not contains_special_chars(response_str):
            error_content = f"模型已拒绝翻译或格式错误，回复内容：\n{response_str}"
            return False, error_content

        # 检查文本行数    
        if not check_text_line_count(source_text_dict, response_dict):
            return False, "【行数错误】 - 行数不一致"

        # 检查文本空行
        if not check_empty_response(response_dict):
            return False, "【行数错误】 - 行数无法对应"
        
        # 检查数字序号是否正确
        if not check_dict_order(source_text_dict, response_dict):
            return False, "【行数错误】 - 出现错行串行"

        # 多行文本块检查
        if response_check_switch.get('newline_character_count_check', False):
            if not check_multiline_text(source_text_dict, response_dict):
                return False, "【换行符数】 - 换行符数量不一致"

        # 全部检查通过
        return True, "检查无误"