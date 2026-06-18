import logging
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
        self.translation_map = {x.source_text: x.final_text for x in items}

    def translate(self, text, *args, **kwargs):
        return self.do_translate(text)

    def do_translate(self, text, rate_limit_params: dict = None):
        if text in self.translation_map:
            translated_text = self.translation_map[text]
            if not translated_text:
                return text
            # 剥离可能因缓存混用或模型脑补带入的 Word 格式保护标签
            import re
            clean_text = re.sub(r'<t id="\d+">', '', translated_text)
            clean_text = clean_text.replace('</t>', '')
            return clean_text
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
    def __init__(
        self,
        tmp_directory: Path,
        output_config: OutputConfig | None,
        source_lang: str = "zh",
        target_lang: str = "en",
    ) -> None:
        self.tmp_directory = tmp_directory
        self.output_config = output_config
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._result_cache: dict[(Path, int), TranslateResult] = {}
        self._init_babeldoc_args()

    def _init_babeldoc_args(self):
        parser = create_parser()
        cmd_args = [
            "--no-watermark", "--ignore-cache", "--skip-scanned-detection",
            "--working-dir", str(self.tmp_directory / "babeldoc_working"),
            "--output", str(self.tmp_directory),
            # 正确设置源/目标语言（影响 babeldoc 内部字体选择、语言过滤等逻辑）
            "--lang-in", self.source_lang,
            "--lang-out", self.target_lang,
            # 将最小文本长度设为 1，防止"目录"、"申办方："等短中文词被过滤而漏译
            "--min-text-length", "1",
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

        import pickle
        import hashlib

        def new_translate(*args, **kwargs):
            try:
                doc_il = args[1] if len(args) > 1 else kwargs.get("document")
                if doc_il:
                    file_key = hashlib.md5(str(source_file_path).encode("utf-8")).hexdigest()
                    snapshot_file = self.tmp_directory / f"{file_key}.ir.pkl"
                    self.tmp_directory.mkdir(parents=True, exist_ok=True)
                    with open(snapshot_file, "wb") as f:
                        pickle.dump(doc_il, f)
            except Exception as e:
                logging.getLogger("BabeldocPdfAccessor").error(f"保存 PDF 中间表示快照失败: {e}")

            old_il_translate(*args, **kwargs)
            raise FinishReading

        try:
            progress_monitor.TranslationStage = TranslationStage
            il_translator.ILTranslator.stage_name = new_il_stage_name
            il_translator.PriorityThreadPoolExecutor = MainThreadExecutor

            il_translator.ILTranslator.translate = new_translate

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

        import hashlib
        import pickle

        file_key = hashlib.md5(str(source_file_path).encode("utf-8")).hexdigest()
        snapshot_file = self.tmp_directory / f"{file_key}.ir.pkl"
        
        loaded_doc_il = None
        if snapshot_file.exists():
            try:
                with open(snapshot_file, "rb") as f:
                    loaded_doc_il = pickle.load(f)
            except Exception as e:
                logging.getLogger("BabeldocPdfAccessor").error(f"加载 PDF 中间表示快照失败，将退回重新解析: {e}")

        # 导入原本的方法，用于之后还原
        from babeldoc.format.pdf.new_parser import native_parse
        from babeldoc.format.pdf.document_il.midend.detect_scanned_file import DetectScannedFile
        from babeldoc.format.pdf.document_il.midend.layout_parser import LayoutParser
        from babeldoc.format.pdf.document_il.midend.table_parser import TableParser
        from babeldoc.format.pdf.document_il.midend.paragraph_finder import ParagraphFinder
        from babeldoc.format.pdf.document_il.midend.styles_and_formulas import StylesAndFormulas
        from babeldoc.format.pdf.document_il.midend.automatic_term_extractor import AutomaticTermExtractor

        old_native_parse = native_parse.parse_prepared_pdf_with_new_parser_to_legacy_ir
        old_detect_process = DetectScannedFile.process
        old_layout_process = LayoutParser.process
        old_table_process = TableParser.process
        old_para_process = ParagraphFinder.process
        old_style_process = StylesAndFormulas.process
        old_term_process = AutomaticTermExtractor.procress

        patch_applied = False
        translator = TranslatedItemsTranslator(items)
        babeldoc_translation_config = self._create_babeldoc_translation_config(
            self.babeldoc_args, str(source_file_path), translator
        )
        try:
            progress_monitor.TranslationStage = TranslationStage
            il_translator.PriorityThreadPoolExecutor = MainThreadExecutor

            if loaded_doc_il:
                # 劫持解析，直接返回已载入的中间表示树
                native_parse.parse_prepared_pdf_with_new_parser_to_legacy_ir = lambda *args, **kwargs: loaded_doc_il
                
                # 劫持前置处理步骤为“空操作”
                DetectScannedFile.process = lambda *args, **kwargs: None
                LayoutParser.process = lambda self, docs, *args, **kwargs: docs
                # babeldoc对于未包含中文的文本，如果在表格中，则不进行分块输出。
                # 为了确保全部字符均能输出，劫持表格内容分析，禁用之。这有可能导致排版略有异常。
                # TableParser.process = lambda self, docs, *args, **kwargs: docs
                ParagraphFinder.process = lambda *args, **kwargs: None
                StylesAndFormulas.process = lambda *args, **kwargs: None
                AutomaticTermExtractor.procress = lambda *args, **kwargs: None
                patch_applied = True

            with ProgressMonitor(TRANSLATE_STAGES) as pm, TranslationStage.create_progress() as pbar_manager:
                pm.pbar_manager = pbar_manager
                result = do_translate(pm, babeldoc_translation_config)
        except ExtractTextError:
            print(f"`{source_file_path!s}` 不包含可复制的文本，可能是扫描件，不处理")
        finally:
            il_translator.PriorityThreadPoolExecutor = self._OldExecutor
            progress_monitor.TranslationStage = self._OldTranslationStage
            # 还原 Hook 的全局方法
            if patch_applied:
                native_parse.parse_prepared_pdf_with_new_parser_to_legacy_ir = old_native_parse
                DetectScannedFile.process = old_detect_process
                LayoutParser.process = old_layout_process
                TableParser.process = old_table_process
                ParagraphFinder.process = old_para_process
                StylesAndFormulas.process = old_style_process
                AutomaticTermExtractor.procress = old_term_process

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
