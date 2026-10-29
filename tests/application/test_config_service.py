import json
from concurrent.futures import ThreadPoolExecutor

from ModuleFolders.Application.ConfigService import ConfigService
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
