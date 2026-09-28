import unittest
from pathlib import Path


class StudyBrandingTests(unittest.TestCase):
    def test_all_three_study_pages_use_compact_logo_sizes(self):
        # The three pages share one _render_logo_row() helper (see
        # ui/screens.py) instead of each repeating the same image calls, so
        # the compact sizing only needs to be declared once -- verify the
        # helper itself is right, and that every page actually calls it.
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        self.assertEqual(source.count('"university_duisburg_essen.png"), width=190'), 1)
        self.assertEqual(source.count('"colaps.png"), width=180'), 1)
        # 1 definition + 3 call sites (one per page).
        self.assertEqual(source.count("_render_logo_row()"), 4)

    def test_compact_branding_css_is_shared_and_responsive(self):
        styles = Path("static/app.css").read_text(encoding="utf-8-sig")
        for key in (
            ".st-key-consent_logos",
            ".st-key-game_guide_logos",
            ".st-key-participant_profile_logos",
        ):
            self.assertIn(key, styles)
        self.assertIn("max-height: 58px", styles)
        self.assertIn("max-height: 50px", styles)


if __name__ == "__main__":
    unittest.main()
