# /// script
# dependencies = [
#   "PyMuPDF",
#   "Pillow",
#   "EbookLib",
#   "requests",
#   "tqdm",
#   "natsort",
# ]
# ///

import os
import re
import sys
import io
import argparse
import platform
import shutil
import webbrowser
import subprocess
import gc 
import time
import zipfile
import importlib
import posixpath
import urllib.parse
import json

elysiaFitz = None



FORMAT_CHOICE_MAP = {
    '1': 'epub', '2': 'pdf', '3': 'cbz', '4': 'mobi', '5': 'azw3', '6': 'docx',
    '7': 'txt', '8': 'kepub', '9': 'fb2', '10': 'lit', '11': 'lrf',
    '12': 'pdb', '13': 'pmlz', '14': 'rb', '15': 'rtf', '16': 'tcr',
    '17': 'txtz', '18': 'htmlz',
    '19': 'all_native'
}
ALL_FORMAT_VALUES = list(FORMAT_CHOICE_MAP.values())

STRINGS = {
    'error_dir_not_exist': {'zh': "错误: 目录 '{}' 不存在。", 'en': "Error: Directory '{}' does not exist.", 'ja': "エラー: ディレクトリ「{}」が見つかりません。"},
    'error_no_files': {'zh': "错误：在目录 '{}' 中未找到任何 '{}' 文件。", 'en': "Error: No '{}' files found in the directory '{}'.", 'ja': "エラー：ディレクトリ「{}」に「{}」ファイルが見つかりませんでした。"},
    'prompt_main_menu': {'zh': "\n欢迎使用！请选择操作模式:\n  1) 控制台交互模式\n  2) 查看所有参数说明\n  3) 退出\n请输入选项 (1, 2 或 3):", 'en': "\nWelcome! Please select an operation mode:\n  1) Interactive Console Mode\n  2) View All Parameter Help\n  3) Exit\nEnter your choice (1, 2 or 3):", 'ja': "\nようこそ！操作モードを選択してください:\n  1) 対話型コンソールモード\n  2) すべてのパラメータヘルプを表示\n  3) 終了\n選択肢（1、2、または3）を入力してください:"},
    'prompt_language_select': {'zh': "请选择后续提示的语言 (zh, en, ja):", 'en': "Please select a language for subsequent prompts (zh, en, ja):", 'ja': "後続のプロンプトの言語を選択してください (zh, en, ja):"},
    'prompt_input_path': {'zh': "请输入包含源文件（PDF, CBZ, EPUB等）的文件夹路径:", 'en': "Please enter the path to the folder containing source files (PDFs, CBZs, EPUBs, etc.):", 'ja': "ソースファイル（PDF、CBZ、EPUBなど）が含まれるフォルダのパスを入力してください:"},
    'multi_folder_tip': {'zh': "提示：若要一次性处理多个文件夹，请使用命令行参数模式 (例如: python 批量电子书整合.py -p C:\\A C:\\B ...)。", 'en': "Tip: To process multiple folders at once, please use the command-line argument mode (e.g., python 批量电子书整合.py -p C:\\A C:\\B ...).", 'ja': "ヒント：一度に複数のフォルダを処理するには、コマンドライン引数モードを使用してください (例: python 批量电子书整合.py -p C:\\A C:\\B ...)。"},
    'warn_multi_folder_output_ignored': {'zh': "警告：在多文件夹模式下，-o/--output 参数 '{}' 将被忽略，以防止文件覆盖。将使用文件夹名称作为输出文件名。", 'en': "Warning: In multi-folder mode, the -o/--output argument '{}' is ignored to prevent file overwrites. Folder names will be used for output files.", 'ja': "警告：複数フォルダモードでは、-o/--output引数「{}」はファイルの上書きを防ぐために無視されます。フォルダ名が出力ファイル名として使用されます。"},
    'warn_multi_folder_title_ignored': {'zh': "警告：在多文件夹模式下，-t/--title 参数 '{}' 将被忽略。将使用文件夹名称作为标题。", 'en': "Warning: In multi-folder mode, the -t/--title argument '{}' is ignored. Folder names will be used for titles.", 'ja': "警告：複数フォルダモードでは、-t/--title引数「{}」は無視されます。フォルダ名がタイトルとして使用されます。"},
    'detected_folder_type': {'zh': "检测到文件夹主要包含 '{}' 文件。将首先将它们批量整合成一个临时的EPUB文件。", 'en': "Detected folder primarily contains '{}' files. They will be consolidated into a single temporary EPUB file first.", 'ja': "フォルダに主に「{}」ファイルが含まれていることが検出されました。最初にこれらを単一个の一時的なEPUBに統合します。"},
    'consolidating': {'zh': "第一步：整合 {} 个 '{}' 文件...", 'en': "Step 1: Consolidating {} '{}' files...", 'ja': "ステップ1：{}個の「{}」ファイルを統合しています..."},
    'consolidation_complete': {'zh': "整合完成，临时EPUB文件已生成。", 'en': "Consolidation complete, temporary EPUB file generated.", 'ja': "統合が完了し、一時的なEPUBファイルが生成されました。"},
    'distributing': {'zh': "分发步骤：从临时文件分发到最终格式...", 'en': "Distribution Step: Distributing from temporary file to final formats...", 'ja': "配布ステップ：一時ファイルから最終フォーマットに配布しています..."},
    'calibre_needed': {'zh': "此操作需要Calibre命令行工具。", 'en': "This operation requires the Calibre command-line tools.", 'ja': "この操作にはCalibreコマンドラインツールが必要です。"},
    'calibre_needed_param_mode': {'zh': "错误：此操作需要Calibre，但在系统中未找到。请手动安装Calibre并确保其在系统PATH中，或使用控制台模式进行自动下载。", 'en': "Error: This operation requires Calibre, which was not found. Please install Calibre manually and ensure it's in the system PATH, or use the interactive console mode for automatic download.", 'ja': "エラー：この操作にはCalibreが必要ですが、システムに見つかりませんでした。手動でCalibreをインストールしてPATHに追加するか、コンソールモードを使用して自動ダウンロードを行ってください。"},
    'prompt_calibre_download': {'zh': "  1) 自动下载并安装到脚本目录 (推荐, 仅限Windows)\n  2) 打开官网手动下载\n请选择 (1或2):", 'en': "  1) Automatically download and set up locally (Recommended, Windows Only)\n  2) Open official website to download manually\nPlease choose (1 or 2):", 'ja': "  1) 自動的にダウンロードしてローカルに設定 (推奨, Windowsのみ)\n  2) 公式サイトを開いて手動でダウンロード\n選択してください (1または2):"},
    'calibre_downloading': {'zh': "正在从官网下载Calibre便携版...", 'en': "Downloading Calibre Portable from the official website...", 'ja': "公式サイトからCalibreポータブル版をダウンロードしています..."},
    'calibre_extracting': {'zh': "下载完成。正在安装到 '{}'...", 'en': "Download complete. Installing to '{}'...", 'ja': "ダウンロードが完了しました。「{}」にインストールしています..."},
    'calibre_ready': {'zh': "Calibre已准备就绪。", 'en': "Calibre is ready.", 'ja': "Calibreの準備ができました。"},
    'calibre_manual_prompt': {'zh': "请访问 https://calibre-ebook.com/download 进行下载和安装，然后重新运行脚本。", 'en': "Please visit https://calibre-ebook.com/download to download and install, then restart the script.", 'ja': "https://calibre-ebook.com/download にアクセスしてダウンロードとインストールを行い、スクリプトを再起動してください。"},
    'calibre_download_failed': {'zh': "自动下载失败。请检查您的网络连接。", 'en': "Automatic download failed. Please check your network connection.", 'ja': "自動ダウンロードに失敗しました。网络接続を確認してください。"},
    'calibre_install_failed': {'zh': "Calibre 安装失败。请尝试手动安装或检查权限。", 'en': "Calibre installation failed. Please try manual installation or check permissions.", 'ja': "Calibreのインストールに失敗しました。手動でインストールを試すか、権限を確認してください。"},
    'prompt_final_format': {
        'zh': """请选择最终输出格式 (输入数字):
---
常用格式 ---
  1) EPUB (通用电子书)
  2) PDF (通用文档)
  3) CBZ (漫画格式)
---
Kindle 专用 ---
  4) MOBI (旧Kindle)
  5) AZW3 (新Kindle)
---
其他格式 (需要Calibre) ---
  6) DOCX   7) TXT    8) KEPUB  9) FB2
  10) LIT   11) LRF   12) PDB   13) PMLZ
  14) RB    15) RTF   16) TCR   17) TXTZ
  18) HTMLZ
---
特殊选项 ---
  19) 全部原生格式 (EPUB+PDF+CBZ)
您的选择:""",
        'en': """Please select the final output format (enter number):
---
Common Formats ---
  1) EPUB (Universal E-book)
  2) PDF (Universal Document)
  3) CBZ (Comic Book Archive)
---
Kindle Formats ---
  4) MOBI (Old Kindle)
  5) AZW3 (New Kindle)
---
Other Formats (Calibre Required) ---
  6) DOCX   7) TXT    8) KEPUB  9) FB2
  10) LIT   11) LRF   12) PDB   13) PMLZ
  14) RB    15) RTF   16) TCR   17) TXTZ
  18) HTMLZ
---
Special Options ---
  19) All Native Formats (EPUB+PDF+CBZ)
Your choice:""",
        'ja': """最終的な出力形式を選択してください（番号を入力）:
---
一般的な形式 ---
  1) EPUB (汎用電子書籍)
  2) PDF (汎用ドキュメント)
  3) CBZ (コミックブックアーカイブ)
---
Kindle形式 ---
  4) MOBI (旧Kindle)
  5) AZW3 (新Kindle)
---
その他の形式 (Calibreが必要) ---
  6) DOCX   7) TXT    8) KEPUB  9) FB2
  10) LIT   11) LRF   12) PDB   13) PMLZ
  14) RB    15) RTF   16) TCR   17) TXTZ
  18) HTMLZ
---
特別なオプション ---
  19) すべてのネイティブ形式 (EPUB+PDF+CBZ)
選択:"""
    },
    'creating_epub': {'zh': "创建EPUB...", 'en': "Creating EPUB...", 'ja': "EPUBを作成..."},
    'creating_pdf': {'zh': "创建PDF...", 'en': "Creating PDF...", 'ja': "PDFを作成..."},
    'creating_cbz': {'zh': "创建CBZ...", 'en': "Creating CBZ...", 'ja': "CBZを作成..."},
    'preparing_pages': {'zh': "正在准备页面列表... 发现 {} 个总页面/图片。", 'en': "Preparing page list... Found {} total pages/images.", 'ja': "ページリストを準備中... 合計{}ページ/画像が見つかりました。"},
    'processing_and_writing': {'zh': "正在使用 {} 个线程并行处理并写入: {}/{}", 'en': "Processing and writing in parallel with {} workers: {}/{}", 'ja': "{}個のワーカーで並列処理および書き込み中: {}/{}"},
    'finalizing_file': {'zh': "\n所有内容处理完毕。正在最终化文件...", 'en': "\nAll content processed. Finalizing file...", 'ja': "\nすべてのコンテンツが処理されました。最終ファイルを生成しています..."},
    'task_complete': {'zh': "任务完成！文件已保存为 '{}'", 'en': "Task complete! File saved as '{}'", 'ja': "タスク完了！ファイルは「{}」として保存されました。"},
    'exiting': {'zh': "正在退出...", 'en': "Exiting...", 'ja': "終了しています..."},
    'error_invalid_choice': {'zh': "输入无效。", 'en': "Invalid input.", 'ja': "無効な入力です。"},
    'epub_merge_notice_calibre': {'zh': "警告：EPUB合并功能将使用Calibre的 ebook-convert 工具。此方法会保留文本和排版，但对于不同来源的EPUB，仍可能出现小的格式调整。", 'en': "Warning: EPUB merge will use Calibre's ebook-convert tool. This method preserves text and layout but might have minor formatting adjustments for EPUBs from different sources.", 'ja': "警告：EPUB結合機能はCalibreのebook-convertツールを使用します。この方法はテキストとレイアウトを保持しますが、異なるソースのEPUBでは、小さなフォーマット調整が発生する可能性があります。"},
    'epub_merge_fail_calibre': {'zh': "EPUB合并失败。", 'en': "EPUB merge failed.", 'ja': "EPUB結合に失敗しました。"},
    'dep_missing_tip': {'zh': "缺少 Python 库：'{}'。请运行以下命令安装：\n  pip install {}", 'en': "Missing Python library: '{}'. Please install it using:\n  pip install {}", 'ja': "Pythonライブラリ「{}」が見つかりません。以下のコマンドでインストールしてください:\n  pip install {}"},
    'dep_reboot_tip': {'zh': "请安装上述缺失的库后，重新运行脚本。", 'en': "Please install the missing libraries above, then restart the script.", 'ja': "上記の見つからないライブラリをインストールしてから、スクリプトを再起動してください。"},
    'get_version_fail': {'zh': "无法获取Calibre最新版本信息。请检查网络或稍后重试。", 'en': "Could not fetch latest Calibre version. Check network or try again later.", 'ja': "Calibreの最新バージョン情報を取得できませんでした。ネットワークを確認するか、後で再試行してください。"},
    'download_url_fail': {'zh': "未能找到Calibre便携版下载链接。", 'en': "Could not find Calibre Portable download link.", 'ja': "Calibreポータブル版のダウンロードリンクが見つかりませんでした。"},
    'calibre_tool_missing_specific': {'zh': "错误：Calibre 工具 '{}' 在您的 Calibre 安装中未找到。\n此操作需要此工具。请尝试使用本脚本的自动下载功能，或手动安装完整的 Calibre 桌面版。", 'en': "Error: Calibre tool '{}' not found in your Calibre installation.\nThis operation requires this tool. Try using the script's automatic download, or manually install the full Calibre desktop version.", 'ja': "エラー：Calibreツール「{}」がCalibreのインストールに見つかりませんでした。\nこの操作にはこのツールが必要です。このスクリプトの自動ダウンロードを試すか、Calibreの完全デスクトップ版を手動でインストールしてください。"},
    'prompt_mode_select': {'zh': "请选择处理模式:\n  1) 漫画模式 (图片优先，适合扫描PDF/CBZ)\n  2) 小说模式 (文本优先，智能识别TXT/EPUB章节合并)\n您的选择:", 'en': "Select mode:\n  1) Comic Mode (Image-first)\n  2) Novel Mode (Text-first, Smart TXT/EPUB Merge)\nChoice:", 'ja': "モード選択:\n  1) コミック\n  2) 小説 (テキスト優先、スマート結合)\n選択:"},
    'novel_mode_intro': {'zh': "已选择小说模式。将自动检测是否可用智能合并(TXT/EPUB)，否则使用通用PDF转换流程。", 'en': "Novel mode selected. Will auto-detect Smart Merge (TXT/EPUB) or fallback to PDF flow.", 'ja': "小説モードが選択されました。スマート結合(TXT/EPUB)を自動検出し、それ以外の場合はPDFフローを使用します。"},
    'novel_step1_convert_to_pdf': {'zh': "小说模式第一步：使用Calibre将所有源文件转换为PDF格式...", 'en': "Novel Mode Step 1: Converting all source files to PDF using Calibre...", 'ja': "小説モードステップ1：CalibreでPDFに変換..."}, 
    'novel_step1_skip_convert': {'zh': "小说模式第一步：检测到源文件已是PDF，跳过转换步骤。", 'en': "Novel Mode Step 1: Source files are already PDF, skipping conversion.", 'ja': "小説モードステップ1：PDFのため、変換をスキップ。"}, 
    'novel_step2_merge_pdf': {'zh': "小说模式第二步：合并所有PDF文件为一个临时文件...", 'en': "Novel Mode Step 2: Merging all PDF files into a single temporary file...", 'ja': "小説モードステップ2：PDFを一つに統合..."}, 
    'novel_step3_convert_to_epub': {'zh': "小说模式第三步：使用Calibre将合并后的PDF转换为临时EPUB...", 'en': "Novel Mode Step 3: Converting merged PDF to temporary EPUB using Calibre...", 'ja': "小説モードステップ3：統合PDFをEPUBに変換..."},
    'calibre_conversion_failed_drm': {'zh': "错误：文件 '{}' 转换失败。\n该文件可能有DRM保护，我们无法处理这个步骤，请获取到无DRM保护的版本！", 'en': "Error: Conversion failed for '{}'. The file may be DRM-protected.", 'ja': "エラー：'{}'の変換に失敗しました。DRM保護されている可能性があります。"},
    'pdf_merge_success': {'zh': "PDF合并完成，已生成 '{}'", 'en': "PDF merge complete: '{}'", 'ja': "PDF統合完了: '{}'"},
    'pdf_merge_fail': {'zh': "PDF合并失败: {}", 'en': "PDF merge failed: {}", 'ja': "PDF統合失敗: {}"},
    'prompt_confirm_path': {'zh': "您输入的路径是：'{}'\n确认无误吗？(y/n): ", 'en': "You entered path: '{}'\nIs this correct? (y/n): ", 'ja': "入力されたパスは「{}」です。\nよろしいですか？(y/n): "},
    'prompt_confirm_mode': {'zh': "您选择的处理模式是：{}模式。\n确认吗？(y/n): ", 'en': "You selected {} Mode.\nConfirm? (y/n): ", 'ja': "選択された処理モードは「{}」です。\nよろしいですか？(y/n): "},
    'prompt_confirm_format': {'zh': "您选择的最终输出格式是：{}。\n确认吗？(y/n): ", 'en': "You selected output format: {}.\nConfirm? (y/n): ", 'ja': "選択された出力形式は「{}」です。\nよろしいですか？(y/n): "},
    'prompt_confirm_output_name': {'zh': "输出文件的基础名称将是：'{}'\n确认吗？(y/n): ", 'en': "Output base name: '{}'\nConfirm? (y/n): ", 'ja': "出力ファイル名は「{}」です。\nよろしいですか？(y/n): "},
    'prompt_confirm_quality': {'zh': "图片质量设置为：{}。\n确认吗？(y/n): ", 'en': "Image quality: {}.\nConfirm? (y/n): ", 'ja': "画像品質は{}です。\nよろしいですか？(y/n): "},
    'prompt_remove_styling': {'zh': "是否移除原书的字体和颜色样式？(适合清除'精调'样式) (y = 是, n = 否): ", 'en': "Remove original fonts and colors? (Good for 'fine-tuned' styles) (y/n): ", 'ja': "元のフォントと色を削除しますか？（「微調整」されたスタイルに適しています） (y/n): "},
    'prompt_confirm_remove_styling': {'zh': "样式移除功能：{}。\n确认吗？(y/n): ", 'en': "Remove Styling: {}.\nConfirm? (y/n): ", 'ja': "スタイル削除：{}。\nよろしいですか？(y/n): "},
    'prompt_confirm_title': {'zh': "电子书标题将是：'{}'\n确认吗？(y/n): ", 'en': "Book title: '{}'\nConfirm? (y/n): ", 'ja': "本のタイトルは「{}」です。\nよろしいですか？(y/n): "},
    'prompt_confirm_workers': {'zh': "并行线程数设置为：{}。\n(注: 多线程可能会导致其他应用卡顿，若您后台正在运行一些比较重要的软件，请设定更小的线程数)\n确认吗？(y/n): ", 'en': "Number of workers: {}.\n(Note: Multi-threading may cause system lag. Set a lower number if running important background apps.)\nConfirm? (y/n): ", 'ja': "並列スレッド数は{}です。\n(注: マルチスレッドはシステムの遅延を引き起こす可能性があります。重要なバックグラウンドアプリを実行している場合は、より小さな数値を設定してください)\nよろしいですか？(y/n): "},
    'prompt_ask_scale': {
        'zh': "请输入PDF渲染缩放系数 (1.0=原大, 2.0=高清, 默认: 1.0)。\n(注: 系数越高，生成的电子书清晰度越高，但文件体积会成倍增长):\n> ",
        'en': "Enter PDF rendering scale factor (1.0=Original, 2.0=High-Def, Default: 1.0).\n(Note: Higher values increase clarity but significantly increase file size):\n> ",
        'ja': "PDFレンダリング倍率を入力してください (1.0=標準, 2.0=高画質, デフォルト: 1.0)。\n(注: 倍率が高いほど画質は向上しますが、ファイルサイズは劇的に増加します):\n> "
    },
    'prompt_confirm_scale': {'zh': "PDF渲染缩放系数设置为：{}。\n确认吗？(y/n): ", 'en': "PDF scale factor: {}.\nConfirm? (y/n): ", 'ja': "PDFレンダリング倍率は{}です。\nよろしいですか？(y/n): "},
    'prompt_ask_workers': {
        'zh': "请输入并行处理的线程数 (回车使用默认: {defaultWorkers})。\n(注: 多线程可能会导致其他应用卡顿，若您后台正在运行一些比较重要的软件，请设定更小的线程数):\n> ",
        'en': "Enter number of parallel workers (Enter for default: {defaultWorkers}).\n(Note: High concurrency may cause system lag. Reduce this if running critical background apps):\n> ",
        'ja': "並列処理のスレッド数を入力してください (Enterでデフォルト: {defaultWorkers})。\n(注: マルチスレッドはシステムの遅延を引き起こす可能性があります。重要なアプリを実行中の場合は減らしてください):\n> "
    },
    'starting_task': {'zh': "所有配置已确认。开始处理任务...", 'en': "All configurations confirmed. Starting task...", 'ja': "すべての設定が確認されました。タスクを開始します..."},
    'invalid_confirmation': {'zh': "无效确认，请重新输入。", 'en': "Invalid confirmation, please re-enter.", 'ja': "無効な入力です。もう一度入力してください。"},
    'comic_mode_name': {'zh': "漫画", 'en': "Comic", 'ja': "コミック"},
    'novel_mode_name': {'zh': "小说", 'en': "Novel", 'ja': "小説"},
    'calibre_conversion_timed': {'zh': "完成, 耗时 {:.1f} 秒。", 'en': "Done, took {:.1f}s.", 'ja': "完了、{:.1f}秒かかりました。"},
    'congratulations_complete': {'zh': "恭喜您完成了转换 '{}' 的流程，本次处理花费了 {:.1f} 秒，其中Calibre转换花费了 {:.1f} 秒。", 'en': "Congratulations! Processing for '{}' is complete. Total time: {:.1f}s, Calibre conversion time: {:.1f}s.", 'ja': "「{}」の変換が完了しました。総処理時間：{:.1f}秒、Calibre変換時間：{:.1f}秒。"},
    'prompt_file_summary': {
        'zh': "文件分析摘要:\n  - 共发现 {total_count} 个受支持的文件。\n  - 文件按数字顺序排列范围: {min_num}-{max_num}。\n  - 格式分布:\n{breakdown}\n  - 发现 {decimal_count} 个文件名中包含小数 (例如 '1.5.pdf')。",
        'en': "File Analysis Summary:\n  - Found {total_count} supported files in total.\n  - Files are numerically sorted from {min_num} to {max_num}.\n  - Format Distribution:\n{breakdown}\n  - Found {decimal_count} files with decimal numbers in their names (e.g., '1.5.pdf').",
        'ja': "ファイル分析概要:\n  - 合計{total_count}個のサポートされているファイルが見つかりました。\n  - ファイルは{min_num}から{max_num}まで数値順にソートされています。\n  - 形式の分布:\n{breakdown}\n  - 名前に小数を含むファイルが{decimal_count}個見つかりました（例: '1.5.pdf'）。"
    },
    'prompt_confirm_decimal_ignore': {
        'zh': "是否处理所有文件？ (y = 全部处理, n = 忽略带小数的文件): ",
        'en': "Process all files? (y = process all, n = ignore files with decimals): ",
        'ja': "すべてのファイルを処理しますか？ (y = すべて処理, n = 小数を含むファイルを無視): "
    },
    'calibre_conversion_error': {
        'zh': "错误：Calibre 转换失败。",
        'en': "Error: Calibre conversion failed.",
        'ja': "エラー：Calibre変換に失敗しました。"
    },
    'prompt_skip_failed_file': {
        'zh': "文件 '{}' 转换失败。请选择操作 (r = 重试, s = 跳过, a = 中止): ",
        'en': "Conversion failed for file '{}'. Choose an action (r = retry, s = skip, a = abort): ",
        'ja': "ファイル「{}」の转换に失败しました。アクションを選択してください (r = 再試行, s = スキップ, a = 中止): "
    },
    'prompt_specify_calibre_path': {'zh': "在您的系统中找不到Calibre。是否要指定一个自定义的Calibre安装路径? (y/n):", 'en': "Calibre not found on your system. Would you like to specify a custom path to your Calibre installation? (y/n):", 'ja': "システムにCalibreが見つかりません。カスタムのCalibreインストールパスを指定しますか？ (y/n):"},
    'prompt_enter_calibre_path': {'zh': "请输入您的Calibre安装文件夹的完整路径 (例如: C:\\Program Files\\Calibre2):", 'en': "Please enter the full path to your Calibre installation folder (e.g., C:\\Program Files\\Calibre2):", 'ja': "Calibreインストールフォルダへのフルパスを入力してください（例：C:\\Program Files\\Calibre2）："},
    'warn_custom_path_set': {'zh': "警告：指定自定义路径后，脚本将始终使用此路径，自动搜索功能将失效。如果与他人分享此脚本，他们可能需要修改此路径。\n路径已成功验证并保存。请重新启动脚本以使更改生效。", 'en': "Warning: After setting a custom path, the script will always use it, and the auto-search feature will be disabled. If you share this script, others may need to change this path.\nThe path has been successfully validated and saved. Please restart the script for the changes to take effect.", 'ja': "警告：カスタムパスを設定すると、スクリプトは常にこのパスを使用し、自動検索機能は無効になります。このスクリプトを他の人と共有する場合、彼らはこのパスを変更する必要があるかもしれません。\nパスは正常に検証され、保存されました。変更を有効にするためにスクリプトを再起動してください。"},
    'error_invalid_calibre_path': {'zh': "错误：提供的路径无效或在该路径下找不到Calibre工具 '{}'。请重试。", 'en': "Error: The provided path is invalid or the Calibre tool '{}' was not found in that path. Please try again.", 'ja': "エラー：指定されたパスが無効か、そのパスにCalibreツール「{}」が見つかりませんでした。再試行してください。"},
    'prompt_cover_auto': {'zh': "是否自动使用第一本书的第一张图片作为封面？ (y = 自动, n = 手动指定): ", 'en': "Use the first image of the first book as the cover? (y = Auto, n = Manual): ", 'ja': "最初の本の最初の画像をカバーとして使用しますか？ (y = 自動, n = 手動): "},
    'prompt_cover_path': {'zh': "请输入有效的封面图片路径:", 'en': "Please enter a valid path to the cover image:", 'ja': "有効なカバー画像のパスを入力してください:"},
    'prompt_cover_invalid': {'zh': "无法读取该图片或路径无效。是否使用简易封面(s) 或 重试路径(r)?", 'en': "Cannot read image or path invalid. Use simple cover (s) or Retry path (r)?", 'ja': "画像を読み取れないか、パスが無効です。簡易カバーを使用(s) または パスを再試行(r)?"},
    'cover_extract_fail': {'zh': "检测到第一张页面不是有效图片，无法自动设置。", 'en': "First page is not a valid image, cannot auto-set cover.", 'ja': "最初のページが有効な画像ではないため、自動設定できません。"},
    'smart_merge_txt_start': {'zh': "正在使用智能TXT合并...", 'en': "Starting Smart TXT Merge...", 'ja': "スマートTXT結合を開始しています..."},
    'smart_merge_epub_start': {'zh': "正在使用智能EPUB合并...", 'en': "Starting Smart EPUB Merge...", 'ja': "スマートEPUB結合を開始しています..."},
    'txt_decode_fail': {'zh': "警告：无法解码 '{}'", 'en': "Warning: Could not decode '{}'", 'ja': "警告：'{}' をデコードできませんでした"},
    'smart_merge_success': {'zh': "智能合并成功：'{}'", 'en': "Smart merge successful: '{}'", 'ja': "スマート結合に成功しました：'{}'"},
    'smart_merge_fail': {'zh': "智能合并失败：{}", 'en': "Smart merge failed: {}", 'ja': "スマート結合に失敗しました：{}"},
    'conversion_fail_single': {'zh': "转换失败 {}: {}", 'en': "Conversion failed {}: {}", 'ja': "変換に失敗しました {}: {}"},
    'dependency_check_title': {'zh': "\n--- 依赖库检查 (Dependency Check) ---", 'en': "\n--- Dependency Check ---", 'ja': "\n--- 依存関係チェック ---"},
    'separator': {'zh': "--------------------", 'en': "--------------------", 'ja': "--------------------"},
    'error_update_path_placeholder': {'zh': "错误：无法在脚本中找到更新路径的占位符。", 'en': "Error: Could not find the placeholder to update the path in the script.", 'ja': "エラー：スクリプト内でパスを更新するためのプレースホルダーが見つかりませんでした。"},
    'auto_download_windows_only': {'zh': "自动下载目前仅支持Windows系统。", 'en': "Automatic download is currently only supported for Windows.", 'ja': "自動ダウンロードは現在Windowsのみをサポートしています。"},
    'error_corrupt_file_skip': {'zh': "跳过损坏的文件 {}: {}", 'en': "Skipping corrupt file {}: {}", 'ja': "破損したファイル {}: {} をスキップしています"},
    'warning_no_images_cbz_epub': {'zh': "警告：EPUB中未找到图片。无法创建CBZ。", 'en': "Warning: No images found in the EPUB. Cannot create CBZ.", 'ja': "警告：EPUBに画像が見つかりません。CBZを作成できません。"},
    'warning_skip_image_error': {'zh': "由于处理错误，正在跳过一张图片: {}", 'en': "Skipping an image due to processing error: {}", 'ja': "処理エラーのため画像をスキップしています: {}"},
    'no_non_pdf_found': {'zh': "未找到需要转换的非PDF文件。", 'en': "No non-PDF files requiring conversion were found.", 'ja': "変換が必要な非PDFファイルは見つかりませんでした。"},
    'no_pdf_files_to_merge': {'zh': "未找到要合并的PDF文件。", 'en': "No PDF files found to merge.", 'ja': "結合するPDFファイルが見つかりませんでした。"},
    'output_path_display': {'zh': "所有文件将输出到 (All files will be output to): {}", 'en': "All files will be output to: {}", 'ja': "すべてのファイルは次に出力されます: {}"},
    'start_processing_folder': {'zh': "\n{}开始处理文件夹 (Processing folder): {}{}", 'en': "\n{}Starting processing for folder: {}{}", 'ja': "\n{}フォルダの処理を開始します: {}{}"},
    'comic_mode_major_type': {'zh': "漫画模式: 检测到主要文件类型为 '{}'", 'en': "Comic Mode: Detected primary file type as '{}'", 'ja': "コミックモード：主要なファイルタイプは '{}' です"},
    'info_css_filter_enabled': {'zh': "信息：CSS过滤已启用（移除字体和颜色）。", 'en': "Info: CSS Filtering enabled (removing fonts and colors).", 'ja': "情報：CSSフィルタリングが有効です（フォントと色を削除）。"},
    'pdf_to_epub_conversion_failed': {'zh': "\nPDF到EPUB转换失败: {}", 'en': "\nPDF to EPUB conversion failed: {}", 'ja': "\nPDFからEPUBへの変換に失敗しました: {}"},
    'creating_format_message': {'zh': "\n{}' 正在创建: {}.{} '{} {} {}", 'en': "\n{}' Creating: {}.{} '{} {} {}", 'ja': "\n{}' 作成中: {}.{} '{} {} {}"},
    'calibre_strip_styles_info': {'zh': "正在使用Calibre清理EPUB样式...", 'en': "Cleaning EPUB styles with Calibre...", 'ja': "CalibreでEPUBスタイルをクリーニング中..."},
    'calibre_strip_styles_fail': {'zh': "样式清理失败，保留原版: {}", 'en': "Style cleaning failed, keeping original: {}", 'ja': "スタイルクリーニングに失敗しました。元のファイルを保持します: {}"},
    'calibre_unavailable_skip_format': {'zh': "跳过 {}.{} 创建，因为Calibre不可用。", 'en': "Skipping {}.{} creation because Calibre is unavailable.", 'ja': "Calibreが利用できないため、{}.{} の作成をスキップします。"},
    'calibre_converting_temp_file': {'zh': "正在使用Calibre将临时文件转换为 {}.{}", 'en': "Converting temporary file to {}.{} with Calibre", 'ja': "Calibreを使用して一時ファイルを {}.{} に変換中"},
    'calibre_conversion_fail_generic': {'zh': "\nCalibre转换失败: {}", 'en': "\nCalibre conversion failed: {}", 'ja': "\nCalibre変換に失敗しました: {}"},
    'cleaning_temp_files': {'zh': "\n正在清理当前文件夹的临时文件和目录...", 'en': "\nCleaning temporary files and directories for current folder...", 'ja': "\n現在のフォルダの一時ファイルとディレクトリをクリーンアップ中..."},
    'deleted_temp_file': {'zh': "已删除临时文件: {}", 'en': "Deleted temporary file: {}", 'ja': "一時ファイルを削除しました: {}"},
    'deleted_temp_directory': {'zh': "已删除临时目录: {}", 'en': "Deleted temporary directory: {}", 'ja': "一時ディレクトリを削除しました: {}"},
    'all_folders_processed': {'zh': "\n{}所有指定的文件夹均已处理完毕。\nAll specified folders have been processed.\n{}", 'en': "\n{}All specified folders have been processed.\n{}", 'ja': "\n{}すべての指定されたフォルダの処理が完了しました。\n{}"},
    'interactive_mode_welcome': {'zh': "\n--- 欢迎进入交互模式 ---", 'en': "\n--- Welcome to Interactive Mode ---", 'ja': "\n--- 対話モードへようこそ ---"},
    'no_files_to_process_exit': {'zh': "没有要处理的文件。退出交互模式。", 'en': "No files to process. Exiting interactive mode.", 'ja': "処理するファイルがありません。対話モードを終了します。"},
    'prompt_output_base_name': {'zh': "请输入输出文件的基础名称 (回车使用默认: '{}'):\n> ", 'en': "Please enter the base name for the output file (Enter for default: '{}'):\n> ", 'ja': "出力ファイルのベース名を入力してください (Enterでデフォルト: '{}'):\n> "},
    'prompt_image_quality': {'zh': "请输入图片质量 (1-100, 回车使用默认: {}):\n> ", 'en': "Please enter image quality (1-100, Enter for default: {}):\n> ", 'ja': "画像品質を入力してください (1-100, Enterでデフォルト: {}):\n> "},
    'prompt_book_title': {'zh': "请输入电子书标题 (回车使用默认: '{}'):\n> ", 'en': "Please enter the book title (Enter for default: '{}'):\n> ", 'ja': "電子書籍のタイトルを入力してください (Enterでデフォルト: '{}'):\n> "},
    'cleaned_temp_dir': {'zh': "已清理临时处理文件夹: {}", 'en': "Cleaned temporary processing folder: {}", 'ja': "一時処理フォルダをクリーンアップしました: {}"},
    'prompt_language_menu_title': {'zh': "\n请选择语言 (Select Language):", 'en': "\nPlease select a language:", 'ja': "\n言語を選択してください:"},
    'prompt_language_chinese': {'zh': "1) 中文 (Chinese)", 'en': "1) Chinese", 'ja': "1) 中国語"},
    'prompt_language_english': {'zh': "2) English", 'en': "2) English", 'ja': "2) 英語"},
    'prompt_language_japanese': {'zh': "3) 日本語 (Japanese)", 'en': "3) Japanese", 'ja': "3) 日本語"},
    'error_arg_parse': {'zh': "参数错误 (Argument Error): {}", 'en': "Argument Error: {}", 'ja': "引数エラー: {}"},
    'error_parsing_arguments': {'zh': "解析参数时出错。", 'en': "Error parsing arguments.", 'ja': "引数を解析中にエラーが発生しました。"},
    'smart_merger_author': {'zh': "智能合并器", 'en': "Smart Merger", 'ja': "スマートマージャー"},
    'error_generic': {'zh': "错误: {}", 'en': "Error: {}", 'ja': "エラー: {}"},
    'prompt_batch_enable': {
        'zh': "是否启动批处理模式？（有效控制内存占用，对内存较少的电脑更友好，但可能会略微增加一些处理时间）(y/n): ",
        'en': "Enable batch processing mode? (Reduces memory usage, good for low-RAM systems, but may slightly increase processing time) (y/n): ",
        'ja': "バッチ処理モードを有効にしますか？（メモリ使用量を抑えます。低メモリPCに適していますが、処理時間がわずかに长くなる可能性があります）(y/n): "
    },
    'prompt_batch_count': {
        'zh': "请设置批次大小 (分批数量): ",
        'en': "Please set the batch count (number of batches): ",
        'ja': "バッチサイズ（バッチ数）を設定してください: "
    },
    'batch_processing_info': {
        'zh': "正在处理第 {}/{} 批 (本批包含 {} 个文件)...",
        'en': "Processing batch {}/{} ({} files)...",
        'ja': "バッチ {}/{} を処理中 ({} ファイル)..."
    },
    'pre_convert_notice': {
        'zh': "检测到 {} 个非EPUB文件需要预转换为EPUB...",
        'en': "Detected {} non-EPUB files requiring pre-conversion to EPUB...",
        'ja': "{}個の非EPUBファイルがEPUBへの事前変換を必要とします..."
    },
    'pre_convert_progress': {
        'zh': "预转换中...",
        'en': "Pre-converting...",
        'ja': "事前変換中..."
    },
    'calibre_missing_pre_convert': {
        'zh': "警告：Calibre命令行工具未找到，将跳过非EPUB文件的预转换。",
        'en': "Warning: Calibre command-line tools not found, skipping pre-conversion of non-EPUB files.",
        'ja': "警告：Calibreコマンドラインツールが見つかりません。非EPUBファイルの事前変換をスキップします。"
    },
    'pre_convert_error': {
        'zh': "预转换过程中发生错误: {}",
        'en': "An error occurred during pre-conversion: {}",
        'ja': "事前変換中にエラーが発生しました: {}"
    },
    'smart_merge_epub_fail_fallback': {
        'zh': "智能EPUB合并失败，将尝试回退到通用PDF处理流程。",
        'en': "Smart EPUB merge failed, attempting to fall back to general PDF processing flow.",
        'ja': "スマートEPUB結合に失敗しました。一般的なPDF処理フローへのフォールバックを試みます。"
    },
    'crawler_tip': {
        'zh': "\n提示：如果您需要下载在线漫画，建议您尝试使用我们的自动化漫画爬虫脚本（Coming Soon）：\n  https://github.com/ShadowLoveElysia/Automated-Comic-Crawler",
        'en': "\nTip: If you need to download online comics, we suggest trying our automated comic crawler script (Coming Soon):\n  https://github.com/ShadowLoveElysia/Automated-Comic-Crawler",
        'ja': "\nヒント：オンライン漫画をダウンロードする必要がある場合は、自動漫画クローラスクリプト（近日公開）をお試しください：\n  https://github.com/ShadowLoveElysia/Automated-Comic-Crawler"
    }
}

