"""从旧设置页抽取的默认值，与界面和传输框架无关。"""

from copy import deepcopy

from ModuleFolders.Config.FilePathConfig import default_output_dir, default_polish_output_dir


SETTING_DEFAULTS = {
    "lines_limit_switch": False,
    "tokens_limit_switch": True,
    "lines_limit": 10,
    "tokens_limit": 1024,
    "user_thread_counts": 0,
    "request_timeout": 120,
    "round_limit": 10,
    "auto_set_output_path": True,
    "output_filename_suffix": "_translated",
    "bilingual_text_order": "translation_first",
    "translation_result_check_switch": False,
    "response_conversion_toggle": False,
    "opencc_preset": "s2t",
    "keep_original_encoding": False,
    "extract_task_token_limit": 10000,
    "auto_extract_non_translate_switch": False,
    "extract_short_name_merge_switch": True,
    "source_language": "auto",
    "target_language": "chinese_simplified",
    "language_filter_switch": False,
    "code_filter_switch": False,
    "pre_line_counts": 0,
    "few_shot_and_example_switch": True,
    "auto_process_text_code_segment": False,
    "text_symbol_repair_switch": False,
    "response_check_switch": {
        "return_to_original_text_check": True,
        "residual_original_text_check": True,
        "newline_character_count_check": True,
        "reply_format_check": False,
    },
    "polishing_pre_line_counts": 10,
    "theme": "auto",
    "accent_color": "#808b9d",
    "interface_language_setting": "简中",
}


def setting_defaults() -> dict:
    """路径在调用时解析，支持原有便携模式及用户目录覆盖。"""
    return {
        **deepcopy(SETTING_DEFAULTS),
        "label_output_path": str(default_output_dir()),
        "label_polish_output_path": str(default_polish_output_dir()),
    }


def fill_setting_defaults(config: dict) -> dict:
    """只为响应填补缺失值，保留老用户配置、扩展键和未知检查规则。"""
    result = deepcopy(config)
    for key, default in setting_defaults().items():
        if key not in result:
            result[key] = default
        elif isinstance(default, dict) and isinstance(result[key], dict):
            result[key] = {**default, **result[key]}
    return result
