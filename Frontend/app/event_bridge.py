from PyQt5.QtCore import QObject, Qt, pyqtSignal
import logging

from Frontend.core.base import Base
from Frontend.core.events import EventManager
from Frontend.models.project import CacheProjectStatistics
from Frontend.services.protocol import command_failure


class QtEventBridge(QObject):
    """Marshal incoming backend events onto the GUI thread."""
    signal = pyqtSignal(int, object)
    message = pyqtSignal(object)

    def __init__(self, parent=None, command_sender=None):
        super().__init__(parent)
        manager = EventManager.get_singleton()
        self.signal.connect(manager.process_event, Qt.QueuedConnection)
        manager.configure(self.signal.emit, command_sender)
        self.message.connect(self.receive, Qt.QueuedConnection)
        self.cache = None
        self.window = None
        self._disconnected = False
        self._connected_once = False

    def receive(self, message):
        manager = EventManager.get_singleton()
        kind = message["type"]
        if "project" in message and self.cache is not None:
            self.cache.apply_snapshot(message["project"])
        if "status" in message:
            status = message["status"]
            Base.work_status = status["work_status_code"]
            if not status.get("busy") and Base.work_status == Base.STATUS.TASKSTOPPED:
                Base.work_status = Base.STATUS.IDLE
            if self.cache and self.cache.project:
                progress = {**status.get("stats", {}), "active_workers": status.get("active_workers", 0),
                    "elapsed_seconds": status.get("progress", {}).get("elapsed_seconds", status.get("stats", {}).get("time", 0))}
                self.cache.project.stats_data = CacheProjectStatistics.from_dict(progress)
                manager.process_event(Base.EVENT.TASK_UPDATE, progress)
        if kind == "command_rejected":
            # Restore controls even if the request failed before a WebSocket
            # task could be created. Preserve an unrelated server task's state.
            server_status = Base.work_status if message.get("status", {}).get("busy") else Base.STATUS.IDLE
            Base.work_status = Base.STATUS.IDLE
            failure = command_failure(message["event"], message.get("data", {}), message["message"])
            if failure:
                manager.process_event(*failure)
            Base.work_status = server_status
            logging.getLogger("AiNiee.backend").error(message["message"])
            if self.window and (failure is None or message["event"] in (
                Base.EVENT.TASK_START, Base.EVENT.TABLE_TRANSLATE_START,
                Base.EVENT.TABLE_POLISH_START, Base.EVENT.TABLE_PROOFREAD_START,
            )):
                self.window.error_toast("后端错误", message["message"])
        elif kind == "event":
            # Full task completion is delivered once the backend has also saved/exported.
            if message["event"] != Base.EVENT.TASK_STOP_DONE:
                manager.process_event(message["event"], message["data"])
        elif kind == "settled":
            Base.work_status = Base.STATUS.IDLE if not message["status"].get("busy") else Base.work_status
            if message["event"] == Base.EVENT.TASK_START and not message["status"].get("busy"):
                manager.process_event(Base.EVENT.TASK_STOP_DONE, {})
            if message["status"].get("last_error"):
                logging.getLogger("AiNiee.backend").error(message["status"]["last_error"])
        elif kind == "connected":
            reconnecting = self._connected_once
            self._connected_once = True
            self._disconnected = False
            logging.getLogger("AiNiee.backend").info("已连接 FastAPI 后端")
            if self.window:
                if reconnecting:
                    glossary = getattr(self.window, "prompt_dictionary_page", None)
                    if glossary is not None:
                        glossary.refresh_after_reconnect()
                view = self.window.edit_view_page
                if not message["status"].get("busy"):
                    manager.process_event(Base.EVENT.TASK_STOP_DONE, {})
                if self.cache and self.cache.project:
                    view.on_folder_selected(self.cache.project.project_name, "continue")
                    if message["status"].get("busy") and Base.work_status in (Base.STATUS.TASKING, Base.STATUS.STOPING):
                        bar = view.translation_page.bottom_bar
                        bar.start_btn.setEnabled(False)
                        bar.update_task_action_button(bar.ACTION_STOP)
                elif Base.work_status == Base.STATUS.IDLE:
                    view.on_back_button_clicked()
        elif kind == "log":
            from Frontend.core.log_system import get_gui_handler
            record = logging.LogRecord("AiNiee.backend", getattr(logging, message["level"], logging.INFO), "", 0, message["line"], (), None)
            record.ainiee_gui_style = message.get("style", "")
            record.ainiee_gui_rows = message.get("rows")
            get_gui_handler().emit(record)
        elif kind == "error":
            logging.getLogger("AiNiee.backend").error(message["message"])
            if self.window:
                self.window.error_toast("后端错误", message["message"])
        elif kind == "disconnected" and not self._disconnected:
            self._disconnected = True
            logging.getLogger("AiNiee.backend").warning(message["message"])
            if self.window:
                self.window.warning_toast("连接中断", message["message"])
