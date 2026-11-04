from Backend.domain import languages as TranslatorUtil
from Backend.domain.text.epub_markup import TOKEN_RE, validate_tokens

from Backend.domain.responses.base_checks import (
    check_text_line_count,
    check_empty_response,
    check_dict_order,
    contains_special_chars
)

from Backend.domain.responses.advanced_checks import (
    check_multiline_text, 
    check_dicts_equal, 
    detecting_remaining_original_text, 
    check_placeholders_exist,
)

class ResponseChecker():
    def __init__(self):
        pass

    @staticmethod
    def check_response_items(config, placeholder_order, response_str, response_dict, source_text_dict, source_lang):
        """Validate alignment for the whole reply, then localize content errors.

        A broken envelope, key set or numbering makes every mapping unsafe.
        Once those pass, a bad translation need not erase its valid neighbours.
        Return (batch_error, errors_by_response_key).
        """
        switches = config.response_check_switch
        if not isinstance(response_str, str) or not contains_special_chars(response_str):
            return "模型已拒绝翻译或格式错误", {}
        if not isinstance(response_dict, dict) or not check_text_line_count(source_text_dict, response_dict):
            return "【行数错误】 - 行数不一致", {}
        if any(not isinstance(value, str) or not value.strip() for value in response_dict.values()):
            return "【行数错误】 - 行数无法对应", {}
        if not check_dict_order(source_text_dict, response_dict):
            return "【行数错误】 - 出现错行串行", {}

        semantic_source = {key: TOKEN_RE.sub('', text) for key, text in source_text_dict.items()}
        semantic_response = {key: TOKEN_RE.sub('', text) for key, text in response_dict.items()}
        # Keep the existing batch-level similarity heuristic. Testing each
        # proper name independently would reject unchanged Ubuntu/Windows etc.
        returned_original = switches.get('return_to_original_text_check', False) and not check_dicts_equal(
            semantic_source, semantic_response)
        source_language = TranslatorUtil.map_language_code_to_name(source_lang)
        errors = {}
        for key, source in source_text_dict.items():
            response = response_dict[key]
            one_source, one_response = {key: source}, {key: response}
            semantic_one_source = {key: semantic_source[key]}
            semantic_one_response = {key: semantic_response[key]}
            if not validate_tokens(source, response):
                errors[key] = "【EPUB 注释】 - 链接标记缺失、重复或顺序错误"
            elif switches.get('newline_character_count_check', False) and not check_multiline_text(
                    one_source, one_response, check_single=True):
                errors[key] = "【换行符数】 - 译文换行符数量不一致"
            elif returned_original and not check_dicts_equal(
                    semantic_one_source, semantic_one_response, check_single=True):
                errors[key] = "【返回原文】 - 译文与原文完全相同"
            elif switches.get('residual_original_text_check', False) and not detecting_remaining_original_text(
                    semantic_one_source, semantic_one_response, source_language, check_single=True):
                errors[key] = "【翻译残留】 - 译文中残留部分原文"
            elif not check_placeholders_exist({key: placeholder_order.get(key, [])}, one_response):
                errors[key] = "【自动处理】 - 未正确保留全部的占位符"
        return None, errors

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

        if any(not validate_tokens(text, response_dict[key]) for key, text in source_text_dict.items()):
            return False, "【EPUB 注释】 - 链接标记缺失、重复或顺序错误"

        # 结构标记不参与语义相似度和残留原文判断。
        semantic_source = {key: TOKEN_RE.sub('', text) for key, text in source_text_dict.items()}
        semantic_response = {key: TOKEN_RE.sub('', text) for key, text in response_dict.items()}

        # 进阶检查
        # 多行文本块检查
        if response_check_switch.get('newline_character_count_check', False):
            if not check_multiline_text(source_text_dict, response_dict):
                return False, "【换行符数】 - 译文换行符数量不一致"
        
        # 返回原文检查
        if response_check_switch.get('return_to_original_text_check', False):
            if not check_dicts_equal(semantic_source, semantic_response):
                return False, "【返回原文】 - 译文与原文完全相同"
        
        # 残留原文检查
        if response_check_switch.get('residual_original_text_check', False):
            if not detecting_remaining_original_text(
                semantic_source,
                semantic_response,
                source_language,
            ):
                return False, "【翻译残留】 - 译文中残留部分原文"

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

        if any(not validate_tokens(text, response_dict[key]) for key, text in source_text_dict.items()):
            return False, "【EPUB 注释】 - 链接标记缺失、重复或顺序错误"

        # 多行文本块检查
        if response_check_switch.get('newline_character_count_check', False):
            if not check_multiline_text(source_text_dict, response_dict):
                return False, "【换行符数】 - 换行符数量不一致"

        # 全部检查通过
        return True, "检查无误"
