from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.ExportService import ExportService
from ModuleFolders.Config.Config import ConfigMixin


def make_service(tmp_path):
    cache = SimpleNamespace(project=SimpleNamespace(input_path=str(tmp_path / "input")), save_to_file=Mock())
    writer = SimpleNamespace(output_translated_content=Mock())
    executor = SimpleNamespace(
        _resolve_output_source_language=lambda language: "en",
        _resolve_output_target_language=lambda language: "zh-Hans",
        _convert_translated_text_with_opencc=Mock(return_value=True),
    )
    return ExportService(cache, writer, executor)


def test_export_preserves_legacy_writer_options_and_lists_written_files(tmp_path):
    service = make_service(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")
    ConfigMixin().save_config({
        "label_input_path": str(tmp_path / "input"), "output_filename_suffix": "_out",
        "bilingual_text_order": "source_first", "source_language": "english", "target_language": "chinese_simplified",
    })

    def write(project, directory, source, config):
        assert source == str(tmp_path / "input")
        assert config == {
            "translated_suffix": "_out", "bilingual_suffix": "_bilingual", "bilingual_order": "source_first",
            "source_lang_code": "en", "target_lang_code": "zh-Hans",
        }
        (Path(directory) / "sample_out.txt").write_text("译文", encoding="utf-8")

    service.file_writer.output_translated_content.side_effect = write
    assert service.export(str(output)) == {"output_path": str(output), "files": ["sample_out.txt"]}
    service.cache_manager.save_to_file.assert_called_once()


def test_export_defaults_to_legacy_automatic_output_directory(tmp_path):
    service = make_service(tmp_path)
    result = service.export()
    assert result["output_path"] == str(tmp_path / "AiNieeOutput")


@pytest.mark.parametrize("path", ["", "  ", "bad\x00path"])
def test_export_rejects_invalid_path(tmp_path, path):
    service = make_service(tmp_path)
    with pytest.raises(ApplicationError, match="export_path_invalid"):
        service.export(path)
    service.file_writer.output_translated_content.assert_not_called()


def test_export_reports_writer_and_conversion_failures_without_provider_details(tmp_path):
    service = make_service(tmp_path)
    service.file_writer.output_translated_content.side_effect = RuntimeError("private failure")
    with pytest.raises(ApplicationError, match="^export_failed$"):
        service.export()
    ConfigMixin().save_config({"response_conversion_toggle": True})
    service.task_executor._convert_translated_text_with_opencc.return_value = False
    with pytest.raises(ApplicationError, match="^export_conversion_failed$"):
        service.export()


def test_cache_save_reports_missing_project_and_write_failure(tmp_path):
    service = make_service(tmp_path)
    assert service.save_cache() == {"saved": True}
    service.cache_manager.save_to_file.side_effect = OSError("disk full")
    with pytest.raises(ApplicationError, match="cache_save_failed"):
        service.save_cache()
    service.cache_manager.project = None
    with pytest.raises(ApplicationError, match="project_not_open"):
        service.save_cache()
    with pytest.raises(ApplicationError, match="project_not_open"):
        service.export()
