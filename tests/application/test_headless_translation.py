"""Exercise the existing translation pipeline without a GUI or an LLM server."""

import json
import threading
from pathlib import Path


SOURCE_TEXT = "Hello, world!\nThis is a headless translation test.\n"
TRANSLATIONS = ["你好，世界！", "这是一次无界面翻译测试。"]
MOCK_RESPONSE = "<textarea>\n1.你好，世界！\n2.这是一次无界面翻译测试。\n</textarea>"


def _translation_config(input_dir: Path, output_dir: Path) -> dict:
    """A self-contained legacy config, independent of a user's saved settings."""
    return {
        "translation_project": "Txt",
        "label_input_path": str(input_dir),
        "label_output_path": str(output_dir),
        "label_polish_output_path": str(output_dir / "polish"),
        "auto_set_output_path": False,
        "output_filename_suffix": "_translated",
        "bilingual_text_order": "translation_first",
        "keep_original_encoding": False,
        "response_conversion_toggle": False,
        "translation_result_check_switch": False,
        "source_language": "english",
        "target_language": "chinese_simplified",
        "language_filter_switch": False,
        "code_filter_switch": False,
        "lines_limit_switch": True,
        "tokens_limit_switch": False,
        "lines_limit": 10,
        "tokens_limit": 1024,
        "user_thread_counts": 1,
        "request_timeout": 5,
        "round_limit": 1,
        "pre_line_counts": 0,
        "few_shot_and_example_switch": False,
        "translation_example_switch": False,
        "auto_process_text_code_segment": False,
        "text_symbol_repair_switch": False,
        "response_check_switch": {
            "return_to_original_text_check": True,
            "residual_original_text_check": True,
            "newline_character_count_check": True,
            "reply_format_check": False,
        },
        "translation_prompt_selection": {"last_selected_id": 100},
        "platforms": {
            "custom_platform_mock": {
                "tag": "custom_platform_mock",
                "name": "Fixed test LLM",
                "api_url": "https://llm.invalid/v1",
                "api_format": "OpenAI",
                "api_key": "test-only-not-a-real-key",
                "model": "fixed-mock-model",
                "rpm_limit": 4096,
            }
        },
        "api_settings": {"active": "custom_platform_mock"},
    }


def test_translation_uses_real_reader_pipeline_writer_and_cache(isolated_app_paths, monkeypatch):
    # The shared fixture redirects writable paths before application imports.
    data_dir = isolated_app_paths / "data"
    input_dir = isolated_app_paths / "input"
    output_dir = isolated_app_paths / "output"
    data_dir.mkdir()
    input_dir.mkdir()
    (data_dir / "config.json").write_text(
        json.dumps(_translation_config(input_dir, output_dir), ensure_ascii=False),
        encoding="utf-8",
    )
    (input_dir / "sample.txt").write_text(SOURCE_TEXT, encoding="utf-8")

    from ModuleFolders.Application.Bootstrap import bootstrap
    from ModuleFolders.Base.Base import Base
    from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
    from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
    from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
    from ModuleFolders.Service.Cache.CacheManager import CacheManager
    from ModuleFolders.Service.Cache.CacheProject import ProjectType
    from tqdm import tqdm

    requests = []

    def fixed_llm_response(self, messages, system_prompt, platform_config):
        requests.append((messages, system_prompt, platform_config))
        return False, "", MOCK_RESPONSE, 32, 16

    # The sole replaced processing boundary is the external LLM call.
    monkeypatch.setattr(LLMRequester, "sent_request", fixed_llm_response)
    # Use the real autosave worker, with a shorter scheduling interval.
    monkeypatch.setattr(CacheManager, "SAVE_INTERVAL", 0.05)
    completed = threading.Event()
    updates = []
    runtime = bootstrap()
    initial_threads = set(threading.enumerate())
    manager = runtime.task_executor.event_manager_singleton

    def on_completed(event, data):
        completed.set()

    def on_updated(event, data):
        updates.append(dict(data))

    manager.subscribe(Base.EVENT.TASK_COMPLETED, on_completed)
    manager.subscribe(Base.EVENT.TASK_UPDATE, on_updated)
    try:
        project = runtime.file_reader.read_files(ProjectType.TXT, str(input_dir), "")
        runtime.cache_manager.load_from_project(project)
        assert runtime.cache_manager.get_item_count() == 2

        manager.emit(
            Base.EVENT.TASK_START,
            {"continue_status": False, "current_mode": TaskType.TRANSLATION},
        )
        assert completed.wait(30), "The real translation task did not complete"

        assert len(requests) == 1
        messages, system_prompt, platform_config = requests[0]
        assert system_prompt
        assert "Hello, world!" in messages[-1]["content"]
        assert "This is a headless translation test." in messages[-1]["content"]
        assert platform_config["model_name"] == "fixed-mock-model"
        assert updates[-1]["line"] == 2
        assert updates[-1]["token"] == 48

        items = list(runtime.cache_manager.project.items_iter())
        assert [item.translated_text for item in items] == TRANSLATIONS
        assert all(item.translation_status == TranslationStatus.TRANSLATED for item in items)
        assert (output_dir / "sample_translated.txt").read_text(encoding="utf-8") == (
            "\n".join(TRANSLATIONS) + "\n"
        )
        assert (
            output_dir / "bilingual_txt" / "sample_bilingual.txt"
        ).read_text(encoding="utf-8") == (
            "你好，世界！\nHello, world!\n"
            "这是一次无界面翻译测试。\nThis is a headless translation test.\n"
        )

        # The old cache format remains writable and reloads translation progress.
        manager.emit(Base.EVENT.TASK_MANUAL_SAVE_CACHE, {})
        runtime.cache_manager.load_from_project_id(project.project_id)
        assert runtime.cache_manager.get_item_count_by_status(TranslationStatus.TRANSLATED) == 2
        assert [item.translated_text for item in runtime.cache_manager.project.items_iter()] == TRANSLATIONS
        assert runtime.cache_manager.project.stats_data.line == 2
    finally:
        runtime.close()
        manager.unsubscribe(Base.EVENT.TASK_COMPLETED, on_completed)
        manager.unsubscribe(Base.EVENT.TASK_UPDATE, on_updated)
        # tqdm owns a separate process-wide monitoring thread; stop it if this
        # test created it, before checking that application workers have exited.
        if tqdm.monitor is not None and tqdm.monitor not in initial_threads:
            tqdm.monitor.exit()
        # Do not let a delayed autosave survive restoration of the isolated paths.
        for thread in set(threading.enumerate()) - initial_threads:
            thread.join(timeout=10)
            assert not thread.is_alive(), f"Translation worker leaked: {thread.name}"
