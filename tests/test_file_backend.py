import logging
import os
import time


def _make_record(msg, level=logging.INFO):
    return logging.LogRecord(
        name="test", level=level, pathname=__file__, lineno=1,
        msg=msg, args=None, exc_info=None,
    )


class TestSensitiveFilter:
    def test_redacts_openai_style_key(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record("call: sk-abcdefghijklmnopqrstuvwxyz1234567890")
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "sk-abc" not in rec.getMessage()

    def test_redacts_anthropic_key(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record("key=sk-ant-api03-xyzABC1234567890ABCDEF end")
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "sk-ant-api03" not in rec.getMessage()

    def test_redacts_google_api_key(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record("g=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx done")
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "AIzaSy" not in rec.getMessage()

    def test_redacts_oauth_token(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record("ya29.A0AfH6SMBxxxxxxx_yz.sample tail")
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "ya29.A0AfH6SMB" not in rec.getMessage()

    def test_redacts_bearer_token(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record("Authorization: Bearer abcdef.ghijkl.mnopqr-stuvwx_yz12345")
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "Bearer abcdef" not in rec.getMessage()

    def test_passes_clean_message_unchanged(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter
        f = SensitiveFilter()
        rec = _make_record("nothing sensitive here")
        original = rec.getMessage()
        f.filter(rec)
        assert rec.getMessage() == original

    def test_redacts_unprefixed_key_via_context(self):
        """I2: DeepSeek/Moonshot 等无规范前缀的 key 通过上下文 key= 兜底。"""
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record("config: api_key=randomToken1234567890abcdef ready")
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "randomToken1234567890abcdef" not in rec.getMessage()

    def test_redacts_apikey_with_dash_and_quoted_value(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record('api-key: "aBcDeFgHiJkLmNoPqRsT1234"')
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "aBcDeFgHiJkLmNoPqRsT1234" not in rec.getMessage()

    def test_redacts_secret_field(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter, REDACTED
        f = SensitiveFilter()
        rec = _make_record("payload {secret=zxywvutsrqponmlkjihgfedcba}")
        f.filter(rec)
        assert REDACTED in rec.getMessage()
        assert "zxywvutsrqponmlkjihgfedcba" not in rec.getMessage()

    def test_does_not_match_short_value(self):
        """阈值下不动，避免把 \"api_key=null\" 这类正常消息误伤。"""
        from ModuleFolders.Log.FileBackend import SensitiveFilter
        f = SensitiveFilter()
        rec = _make_record("api_key=null in config")
        before = rec.getMessage()
        f.filter(rec)
        assert rec.getMessage() == before

    def test_does_not_match_plain_english_prose(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter
        f = SensitiveFilter()
        rec = _make_record("the api_key field is required for authentication")
        before = rec.getMessage()
        f.filter(rec)
        assert rec.getMessage() == before

    def test_filter_returns_true_to_keep_record(self):
        from ModuleFolders.Log.FileBackend import SensitiveFilter
        assert SensitiveFilter().filter(_make_record("x")) is True


class TestPlainFormatter:
    def test_strips_simple_rich_markup(self):
        from ModuleFolders.Log.FileBackend import _PlainFormatter
        fmt = _PlainFormatter("%(message)s")
        assert fmt.format(_make_record("hello [red]world[/]")) == "hello world"

    def test_double_bracket_becomes_literal_bracket(self):
        from ModuleFolders.Log.FileBackend import _PlainFormatter
        fmt = _PlainFormatter("%(message)s")
        assert fmt.format(_make_record("[[red]ERROR[/]] boom")) == "[ERROR] boom"

    def test_plain_text_passes_through(self):
        from ModuleFolders.Log.FileBackend import _PlainFormatter
        fmt = _PlainFormatter("%(message)s")
        assert fmt.format(_make_record("plain")) == "plain"

    def test_restores_record_msg_after_format(self):
        """Other handlers must not see the stripped version."""
        from ModuleFolders.Log.FileBackend import _PlainFormatter
        fmt = _PlainFormatter("%(message)s")
        rec = _make_record("[red]X[/]")
        fmt.format(rec)
        assert rec.msg == "[red]X[/]"


class TestCleanupOldLogs:
    def test_removes_files_older_than_retention(self, tmp_path):
        from ModuleFolders.Log.FileBackend import _cleanup_old_logs, LOG_FILENAME
        old = tmp_path / f"{LOG_FILENAME}.5"
        old.write_text("x")
        old_time = time.time() - 100 * 86400
        os.utime(old, (old_time, old_time))
        _cleanup_old_logs(tmp_path, retention_days=30)
        assert not old.exists()

    def test_keeps_recent_files(self, tmp_path):
        from ModuleFolders.Log.FileBackend import _cleanup_old_logs, LOG_FILENAME
        recent = tmp_path / f"{LOG_FILENAME}.1"
        recent.write_text("x")
        _cleanup_old_logs(tmp_path, retention_days=30)
        assert recent.exists()

    def test_ignores_non_log_files(self, tmp_path):
        from ModuleFolders.Log.FileBackend import _cleanup_old_logs
        other = tmp_path / "notes.txt"
        other.write_text("x")
        old_time = time.time() - 100 * 86400
        os.utime(other, (old_time, old_time))
        _cleanup_old_logs(tmp_path, retention_days=30)
        assert other.exists()

    def test_does_not_match_log_name_prefix(self, tmp_path):
        """I1: 文件名以 'ainiee.log' 开头但不是真正的轮转日志，不能误删。"""
        from ModuleFolders.Log.FileBackend import _cleanup_old_logs
        not_a_log = tmp_path / "ainiee.log.bak.txt"
        weird_name = tmp_path / "ainiee.logorama"
        for f in (not_a_log, weird_name):
            f.write_text("user data")
            old_time = time.time() - 100 * 86400
            os.utime(f, (old_time, old_time))
        _cleanup_old_logs(tmp_path, retention_days=30)
        assert not_a_log.exists()
        assert weird_name.exists()

    def test_removes_rotated_numbered_logs(self, tmp_path):
        """正向回归：ainiee.log.1 / .5 这种真正的 RotatingFileHandler 产物必须被清。"""
        from ModuleFolders.Log.FileBackend import _cleanup_old_logs, LOG_FILENAME
        old_time = time.time() - 100 * 86400
        for suffix in ("", ".1", ".5"):
            f = tmp_path / f"{LOG_FILENAME}{suffix}"
            f.write_text("x")
            os.utime(f, (old_time, old_time))
        _cleanup_old_logs(tmp_path, retention_days=30)
        for suffix in ("", ".1", ".5"):
            assert not (tmp_path / f"{LOG_FILENAME}{suffix}").exists()

    def test_silently_skips_missing_directory(self, tmp_path):
        from ModuleFolders.Log.FileBackend import _cleanup_old_logs
        missing = tmp_path / "does-not-exist"
        _cleanup_old_logs(missing, retention_days=30)


class TestInitFileLogging:
    def test_returns_path_under_user_log_dir(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging, LOG_FILENAME
        assert init_file_logging() == tmp_log_dir / LOG_FILENAME

    def test_creates_nested_log_directory_if_missing(self, tmp_path, monkeypatch):
        import importlib
        target = tmp_path / "nested" / "deep" / "logs"
        monkeypatch.setenv("AINIEE_LOG_DIR", str(target))
        import ModuleFolders.Config.FilePathConfig as fpc
        import ModuleFolders.Log.FileBackend as fb
        importlib.reload(fpc); importlib.reload(fb)
        try:
            assert not target.exists()
            fb.init_file_logging()
            assert target.exists()
        finally:
            for h in list(logging.getLogger().handlers):
                if getattr(h, "name", "") == fb.HANDLER_NAME:
                    logging.getLogger().removeHandler(h)
                    h.close()
            fb._INSTALLED = False

    def test_is_idempotent_under_repeated_calls(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging, HANDLER_NAME
        init_file_logging()
        init_file_logging()
        init_file_logging()
        handlers = [h for h in logging.getLogger().handlers if getattr(h, "name", "") == HANDLER_NAME]
        assert len(handlers) == 1

    def test_silences_noisy_third_party_loggers(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        init_file_logging()
        for name in ("urllib3", "httpx", "httpcore", "PIL", "matplotlib", "asyncio"):
            assert logging.getLogger(name).level >= logging.WARNING

    def test_does_not_downgrade_verbose_root_level(self, tmp_log_dir):
        """If user set root to DEBUG before init, init must not raise it back to INFO."""
        import importlib
        import ModuleFolders.Log.FileBackend as fb
        logging.getLogger().setLevel(logging.DEBUG)
        importlib.reload(fb)
        fb.init_file_logging()
        try:
            assert logging.getLogger().level == logging.DEBUG
        finally:
            logging.getLogger().setLevel(logging.WARNING)
            for h in list(logging.getLogger().handlers):
                if getattr(h, "name", "") == fb.HANDLER_NAME:
                    logging.getLogger().removeHandler(h)
                    h.close()
            fb._INSTALLED = False

    def test_writes_log_lines_to_file(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        logging.getLogger("e2e.fb").info("hello world")
        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "hello world" in content
        assert "[INFO]" in content

    def test_redacts_keys_in_file_output(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        logging.getLogger("e2e.fb").warning("key sk-abcdefghijklmnopqrstuvwxyz123456")
        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "sk-abc" not in content
        assert "***REDACTED***" in content

    def test_redacts_keys_in_exception_traceback(self, tmp_log_dir):
        """C1: 异常 message 里出现的 key 必须被脱敏，否则 LLM SDK 错误就是泄漏点。"""
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        try:
            raise RuntimeError(
                "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz1234567890"
            )
        except RuntimeError:
            logging.getLogger("e2e.fb").error("request failed", exc_info=True)
        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "sk-abc" not in content
        assert "Bearer sk-" not in content
        assert "***REDACTED***" in content
        assert "RuntimeError" in content
        assert "Traceback" in content

    def test_rich_markup_does_not_reach_file(self, tmp_log_dir):
        from ModuleFolders.Log.FileBackend import init_file_logging
        path = init_file_logging()
        logging.getLogger("e2e.fb").info("[red]styled[/]")
        for h in logging.getLogger().handlers:
            h.flush()
        content = path.read_text()
        assert "[red]" not in content
        assert "styled" in content
