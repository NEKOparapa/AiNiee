"""Video picture and the existing editable, time-aligned subtitle controls."""
import json
from uuid import uuid4

from PyQt5.QtCore import QEasingCurve, QEvent, QRect, QSize, QUrl, Qt, QVariantAnimation, pyqtSignal
from PyQt5.QtNetwork import QNetworkReply, QNetworkRequest
from PyQt5.QtWidgets import QAbstractItemDelegate, QAbstractItemView, QFrame, QVBoxLayout, QWidget
from qfluentwidgets import isDarkTheme, qconfig

from Frontend.pages.media.audio_preview import AudioPreview, QMediaContent, QMediaPlayer

try:
    from PyQt5 import sip
    from PyQt5.QtMultimedia import QMediaStreamsControl
    from PyQt5.QtMultimediaWidgets import QVideoWidget
except (ImportError, OSError):
    QMediaStreamsControl = QVideoWidget = None


class VideoPreview(AudioPreview):
    subtitleTableVisibilityChanged = pyqtSignal(bool)
    MEDIA_SUFFIXES = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".flv")
    CACHE_PREFIX = "ainiee-video-"
    CACHE_SUFFIX = ".video"

    def __init__(self, parent=None):
        self._preview_reply = None
        self._preview_operation = None
        self._preview_source = ""
        self._preview_headers = {}
        self._fallback_active = False
        self._track_verified = False
        self._selecting_track = False
        self._stream_control = None
        self._headers = {}
        super().__init__(parent)
        self.setObjectName("videoPreview")
        self.table.setObjectName("videoSubtitleTable")

    def tra(self, text):
        return super().tra(text.replace("音频", "视频"))

    def _build_ui(self):
        super()._build_ui()
        self._subtitle_table_visible = False
        self._drawer_progress = 0.0
        self.picture_area = QWidget(self)
        self.picture_area.setMinimumHeight(160)
        picture_layout = QVBoxLayout(self.picture_area)
        picture_layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QVideoWidget(self.picture_area) if QVideoWidget is not None else QWidget(self.picture_area)
        self.video_widget.setObjectName("videoPicture")
        self.video_widget.setMinimumHeight(160)
        self.video_widget.setStyleSheet("background: black;")
        if QVideoWidget is not None:
            self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
            self.video_widget.videoSurface().surfaceFormatChanged.connect(self._fit_current_subtitles)
        picture_layout.addWidget(self.video_widget)
        self.layout().removeWidget(self.subtitle_panel)
        self.subtitle_panel.setParent(self.video_widget)
        self.subtitle_panel.setObjectName("videoSubtitleOverlay")
        self.subtitle_panel.setAttribute(Qt.WA_StyledBackground)
        self.subtitle_panel.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.subtitle_panel.layout().setContentsMargins(12, 8, 12, 8)
        self.subtitle_panel.hide()
        self.layout().removeWidget(self.table)
        # The drawer overlays the picture instead of reserving video space.
        # Keep both widgets non-native, including while the drawer animates.
        self.subtitle_drawer = QFrame(self.picture_area)
        self.subtitle_drawer.setObjectName("videoSubtitleDrawer")
        drawer_layout = QVBoxLayout(self.subtitle_drawer)
        drawer_layout.setContentsMargins(8, 8, 8, 8)
        drawer_layout.addWidget(self.table)
        self.subtitle_drawer.hide()
        self._drawer_animation = QVariantAnimation(self)
        self._drawer_animation.setDuration(180)
        self._drawer_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._drawer_animation.valueChanged.connect(self._set_drawer_progress)
        self._drawer_animation.finished.connect(self._finish_drawer_animation)
        self.picture_area.installEventFilter(self)
        self.video_widget.installEventFilter(self)
        qconfig.themeChangedFinished.connect(self._update_drawer_style)
        self._update_drawer_style()
        self.layout().insertWidget(0, self.picture_area, 1)

    def _update_drawer_style(self):
        background, border = ("#2b2b2b", "#454545") if isDarkTheme() else ("#ffffff", "#dedede")
        self.subtitle_drawer.setStyleSheet(
            f"QFrame#videoSubtitleDrawer {{ background: {background}; border: 1px solid {border}; border-radius: 8px; }}")
        self.subtitle_panel.setStyleSheet(
            "QWidget#videoSubtitleOverlay { background: rgba(0, 0, 0, 165); border-radius: 6px; }")
        for label in (self.current_source, self.current_translation):
            label.setStyleSheet("color: white; background: transparent;")

    def _video_picture_rect(self):
        bounds = self.video_widget.rect()
        metadata = (self.file or {}).get("media_metadata", {})
        width, height = metadata.get("width"), metadata.get("height")
        size = QSize(width, height) if type(width) is int and type(height) is int else QSize()
        if QVideoWidget is not None:
            surface = self.video_widget.videoSurface()
            if surface.isActive():
                size = surface.surfaceFormat().sizeHint()
        if not size.isEmpty():
            picture = QRect(bounds.topLeft(), size.scaled(bounds.size(), Qt.KeepAspectRatio))
            picture.moveCenter(bounds.center())
            return picture
        return bounds

    def _fit_current_subtitles(self):
        if not hasattr(self, "video_widget"):
            return
        labels = (self.current_source, self.current_translation)
        visible = [label for label in labels if label.text().strip()]
        if not visible:
            self.subtitle_panel.hide()
            return
        # Anchor to the displayed picture, including letterboxed/portrait video.
        # The panel is outside the layout, so cues never resize the picture.
        picture = self._video_picture_rect()
        margin = max(8, round(picture.width() * 0.05))
        longest = max(label.fontMetrics().horizontalAdvance(line)
                      for label in visible for line in label.text().splitlines())
        width = max(1, min(picture.width() - 2 * margin, longest + 24))
        height = 16 + (len(visible) - 1) * 2
        for label in labels:
            label.setVisible(label in visible)
            label.setMinimumHeight(0)
            if label in visible:
                line_height = max(label.fontMetrics().height(), label.heightForWidth(max(1, width - 24)))
                label.setMinimumHeight(line_height)
                height += line_height
        bottom_margin = max(8, round(picture.height() * 0.025))
        height = min(height, max(1, picture.height() - 2 * bottom_margin))
        self.subtitle_panel.setGeometry(picture.x() + (picture.width() - width) // 2,
                                        picture.bottom() + 1 - bottom_margin - height, width, height)
        self.subtitle_panel.show()
        self.subtitle_panel.raise_()

    def set_subtitle_table_visible(self, visible, *, animated=True):
        visible = bool(visible)
        if self._subtitle_table_visible == visible:
            return
        self._subtitle_table_visible = visible
        self._drawer_animation.stop()
        if visible:
            self.stop_playback()
            self.subtitle_drawer.show()
            self.subtitle_drawer.raise_()
            if self._active_row is not None and self._active_row >= 0:
                self.table.scrollToItem(self.table.item(self._active_row, 0), QAbstractItemView.EnsureVisible)
        elif self.table.state() == QAbstractItemView.EditingState:
            # Commit the editor before hiding it, including page switches.
            editor = self.table.indexWidget(self.table.currentIndex())
            if editor is not None:
                self.table.commitData(editor)
                self.table.closeEditor(editor, QAbstractItemDelegate.NoHint)
        target = 1.0 if visible else 0.0
        if animated and self.isVisible():
            self._drawer_animation.setStartValue(self._drawer_progress)
            self._drawer_animation.setEndValue(target)
            self._drawer_animation.start()
        else:
            self._set_drawer_progress(target)
            self._finish_drawer_animation()
        self.subtitleTableVisibilityChanged.emit(visible)

    def _set_drawer_progress(self, progress):
        self._drawer_progress = float(progress)
        self._position_subtitle_drawer()

    def _position_subtitle_drawer(self):
        height = self.picture_area.height()
        drawer_height = min(height, max(160, round(height * 0.65)))
        self.subtitle_drawer.setGeometry(0, height - round(drawer_height * self._drawer_progress),
                                         self.picture_area.width(), drawer_height)

    def _finish_drawer_animation(self):
        if not self._subtitle_table_visible:
            self.subtitle_drawer.hide()

    def eventFilter(self, watched, event):
        if watched is getattr(self, "picture_area", None) and event.type() == QEvent.Resize:
            self._position_subtitle_drawer()
        if watched is getattr(self, "video_widget", None) and event.type() == QEvent.Resize:
            self._fit_current_subtitles()
        return super().eventFilter(watched, event)

    def _build_player(self):
        super()._build_player()
        if self.player is not None and QVideoWidget is not None:
            # Binding the widget selects Qt's native video-window backend on
            # Windows. It calls winId(), promoting the hidden page, navigation
            # and title bar to native windows and breaking FluentWindow's
            # backing-store composition. Feed frames into the widget's surface
            # instead so it remains part of the normal QWidget paint hierarchy.
            self.player.setVideoOutput(self.video_widget.videoSurface())

    def set_file(self, file, source_url="", headers=None):
        self._headers = dict(headers or {})
        super().set_file(file, source_url, headers)
        if self._preview_reply is not None:
            self.play_button.setEnabled(False)

    def _reset_media(self):
        self._cancel_preview()
        self._fallback_active = self._track_verified = False
        super()._reset_media()

    def _ensure_audio_track(self):
        if self._selecting_track or not self.file or self.player is None:
            return False
        metadata = self.file.get("media_metadata", {})
        count = metadata.get("audio_stream_count", 1)
        if count <= 1 or self._track_verified or self._fallback_active:
            return self._preview_reply is None
        self._selecting_track = True
        try:
            # QMediaPlayer has no portable track setter. Some native backends
            # expose QMediaStreamsControl; others need a single-track remux.
            if self._stream_control is None and QMediaStreamsControl is not None:
                service = self.player.service()
                control = service.requestControl("org.qt-project.qt.mediastreamscontrol/5.0") if service else None
                if control is not None:
                    self._stream_control = sip.cast(control, QMediaStreamsControl)
            control = self._stream_control
            if control is not None:
                tracks = [i for i in range(control.streamCount()) if control.streamType(i) == control.AudioStream]
                selected = metadata.get("audio_track_index", 0)
                if len(tracks) == count and type(selected) is int and 0 <= selected < len(tracks):
                    for ordinal, index in enumerate(tracks):
                        control.setActive(index, ordinal == selected)
                    self._track_verified = all(control.isActive(index) == (ordinal == selected)
                                               for ordinal, index in enumerate(tracks))
                    if self._track_verified:
                        return True
        except (RuntimeError, TypeError, AttributeError):
            pass
        finally:
            self._selecting_track = False
        self._prepare_fallback()
        return False

    def _on_media_status(self, status):
        super()._on_media_status(status)
        if QMediaPlayer is not None and status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
            self._ensure_audio_track()

    def toggle_playback(self):
        if self._ensure_audio_track():
            super().toggle_playback()

    @staticmethod
    def _request(url, headers):
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        for name, value in headers.items():
            if isinstance(name, str) and isinstance(value, str) and not any(c in name + value for c in "\r\n"):
                request.setRawHeader(name.encode("utf-8"), value.encode("utf-8"))
        return request

    def _prepare_fallback(self):
        if self._fallback_active or self._preview_reply is not None or not self._source_url:
            return
        self.player.pause()
        self._fallback_active = True
        self.play_button.setEnabled(False)
        if "/api/v2/media/" not in self._source_url or not self._source_url.endswith("/source"):
            self._fallback_failed()
            return
        self._preview_source, self._preview_headers = self._source_url, dict(self._headers)
        self._preview_operation = uuid4().hex
        request = self._request(self._source_url.rsplit("/", 1)[0] + "/video-preview", self._headers)
        reply = self._network.post(request, json.dumps({"operation_id": self._preview_operation}).encode())
        self._preview_reply = reply
        reply.finished.connect(lambda: self._fallback_finished(reply))
        self._set_status(self.tra("正在准备默认音轨的视频预览…"))

    def _fallback_finished(self, reply):
        if reply is not self._preview_reply:
            reply.deleteLater()
            return
        self._preview_reply = None
        self._preview_operation = None
        try:
            if reply.error() != QNetworkReply.NoError:
                self._fallback_failed()
                return
            payload = json.loads(bytes(reply.readAll()))
            expected = self._preview_source.rsplit("/", 1)[0] + "/preview"
            if payload.get("url") != QUrl(expected).path():
                self._fallback_failed()
                return
            position = self._position_ms
            self._cancel_download()
            self.player.stop()
            self.player.setMedia(QMediaContent())
            self._remove_cache(self._media_path)
            self._media_path = None
            self._pending_seek = position
            self._playback_failed = False
            self._load_media(expected, self._headers)
        except (ValueError, TypeError, RuntimeError):
            self._fallback_failed()
        finally:
            reply.deleteLater()

    def _fallback_failed(self):
        self._playback_failed = True
        self.play_button.setEnabled(False)
        self._set_status(self.tra("无法准备选定音轨的视频预览；字幕仍可编辑和导出。"))

    def _cancel_preview(self):
        reply, self._preview_reply = self._preview_reply, None
        operation, self._preview_operation = self._preview_operation, None
        if reply is not None:
            reply.abort()
        if operation and "/api/v2/media/" in self._preview_source:
            base = self._preview_source.split("/api/v2/media/", 1)[0]
            cancellation = self._network.post(self._request(
                f"{base}/api/v2/media/operations/{operation}/stop", self._preview_headers), b"{}")
            cancellation.finished.connect(cancellation.deleteLater)

    def dispose(self):
        super().dispose()
        if self._stream_control is not None and self.player is not None:
            try:
                self.player.service().releaseControl(self._stream_control)
            except RuntimeError:
                pass
            self._stream_control = None
