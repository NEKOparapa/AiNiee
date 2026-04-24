import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class ConfigPathTest(unittest.TestCase):
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

    def test_config_mixin_loads_migrated_macos_config_and_saves_user_copy(self):
        with tempfile.TemporaryDirectory() as tmp, patch("platform.system", return_value="Darwin"):
            resource_dir = Path(tmp) / "Resource"
            user_dir = Path(tmp) / "UserData"
            resource_dir.mkdir()
            (resource_dir / "config.json").write_text(json.dumps({"theme": "light"}), encoding="utf-8")
            os.environ["AINIEE_RESOURCE_DIR"] = str(resource_dir)
            os.environ["AINIEE_USER_DATA_DIR"] = str(user_dir)
            sys.modules.setdefault("rapidjson", json)
            sys.modules.setdefault("rich", types.SimpleNamespace(print=print))

            import ModuleFolders.Config.Config as config_module

            config_module = importlib.reload(config_module)
            mixin = config_module.ConfigMixin()

            self.assertEqual(mixin.load_config(), {"theme": "light"})

            mixin.save_config({"theme": "dark"})
            self.assertEqual(json.loads((user_dir / "config.json").read_text(encoding="utf-8")), {"theme": "dark"})
            self.assertEqual(json.loads((resource_dir / "config.json").read_text(encoding="utf-8")), {"theme": "light"})


if __name__ == "__main__":
    unittest.main()
