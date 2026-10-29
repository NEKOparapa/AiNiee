"""Fixed-LLM acceptance: legacy parity and a real stop/resume round trip."""

import threading
from pathlib import Path

from ModuleFolders.Application.Bootstrap import bootstrap
from ModuleFolders.Application.ExportService import ExportService
from ModuleFolders.Application.TaskService import TaskService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from test_headless_translation import MOCK_RESPONSE, SOURCE_TEXT, _translation_config


def file_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def finish_runtime(runtime, initial_threads):
    from tqdm import tqdm

    runtime.close()
    if tqdm.monitor is not None and tqdm.monitor not in initial_threads:
        tqdm.monitor.exit()
    for worker in set(threading.enumerate()) - initial_threads:
        worker.join(10)
        assert not worker.is_alive(), f"Leaked worker: {worker.name}"
    Base.work_status = Base.STATUS.IDLE


def test_application_export_matches_legacy_event_pipeline_byte_for_byte(tmp_path, monkeypatch):
    source = tmp_path / "input"
    source.mkdir()
    (source / "sample.txt").write_text(SOURCE_TEXT, encoding="utf-8")
    monkeypatch.setattr(CacheManager, "SAVE_INTERVAL", 0.03)
    requests = []

    def fixed_response(self, messages, system_prompt, platform_config):
        requests.append((messages, system_prompt, platform_config["model_name"]))
        return False, "", MOCK_RESPONSE, 32, 16

    monkeypatch.setattr(LLMRequester, "sent_request", fixed_response)
    legacy_output, web_output = tmp_path / "legacy", tmp_path / "web"
    ConfigMixin().save_config(_translation_config(source, legacy_output))
    legacy = bootstrap()
    initial_threads = set(threading.enumerate())
    complete = threading.Event()

    def completed(event, data):
        complete.set()

    manager = legacy.task_executor.event_manager_singleton
    manager.subscribe(Base.EVENT.TASK_COMPLETED, completed)
    try:
        legacy.cache_manager.load_from_project(legacy.file_reader.read_files(ProjectType.TXT, str(source), ""))
        # This is exactly the old Qt command bar's event-driven invocation.
        manager.emit(Base.EVENT.TASK_START, {"continue_status": False, "current_mode": TaskType.TRANSLATION})
        assert complete.wait(30)
        manager.emit(Base.EVENT.TASK_MANUAL_EXPORT, {"export_path": str(legacy_output)})
        legacy_files = file_bytes(legacy_output)
        assert len(legacy_files) == 2
    finally:
        manager.unsubscribe(Base.EVENT.TASK_COMPLETED, completed)
        finish_runtime(legacy, initial_threads)

    ConfigMixin().save_config(_translation_config(source, web_output))
    web = bootstrap()
    initial_threads = set(threading.enumerate())
    service = TaskService(web.cache_manager, web.task_executor)
    try:
        web.cache_manager.load_from_project(web.file_reader.read_files(ProjectType.TXT, str(source), ""))
        service.translate()
        assert service.wait(30)
        assert service.get_current()["status"] == "completed", service.get_current()
        exported = ExportService(web.cache_manager, web.file_writer, web.task_executor).export(str(web_output))
        assert exported["output_path"] == str(web_output)
        assert file_bytes(web_output) == legacy_files
        # The new orchestration also supplies identical prompts to the fixed LLM.
        assert len(requests) == 2
        assert requests[0] == requests[1]
    finally:
        service.close()
        finish_runtime(web, initial_threads)