def getSakuraConfigPath():
    try:
        script_dir = os.path.dirname(__file__)
    except NameError:
        script_dir = os.getcwd()
    return os.path.join(script_dir, "config.json")

def loadSakuraConfig():
    try:
        configPath = getSakuraConfigPath()
        if os.path.exists(configPath):
            with open(configPath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception: pass
    return {}

def saveSakuraConfig(key, value):
    config = loadSakuraConfig()
    config[key] = value
    try:
        with open(getSakuraConfigPath(), 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception: pass

def checkDependencies():
    global elysiaFitz, edenImage, griseoEpub, mobiusEbookLib, kevinConcurrent, aponiaRequests, villVTqdm, kalpasNatsort
    missingPardofelisDeps = []
    
    huaDependencies = [
        ('PyMuPDF', 'PyMuPDF', 'import fitz'),
        ('Pillow', 'Pillow', 'from PIL import Image'),
        ('EbookLib', 'EbookLib', 'import ebooklib; from ebooklib import epub'),
        ('requests', 'requests', 'import requests'),
        ('tqdm', 'tqdm', 'from tqdm import tqdm'),
        ('natsort', 'natsort', 'import natsort')
    ]

    for displayName, installName, importCommand in huaDependencies:
        try:
            exec(importCommand, globals())
        except ImportError:
            missingPardofelisDeps.append((displayName, installName))

    if missingPardofelisDeps:
        print("\n--- 依赖库检查 (Dependency Check) ---")
        for displayName, installName in missingPardofelisDeps:
            print(STRINGS['dep_missing_tip']['en'].format(displayName, installName))
            print(STRINGS['dep_missing_tip']['zh'].format(displayName, installName))
            print(STRINGS['dep_missing_tip']['ja'].format(displayName, installName))
            print("-" * 20)
        print(STRINGS['dep_reboot_tip']['en'])
        print(STRINGS['dep_reboot_tip']['zh'])
        print(STRINGS['dep_reboot_tip']['ja'])
        sys.exit(1)
    
    import concurrent.futures
    
    elysiaFitz = globals().get('fitz')
    edenImage = globals().get('Image')
    griseoEpub = globals().get('epub')
    mobiusEbookLib = globals().get('ebooklib')
    kevinConcurrent = concurrent.futures
    aponiaRequests = globals().get('requests')
    villVTqdm = globals().get('tqdm')
    kalpasNatsort = globals().get('natsort')

def getLatestCalibrePortableUrl(languageCode):
    return "https://download.calibre-ebook.com/8.9.0/calibre-portable-installer-8.9.0.exe"

def getCalibreToolPath(toolName):
    config = loadSakuraConfig()
    custom_path = config.get('calibre_path')
    if custom_path and os.path.isdir(custom_path):
        custom_tool_path = os.path.join(custom_path, toolName)
        if os.path.exists(custom_tool_path):
            return custom_tool_path

    try:
        script_dir = os.path.dirname(__file__)
    except NameError:
        script_dir = os.getcwd()

    if platform.system() == "Windows":
        portableBaseLibraryPath = os.path.join(script_dir, 'lib', 'Calibre Portable')
        possiblePaths = [
            os.path.join(portableBaseLibraryPath, 'Calibre Portable', 'app', toolName),
            os.path.join(portableBaseLibraryPath, 'app', toolName),
            os.path.join(portableBaseLibraryPath, 'Calibre Portable', toolName),
            os.path.join(portableBaseLibraryPath, toolName)
        ]
        for path in possiblePaths:
            if os.path.exists(path): return path

        systemPaths = [
            os.path.join("C:\\Program Files\\Calibre2", toolName),
            os.path.join("C:\\Program Files\\Calibre", toolName)
        ]
        for path in systemPaths:
            if os.path.exists(path): return path
    else:
        whichCommand = shutil.which
        if whichCommand(toolName): return whichCommand(toolName)
    return None

def downloadCalibre(languageCode):
    mobiusDownloadUrl = getLatestCalibrePortableUrl(languageCode)
    if not mobiusDownloadUrl: return None
    try:
        script_dir = os.path.dirname(__file__)
    except NameError:
        script_dir = os.getcwd()
    installerPath = os.path.join(script_dir, "calibre_portable_installer.exe")
    try:
        print(STRINGS['calibre_downloading'][languageCode])
        aponiaResponse = aponiaRequests.get(mobiusDownloadUrl, stream=True)
        aponiaResponse.raise_for_status()
        totalSize = int(aponiaResponse.headers.get('content-length', 0))
        with open(installerPath, 'wb') as localFile, villVTqdm(total=totalSize, unit='iB', unit_scale=True, unit_divisor=1024) as progressBar:
            for dataChunk in aponiaResponse.iter_content(chunk_size=1024):
                progressBar.update(localFile.write(dataChunk))
        return installerPath
    except aponiaRequests.exceptions.RequestException as requestError:
        print(f"\n{STRINGS['calibre_download_failed'][languageCode]}: {requestError}")
        return None

def setupCalibreLocally(languageCode):
    installerPath = downloadCalibre(languageCode)
    if not installerPath: return False
    try:
        script_dir = os.path.dirname(__file__)
    except NameError:
        script_dir = os.getcwd()
    installDirectory = os.path.join(script_dir, 'lib', 'Calibre Portable')
    os.makedirs(installDirectory, exist_ok=True)
    print(STRINGS['calibre_extracting'][languageCode].format(installDirectory))
    command = [installerPath, '/S', f'/D={installDirectory}']
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        if getCalibreToolPath('ebook-convert.exe'):
            print(STRINGS['calibre_ready'][languageCode])
            return True
        else:
            print(STRINGS['calibre_install_failed'][languageCode])
            return False
    except subprocess.CalledProcessError as processError:
        print(f"{STRINGS['calibre_install_failed'][languageCode]}: {processError.stderr if hasattr(processError, 'stderr') else processError}")
        return False
    except Exception as error:
        print(STRINGS['error_generic'][languageCode].format(error))
        return False
    finally:
        if os.path.exists(installerPath): os.remove(installerPath)

def ensureCalibreTool(toolName, languageCode, isInteractive=True):
    toolPath = getCalibreToolPath(toolName)
    if toolPath:
        if isInteractive: print(STRINGS['calibre_ready'][languageCode])
        return toolPath
    
    if isInteractive:
        print(STRINGS['calibre_needed'][languageCode])
        while True:
            userChoice = input(STRINGS['prompt_specify_calibre_path'][languageCode]).strip().lower()
            if userChoice in ['y', 'yes']:
                customPath = input(STRINGS['prompt_enter_calibre_path'][languageCode]).strip().replace('"', '')
                if os.path.isdir(customPath) and os.path.exists(os.path.join(customPath, toolName)):
                    saveSakuraConfig('calibre_path', customPath)
                    print(STRINGS['warn_custom_path_set'][languageCode])
                    return os.path.join(customPath, toolName)
                else:
                    print(STRINGS['error_invalid_calibre_path'][languageCode].format(toolName))
            elif userChoice in ['n', 'no']: break
            else: print(STRINGS['error_invalid_choice'][languageCode])

        print(STRINGS['calibre_tool_missing_specific'][languageCode].format(toolName))
        while True:
            print(STRINGS['prompt_calibre_download'][languageCode])
            userChoice = input("> ").strip()
            if userChoice == '2':
                print(STRINGS['calibre_manual_prompt'][languageCode])
                webbrowser.open("https://calibre-ebook.com/download")
                return None
            elif userChoice == '1':
                if platform.system() != "Windows":
                    print(STRINGS['auto_download_windows_only'][languageCode])
                    return None
                setupSuccess = setupCalibreLocally(languageCode)
                return getCalibreToolPath(toolName) if setupSuccess else None
            else: print(STRINGS['error_invalid_choice'][languageCode])
    else:
        print(STRINGS['calibre_needed_param_mode'][languageCode])
        return None

def processPageWorker(workerArguments):
    pageIndex, filePath, pageNumber, imageQuality, scale = workerArguments
    import fitz as elysiaFitz
    from PIL import Image as edenImage
    doc = None
    try:
        doc = elysiaFitz.open(filePath)
        pageObject = doc.load_page(pageNumber)
        # 使用动态缩放系数
        pix = pageObject.get_pixmap(matrix=elysiaFitz.Matrix(scale, scale))
        imageData = pix.tobytes("png")
        pillowImage = edenImage.open(io.BytesIO(imageData))
        if pillowImage.mode in ("RGBA", "P"): pillowImage = pillowImage.convert("RGB")
        byteBuffer = io.BytesIO()
        pillowImage.save(byteBuffer, format="JPEG", quality=imageQuality, optimize=True)
        return {'index': pageIndex, 'data': byteBuffer.getvalue()}
    except Exception as error: return {'index': pageIndex, 'error': str(error)}
    finally:
        if doc: doc.close()

def processImageWorker(workerArguments):
    pageIndex, imagePath, imageQuality = workerArguments
    from PIL import Image as edenImage
    import io
    try:
        imageObject = edenImage.open(imagePath)
        if imageObject.mode in ("P", "RGBA"): imageObject = imageObject.convert("RGB")
        imageBuffer = io.BytesIO()
        imageObject.save(imageBuffer, format="JPEG", quality=imageQuality, optimize=True)
        return {'index': pageIndex, 'data': imageBuffer.getvalue()}
    except Exception as error:
        return {'index': pageIndex, 'error': str(error)}

def processPdfBatchWorker(workerArguments):
    filePath, pages, quality, startIndexBase, imageFormat, scale = workerArguments
    import fitz as elysiaFitz
    from PIL import Image as edenImage
    results = []
    doc = None
    try:
        doc = elysiaFitz.open(filePath)
        for i, pageNum in enumerate(pages):
            globalIndex = startIndexBase + i
            try:
                pageObject = doc.load_page(pageNum)
                # 使用动态缩放系数
                pix = pageObject.get_pixmap(matrix=elysiaFitz.Matrix(scale, scale))
                imageData = pix.tobytes("png")
                
                pillowImage = edenImage.open(io.BytesIO(imageData))
                if pillowImage.mode in ("RGBA", "P"): pillowImage = pillowImage.convert("RGB")
                byteBuffer = io.BytesIO()
                pillowImage.save(byteBuffer, format=imageFormat.upper(), quality=quality, optimize=(imageFormat=='jpeg'))
                results.append({'index': globalIndex, 'data': byteBuffer.getvalue()})
            except Exception as e:
                results.append({'index': globalIndex, 'error': str(e)})
    except Exception as e:
        for i in range(len(pages)):
             results.append({'index': startIndexBase + i, 'error': str(e)})
    finally:
        if doc: doc.close()
    return results

def processZipImageWorker(workerArguments):
    pageIndex, zipPath, internalPath, imageQuality, imageFormat = workerArguments
    from PIL import Image as edenImage
    import zipfile
    import io
    try:
        with zipfile.ZipFile(zipPath, 'r') as z:
            imageData = z.read(internalPath)
        imageObject = edenImage.open(io.BytesIO(imageData))
        if imageObject.mode in ("P", "RGBA"): imageObject = imageObject.convert("RGB")
        imageBuffer = io.BytesIO()
        imageObject.save(imageBuffer, format=imageFormat.upper(), quality=imageQuality, optimize=(imageFormat=='jpeg'))
        return {'index': pageIndex, 'data': imageBuffer.getvalue()}
    except Exception as error:
        return {'index': pageIndex, 'error': str(error)}

def executeAndWriteImageEpub(outputFilePath, bookTitle, languageCode, workerCount, tasks, workerFunc, totalItems, coverPath, firstPageData=None, chapterInfo=None, suppress_copyright=False):
    if not tasks:
        raise FileNotFoundError(STRINGS['error_no_files'][languageCode].format("Source", 'images'))
    
    print(STRINGS['preparing_pages'][languageCode].format(totalItems))
    
    griseoEpubBook = griseoEpub.EpubBook()
    griseoEpubBook.set_identifier(f'id_{os.path.basename(outputFilePath)}')
    griseoEpubBook.set_title(bookTitle)
    griseoEpubBook.set_language(languageCode)
    griseoEpubBook.add_author('File Converter')
    if not suppress_copyright:
        griseoEpubBook.add_metadata('DC', 'description', "本电子书使用https://github.com/ShadowLoveElysia/Bulk-Ebook-Merger-Converter项目进行辅助合成/处理，本项目完全开源免费，若您是付费获取的此电子书/软件，请向平台举报！")
    
    styleSheet = griseoEpub.EpubItem(uid="main_style", file_name="style/main.css", media_type="text/css", content='body{text-align:center;}img{max-width:100%;height:auto;}')
    griseoEpubBook.add_item(styleSheet)
    griseoEpubBook.spine = ['nav']
    
    processedResults, nextToWriteIndex = {}, 0
    runningFutures = set()
    tasksIter = iter(tasks)

    with kevinConcurrent.ProcessPoolExecutor(max_workers=workerCount) as executor:
        for _ in range(min(workerCount * 2, len(tasks))):
            try:
                task = next(tasksIter)
                future = executor.submit(workerFunc, task)
                runningFutures.add(future)
            except StopIteration: break

        with villVTqdm(total=totalItems, desc=STRINGS['processing_and_writing'][languageCode].format(workerCount, '','')) as pbar:
            while runningFutures:
                finishedFutures, pendingFutures = kevinConcurrent.wait(runningFutures, return_when=kevinConcurrent.FIRST_COMPLETED)
                runningFutures = pendingFutures
                
                for future in finishedFutures:
                    res = future.result()
                    resultsList = res if isinstance(res, list) else [res]
                    
                    for result in resultsList:
                        pbar.update(1)
                        processedResults[result['index']] = result
                        if result['index'] == 0 and not result.get('error') and result.get('data'):
                            firstPageData = result['data']

                        try:
                            nextTask = next(tasksIter)
                            newFuture = executor.submit(workerFunc, nextTask)
                            runningFutures.add(newFuture)
                        except StopIteration: pass

                        while nextToWriteIndex in processedResults:
                            currentResult = processedResults.pop(nextToWriteIndex)
                            if 'error' not in currentResult and currentResult['data']:
                                index, data = currentResult['index'], currentResult['data']
                                
                                ext = 'jpeg' 
                                mediaType = f"image/{ext}"
                                imageFileName = f"images/img_{index+1:04d}.{ext}"
                                chapterTitle = f"Page {index+1}"
                                
                                epubImageItem = griseoEpub.EpubItem(uid=f"img_{index+1}", file_name=imageFileName, media_type=mediaType, content=data)
                                griseoEpubBook.add_item(epubImageItem)
                                
                                chapterFileName = f"pages/p_{index+1:04d}.xhtml"
                                epubHtmlChapter = griseoEpub.EpubHtml(title=chapterTitle, file_name=chapterFileName, lang=languageCode)
                                epubHtmlChapter.content = f'<!DOCTYPE html><html><head><title>{chapterTitle}</title><link rel="stylesheet" type="text/css" href="../style/main.css" /></head><body><div><img src="../{imageFileName}" alt="{chapterTitle}"/></div></body></html>'
                                griseoEpubBook.add_item(epubHtmlChapter)
                                griseoEpubBook.spine.append(epubHtmlChapter)
                            nextToWriteIndex += 1
                            if nextToWriteIndex % 20 == 0: gc.collect()

    if coverPath == 'auto' and firstPageData:
        griseoEpubBook.set_cover("cover.jpg", firstPageData)
    elif coverPath and coverPath != 'auto' and os.path.exists(coverPath):
        try:
            with open(coverPath, 'rb') as f: griseoEpubBook.set_cover("cover.jpg", f.read())
        except Exception: pass

    print(STRINGS['finalizing_file'][languageCode])
    
    tocLinks = []
    if chapterInfo:
        for startIndex, title in chapterInfo:
            finalIndex = startIndex
            if finalIndex >= 0:
                chapterFileName = f"pages/p_{finalIndex+1:04d}.xhtml"
                tocLinks.append(griseoEpub.Link(chapterFileName, title, f"chap_{finalIndex+1}"))
            
    griseoEpubBook.toc = tocLinks
    griseoEpubBook.add_item(griseoEpub.EpubNcx())
    griseoEpubBook.add_item(griseoEpub.EpubNav())
    griseoEpub.write_epub(outputFilePath, griseoEpubBook, {})
    print(STRINGS['consolidation_complete'][languageCode])

def convertPdfsToEpub(sourceDirectory, outputFilePath, imageQuality, bookTitle, languageCode, workerCount, coverPath=None, imageFormat='jpeg', input_files=None, scale=1.0, suppress_copyright=False):
    if input_files:
        print(STRINGS['consolidating'][languageCode].format(len(input_files), 'PDF'))
        pdfFiles = input_files
    else:
        print(STRINGS['consolidating'][languageCode].format(len(os.listdir(sourceDirectory)), 'PDF'))
        pdfFiles = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith('.pdf')])
    
    tasks, pageCounter = [], 0
    chapterInfo = [] 
    BATCH_SIZE = 10 

    for path in pdfFiles:
        baseName = os.path.splitext(os.path.basename(path))[0]
        numMatch = re.search(r"(\d+(?:\.\d+)?)", baseName)
        
        sideKeywords = ['番外', 'extra', 'omake', 'side story', 'sp', 'special']
        isSideStory = any(k in baseName.lower() for k in sideKeywords)

        if languageCode == 'ja': prefix, suffix, extraTag = "第", "话", "[番外編]"
        elif languageCode == 'en': prefix, suffix, extraTag = "Chapter ", "", "[Extra] "
        else: prefix, suffix, extraTag = "第", "话", "[番外]"

        if isSideStory: title = f"{extraTag}{prefix}{numMatch.group(1)}{suffix}" if numMatch else f"{extraTag}{baseName}"
        else: title = f"{prefix}{numMatch.group(1)}{suffix}" if numMatch else baseName
        
        startIndex = pageCounter
        try:
            with elysiaFitz.open(path) as doc:
                pageCount = len(doc)
                if pageCount > 0:
                     chapterInfo.append((startIndex, title))
                     for i in range(0, pageCount, BATCH_SIZE):
                        chunk = range(i, min(i + BATCH_SIZE, pageCount))
                        tasks.append((path, chunk, imageQuality, pageCounter, imageFormat, scale))
                        pageCounter += len(chunk)
        except Exception as error: 
            print(STRINGS['error_corrupt_file_skip'][languageCode].format(path, error))
            
    executeAndWriteImageEpub(outputFilePath, bookTitle, languageCode, workerCount, tasks, processPdfBatchWorker, pageCounter, coverPath, chapterInfo=chapterInfo, suppress_copyright=suppress_copyright)

