import os
import subprocess
import threading
from pathlib import Path

from PyQt5.QtWidgets import QFrame, QGroupBox, QHBoxLayout, QVBoxLayout, QFileDialog, QWidget, QComboBox
from PyQt5.QtCore import Qt, pyqtSignal

from qfluentwidgets import (
    StrongBodyLabel, PushButton, PrimaryPushButton, FluentIcon, 
    CheckBox, ComboBox, LineEdit, InfoBar, InfoBarPosition
)

class MergeEbookPage(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(' ', '-'))
        self.script_path = os.path.join(os.getcwd(), "批量电子书整合.py")
        self._init_ui()

    def _init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # 标题
        title_label = StrongBodyLabel("批量电子书整合 (Merge Ebooks)", self)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        main_layout.addWidget(title_label)

        # 说明
        desc_label = StrongBodyLabel("支持将多本小说/漫画合并，或转换格式 (EPUB, MOBI, AZW3, PDF 等)。\nSupport merging multiple ebooks/comics or converting formats.", self)
        main_layout.addWidget(desc_label)

        # --- 输入设置 ---
        input_group = QGroupBox("输入设置 (Input)")
        input_layout = QVBoxLayout(input_group)
        
        # 输入文件夹/文件
        path_layout = QHBoxLayout()
        self.input_path_label = StrongBodyLabel("未选择 (No Selection)", self)
        self.input_path_label.setWordWrap(True)
        
        self.input_file_btn = PushButton("选择文件 (Select File)", self, FluentIcon.DOCUMENT)
        self.input_file_btn.clicked.connect(self._select_input_file)
        
        self.input_folder_btn = PushButton("选择文件夹 (Select Folder)", self, FluentIcon.FOLDER)
        self.input_folder_btn.clicked.connect(self._select_input_folder)
        
        path_layout.addWidget(self.input_path_label, 1)
        path_layout.addWidget(self.input_file_btn)
        path_layout.addWidget(self.input_folder_btn)
        input_layout.addLayout(path_layout)
        
        main_layout.addWidget(input_group)

        # --- 输出设置 ---
        output_group = QGroupBox("输出设置 (Output)")
        output_layout = QVBoxLayout(output_group)

        # 输出文件夹
        out_path_layout = QHBoxLayout()
        self.output_path_label = StrongBodyLabel("默认输出到源目录 (Default: Source Dir)", self)
        self.output_path_btn = PushButton("选择输出文件夹 (Select Output)", self, FluentIcon.FOLDER)
        self.output_path_btn.clicked.connect(self._select_output_folder)
        out_path_layout.addWidget(self.output_path_label, 1)
        out_path_layout.addWidget(self.output_path_btn)
        output_layout.addLayout(out_path_layout)
        
        # 文件名
        name_layout = QHBoxLayout()
        name_label = StrongBodyLabel("输出文件名 (Output Name):", self)
        self.output_name_edit = LineEdit(self)
        self.output_name_edit.setPlaceholderText("默认 (Default)")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.output_name_edit, 1)
        output_layout.addLayout(name_layout)

        main_layout.addWidget(output_group)

        # --- 转换选项 ---
        opt_group = QGroupBox("转换选项 (Options)")
        opt_layout = QVBoxLayout(opt_group)
        
        # 模式 & 格式
        combo_layout = QHBoxLayout()
        
        mode_label = StrongBodyLabel("模式 (Mode):", self)
        self.mode_combo = ComboBox(self)
        self.mode_combo.addItems(["Novel (小说 - 文本优先)", "Comic (漫画 - 图片优先)"])
        
        format_label = StrongBodyLabel("目标格式 (Format):", self)
        self.format_combo = ComboBox(self)
        self.format_combo.addItems(["EPUB", "MOBI", "AZW3", "PDF", "CBZ", "All Native (EPUB+PDF+CBZ)"])
        
        combo_layout.addWidget(mode_label)
        combo_layout.addWidget(self.mode_combo, 1)
        combo_layout.addStretch(1)
        combo_layout.addWidget(format_label)
        combo_layout.addWidget(self.format_combo, 1)
        opt_layout.addLayout(combo_layout)

        # 其他选项
        check_layout = QHBoxLayout()
        self.remove_style_check = CheckBox("移除原样式 (Remove Styling)", self)
        self.remove_style_check.setChecked(True) # 默认移除，通常更好
        self.ai_niee_check = CheckBox("AiNiee 模式 (无版权信息)", self)
        self.ai_niee_check.setChecked(True)
        
        check_layout.addWidget(self.remove_style_check)
        check_layout.addWidget(self.ai_niee_check)
        check_layout.addStretch(1)
        opt_layout.addLayout(check_layout)

        main_layout.addWidget(opt_group)

        # --- 按钮 ---
        btn_layout = QHBoxLayout()
        self.start_btn = PrimaryPushButton("开始处理 (Start Processing)", self, FluentIcon.PLAY)
        self.start_btn.clicked.connect(self._start_processing)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addStretch(1)
        
        main_layout.addLayout(btn_layout)
        main_layout.addStretch(1)

        self.input_path = ""
        self.output_dir = ""

    def _select_input_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "Ebooks (*.epub *.mobi *.azw3 *.txt *.pdf *.cbz);;All Files (*.*)")
        if file:
            self.input_path = file
            self.input_path_label.setText(file)

    def _select_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if folder:
            self.input_path = folder
            self.input_path_label.setText(folder)

    def _select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.output_dir = folder
            self.output_path_label.setText(folder)

    def _start_processing(self):
        if not self.input_path:
            InfoBar.error("错误 (Error)", "请先选择输入 (Please select input first)", parent=self)
            return

        mode = "novel" if "Novel" in self.mode_combo.currentText() else "comic"
        
        format_map = {
            "EPUB": "epub", "MOBI": "mobi", "AZW3": "azw3", 
            "PDF": "pdf", "CBZ": "cbz", "All Native (EPUB+PDF+CBZ)": "all_native"
        }
        fmt = format_map.get(self.format_combo.currentText(), "epub")
        
        cmd = [
            "python", self.script_path,
            "-p", self.input_path,
            "-f", fmt,
            "-m", mode,
            "--auto-merge"
        ]

        if self.output_dir:
            cmd.extend(["-op", self.output_dir])
        
        out_name = self.output_name_edit.text().strip()
        if out_name:
            cmd.extend(["-o", out_name])
            
        if self.remove_style_check.isChecked():
            cmd.append("-rs")
            
        if self.ai_niee_check.isChecked():
            cmd.append("--AiNiee")

        self.start_btn.setEnabled(False)
        self.start_btn.setText("正在处理 (Processing)...")
        
        # 在后台线程运行
        threading.Thread(target=self._run_script, args=(cmd,), daemon=True).start()

    def _run_script(self, cmd):
        try:
            # print("Executing:", " ".join(cmd))
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            output_lines = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    print(line.strip()) # 输出到控制台供调试
                    output_lines.append(line)
            
            rc = process.poll()
            
            # 回到主线程更新 UI (简单方式：直接在线程调用，PyQt通常允许setText等简单操作，但InfoBar需要注意)
            # 为了安全，这里不使用信号槽（虽然应该用），而是简单的状态重置
            # 实际项目中建议使用 QThread + Signal
            
            if rc == 0:
                self.start_btn.setText("完成 (Completed)")
                # InfoBar.success("完成", "处理成功！请查看输出目录。", parent=self) # 跨线程调用可能崩溃
            else:
                self.start_btn.setText("失败 (Failed)")
                # InfoBar.error("错误", "处理失败，请查看日志。", parent=self)

        except Exception as e:
            print(f"Error running script: {e}")
            self.start_btn.setText("错误 (Error)")
        finally:
            # 恢复按钮
            # QTimer.singleShot(2000, lambda: self.start_btn.setEnabled(True))
            # QTimer.singleShot(2000, lambda: self.start_btn.setText("开始处理 (Start Processing)"))
            self.start_btn.setEnabled(True) # 立即恢复以便重试
