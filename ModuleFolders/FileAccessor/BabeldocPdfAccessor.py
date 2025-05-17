
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from babeldoc.document_il.backend.pdf_creater import PDFCreater
from babeldoc.document_il.frontend.il_creater import ILCreater
from babeldoc.document_il.midend.il_translator import ILTranslator
from babeldoc.document_il.midend.layout_parser import LayoutParser
from babeldoc.document_il.midend.paragraph_finder import ParagraphFinder
from babeldoc.document_il.midend.styles_and_formulas import StylesAndFormulas
from babeldoc.document_il.midend.table_parser import TableParser
from babeldoc.document_il.midend.typesetting import Typesetting
from babeldoc.document_il.translator.translator import BaseTranslator
from babeldoc.document_il.utils.priority_thread_pool_executor import (
    PriorityThreadPoolExecutor
)
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
from babeldoc.high_level import (
    TRANSLATE_STAGES,
    fix_filter,
    fix_media_box,
    fix_null_xref,
    start_parse_il
)
from babeldoc.main import create_parser
from babeldoc.progress_monitor import ProgressMonitor
from babeldoc.translation_config import (
    TranslateResult,
    TranslationConfig,
    WatermarkOutputMode
)
from pymupdf import Document

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import OutputConfig


class PdfSourceVisitor(BaseTranslator):
    def __init__(self):
        super().__init__('', '', True)
        # do_translate本身是多线程操作，但是更换为单线程的线程池后没有线程安全问题
        self.source_texts: list[str] = []

    def do_translate(self, text, rate_limit_params: dict = None):
        self.source_texts.append(text)
        return text

    def do_llm_translate(self, text, rate_limit_params: dict = None):
        raise NotImplementedError


class TranslatedItemsTranslator(BaseTranslator):
    def __init__(self, items: list[CacheItem]):
        super().__init__('', '', True)
        self.source_texts = set(x.source_text for x in items)
        self.translated_iter = ((x.source_text, x.translated_text) for x in items)

    def do_translate(self, text, rate_limit_params: dict = None):
        if text in self.source_texts:
            for source_text, translated_text in self.translated_iter:
                if text == source_text:
                    return translated_text
        return text

    def do_llm_translate(self, text, rate_limit_params: dict = None):
        raise NotImplementedError


def _create_babeldoc_translation_config(args, file, translator):
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


# 修改于 babeldoc.high_level._do_translate_single，增加了read_only的退出，删去了不必要的代码
# 官方文档说BabelDOC应该放到子进程中执行，但未放到子进程中也没看出什么问题
def _do_translate_single(
    pm: ProgressMonitor,
    translation_config: TranslationConfig,
    read_only,
) -> TranslateResult:
    """Original translation logic for a single document or part"""
    translation_config.progress_monitor = pm
    original_pdf_path = translation_config.input_file

    # Continue with original processing
    temp_pdf_path = translation_config.get_working_file_path("input.pdf")
    doc_pdf2zh = Document(original_pdf_path)
    resfont = "china-ss"

    # Fix null xref in PDF file
    fix_filter(doc_pdf2zh)
    fix_null_xref(doc_pdf2zh)

    mediabox_data = fix_media_box(doc_pdf2zh)

    for page in doc_pdf2zh:
        page.insert_font(resfont, None)

    resfont = None
    doc_pdf2zh.save(temp_pdf_path)
    il_creater = ILCreater(translation_config)
    il_creater.mupdf = doc_pdf2zh
    with Path(temp_pdf_path).open("rb") as f:
        start_parse_il(
            f,
            doc_zh=doc_pdf2zh,
            resfont=resfont,
            il_creater=il_creater,
            translation_config=translation_config,
        )
    docs = il_creater.create_il()
    del il_creater
    # Rest of the original translation logic...
    # [Previous implementation of do_translate continues here]

    # Generate layouts for all pages
    docs = LayoutParser(translation_config).process(docs, doc_pdf2zh)

    if translation_config.table_model:
        docs = TableParser(translation_config).process(docs, doc_pdf2zh)
    ParagraphFinder(translation_config).process(docs)
    StylesAndFormulas(translation_config).process(docs)

    il_translator = ILTranslator(translation_config.translator, translation_config)
    try:
        # 为了保证顺序，换成单线程的线程池
        def single_thread_init(self, *args, **kwargs):
            ThreadPoolExecutor.__init__(self, max_workers=2)

        def single_thread_submit(self, fn, *args, **kwargs):
            if "priority" in kwargs:
                del kwargs["priority"]
            ThreadPoolExecutor.submit(self, fn, *args, **kwargs)

        old_init = PriorityThreadPoolExecutor.__init__
        old_submit = PriorityThreadPoolExecutor.submit
        old_shutdown = PriorityThreadPoolExecutor.shutdown
        old__adjust_thread_count = PriorityThreadPoolExecutor._adjust_thread_count
        PriorityThreadPoolExecutor.__init__ = single_thread_init
        PriorityThreadPoolExecutor.submit = single_thread_submit
        PriorityThreadPoolExecutor.shutdown = ThreadPoolExecutor.shutdown
        PriorityThreadPoolExecutor._adjust_thread_count = ThreadPoolExecutor._adjust_thread_count
        il_translator.translate(docs)
    finally:
        PriorityThreadPoolExecutor.__init__ = old_init
        PriorityThreadPoolExecutor.submit = old_submit
        PriorityThreadPoolExecutor.shutdown = old_shutdown
        PriorityThreadPoolExecutor._adjust_thread_count = old__adjust_thread_count

    if read_only:
        return

    Typesetting(translation_config).typsetting_document(docs)

    pdf_creater = PDFCreater(temp_pdf_path, docs, translation_config, mediabox_data)
    return pdf_creater.write(translation_config)


class BabeldocPdfAccessor:
    def __init__(self, tmp_directory: Path, output_config: OutputConfig | None) -> None:
        self.tmp_directory = tmp_directory
        self.output_config = output_config
        self._result_cache: dict[(Path, int), TranslateResult] = {}

    def __enter__(self):
        parser = create_parser()
        cmd_args = [
            "--no-watermark", "--ignore-cache",
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

    def __exit__(self, exc_type, exc, exc_tb):
        pass

    def read_content(self, source_file_path: Path):
        visitor = PdfSourceVisitor()
        babeldoc_translation_config = _create_babeldoc_translation_config(
            self.babeldoc_args, str(source_file_path), visitor
        )
        with ProgressMonitor(TRANSLATE_STAGES) as pm:
            _do_translate_single(pm, babeldoc_translation_config, True)
        return visitor.source_texts

    def write_content(self, source_file_path: Path, items: list[CacheItem]):
        # Babeldoc会同时输出译文和双语文件，为了性能考虑不修改config写两次，而选择一次性输出译文和双语文件，同时缓存输出文件路径
        # lru_cache不接受list，这里手写，简单认为items数组的id代表数组
        cache_id = (source_file_path, id(items))
        result = self._result_cache.get(cache_id)
        if result is not None:
            return result

        translator = TranslatedItemsTranslator(items)
        babeldoc_translation_config = _create_babeldoc_translation_config(
            self.babeldoc_args, str(source_file_path), translator
        )
        with ProgressMonitor(TRANSLATE_STAGES) as pm:
            result = _do_translate_single(pm, babeldoc_translation_config, False)

        self._result_cache.clear()
        self._result_cache[cache_id] = result
        return result