def convertCbzsToEpub(sourceDirectory, outputFilePath, imageQuality, bookTitle, languageCode, workerCount, coverPath=None, imageFormat='jpeg', input_files=None, suppress_copyright=False):
    if input_files:
        print(STRINGS['consolidating'][languageCode].format(len(input_files), 'CBZ/CBR'))
        cbzFiles = input_files
    else:
        print(STRINGS['consolidating'][languageCode].format(len(os.listdir(sourceDirectory)), 'CBZ/CBR'))
        cbzFiles = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith(('.cbz', '.cbr'))])
    
    tasks = []
    chapterInfo = [] 
    currentIndex = 0
    
    for cbzPath in cbzFiles:
        baseName = os.path.splitext(os.path.basename(cbzPath))[0]
        numMatch = re.search(r"(\d+(?:\.\d+)?)", baseName)
        sideKeywords = ['番外', 'extra', 'omake', 'side story', 'sp', 'special']
        isSideStory = any(k in baseName.lower() for k in sideKeywords)

        if languageCode == 'ja': prefix, suffix, extraTag = "第", "话", "[番外編]"
        elif languageCode == 'en': prefix, suffix, extraTag = "Chapter ", "", "[Extra] "
        else: prefix, suffix, extraTag = "第", "话", "[番外]"

        if isSideStory: title = f"{extraTag}{prefix}{numMatch.group(1)}{suffix}" if numMatch else f"{extraTag}{baseName}"
        else: title = f"{prefix}{numMatch.group(1)}{suffix}" if numMatch else baseName
        
        try:
            with zipfile.ZipFile(cbzPath, 'r') as zipFileHandle:
                imagesInZip = kalpasNatsort.natsorted([f for f in zipFileHandle.namelist() if f.lower().endswith(('jpg', 'jpeg', 'png', 'webp'))])
                if imagesInZip:
                    chapterInfo.append((currentIndex, title))
                    for imgName in imagesInZip:
                        tasks.append((currentIndex, cbzPath, imgName, imageQuality, imageFormat))
                        currentIndex += 1
        except zipfile.BadZipFile: pass
    
    executeAndWriteImageEpub(outputFilePath, bookTitle, languageCode, workerCount, tasks, processZipImageWorker, currentIndex, coverPath, chapterInfo=chapterInfo, suppress_copyright=suppress_copyright)

