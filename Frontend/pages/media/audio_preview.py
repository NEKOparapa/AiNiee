"""Audio playback and time-aligned subtitle preview for model-owned workspaces."""
from bisect import bisect_right
import copy
import math
import os
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QHeaderView, QHBoxLayout,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon, PushButton, Slider, StrongBodyLabel, TableWidget, isDarkTheme

from Frontend.core.config import ConfigMixin

try:
    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
except (ImportError, OSError):  # Subtitle editing still works without a media service.
    QMediaContent = QMediaPlayer = None


def format_time(milliseconds, *, precise=False):
    """Display a millisecond timestamp, including hours for long recordings."""
    milliseconds = max(0, int(milliseconds))
    seconds, fraction = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    value = f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"
    return f"{value}.{fraction:03}" if precise else value


class SubtitleTimeline(QWidget):
    """A compact seekable overview; bars represent cues, not an audio waveform."""
    seekRequested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration_ms = 0
        self.position_ms = 0
        self.segments = []
        self.setMinimumHeight(46)
        self.setMaximumHeight(50)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName("字幕时间轴")

    def set_segments(self, segments, duration_ms):
        self.segments = [(item["start_ms"], item["end_ms"]) for item in segments]
        self.duration_ms = max(0, int(duration_ms))
        self.position_ms = min(self.position_ms, self.duration_ms)
        self.update()

    def set_position(self, position_ms):
        self.position_ms = max(0, min(int(position_ms), self.duration_ms))
        self.update()

    def position_at(self, x):
        width = max(1, self.width() - 24)
        return round(max(0.0, min(1.0, (x - 12) / width)) * self.duration_ms)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.duration_ms:
            self.seekRequested.emit(self.position_at(event.pos().x()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.duration_ms and event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End):
            target = {Qt.Key_Left: self.position_ms - 5000, Qt.Key_Right: self.position_ms + 5000,
                      Qt.Key_Home: 0, Qt.Key_End: self.duration_ms}[event.key()]
            self.seekRequested.emit(max(0, min(target, self.duration_ms)))
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = max(1, self.width() - 24)
        label_baseline = painter.fontMetrics().ascent() + 2
        track_y = label_baseline + 7
        dark = isDarkTheme()
        painter.fillRect(12, track_y, width, 12, QColor("#30343d" if dark else "#e8edf5"))
        if not self.duration_ms:
            painter.setPen(QColor("#b7c0cd" if dark else "#607086"))
            painter.drawText(self.rect(), Qt.AlignCenter, "00:00")
            return
        painter.setPen(Qt.NoPen)
        for start, end in self.segments:
            x = 12 + width * min(start, self.duration_ms) / self.duration_ms
            extent = width * (min(end, self.duration_ms) - min(start, self.duration_ms)) / self.duration_ms
            painter.setBrush(QColor("#70a9f5" if start <= self.position_ms < end else "#8397b5"))
            painter.drawRoundedRect(round(x), track_y + 1, max(2, round(extent)), 10, 2, 2)
        painter.setPen(QColor("#bbc4d0" if dark else "#526277"))
        for index in range(5):
            stamp = round(self.duration_ms * index / 4)
            x = round(12 + width * index / 4)
            label = format_time(stamp)
            text_width = painter.fontMetrics().horizontalAdvance(label)
            painter.drawText(max(0, min(self.width() - text_width, x - text_width // 2)), label_baseline, label)
        x = round(12 + width * self.position_ms / self.duration_ms)
        painter.setPen(QPen(QColor("#3185ed"), 2))
        painter.drawLine(x, track_y - 4, x, track_y + 16)


class AudioPreview(QWidget, ConfigMixin):
    """Display one wire-format CacheFile without mutating the supplied model.

    ``translationEdited`` carries the stable item ID, never a visual row index.
    ``stop_playback`` pauses when leaving a page and retains its playhead.
    """
    translationEdited = pyqtSignal(str, str)
    MEDIA_SUFFIXES = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".wma")
    CACHE_PREFIX = "ainiee-audio-"
    CACHE_SUFFIX = ".audio"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("audioPreview")
        self.file = None
        self.segments = []
        self._starts = []
        self._duration_ms = 0
        self._position_ms = 0
        self._file_id = ""
        self._source_url = ""
        self._active_row = -1
        self._loading = False
        self._subtitle_status = ""
        self._editable = True
        self._closed = False
        self._playback_failed = False
        self._downloading = False
        self._reply = None
        self._download_file = None
        self._download_path = None
        self._media_path = None
        self._pending_seek = None
        self._network = QNetworkAccessManager(self)
        self.player = None
        self._build_ui()
        self._build_player()
        self.set_file(None)
        if QApplication.instance() is not None:
            QApplication.instance().aboutToQuit.connect(self.dispose)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.timeline = SubtitleTimeline(self)
        self.timeline.seekRequested.connect(self.seek)
        self.subtitle_panel = QWidget(self)
        subtitle_layout = QVBoxLayout(self.subtitle_panel)
        subtitle_layout.setContentsMargins(0, 0, 0, 0)
        subtitle_layout.setSpacing(2)
        self.current_source = BodyLabel(self)
        self.current_translation = StrongBodyLabel(self)
        for label in (self.current_source, self.current_translation):
            label.setWordWrap(True)
            label.setTextFormat(Qt.PlainText)
            label.setAlignment(Qt.AlignCenter)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setMinimumHeight(20)
            subtitle_layout.addWidget(label)
        self.table = TableWidget(self)
        self.table.setObjectName("audioSubtitleTable")
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([self.tra("开始"), self.tra("结束"), self.tra("原文"), self.tra("译文")])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setWordWrap(True)
        self.table.setSortingEnabled(False)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        header = self.table.horizontalHeader()
        for column in (0, 1):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
            self.table.setColumnWidth(column, 112)
        for column in (2, 3):
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        self.table.cellClicked.connect(self._select_cue)
        self.table.itemChanged.connect(self._edit_translation)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.timeline)
        layout.addWidget(self.subtitle_panel)

        self.status_label = CaptionLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status_label)
        bar = QFrame(self)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        self.play_button = PushButton(FluentIcon.PLAY, self.tra("播放"), bar)
        self.play_button.setAccessibleName(self.tra("播放或暂停音频"))
        self.play_button.clicked.connect(self.toggle_playback)
        bar_layout.addWidget(self.play_button)
        self.position_label = CaptionLabel("00:00 / 00:00", bar)
        self.position_label.setMinimumWidth(112)
        bar_layout.addWidget(self.position_label)
        bar_layout.addStretch(1)
        self.translation_progress_label = CaptionLabel(bar)
        self.translation_progress_label.setAccessibleName(self.tra("字幕翻译进度"))
        bar_layout.addWidget(self.translation_progress_label)
        bar_layout.addWidget(CaptionLabel(self.tra("音量"), bar))
        self.volume_slider = Slider(Qt.Horizontal, bar)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.setAccessibleName(self.tra("音量"))
        self.volume_slider.valueChanged.connect(self._set_volume)
        bar_layout.addWidget(self.volume_slider)
        layout.addWidget(bar)

    def _build_player(self):
        if QMediaPlayer is None:
            return
        # Qt caches its multimedia provider when the first player is created.
        # Audio is initialized before video in the main window, so choose the
        # Windows built-in decoder here, not only in VideoPreview. Respect an
        # explicitly configured provider and restore the process environment.
        preference = "QT_MULTIMEDIA_PREFERRED_PLUGINS"
        prefer_wmf = os.name == "nt" and preference not in os.environ
        try:
            if prefer_wmf:
                os.environ[preference] = "windowsmediafoundation"
            self.player = QMediaPlayer(self)
            self.player.setNotifyInterval(80)
            self.player.setVolume(self.volume_slider.value())
            self.player.positionChanged.connect(self._on_position_changed)
            self.player.durationChanged.connect(self._on_duration_changed)
            self.player.stateChanged.connect(self._on_state_changed)
            self.player.mediaStatusChanged.connect(self._on_media_status)
            self.player.error.connect(self._on_media_error)
        except (RuntimeError, OSError):
            self.player = None
        finally:
            if prefer_wmf:
                os.environ.pop(preference, None)

    @staticmethod
    def _valid_segments(file):
        result, invalid = [], 0
        for item in file.get("items", []):
            if not isinstance(item, dict):
                invalid += 1
                continue
            locator = item.get("locator") or {}
            if not isinstance(locator, dict):
                invalid += 1
                continue
            start, end = locator.get("start_ms"), locator.get("end_ms")
            if (locator.get("kind") not in ("audio", "video") or type(start) is not int or type(end) is not int
                    or not 0 <= start < end or not isinstance(item.get("item_id"), str)):
                invalid += 1
                continue
            result.append({"item_id": item["item_id"], "start_ms": start, "end_ms": end,
                           "source_text": str(item.get("source_text") or ""),
                           "translated_text": str(item.get("translated_text") or "")})
        result.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
        return result, invalid

    def set_file(self, file, source_url="", headers=None):
        if self._closed:
            return
        file = copy.deepcopy(file) if isinstance(file, dict) else None
        file_id = str(file.get("file_id", "")) if file else ""
        same_media = bool(file and file_id and file_id == self._file_id and source_url == self._source_url)
        if not same_media:
            self._reset_media()
        self.file, self._file_id, self._source_url = file, file_id, source_url
        self.segments, invalid = self._valid_segments(file) if file else ([], 0)
        self._starts = [segment["start_ms"] for segment in self.segments]
        duration = (file.get("media_metadata") or {}).get("duration_ms", 0) if file else 0
        if not isinstance(duration, (int, float)) or not math.isfinite(duration):
            duration = 0
        self._duration_ms = max(0, int(duration), max((segment["end_ms"] for segment in self.segments), default=0))
        items = file.get("items", []) if file else []
        completed = sum(isinstance(item, dict) and item.get("translation_status") in (1, 2)
                        and bool(item.get("translated_text")) for item in items)
        self.set_translation_progress(completed, len(items))
        self._loading = True
        try:
            self.table.setRowCount(len(self.segments))
            for row, segment in enumerate(self.segments):
                values = [format_time(segment["start_ms"], precise=True), format_time(segment["end_ms"], precise=True),
                          segment["source_text"], segment["translated_text"]]
                for column, text in enumerate(values):
                    cell = QTableWidgetItem(text)
                    cell.setData(Qt.UserRole, segment["item_id"])
                    cell.setToolTip(text)
                    if column != 3 or not self._editable:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, column, cell)
                self.table.setRowHeight(row, 70)
        finally:
            self._loading = False
        self.timeline.set_segments(self.segments, self._duration_ms)
        self._subtitle_status = ("" if self.segments else self.tra("转录完成后将在这里显示时间轴与字幕。")
                                 if file else self.tra("从左侧选择一个音频文件。"))
        if invalid:
            self._subtitle_status = self.tra("{0} 条字幕时间信息无效，已跳过预览。").format(invalid)
        self._set_status(self._subtitle_status)
        if file and source_url and not same_media:
            self._load_media(source_url, headers or {})
        elif file and not source_url:
            self._set_status(self.tra("音频预览地址不可用，仍可查看和编辑字幕。"))
        self.volume_slider.setEnabled(self._player_available())
        self.play_button.setEnabled(bool(file and source_url and self._player_available()
                                         and not self._playback_failed and not self._downloading))
        self._active_row = None
        self._on_position_changed(self._position_ms if same_media else 0)

    def set_translation_progress(self, completed, total):
        total = max(0, int(total))
        completed = max(0, min(int(completed), total))
        self.translation_progress_label.setText(self.tra("已译 {0} / {1} 条").format(completed, total))

    def _set_status(self, message):
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))

    def _player_available(self):
        return self.player is not None and self.player.isAvailable()

    def _load_media(self, source_url, headers):
        if not self._player_available():
            self._set_status(self.tra("当前系统没有可用音频播放器，字幕预览和编辑仍可使用。"))
            return
        url = QUrl(source_url)
        if not url.isValid() or url.scheme().lower() not in ("http", "https", "file"):
            self._playback_failed = True
            self._set_status(self.tra("音频预览地址无效。"))
            return
        request = QNetworkRequest(url)
        for name, value in headers.items():
            if isinstance(name, str) and isinstance(value, str) and not any(c in name + value for c in "\r\n"):
                request.setRawHeader(name.encode("utf-8"), value.encode("utf-8"))
        if headers and url.scheme().lower() in ("http", "https"):
            # Windows DirectShow silently drops QMediaContent's HTTP headers.
            # Qt's network stack must perform authenticated transfers; the native
            # decoder then reads a seekable local file. No credentials enter URLs.
            self._start_authenticated_download(request)
            return
        try:
            self.player.setMedia(QMediaContent(request))
        except (RuntimeError, OSError):
            self._playback_failed = True
            self._set_status(self.tra("音频无法加载，请检查连接或系统音频解码器。"))

    def _start_authenticated_download(self, request):
        suffix = PurePosixPath(str(self.file.get("storage_path", "")).replace("\\", "/")).suffix.lower()
        if suffix not in self.MEDIA_SUFFIXES:
            suffix = self.CACHE_SUFFIX
        try:
            temporary = NamedTemporaryFile(prefix=self.CACHE_PREFIX, suffix=suffix, delete=False)
        except OSError:
            self._playback_failed = True
            self._set_status(self.tra("无法创建音频预览缓存，请检查临时目录可用空间。"))
            return
        self._download_file = temporary
        self._download_path = Path(temporary.name)
        self._downloading = True
        self._set_status(self.tra("正在下载音频供本地预览…"))
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.ManualRedirectPolicy)
        reply = self._network.get(request)
        self._reply = reply
        reply.setReadBufferSize(1024 * 1024)
        reply.readyRead.connect(lambda: self._download_ready(reply))
        reply.downloadProgress.connect(lambda received, total: self._download_progress(reply, received, total))
        reply.finished.connect(lambda: self._download_finished(reply))

    def _download_ready(self, reply):
        if reply is not self._reply or self._download_file is None:
            return
        data = bytes(reply.readAll())
        try:
            written = self._download_file.write(data)
        except OSError:
            written = -1
        if written != len(data):
            self._download_failed(self.tra("音频预览缓存写入失败，请检查磁盘空间。"))

    def _download_progress(self, reply, received, total):
        if reply is self._reply:
            progress = f"{received / 1048576:.1f} MB"
            if total > 0:
                progress += f" / {total / 1048576:.1f} MB"
            self._set_status(self.tra("正在下载音频供本地预览：{0}").format(progress))

    def _download_finished(self, reply):
        if reply is not self._reply:
            reply.deleteLater()
            return
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if reply.error() != QNetworkReply.NoError or not isinstance(status, int) or status != 200:
            self._download_failed(self.tra("音频下载失败，请检查后端连接或访问令牌。"))
            return
        self._download_ready(reply)
        if reply is not self._reply:
            return
        temporary = self._download_file
        path, self._download_path = self._download_path, None
        self._reply = self._download_file = None
        self._downloading = False
        reply.deleteLater()
        try:
            temporary.close()
        except OSError:
            self._remove_cache(path)
            self._playback_failed = True
            self._set_status(self.tra("音频预览缓存写入失败，请检查磁盘空间。"))
            return
        self._media_path = path
        self._pending_seek = self._position_ms
        try:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(str(path))))
        except (RuntimeError, OSError):
            self._playback_failed = True
            self._set_status(self.tra("音频无法加载，请检查系统音频解码器。"))
        self.play_button.setEnabled(not self._playback_failed)
        if not self._playback_failed:
            self._set_status(self._subtitle_status)

    def _download_failed(self, message):
        self._cancel_download()
        self._playback_failed = True
        self.play_button.setEnabled(False)
        self._set_status(message)

    def _cancel_download(self):
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()
        if self._download_file is not None:
            try:
                self._download_file.close()
            except OSError:
                pass
            self._download_file = None
        self._remove_cache(self._download_path)
        self._download_path = None
        self._downloading = False

    @staticmethod
    def _remove_cache(path):
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass  # A native decoder may release its handle just after close.

    def _reset_media(self):
        self._cancel_download()
        if self.player is not None:
            self.player.stop()
            self.player.setMedia(QMediaContent())
        self._remove_cache(self._media_path)
        self._media_path = None
        self._position_ms = 0
        self._pending_seek = None
        self._playback_failed = False
        self._active_row = -1
        self._on_state_changed(0)

    def set_editable(self, editable):
        self._editable = bool(editable)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 3)
            if item:
                item.setFlags((item.flags() | Qt.ItemIsEditable) if self._editable else (item.flags() & ~Qt.ItemIsEditable))

    def _edit_translation(self, cell):
        if self._loading or not self._editable or cell.column() != 3:
            return
        identity = cell.data(Qt.UserRole)
        segment = next((item for item in self.segments if item["item_id"] == identity), None)
        if segment is None or cell.text() == segment["translated_text"]:
            return
        segment["translated_text"] = cell.text()
        self.translationEdited.emit(identity, cell.text())
        if self._active_row == cell.row():
            self.current_translation.setText(cell.text())
            self._fit_current_subtitles()

    def _select_cue(self, row, column):
        if 0 <= row < len(self.segments):
            self.seek(self.segments[row]["start_ms"])

    def seek(self, milliseconds):
        if not self.file:
            return
        position = max(0, min(int(milliseconds), self._duration_ms))
        if self.player is not None and self._source_url:
            self.player.setPosition(position)
        self._on_position_changed(position)

    def toggle_playback(self):
        if (not self.file or not self._source_url or not self._player_available()
                or self._playback_failed or self._downloading):
            return
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if self._position_ms >= self._duration_ms:
                self.seek(0)
            self.player.play()

    def stop_playback(self):
        if self.player is not None:
            self.player.pause()

    def _set_volume(self, value):
        if self.player is not None:
            self.player.setVolume(value)

    def _on_state_changed(self, state):
        playing = QMediaPlayer is not None and state == QMediaPlayer.PlayingState
        self.play_button.setIcon(FluentIcon.PAUSE if playing else FluentIcon.PLAY)
        self.play_button.setText(self.tra("暂停") if playing else self.tra("播放"))

    def _on_duration_changed(self, duration):
        if self.file and duration > 0:
            self._duration_ms = max(int(duration), max((s["end_ms"] for s in self.segments), default=0))
            self.timeline.set_segments(self.segments, self._duration_ms)
            self._on_position_changed(self._position_ms)

    def _on_position_changed(self, position):
        self._position_ms = max(0, min(int(position), self._duration_ms))
        self.timeline.set_position(self._position_ms)
        self.position_label.setText(f"{format_time(self._position_ms)} / {format_time(self._duration_ms)}")
        upper = bisect_right(self._starts, self._position_ms)
        row = next((i for i in range(upper - 1, -1, -1) if self._position_ms < self.segments[i]["end_ms"]), -1)
        if row == self._active_row:
            return
        self._active_row = row
        self.current_source.setText(self.segments[row]["source_text"] if row >= 0 else "")
        self.current_translation.setText(self.segments[row]["translated_text"] if row >= 0 else "")
        self._fit_current_subtitles()
        if self.table.state() != QAbstractItemView.EditingState:
            if row >= 0:
                self.table.selectRow(row)
                self.table.scrollToItem(self.table.item(row, 0), QAbstractItemView.EnsureVisible)
            else:
                self.table.clearSelection()

    def _fit_current_subtitles(self):
        width = max(1, self.contentsRect().width())
        for label in (self.current_source, self.current_translation):
            # QLabel's heightForWidth includes its previous minimum height.
            # Reset that floor so shorter cues can return to a compact line.
            label.setMinimumHeight(20)
            label.setMinimumHeight(max(20, label.heightForWidth(width)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_current_subtitles()

    def _on_media_status(self, status):
        if QMediaPlayer is not None and status == QMediaPlayer.InvalidMedia:
            self._on_media_error()
        elif (QMediaPlayer is not None and status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia)
              and self._pending_seek is not None):
            position, self._pending_seek = self._pending_seek, None
            self.seek(position)

    def _on_media_error(self, *args):
        if not self.file or self.player is None:
            return
        if self.player.error() == QMediaPlayer.NoError:
            return
        self._playback_failed = True
        self.play_button.setEnabled(False)
        self._set_status(self.tra("音频无法播放，请检查后端连接和系统音频解码器；字幕仍可预览、编辑和导出。"))

    def clear(self):
        self.set_file(None)

    def hideEvent(self, event):
        self.stop_playback()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)

    def dispose(self):
        """Release native playback and downloaded media when the app exits."""
        if not self._closed:
            self._reset_media()
            self._closed = True
