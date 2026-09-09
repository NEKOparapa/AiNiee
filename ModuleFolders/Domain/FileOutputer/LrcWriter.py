from pathlib import Path

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class LrcWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        """输出文件格式示例
        [ti:1.したっぱ童貞構成員へハニートラップ【手コキ】 (Transcribed on 15-May-2023 19-10-13)]
        [00:00.00]お疲れ様です大長 ただいま機会いたしました
        [00:06.78]法案特殊情報部隊一番対処得フィルレイやセルドツナイカーです 今回例の犯罪組織への潜入が成功しましたのでご報告させていただきます
        """
        output_lines = []
        if subtitle_title := cache_file.get_extra("subtitle_title"):
            output_lines.append(f"[ti:{subtitle_title}]\n")
        # 保留读取时收集的非歌词行（[ar:]/[al:]/[offset:]等元数据）
        for kind, line in cache_file.get_extra("other_lines") or []:
            if kind == 'raw':
                output_lines.append(line + "\n")
        # 转换中间字典的格式为最终输出格式
        for item in cache_file.items:
            # 获取字幕时间轴
            subtitle_time = item.require_extra("subtitle_time")
            # 获取字幕文本内容（真实换行会破坏LRC单行结构，替换为空格）
            # splitlines()同时处理 \r\n / \r / \n（旧实现只split("\n")，残留的\r会造出无时间戳的裸行）
            subtitle_text = " ".join(str(item.final_text).splitlines())

            output_lines.append(f"[{subtitle_time}]{subtitle_text}\n")

        # 输出已经翻译的文件
        translation_file_path.write_text("".join(output_lines), encoding=pre_write_metadata.encoding)

    @classmethod
    def get_project_type(self):
        return ProjectType.LRC
