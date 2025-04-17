from pathlib import Path

from ModuleFolders.FileConverter.BaseConverter import BaseFileConverter


class OfficeFileConverter(BaseFileConverter):

    FILE_SUFFIX_MAPPING = {
        ".doc": 0,  # wdFormatDocument
        ".docx": 16,  # wdFormatDocumentDefault
        ".pdf": 17,  # wdFormatPDF
    }

    def __enter__(self):
        import pythoncom
        from win32com import client

        pythoncom.CoInitialize()
        try:
            self.office = client.Dispatch("Word.Application")
            self.office.Visible = False  # 不显示 Word 界面
            self.office.DisplayAlerts = False  # 关闭所有弹窗
            self.office.AutomationSecurity = 1  # 禁用宏和安全性弹窗（重要！）
        except:
            print("不能打开Word程序，请确保安装了 Microsoft Office")
            pythoncom.CoUninitialize()

    def __exit__(self, exc_type, exc, exc_tb):
        import pythoncom

        if self.office:
            self.office.Quit()
        pythoncom.CoUninitialize()

    def can_convert(self, input_file_path: Path, output_file_path: Path) -> bool:
        # 输出文件类型不在类型映射中暂不支持
        if output_file_path.suffix not in self.FILE_SUFFIX_MAPPING:
            return False

        # wps 不支持 pdf 转其他格式
        if input_file_path.suffix != '.pdf':
            return True
        app_name = self.office.Name.lower()
        is_wps = 'wps' in app_name or 'kingsoft' in app_name
        if is_wps:
            print("wps不支持把pdf文件转换为其他格式")
        return not is_wps

    def convert_file(self, input_file_path: Path, output_file_path: Path):
        if not output_file_path.parent.exists():
            output_file_path.parent.mkdir(parents=True)
        # 打开文件另存为
        doc = self.office.Documents.Open(str(input_file_path), ReadOnly=1)
        try:
            doc.SaveAs(str(output_file_path), self.FILE_SUFFIX_MAPPING[output_file_path.suffix])
        finally:
            doc.Close()
