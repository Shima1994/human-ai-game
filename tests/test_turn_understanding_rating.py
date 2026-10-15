"""After every turn the participant answers one role-specific question, and
each question has its own stored field -- no field whose meaning depends on
the role or on whether guesses were made."""

import unittest
from pathlib import Path
from unittest.mock import patch

from core import storage
from ui import screens

CLUE_FIELD = "human_rating_ai_understood_my_clue"
GUESS_FIELD = "human_rating_i_understood_ai_clue"


class TurnUnderstandingRatingTests(unittest.TestCase):
    def test_question_depends_only_on_the_role(self):
        self.assertEqual(
            screens._turn_understanding_question(True),
            "How well do you think the AI understood your clue?",
        )
        self.assertEqual(
            screens._turn_understanding_question(False),
            "How well do you think you understood the AI's clue?",
        )

    def test_each_role_writes_its_own_field(self):
        with patch.object(screens, "_sync_reflection_to_round_summary"), patch.object(
            screens, "st"
        ) as fake_st:
            fake_st.session_state = type("S", (dict,), {"__setattr__": dict.__setitem__})()
            clue_turn = {"clue_giver": "human", "turn": 1}
            guess_turn = {"clue_giver": "ai", "turn": 2}
            screens._save_turn_reflection(clue_turn, 4, "", "")
            screens._save_turn_reflection(guess_turn, 2, "", "")
        self.assertEqual(clue_turn[CLUE_FIELD], 4)
        self.assertNotIn(GUESS_FIELD, clue_turn)
        self.assertEqual(guess_turn[GUESS_FIELD], 2)
        self.assertNotIn(CLUE_FIELD, guess_turn)

    def test_turn_rows_have_one_field_per_question(self):
        self.assertIn(CLUE_FIELD, storage.TURNS_LOG_FIELDS)
        self.assertIn(GUESS_FIELD, storage.TURNS_LOG_FIELDS)
        self.assertIn("human_expected_ai_understanding_rating", storage.TURNS_LOG_FIELDS)
        self.assertNotIn("human_perceived_understanding_rating", storage.TURNS_LOG_FIELDS)

    def test_tutorial_and_guide_ask_the_same_questions_as_the_game(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        guide = Path("ui/guide_walkthrough.py").read_text(encoding="utf-8-sig")
        for text in (source, guide):
            self.assertNotIn("understood each other", text)
            self.assertNotIn("you understood the AI?", text)
        self.assertIn("TURN_RATING_GUESSER,", source)
        self.assertIn("TURN_RATING_CLUE_GIVER,", source)
        self.assertIn("How well do you think you understood the AI's clue?", guide)


if __name__ == "__main__":
    unittest.main()
