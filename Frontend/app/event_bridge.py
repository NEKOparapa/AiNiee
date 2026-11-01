from PyQt5.QtCore import QObject, Qt, pyqtSignal
import json
import logging

from Frontend.core.base import Base
from Frontend.core.events import EventManager
from Frontend.models.project import CacheProjectStatistics
from Frontend.services.protocol import notification_event, request_failure


class QtEventBridge(QObject):
    """Adapt named backend notifications to local UI events on the GUI thread."""
    signal = pyqtSignal(int, object)
    message = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        manager = EventManager.get_singleton()
        self.signal.connect(manager.process_event, Qt.QueuedConnection)
        manager.configure(self.signal.emit)
        self.message.connect(self.receive, Qt.QueuedConnection)
        self.cache = None
        self.window = None
        self._disconnected = False
        self._disconnect_message = None
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
                progress = {"start_time": 0, "time": 0, **status.get("stats", {}),
                    **status.get("progress", {}), "project_id": status.get("project_id", ""),
                    "active_workers": status.get("active_workers", 0),
                    "elapsed_seconds": status.get("progress", {}).get("elapsed_seconds", status.get("stats", {}).get("time", 0))}
                self.cache.project.stats_data = CacheProjectStatistics.from_dict(progress)
                manager.process_event(Base.EVENT.TASK_UPDATE, progress)
        if kind == "request_rejected":
            # Restore controls even if the request failed before a WebSocket
            # task could be created. Preserve an unrelated server task's state.
            operation = message["operation"]
            preserve_status = message.get("status", {}).get("busy") or (operation == "stop" and "status" not in message)
            server_status = Base.work_status if preserve_status else Base.STATUS.IDLE
            Base.work_status = Base.STATUS.IDLE
            failure = request_failure(operation, message.get("data", {}), message["message"])
            if failure:
                manager.process_event(*failure)
            Base.work_status = server_status
            manager.process_event(Base.EVENT.BACKEND_REQUEST_REJECTED, message)
            logging.getLogger("AiNiee.backend").error(message["message"])
            if self.window and (failure is None or operation == "translation"):
                self.window.error_toast("后端错误", message["message"])
        elif kind == "request_completed":
            if message["operation"] == "project.save" and self.window:
                self.window.success_toast("保存成功", "项目缓存已保存。")
        elif kind == "notification":
            if message["name"] == "project.export.completed":
                self._show_export_result(message.get("data", {}))
            # Full task completion is delivered once the backend has also saved/exported.
            notification = notification_event(message["name"], message.get("data", {}))
            if notification and message["name"] != "translation.stopped":
                manager.process_event(*notification)
        elif kind == "settled":
            Base.work_status = Base.STATUS.IDLE if not message["status"].get("busy") else Base.work_status
            if message["operation"] == "translation" and not message["status"].get("busy"):
                manager.process_event(Base.EVENT.TASK_STOP_DONE, {})
            if message["status"].get("last_error"):
                logging.getLogger("AiNiee.backend").error(message["status"]["last_error"])
        elif kind == "connected":
            reconnecting = self._connected_once
            self._connected_once = True
            self._disconnected = False
            self._disconnect_message = None
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
            # Export's terminal report contains its full outcome and displays the
            # error once, after persistence and operation cleanup have finished.
            if self.window and message.get("operation") != "project.export":
                self.window.error_toast("后端错误", message["message"])
        elif kind == "disconnected":
            if self._disconnected and self._disconnect_message == message["message"]:
                return
            self._disconnected = True
            self._disconnect_message = message["message"]
            logging.getLogger("AiNiee.backend").warning(message["message"])
            if self.window:
                self.window.warning_toast("连接中断", message["message"])

    def _show_export_result(self, result):
        report = result.get("report") or {}
        files = result.get("files") or []
        errors = [*(report.get("errors") or []), *(report.get("operation_errors") or [])]
        warnings = report.get("warnings") or []
        status = result.get("status")
        if status == "success" and not errors:
            feedback, title = ("warning", "导出完成（有提示）") if warnings else ("success", "导出完成")
        elif status == "partial":
            feedback, title = "warning", "导出部分完成"
        elif status in ("cancelled", "stopped"):
            feedback, title = "info", "导出已停止"
        else:
            feedback, title = "error", "导出失败"

        logger = logging.getLogger("AiNiee.backend")
        level = {"error": logging.ERROR, "warning": logging.WARNING}.get(feedback, logging.INFO)
        # A normal logger reaches both the GUI and the frontend file handler.
        # The complete report stays in the file even if the GUI truncates it.
        logger.log(level, "完整导出报告：%s", json.dumps(result, ensure_ascii=False))
        for error in errors:
            # Individual failures remain readable in the GUI for large projects.
            logger.error("导出失败详情：%s", json.dumps(error, ensure_ascii=False))

        summary = f"已生成 {len(files)} 个文件。"
        if errors:
            first = errors[0]
            detail = "：".join(str(first.get(key)) for key in ("code", "path", "message") if first.get(key)) if isinstance(first, dict) else str(first)
            if len(detail) > 300:
                detail = detail[:300] + "…"
            summary += f"{len(errors)} 项失败。{detail}"
        elif result.get("message"):
            summary += str(result["message"])
        elif warnings:
            summary += f"{len(warnings)} 项提示。"
        summary += "完整详情见运行日志及日志文件。"
        if self.window:
            getattr(self.window, f"{feedback}_toast")(title, summary)
