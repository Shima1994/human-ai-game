import unittest
from pathlib import Path


class StudyBrandingTests(unittest.TestCase):
    def test_all_three_study_pages_use_compact_logo_sizes(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        self.assertEqual(source.count('"university_duisburg_essen.png"), width=190'), 3)
        self.assertEqual(source.count('"colaps.png"), width=180'), 3)

    def test_compact_branding_css_is_shared_and_responsive(self):
        styles = Path("ui/styles.py").read_text(encoding="utf-8-sig")
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
