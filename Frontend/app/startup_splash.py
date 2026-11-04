"""A short-lived loading window, independent of backend and main-window startup."""
import logging
import multiprocessing
import sys
import time


def _run_splash(receiver, ready):
    # Qt widgets stay on this process's main thread, keeping the loading window
    # responsive while the desktop connects to the backend and builds its UI.
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QColor, QFont, QIcon
    from PyQt5.QtWidgets import QApplication, QSplashScreen
    from Frontend.core.resources import frontend_resource_path
    from Frontend.platform.app_metadata import configure_application_metadata
    from Frontend.platform.platform_paths import ui_font_family

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(["AiNiee-loading"])
    configure_application_metadata(app, "0.0.0")
    if sys.platform == "darwin":
        # The helper has no application menu or separate Dock icon.
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    pixmap = QIcon(str(frontend_resource_path("icons", "logo.png"))).pixmap(400, 200)
    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.setEnabled(False)
    font = QFont(ui_font_family(), 10, QFont.Bold)
    splash.setFont(font)
    splash.show()

    def show_message(message):
        splash.showMessage(message, Qt.AlignBottom | Qt.AlignCenter, QColor(255, 182, 193))

    def receive_messages():
        try:
            while receiver.poll():
                show_message(receiver.recv())
        except (EOFError, OSError):
            # Also handles an unexpected parent exit, avoiding an orphan window.
            splash.close()
            app.quit()

    show_message("正在启动 AiNiee...")
    app.processEvents()
    ready.set()
    timer = QTimer(splash)
    timer.timeout.connect(receive_messages)
    timer.start(50)
    try:
        app.exec_()
    finally:
        receiver.close()


class StartupSplash:
    def __init__(self):
        context = multiprocessing.get_context("spawn")
        self._receiver, self._sender = context.Pipe(duplex=False)
        self._ready = context.Event()
        self._process = context.Process(target=_run_splash, args=(self._receiver, self._ready),
                                        name="AiNiee-loading", daemon=True)
        self._started = False

    def __enter__(self):
        try:
            self._process.start()
            self._started = True
            self._receiver.close()
            # Normally ready in well under a second. Never make a failed splash
            # prevent the real application from starting.
            deadline = time.monotonic() + 8
            while self._process.is_alive() and time.monotonic() < deadline:
                if self._ready.wait(0.05):
                    break
            if not self._ready.is_set():
                logging.getLogger("AiNiee.bootstrap").warning("加载页未及时就绪，继续启动应用")
                self.close()
        except Exception:
            logging.getLogger("AiNiee.bootstrap").exception("无法显示加载页，继续启动应用")
            self.close()
        return self

    def show_message(self, message):
        try:
            if self._started and self._process.is_alive():
                self._sender.send(message)
        except (BrokenPipeError, EOFError, OSError):
            pass

    def close(self):
        self._sender.close()
        self._receiver.close()
        if self._started:
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=2)
            self._started = False

    def __exit__(self, *exc):
        self.close()
