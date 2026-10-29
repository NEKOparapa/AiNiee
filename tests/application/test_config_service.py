import json
from concurrent.futures import ThreadPoolExecutor

from ModuleFolders.Application.ConfigService import ConfigService
from ModuleFolders.Application.SettingsDefaults import fill_setting_defaults, setting_defaults
from ModuleFolders.Config.FilePathConfig import config_path, project_cache_root


def write_config(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_patch_keeps_unrelated_legacy_data_and_persists_after_recreation():
    write_config({
        "accent_color": "#808b9d",
        "custom_extension": {"keep": ["existing", 42]},
        "platforms": {"custom": {"api_key": "fixed-test-key", "model": "old-model"}},
        "prompt_dictionary_data": [{"src": "Alice", "dst": "爱丽丝"}],
    })
    service = ConfigService()
    before = service.get_config()
    cache_file = project_cache_root() / "existing-project.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b'{"translated_text":"preserve existing progress"}')
    cache_bytes = cache_file.read_bytes()

    result = service.patch_config({"accent_color": "#112233", "user_thread_counts": 2})

    assert result["accent_color"] == "#112233"
    assert result["custom_extension"] == before["custom_extension"]
    assert result["platforms"] == before["platforms"]
    assert result["prompt_dictionary_tables"] == before["prompt_dictionary_tables"]
    assert ConfigService().get_config() == result
    assert cache_file.read_bytes() == cache_bytes


def test_patch_replaces_only_provided_top_level_values():
    write_config({"custom": {"first": 1, "second": 2}, "untouched": True})
    result = ConfigService().patch_config({"custom": {"first": 3}})
    assert result["custom"] == {"first": 3}
    assert result["untouched"] is True


def test_concurrent_patches_do_not_lose_other_keys():
    write_config({"existing": "keep"})
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(ConfigService().patch_config, {f"setting_{index}": index})
            for index in range(20)
        ]
        for future in futures:
            future.result(timeout=5)
    config = ConfigService().get_config()
    assert config["existing"] == "keep"
    assert {key: value for key, value in config.items() if key.startswith("setting_")} == {
        f"setting_{index}": index for index in range(20)
    }


def test_missing_config_get_returns_old_page_defaults_without_creating_file():
    config = ConfigService().get_config()
    assert config["lines_limit"] == 10
    assert config["tokens_limit"] == 1024
    assert config["extract_task_token_limit"] == 10000
    assert config["polishing_pre_line_counts"] == 10
    assert config["response_check_switch"]["reply_format_check"] is False
    assert config["theme"] == "auto"
    assert config["accent_color"] == "#808b9d"
    assert not config_path().exists()


def test_fill_defaults_preserves_legacy_values_and_unknown_nested_rules():
    original = {
        "lines_limit": 42,
        "interface_language_setting": "日本語",
        "response_check_switch": {"reply_format_check": True, "extension_check": True},
    }
    config = fill_setting_defaults(original)
    assert config["lines_limit"] == 42
    assert config["interface_language_setting"] == "日本語"
    assert config["response_check_switch"] == {
        "return_to_original_text_check": True,
        "residual_original_text_check": True,
        "newline_character_count_check": True,
        "reply_format_check": True,
        "extension_check": True,
    }
    config["response_check_switch"]["extension_check"] = False
    assert original["response_check_switch"]["extension_check"] is True
    assert setting_defaults()["response_check_switch"]["reply_format_check"] is False
