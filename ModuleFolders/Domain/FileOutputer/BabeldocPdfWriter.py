import shutil
from pathlib import Path

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheProject import ProjectType
try:
    from ModuleFolders.Domain.FileAccessor.BabeldocPdfAccessor import BabeldocPdfAccessor
except ImportError:
    BabeldocPdfAccessor = None
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class BabeldocPdfWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig, tmp_directory='babeldoc_cache',
                 source_lang: str = "zh", target_lang: str = "en"):
        super().__init__(output_config)
        self.tmp_directory = tmp_directory
        
        if BabeldocPdfAccessor is None:
            self.file_accessor = None
            self.abs_tmp_directory = None
            return

        # 获取输入根路径
        root_path = output_config.input_root
        # 如果输入路径存在且是文件（即用户选择了单文件进行处理），则使用其父目录
        if root_path and root_path.is_file():
            root_path = root_path.parent
            
        self.abs_tmp_directory = root_path / self.tmp_directory
        
        self.file_accessor = BabeldocPdfAccessor(self.abs_tmp_directory, output_config, source_lang, target_lang)

    def __exit__(self, exc_type, exc, exc_tb):
        if getattr(self, 'abs_tmp_directory', None) and self.abs_tmp_directory.exists():
            shutil.rmtree(self.abs_tmp_directory)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file,
            pre_write_metadata, source_file_path, "mono_pdf_path"
        )

    def on_write_bilingual(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file,
            pre_write_metadata, source_file_path, "dual_pdf_path"
        )

    def _write_translation_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path,
        babeldoc_output_attr: str,
    ):
        if self.file_accessor is None:
            raise RuntimeError("未安装 PDF 翻译依赖 (BabelDOC)，无法导出 PDF。请在命令行运行 `pip install BabelDOC` 安装后再试。")
        result = self.file_accessor.write_content(source_file_path, cache_file.items)
        babeldoc_path_str = getattr(result, babeldoc_output_attr)
        if babeldoc_path_str and (babeldoc_path := Path(babeldoc_path_str)).exists():
            # 确保目标文件夹存在
            if not translation_file_path.parent.exists():
                translation_file_path.parent.mkdir(parents=True, exist_ok=True)
                
            if translation_file_path.exists():
                translation_file_path.unlink()
            babeldoc_path.rename(translation_file_path)

    @classmethod
    def get_project_type(self):
        return ProjectType.BABELDOC_PDF