import logging
from importlib.metadata import version
from contextlib import contextmanager
from concurrent.futures import Executor, Future
from concurrent.futures.thread import _WorkItem
from pathlib import Path

from Backend.infrastructure.compat.babeldoc import ensure_optional_imports, ensure_pdf_runtime

ensure_optional_imports()

from babeldoc import progress_monitor
from babeldoc.babeldoc_exception.BabelDOCException import ExtractTextError
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
from babeldoc.format.pdf.document_il.midend import il_translator
from babeldoc.format.pdf.high_level import TRANSLATE_STAGES, do_translate
from babeldoc.format.pdf import high_level as pdf_high_level
from babeldoc.format.pdf.translation_config import (
    TranslateResult,
    TranslationConfig,
    WatermarkOutputMode
)
from babeldoc.main import create_parser
from babeldoc.progress_monitor import ProgressMonitor
from babeldoc.translator.translator import BaseTranslator
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn
)

from Backend.domain.models.cache_item import CacheItem
from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.files.pipeline_support import file_sha256, source_sequence_digest
from Backend.infrastructure.files.writers.base_writer import OutputConfig


@contextmanager
def _managed_documents():
    """Close BabelDOC's metadata/working documents, including early-read exits.

    The service already serializes PDF operations because BabelDOC adapters patch
    its global executor/stage classes. Keep this additional patch equally scoped.
    """
    original = pdf_high_level.Document
    documents = []
    def open_document(*args, **kwargs):
        document = original(*args, **kwargs)
        documents.append(document)
        return document
    pdf_high_level.Document = open_document
    try:
        yield
    finally:
        pdf_high_level.Document = original
        for document in reversed(documents):
            if not document.is_closed:
                document.close()


class FinishReading(Exception):
    @classmethod
    def raise_after_call(cls, func):
        def warpper(*args, **kwargs):
            func(*args, **kwargs)
            raise FinishReading
        return warpper


class IgnoreStyleNoneFilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().startswith("Style is None")


class IgnoreFinishReadingException(logging.Filter):
    def filter(self, record):
        if record.exc_info:
            exc_type = record.exc_info[0]
            return exc_type and issubclass(exc_type, FinishReading)
        return False


# 屏蔽告警
logging.getLogger("babeldoc.format.pdf.document_il.midend.typesetting").addFilter(IgnoreStyleNoneFilter())
logging.getLogger("babeldoc.format.pdf.high_level").addFilter(IgnoreFinishReadingException())


class PdfSourceVisitor(BaseTranslator):
    def __init__(self):
        super().__init__('', '', True)
        # do_translate本身是多线程操作，但是更换为单线程的线程池后没有线程安全问题
        self.source_texts: list[str] = []

    def translate(self, text, *args, **kwargs):
        return self.do_translate(text)

    def do_translate(self, text, rate_limit_params: dict = None):
        self.source_texts.append(text)
        return text

    def do_llm_translate(self, text, rate_limit_params: dict = None):
        raise NotImplementedError


class TranslatedItemsTranslator(BaseTranslator):
    def __init__(self, items: list[CacheItem]):
        super().__init__('', '', True)
        self.items = items
        self.position = 0

    def translate(self, text, *args, **kwargs):
        return self.do_translate(text)

    def do_translate(self, text, rate_limit_params: dict = None):
        if self.position >= len(self.items) or self.items[self.position].source_text != text:
            raise PipelineError("PDF_MAPPING_MISMATCH", "PDF 原文或顺序与缓存不一致，请重新读取 PDF")
        item = self.items[self.position]
        self.position += 1
        return item.final_text

    def assert_complete(self):
        if self.position != len(self.items):
            raise PipelineError("PDF_MAPPING_MISMATCH", "PDF 未完整消费缓存条目，请重新读取 PDF")

    def do_llm_translate(self, text, rate_limit_params: dict = None):
        raise NotImplementedError


class MainThreadExecutor(Executor):
    def __init__(self, *args, **kwargs) -> None:
        pass

    def submit(self, fn, /, *args, **kwargs):
        if "priority" in kwargs:
            del kwargs["priority"]
        f = Future()
        _WorkItem(f, fn, args, kwargs).run()
        return f

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        pass


