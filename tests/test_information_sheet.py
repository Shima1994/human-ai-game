import ast
import unittest
from pathlib import Path

from ui.study_documents import (
    INFORMATION_SHEET_CONTACT,
    INFORMATION_SHEET_INTRODUCTION,
    INFORMATION_SHEET_SECTIONS,
    INFORMATION_SHEET_TITLE,
)


class InformationSheetTests(unittest.TestCase):
    def test_all_ten_approved_sections_are_present(self):
        self.assertEqual(len(INFORMATION_SHEET_SECTIONS), 10)
        headings = [heading for heading, _ in INFORMATION_SHEET_SECTIONS]
        self.assertEqual(
            headings,
            [
                "What is the research about?",
                "Do I have to take part?",
                "What will my involvement be?",
                "Are there different versions of the game?",
                "What data will be collected?",
                "",
                "What will my information be used for?",
                "Will my data be kept confidential and anonymized?",
                "How can I withdraw from the study?",
                "Are there any risks?",
            ],
        )

    def test_required_approved_content_is_not_truncated(self):
        rendered = " ".join(
            [INFORMATION_SHEET_TITLE, INFORMATION_SHEET_INTRODUCTION]
            + [heading + content for heading, content in INFORMATION_SHEET_SECTIONS]
            + [INFORMATION_SHEET_CONTACT]
        )
        required_phrases = (
            "25-30 minutes",
            "game condition and session ID",
            "short rating responses and optional reflection texts",
            "No directly identifying personal information",
            "future research on human–AI collaboration",
            "open data repositories (e.g. zenodo)",
            "closing the browser window",
            "This study is considered low risk",
            "shima.ghasempour-ardestani@stud.unidue.de",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, rendered)

    def test_screen_uses_requested_identity_date_and_existing_consent_state(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        screen = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "screen_consent"
        )
        screen_source = ast.get_source_segment(source, screen)
        self.assertIn("Shima Ghasempour</strong>", screen_source)
        self.assertNotIn("Shima Ghasempour Ardestani", screen_source)
        self.assertIn("September 2026", screen_source)
        self.assertNotIn("July 2026", screen_source)
        self.assertNotIn("selectbox", screen_source)
        self.assertIn("consent_confirmation", screen_source)
        self.assertIn("st.session_state.consent_given = True", screen_source)

    def test_layout_is_single_column_without_inner_scroll(self):
        styles = Path("ui/styles.py").read_text(encoding="utf-8-sig")
        self.assertIn(".information-section", styles)
        self.assertNotIn(".information-section {\n            overflow", styles)
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        self.assertIn("for section_number", source)

    def test_game_header_is_not_rendered_before_information_sheet(self):
        source = Path("app.py").read_text(encoding="utf-8-sig")
        consent_branch = source[
            source.index("if not st.session_state.consent_given"):
            source.index("if not st.session_state.started")
        ]
        self.assertIn("screen_consent()", consent_branch)
        self.assertNotIn("render_app_header()", consent_branch)


if __name__ == "__main__":
    unittest.main()