def mergeEpubsWithCalibre(sourceDirectory, outputFilePath, bookTitle, languageCode, coverPath=None, calibre_extra_args=None, input_files=None):
    print(STRINGS['epub_merge_notice_calibre'][languageCode])
    calibreExecutable = ensureCalibreTool('ebook-convert.exe', languageCode, isInteractive=True)
    if not calibreExecutable: return False, 0, False

    if input_files: epubFiles = input_files
    else: epubFiles = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith('.epub')])
    if not epubFiles: raise FileNotFoundError(STRINGS['error_no_files'][languageCode].format(sourceDirectory, 'EPUB'))
    
    print(f"{STRINGS['consolidating'][languageCode].format(len(epubFiles), 'EPUB')}... ", end="", flush=True)

    command = [calibreExecutable] + epubFiles + [outputFilePath]
    if bookTitle: command.extend(['--title', bookTitle])
    
    if coverPath and coverPath != 'auto' and os.path.exists(coverPath):
         command.extend(['--cover', coverPath])
    elif coverPath == 'auto':
        first_epub_cover_data = extractCoverFromFirstFile(sourceDirectory)
        if first_epub_cover_data:
            cover_file_path = os.path.join(os.path.dirname(outputFilePath), "temp_cover.jpg")
            try:
                with open(cover_file_path, "wb") as f: f.write(first_epub_cover_data)
                command.extend(['--cover', cover_file_path])
            except: pass

    if calibre_extra_args: command.extend(calibre_extra_args)

    start_time = time.time()
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        duration = time.time() - start_time
        print(STRINGS['calibre_conversion_timed'][languageCode].format(duration))
        print(STRINGS['consolidation_complete'][languageCode])
        return True, duration, bool(calibre_extra_args)
    except subprocess.CalledProcessError as processError: 
        print(f"\n{STRINGS['epub_merge_fail_calibre'][languageCode]}: {processError.stderr if hasattr(processError, 'stderr') else processError}")
        return False, 0, False
    except Exception as error: 
        print(f"\n{STRINGS['epub_merge_fail_calibre'][languageCode]}: {error}")
        return False, 0, False
    finally:
        if 'cover_file_path' in locals() and os.path.exists(cover_file_path): os.remove(cover_file_path)

