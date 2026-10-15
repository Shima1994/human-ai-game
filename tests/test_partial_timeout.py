"""When the guesser's time runs out after clicking at least one card, those
cards were already revealed, so they must count and score (a "partial
timeout"); and a notice from one round must not show up in the next."""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import game_logic, storage
from core.constants import GUESSER_TIMER_SECONDS, MAX_SKIPS_PER_ROUND
from tests.test_data_integrity import _GameAndStorageState
from ui import screens


class PartialTimeoutTests(_GameAndStorageState):
    role = "ai_clue"

    def setUp(self):
        super().setUp()
        self.state.update(
            hint="breeze",
            hint_number=2,
            hint_targets=["Alpha", "Beta"],
            hint_expected_guesses=["Alpha", "Beta"],
            hint_explanation="",
            pending_hint_meta={},
            current_guess_rationale="Things that move gently in the air",
            current_guess_start_time="",
            pending_guesses=["Alpha"],
            used_hints=[],
            final_guess_deadline_active=False,
        )
        started = datetime.now(timezone.utc) - timedelta(seconds=GUESSER_TIMER_SECONDS + 1)
        game_logic.start_participant_decision_timer(
            started.isoformat(), duration_seconds=GUESSER_TIMER_SECONDS
        )
        self.patches = [
            patch.object(screens, "st", SimpleNamespace(session_state=self.state)),
            patch.object(screens, "log_event"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        super().tearDown()

    def test_clicked_card_counts_and_uses_a_skip(self):
        self.assertTrue(screens._consume_human_guess_timeout())
        item = self.state.interaction_history[-1]
        self.assertEqual(item["outcome"], "partial_timeout")
        self.assertEqual(item["guesses"], ["Alpha"])
        self.assertEqual(item["correct_guesses"], ["Alpha"])
        self.assertGreater(item["turn_points"], 0)
        self.assertIn("Alpha", self.state.found_targets)
        self.assertEqual(self.state.round_skips, 1)
        self.assertEqual(self.state.round_interactions, 1)
        self.assertTrue(item["timed_out"])
        self.assertEqual(storage._action_classification(item), "partial_timeout")
        self.assertEqual(storage._alignment_applicability(item), "partial_selection")
        self.assertEqual(self.state.pending_reflection_turn, item["turn"])

    def test_in_the_final_window_cards_count_and_the_round_ends(self):
        self.state.round_skips = MAX_SKIPS_PER_ROUND
        self.state.final_guess_deadline_active = True
        with patch.object(screens, "finish_round", wraps=game_logic.finish_round) as finish:
            self.assertTrue(screens._consume_human_guess_timeout())
        item = self.state.interaction_history[-1]
        self.assertEqual(item["guesses"], ["Alpha"])
        self.assertIn("Alpha", self.state.found_targets)
        self.assertEqual(self.state.round_skips, MAX_SKIPS_PER_ROUND)
        finish.assert_called_once_with(forced_loss_reason="timeout_loss")

    def test_final_window_timeout_without_cards_counts_as_a_used_turn(self):
        self.state.pending_guesses = []
        self.state.round_skips = MAX_SKIPS_PER_ROUND
        self.state.round_interactions = 2
        self.state.final_guess_deadline_active = True
        with patch.object(screens, "_clear_current_clue"):
            self.assertTrue(screens._consume_human_guess_timeout())
        self.assertEqual(self.state.round_interactions, 3)
        self.assertEqual(self.state.interaction_history[-1]["completed_turn_number"], 3)

    def test_no_clicked_card_is_still_an_ordinary_timeout(self):
        self.state.pending_guesses = []
        with patch.object(screens, "record_timeout", return_value="t") as record, patch.object(
            screens, "_log_timeout"
        ):
            self.assertTrue(screens._consume_human_guess_timeout())
        record.assert_called_once()


class NoticeAndResultTextTests(unittest.TestCase):
    def test_a_new_round_clears_notices_from_the_previous_one(self):
        source = Path("core/game_logic.py").read_text(encoding="utf-8-sig")
        setup = source[source.index("def setup_new_round"):]
        setup = setup[: setup.index("\ndef ", 10)]
        for notice in (
            "clue_giver_timeout_notice",
            "last_timeout_notice",
            "final_guess_warning_notice",
        ):
            self.assertIn(f'"{notice}"', setup)

    def test_partial_skip_result_names_the_clicked_cards(self):
        kind, text = screens._guess_outcome_summary(
            {"outcome": "partial_skip", "guesses": ["Penguin"], "correct_guesses": ["Penguin"],
             "neutral_guesses": [], "bomb_guesses": []}
        )
        self.assertEqual(kind, "success")
        self.assertIn("Penguin", text)
        self.assertNotIn("no cards were guessed", text)

    def test_partial_timeout_result_says_the_cards_count(self):
        _, text = screens._guess_outcome_summary(
            {"outcome": "partial_timeout", "guesses": ["Lamp"], "correct_guesses": [],
             "neutral_guesses": ["Lamp"], "bomb_guesses": []}
        )
        self.assertIn("Time ran out, but the cards you clicked count.", text)

    def test_round_questions_have_their_own_page(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        summary = source[source.index("def screen_round_summary"):source.index("def _render_round_questions_page")]
        self.assertNotIn("_render_round_questionnaire()", summary)
        self.assertIn('st.session_state.round_reflection_saved = True', summary)
        page = source[source.index("def _render_round_questions_page"):source.index("def _advance_after_round")]
        self.assertIn("_render_round_questionnaire()", page)
        self.assertIn("Please answer all questions about this round.", page)


if __name__ == "__main__":
    unittest.main()
