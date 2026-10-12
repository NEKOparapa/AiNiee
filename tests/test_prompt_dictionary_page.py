import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import openpyxl
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QWidget
from qfluentwidgets import SwitchButton, TableWidget

from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from UserInterface.Table.PromptDictionaryPage import PromptDictionaryPage
from UserInterface.Table.TableHelper.TableHelper import TableHelper


class PromptDictionaryPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config_path = Path(self.directory.name) / "config.json"
        self.config_path.write_text("{}", encoding="utf-8")
        for patcher in (
            patch("ModuleFolders.Config.Config.config_path", return_value=str(self.config_path)),
            patch("ModuleFolders.Config.Config.migrate_config_if_needed"),
            patch.object(PromptDictionaryPage, "_show_toast"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.page = PromptDictionaryPage("glossary-test", None)
        self.page.resize(1200, 800)
        self.page.show()
        self.app.processEvents()
        self.addCleanup(self.close_page)

    def close_page(self):
        self.page._cleanup_event_subscriptions()
        self.page.close()
        self.page.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    def saved_rows(self):
        return json.loads(self.config_path.read_text(encoding="utf-8"))["prompt_dictionary_data"]

    def test_large_glossary_does_not_create_widgets_per_row(self):
        rows = [
            {"src": f"用語{i}", "dst": f"术语{i}", "info": "描述", "regex": i % 2 == 0}
            for i in range(7000)
        ]
        widget_count = len(self.page.table.findChildren(QWidget))
        self.page._update_table_rows(rows)
        self.app.processEvents()

        self.assertEqual(self.page._load_table_rows(), rows)
        self.assertEqual(len(self.page.table.findChildren(QWidget)), widget_count)
        self.assertEqual(self.page.table.findChildren(SwitchButton), [])
        self.page._update_table_rows(rows)
        self.app.processEvents()
        self.assertEqual(len(self.page.table.findChildren(QWidget)), widget_count)

    def test_edits_and_switches_validate_only_the_changed_row(self):
        self.page._update_table_rows([{"src": f"term{i}"} for i in range(1000)])
        with patch.object(GlossaryHelper, "get_row_state", wraps=GlossaryHelper.get_row_state) as validate:
            self.page.table.item(500, 0).setText("[")
            self.assertEqual(validate.call_count, 1)
            self.page.table.item(500, 3).setCheckState(Qt.Checked)
            self.assertEqual(validate.call_count, 2)
            self.page.table.item(500, 1).setText("translation")
            self.assertEqual(validate.call_count, 2)

        self.assertEqual(self.page.table.item(500, 0).background(), self.page.INVALID_ROW_BRUSH)
        self.assertNotEqual(self.page.table.item(499, 0).background(), self.page.INVALID_ROW_BRUSH)
        self.page.table.item(500, 3).setCheckState(Qt.Unchecked)
        self.assertNotEqual(self.page.table.item(500, 0).background(), self.page.INVALID_ROW_BRUSH)

    def test_blank_sources_hide_and_reset_switches(self):
        self.page._update_table_rows([{"src": "source", "regex": True}])
        self.assertIsNone(self.page.table.item(1, 3).data(Qt.CheckStateRole))
        self.page.table.item(0, 0).setText(" ")
        self.assertIsNone(self.page.table.item(0, 3).data(Qt.CheckStateRole))
        self.assertEqual(self.page._load_table_rows(), [])
        self.page.table.item(0, 0).setText("new source")
        self.assertEqual(self.page.table.item(0, 3).checkState(), Qt.Unchecked)
        self.page.table.item(0, 3).setCheckState(Qt.Checked)
        self.page.table.item(0, 0).setText("changed source")
        self.assertTrue(self.page._load_table_rows()[0]["regex"])

    def test_switch_supports_mouse_and_space_without_opening_editor(self):
        self.page._update_table_rows([{"src": "source"}])
        self.app.processEvents()
        item = self.page.table.item(0, 3)
        rect = self.page.table.visualItemRect(item)
        QTest.mouseClick(self.page.table.viewport(), Qt.LeftButton, pos=rect.center())
        self.assertEqual(item.checkState(), Qt.Checked)
        QTest.keyClick(self.page.table, Qt.Key_Space)
        self.assertEqual(item.checkState(), Qt.Unchecked)
        QTest.mouseClick(self.page.table.viewport(), Qt.LeftButton, pos=rect.topLeft())
        self.assertEqual(item.checkState(), Qt.Unchecked)
        self.assertFalse(item.flags() & Qt.ItemIsEditable)

    def test_save_writes_edits_without_rebuilding_or_losing_selection(self):
        self.page._update_table_rows([{"src": "source", "regex": True}])
        self.page.table.item(0, 1).setText("  translation  ")
        self.page.table.selectRow(0)
        original_item = self.page.table.item(0, 0)
        with patch.object(self.page, "_update_table_rows", wraps=self.page._update_table_rows) as rebuild:
            self.page.save_data()
            rebuild.assert_not_called()
        self.assertIs(self.page.table.item(0, 0), original_item)
        self.assertEqual([i.row() for i in self.page.table.selectionModel().selectedRows()], [0])
        self.assertEqual(self.saved_rows(), [{"src": "source", "dst": "translation", "info": "", "regex": True}])

    def test_reopening_unchanged_page_preserves_unsaved_edits(self):
        self.page.save_config({"prompt_dictionary_data": [{"src": "source"}]})
        self.page.update_table()
        self.page.table.item(0, 1).setText("unsaved translation")
        original_item = self.page.table.item(0, 0)
        self.page.hide()
        self.page.show()
        self.assertIs(self.page.table.item(0, 0), original_item)
        self.assertEqual(self.page._load_table_rows()[0]["dst"], "unsaved translation")

        self.page.save_config({"prompt_dictionary_data": [{"src": "external change", "regex": True}]})
        self.page.update_table()
        self.assertEqual(self.page._load_table_rows()[0]["src"], "external change")
        self.assertTrue(self.page._load_table_rows()[0]["regex"])

    def test_save_deduplicates_sources_created_by_editing(self):
        self.page._update_table_rows([
            {"src": "source", "dst": "first"},
            {"src": "other", "dst": "last", "regex": True},
        ])
        self.page.table.item(1, 0).setText("source")
        self.page.save_data()
        expected = [{"src": "source", "dst": "last", "info": "", "regex": True}]
        self.assertEqual(self.saved_rows(), expected)
        self.assertEqual(self.page._load_table_rows(), expected)

    def test_json_import_merges_edits_and_deduplicates_sources(self):
        self.page._update_table_rows([{"src": "existing", "dst": "unsaved edit", "regex": True}])
        path = Path(self.directory.name) / "glossary.json"
        path.write_text(json.dumps([
            {"src": "existing", "dst": "do not overwrite"},
            {"src": "new", "dst": "first"},
            {"src": "new", "dst": "last", "regex": True},
            {"src": "literal[", "dst": "literal"},
            {"src": " ", "dst": "ignore"},
        ]), encoding="utf-8")
        with patch("UserInterface.Table.PromptDictionaryPage.get_open_file_name", return_value=(str(path), "")):
            self.page.import_data()
        rows = self.saved_rows()
        self.assertEqual([row["src"] for row in rows], ["existing", "new", "literal["])
        self.assertEqual([row["dst"] for row in rows], ["unsaved edit", "last", "literal"])
        self.assertEqual([row["regex"] for row in rows], [True, True, False])
        self.assertEqual(self.page._load_table_rows(), rows)

    def test_xlsx_import_and_json_export_preserve_switch_values(self):
        path = Path(self.directory.name) / "glossary.xlsx"
        workbook = openpyxl.Workbook()
        workbook.active.append(["src", "dst", "info", "regex"])
        workbook.active.append(["source", "translation", "description", True])
        workbook.save(path)
        workbook.close()
        with patch("UserInterface.Table.PromptDictionaryPage.get_open_file_name", return_value=(str(path), "")):
            self.page.import_data()
        self.assertTrue(self.saved_rows()[0]["regex"])

        output = Path(self.directory.name) / "export.json"
        with patch("UserInterface.Table.PromptDictionaryPage.get_save_file_name", return_value=(str(output), "JSON 文件 (*.json)")):
            self.page.export_data()
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.saved_rows())

    def test_sort_search_insert_and_delete_keep_switches_attached_to_sources(self):
        self.page._update_table_rows([{"src": "zebra", "regex": True}, {"src": "apple"}])
        self.page._sort_table_by_column(0)
        self.assertEqual([row["src"] for row in self.page._load_table_rows()], ["apple", "zebra"])
        self.assertEqual([row["regex"] for row in self.page._load_table_rows()], [False, True])
        self.page.search_input.setText("zebra")
        self.page._perform_search()
        self.assertEqual(self.page._search_results, [(1, 0)])
        self.page._handle_remove_selected_rows()
        self.assertEqual([row["src"] for row in self.page._load_table_rows()], ["apple"])
        self.page.table.selectRow(0)
        self.page._handle_insert_row()
        self.page.table.item(1, 0).setText("inserted")
        self.page.table.item(1, 3).setCheckState(Qt.Checked)
        self.assertEqual([row["regex"] for row in self.page._load_table_rows()], [False, True])

    def test_table_helper_still_reads_existing_widget_switches(self):
        table = TableWidget()
        table.setColumnCount(4)
        rows = [{"src": "source", "dst": "translation", "info": "", "regex": True}]
        TableHelper.update_to_table(table, rows, self.page.KEYS, self.page.SWITCH_KEYS)
        self.assertEqual(TableHelper.load_from_table(table, self.page.KEYS, self.page.SWITCH_KEYS), rows)
        table.deleteLater()


if __name__ == "__main__":
    unittest.main()