def FilesToPdf(sourceDirectory, outputDirectory, languageCode, isInteractive, input_files=None):
    print(STRINGS['novel_step1_convert_to_pdf'][languageCode])
    calibreExecutable = ensureCalibreTool('ebook-convert.exe', languageCode, isInteractive)
    if not calibreExecutable: return False, 0

    supportedExtensions = ('.epub', '.mobi', '.azw3', '.docx', '.txt', '.kepub', '.fb2', 
                             '.lit', '.lrf', '.pdb', '.pmlz', '.rb', '.rtf', '.tcr', 
                             '.txtz', '.htmlz')
    
    if input_files: sourceFiles = input_files
    else: sourceFiles = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith(supportedExtensions)])

    if not sourceFiles:
        print(STRINGS['no_non_pdf_found'][languageCode])
        return True, 0

    os.makedirs(outputDirectory, exist_ok=True)
    total_duration = 0
    files_to_process = list(sourceFiles) 

    with villVTqdm(total=len(files_to_process), desc="Converting to PDF") as pbar:
        for sourceFile in files_to_process:
            conversion_successful = False
            while not conversion_successful:
                baseName = os.path.splitext(os.path.basename(sourceFile))[0]
                outputFile = os.path.join(outputDirectory, f"{baseName}.pdf")
                command = [calibreExecutable, sourceFile, outputFile]
                start_time = time.time()
                try:
                    subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
                    total_duration += time.time() - start_time
                    conversion_successful = True
                except subprocess.CalledProcessError as processError:
                    pbar.write(f"\n{STRINGS['calibre_conversion_error'][languageCode]}")
                    pbar.write(f"Calibre Error: {processError.stderr}")
                    if isInteractive:
                        while True:
                            user_choice = input(STRINGS['prompt_skip_failed_file'][languageCode].format(os.path.basename(sourceFile))).strip().lower()
                            if user_choice in ['r', 'retry']:
                                pbar.write("Retrying conversion...")
                                break 
                            elif user_choice in ['s', 'skip', 'y', 'yes']:
                                conversion_successful = True
                                break
                            elif user_choice in ['a', 'abort', 'n', 'no']:
                                return False, total_duration
                            else: pbar.write(STRINGS['error_invalid_choice'][languageCode])
                        if user_choice in ['r', 'retry']: continue 
                        else: break 
                    else: return False, total_duration
            pbar.update(1)
    return True, total_duration

def mergePdfs(sourceDirectory, outputFilePath, languageCode, input_files=None):
    print(STRINGS['novel_step2_merge_pdf'][languageCode])
    if input_files: pdfFiles = input_files
    else: pdfFiles = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith('.pdf')])
    if not pdfFiles:
        print(STRINGS['no_pdf_files_to_merge'][languageCode])
        return False
    try:
        mergedDoc = elysiaFitz.open()
        for path in villVTqdm(pdfFiles, desc="Merging PDFs"):
            with elysiaFitz.open(path) as doc: mergedDoc.insert_pdf(doc)
        mergedDoc.save(outputFilePath)
        mergedDoc.close()
        print(STRINGS['pdf_merge_success'][languageCode].format(outputFilePath))
        return True
    except Exception as error: 
        print(STRINGS['pdf_merge_fail'][languageCode].format(error))
        return False

def convertEpubToCbz(sourceFile, outputFilePath, imageQuality, languageCode, imageFormat='jpeg'):
    print(STRINGS['creating_cbz'][languageCode])
    readEpubBook = griseoEpub.read_epub(sourceFile)
    imageList = []
    
    for item in readEpubBook.get_items():
        if item.get_type() == mobiusEbookLib.ITEM_IMAGE: imageList.append(item.get_content())

    if not imageList:
        print(STRINGS['warning_no_images_cbz_epub'][languageCode])
        return

    print(STRINGS['preparing_pages'][languageCode].format(len(imageList)))
    with zipfile.ZipFile(outputFilePath, 'w', zipfile.ZIP_DEFLATED) as zipFileHandle:
        with villVTqdm(total=len(imageList), desc=STRINGS['processing_and_writing'][languageCode].format(1, '', '')) as pbar:
            for index, imageData in enumerate(imageList):
                pbar.update(1)
                try:
                    imageObject = edenImage.open(io.BytesIO(imageData))
                    if imageObject.mode in ("P", "RGBA"): imageObject = imageObject.convert("RGB")
                    imageBuffer = io.BytesIO()
                    imageObject.save(imageBuffer, format=imageFormat.upper(), quality=imageQuality, optimize=(imageFormat=='jpeg'))
                    zipFileHandle.writestr(f"page_{index:04d}.{imageFormat}", imageBuffer.getvalue())
                except Exception as error: 
                    print(STRINGS['warning_skip_image_error'][languageCode].format(error))
    print(STRINGS['finalizing_file'][languageCode])
    print(STRINGS['task_complete'][languageCode].format(outputFilePath))

class MyHelpFormatter(argparse.HelpFormatter):
    def format_help(self):
        helpText = super().format_help()
        programName = self._prog
        exampleUsageText = f"""
-------------------------------------------------------------------
用法示例 (中文):
  # [交互模式] 不带参数运行即可进入交互菜单
  python {programName}

  # [漫画模式] 将 \"C:\\MyScans\" 中的PDF转为图片优先的EPUB和PDF
  python {programName} -p \"C:\\MyScans\" -f pdf --mode comic
  
  # [小说模式] 将 \"D:\\Novels\" 中的EPUB文件(文本优先)整合并创建MOBI
  python {programName} -p \"D:\\Novels\" -f mobi -o \"MyNovel\" --mode novel

  # [智能合并] \"D:\\Book\" 包含多个txt/epub章节，自动识别并合并
  python {programName} -p \"D:\\Book\" -f epub --mode novel

  # [多文件夹模式] 分别处理 \"C:\\A\" 和 \"D:\\B\"，并将结果都保存到 \"E:\\Output\"
  python {programName} -p \"C:\\A\" \"D:\\B\" -f epub --mode novel -op \"E:\\Output\"

  # 使用数字选择格式, 将 \"C:\\Comics\" 转为 KEPUB
  python {programName} -p \"C:\\Comics\" -f 8 --mode comic
-------------------------------------------------------------------"""
        return helpText + exampleUsageText

def createArgumentParser():
    griseoParser = argparse.ArgumentParser(description="批量将文件夹内的文档转换为各种电子书格式。", formatter_class=MyHelpFormatter, add_help=False)
    requiredGroup = griseoParser.add_argument_group('必要参数')
    optionalGroup = griseoParser.add_argument_group('可选参数')
    
    validFormatInputs = ALL_FORMAT_VALUES + list(FORMAT_CHOICE_MAP.keys())

    requiredGroup.add_argument('-p', '--path', type=str, required=True, nargs='+', help="一个或多个包含源文件(PDF, CBZ, EPUB等)的输入文件夹路径。")
    requiredGroup.add_argument('-f', '--format', type=str, required=True, choices=validFormatInputs, help="目标输出格式。可以是格式名(如 epub)或菜单数字(如 1)。")
    requiredGroup.add_argument('-m', '--mode', type=str, required=True, choices=['comic', 'novel'], help="处理模式: 'comic' (图片优先) 或 'novel' (文本优先)。")
    
    optionalGroup.add_argument('-o', '--output', type=str, nargs='+', help="输出文件的基础名称。可以是单个名称或与输入路径对应的名称列表。")
    optionalGroup.add_argument('-op', '--outputpath', type=str, help="所有输出文件的统一存放目录。如果未指定，则输出到每个源文件夹的父目录中。")
    optionalGroup.add_argument('-q', '--quality', type=int, default=85, choices=range(1, 101), help="图片压缩质量 (1-100)。默认: 85。")
    optionalGroup.add_argument('-s', '--scale', type=float, default=1.0, help="PDF渲染缩放系数 (1.0=原大, 2.0=高清)。默认: 1.0。")
    optionalGroup.add_argument('-t', '--title', type=str, nargs='+', help="电子书元数据中的标题。可以是单个标题或与输入路径对应的标题列表。")
    optionalGroup.add_argument('-l', '--lang', type=str, default='zh', choices=['zh', 'en', 'ja'], help="提示信息的语言。默认: zh。")
    optionalGroup.add_argument('-w', '--workers', type=int, default=os.cpu_count(), help=f"并行处理的线程数。默认: {os.cpu_count()}。")
    optionalGroup.add_argument('-c', '--cover', type=str, help="封面图片路径。")
    optionalGroup.add_argument('-rs', '--remove-styling', action='store_true', help="使用Calibre转换时移除字体和颜色样式。")
    optionalGroup.add_argument('-if', '--image-format', type=str, default='jpeg', choices=['jpeg', 'webp'], help="图片输出格式 (jpeg或webp)。仅在命令行模式下可用。默认: jpeg。")
    optionalGroup.add_argument('--batch', action='store_true', help="启用批处理模式以减少内存占用，对内存较少的电脑更友好。")
    optionalGroup.add_argument('--batch-size', type=int, help="批处理模式下，设置每个批次处理的文件数量。默认为文件总数 / 10 (四舍五入)。")
    optionalGroup.add_argument('--auto-merge', action='store_true', help="自动化整合模式（由上游脚本调用时使用）。")
    optionalGroup.add_argument('--AiNiee', action='store_true', help="如果传入此参数，则不写入元数据的版权信息")
    optionalGroup.add_argument('-h', '--help', action='help', help="显示此帮助信息并退出。")
    return griseoParser

def extractCoverFromFirstFile(sourceDirectory):
    extensions = ('.pdf', '.cbz', '.cbr', '.epub')
    files = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith(extensions)])
    if not files: return None
    firstFile = files[0]
    try:
        if firstFile.lower().endswith('.pdf'):
            with elysiaFitz.open(firstFile) as doc:
                if len(doc) > 0:
                    for img in doc.get_page_images(0):
                        xref = img[0]
                        return doc.extract_image(xref)("image")
        elif firstFile.lower().endswith(('.cbz', '.cbr')):
            with zipfile.ZipFile(firstFile, 'r') as zf:
                imgFiles = kalpasNatsort.natsorted([f for f in zf.namelist() if f.lower().endswith(('jpg','jpeg','png','webp'))])
                if imgFiles: return zf.read(imgFiles[0])
        elif firstFile.lower().endswith('.epub'):
            book = griseoEpub.read_epub(firstFile)
            cover_item = book.get_item_with_id('cover')
            if cover_item: return cover_item.get_content()
            for item in book.get_items_of_type(griseoEpub.ITEM_IMAGE): return item.get_content()
    except: return None
    return None