class TranslationStage:
    __init__ = progress_monitor.TranslationStage.__init__

    def __enter__(self):
        # 在read_content 和 write_content 中对pm附加的属性 pm.pbar_manager = Progress()
        self.pbar = self.pm.pbar_manager.add_task(self.name, total=self.total)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "pbar"):
            with self.lock:
                diff = self.total - self.current
                self.pm.pbar_manager.update(self.pbar, advance=diff)

    def advance(self, n: int = 1):
        if hasattr(self, "pbar"):
            with self.lock:
                self.current += n
                self.pm.pbar_manager.update(self.pbar, advance=n)

    @classmethod
    def create_progress(cls):
        return Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )


class BabeldocPdfAccessor:
    def __init__(self, tmp_directory: Path, output_config: OutputConfig | None, parse_options=None) -> None:
        ensure_pdf_runtime()
        self.tmp_directory = tmp_directory
        self.output_config = output_config
        self.parse_options = dict(parse_options or {})
        self._result_cache: dict[(Path, int), TranslateResult] = {}
        self._init_babeldoc_args()

    def _init_babeldoc_args(self):
        parser = create_parser()
        cmd_args = [
            "--no-watermark", "--ignore-cache", "--skip-scanned-detection",
            "--working-dir", str(self.tmp_directory / "babeldoc_working"),
            "--output", str(self.tmp_directory),
        ]
        if self.output_config:
            if not self.output_config.translated_config.enabled:
                cmd_args.append("--no-mono")
            if not self.output_config.bilingual_config.enabled:
                cmd_args.append("--no-dual")
            if self.output_config.language_config.target_lang_code:
                cmd_args.extend(("--lang-out", self.output_config.language_config.target_lang_code))
        if self.parse_options.get("pages"):
            cmd_args.extend(("--pages", self.parse_options["pages"]))
        self.babeldoc_args = parser.parse_args(cmd_args)
        return self

    def parse_metadata(self, texts):
        settings = ("split_short_lines", "short_line_split_factor", "disable_rich_text_translate",
                    "min_text_length", "formular_font_pattern", "formular_char_pattern", "translate_table_text")
        return {
            "babeldoc_version": version("babeldoc"),
            "parse_options": {"pages": self.babeldoc_args.pages},
            "parser_settings": {name: getattr(self.babeldoc_args, name) for name in settings},
            "source_sequence_sha256": source_sequence_digest(texts),
        }

    _OldExecutor = il_translator.PriorityThreadPoolExecutor
    _OldTranslationStage = progress_monitor.TranslationStage

    def read_content(self, source_file_path: Path):
        visitor = PdfSourceVisitor()
        babeldoc_translation_config = self._create_babeldoc_translation_config(
            self.babeldoc_args, str(source_file_path), visitor
        )

        old_il_translate = il_translator.ILTranslator.translate
        old_il_stage_name = il_translator.ILTranslator.stage_name
        new_il_stage_name = "Read Paragraphs"

        try:
            progress_monitor.TranslationStage = TranslationStage
            il_translator.ILTranslator.stage_name = new_il_stage_name
            il_translator.PriorityThreadPoolExecutor = MainThreadExecutor

            # 提取完原文就可以终止了，不需要后面的写入
            new_il_translate = FinishReading.raise_after_call(old_il_translate)
            il_translator.ILTranslator.translate = new_il_translate

            new_stages = [
                (new_il_stage_name, *stage[1:]) if stage[0] == old_il_stage_name else stage
                for stage in TRANSLATE_STAGES
            ]
            with _managed_documents(), ProgressMonitor(new_stages) as pm, TranslationStage.create_progress() as pbar_manager:
                pm.pbar_manager = pbar_manager
                do_translate(pm, babeldoc_translation_config)
        except ExtractTextError as exc:
            raise PipelineError("SCANNED_PDF_NOT_SUPPORTED", "PDF 不包含可复制文本，本轮不支持扫描件") from exc
        except FinishReading:
            pass
        finally:
            il_translator.ILTranslator.translate = old_il_translate
            il_translator.PriorityThreadPoolExecutor = self._OldExecutor
            il_translator.ILTranslator.stage_name = old_il_stage_name
            progress_monitor.TranslationStage = self._OldTranslationStage
        if not visitor.source_texts:
            raise PipelineError("NO_TRANSLATABLE_TEXT", "PDF 没有可翻译的文本")
        return visitor.source_texts

    def write_content(self, source_file_path: Path, items: list[CacheItem], metadata=None):
        # Babeldoc会同时输出译文和双语文件，为了性能考虑不修改config写两次，而选择一次性输出译文和双语文件，同时缓存输出文件路径
        # lru_cache不接受list，这里手写，简单认为items数组的id代表数组
        metadata = metadata or {}
        current_metadata = self.parse_metadata(item.source_text for item in items)
        for key in ("babeldoc_version", "parse_options", "parser_settings", "source_sequence_sha256"):
            if metadata.get(key) != current_metadata[key]:
                raise PipelineError("PDF_MAPPING_MISMATCH", "PDF 解析版本、参数或原文已变化，请重新读取 PDF")
        cache_id = (file_sha256(source_file_path), source_sequence_digest(
            value for item in items for value in (item.source_text, item.final_text)))
        result = self._result_cache.get(cache_id)
        if result is not None:
            return result

        extracted = self.read_content(source_file_path)
        if source_sequence_digest(extracted) != current_metadata["source_sequence_sha256"]:
            raise PipelineError("PDF_MAPPING_MISMATCH", "PDF 原文定位与缓存不一致，请重新读取 PDF")
        translator = TranslatedItemsTranslator(items)
        babeldoc_translation_config = self._create_babeldoc_translation_config(
            self.babeldoc_args, str(source_file_path), translator
        )
        try:
            progress_monitor.TranslationStage = TranslationStage
            il_translator.PriorityThreadPoolExecutor = MainThreadExecutor

            with _managed_documents(), ProgressMonitor(TRANSLATE_STAGES) as pm, TranslationStage.create_progress() as pbar_manager:
                pm.pbar_manager = pbar_manager
                result = do_translate(pm, babeldoc_translation_config)
            translator.assert_complete()
        except ExtractTextError as exc:
            raise PipelineError("SCANNED_PDF_NOT_SUPPORTED", "PDF 不包含可复制文本，本轮不支持扫描件") from exc
        finally:
            il_translator.PriorityThreadPoolExecutor = self._OldExecutor
            progress_monitor.TranslationStage = self._OldTranslationStage

        self._result_cache.clear()
        self._result_cache[cache_id] = result
        return result

    @classmethod
    def _create_babeldoc_translation_config(cls, args, file, translator):
        table_model = RapidOCRModel() if args.translate_table_text else None
        return TranslationConfig(
            input_file=file,
            font=None,
            pages=args.pages,
            output_dir=args.output,
            translator=translator,
            debug=args.debug,
            lang_in=args.lang_in,
            lang_out=args.lang_out,
            no_dual=args.no_dual,
            no_mono=args.no_mono,
            qps=args.qps,
            formular_font_pattern=args.formular_font_pattern,
            formular_char_pattern=args.formular_char_pattern,
            split_short_lines=args.split_short_lines,
            short_line_split_factor=args.short_line_split_factor,
            doc_layout_model=DocLayoutModel.load_onnx(),
            skip_clean=args.skip_clean,
            dual_translate_first=args.dual_translate_first,
            disable_rich_text_translate=args.disable_rich_text_translate,
            enhance_compatibility=args.enhance_compatibility,
            use_alternating_pages_dual=args.use_alternating_pages_dual,
            report_interval=args.report_interval,
            min_text_length=args.min_text_length,
            watermark_output_mode=WatermarkOutputMode.NoWatermark,
            split_strategy=None,  # 源码中对应args.max_pages_per_part，这里不要
            table_model=table_model,
            show_char_box=args.show_char_box,
            skip_scanned_detection=args.skip_scanned_detection,
            ocr_workaround=args.ocr_workaround,
            custom_system_prompt=None,
        )
