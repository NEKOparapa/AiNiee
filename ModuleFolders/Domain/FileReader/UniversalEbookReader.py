# Module: Universal Ebook Reader & Converter
# Description: Handles conversion of non-standard ebook formats (AZW3, MOBI, DOCX) to EPUB for processing.
#
# Note:
# This module implements conversion logic adapted from:
# https://github.com/ShadowLoveElysia/Bulk-Ebook-Merger-Converter
# Integrated to provide seamless pre-processing for AiNiee.
#
# Author: ShadowLoveElysia
import os
import sys
import subprocess
import shutil
import tempfile
import hashlib
from pathlib import Path
import logging

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
from ModuleFolders.Infrastructure.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)
from ModuleFolders.Domain.FileReader.EpubReader import EpubReader

class UniversalEbookReader(BaseSourceReader):
    
    SUPPORTED_EXTENSIONS = [
        '.azw3', '.mobi', '.docx', '.kepub', '.fb2', 
        '.lit', '.lrf', '.pdb', '.pmlz', '.rb', '.rtf', 
        '.tcr', '.txtz', '.htmlz'
    ]

    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.epub_reader = EpubReader(input_config)
        self.logger = logging.getLogger(__name__)
        # 建立持久化转换缓存目录
        self.cache_base_dir = Path("Resource/Cache/ConvertedEbooks")
        self.cache_base_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_project_type(cls):
        return ProjectType.EPUB

    @property
    def support_file(self):
        exts = [ext.lstrip('.').lower() for ext in self.SUPPORTED_EXTENSIONS]
        exts.append('epub')
        return exts

    def can_read_by_extension(self, file_path: Path) -> bool:
        return file_path.suffix.lstrip('.').lower() in self.support_file

    def can_read_by_content(self, file_path: Path) -> bool:
        return self.can_read_by_extension(file_path)

    def get_file_project_type(self, file_path: Path) -> str:
        return ProjectType.EPUB

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        if file_path.suffix.lower() == '.epub':
            return self.epub_reader.on_read_source(file_path, pre_read_metadata)

        cache_path = self._get_cache_path(file_path)
        if cache_path.exists():
            self.logger.info(f"Using cached EPUB for {file_path}")
            converted_epub_path = cache_path
            need_cleanup = False
        else:
            converted_epub_path = self._convert_to_epub(file_path, cache_path)
            need_cleanup = False

        if not converted_epub_path or not converted_epub_path.exists():
            self.logger.error(f"Failed to obtain EPUB for {file_path}.")
            return CacheFile(items=[])

        try:
            cache_file = self.epub_reader.on_read_source(converted_epub_path, pre_read_metadata)
            
            if cache_file:
                cache_file.extra["original_file_path"] = str(file_path)
                cache_file.extra["original_format"] = file_path.suffix.lower()
                
            return cache_file
        finally:
            if need_cleanup:
                self._cleanup_temp_file(converted_epub_path)

    def _get_cache_path(self, source_path: Path) -> Path:
        """根据文件路径和修改时间生成唯一的缓存文件名"""
        file_stat = source_path.stat()
        # 包含路径、大小和修改时间，确保唯一性
        unique_str = f"{source_path.absolute()}_{file_stat.st_size}_{file_stat.st_mtime}"
        hash_digest = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        return self.cache_base_dir / f"{source_path.stem}_{hash_digest}.epub"

    def _convert_to_epub(self, source_path: Path, target_cache_path: Path) -> Path:
        """调用批量电子书整合.py进行转换"""
        script_path = Path("批量电子书整合.py").resolve()
        if not script_path.exists():
            self.logger.error(f"Conversion script not found at {script_path}")
            return None

        # 临时转换目录
        temp_dir = Path(tempfile.mkdtemp(prefix="ainiee_conv_work_"))
        output_filename = "converted_result" 

        cmd = [
            sys.executable, str(script_path),
            "-p", str(source_path), 
            "-f", "epub",
            "-m", "novel", 
            "-o", output_filename, 
            "-op", str(temp_dir), 
            "--AiNiee", 
            "--auto-merge" 
        ]
        
        try:
            self.logger.info(f"Converting {source_path} to EPUB...")
            result = subprocess.run(cmd, capture_output=True, text=False)

            # 查找生成的 EPUB
            epubs = list(temp_dir.glob("*.epub"))
            if not epubs:
                # 尝试解码错误信息输出
                stderr_text = result.stderr.decode('utf-8', errors='ignore')
                self.logger.error(f"Conversion failed. Script output: {stderr_text}")
                return None
            
            # 将生成的 EPUB 移动到持久化缓存位置
            generated_epub = epubs[0]
            shutil.move(str(generated_epub), str(target_cache_path))
            return target_cache_path

        except Exception as e:
            self.logger.error(f"Error during conversion: {e}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _cleanup_temp_file(self, file_path: Path):
        # 此方法现在仅用于非缓存的临时清理（如果有的话）
        pass
