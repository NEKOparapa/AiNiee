"""Logging continues to serve the file/WS sinks after removing desktop adapters."""

import logging

from rich.table import Table

from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Log.LogSystem import SensitiveFilter, sensitive_values


def test_rich_and_plain_logs_reach_standard_handlers_once(caplog, monkeypatch):
    monkeypatch.setattr("ModuleFolders.Log.Log._rich_print", lambda *args, **kwargs: None)
    caplog.set_level(logging.DEBUG)
    log = LogMixin()
    table = Table()
    table.add_column("Source")
    table.add_column("Translation")
    table.add_row("Hello", "你好")
    log.print(table)
    log.info("literal [brackets] <xml> remain visible")
    log.warning("warning text")
    log.debug("debug text")
    assert len(caplog.records) == 4
    assert "Hello" in caplog.records[0].getMessage()
    assert "你好" in caplog.records[0].getMessage()
    assert caplog.records[1].getMessage() == "literal [brackets] <xml> remain visible"
    assert [record.levelname for record in caplog.records] == ["INFO", "INFO", "WARNING", "DEBUG"]
    # No copied desktop presentation payloads are retained on a LogRecord.
    assert not any(key.startswith("ainiee_") for record in caplog.records for key in vars(record))


def test_exception_and_plain_messages_keep_credential_redaction(caplog, monkeypatch):
    monkeypatch.setattr("ModuleFolders.Log.Log._rich_print", lambda *args, **kwargs: None)
    secret = "fixed-private-provider-value"
    with sensitive_values([secret]):
        try:
            raise RuntimeError(f"Provider rejected {secret}")
        except RuntimeError as error:
            LogMixin().error(f"Request failed for {secret}", error)
        record = caplog.records[-1]
        assert SensitiveFilter().filter(record)
        formatted = logging.Formatter("%(message)s").format(record)
    assert secret not in formatted
    assert "REDACTED" in formatted
    assert "RuntimeError" in formatted
