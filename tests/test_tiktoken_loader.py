import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TiktokenLoaderTest(unittest.TestCase):
    def setUp(self):
        self.old_cache_dir = os.environ.pop("AINIEE_CACHE_DIR", None)
        self.old_tiktoken_cache_dir = os.environ.pop("TIKTOKEN_CACHE_DIR", None)

    def tearDown(self):
        try:
            from ModuleFolders.Infrastructure.Tokener.BabeldocPatch import remove_patch

            remove_patch()
        except Exception:
            pass

        if self.old_cache_dir is not None:
            os.environ["AINIEE_CACHE_DIR"] = self.old_cache_dir
        else:
            os.environ.pop("AINIEE_CACHE_DIR", None)

        if self.old_tiktoken_cache_dir is not None:
            os.environ["TIKTOKEN_CACHE_DIR"] = self.old_tiktoken_cache_dir
        else:
            os.environ.pop("TIKTOKEN_CACHE_DIR", None)

    def test_macos_tiktoken_cache_uses_user_cache_root(self):
        with tempfile.TemporaryDirectory() as tmp, patch("platform.system", return_value="Darwin"):
            cache_root = Path(tmp) / "UserCaches"
            os.environ["AINIEE_CACHE_DIR"] = str(cache_root)

            import ModuleFolders.Infrastructure.Tokener.TiktokenLoader as loader

            loader = importlib.reload(loader)

            cache_dir = Path(loader.initialize_tiktoken())

            self.assertEqual(cache_dir, cache_root.resolve() / "tiktoken")
            self.assertEqual(Path(os.environ["TIKTOKEN_CACHE_DIR"]), cache_dir)
            self.assertTrue(cache_dir.exists())


if __name__ == "__main__":
    unittest.main()
