"""Points beside correct cards in the History appear only in the adaptive
game; and granting the clue-giver's extra time must not restart the page
(that reset the clue number and dropped selected target cards)."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui import components, screens

TURN = {
    "turn": 1,
    "clue_giver": "ai",
    "guesser": "human",
    "hint": "married",
    "hint_number": 2,
    "intended_targets": ["Promise", "Ring"],
    "expected_guesses": [],
    "guesses": ["Promise", "Honesty"],
    "correct_guesses": ["Promise", "Honesty"],
    "neutral_guesses": [],
    "correct": True,
    "outcome": "correct",
}


def _history_html(show_points):
    fake_st = SimpleNamespace(markdown=MagicMock(), session_state={})
    with patch.object(components, "st", fake_st):
        components.render_interaction_history([TURN], show_points=show_points)
    return fake_st.markdown.call_args.args[0]


def _sidebar_show_points(share, tutorial_completed):
    fake_st = MagicMock()
    fake_st.session_state = {"tutorial_completed": tutorial_completed}
    with patch.object(screens, "st", fake_st), patch.object(screens, "render_interaction_history") as render:
        screens._render_live_history_sidebar([TURN], share)
    return render.call_args.kwargs["show_points"]


class HistoryPointsTests(unittest.TestCase):
    def test_points_beside_each_correct_card_when_enabled(self):
        html = _history_html(show_points=True)
        self.assertIn("Promise <span class='history-chip-points'>+2</span>", html)
        self.assertIn("Honesty <span class='history-chip-points'>+1</span>", html)

    def test_no_points_when_disabled(self):
        self.assertNotIn("history-chip-points", _history_html(show_points=False))

    def test_only_the_adaptive_game_shows_points(self):
        self.assertTrue(_sidebar_show_points(share=True, tutorial_completed=True))
        self.assertFalse(_sidebar_show_points(share=False, tutorial_completed=True))  # baseline
        self.assertFalse(_sidebar_show_points(share=True, tutorial_completed=False))  # tutorial


class ExtraTimeKeepsTheFormTests(unittest.TestCase):
    def test_granting_extra_time_does_not_restart_the_page(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        handler = source[source.index("def _consume_human_clue_timeout"):]
        grant = handler[handler.index("if grant_clue_giver_extra_time():"):handler.index("turn_index = _current_action_index()")]
        self.assertIn("return False", grant)
        self.assertNotIn("st.rerun()", grant)
        self.assertIn("_clue_extra_time_toast()", grant)


if __name__ == "__main__":
    unittest.main()
