from ainiee_mcp import enums


def test_languages():
    assert "japanese" in enums.LANGUAGES
    assert "chinese_simplified" in enums.LANGUAGES
    assert len(enums.LANGUAGES) == 12


def test_project_types():
    for t in ("AutoType", "Mtool", "Epub", "Renpy", "Paratranz", "Xlsx"):
        assert t in enums.PROJECT_TYPES


def test_modes_roles_scopes():
    assert enums.TASK_MODES == frozenset({"translate", "polish"})
    assert {"active", "translate", "polish", "extract", "proofread"} <= enums.API_ROLES
    assert enums.SEARCH_SCOPES == frozenset({"all", "source_text", "translated_text"})


def test_status_codes():
    assert enums.STATUS_TRANSLATED == 1
    assert enums.STATUS_NAMES[2] == "polished"
