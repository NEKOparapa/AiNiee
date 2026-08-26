import json

import pytest

from ainiee_mcp.config_store import ConfigStore
from ainiee_mcp.errors import ValidationError


def _store(tmp_path, seed=None):
    p = tmp_path / "config.json"
    if seed is not None:
        p.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
    return ConfigStore(config_path=p), p


def test_load_missing_returns_empty(tmp_path):
    store, _ = _store(tmp_path)
    assert store.load() == {}


def test_merge_save_overwrites_top_level_and_is_atomic(tmp_path):
    store, p = _store(tmp_path, {"a": 1, "b": {"x": 1}})
    store.merge_save({"b": {"y": 2}, "c": 3})
    cfg = json.loads(p.read_text(encoding="utf-8"))
    assert cfg == {"a": 1, "b": {"y": 2}, "c": 3}  # top-level overwrite, not deep merge
    # no stray temp files left behind
    assert [f.name for f in tmp_path.iterdir()] == ["config.json"]


def test_set_api_role_validates(tmp_path):
    store, _ = _store(tmp_path, {"platforms": {"openai_1": {"name": "OpenAI"}}, "api_settings": {}})
    out = store.set_api_role("translate", "openai_1")
    assert out["translate"] == "openai_1"
    with pytest.raises(ValidationError):
        store.set_api_role("translate", "missing_tag")
    with pytest.raises(ValidationError):
        store.set_api_role("not_a_role", "openai_1")


def test_set_languages_validates(tmp_path):
    store, p = _store(tmp_path, {})
    store.set_languages(source="english", target="chinese_simplified")
    cfg = json.loads(p.read_text(encoding="utf-8"))
    assert cfg["source_language"] == "english" and cfg["target_language"] == "chinese_simplified"
    with pytest.raises(ValidationError):
        store.set_languages(source="martian")


def test_set_project_type_validates(tmp_path):
    store, _ = _store(tmp_path, {})
    store.set_project_type("Mtool")
    with pytest.raises(ValidationError):
        store.set_project_type("Nope")


def test_upsert_platform_merges(tmp_path):
    store, _ = _store(tmp_path, {"platforms": {"p1": {"name": "A", "model": "m1"}}})
    out = store.upsert_platform("p1", {"model": "m2", "api_key": None})
    assert out["model"] == "m2" and out["name"] == "A"  # None dropped, existing kept


def test_set_resource_list_with_switch(tmp_path):
    store, p = _store(tmp_path, {})
    store.set_resource_list("prompt_dictionary_data", [{"src": "a", "dst": "b"}],
                            switch_key="prompt_dictionary_switch", switch=True)
    cfg = json.loads(p.read_text(encoding="utf-8"))
    assert cfg["prompt_dictionary_data"][0]["dst"] == "b" and cfg["prompt_dictionary_switch"] is True


def test_set_io_paths_validates_input(tmp_path):
    store, _ = _store(tmp_path, {})
    out = store.set_io_paths(input_path=str(tmp_path), output_path="~/out")
    assert out["label_input_path"] == str(tmp_path)
    assert out["label_output_path"].endswith("/out")
    with pytest.raises(ValidationError):
        store.set_io_paths(input_path=str(tmp_path / "nope"))


def test_list_platforms_redacted_hides_key(tmp_path):
    store, _ = _store(tmp_path, {"platforms": {"p1": {"name": "A", "api_key": "secret", "model": "m"}}})
    red = store.list_platforms_redacted()
    assert red["p1"]["has_key"] is True and "api_key" not in red["p1"]
