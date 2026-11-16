from asyncio import CancelledError
from collections import defaultdict, deque
from functools import cached_property
import gc
from importlib.metadata import version
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_item import CacheItem
from Backend.infrastructure.compat.babeldoc import ensure_pdf_runtime, ensure_skimage
from Backend.infrastructure.files.pipeline_support import file_sha256, source_sequence_digest
from Backend.infrastructure.files.writers.base_writer import OutputConfig

ensure_pdf_runtime()
ensure_skimage()

from babeldoc.babeldoc_exception.BabelDOCException import ExtractTextError
from babeldoc.docvision.base_doclayout import DocLayoutModel
from babeldoc.format.pdf.high_level import do_translate, get_translation_stage
from babeldoc.format.pdf.translation_config import TranslateResult, TranslationConfig
from babeldoc.progress_monitor import ProgressMonitor
from babeldoc.translator.translator import BaseTranslator


_PARSER_SETTINGS = {
    "split_short_lines": False,
    "short_line_split_factor": 0.8,
    "disable_rich_text_translate": False,
    "min_text_length": 5,
    "formular_font_pattern": None,
    "formular_char_pattern": None,
}


class _ReadComplete(CancelledError):
    """Stop the native pipeline once its ordered paragraph record is on disk."""


def _stop_before_typesetting(**event):
    if event["type"] == "progress_start" and event["stage"] == "Typesetting":
        raise _ReadComplete()


class _CacheTranslator(BaseTranslator):
    def __init__(self, items: list[CacheItem] | None):
        super().__init__("en", "zh", True)
        self.reading = items is None
        self.translations = defaultdict(deque)
        for item in items or ():
            self.translations[item.source_text].append(item.final_text)

    def translate(self, text, **kwargs):
        # The single Rust worker admits equal-priority requests FIFO. Distinct
        # source texts can arrive out of order because priority uses token count.
        if self.reading:
            return text
        return self.translations[text].popleft()

    def do_translate(self, text, rate_limit_params=None):
        return self.translate(text)

    def do_llm_translate(self, text, rate_limit_params=None):
        raise NotImplementedError


class BabeldocPdfAccessor:
    def __init__(self, tmp_directory: Path, output_config: OutputConfig | None, parse_options=None):
        self.tmp_directory = tmp_directory
        self.output_config = output_config
        self.parse_options = dict(parse_options or {})
        self._result_cache: dict[tuple[str, str], TranslateResult] = {}

    @cached_property
    def _layout_model(self):
        return DocLayoutModel.load_onnx()

    def parse_metadata(self, texts):
        return {
            "babeldoc_version": version("babeldoc"),
            "parse_options": {"pages": self.parse_options.get("pages")},
            "parser_settings": {**_PARSER_SETTINGS, "translate_table_text": False},
            "source_sequence_sha256": source_sequence_digest(texts),
        }

    def _run(self, source: Path, items: list[CacheItem] | None):
        output = self.output_config
        reading = items is None
        with TemporaryDirectory(dir=self.tmp_directory) as work:
            config = TranslationConfig(
                translator=_CacheTranslator(items),
                input_file=source,
                lang_in="en",
                lang_out=(output.language_config.target_lang_code if output else None) or "zh",
                pages=self.parse_options.get("pages"),
                doc_layout_model=self._layout_model,
                working_dir=work,
                output_dir=self.tmp_directory,
                no_dual=reading or bool(output and not output.bilingual_config.enabled),
                no_mono=reading or bool(output and not output.translated_config.enabled),
                pool_max_workers=1,
                skip_scanned_detection=True,
                auto_extract_glossary=False,
                save_auto_extracted_glossary=False,
                **_PARSER_SETTINGS,
            )
            callback = _stop_before_typesetting if reading else None
            result = None
            try:
                with ProgressMonitor(get_translation_stage(config), progress_change_callback=callback) as monitor:
                    result = do_translate(monitor, config)
            except _ReadComplete:
                pass
            except ExtractTextError as exc:
                raise PipelineError("SCANNED_PDF_NOT_SUPPORTED", "PDF 不包含可复制文本，本轮不支持扫描件") from exc
            finally:
                # BabelDOC leaves PyMuPDF reference cycles after metadata/TOC
                # processing. Release their file handles before cleaning up on Windows.
                gc.collect()

            # The native stage writes this in page/paragraph order, independent
            # of the order in which it called the translator.
            tracking = json.loads(config.get_working_file_path("translate_tracking.json").read_bytes())
            paragraphs = [
                paragraph for page in tracking["page"] for paragraph in page["paragraph"]
                if paragraph["llm_translate_trackers"]
            ]
            return result, paragraphs

    def read_content(self, source_file_path: Path):
        _, paragraphs = self._run(source_file_path, None)
        if not paragraphs:
            raise PipelineError("NO_TRANSLATABLE_TEXT", "PDF 没有可翻译的文本")
        return [paragraph["input"] for paragraph in paragraphs]

    def write_content(self, source_file_path: Path, items: list[CacheItem], metadata=None):
        current = self.parse_metadata(item.source_text for item in items)
        if any((metadata or {}).get(key) != value for key, value in current.items()):
            raise PipelineError("PDF_MAPPING_MISMATCH", "PDF 解析版本、参数或原文已变化，请重新读取 PDF")
        cache_id = (file_sha256(source_file_path), source_sequence_digest(
            value for item in items for value in (item.source_text, item.final_text)))
        if cache_id in self._result_cache:
            return self._result_cache[cache_id]

        self._result_cache.clear()  # BabelDOC reuses output names on the next run.
        result, paragraphs = self._run(source_file_path, items)
        # BabelDOC collapses long punctuation runs before recording its output.
        if len(paragraphs) != len(items) or any(
            paragraph["input"] != item.source_text or paragraph["output"] != re.sub(r"[. 。…，]{20,}", ".", item.final_text)
            for paragraph, item in zip(paragraphs, items)
        ):
            raise PipelineError("PDF_MAPPING_MISMATCH", "PDF 段落与缓存译文不匹配，请重新读取 PDF")
        self._result_cache = {cache_id: result}
        return result
