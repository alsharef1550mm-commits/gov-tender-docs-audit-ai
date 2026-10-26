"""Presentation regression checks. No model/server calls or production jobs."""
import os
import tempfile
os.environ["AUDIT_DATA_DIR"] = tempfile.mkdtemp(prefix="audit_ui_test_")
import unittest
from unittest.mock import patch
import app
import ui_workspace as UI


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [["first", "ضريبة", "STO001", "INV001", "a.pdf", 1, "—"],
                     ["second", "هوية", "", "INV002", "a.pdf", 2, "قراءة مطابقة"]]

    def test_navigation_empty_and_boundaries(self):
        self.assertIsNone(app.adjacent_review([], None, 1))
        self.assertEqual(app.adjacent_review(self.rows, None, 1), "first")
        self.assertEqual(app.adjacent_review(self.rows, "first", -1), "first")
        self.assertEqual(app.adjacent_review(self.rows, "first", 1), "second")
        self.assertEqual(app.adjacent_review(self.rows, "second", 1), "second")

    def test_choices_preserve_selection_and_clear_removed_key(self):
        self.assertEqual(app.review_choices(self.rows, "second")["value"], "second")
        self.assertIsNone(app.review_choices(self.rows, "stale")["value"])
        self.assertEqual(len(app.review_choices(self.rows, None)["choices"]), 2)

    def test_dataframe_navigation(self):
        import pandas as pd
        self.assertEqual(app.adjacent_review(pd.DataFrame(self.rows), "first", 1), "second")

    def test_stale_evidence_cannot_save_to_new_selection(self):
        with patch.object(app, "save_decision", return_value="saved") as save:
            self.assertIn("انتظر", app.save_visible_decision("job", "second", "first", "ok", None, "note", "name"))
            save.assert_not_called()
            self.assertEqual(app.save_visible_decision("job", "second", "second", "ok", None, "note", "name"), "saved")
            save.assert_called_once_with("job", "second", "ok", None, "note", "name")

    def test_summary_does_not_claim_acceptance(self):
        self.assertIn("لا يعني اعتماد", app._review_summary([]))
        result = app._review_summary(self.rows)
        self.assertIn("<b>2</b>", result)
        self.assertEqual(result.count("<b>1</b>"), 2)

    def test_empty_evidence_and_bidi(self):
        evidence, details = app.show_item(None, None)
        self.assertIn("اختر بنداً", evidence)
        self.assertEqual(details, "")
        self.assertEqual(app._ltr("<PO>"), "<bdi dir='ltr'>&lt;PO&gt;</bdi>")

    def test_build_without_model_operations(self):
        with patch.object(app.MS, "load_state", return_value={"status": "off"}), \
             patch.object(app.MS, "start", side_effect=AssertionError("No model start")), \
             patch.object(app.MS, "stop", side_effect=AssertionError("No model stop")):
            demo = app.build()
        labels = [getattr(b, "label", None) for b in demo.blocks.values()]
        self.assertIn("البند المحدد", labels)
        self.assertIn("ملاحظة المراجع (إلزامية)", labels)
        self.assertNotIn("إرشادات تجهيز المستندات وتسميتها", labels)
        self.assertTrue(any("preparation-guide" in " ".join(getattr(b, "elem_classes", None) or []).split() for b in demo.blocks.values()))
        self.assertNotIn("<ol", app._orient_hint())
        self.assertNotIn("<details", app._orient_hint())

    def test_viewer_has_native_keyboard_close_and_no_remote_io(self):
        self.assertIn("document.createElement('dialog')", UI.JS)
        self.assertIn("showModal()", UI.JS)
        self.assertIn("previousFocus.focus()", UI.JS)
        self.assertNotIn("fetch(", UI.JS)
        self.assertIn("prefers-reduced-motion", UI.CSS)


if __name__ == "__main__":
    unittest.main()
