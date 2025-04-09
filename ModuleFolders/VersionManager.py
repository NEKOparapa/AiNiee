import os
import sys
import json
import threading
import requests
from PyQt5.QtCore import QUrl, Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtGui import QDesktopServices
from qfluentwidgets import MessageBox, InfoBar, InfoBarPosition

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

        # Connect signals
        self.signals.progress_updated.connect(self._update_progress)
        self.signals.download_completed.connect(self._download_completed)
        self.signals.download_failed.connect(self._download_failed)

    def _get_current_version(self):
        """Get the current version from the Version file"""
        try:
            with open("Version", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            self.error(f"Failed to read current version: {e}")
            return "0.0.0"

    def check_for_updates(self):
        """Check if updates are available"""
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
        """Compare two version strings"""
        v1_parts = [int(x) for x in version1.split(".")]
        v2_parts = [int(x) for x in version2.split(".")]

        # Pad with zeros if needed
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

        # Check for updates first
        has_update, latest_version = self.check_for_updates()
        if not has_update:
            self.info_toast(self.tra("更新检查"), self.tra("当前已是最新版本"))
            return

        # Create update dialog
        self.update_dialog = QDialog(self.main_window)
        self.update_dialog.setWindowTitle(self.tra("软件更新"))
        self.update_dialog.setMinimumWidth(400)

        # Create layout
        layout = QVBoxLayout()

        # Version info
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

        # Buttons
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

    def _start_update(self):
        """Start the update process"""
        self.progress_bar.setVisible(True)
        self.status_label.setText(self.tra("正在下载更新..."))
        self.update_button.setEnabled(False)
        self.pause_button.setVisible(True)
        self.pause_button.setEnabled(True)
        self.resume_button.setVisible(False)

        # Get download URL
        try:
            response = requests.get(self.GITHUB_API_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                download_url = None

                # Find the asset with .zip extension
                for asset in data["assets"]:
                    if asset["name"].endswith(".zip"):
                        download_url = asset["browser_download_url"]
                        break

                if download_url:
                    # Start download in a separate thread
                    self.download_thread = threading.Thread(
                        target=self._download_update,
                        args=(download_url,)
                    )
                    self.download_thread.daemon = True
                    self.download_thread.start()
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
        """Download the update file"""
        try:
            # Create downloads directory if it doesn't exist
            os.makedirs("downloads", exist_ok=True)

            # Download file
            local_filename = os.path.join("downloads", "AiNiee-update.zip")

            # Stream the download to show progress
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                block_size = 8192
                downloaded = 0

                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=block_size):
                        if getattr(self, '_cancel_download', False):
                            # Cancel download
                            self.signals.download_failed.emit(self.tra("下载已取消"))
                            return

                        if getattr(self, '_pause_download', False):
                            # Pause download
                            while getattr(self, '_pause_download', False):
                                if getattr(self, '_cancel_download', False):
                                    self.signals.download_failed.emit(self.tra("下载已取消"))
                                    return
                                # Wait while paused
                                import time
                                time.sleep(0.5)

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = int(downloaded * 100 / total_size)
                                self.signals.progress_updated.emit(progress)

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
        self.status_label.setText(self.tra("下载完成，准备安装更新..."))
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)

        # Ask user to confirm installation
        msg_box = MessageBox(
            self.tra("更新确认"),
            self.tra("下载完成，是否立即安装更新？安装过程中应用将会关闭。"),
            self.main_window
        )
        msg_box.yesButton.setText(self.tra("安装"))
        msg_box.cancelButton.setText(self.tra("稍后安装"))

        if msg_box.exec():
            # Close the update dialog
            if self.update_dialog:
                self.update_dialog.accept()

            # Run the updater
            self._run_updater(filename)
        else:
            self.status_label.setText(self.tra("更新已下载，将在下次启动时安装"))
            self.update_button.setEnabled(True)
            self.pause_button.setVisible(False)
            self.resume_button.setVisible(False)

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
        if self.download_thread and self.download_thread.is_alive():
            self._cancel_download = True
            self.status_label.setText(self.tra("正在取消..."))
            self.update_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
        else:
            if self.update_dialog:
                self.update_dialog.reject()

    def _open_release_page(self):
        """Open the release page in browser"""
        if self.latest_version_url:
            QDesktopServices.openUrl(QUrl(self.latest_version_url))

    def _run_updater(self, update_file):
        """Run the updater executable"""
        try:
            # Get the current directory
            current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

            # Run the updater
            import subprocess
            updater_path = os.path.join(current_dir, "updater.exe")

            if os.path.exists(updater_path):
                # Start the updater and exit the application
                subprocess.Popen([
                    updater_path,
                    update_file,
                    current_dir
                ])

                # Exit the application
                self.emit(Base.EVENT.APP_SHUT_DOWN, {})
                sys.exit(0)
            else:
                self.error(f"Updater not found: {updater_path}")
                self.status_label.setText(self.tra("更新程序未找到"))
        except Exception as e:
            self.error(f"Failed to run updater: {e}")
            self.status_label.setText(f"{self.tra('启动更新程序失败')}: {str(e)}")