def mergeTxtsToEpubSmart(sourceDirectory, outputFilePath, bookTitle, languageCode, coverPath=None, input_files=None, suppress_copyright=False):
    print(STRINGS['smart_merge_txt_start'][languageCode])
    if input_files: txtFiles = input_files
    else: txtFiles = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith('.txt')])
    if not txtFiles: return False
    griseoEpubBook = griseoEpub.EpubBook()
    griseoEpubBook.set_identifier(f'id_{os.path.basename(outputFilePath)}')
    griseoEpubBook.set_title(bookTitle)
    griseoEpubBook.set_language(languageCode)
    griseoEpubBook.add_author(STRINGS['smart_merger_author'][languageCode])
    if not suppress_copyright:
        griseoEpubBook.add_metadata('DC', 'description', "本电子书使用https://github.com/ShadowLoveElysia/Bulk-Ebook-Merger-Converter项目进行辅助合成/处理，本项目完全开源免费，若您是付费获取的此电子书/软件，请向平台举报！")

    if coverPath == 'auto':
        coverData = extractCoverFromFirstFile(sourceDirectory)
        if coverData: griseoEpubBook.set_cover("cover.jpg", coverData)
    elif coverPath and coverPath != 'auto' and os.path.exists(coverPath):
        try:
            with open(coverPath, 'rb') as f: griseoEpubBook.set_cover("cover.jpg", f.read())
        except Exception: pass

    styleContent = 'body { font-family: "Microsoft YaHei", "SimSun", sans-serif; line-height: 1.6; } p { text-indent: 2em; margin-bottom: 0.5em; }'
    styleSheet = griseoEpub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=styleContent)
    griseoEpubBook.add_item(styleSheet)
    griseoEpubBook.spine = ['nav']
    tocList = []
    for index, txtPath in enumerate(villVTqdm(txtFiles, desc="Merging TXT")):
        try:
            txtContent = ""
            encodingList = ['utf-8', 'gb18030', 'gbk', 'big5', 'utf-16']
            for encodingItem in encodingList:
                try:
                    with open(txtPath, 'r', encoding=encodingItem) as fileHandle:
                        txtContent = fileHandle.read()
                    break
                except UnicodeDecodeError: continue
            if not txtContent:
                print(STRINGS['txt_decode_fail'][languageCode].format(os.path.basename(txtPath)))
                continue
            chapterTitle = os.path.splitext(os.path.basename(txtPath))[0]
            chapterTitle = re.sub(r'^\d+[\.\s]*', '', chapterTitle)
            contentLines = txtContent.splitlines()
            htmlContent = f'<html><head><title>{chapterTitle}</title><link rel="stylesheet" type="text/css" href="style/nav.css" /></head><body>'
            htmlContent += f'<h2>{chapterTitle}</h2>'
            for line in contentLines:
                line = line.strip()
                if line: htmlContent += f'<p>{line}</p>'
            htmlContent += '</body></html>'
            chapterFileName = f'chapter_{index + 1:04d}.xhtml'
            epubHtmlChapter = griseoEpub.EpubHtml(title=chapterTitle, file_name=chapterFileName, lang=languageCode)
            epubHtmlChapter.content = htmlContent
            epubHtmlChapter.add_item(styleSheet)
            griseoEpubBook.add_item(epubHtmlChapter)
            griseoEpubBook.spine.append(epubHtmlChapter)
            tocList.append(epubHtmlChapter)
        except Exception as error: print(STRINGS['error_generic'][languageCode].format(error))
    griseoEpubBook.toc = tocList
    griseoEpubBook.add_item(griseoEpub.EpubNcx())
    griseoEpubBook.add_item(griseoEpub.EpubNav())
    try:
        griseoEpub.write_epub(outputFilePath, griseoEpubBook, {})
        print(STRINGS['smart_merge_success'][languageCode].format(outputFilePath))
        return True
    except Exception as error:
        print(STRINGS['smart_merge_fail'][languageCode].format(error))
        return False

def mergeEpubsSmart(sourceDirectory, outputFilePath, bookTitle, languageCode, coverPath=None, input_files=None, flat_merge=False, suppress_copyright=False):
    print(STRINGS['smart_merge_epub_start'][languageCode])
    if input_files: epubFiles = input_files
    else: epubFiles = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith('.epub')])
    if not epubFiles: return False
    griseoEpubBook = griseoEpub.EpubBook()
    griseoEpubBook.set_identifier(f'id_{os.path.basename(outputFilePath)}')
    griseoEpubBook.set_title(bookTitle)
    griseoEpubBook.set_language(languageCode)
    if not suppress_copyright:
        griseoEpubBook.add_metadata('DC', 'description', "本电子书使用https://github.com/ShadowLoveElysia/Bulk-Ebook-Merger-Converter项目进行辅助合成/处理，本项目完全开源免费，若您是付费获取的此电子书/软件，请向平台举报！")

    if coverPath == 'auto':
        coverData = extractCoverFromFirstFile(sourceDirectory)
        if coverData: griseoEpubBook.set_cover("cover.jpg", coverData)
    elif coverPath and coverPath != 'auto' and os.path.exists(coverPath):
        try:
            with open(coverPath, 'rb') as f: griseoEpubBook.set_cover("cover.jpg", f.read())
        except Exception: pass

    try:
        firstBook = griseoEpub.read_epub(epubFiles[0])
        authors = firstBook.get_metadata('DC', 'creator')
        if authors: griseoEpubBook.add_author(authors[0][0])
    except: griseoEpubBook.add_author('Smart Merger')
    spineList = ['nav']
    masterToc = []
    defaultCss = griseoEpub.EpubItem(uid="master_style", file_name="style/master.css", media_type="text/css", content="img { max-width: 100%; }")
    griseoEpubBook.add_item(defaultCss)
    for bookIndex, epubPath in enumerate(villVTqdm(epubFiles, desc="Merging EPUBs")):
        try:
            sourceEpubBook = griseoEpub.read_epub(epubPath)
            bookPrefix = f"b{bookIndex}_"
            sourceManifest = {}
            sourceFilenameMap = {}
            for item in sourceEpubBook.get_items():
                if item.get_type() == mobiusEbookLib.ITEM_DOCUMENT or item.get_type() == mobiusEbookLib.ITEM_NAVIGATION: continue
                newId = bookPrefix + item.get_id()
                newFilename = bookPrefix + item.get_name()
                newItem = griseoEpub.EpubItem(uid=newId, file_name=newFilename, media_type=item.media_type, content=item.get_content())
                griseoEpubBook.add_item(newItem)
                sourceManifest[item.get_id()] = newItem
                sourceFilenameMap[item.get_name()] = newFilename
            bookTitleClean = os.path.splitext(os.path.basename(epubPath))[0]
            try:
                metaTitles = sourceEpubBook.get_metadata('DC', 'title')
                if metaTitles: bookTitleClean = metaTitles[0][0]
            except: pass
            for itemId, linear in sourceEpubBook.spine:
                item = sourceEpubBook.get_item_with_id(itemId)
                if not item: continue
                if item.get_type() == mobiusEbookLib.ITEM_DOCUMENT:
                    newId = bookPrefix + item.get_id()
                    newFilename = bookPrefix + item.get_name()
                    contentStr = item.get_content().decode('utf-8', errors='ignore')
                    
                    def suReplaceLink(match):
                        attrName = match.group(1)
                        quoteChar = match.group(2)
                        linkUrl = match.group(3)
                        if linkUrl.startswith(('http:', 'https:', 'mailto:', 'data:', '#')): return match.group(0)
                        
                        try: decodedLink = urllib.parse.unquote(linkUrl)
                        except: decodedLink = linkUrl

                        currentPath = item.get_name()
                        currentDir = posixpath.dirname(currentPath)
                        try:
                            absLink = posixpath.normpath(posixpath.join(currentDir, decodedLink))
                        except: return match.group(0)
                        if absLink in sourceFilenameMap:
                            newTarget = sourceFilenameMap[absLink]
                            newCurrentPath = newFilename
                            newCurrentDir = posixpath.dirname(newCurrentPath)
                            newRelLink = posixpath.relpath(newTarget, newCurrentDir)
                            encodedNewLink = urllib.parse.quote(newRelLink)
                            return f'{attrName}={quoteChar}{encodedNewLink}{quoteChar}'
                        return match.group(0)

                    contentStr = re.sub(r'(src|href)=([\'"])(.*?)\2', suReplaceLink, contentStr)

                    newDoc = griseoEpub.EpubHtml(uid=newId, file_name=newFilename, media_type=item.media_type, content=contentStr.encode('utf-8'), lang=languageCode)
                    griseoEpubBook.add_item(newDoc)
                    spineList.append(newDoc)
                    sourceFilenameMap[item.get_name()] = newFilename
            def suProcessToc(tocItems):
                processedToc = []
                for item in tocItems:
                    if isinstance(item, (list, tuple)):
                        processedToc.append((suProcessToc([item[0]])[0], suProcessToc(item[1])))
                    elif isinstance(item, griseoEpub.Link):
                        oldHref = item.href
                        if '#' in oldHref:
                            baseHref, anchor = oldHref.split('#', 1)
                            newBaseHref = sourceFilenameMap.get(baseHref, baseHref)
                            newHref = f"{newBaseHref}#{anchor}"
                        else:
                            newHref = sourceFilenameMap.get(oldHref, oldHref)
                        processedToc.append(griseoEpub.Link(newHref, item.title, bookPrefix + (item.uid or '')))
                    elif isinstance(item, griseoEpub.Section):
                        oldHref = item.href
                        newHref = None
                        if oldHref:
                            if '#' in oldHref:
                                baseHref, anchor = oldHref.split('#', 1)
                                newBaseHref = sourceFilenameMap.get(baseHref, baseHref)
                                newHref = f"{newBaseHref}#{anchor}"
                            else:
                                newHref = sourceFilenameMap.get(oldHref, oldHref)
                        processedToc.append(griseoEpub.Section(item.title, newHref))
                return processedToc
            if flat_merge:
                mappedToc = suProcessToc(sourceEpubBook.toc)
                masterToc.extend(mappedToc)
            else:
                bookSection = griseoEpub.Section(bookTitleClean)
                mappedToc = suProcessToc(sourceEpubBook.toc)
                masterToc.append((bookSection, mappedToc))
        except Exception as error: print(STRINGS['error_generic'][languageCode].format(error))
    griseoEpubBook.spine = spineList
    griseoEpubBook.toc = masterToc
    griseoEpubBook.add_item(griseoEpub.EpubNcx())
    griseoEpubBook.add_item(griseoEpub.EpubNav())
    try:
        griseoEpub.write_epub(outputFilePath, griseoEpubBook, {})
        print(STRINGS['smart_merge_success'][languageCode].format(outputFilePath))
        return True
    except Exception as error:
        print(STRINGS['smart_merge_fail'][languageCode].format(error))
        return False

