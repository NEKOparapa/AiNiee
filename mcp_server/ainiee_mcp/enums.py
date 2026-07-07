"""Validated value sets, copied from AiNiee (kept in sync, NOT imported, to stay PyQt-free).

Sources of truth (update here if AiNiee changes these):
- LANGUAGES:    ModuleFolders/Service/TaskExecutor/TranslatorUtil.py
- PROJECT_TYPES: ModuleFolders/Service/Cache/CacheProject.py  (class ProjectType)
- API_ROLES:    ModuleFolders/Infrastructure/TaskConfig/TaskConfig.py
- STATUS_*:     ModuleFolders/Service/Cache/CacheItem.py  (class TranslationStatus)
"""
from __future__ import annotations

# config keys source_language / target_language accept these values
LANGUAGES: frozenset[str] = frozenset({
    "japanese", "english", "korean", "russian",
    "chinese_simplified", "chinese_traditional",
    "french", "german", "spanish", "indonesian", "vietnamese", "thai",
})

# config key translation_project accepts these (ProjectType members)
PROJECT_TYPES: frozenset[str] = frozenset({
    "AutoType", "Docx", "Epub", "Lrc", "Md", "Mtool",
    "OfficeConversionPdf", "OfficeConversionDoc", "Paratranz", "Renpy",
    "Srt", "Ass", "Tpp", "Trans", "Txt", "Vnt", "Vtt", "I18next", "Po",
    "BabeldocPdf", "Csv", "Pptx", "Xlsx", "WolfXlsx",
})

# task/start mode
TASK_MODES: frozenset[str] = frozenset({"translate", "polish"})

# api_settings role keys
API_ROLES: frozenset[str] = frozenset({"active", "translate", "polish", "extract", "proofread"})

# cache search scope
SEARCH_SCOPES: frozenset[str] = frozenset({"all", "source_text", "translated_text"})

# CacheItem.translation_status integer codes
STATUS_UNTRANSLATED = 0
STATUS_TRANSLATED = 1
STATUS_POLISHED = 2
STATUS_EXCLUDED = 7
STATUS_NAMES: dict[int, str] = {
    STATUS_UNTRANSLATED: "untranslated",
    STATUS_TRANSLATED: "translated",
    STATUS_POLISHED: "polished",
    STATUS_EXCLUDED: "excluded",
}
