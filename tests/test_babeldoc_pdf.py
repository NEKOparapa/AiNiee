import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


@unittest.skipUnless(os.environ.get("AINIEE_TEST_PDF") == "1", "需要 BabelDOC 字体和版面模型")
class BabeldocPdfTest(unittest.TestCase):
    def test_selected_pages_and_duplicate_paragraphs_round_trip(self):
        import pymupdf
        from Backend.application.read_service import read_document
        from Backend.application.write_service import write_model
        from Backend.domain.models.cache_item import TranslationStatus

        root = Path(self.enterContext(TemporaryDirectory()))
        source = root / "source.pdf"
        repeated = "The same paragraph appears on both pages."
        with pymupdf.open() as doc:
            for number in range(3):
                page = doc.new_page()
                page.insert_text((60, 120), repeated)
                page.insert_text((60, 300), f"Page number {number + 1}.")
            doc.save(source)

        project = read_document(source, {"pages": "2-3"})["model"]
        file = next(iter(project.files.values()))
        self.assertEqual([item.source_text for item in file.items],
                         [repeated, "Page number 2.", repeated, "Page number 3."])
        translations = ["第一处译文", "第二页", "另一处译文", "第三页"]
        for item, text in zip(file.items, translations):
            item.translated_text = text
            item.translation_status = TranslationStatus.TRANSLATED

        options = {"mode": "both", "output_dir": str(root / "out")}
        result = write_model(project, options)
        self.assertEqual(result["status"], "success", result["report"])
        self.assertEqual({entry["mode"] for entry in result["files"]}, {"translated", "bilingual"})
        for entry in result["files"]:
            with pymupdf.open(entry["path"]) as doc:
                self.assertEqual(len(doc), 3)
                self.assertIn(repeated, doc[0].get_text())
                for number in (1, 2):
                    text = doc[number].get_text()
                    self.assertIn(translations[2 * (number - 1)], text)
                    self.assertIn(translations[2 * number - 1], text)
                    self.assertEqual(repeated in text, entry["mode"] == "bilingual")

        file.extra["pdf"]["babeldoc_version"] = "0.6.4"
        result = write_model(project, {**options, "overwrite": True})
        self.assertEqual(result["report"]["errors"][0]["code"], "PDF_MAPPING_MISMATCH")
        self.assertEqual(result["files"], [])
