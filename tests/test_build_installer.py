import importlib.util
from pathlib import Path

import pytest


def _load_biw():
    spec = importlib.util.spec_from_file_location(
        "biw", Path(__file__).resolve().parents[1] / "Tools" / "build_installer_windows.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestParseVersionString:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("AiNiee 7.2.3 dev", "7.2.3"),
            ("AiNiee 7.2.3.4", "7.2.3.4"),
            ("v7.2.3-beta", "7.2.3"),
            ("Release 1.0.0", "1.0.0"),
            ("10.20.30 stable", "10.20.30"),
        ],
    )
    def test_extracts_semver_from_decorated_string(self, raw, expected):
        biw = _load_biw()
        assert biw._parse_version_string(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "AiNiee",
            "no digits here",
            "1.0",  # 只有两段，Inno Setup AppVersion 不接受
            "v1",
        ],
    )
    def test_falls_back_to_default_when_no_semver(self, raw):
        biw = _load_biw()
        assert biw._parse_version_string(raw) == "0.0.0"


class TestReadVersion:
    def test_reads_from_resource_version_file(self):
        biw = _load_biw()
        v = biw._read_version()
        assert v
        parts = v.split(".")
        assert all(p.isdigit() for p in parts), f"unclean version: {v}"
        assert 3 <= len(parts) <= 4
