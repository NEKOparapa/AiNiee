import io
import logging
import sys
import threading


class TestEnsureStdStreams:
    def test_replaces_none_stdout_with_writable_stream(self, monkeypatch):
        from ModuleFolders.Log.CrashHook import _ensure_std_streams
        monkeypatch.setattr(sys, "stdout", None)
        _ensure_std_streams()
        assert sys.stdout is not None
        sys.stdout.write("must not raise")

    def test_replaces_none_stderr_with_writable_stream(self, monkeypatch):
        from ModuleFolders.Log.CrashHook import _ensure_std_streams
        monkeypatch.setattr(sys, "stderr", None)
        _ensure_std_streams()
        assert sys.stderr is not None
        sys.stderr.write("must not raise")

    def test_leaves_existing_stdout_untouched(self, monkeypatch):
        from ModuleFolders.Log.CrashHook import _ensure_std_streams
        sentinel = io.StringIO()
        monkeypatch.setattr(sys, "stdout", sentinel)
        _ensure_std_streams()
        assert sys.stdout is sentinel

    def test_leaves_existing_stderr_untouched(self, monkeypatch):
        from ModuleFolders.Log.CrashHook import _ensure_std_streams
        sentinel = io.StringIO()
        monkeypatch.setattr(sys, "stderr", sentinel)
        _ensure_std_streams()
        assert sys.stderr is sentinel

    def test_replacement_does_not_accumulate_writes(self, monkeypatch):
        """S3: 兜底 stream 不应是 StringIO（会无界增长），应是真 sink。"""
        from ModuleFolders.Log.CrashHook import _ensure_std_streams
        monkeypatch.setattr(sys, "stdout", None)
        _ensure_std_streams()
        assert not isinstance(sys.stdout, io.StringIO)
        # write 大量内容不应该被某处缓冲；如果是 devnull，写完就丢
        for _ in range(1000):
            sys.stdout.write("x" * 1024)
        sys.stdout.flush()
        assert not hasattr(sys.stdout, "getvalue")


class TestInstallCrashHooks:
    def test_replaces_sys_excepthook(self, clean_crash_hooks):
        original = sys.excepthook
        clean_crash_hooks.install_crash_hooks()
        assert sys.excepthook is not original

    def test_replaces_threading_excepthook(self, clean_crash_hooks):
        original = threading.excepthook
        clean_crash_hooks.install_crash_hooks()
        assert threading.excepthook is not original

    def test_idempotent_does_not_double_wrap(self, clean_crash_hooks):
        clean_crash_hooks.install_crash_hooks()
        first = sys.excepthook
        clean_crash_hooks.install_crash_hooks()
        clean_crash_hooks.install_crash_hooks()
        assert sys.excepthook is first


class TestSysExcepthook:
    def test_logs_critical_with_traceback_to_file(self, tmp_log_dir, clean_crash_hooks):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        clean_crash_hooks.install_crash_hooks()
        try:
            raise RuntimeError("test boom")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "test boom" in content
        assert "[CRITICAL]" in content
        assert "Traceback" in content
        assert "RuntimeError" in content

    def test_chains_to_original_excepthook(self, clean_crash_hooks):
        captured = []

        def recorder(exc_type, exc_value, exc_tb):
            captured.append(exc_value)

        sys.excepthook = recorder
        clean_crash_hooks.install_crash_hooks()
        try:
            raise ValueError("chain me")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        assert len(captured) == 1
        assert isinstance(captured[0], ValueError)
        assert str(captured[0]) == "chain me"


class TestThreadingExcepthook:
    def test_thread_crash_logs_thread_name_and_traceback(self, tmp_log_dir, clean_crash_hooks):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        clean_crash_hooks.install_crash_hooks()

        def boomer():
            raise ValueError("thread boom")

        t = threading.Thread(target=boomer, name="ProbeThread")
        t.start()
        t.join()

        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "ProbeThread" in content
        assert "thread boom" in content
        assert "[CRITICAL]" in content

    def test_chains_to_original_threading_excepthook(self, clean_crash_hooks):
        captured = []

        def recorder(args):
            captured.append(args.exc_value)

        threading.excepthook = recorder
        clean_crash_hooks.install_crash_hooks()

        def boomer():
            raise KeyError("chained")

        t = threading.Thread(target=boomer)
        t.start()
        t.join()

        assert len(captured) == 1
        assert isinstance(captured[0], KeyError)