def runTask(villV_Args):
    # --- Auto-Merge & CLI Smart Defaults ---
    is_auto = getattr(villV_Args, 'auto_merge', False)
    is_interactive = getattr(villV_Args, 'interactive', False)
    
    if is_auto:
        # If auto-merge is triggered, we force non-interactive and apply safe defaults
        villV_Args.interactive = False
        is_interactive = False
        if getattr(villV_Args, 'cover', None) is None: villV_Args.cover = 'auto'
        # Auto-merge usually implies batch mode for stability
        villV_Args.batch = True

    # General CLI defaults for non-interactive mode
    if not is_interactive:
        if getattr(villV_Args, 'cover', None) is None:
            villV_Args.cover = 'auto'
        if villV_Args.mode == 'novel' and not getattr(villV_Args, 'remove_styling', False):
            villV_Args.remove_styling = True

    if is_auto and not villV_Args.outputpath and villV_Args.path:
        try:
            first_path = os.path.abspath(villV_Args.path[0])
            if os.path.basename(first_path).lower() == '_pdf_output':
                # Input is .../Book/_PDF_Output -> Output to .../Merged Files (Grandparent)
                grandparent = os.path.dirname(os.path.dirname(first_path))
                villV_Args.outputpath = os.path.join(grandparent, "Merged Files")
            else:
                # Input is .../Book -> Output to .../Merged Files (Parent)
                parent = os.path.dirname(first_path)
                villV_Args.outputpath = os.path.join(parent, "Merged Files")
            
            print(f"Auto-Merge: Smart output path set to '{villV_Args.outputpath}'")
        except Exception: pass

    if villV_Args.outputpath:
        os.makedirs(villV_Args.outputpath, exist_ok=True)
        print(STRINGS['output_path_display'][villV_Args.lang].format(villV_Args.outputpath))

    for index, sourceDirectory in enumerate(villV_Args.path):
        folderStartTime = time.time()
        calibreTimeTotal = 0.0
        
        masterFileList = []
        is_single_file_mode = False

        if os.path.isfile(sourceDirectory):
             print(f"\n{'='*20}Processing Single File: {sourceDirectory}{'='*20}")
             masterFileList = [sourceDirectory]
             is_single_file_mode = True
             # If output path not set, default to file's directory
             if not villV_Args.outputpath:
                 outputDirectory = os.path.dirname(sourceDirectory)
             # Adjust sourceDirectory to be the parent dir so subsequent logic works
             # But we keep masterFileList as just this file.
             file_path = sourceDirectory
             sourceDirectory = os.path.dirname(file_path)
        else:
            print(STRINGS['start_processing_folder'][villV_Args.lang].format('='*20, sourceDirectory, '='*20))

            if not os.path.isdir(sourceDirectory):
                print(STRINGS['error_dir_not_exist'][villV_Args.lang].format(sourceDirectory))
                continue 

            supportedExtensions = ('.pdf', '.cbz', '.cbr', '.epub', '.mobi', '.azw3', '.docx', 
                                     '.txt', '.kepub', '.fb2', '.lit', '.lrf', '.pdb', '.pmlz', 
                                     '.rb', '.rtf', '.tcr', '.txtz', '.htmlz')
            masterFileList = kalpasNatsort.natsorted([os.path.join(sourceDirectory, f) for f in os.listdir(sourceDirectory) if f.lower().endswith(supportedExtensions)])

        if not masterFileList:
            print(STRINGS['error_no_files'][villV_Args.lang].format(sourceDirectory, 'supported files'))
            continue

        pdfCount = len([f for f in masterFileList if f.lower().endswith('.pdf')])
        cbzCount = len([f for f in masterFileList if f.lower().endswith(('.cbz', '.cbr'))])
        nativeEbookCount = len([f for f in masterFileList if f.lower().endswith(('.epub', '.mobi', '.azw3'))])
        calibreRequiredCount = len([f for f in masterFileList if f.lower().endswith(('.docx', '.txt', '.kepub', '.fb2', '.lit', '.lrf', '.pdb', '.pmlz', '.rb', '.rtf', '.tcr', '.txtz', '.htmlz'))])
        txtCount = len([f for f in masterFileList if f.lower().endswith('.txt')])

        majorType = 'none'
        counts = {'epub': nativeEbookCount, 'pdf': pdfCount, 'cbz': cbzCount, 'text': calibreRequiredCount}
        if any(count > 0 for count in counts.values()):
            if villV_Args.mode == 'novel':
                if txtCount > len(masterFileList) * 0.5: majorType = 'txt_smart'
                elif nativeEbookCount > 0: majorType = 'epub_smart'
                elif calibreRequiredCount > 0: majorType = 'text' 
                else: majorType = max(counts, key=counts.get)
            else: majorType = max(counts, key=counts.get)

        is_comic_intent = (villV_Args.mode == 'comic')
        if is_comic_intent and majorType in ['epub', 'text']:
            print(f"\nDetection: Found major type '{majorType}' in Comic Mode.")
            print("Switching to Novel Mode logic for proper EPUB/Text merging...")
            print("检测到非图片格式 (EPUB/Text)，自动切换到小说模式逻辑进行智能合并...")
            print("非画像形式 (EPUB/Text) が検出されました。スマート結合のために小説モードのロジックに切り替えます...")
            villV_Args.mode = 'novel'
            if txtCount > len(masterFileList) * 0.5: majorType = 'txt_smart'
            elif nativeEbookCount > 0: majorType = 'epub_smart'
            elif calibreRequiredCount > 0: majorType = 'text' 
            else: majorType = max(counts, key=counts.get)

        if majorType == 'none':
            print(STRINGS['error_no_files'][villV_Args.lang].format(sourceDirectory, 'supported files'))
            continue

        if villV_Args.outputpath: outputDirectory = villV_Args.outputpath
        else:
            outputDirectory = os.path.dirname(villV_Args.path[0]) if len(villV_Args.path) == 1 and getattr(villV_Args, 'interactive', False) else os.path.dirname(sourceDirectory)
            outputDirectory = outputDirectory or '.'

        # Determine Output Base Name
        outputBaseName = None
        if villV_Args.output:
            if isinstance(villV_Args.output, list) and len(villV_Args.output) == len(villV_Args.path):
                outputBaseName = villV_Args.output[index]
            elif isinstance(villV_Args.output, list) and len(villV_Args.output) == 1 and len(villV_Args.path) == 1:
                outputBaseName = villV_Args.output[0]
            elif isinstance(villV_Args.output, str) and len(villV_Args.path) == 1:
                outputBaseName = villV_Args.output

        if not outputBaseName:
            outputBaseName = os.path.basename(os.path.normpath(sourceDirectory))

        # Determine Book Title
        bookTitle = None
        if villV_Args.title:
            if isinstance(villV_Args.title, list) and len(villV_Args.title) == len(villV_Args.path):
                bookTitle = villV_Args.title[index]
            elif isinstance(villV_Args.title, list) and len(villV_Args.title) == 1 and len(villV_Args.path) == 1:
                bookTitle = villV_Args.title[0]
            elif isinstance(villV_Args.title, str) and len(villV_Args.path) == 1:
                bookTitle = villV_Args.title
        
        if not bookTitle:
            bookTitle = outputBaseName

        edenTempFiles = []
        edenTempDirectories = []
        intermediateEpubs = [] 
        
        calibre_extra_args = []
        if getattr(villV_Args, 'remove_styling', False):
            calibre_extra_args = ['--filter-css', 'font-family,color,background-color']
            print(STRINGS['info_css_filter_enabled'][villV_Args.lang])
        
        temp_file_is_clean = False
        doBatchProcessing = getattr(villV_Args, 'batch', False)
        batchSize = getattr(villV_Args, 'batch_size', None)
        if doBatchProcessing and batchSize is None: batchSize = max(1, round(len(masterFileList) / 10))

        currentFileList = masterFileList 
        batches = []
        if doBatchProcessing and batchSize > 0:
            for i in range(0, len(currentFileList), batchSize):
                batches.append(currentFileList[i:i + batchSize])
        else: batches.append(currentFileList) 

        try:
            finalTempPath = ""
            for batchIndex, currentBatchFiles in enumerate(batches):
                currentBatchNum = batchIndex + 1
                totalBatches = len(batches)
                if doBatchProcessing:
                    print(STRINGS['batch_processing_info'][villV_Args.lang].format(currentBatchNum, totalBatches, len(currentBatchFiles)))
                    batchTempDir = os.path.join(outputDirectory, f"{outputBaseName}_batch_{currentBatchNum}_tmp")
                    os.makedirs(batchTempDir, exist_ok=True)
                    edenTempDirectories.append(batchTempDir)
                    targetSourceDirectory = batchTempDir
                else: targetSourceDirectory = sourceDirectory

                if villV_Args.mode == 'comic':
                    print(STRINGS['comic_mode_major_type'][villV_Args.lang].format(majorType.upper()))
                    if doBatchProcessing: tempComicEpubPath = os.path.join(outputDirectory, f"{outputBaseName}_batch_{currentBatchNum}_temp.epub")
                    else: tempComicEpubPath = os.path.join(outputDirectory, f"{outputBaseName}_temp_comic.epub")
                    
                    edenTempFiles.append(tempComicEpubPath)

                    if majorType == 'pdf':
                        pdf_scale = getattr(villV_Args, 'scale', 1.0)
                        convertPdfsToEpub(targetSourceDirectory, tempComicEpubPath, villV_Args.quality, bookTitle, villV_Args.lang, villV_Args.workers, villV_Args.cover, villV_Args.image_format, input_files=currentBatchFiles, scale=pdf_scale, suppress_copyright=getattr(villV_Args, 'AiNiee', False))
                    elif majorType == 'cbz':
                        convertCbzsToEpub(targetSourceDirectory, tempComicEpubPath, villV_Args.quality, bookTitle, villV_Args.lang, villV_Args.workers, villV_Args.cover, villV_Args.image_format, input_files=currentBatchFiles, suppress_copyright=getattr(villV_Args, 'AiNiee', False))
                    elif majorType == 'epub' or majorType == 'text':
                        comicPreConvertTempDir = None
                        allEpubsToMerge = []
                        nonEpubFilesForConversion = []
                        originalEpubFilesInBatch = []
                        supportedExtensionsForConversion = ('.mobi', '.azw3', '.docx', '.txt', '.kepub', '.fb2', '.lit', '.lrf', '.pdb', '.pmlz', '.rb', '.rtf', '.tcr', '.txtz', '.htmlz')

                        for filePath in currentBatchFiles:
                            if filePath.lower().endswith('.epub'): originalEpubFilesInBatch.append(filePath)
                            elif filePath.lower().endswith(supportedExtensionsForConversion): nonEpubFilesForConversion.append(filePath)
                        
                        if nonEpubFilesForConversion:
                            print(STRINGS['pre_convert_notice'][villV_Args.lang].format(len(nonEpubFilesForConversion)))
                            comicPreConvertTempDir = os.path.join(outputDirectory, f"{outputBaseName}_batch_{currentBatchNum}_comic_prep_epubs")
                            os.makedirs(comicPreConvertTempDir, exist_ok=True)
                            edenTempDirectories.append(comicPreConvertTempDir)
                            huaCalibreExecutable = ensureCalibreTool('ebook-convert.exe', villV_Args.lang, getattr(villV_Args, 'interactive', False))
                            if huaCalibreExecutable:
                                with villVTqdm(total=len(nonEpubFilesForConversion), desc=STRINGS['pre_convert_progress'][villV_Args.lang]) as pbar:
                                    for f_path in nonEpubFilesForConversion:
                                        destFile = os.path.join(comicPreConvertTempDir, os.path.splitext(os.path.basename(f_path))[0] + ".epub")
                                        try:
                                            subprocess.run([huaCalibreExecutable, f_path, destFile], check=True, capture_output=True, encoding='utf-8')
                                            allEpubsToMerge.append(destFile)
                                        except Exception as e:
                                            print(STRINGS['conversion_fail_single'][villV_Args.lang].format(os.path.basename(f_path), e))
                                        pbar.update(1)
                            else: print(STRINGS['calibre_missing_pre_convert'][villV_Args.lang])
                        
                        allEpubsToMerge.extend(originalEpubFilesInBatch)

                        if not allEpubsToMerge:
                            print(STRINGS['error_no_files'][villV_Args.lang].format(targetSourceDirectory, 'EPUB files for comic mode consolidation'))
                            continue

                        success, duration, was_cleaned = mergeEpubsWithCalibre(targetSourceDirectory, tempComicEpubPath, bookTitle, villV_Args.lang, villV_Args.cover, calibre_extra_args, input_files=allEpubsToMerge)
                        if success:
                            calibreTimeTotal += duration
                            if was_cleaned: temp_file_is_clean = True
                        else: continue

                        if comicPreConvertTempDir and os.path.exists(comicPreConvertTempDir):
                            shutil.rmtree(comicPreConvertTempDir)
                            edenTempDirectories.remove(comicPreConvertTempDir)
                            gc.collect()
                    
                    if doBatchProcessing:
                        intermediateEpubs.append(tempComicEpubPath)
                        shutil.rmtree(batchTempDir)
                        edenTempDirectories.remove(batchTempDir)
                        gc.collect()
                    else: finalTempPath = tempComicEpubPath

                elif villV_Args.mode == 'novel':
                    print(STRINGS['novel_mode_intro'][villV_Args.lang])
                    smartMergeSuccess = False
                    if doBatchProcessing: tempSmartEpubPath = os.path.join(outputDirectory, f"{outputBaseName}_batch_{currentBatchNum}_smart.epub")
                    else: tempSmartEpubPath = os.path.join(outputDirectory, f"{outputBaseName}_temp_smart.epub")

                    if majorType == 'txt_smart':
                         if mergeTxtsToEpubSmart(targetSourceDirectory, tempSmartEpubPath, bookTitle, villV_Args.lang, villV_Args.cover, input_files=currentBatchFiles, suppress_copyright=getattr(villV_Args, 'AiNiee', False)):
                             smartMergeSuccess = True
                             if doBatchProcessing: intermediateEpubs.append(tempSmartEpubPath)
                             else: finalTempPath = tempSmartEpubPath
                             edenTempFiles.append(tempSmartEpubPath)
                    
                    if majorType == 'epub_smart':
                        mobiusTargetSourceDir = targetSourceDirectory
                        kalpasTempPrepDir = None
                        try:
                            suRawFiles = currentBatchFiles
                            suConversionExtensions = ('.mobi', '.azw3', '.docx', '.txt', '.kepub', '.fb2', '.lit', '.lrf', '.pdb', '.pmlz', '.rb', '.rtf', '.tcr', '.txtz', '.htmlz')
                            suNeedsConversion = [f for f in suRawFiles if f.lower().endswith(suConversionExtensions)]
                            
                            if suNeedsConversion:
                                print(STRINGS['pre_convert_notice'][villV_Args.lang].format(len(suNeedsConversion)))
                                kalpasTempPrepDir = os.path.join(outputDirectory, f"{outputBaseName}_temp_prep_epubs")
                                os.makedirs(kalpasTempPrepDir, exist_ok=True)
                                edenTempDirectories.append(kalpasTempPrepDir)
                                huaCalibreExecutable = ensureCalibreTool('ebook-convert.exe', villV_Args.lang, getattr(villV_Args, 'interactive', False))
                                if huaCalibreExecutable:
                                    with villVTqdm(total=len(suNeedsConversion), desc=STRINGS['pre_convert_progress'][villV_Args.lang]) as pbar:
                                        for f_path in suNeedsConversion:
                                            destFile = os.path.join(kalpasTempPrepDir, os.path.splitext(os.path.basename(f_path))[0] + ".epub")
                                            try:
                                                subprocess.run([huaCalibreExecutable, f_path, destFile], check=True, capture_output=True, encoding='utf-8')
                                            except Exception as e:
                                                print(STRINGS['conversion_fail_single'][villV_Args.lang].format(os.path.basename(f_path), e))
                                            pbar.update(1)
                                    mobiusTargetSourceDir = kalpasTempPrepDir
                                else: print(STRINGS['calibre_missing_pre_convert'][villV_Args.lang])
                        except Exception as e:
                            print(STRINGS['pre_convert_error'][villV_Args.lang].format(e))
                        
                        prepFiles = None
                        if mobiusTargetSourceDir != targetSourceDirectory:
                             prepFiles = kalpasNatsort.natsorted([os.path.join(mobiusTargetSourceDir, f) for f in os.listdir(mobiusTargetSourceDir) if f.lower().endswith('.epub')])
                             currentBatchEpubs = [f for f in currentBatchFiles if f.lower().endswith('.epub')]
                             prepFiles.extend(currentBatchEpubs)
                        else: prepFiles = currentBatchFiles

                        if mergeEpubsSmart(mobiusTargetSourceDir, tempSmartEpubPath, bookTitle, villV_Args.lang, villV_Args.cover, input_files=prepFiles, suppress_copyright=getattr(villV_Args, 'AiNiee', False)):
                            smartMergeSuccess = True
                            if doBatchProcessing: intermediateEpubs.append(tempSmartEpubPath)
                            else: finalTempPath = tempSmartEpubPath
                            edenTempFiles.append(tempSmartEpubPath)
                        else: print(STRINGS['smart_merge_epub_fail_fallback'][villV_Args.lang])

                    if not smartMergeSuccess:
                        tempPdfsDirectory = os.path.join(outputDirectory, f"{outputBaseName}_temp_pdfs_for_merge")
                        tempMergedPdfPath = os.path.join(outputDirectory, f"{outputBaseName}_temp_merged.pdf")
                        tempNovelEpubPath = os.path.join(outputDirectory, f"{outputBaseName}_temp_novel.epub")
                        edenTempDirectories.append(tempPdfsDirectory)
                        edenTempFiles.extend([tempMergedPdfPath, tempNovelEpubPath])
                        os.makedirs(tempPdfsDirectory, exist_ok=True)
                        anyNonPdfFiles = nativeEbookCount > 0 or calibreRequiredCount > 0
                        if anyNonPdfFiles:
                            success, duration = FilesToPdf(targetSourceDirectory, tempPdfsDirectory, villV_Args.lang, villV_Args.interactive, input_files=currentBatchFiles)
                            if success: calibreTimeTotal += duration
                            else: continue
                        else: print(STRINGS['novel_step1_skip_convert'][villV_Args.lang])
                        mergePdfs(tempPdfsDirectory, tempMergedPdfPath, villV_Args.lang, input_files=[f for f in currentBatchFiles if f.lower().endswith('.pdf')])
                        
                        print(f"{STRINGS['novel_step3_convert_to_epub'][villV_Args.lang]}... ", end="", flush=True)
                        calibreExecutable = ensureCalibreTool('ebook-convert.exe', villV_Args.lang, villV_Args.interactive)
                        if not calibreExecutable: continue
                        start_time = time.time()
                        try:
                            cmd = [calibreExecutable, tempMergedPdfPath, tempNovelEpubPath, '--title', bookTitle] + calibre_extra_args
                            if villV_Args.cover and villV_Args.cover != 'auto': cmd.extend(['--cover', villV_Args.cover])
                            elif villV_Args.cover == 'auto':
                                coverData = extractCoverFromFirstFile(sourceDirectory)
                                if coverData:
                                    coverPath = os.path.join(outputDirectory, "temp_cover.jpg")
                                    with open(coverPath, "wb") as f: f.write(coverData)
                                    cmd.extend(['--cover', coverPath])
                                    edenTempFiles.append(coverPath)
                            subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
                            duration = time.time() - start_time
                            calibreTimeTotal += duration
                            print(STRINGS['calibre_conversion_timed'][villV_Args.lang].format(duration))
                            finalTempPath = tempNovelEpubPath
                            if calibre_extra_args: temp_file_is_clean = True
                            print(STRINGS['consolidation_complete'][villV_Args.lang])
                        except Exception as error: 
                            print(STRINGS['pdf_to_epub_conversion_failed'][villV_Args.lang].format(error.stderr if hasattr(error, 'stderr') else error))
                            continue
                    
                    if doBatchProcessing and os.path.exists(batchTempDir):
                         shutil.rmtree(batchTempDir)
                         edenTempDirectories.remove(batchTempDir)
                         gc.collect()

            if doBatchProcessing and intermediateEpubs:
                print("Merging Batches...")
                finalMergedEpubPath = os.path.join(outputDirectory, f"{outputBaseName}_final_merged.epub")
                edenTempFiles.append(finalMergedEpubPath)
                finalMergeTempDir = os.path.join(outputDirectory, f"{outputBaseName}_final_merge_tmp")
                os.makedirs(finalMergeTempDir, exist_ok=True)
                edenTempDirectories.append(finalMergeTempDir)
                if mergeEpubsSmart(finalMergeTempDir, finalMergedEpubPath, bookTitle, villV_Args.lang, villV_Args.cover, input_files=intermediateEpubs, flat_merge=True, suppress_copyright=getattr(villV_Args, 'AiNiee', False)):
                    finalTempPath = finalMergedEpubPath
                else:
                    print("Batch merge failed.")
                    continue

            if os.path.exists(finalTempPath):
                print(f"\n{STRINGS['distributing'][villV_Args.lang]}")
                resolvedFormat = FORMAT_CHOICE_MAP.get(villV_Args.format, villV_Args.format)
                targetFormats = ['epub', 'pdf', 'cbz'] if resolvedFormat == 'all_native' else [resolvedFormat]
                
                calibre_extra_args = []
                if getattr(villV_Args, 'remove_styling', False):
                    calibre_extra_args = ['--filter-css', 'font-family,color,background-color']

                for formatUnit in targetFormats:
                    finalFilePath = os.path.join(outputDirectory, f"{outputBaseName}.{formatUnit}")
                    print(STRINGS['creating_format_message'][villV_Args.lang].format('='*10, outputBaseName, formatUnit.upper(), '='*10, '='*10, '='*10))

                    if formatUnit == 'epub':
                        if getattr(villV_Args, 'remove_styling', False) and not temp_file_is_clean:
                             huaCalibreExecutable = ensureCalibreTool('ebook-convert.exe', villV_Args.lang, villV_Args.interactive)
                             if not huaCalibreExecutable:
                                 print(STRINGS['calibre_unavailable_skip_format'][villV_Args.lang].format("EPUB", ""))
                                 shutil.copy(finalTempPath, finalFilePath)
                             else:
                                 print(STRINGS['calibre_strip_styles_info'][villV_Args.lang])
                                 command = [huaCalibreExecutable, finalTempPath, finalFilePath] + calibre_extra_args
                                 try:
                                    subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
                                    print(STRINGS['task_complete'][villV_Args.lang].format(finalFilePath))
                                 except Exception as error:
                                    print(STRINGS['calibre_strip_styles_fail'][villV_Args.lang].format(error))
                                    shutil.copy(finalTempPath, finalFilePath)
                        else:
                            shutil.copy(finalTempPath, finalFilePath)
                            print(STRINGS['task_complete'][villV_Args.lang].format(finalFilePath))
                    elif formatUnit == 'cbz':
                        convertEpubToCbz(finalTempPath, finalFilePath, villV_Args.quality, villV_Args.lang, villV_Args.image_format)
                    
                    else:
                        huaCalibreExecutable = ensureCalibreTool('ebook-convert.exe', villV_Args.lang, villV_Args.interactive)
                        if not huaCalibreExecutable:
                            print(STRINGS['calibre_unavailable_skip_format'][villV_Args.lang].format(formatUnit.upper(), ""))
                            continue
                        
                        message = STRINGS['calibre_converting_temp_file'][villV_Args.lang].format(formatUnit.upper(), "")
                        print(f"{message}... ", end="", flush=True)

                        command = [huaCalibreExecutable, finalTempPath, finalFilePath] + calibre_extra_args
                        if formatUnit == 'pdf':
                            command.append('--pdf-add-toc')
                        
                        start_time = time.time()
                        try:
                            subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
                            duration = time.time() - start_time
                            calibreTimeTotal += duration
                            
                            print(f"\r{message}... {STRINGS['calibre_conversion_timed'][villV_Args.lang].format(duration)}")
                            print(STRINGS['task_complete'][villV_Args.lang].format(finalFilePath))
                        except Exception as error: 
                            print(STRINGS['calibre_conversion_fail_generic'][villV_Args.lang].format(error.stderr if hasattr(error, 'stderr') else error))

        finally:
            print(STRINGS['cleaning_temp_files'][villV_Args.lang])
            for filePath in intermediateEpubs:
                try:
                    if os.path.exists(filePath): os.remove(filePath)
                except Exception: pass
            for dirPath in edenTempDirectories:
                if os.path.exists(dirPath):
                    shutil.rmtree(dirPath)
                    print(STRINGS['deleted_temp_directory'][villV_Args.lang].format(dirPath))

            totalFolderTime = time.time() - folderStartTime
            print("\n" + STRINGS['congratulations_complete'][villV_Args.lang].format(outputBaseName, totalFolderTime, calibreTimeTotal))
            
            if is_comic_intent:
                print(STRINGS['crawler_tip'][villV_Args.lang])

    print(STRINGS['all_folders_processed'][villV_Args.lang].format('='*20, '='*20))

