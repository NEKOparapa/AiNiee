import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PackagedRuntimeRegressionTest(unittest.TestCase):
    def test_language_detector_model_path_uses_packaged_resource_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            resource_dir = Path(tmp) / "Resource"
            model_path = resource_dir / "Models" / "mediapipe" / "language_detector.tflite"
            model_path.parent.mkdir(parents=True)
            model_path.write_bytes(b"model")

            with patch.dict("os.environ", {"AINIEE_RESOURCE_DIR": str(resource_dir)}, clear=False):
                from ModuleFolders.Domain.FileReader import ReaderUtil

                self.assertEqual(ReaderUtil.language_detector_model_path(), model_path.resolve())

    def test_macos_latest_release_404_is_not_reported_as_update_failure(self):
        from UserInterface.VersionManager.VersionManager import VersionManager

        class Response:
            status_code = 404

            def json(self):
                return {"message": "Not Found"}

        manager = VersionManager(version="AiNiee 7.2.1 dev")

        with patch("UserInterface.VersionManager.VersionManager.is_macos", return_value=True), patch(
            "UserInterface.VersionManager.VersionManager.requests.get", return_value=Response()
        ):
            has_update, latest_version = manager.check_for_updates()

        self.assertFalse(has_update)
        self.assertEqual(latest_version, "7.2.1")
        self.assertIsNone(getattr(manager, "check_error", None))

    def test_release_tag_parser_accepts_macos_tag_names(self):
        from UserInterface.VersionManager.VersionManager import VersionManager

        class Response:
            status_code = 200

            def json(self):
                return {
                    "tag_name": "AiNiee_MacOS-v7.2.2",
                    "html_url": "https://github.com/beautifulrem/AiNiee_MacOS/releases/tag/AiNiee_MacOS-v7.2.2",
                    "assets": [],
                }

        manager = VersionManager(version="AiNiee 7.2.1 dev")

        with patch("UserInterface.VersionManager.VersionManager.requests.get", return_value=Response()):
            has_update, latest_version = manager.check_for_updates()

        self.assertTrue(has_update)
        self.assertEqual(latest_version, "7.2.2")

    def test_macos_packaging_collects_mediapipe_native_bindings(self):
        from Tools import pyinstall_macos

        cmd = pyinstall_macos.pyinstaller_command(Path("/tmp/icon.icns"))

        self.assertIn("--hidden-import=mediapipe.tasks.c", cmd)
        self.assertIn("--collect-all=mediapipe.tasks.c", cmd)


if __name__ == "__main__":
    unittest.main()
