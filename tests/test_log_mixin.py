import inspect
import logging


class TestSignatureCompat:
    """LogMixin is consumed by ~20 modules; signatures must stay backward compatible."""

    def test_print_signature_is_self_msg(self):
        from ModuleFolders.Log.Log import LogMixin
        assert list(inspect.signature(LogMixin.print).parameters) == ["self", "msg"]

    def test_info_signature_is_self_msg(self):
        from ModuleFolders.Log.Log import LogMixin
        assert list(inspect.signature(LogMixin.info).parameters) == ["self", "msg"]

    def test_warning_signature_is_self_msg(self):
        from ModuleFolders.Log.Log import LogMixin
        assert list(inspect.signature(LogMixin.warning).parameters) == ["self", "msg"]

    def test_error_accepts_optional_exception(self):
        from ModuleFolders.Log.Log import LogMixin
        params = inspect.signature(LogMixin.error).parameters
        assert list(params) == ["self", "msg", "error"]
        assert params["error"].default is None

    def test_debug_accepts_optional_exception(self):
        from ModuleFolders.Log.Log import LogMixin
        params = inspect.signature(LogMixin.debug).parameters
        assert list(params) == ["self", "msg", "error"]
        assert params["error"].default is None


class TestDualOutput:
    def _demo_class(self):
        from ModuleFolders.Log.Log import LogMixin

        class Demo(LogMixin):
            pass

        return Demo

    def test_info_writes_to_console_and_file(self, tmp_log_dir, capsys):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        self._demo_class()().info("dual write")
        for h in logging.getLogger().handlers:
            h.flush()
        assert "dual write" in path.read_text()
        assert "dual write" in capsys.readouterr().out

    def test_warning_writes_to_console_and_file(self, tmp_log_dir, capsys):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        self._demo_class()().warning("be careful")
        for h in logging.getLogger().handlers:
            h.flush()
        assert "be careful" in path.read_text()
        assert "be careful" in capsys.readouterr().out

    def test_print_writes_to_console_and_file(self, tmp_log_dir, capsys):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        self._demo_class()().print("hi")
        for h in logging.getLogger().handlers:
            h.flush()
        assert "hi" in path.read_text()
        assert "hi" in capsys.readouterr().out

    def test_error_without_exception_logs_message_only(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        self._demo_class()().error("simple err")
        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "simple err" in content
        assert "[ERROR]" in content
        assert "Traceback" not in content

    def test_error_with_exception_includes_traceback_in_file(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        try:
            raise RuntimeError("inner cause")
        except RuntimeError as e:
            self._demo_class()().error("outer wrap", e)
        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "outer wrap" in content
        assert "RuntimeError: inner cause" in content
        assert "Traceback" in content

    def test_debug_with_exception_includes_traceback_in_file(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        logging.getLogger().setLevel(logging.DEBUG)
        try:
            try:
                raise KeyError("missing")
            except KeyError as e:
                self._demo_class()().debug("dbg wrap", e)
            for h in logging.getLogger().handlers:
                h.flush()
            content = path.read_text()
            assert "dbg wrap" in content
            assert "KeyError" in content
            assert "Traceback" in content
        finally:
            logging.getLogger().setLevel(logging.WARNING)


class TestLoggerNaming:
    def test_logger_name_matches_instance_module(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        from ModuleFolders.Log.Log import LogMixin
        init_file_logging()

        class Demo(LogMixin):
            pass

        assert Demo()._logger().name == Demo.__module__


class TestPublicSurface:
    def test_star_import_only_exposes_log_mixin(self):
        """S7: 模块顶部 `from rich import print` 会 shadow builtin；
        通过 __all__ 限定 star import 不污染调用方"""
        import ModuleFolders.Log.Log as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ("LogMixin",) or mod.__all__ == ["LogMixin"]
        # 模拟 from ... import *
        exported = {name: getattr(mod, name) for name in mod.__all__}
        assert "print" not in exported
        assert "traceback" not in exported
        assert "logging" not in exported
        assert "LogMixin" in exported
