import unittest
from unittest.mock import patch

from ModuleFolders.Service.TaskExecutor.AnalysisTask import AnalysisTask


class AnalysisTaskReductionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokener_patch = patch(
            "ModuleFolders.Service.TaskExecutor.AnalysisTask.Tokener.num_tokens_from_str",
            return_value=1,
        )
        self.tokener_patch.start()
        self.addCleanup(self.tokener_patch.stop)
        self.task = AnalysisTask(None, lambda executor: None, lambda executor: None)
        self.first_stage_results = [
            {
                "characters": [
                    {"source": "Arthur King", "recommended_translation": "亚瑟王", "gender": "男性", "note": "国王"},
                    {"source": "Arthur", "recommended_translation": "亚瑟", "gender": "男性", "note": "简称"},
                ],
                "terms": [{"source": "Arthur", "recommended_translation": "亚瑟", "category_path": "称号", "note": "别称"}],
            },
            {
                "characters": [{"source": "Arthur", "recommended_translation": "亚瑟", "gender": "男性", "note": "简称"}],
                "terms": [],
            },
        ]

    def test_disabled_short_name_merge_keeps_sources_independent(self) -> None:
        self.task.config.extract_short_name_merge_switch = False

        batches = self.task._prepare_reduction_batches(self.first_stage_results)

        grouped_sources = {item["source"] for batch in batches for item in batch}
        self.assertEqual({"Arthur", "Arthur King"}, grouped_sources)
        self.assertEqual("Arthur", self.task.grouped_stage_two_source_aliases["Arthur"])

        final_data = self.task._finalize_results(
            self.first_stage_results,
            [{"terms": [{"source": "Arthur", "recommended_translation": "亚瑟", "category_path": "称号", "note": ""}], "characters": []}],
        )
        self.assertEqual(3, final_data["terms"][0]["occurrence_count"])

    def test_enabled_short_name_merge_keeps_short_name_count(self) -> None:
        self.task.config.extract_short_name_merge_switch = True

        self.task._prepare_reduction_batches(self.first_stage_results)
        final_data = self.task._finalize_results(
            self.first_stage_results,
            [{"characters": [{"source": "Arthur King", "recommended_translation": "亚瑟王", "gender": "男性", "note": ""}], "terms": []}],
        )

        characters_by_source = {row["source"]: row for row in final_data["characters"]}
        self.assertEqual("Arthur King", self.task.grouped_stage_two_source_aliases["Arthur"])
        self.assertEqual(3, characters_by_source["Arthur"]["occurrence_count"])
        self.assertEqual(1, characters_by_source["Arthur King"]["occurrence_count"])


if __name__ == "__main__":
    unittest.main()
