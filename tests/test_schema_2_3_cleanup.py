"""Schema 2.3.0: no column repeats another one, missing values are stored as
"" (never null), the guess prompt states the real bomb rule, and the prompt
version labels name this prompt set."""

import unittest

from core import ai_service, storage
from core.constants import SCHEMA_VERSION
from tests.test_data_integrity import _GameAndStorageState

REMOVED = {
    "rounds": {"remaining_targets_start", "bomb_selected"},
    "turns": {"ai_explanation", "human_timed_out", "turn_score_delta"},
}


class SchemaCleanupTests(_GameAndStorageState):
    def test_duplicate_columns_are_gone_and_their_originals_stay(self):
        self.assertGreaterEqual(SCHEMA_VERSION, "2.3.0")
        self.assertFalse(REMOVED["rounds"] & set(storage.ROUNDS_LOG_FIELDS))
        self.assertFalse(REMOVED["turns"] & set(storage.TURNS_LOG_FIELDS))
        for kept in ("target_words", "round_terminated_by_bomb"):
            self.assertIn(kept, storage.ROUNDS_LOG_FIELDS)
        for kept in ("ai_explanation_sanitized", "timed_out", "target_yield"):
            self.assertIn(kept, storage.TURNS_LOG_FIELDS)

    def test_turn_row_has_no_null_values(self):
        item = {
            "turn": 1, "clue_giver": "ai", "guesser": "human", "hint": "x", "hint_number": 1,
            "guesses": [], "human_expected_ai_understanding_rating": None, "hint_attempts": None,
        }
        row = storage._turn_analysis_row("p1", item, self.state.word_type_per_card)
        self.assertEqual(row["human_expected_ai_understanding_rating"], "")
        self.assertEqual(row["ai_clue_attempts"], "")
        self.assertEqual(set(row), set(storage.TURNS_LOG_FIELDS))


class PromptCorrectnessTests(unittest.TestCase):
    def test_guess_prompts_state_the_real_bomb_rule(self):
        for prompt in (ai_service.GUESS_SYSTEM_PROMPT, ai_service.BASELINE_GUESS_SYSTEM_PROMPT):
            self.assertNotIn("zero points", prompt)
            self.assertIn("points already earned this round still count", prompt)

    def test_prompt_version_labels_are_current(self):
        source = open("core/storage.py", encoding="utf-8").read()
        self.assertIn('prompt_version = "hint_v4_condition_memory"', source)
        self.assertIn('prompt_version = "guess_v4_partial_skip"', source)
        self.assertNotIn("_v2_", source)
        self.assertNotIn("_v3_", source)


if __name__ == "__main__":
    unittest.main()
