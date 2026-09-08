import unittest
from pathlib import Path


class PageNavigationTests(unittest.TestCase):
    def test_navigation_scrolls_only_when_the_view_key_changes(self):
        app_source = Path("app.py").read_text(encoding="utf-8-sig")
        self.assertIn("def _current_view_key():", app_source)
        self.assertIn("previous_view != current_view", app_source)
        self.assertIn("scroll_page_to_top()", app_source)
        self.assertIn("tutorial_step", app_source)
        self.assertIn("post_study_questionnaire", app_source)
        self.assertIn("debriefing", app_source)
        self.assertIn("completion", app_source)
        self.assertIn("round_finished", app_source)

    def test_scroll_helper_targets_the_parent_streamlit_viewport(self):
        source = Path("ui/components.py").read_text(encoding="utf-8-sig")
        self.assertIn("def scroll_page_to_top():", source)
        self.assertIn("window.parent", source)
        self.assertIn('stAppViewContainer', source)
        self.assertIn('stMain', source)


if __name__ == "__main__":
    unittest.main()
