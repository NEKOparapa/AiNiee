"""
角色称呼变体（本名+敬称）扫描与提示词路由测试。

运行：.venv/bin/python tests/test_character_name.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ModuleFolders.Domain.PromptBuilder.CharacterHelper import CharacterHelper
from ModuleFolders.Domain.PromptBuilder.CharacterNameHelper import CharacterNameHelper
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.Domain.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.Domain.PromptBuilder.PromptBuilderPolishing import PromptBuilderPolishing

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def make_config(target_language="chinese_simplified", unify_switch=True):
    """构造最小 TaskConfig 替身（SimpleNamespace），避免依赖完整配置。"""
    from types import SimpleNamespace
    config = SimpleNamespace(
        target_language=target_language,
        character_name_unify_switch=unify_switch,
        project_characters_data=[
            {"source": "空太", "recommended_translation": "空太", "gender": "男性", "note": "主角"},
            {"source": "远坂[Separator]凛", "recommended_translation": "远坂凛", "gender": "女性", "note": "女主角"},
            {"source": "Alice", "recommended_translation": "爱丽丝", "gender": "女性", "note": ""},
        ],
        project_terms_data=[],
        project_non_translate_data=[],
        project_character_variants={},
    )
    return config


# ========================================================================
# 1. 变体扫描
# ========================================================================
print("== 变体扫描 collect_variants ==")

full_text = (
    "空太先輩、空太くん、空太君はここにいる。\n"
    "空太さんも来た。\n"
    "远坂凛先輩が笑った。\n"
    "凛ちゃん、凛さんも一緒だ。\n"
    "Alice senpai, Alice-san, Alice-chan."
)

variants = CharacterNameHelper.collect_variants(full_text, "空太")
check("空太 扫出 空太先輩", "空太先輩" in variants, str(variants))
check("空太 扫出 空太くん", "空太くん" in variants, str(variants))
check("空太 扫出 空太君", "空太君" in variants, str(variants))
check("空太 扫出 空太さん", "空太さん" in variants, str(variants))
check("空太 不含本名自身", "空太" not in variants, str(variants))

variants_l = CharacterNameHelper.collect_variants(full_text, "远坂[Separator]凛")
check("远坂凛 扫出 远坂凛先輩", "远坂凛先輩" in variants_l, str(variants_l))
check("远坂凛 扫出 凛ちゃん", "凛ちゃん" in variants_l, str(variants_l))
check("远坂凛 扫出 凛さん", "凛さん" in variants_l, str(variants_l))

variants_a = CharacterNameHelper.collect_variants(full_text, "Alice")
check("Alice 扫出 Alice senpai", "Alice senpai" in variants_a, str(variants_a))
check("Alice 扫出 Alice-san", "Alice-san" in variants_a, str(variants_a))
check("Alice 扫出 Alice-chan", "Alice-chan" in variants_a, str(variants_a))

check("空文本返回空", CharacterNameHelper.collect_variants("", "空太") == [])
check("空本名返回空", CharacterNameHelper.collect_variants(full_text, "") == [])

# 大小写不敏感
variants_case = CharacterNameHelper.collect_variants("alice SENPAI です", "Alice")
check("大小写不敏感 (alice SENPAI)", "alice SENPAI" in variants_case, str(variants_case))

# 无命中
check("无变体时返回空", CharacterNameHelper.collect_variants("全く別の文章", "空太") == [])

# 批量扫描
anchors = [
    {"source": "空太", "recommended_translation": "空太"},
    {"source": "Alice", "recommended_translation": "爱丽丝"},
]
project_variants = CharacterNameHelper.collect_project_variants(full_text, anchors)
check("批量扫描含 空太", "空太" in project_variants, str(project_variants))
check("批量扫描含 Alice", "Alice" in project_variants, str(project_variants))
check("批量扫描不含未出现角色", "远坂[Separator]凛" not in project_variants, str(project_variants))
check("批量扫描变体非空", bool(project_variants.get("空太")), str(project_variants))

# 敬称被吞进名字的场景：source 为 露娜小姐 时，正文单独出现 露娜 不匹配
variants_n = CharacterNameHelper.collect_variants("露娜が来た", "露娜小姐")
check("含敬称 source 不误配纯本名", variants_n == [], str(variants_n))


# ========================================================================
# 2. 提示词构建：通用版
# ========================================================================
print("== 通用版 PromptBuilder 提示词 ==")

config = make_config()
config.project_character_variants = {
    "空太": ["空太先輩", "空太くん", "空太君"],
    "Alice": ["Alice senpai"],
}

source_dict = {
    "0": "空太先輩が来た。空太くんも。空太君も。",
    "1": "Alice senpai は元気。",
}

character_prompt = PromptBuilder.build_project_characters_prompt(config, source_dict)
check("通用版含角色表标题", "###角色表" in character_prompt)
check("通用版含路由指令", "推荐译名" in character_prompt and "全文保持一致" in character_prompt)
check("通用版含变体小节标题", "###角色称呼变体" in character_prompt)
check("通用版变体含本名行", "空太|空太|空太先輩、空太くん、空太君" in character_prompt, character_prompt)
check("通用版变体含 Alice 行", "Alice|爱丽丝|Alice senpai" in character_prompt, character_prompt)
check("通用版本名行仍在", "空太|空太|男性|主角" in character_prompt, character_prompt)

# 当前批次未出现的变体不注入
source_dict_no_variant = {"0": "空太だけの話"}
character_prompt_no = PromptBuilder.build_project_characters_prompt(config, source_dict_no_variant)
check("变体未出现在批次时不注入变体小节", "###角色称呼变体" not in character_prompt_no, character_prompt_no)

# 无角色表时为空
config_no_char = make_config()
config_no_char.project_characters_data = []
config_no_char.project_character_variants = {}
empty = PromptBuilder.build_project_characters_prompt(config_no_char, source_dict)
check("无角色表返回空", empty == "", repr(empty))

# 英文目标语言
config_en = make_config(target_language="english")
config_en.project_character_variants = {"Alice": ["Alice senpai"]}
character_prompt_en = PromptBuilder.build_project_characters_prompt(config_en, source_dict)
check("英文版含 Character Table", "###Character Table" in character_prompt_en)
check("英文版含 Character Name Variants", "###Character Name Variants" in character_prompt_en)
check("英文版含英文指令", "MUST use the Recommended Translation" in character_prompt_en)


# ========================================================================
# 3. 提示词构建：Local / Sakura / Polishing
# ========================================================================
print("== Local / Sakura / Polishing ==")

local_prompt = PromptBuilderLocal.build_project_characters_prompt(config, source_dict)
check("Local 版含变体小节", "###角色称呼变体" in local_prompt, local_prompt)
check("Local 版含路由指令", "推荐译名" in local_prompt)

sakura_prompt = PromptBuilderSakura.build_project_characters_prompt(config, source_dict)
check("Sakura 版含变体说明", "角色称呼变体" in sakura_prompt, sakura_prompt)
check("Sakura 版含变体对应", "空太->空太 #称呼: 空太先輩、空太くん、空太君" in sakura_prompt, sakura_prompt)

polishing_prompt = PromptBuilderPolishing.build_project_characters_prompt(config, source_dict)
check("Polishing 委托通用版含变体小节", "###角色称呼变体" in polishing_prompt, polishing_prompt)


# ========================================================================
# 3.5 统一称呼翻译开关（默认关闭）
# ========================================================================
print("== 统一称呼翻译开关 ==")

config_off = make_config(unify_switch=False)
config_off.project_character_variants = {
    "空太": ["空太先輩", "空太くん", "空太君"],
}
prompt_off = PromptBuilder.build_project_characters_prompt(config_off, source_dict)
check("关闭时仍注入角色表", "###角色表" in prompt_off, prompt_off)
check("关闭时不注入路由指令", "推荐译名」列，不得意译" not in prompt_off, prompt_off)
check("关闭时不注入变体小节", "###角色称呼变体" not in prompt_off, prompt_off)
check("关闭时不注入一致性指令", "前辈" not in prompt_off and "学姐" not in prompt_off, prompt_off)

prompt_local_off = PromptBuilderLocal.build_project_characters_prompt(config_off, source_dict)
check("Local 关闭时不注入变体小节", "###角色称呼变体" not in prompt_local_off, prompt_local_off)

prompt_sakura_off = PromptBuilderSakura.build_project_characters_prompt(config_off, source_dict)
check("Sakura 关闭时不注入变体说明", "角色称呼变体" not in prompt_sakura_off, prompt_sakura_off)

config_no_switch = make_config()
del config_no_switch.character_name_unify_switch
config_no_switch.project_character_variants = {"空太": ["空太先輩"]}
prompt_no_switch = PromptBuilder.build_project_characters_prompt(config_no_switch, source_dict)
check("无开关字段时按关闭处理", "###角色称呼变体" not in prompt_no_switch, prompt_no_switch)


# ========================================================================
# 4. CharacterHelper 兼容性
# ========================================================================
print("== CharacterHelper 兼容 ==")

check("split_name 处理 [Separator]", CharacterHelper.split_name("远坂[Separator]凛") == ["远坂", "凛"])
check("validate_name 允许普通名字", CharacterHelper.validate_name("空太") is True)
check("match_original_name 子串匹配", CharacterHelper.match_original_name("空太", "空太先輩が来た") == "空太")


print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
