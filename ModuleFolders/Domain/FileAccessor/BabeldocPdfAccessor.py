import hashlib
import logging
import shutil
from concurrent.futures import Executor, Future
from concurrent.futures.thread import _WorkItem
from pathlib import Path

from babeldoc import progress_monitor
from babeldoc.babeldoc_exception.BabelDOCException import ExtractTextError
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
from babeldoc.format.pdf.document_il.midend import il_translator
from babeldoc.format.pdf.high_level import TRANSLATE_STAGES, do_translate
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

from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Domain.FileOutputer.BaseWriter import OutputConfig


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
        self.source_texts = set(x.source_text for x in items)
        self.translated_iter = ((x.source_text, x.final_text) for x in items)

    def translate(self, text, *args, **kwargs):
        return self.do_translate(text)

    def do_translate(self, text, rate_limit_params: dict = None):
        if text in self.source_texts:
            for source_text, translated_text in self.translated_iter:
                if text == source_text:
                    return translated_text
        return text

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
    def __init__(self, tmp_directory: Path, output_config: OutputConfig | None) -> None:
        self.tmp_directory = tmp_directory
        self.output_config = output_config
        self._result_cache: dict[(Path, int), TranslateResult] = {}
        self._input_alias_cache: dict[Path, Path] = {}
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
        self.babeldoc_args = parser.parse_args(cmd_args)
        return self

    _OldExecutor = il_translator.PriorityThreadPoolExecutor
    _OldTranslationStage = progress_monitor.TranslationStage

    def read_content(self, source_file_path: Path):
        visitor = PdfSourceVisitor()
        prepared_source_file_path = self._prepare_babeldoc_input_file(source_file_path)
        babeldoc_translation_config = self._create_babeldoc_translation_config(
            self.babeldoc_args, str(prepared_source_file_path), visitor
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
            with ProgressMonitor(new_stages) as pm, TranslationStage.create_progress() as pbar_manager:
                pm.pbar_manager = pbar_manager
                do_translate(pm, babeldoc_translation_config)
        except ExtractTextError:
            print(f"`{source_file_path!s}` 不包含可复制的文本，可能是扫描件，不处理")
        except FinishReading:
            pass
        finally:
            il_translator.ILTranslator.translate = old_il_translate
            il_translator.PriorityThreadPoolExecutor = self._OldExecutor
            il_translator.ILTranslator.stage_name = old_il_stage_name
            progress_monitor.TranslationStage = self._OldTranslationStage
        return visitor.source_texts

    def write_content(self, source_file_path: Path, items: list[CacheItem]):
        # Babeldoc会同时输出译文和双语文件，为了性能考虑不修改config写两次，而选择一次性输出译文和双语文件，同时缓存输出文件路径
        # lru_cache不接受list，这里手写，简单认为items数组的id代表数组
        cache_id = (source_file_path, id(items))
        result = self._result_cache.get(cache_id)
        if result is not None:
            return result

        translator = TranslatedItemsTranslator(items)
        prepared_source_file_path = self._prepare_babeldoc_input_file(source_file_path)
        babeldoc_translation_config = self._create_babeldoc_translation_config(
            self.babeldoc_args, str(prepared_source_file_path), translator
        )
        try:
            progress_monitor.TranslationStage = TranslationStage
            il_translator.PriorityThreadPoolExecutor = MainThreadExecutor

            with ProgressMonitor(TRANSLATE_STAGES) as pm, TranslationStage.create_progress() as pbar_manager:
                pm.pbar_manager = pbar_manager
                result = do_translate(pm, babeldoc_translation_config)
        except ExtractTextError:
            print(f"`{source_file_path!s}` 不包含可复制的文本，可能是扫描件，不处理")
        finally:
            il_translator.PriorityThreadPoolExecutor = self._OldExecutor
            progress_monitor.TranslationStage = self._OldTranslationStage

        self._result_cache.clear()
        self._result_cache[cache_id] = result
        return result

    def _prepare_babeldoc_input_file(self, source_file_path: Path) -> Path:
        source_file_path = source_file_path.resolve()
        cached_path = self._input_alias_cache.get(source_file_path)
        if cached_path and cached_path.exists():
            return cached_path

        alias_directory = self.tmp_directory / "input_alias"
        alias_directory.mkdir(parents=True, exist_ok=True)

        safe_stem = self._build_short_pdf_stem(source_file_path)
        alias_path = alias_directory / f"{safe_stem}{source_file_path.suffix.lower() or '.pdf'}"

        if alias_path.exists() or alias_path.is_symlink():
            alias_path.unlink()

        try:
            alias_path.symlink_to(source_file_path)
        except OSError:
            shutil.copy2(source_file_path, alias_path)

        self._input_alias_cache[source_file_path] = alias_path
        return alias_path

    @staticmethod
    def _build_short_pdf_stem(source_file_path: Path) -> str:
        sanitized_stem = ''.join(
            ch if ch.isalnum() or ch in ('-', '_') else '_'
            for ch in source_file_path.stem
        ).strip('_')
        if not sanitized_stem:
            sanitized_stem = "pdf"

        shortened_prefix = sanitized_stem[:32].rstrip('_')
        digest = hashlib.sha1(str(source_file_path).encode("utf-8")).hexdigest()[:12]
        return f"{shortened_prefix}_{digest}" if shortened_prefix else f"pdf_{digest}"

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
