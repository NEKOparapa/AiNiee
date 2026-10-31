"""Read-only editing rules exposed to clients through explicit API operations."""
import inspect

from Backend.core.headers import normalize_extra_headers, parse_extra_headers
from Backend.core.paths import (
    auto_output_dir, auto_polish_output_dir, default_input_dir,
    default_output_dir, default_polish_output_dir,
)
from Backend.domain.config.tables import TableConfigHelper
from Backend.domain.prompts.character_helper import CharacterHelper
from Backend.domain.prompts.glossary_helper import GlossaryHelper
from Backend.domain.prompts.prompt_builder_extraction import PromptBuilderExtraction
from Backend.domain.text.regex import RegexSwitchHelper
from Backend.infrastructure.llm.model_config_helper import ModelConfigHelper


OPERATIONS = {
    "table.get_tables": TableConfigHelper.get_tables,
    "table.new_table": TableConfigHelper.new_table,
    "table.normalize_rows": TableConfigHelper.normalize_rows,
    "table.merge_edited_rows": TableConfigHelper.merge_edited_rows,
    "table.normalize_match_options": TableConfigHelper.normalize_match_options,
    "regex.normalize_exclusion_rows": RegexSwitchHelper.normalize_exclusion_rows,
    "regex.normalize_replacement_rows": RegexSwitchHelper.normalize_replacement_rows,
    "regex.is_valid_re_pattern": RegexSwitchHelper.is_valid_re_pattern,
    "glossary.normalize_rows": GlossaryHelper.normalize_rows,
    "glossary.get_row_state": GlossaryHelper.get_row_state,
    "character.normalize_rows": CharacterHelper.normalize_rows,
    "model.get_thinking_level_options": ModelConfigHelper.get_thinking_level_options,
    "model.is_gemini_3_or_newer": ModelConfigHelper.is_gemini_3_or_newer,
    "extraction.get_user_prompts": PromptBuilderExtraction.get_user_prompts,
    "extraction.get_selected_user_prompt": PromptBuilderExtraction.get_selected_user_prompt,
    "headers.normalize": normalize_extra_headers,
    "headers.parse": parse_extra_headers,
    "paths.input": lambda: str(default_input_dir()),
    "paths.output": lambda: str(default_output_dir()),
    "paths.polish": lambda: str(default_polish_output_dir()),
    "paths.auto_output": auto_output_dir,
    "paths.auto_polish": auto_polish_output_dir,
}


def evaluate(operation, args, kwargs):
    handler = OPERATIONS.get(operation)
    if handler is None:
        raise ValueError("未知编辑操作")
    try:
        inspect.signature(handler).bind(*args, **kwargs)
        result = handler(*args, **kwargs)
    except (TypeError, KeyError) as error:
        raise ValueError("编辑操作参数不正确") from error
    response = {"result": result}
    # Validate all rows in one request; UI highlighting must not issue a request per row.
    if operation in ("glossary.normalize_rows", "regex.normalize_exclusion_rows", "regex.normalize_replacement_rows", "table.normalize_rows"):
        response["validation"] = [{
            "row": row, "state": GlossaryHelper.get_row_state(row),
            "src": RegexSwitchHelper.is_valid_re_pattern(row, "src"),
            "markers": RegexSwitchHelper.is_valid_re_pattern(row, "markers"),
        } for row in result]
    return response
