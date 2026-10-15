"""Schema 2.4.0: no per-round medal anywhere, AI-only clue fields named as
such, and the timing columns hold the human's own time only."""

import unittest
from pathlib import Path

from core import storage
from core.constants import SCHEMA_VERSION
from tests.test_data_integrity import _GameAndStorageState


def _turn(clue_giver):
    guesser = "ai" if clue_giver == "human" else "human"
    return {
        "turn": 1, "clue_giver": clue_giver, "guesser": guesser, "hint": "x", "hint_number": 1,
        "guesses": [], "hint_explanation": "secret reasoning", "hint_attempts": 2,
        "hint_time_sec": 41.5, "guess_time_sec": 2.25,
    }


class SchemaTwoFourTests(_GameAndStorageState):
    def test_version_and_field_names(self):
        self.assertEqual(SCHEMA_VERSION, "2.4.0")
        for gone in ("hint_explanation", "hint_attempts", "hint_time_sec", "guess_time_sec"):
            self.assertNotIn(gone, storage.TURNS_LOG_FIELDS)
        for new in ("ai_clue_reasoning", "ai_clue_attempts", "human_clue_time_sec", "human_guess_time_sec"):
            self.assertIn(new, storage.TURNS_LOG_FIELDS)
        self.assertNotIn("medal", storage.ROUNDS_LOG_FIELDS)

    def test_human_clue_turn_keeps_only_the_humans_clue_time(self):
        row = storage._turn_analysis_row("p1", _turn("human"), self.state.word_type_per_card)
        self.assertEqual(row["human_clue_time_sec"], "41.500")
        self.assertEqual(row["human_guess_time_sec"], "")
        self.assertEqual(row["ai_clue_reasoning"], "")
        self.assertEqual(row["ai_clue_attempts"], "")

    def test_ai_clue_turn_keeps_only_the_humans_guess_time(self):
        row = storage._turn_analysis_row("p1", _turn("ai"), self.state.word_type_per_card)
        self.assertEqual(row["human_clue_time_sec"], "")
        self.assertEqual(row["human_guess_time_sec"], "2.250")
        self.assertEqual(row["ai_clue_reasoning"], "secret reasoning")
        self.assertEqual(row["ai_clue_attempts"], 2)

    def test_debriefing_time_is_stored_on_the_session_row(self):
        self.assertIn("debriefing_acknowledged_at", storage.SESSIONS_LOG_FIELDS)
        self.state.debriefing_acknowledged_at = "2026-10-15T12:00:00+00:00"
        self.state.update(participant_id="p1", session_start_time="", consent_given=True, prolific_pid="")
        row = storage._session_row(completed=True)
        self.assertEqual(row["debriefing_acknowledged_at"], "2026-10-15T12:00:00+00:00")

    def test_no_per_round_medal_left_in_the_code(self):
        for path in ("core/game_logic.py", "core/storage.py", "core/ai_service.py", "core/state.py", "ui/screens.py"):
            source = Path(path).read_text(encoding="utf-8-sig")
            for name in ("round_medal", "medal_counts", "get_medal_for_round", "MEDAL_POINTS"):
                self.assertNotIn(name, source, f"{name} in {path}")


if __name__ == "__main__":
    unittest.main()