def test_real_translation_can_stop_save_reload_and_continue(tmp_path, monkeypatch):
    source = tmp_path / "input"
    source.mkdir()
    (source / "sample.txt").write_text("First line.\nSecond line.\nThird line.\n", encoding="utf-8")
    output = tmp_path / "output"
    config = _translation_config(source, output)
    config["lines_limit"] = 1
    ConfigMixin().save_config(config)
    monkeypatch.setattr(CacheManager, "SAVE_INTERVAL", 0.03)
    second_request, release = threading.Event(), threading.Event()
    requested = []
    answers = {"First line.": "第一行。", "Second line.": "第二行。", "Third line.": "第三行。"}

    def fixed_response(self, messages, system_prompt, platform_config):
        text = str(messages[-1]["content"])
        original = next(original for original in answers if original in text)
        requested.append(original)
        if len(requested) == 2:
            second_request.set()
            assert release.wait(10)
        return False, "", f"<textarea>\n1.{answers[original]}\n</textarea>", 10, 5

    monkeypatch.setattr(LLMRequester, "sent_request", fixed_response)
    runtime = bootstrap()
    initial_threads = set(threading.enumerate())
    service = TaskService(runtime.cache_manager, runtime.task_executor)
    try:
        runtime.cache_manager.load_from_project(runtime.file_reader.read_files(ProjectType.TXT, str(source), ""))
        service.translate()
        assert second_request.wait(20)
        assert service.stop()["status"] == "stopping"
        release.set()
        assert service.wait(20)
        assert service.get_current()["status"] == "stopped"
        assert service.get_current()["can_continue"]
        project_id = runtime.cache_manager.project.project_id
        # Re-open the on-disk legacy cache rather than relying on memory.
        runtime.cache_manager.load_from_project_id(project_id)
        assert runtime.cache_manager.get_item_count_by_status(TranslationStatus.TRANSLATED) == 2
        service.translate(True)
        assert service.wait(20)
        assert service.get_current()["status"] == "completed", service.get_current()
        assert requested == list(answers)
        assert runtime.cache_manager.get_item_count_by_status(TranslationStatus.TRANSLATED) == 3
        assert service.get_current()["progress"]["line"] == 3
        assert (output / "sample_translated.txt").read_text(encoding="utf-8") == "第一行。\n第二行。\n第三行。\n"
    finally:
        release.set()
        service.close(20)
        finish_runtime(runtime, initial_threads)


def test_real_polishing_and_analysis_use_defaults_without_visiting_prompt_pages(tmp_path, monkeypatch):
    source = tmp_path / "input"
    source.mkdir()
    (source / "sample.txt").write_text(SOURCE_TEXT, encoding="utf-8")
    config = _translation_config(source, tmp_path / "output")
    # A newly configured application has never saved these Qt-page defaults.
    config.pop("translation_example_switch")
    config.pop("translation_prompt_selection")
    config.pop("few_shot_and_example_switch")
    ConfigMixin().save_config(config)
    monkeypatch.setattr(CacheManager, "SAVE_INTERVAL", 0.03)
    responses = iter([
        (False, "", MOCK_RESPONSE, 32, 16),
        (False, "", '<textarea>\n1.世界，你好！\n2.这是一个无界面翻译测试。\n</textarea>', 32, 16),
        (False, "", '{"characters": [], "terms": [], "non_translate": []}', 32, 16),
    ])
    calls = []

    def fixed_response(self, messages, system_prompt, platform_config):
        calls.append(messages)
        return next(responses)

    monkeypatch.setattr(LLMRequester, "sent_request", fixed_response)
    runtime = bootstrap()
    initial_threads = set(threading.enumerate())
    service = TaskService(runtime.cache_manager, runtime.task_executor)
    try:
        runtime.cache_manager.load_from_project(runtime.file_reader.read_files(ProjectType.TXT, str(source), ""))
        service.translate()
        assert service.wait(30)
        assert service.get_current()["status"] == "completed", service.get_current()
        service.polish()
        assert service.wait(30)
        assert service.get_current()["status"] == "completed", service.get_current()
        assert runtime.cache_manager.get_item_count_by_status(TranslationStatus.POLISHED) == 2
        polished_file = tmp_path / "output" / "polish" / "sample_translated.txt"
        assert polished_file.read_text(encoding="utf-8") == "世界，你好！\n这是一个无界面翻译测试。\n"
        service.analysis()
        assert service.wait(30)
        assert service.get_current()["status"] == "completed", service.get_current()
        assert service.get_current()["analysis_progress"]["percent"] == 100
        assert runtime.cache_manager.get_analysis_data()["status"] == "success"
        assert len(calls) == 3
    finally:
        service.close(20)
        finish_runtime(runtime, initial_threads)
