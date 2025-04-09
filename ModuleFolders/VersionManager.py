import os
import sys
import json
import signal
import threading
import requests
from PyQt5.QtCore import QUrl, pyqtSignal, QObject
from PyQt5.QtWidgets import (QVBoxLayout,QDialog, QLabel, 
QProgressBar, QPushButton, QHBoxLayout)

from PyQt5.QtGui import QDesktopServices
from qfluentwidgets import MessageBox

from Base.Base import Base

class UpdaterSignals(QObject):
    progress_updated = pyqtSignal(int)
    download_completed = pyqtSignal(str)
    download_failed = pyqtSignal(str)

class VersionManager(Base):
    # GitHub API URL for releases
    GITHUB_API_URL = "https://api.github.com/repos/NEKOparapa/AiNiee/releases/latest"

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.current_version = self._get_current_version()
        self.latest_version = None
        self.latest_version_url = None
        self.download_thread = None
        self.update_dialog = None
        self.signals = UpdaterSignals()


        self.signals.progress_updated.connect(self._update_progress)
        self.signals.download_completed.connect(self._download_completed)
        self.signals.download_failed.connect(self._download_failed)

    def _get_current_version(self):
        """从Version中获取版本"""
        try:
            with open("Version", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            self.error(f"Failed to read current version: {e}")
            return "0.0.0"

    def check_for_updates(self):
        """检查是否需要更新"""
        try:
            response = requests.get(self.GITHUB_API_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # 从 tag_name 中提取版本号，格式为 "AiNiee6.2.3"
                tag_name = data["tag_name"]
                import re
                version_match = re.search(r'AiNiee([\d\.]+)', tag_name)
                if version_match:
                    self.latest_version = version_match.group(1)  # 提取数字部分，如 "6.2.3"
                else:
                    self.latest_version = tag_name.lstrip("v")  # 兼容其他格式

                self.latest_version_url = data["html_url"]

                # Compare versions
                if self._compare_versions(self.latest_version, self.current_version) > 0:
                    return True, self.latest_version
                else:
                    return False, self.current_version
            else:
                self.error(f"Failed to check for updates: {response.status_code}")
                return False, self.current_version
        except Exception as e:
            self.error(f"Error checking for updates: {e}")
            return False, self.current_version

    def _compare_versions(self, version1, version2):
        """比较版本号"""
        v1_parts = [int(x) for x in version1.split(".")]
        v2_parts = [int(x) for x in version2.split(".")]

        # 填充版本号，使得版本号的位数相同
        while len(v1_parts) < 3:
            v1_parts.append(0)
        while len(v2_parts) < 3:
            v2_parts.append(0)

        for i in range(3):
            if v1_parts[i] > v2_parts[i]:
                return 1
            elif v1_parts[i] < v2_parts[i]:
                return -1

        return 0

    def show_update_dialog(self):
        """Show the update dialog"""
        if self.main_window is None:
            self.error("Main window reference is not set")
            return

        # 检查是否有已下载完成的更新文件
        local_filename = os.path.join("downloads", "AiNiee-update.zip")
        download_info_file = os.path.join("downloads", "download_info.json")

        if os.path.exists(local_filename) and os.path.exists(download_info_file):
            try:
                with open(download_info_file, 'r') as f:
                    download_info = json.load(f)

                if download_info.get("status") == "completed":
                    # 已有下载完成的更新文件，直接提示安装
                    msg_box = MessageBox(
                        self.tra("安装更新"),
                        self.tra("发现已下载完成的更新文件，是否立即安装？\n\n安装过程中应用将会关闭。"),
                        self.main_window
                    )
                    msg_box.yesButton.setText(self.tra("立即安装"))
                    msg_box.cancelButton.setText(self.tra("取消"))

                    if msg_box.exec():
                        # 运行更新器
                        self._run_updater(local_filename)
                    return
            except Exception as e:
                self.error(f"Error checking downloaded update: {e}")

        # 检查是否有未完成的下载
        temp_filename = os.path.join("downloads", "AiNiee-update.zip.temp")
        if os.path.exists(temp_filename) and os.path.exists(download_info_file):
            try:
                with open(download_info_file, 'r') as f:
                    download_info = json.load(f)

                if download_info.get("status") == "paused":
                    # 有未完成的下载，提示是否继续
                    msg_box = MessageBox(
                        self.tra("继续下载"),
                        self.tra("发现未完成的下载，是否继续？"),
                        self.main_window
                    )
                    msg_box.yesButton.setText(self.tra("继续下载"))
                    msg_box.cancelButton.setText(self.tra("重新下载"))

                    if msg_box.exec():
                        # 继续下载，直接调用下载函数
                        self._start_download_with_url(download_info.get("url"))
                        return
                    else:
                        # 重新下载，删除临时文件
                        try:
                            os.remove(temp_filename)
                            os.remove(download_info_file)
                        except Exception as e:
                            self.error(f"Error removing temporary files: {e}")
            except Exception as e:
                self.error(f"Error checking paused download: {e}")

        # 检查更新
        has_update, latest_version = self.check_for_updates()
        

        # 创建更新对话框
        self.update_dialog = QDialog(self.main_window)
        self.update_dialog.setWindowTitle(self.tra("软件更新"))
        self.update_dialog.setMinimumWidth(400)

        # 创建布局
        layout = QVBoxLayout()

        # 版本信息
        version_label = QLabel(f"{self.tra('当前版本')}: {self.current_version}")
        latest_version_label = QLabel(f"{self.tra('最新版本')}: {latest_version}")
        layout.addWidget(version_label)
        layout.addWidget(latest_version_label)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()

        self.update_button = QPushButton(self.tra("开始更新"))
        self.update_button.clicked.connect(self._start_update)

        self.pause_button = QPushButton(self.tra("暂停"))
        self.pause_button.clicked.connect(self._pause_update)
        self.pause_button.setEnabled(False)
        self.pause_button.setVisible(False)

        self.resume_button = QPushButton(self.tra("继续"))
        self.resume_button.clicked.connect(self._resume_update)
        self.resume_button.setEnabled(False)
        self.resume_button.setVisible(False)

        self.cancel_button = QPushButton(self.tra("取消"))
        self.cancel_button.clicked.connect(self._cancel_update)

        self.view_release_button = QPushButton(self.tra("查看发布页"))
        self.view_release_button.clicked.connect(self._open_release_page)

        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.resume_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.view_release_button)

        layout.addLayout(button_layout)

        self.update_dialog.setLayout(layout)
        self.update_dialog.exec_()

    def _start_download_with_url(self, url):
        """使用指定URL开始下载"""
        # 重置标志
        self._cancel_download = False
        self._pause_download = False

        # 更新UI
        self.progress_bar.setVisible(True)
        self.status_label.setText(self.tra("正在下载更新..."))
        self.update_button.setEnabled(False)
        self.pause_button.setVisible(True)
        self.pause_button.setEnabled(True)
        self.resume_button.setVisible(False)

        # 启动下载线程
        self.download_thread = threading.Thread(
            target=self._download_update,
            args=(url,)
        )
        self.download_thread.daemon = True
        self.download_thread.start()

    def _start_update(self):
        """开始更新进程"""
        self.progress_bar.setVisible(True)
        self.status_label.setText(self.tra("正在获取下载链接..."))
        self.update_button.setEnabled(False)

        # 获取下载 URL
        try:
            response = requests.get(self.GITHUB_API_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                download_url = None

                # 查找.zip扩展名的资产
                for asset in data["assets"]:
                    if asset["name"].endswith(".zip"):
                        download_url = asset["browser_download_url"]
                        break

                if download_url:
                    # 使用下载链接开始下载
                    self._start_download_with_url(download_url)
                else:
                    self.status_label.setText(self.tra("未找到下载文件"))
                    self.update_button.setEnabled(True)
                    self.pause_button.setVisible(False)
            else:
                self.status_label.setText(self.tra("获取下载链接失败"))
                self.update_button.setEnabled(True)
                self.pause_button.setVisible(False)
        except Exception as e:
            self.error(f"Error starting update: {e}")
            self.status_label.setText(self.tra("更新失败"))
            self.update_button.setEnabled(True)
            self.pause_button.setVisible(False)

    def _download_update(self, url):
        """下载更新文件，支持断点续传"""
        try:
            # 如果目录不存在，则创建
            os.makedirs("downloads", exist_ok=True)

            # 完成的文件名和临时文件名
            local_filename = os.path.join("downloads", "AiNiee-update.zip")
            temp_filename = os.path.join("downloads", "AiNiee-update.zip.temp")
            download_info_file = os.path.join("downloads", "download_info.json")

            # 检查是否已经存在完成的文件
            if os.path.exists(local_filename):
                self.info(f"Found completed download file: {local_filename}")
                self.signals.download_completed.emit(local_filename)
                return

            # 获取文件大小信息
            file_size_response = requests.head(url, allow_redirects=True)
            total_size = int(file_size_response.headers.get('content-length', 0))

            # 记录下载信息
            download_info = {
                "url": url,
                "total_size": total_size,
                "downloaded": 0,
                "status": "downloading"
            }

            # 检查是否存在临时文件，如果存在则续传
            downloaded = 0
            headers = {}

            if os.path.exists(temp_filename) and os.path.exists(download_info_file):
                try:
                    with open(download_info_file, 'r') as f:
                        saved_info = json.load(f)

                    # 验证URL是否相同
                    if saved_info.get("url") == url:
                        downloaded = os.path.getsize(temp_filename)
                        if downloaded < total_size:
                            # 设置Range头部进行续传
                            headers['Range'] = f'bytes={downloaded}-'
                            self.info(f"Resuming download from {downloaded} bytes")
                            download_info["downloaded"] = downloaded
                except Exception as e:
                    self.error(f"Error reading download info: {e}")
                    downloaded = 0

            # 保存下载信息
            with open(download_info_file, 'w') as f:
                json.dump(download_info, f)

            # 开始下载
            mode = 'ab' if downloaded > 0 else 'wb'

            with requests.get(url, stream=True, headers=headers) as r:
                r.raise_for_status()
                block_size = 8192

                with open(temp_filename, mode) as f:
                    for chunk in r.iter_content(chunk_size=block_size):
                        if getattr(self, '_cancel_download', False):
                            # 取消下载
                            download_info["status"] = "canceled"
                            with open(download_info_file, 'w') as info_file:
                                json.dump(download_info, info_file)
                            self.signals.download_failed.emit(self.tra("下载已取消"))
                            return

                        if getattr(self, '_pause_download', False):
                            # 暂停下载
                            download_info["status"] = "paused"
                            download_info["downloaded"] = downloaded
                            with open(download_info_file, 'w') as info_file:
                                json.dump(download_info, info_file)

                            self.signals.download_failed.emit(self.tra("下载已暂停"))
                            return

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            download_info["downloaded"] = downloaded

                            # 定期更新下载信息
                            if downloaded % (block_size * 100) == 0:
                                with open(download_info_file, 'w') as info_file:
                                    json.dump(download_info, info_file)

                            if total_size > 0:
                                progress = int(downloaded * 100 / total_size)
                                self.signals.progress_updated.emit(progress)

            # 下载完成，将临时文件重命名为正式文件
            download_info["status"] = "completed"
            with open(download_info_file, 'w') as info_file:
                json.dump(download_info, info_file)

            # 重命名文件
            if os.path.exists(temp_filename):
                if os.path.exists(local_filename):
                    os.remove(local_filename)  # 删除已存在的文件
                os.rename(temp_filename, local_filename)
                self.info(f"Download completed and renamed to {local_filename}")

            self.signals.download_completed.emit(local_filename)
        except Exception as e:
            self.error(f"Download failed: {e}")
            self.signals.download_failed.emit(str(e))

    def _update_progress(self, progress):
        """Update the progress bar"""
        if self.progress_bar:
            self.progress_bar.setValue(progress)

    def _download_completed(self, filename):
        """Handle download completion"""
        # 先关闭更新对话框，避免UI阻塞
        if self.update_dialog:
            self.update_dialog.accept()

        # 然后显示确认对话框
        msg_box = MessageBox(
            self.tra("更新确认"),
            self.tra("下载完成，是否立即安装更新？\n\n安装过程中应用将会关闭。\n如果选择“稍后安装”，可以通过更新按钮重新安装。"),
            self.main_window
        )
        msg_box.yesButton.setText(self.tra("立即安装"))
        msg_box.cancelButton.setText(self.tra("稍后安装"))

        if msg_box.exec():
            # 通过rust更新器更新
            self._run_updater(filename)
        else:
            # 将下载的文件路径保存到配置文件中，便于稍后安装
            config = self.load_config()
            config["pending_update_file"] = filename
            self.save_config(config)

            # 显示成功提示
            if self.main_window:
                self.main_window.success_toast(
                    self.tra("更新已下载"),
                    self.tra("更新已下载，可以通过更新按钮重新安装")
                )

    def _download_failed(self, error_msg):
        """Handle download failure"""
        self.status_label.setText(f"{self.tra('下载失败')}: {error_msg}")
        self.update_button.setEnabled(True)
        self.pause_button.setVisible(False)
        self.resume_button.setVisible(False)

    def _pause_update(self):
        """Pause the update download"""
        self._pause_download = True
        self.pause_button.setEnabled(False)
        self.resume_button.setVisible(True)
        self.resume_button.setEnabled(True)
        self.status_label.setText(self.tra("下载已暂停"))

    def _resume_update(self):
        """Resume the update download"""
        self._pause_download = False
        self.resume_button.setEnabled(False)
        self.pause_button.setVisible(True)
        self.pause_button.setEnabled(True)
        self.status_label.setText(self.tra("正在下载更新..."))

    def _cancel_update(self):
        """Cancel the update process"""
        # 无论下载线程是否正在运行，都先关闭对话框
        if self.update_dialog:
            self.update_dialog.reject()

        # 如果下载线程正在运行，设置取消标志
        if self.download_thread and self.download_thread.is_alive():
            self._cancel_download = True
            # 显示取消提示（不使用info_toast，因为它需要QWidget父组件）
            self.info(self.tra("正在取消下载，请稍候..."))

    def _open_release_page(self):
        """Open the release page in browser"""
        if self.latest_version_url:
            QDesktopServices.openUrl(QUrl(self.latest_version_url))

    def _update_version_file(self, new_version):
        """更新Version文件中的版本号"""
        try:
            with open("Version", "w", encoding="utf-8") as f:
                f.write(new_version)
            self.info(f"Updated Version file to {new_version}")
            return True
        except Exception as e:
            self.error(f"Failed to update Version file: {e}")
            return False

    def _run_updater(self, update_file):
        """Run the updater executable"""
        try:
            # Get the current directory
            current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))


            import subprocess
            updater_path = os.path.join(current_dir, "updater.exe")

            if os.path.exists(updater_path):
                # 使用PowerShell启动更新器
                powershell_command = f'Start-Process -FilePath "{updater_path}" -ArgumentList "{update_file}", "{current_dir}" -WindowStyle Normal'

                # 启动PowerShell并执行命令
                subprocess.Popen([
                    "powershell.exe",
                    "-Command",
                    powershell_command
                ],
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW)

                # 退出当前程序
                os.kill(os.getpid(), signal.SIGTERM)

                # 更新Version文件
                self._update_version_file(self.latest_version)
            else:
                self.error(f"Updater not found: {updater_path}")
                self.status_label.setText(self.tra("更新程序未找到"))
        except Exception as e:
            self.error(f"Failed to run updater: {e}")
            self.status_label.setText(f"{self.tra('启动更新程序失败')}: {str(e)}")
