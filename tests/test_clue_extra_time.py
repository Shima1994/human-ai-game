"""The clue-giver gets 30 extra seconds once per clue when the 120-second
timer runs out; only after that is it a timeout, with the old rules."""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core import game_logic, storage
from core.constants import CLUE_GIVER_EXTRA_SECONDS, CLUE_GIVER_TIMER_SECONDS
from tests.test_data_integrity import _GameAndStorageState


class ClueExtraTimeTests(_GameAndStorageState):
    def _start(self, seconds_ago):
        started = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        game_logic.start_participant_decision_timer(
            started.isoformat(), duration_seconds=CLUE_GIVER_TIMER_SECONDS
        )

    def test_extra_time_is_given_once_and_extends_the_deadline(self):
        self._start(CLUE_GIVER_TIMER_SECONDS + 1)
        self.assertTrue(game_logic.participant_decision_timer_expired())

        self.assertTrue(game_logic.grant_clue_giver_extra_time())
        self.assertFalse(game_logic.participant_decision_timer_expired())
        self.assertEqual(
            self.state.clue_timer_duration_seconds,
            CLUE_GIVER_TIMER_SECONDS + CLUE_GIVER_EXTRA_SECONDS,
        )
        # A second expiry within the same clue is an ordinary timeout.
        self.assertFalse(game_logic.grant_clue_giver_extra_time())

    def test_every_new_clue_gets_its_own_extra_time(self):
        self._start(CLUE_GIVER_TIMER_SECONDS + 1)
        game_logic.grant_clue_giver_extra_time()
        self._start(0)
        self.assertFalse(self.state.clue_extra_time_granted)
        self.assertTrue(game_logic.grant_clue_giver_extra_time())

    def test_turn_row_records_whether_the_extra_time_was_used(self):
        self.assertIn("clue_extra_time_used", storage.TURNS_LOG_FIELDS)
        row = storage._turn_analysis_row(
            "p1",
            {"turn": 1, "clue_giver": "human", "guesser": "ai", "clue_extra_time_used": True},
            self.state.word_type_per_card,
        )
        self.assertIs(row["clue_extra_time_used"], True)


class ClueExtraTimeScreenTests(unittest.TestCase):
    def test_expiry_gives_extra_time_before_the_timeout_rules(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        handler = source[source.index("def _consume_human_clue_timeout"):]
        self.assertLess(
            handler.index("grant_clue_giver_extra_time()"),
            handler.index("record_timeout("),
        )
        self.assertIn('"clue_extra_time_granted"', handler)

    def test_practice_clue_round_gives_the_same_extra_time(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        clue_round = source[source.index('if step == "human_clue_round"'):]
        clue_round = clue_round[: clue_round.index("tutorial_human_clue_panel")]
        self.assertIn("CLUE_GIVER_EXTRA_SECONDS", clue_round)
        self.assertIn("_clue_extra_time_toast()", clue_round)


if __name__ == "__main__":
    unittest.main()
