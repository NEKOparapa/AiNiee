import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt5.QtGui import QKeySequence


class MacOSNativeUITest(unittest.TestCase):
    def setUp(self):
        self.old_data_dir = os.environ.pop("AINIEE_USER_DATA_DIR", None)

    def tearDown(self):
        if self.old_data_dir is not None:
            os.environ["AINIEE_USER_DATA_DIR"] = self.old_data_dir
        else:
            os.environ.pop("AINIEE_USER_DATA_DIR", None)

    def _module(self):
        import UserInterface.Native.MacOSUI as macos_ui

        return importlib.reload(macos_ui)

    def test_command_shortcuts_render_as_command_key_on_macos(self):
        with patch("platform.system", return_value="Darwin"):
            macos_ui = self._module()

            self.assertEqual(QKeySequence(macos_ui.command_shortcut(",")).toString(QKeySequence.NativeText), "⌘,")
            self.assertEqual(QKeySequence(macos_ui.command_shortcut("Q")).toString(QKeySequence.NativeText), "⌘Q")

    def test_directory_dialog_starts_in_user_data_for_blank_macos_paths(self):
        with tempfile.TemporaryDirectory() as tmp, patch("platform.system", return_value="Darwin"):
            os.environ["AINIEE_USER_DATA_DIR"] = str(Path(tmp) / "UserData")
            macos_ui = self._module()

            self.assertEqual(macos_ui.dialog_start_directory(""), str((Path(tmp) / "UserData").resolve()))

    def test_macos_copy_uses_native_file_and_path_language(self):
        with patch("platform.system", return_value="Darwin"):
            macos_ui = self._module()

            self.assertEqual(macos_ui.input_folder_button_text(lambda text: text), "选择输入文件夹")
            self.assertIn("~/Documents/Input", macos_ui.auto_output_path_description(lambda text: text))
            self.assertNotIn("D:/", macos_ui.auto_output_path_description(lambda text: text))


if __name__ == "__main__":
    unittest.main()
