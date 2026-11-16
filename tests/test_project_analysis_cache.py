import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from Backend.application.pipeline_common import PipelineError
from Backend.application.runtime import Runtime
from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_item import CacheItem
from Backend.domain.models.cache_project import CacheProject
from Backend.infrastructure.cache import CacheManager


class ProjectAnalysisCacheTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {"AINIEE_PROJECT_CACHE_DIR": str(self.root)}))
        self.cache = CacheManager()
        self.cache.load_from_project(CacheProject(
            project_type="Mtool", project_id="game",
            files={"source.json": CacheFile(file_project_type="Mtool", items=[
                CacheItem(text_index=1, source_text="Hello", translated_text="Bonjour"),
            ])}, extra={"keep": 1, "analysis_v1": {"terms": [{"source": "Earth"}]}},
        ))
        self.base = self.root / "game" / self.cache.CACHE_FILENAME
        self.stats = self.base.with_name(self.cache.STATS_FILENAME)

    def test_inline_cache_migrates_once_and_edits_skip_project_and_job_snapshots(self):
        self.base.parent.mkdir()
        self.base.write_text(json.dumps(self.cache.project.to_dict()), encoding="utf-8")
        self.cache.load_from_project_id("game")
        self.assertEqual(self.cache.get_analysis_data()["terms"][0]["source"], "Earth")
        self.assertNotIn("analysis_v1", json.loads(self.base.read_bytes())["extra"])
        base = self.base.read_bytes()
        runtime = Runtime(job_store_path=self.root / "jobs.sqlite3")
        runtime.cache = self.cache
        self.addCleanup(runtime.scheduler.close)
        updated = {"terms": [{"source": "Earth"}, {"source": "Moon"}]}
        with patch.object(runtime, "load_config", return_value={}), \
             patch.object(CacheProject, "to_dict", side_effect=AssertionError("serialized full project")), \
             patch.object(self.cache, "_write_project_cache_files", side_effect=AssertionError("full save")):
            result = runtime.cache_call("set_analysis_data", [updated], {}, "game", False)
            self.assertEqual(result, {"result": None})
            job = runtime.scheduler.list()[0]
            self.assertEqual(runtime.scheduler.get(job["id"])["result"], result)
            matches = runtime.cache_call("search_items", ["Hello", "source_text", False, False], {}, "game", False)
            self.assertEqual(list(matches), ["result"])
            self.assertEqual(matches["result"][0][2]["translated_text"], "Bonjour")
            with self.assertRaises(PipelineError):
                runtime.cache_call("clear_analysis_data", [], {}, "different-project", False)
        self.assertEqual(self.base.read_bytes(), base)
        self.cache.load_from_project_id("game")
        self.assertEqual(self.cache.project.extra, {"keep": 1, "analysis_v1": updated})
        self.assertEqual(self.cache.project.files["source.json"].items[0].translated_text, "Bonjour")
        self.cache.require_save_to_file()
        self.cache.clear_analysis_data()
        self.assertEqual(self.base.read_bytes(), base)
        self.cache.close()  # unrelated pending saves still flush
        self.assertNotIn("analysis_v1", self.cache.read_from_file(self.base).extra)

    def test_failed_edit_leaves_last_committed_analysis(self):
        self.cache.save_to_file()
        previous = self.cache.get_analysis_data()
        with patch("Backend.infrastructure.files.accessors.cache_accessor.os.replace", side_effect=OSError):
            with self.assertRaises(OSError):
                self.cache.set_analysis_data({"terms": []})
        self.assertEqual(self.cache.get_analysis_data(), previous)
        self.assertEqual(self.cache.read_from_file(self.base).extra["analysis_v1"], previous)
        self.assertFalse(list(self.base.parent.glob("*.tmp")))

    def test_external_cache_bootstraps_local_project_and_checks_companion_identity(self):
        external = self.root / "import.json"
        external.write_text(json.dumps(self.cache.project.to_dict()), encoding="utf-8")
        self.cache.load_from_file(str(external))
        self.cache.set_analysis_data({"terms": []})
        self.assertEqual(self.cache.read_from_file(self.base).extra["analysis_v1"], {"terms": []})
        self.assertEqual(self.cache.read_from_file(external).extra["analysis_v1"]["terms"][0]["source"], "Earth")
        self.stats.write_text('{"project_id":"other","analysis_v1":{}}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.cache.load_from_project_id("game")
        self.stats.unlink()
        with self.assertRaisesRegex(ValueError, self.stats.name):
            self.cache.load_from_project_id("game")

    def test_three_file_cache_merges_tables_and_preserves_history_progress(self):
        self.base.parent.mkdir()
        model = self.cache.project.to_dict()
        tables = model["extra"].pop("analysis_v1")
        old = self.base.with_name("ProjectAnalysis.json")
        model["analysis_cache_file"] = old.name
        self.base.write_text(json.dumps(model), encoding="utf-8")
        old.write_text(json.dumps({"project_id": "game", "analysis_v1": tables}), encoding="utf-8")
        progress = {"project_id": "game", "project_name": "Game", "line": 38, "total_line": 61}
        self.stats.write_text(json.dumps(progress), encoding="utf-8")

        replace = os.replace
        def fail_main(source, target):
            if Path(target) == self.base:
                raise OSError("simulated migration interruption")
            replace(source, target)

        with patch("os.replace", side_effect=fail_main), self.assertRaises(OSError):
            self.cache.load_from_project_id("game")
        self.assertTrue(old.exists())
        self.assertEqual(json.loads(self.base.read_bytes()), model)
        self.cache.load_from_project_id("game")
        self.assertEqual(set(self.base.parent.iterdir()), {self.base, self.stats})
        self.assertEqual(self.cache.get_analysis_data(), tables)
        main_bytes = self.base.read_bytes()
        self.cache.set_analysis_data({"terms": [{"source": "Moon"}]})
        self.assertEqual(self.base.read_bytes(), main_bytes)
        combined = json.loads(self.stats.read_bytes())
        self.assertEqual(combined["analysis_v1"], self.cache.get_analysis_data())
        self.assertEqual({key: combined[key] for key in progress}, progress)
        self.assertNotIn("analysis_v1", self.cache.read_project_statistics("game"))
        history, = self.cache.list_project_histories()
        self.assertEqual((history["project_name"], history["line"], history["total_line"]), ("Game", 38, 61))
        self.cache.clear_analysis_data()
        self.cache.save_to_file()
        self.cache.load_from_project_id("game")
        self.assertEqual(self.cache.get_analysis_data(), {})
        self.assertEqual(self.cache.read_project_statistics("game")["line"], 38)

    def test_unversioned_cache_keeps_backup_and_extension_fields(self):
        self.base.parent.mkdir()
        legacy = self.cache.project.to_dict()
        del legacy["schema_version"]
        legacy["notes"] = ["legacy extension"]
        original = json.dumps(legacy).encode()
        self.base.write_bytes(original)
        self.cache.load_from_project_id("game")
        self.assertEqual(self.base.with_suffix(".json.pre-v2.bak").read_bytes(), original)
        self.assertEqual(self.cache.project.extra["notes"], legacy["notes"])
        self.assertEqual(self.cache.get_analysis_data(), legacy["extra"]["analysis_v1"])
