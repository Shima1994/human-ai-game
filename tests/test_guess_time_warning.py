"""Guessing has no extra time; instead a pop-up warns once when 30 seconds
are left. The clue-giver timer has no such warning (it gets extra time)."""

import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui import components


def _timer_markup(remaining, warning_id="", **state):
    fake_st = SimpleNamespace(session_state=dict(state), markdown=MagicMock())
    fake_st.session_state = type("S", (dict,), {"get": dict.get})(state)
    with patch.object(components, "st", fake_st), patch.object(
        components, "st_components"
    ), patch.object(components, "st_autorefresh"):
        components.render_clue_timer(remaining, pinned=False, warning_id=warning_id)
    return fake_st.markdown.call_args.args[0]


class GuessTimeWarningTests(unittest.TestCase):
    def test_guessing_timer_carries_the_30_second_warning(self):
        markup = _timer_markup(80, warning_id="2026-01-01T00:00:00")
        self.assertIn('data-warn-ms="30000"', markup)
        self.assertIn('data-warn-id="2026-01-01T00:00:00"', markup)
        self.assertIn("Only 30 seconds left", markup)

    def test_no_warning_without_an_id_or_in_the_final_chance_window(self):
        self.assertNotIn("data-warn", _timer_markup(80))
        self.assertNotIn(
            "data-warn",
            _timer_markup(30, warning_id="x", final_guess_deadline_active=True),
        )

    def test_only_the_two_guessing_screens_turn_the_warning_on(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        calls = re.findall(r"render_clue_timer\((.*?)\)\n", source, re.S)
        with_warning = [call for call in calls if "warning_id" in call]
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(with_warning), 2)
        tutorial_guess = source[source.index('if step == "ai_clue_round"'):source.index('if step == "human_clue_round"')]
        self.assertIn("warning_id=", tutorial_guess)
        real_guess = source[source.index("def screen_human_guesser"):]
        self.assertIn("warning_id=", real_guess[: real_guess.index("human_guesser_board_wrap")])

    def test_pop_up_is_shown_once_per_timer_by_the_ticking_script(self):
        source = Path("ui/components.py").read_text(encoding="utf-8-sig")
        self.assertIn("__guessTimeWarnings", source)
        self.assertIn("timer-warning-popup", source)
        styles = Path("static/app.css").read_text(encoding="utf-8-sig")
        self.assertIn(".timer-warning-popup", styles)


if __name__ == "__main__":
    unittest.main()