def confirmUserInput(languageCode, promptKey, promptValue):
    while True:
        confirmedInput = input(STRINGS[promptKey][languageCode].format(promptValue)).strip().lower()
        if confirmedInput in ['y', 'yes']: return True
        elif confirmedInput in ['n', 'no']: return False
        else: print(STRINGS['invalid_confirmation'][languageCode])

def presentFileSummaryAndGetChoice(sourceDirectory, languageCode):
    supportedExtensions = ('.pdf', '.cbz', '.cbr', '.epub', '.mobi', '.azw3', '.docx', 
                             '.txt', '.kepub', '.fb2', '.lit', '.lrf', '.pdb', '.pmlz', 
                             '.rb', '.rtf', '.tcr', '.txtz', '.htmlz')
    allFiles = kalpasNatsort.natsorted([f for f in os.listdir(sourceDirectory) if f.lower().endswith(supportedExtensions)])
    if not allFiles:
        print(STRINGS['error_no_files'][languageCode].format(sourceDirectory, 'supported files'))
        return None
    filesWithDecimals = [f for f in allFiles if re.search(r'\d+\.\d+', f)]
    
    formatCounts = {}
    for f in allFiles:
        ext = os.path.splitext(f)[1].lower()
        formatCounts[ext] = formatCounts.get(ext, 0) + 1
    
    breakdownStr = ""
    for ext, count in formatCounts.items(): breakdownStr += f"    - {ext.upper()}: {count}\n"

    numericParts = [re.findall(r'(\d+)', f) for f in allFiles]
    numericParts = [int(p[0]) for p in numericParts if p]
    minNum, maxNum = (min(numericParts), max(numericParts)) if numericParts else ('N/A', 'N/A')

    summary = STRINGS['prompt_file_summary'][languageCode].format(
        total_count=len(allFiles), min_num=minNum, max_num=maxNum, breakdown=breakdownStr, decimal_count=len(filesWithDecimals)
    )
    print("\n" + "="*20 + "\n" + summary + "="*20 + "\n")

    while True:
        choice = input(STRINGS['prompt_confirm_decimal_ignore'][languageCode]).strip().lower()
        if choice in ['y', 'yes']: return [os.path.join(sourceDirectory, f) for f in allFiles]
        elif choice in ['n', 'no']: return [os.path.join(sourceDirectory, f) for f in allFiles if f not in filesWithDecimals]
        else: print(STRINGS['error_invalid_choice'][languageCode])

def runInteractiveMode(globalLanguage='zh'): 
    print(STRINGS['interactive_mode_welcome'][globalLanguage])

    while True:
        modeChoice = input(f"{STRINGS['prompt_mode_select'][globalLanguage]}\n> ").strip()
        if modeChoice in ['1', '2']:
            selectedMode = 'comic' if modeChoice == '1' else 'novel'
            modeDisplayName = STRINGS[f'{selectedMode}_mode_name'][globalLanguage]
            if confirmUserInput(globalLanguage, 'prompt_confirm_mode', modeDisplayName): break
        else: print(STRINGS['error_invalid_choice'][globalLanguage])
    
    sourcePath = ""
    while True:
        print(STRINGS['multi_folder_tip'][globalLanguage])
        path = input(f"{STRINGS['prompt_input_path'][globalLanguage]}\n> ").strip().replace('"', '')
        if os.path.isdir(path):
            if confirmUserInput(globalLanguage, 'prompt_confirm_path', path):
                sourcePath = path
                break
        else: print(STRINGS['error_dir_not_exist'][globalLanguage].format(path))

    filesToProcess = presentFileSummaryAndGetChoice(sourcePath, globalLanguage)
    if not filesToProcess:
        print(STRINGS['no_files_to_process_exit'][globalLanguage])
        return
    
    pardofelisTempDir = os.path.join(os.path.dirname(sourcePath), f"temp_processing_{int(time.time())}")
    os.makedirs(pardofelisTempDir, exist_ok=True)
    try:
        for f_path in filesToProcess: shutil.copy(f_path, pardofelisTempDir)
        processingPath = pardofelisTempDir
        while True:
            print(STRINGS['prompt_final_format'][globalLanguage])
            formatChoice = input("> ").strip()
            if formatChoice in FORMAT_CHOICE_MAP:
                formatName = FORMAT_CHOICE_MAP[formatChoice]
                formatDisplay = "全部原生格式 (EPUB+PDF+CBZ)" if formatName == 'all_native' else formatName.upper()
                if confirmUserInput(globalLanguage, 'prompt_confirm_format', formatDisplay): break
            else: print(STRINGS['error_invalid_choice'][globalLanguage])

        selectedCover = None
        while True:
            choice = input(STRINGS['prompt_cover_auto'][globalLanguage]).strip().lower()
            if choice in ['y', 'yes']:
                testCoverData = extractCoverFromFirstFile(processingPath)
                if testCoverData:
                    selectedCover = 'auto'
                    break
                else: print(STRINGS['cover_extract_fail'][globalLanguage])
            elif choice in ['n', 'no']:
                while True:
                    customPath = input(STRINGS['prompt_cover_path'][globalLanguage]).strip().replace('"', '')
                    if os.path.isfile(customPath):
                        selectedCover = customPath
                        break
                    else:
                        retry = input(STRINGS['prompt_cover_invalid'][globalLanguage]).strip().lower()
                        if retry in ['s', 'simple']: 
                            selectedCover = None 
                            break
                        elif retry not in ['r', 'retry']: break
                break
            else: print(STRINGS['error_invalid_choice'][globalLanguage])
        
        sakuraParams = argparse.Namespace()
        sakuraParams.mode = selectedMode
        sakuraParams.path = [processingPath]
        sakuraParams.format = formatChoice
        sakuraParams.lang = globalLanguage
        sakuraParams.outputpath = None
        sakuraParams.cover = selectedCover
        sakuraParams.image_format = 'jpeg'
        defaultBaseName = os.path.basename(os.path.normpath(sourcePath))
        outputBaseName = input(STRINGS['prompt_output_base_name'][globalLanguage].format(defaultBaseName)).strip() or defaultBaseName
        sakuraParams.output = outputBaseName
        defaultQuality = 85
        qualityInput = input(STRINGS['prompt_image_quality'][globalLanguage].format(defaultQuality)).strip()
        sakuraParams.quality = int(qualityInput) if qualityInput.isdigit() and 1 <= int(qualityInput) <= 100 else defaultQuality
        
        defaultScale = 1.0
        scaleInput = input(STRINGS['prompt_ask_scale'][globalLanguage]).strip()
        try:
            sakuraParams.scale = float(scaleInput) if scaleInput else defaultScale
        except ValueError:
            sakuraParams.scale = defaultScale
            
        defaultTitle = sakuraParams.output or os.path.basename(os.path.normpath(sourcePath))
        titleInput = input(STRINGS['prompt_book_title'][globalLanguage].format(defaultTitle)).strip() or defaultTitle
        sakuraParams.title = titleInput
        sakuraParams.batch = False
        sakuraParams.batch_size = None

        while True:
            batchEnableChoice = input(STRINGS['prompt_batch_enable'][globalLanguage]).strip().lower()
            if batchEnableChoice in ['y', 'yes']:
                sakuraParams.batch = True
                totalFiles = len(filesToProcess)
                if totalFiles == 0:
                    print(STRINGS['error_no_files'][globalLanguage].format(sourcePath, 'supported files'))
                    return
                while True:
                    try:
                        batchCountInput = input(STRINGS['prompt_batch_count'][globalLanguage]).strip()
                        batchCount = int(batchCountInput)
                        if batchCount <= 0:
                            print(STRINGS['error_invalid_choice'][globalLanguage])
                            continue
                        sakuraParams.batch_size = max(1, round(totalFiles / batchCount))
                        print(f"将分 {batchCount} 批处理，每批约 {sakuraParams.batch_size} 个文件。")
                        break
                    except ValueError: print(STRINGS['error_invalid_choice'][globalLanguage])
                break
            elif batchEnableChoice in ['n', 'no']: break
            else: print(STRINGS['error_invalid_choice'][globalLanguage])

        sakuraParams.remove_styling = False
        if selectedMode == 'novel':
            while True:
                rsChoice = input(STRINGS['prompt_remove_styling'][globalLanguage]).strip().lower()
                if rsChoice in ['y', 'yes']:
                    sakuraParams.remove_styling = True
                    break
                elif rsChoice in ['n', 'no']:
                    sakuraParams.remove_styling = False
                    break
                else: print(STRINGS['error_invalid_choice'][globalLanguage])

        defaultWorkers = os.cpu_count() or 1
        workersPrompt = STRINGS['prompt_ask_workers'][globalLanguage].format(defaultWorkers=defaultWorkers)
        workersInput = input(workersPrompt).strip()
        sakuraParams.workers = int(workersInput) if workersInput.isdigit() and int(workersInput) > 0 else defaultWorkers
        sakuraParams.interactive = True 
        print(STRINGS['starting_task'][globalLanguage])
        runTask(sakuraParams)
    finally:
        if os.path.exists(pardofelisTempDir):
            shutil.rmtree(pardofelisTempDir)
            print(STRINGS['cleaned_temp_dir'][globalLanguage].format(pardofelisTempDir))

def showMainMenu(argumentParser): 
    while True:
        print(f"{STRINGS['prompt_main_menu']['en']}\n{STRINGS['prompt_main_menu']['zh']}\n{STRINGS['prompt_main_menu']['ja']}")
        choice = input("> ").strip()
        if choice == '1':
            print("\n请选择语言 (Select Language):")
            print("1) 中文 (Chinese)")
            print("2) English")
            print("3) 日本語 (Japanese)")
            langChoice = input("> ").strip()
            if langChoice == '1': globalLanguage = 'zh'
            elif langChoice == '2': globalLanguage = 'en'
            elif langChoice == '3': globalLanguage = 'ja'
            else: globalLanguage = 'zh'  
            runInteractiveMode(globalLanguage)
            break
        elif choice == '2':
            argumentParser.print_help()
            break
        elif choice == '3':
            print(f"{STRINGS['exiting']['en']} / {STRINGS['exiting']['zh']} / {STRINGS['exiting']['ja']}")
            break
        else: print(STRINGS['error_invalid_choice']['en'])

if __name__ == '__main__':
    checkDependencies()
    suParser = createArgumentParser()
    if len(sys.argv) == 1: showMainMenu(suParser)
    else:
        try:
            kosmaArgs = suParser.parse_args()
            kosmaArgs.interactive = False
            runTask(kosmaArgs)
        except argparse.ArgumentError as error: 
            print(STRINGS['error_arg_parse'][kosmaArgs.lang].format(error))
        except SystemExit as error: 
             if error.code != 0: print(STRINGS['error_parsing_arguments'][kosmaArgs.lang])