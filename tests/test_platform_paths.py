import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PlatformPathsTest(unittest.TestCase):
    def setUp(self):
        self.old_resource_dir = os.environ.pop("AINIEE_RESOURCE_DIR", None)
        self.old_data_dir = os.environ.pop("AINIEE_USER_DATA_DIR", None)

    def tearDown(self):
        if self.old_resource_dir is not None:
            os.environ["AINIEE_RESOURCE_DIR"] = self.old_resource_dir
        else:
            os.environ.pop("AINIEE_RESOURCE_DIR", None)

        if self.old_data_dir is not None:
            os.environ["AINIEE_USER_DATA_DIR"] = self.old_data_dir
        else:
            os.environ.pop("AINIEE_USER_DATA_DIR", None)

    def _module(self):
        import ModuleFolders.Infrastructure.Platform.PlatformPaths as paths

        return importlib.reload(paths)

    def test_macos_config_path_uses_application_support(self):
        with tempfile.TemporaryDirectory() as home_dir, patch("platform.system", return_value="Darwin"), patch(
            "pathlib.Path.home", return_value=Path(home_dir)
        ):
            paths = self._module()

            self.assertEqual(
                paths.config_path(),
                Path(home_dir) / "Library" / "Application Support" / "AiNiee_MacOS" / "config.json",
            )

    def test_resource_root_can_be_overridden_for_packaged_app(self):
        with tempfile.TemporaryDirectory() as resource_dir:
            os.environ["AINIEE_RESOURCE_DIR"] = resource_dir
            paths = self._module()

            self.assertEqual(paths.resource_root(), Path(resource_dir).resolve())
            self.assertEqual(
                paths.resource_path("Version", "version.json"),
                Path(resource_dir).resolve() / "Version" / "version.json",
            )

    def test_migrate_config_copies_default_without_overwriting_user_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            resource_dir = Path(tmp) / "Resource"
            user_dir = Path(tmp) / "UserData"
            resource_dir.mkdir()
            (resource_dir / "config.json").write_text(json.dumps({"source": "default"}), encoding="utf-8")
            os.environ["AINIEE_RESOURCE_DIR"] = str(resource_dir)
            os.environ["AINIEE_USER_DATA_DIR"] = str(user_dir)

            with patch("platform.system", return_value="Darwin"):
                paths = self._module()

                migrated = paths.migrate_config_if_needed()
                self.assertTrue(migrated)
                self.assertEqual(json.loads(paths.config_path().read_text(encoding="utf-8")), {"source": "default"})

                paths.config_path().write_text(json.dumps({"source": "user"}), encoding="utf-8")
                self.assertFalse(paths.migrate_config_if_needed())
                self.assertEqual(json.loads(paths.config_path().read_text(encoding="utf-8")), {"source": "user"})

    def test_macos_working_directory_uses_user_data_and_links_resource(self):
        with tempfile.TemporaryDirectory() as tmp, patch("platform.system", return_value="Darwin"):
            resource_dir = Path(tmp) / "BundledResource"
            user_dir = Path(tmp) / "UserData"
            resource_dir.mkdir()
            os.environ["AINIEE_RESOURCE_DIR"] = str(resource_dir)
            os.environ["AINIEE_USER_DATA_DIR"] = str(user_dir)
            paths = self._module()

            working_root = paths.prepare_working_directory()

            self.assertEqual(working_root, user_dir.resolve())
            self.assertTrue((working_root / "Resource").exists())
            self.assertEqual((working_root / "Resource").resolve(), resource_dir.resolve())


if __name__ == "__main__":
    unittest.main()
