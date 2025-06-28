import logging
from concurrent.futures import Executor, Future
from concurrent.futures.thread import _WorkItem
from pathlib import Path

from babeldoc import progress_monitor
from babeldoc.babeldoc_exception.BabelDOCException import ExtractTextError
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
from babeldoc.format.pdf.document_il.midend import il_translator
from babeldoc.format.pdf.high_level import (
    TRANSLATE_STAGES,
    _do_translate_single
)
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

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import OutputConfig


class IgnoreStyleNoneFilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().startswith("Style is None")


# 屏蔽告警
logger = logging.getLogger("babeldoc.format.pdf.document_il.midend.typesetting")
logger.addFilter(IgnoreStyleNoneFilter())


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


class FinishReading(Exception):
    @classmethod
    def raise_after_call(cls, func):
        def warpper(*args, **kwargs):
            func(*args, **kwargs)
            raise FinishReading
        return warpper


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
            with ProgressMonitor(new_stages) as pm, TranslationStage.create_progress() as pbar_manager:
                pm.pbar_manager = pbar_manager
                _do_translate_single(pm, babeldoc_translation_config)
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
        babeldoc_translation_config = self._create_babeldoc_translation_config(
            self.babeldoc_args, str(source_file_path), translator
        )
        try:
            progress_monitor.TranslationStage = TranslationStage
            il_translator.PriorityThreadPoolExecutor = MainThreadExecutor

            with ProgressMonitor(TRANSLATE_STAGES) as pm, TranslationStage.create_progress() as pbar_manager:
                pm.pbar_manager = pbar_manager
                result = _do_translate_single(pm, babeldoc_translation_config)
        except ExtractTextError:
            print(f"`{source_file_path!s}` 不包含可复制的文本，可能是扫描件，不处理")
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
