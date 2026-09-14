import ast
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from core.constants import CLUE_TIMER_SECONDS
from core.tutorial import (
    TUTORIAL_BOARD,
    TUTORIAL_BOMB,
    TUTORIAL_CLUE,
    TUTORIAL_CLUE_NUMBER,
    TUTORIAL_NEUTRALS,
    TUTORIAL_ROUND_2_BOARD,
    TUTORIAL_ROUND_2_NEUTRALS,
    TUTORIAL_ROUND_2_TARGETS,
    TUTORIAL_ROUND_2_WORD_ROLES,
    TUTORIAL_TARGETS,
    TUTORIAL_WORD_ROLES,
    simulated_ai_guesses,
    tutorial_clue_is_valid,
    tutorial_comprehension_is_correct,
    tutorial_rationale_is_valid,
    tutorial_repair_clue,
    tutorial_selection_is_correct,
    tutorial_time_remaining,
)
from core.words import WORD_BANKS


class TutorialTests(unittest.TestCase):
    def test_board_is_fixed_disjoint_and_has_expected_roles(self):
        experimental_words = {
            word.lower() for pool in WORD_BANKS.values() for word in pool
        }
        self.assertEqual(
            TUTORIAL_BOARD, ("Cat", "Dog", "Apple", "Table", "Train", "River")
        )
        self.assertEqual(len(TUTORIAL_BOARD), 6)
        self.assertFalse({word.lower() for word in TUTORIAL_BOARD} & experimental_words)
        self.assertEqual(TUTORIAL_TARGETS, {"Cat", "Dog"})
        self.assertEqual(TUTORIAL_NEUTRALS, {"Apple", "Table", "Train"})
        self.assertEqual(TUTORIAL_BOMB, "River")
        self.assertEqual(
            [TUTORIAL_WORD_ROLES[word] for word in TUTORIAL_BOARD],
            ["target", "target", "neutral", "neutral", "neutral", "bomb"],
        )

    def test_static_clue_selection_and_comprehension(self):
        self.assertEqual((TUTORIAL_CLUE, TUTORIAL_CLUE_NUMBER), ("Pet", 2))
        self.assertTrue(tutorial_selection_is_correct(["Dog", "Cat"]))
        self.assertFalse(tutorial_selection_is_correct(["Cat", "Apple"]))
        self.assertTrue(tutorial_comprehension_is_correct(2))
        self.assertFalse(tutorial_comprehension_is_correct(1))
        self.assertTrue(tutorial_rationale_is_valid("Both are household pets"))
        self.assertFalse(tutorial_rationale_is_valid("dog and cat"))
        self.assertFalse(tutorial_rationale_is_valid("pets"))
        self.assertTrue(tutorial_clue_is_valid("Animals"))
        self.assertFalse(tutorial_clue_is_valid("two words"))

    def test_repair_clues_follow_the_unresolved_target_set(self):
        self.assertEqual(tutorial_repair_clue({"Cat", "Dog"}, 1), ("Companion", 2))
        self.assertEqual(tutorial_repair_clue({"Cat", "Dog"}, 2), ("Animals", 2))
        self.assertEqual(tutorial_repair_clue({"Cat"}, 1), ("Feline", 1))
        self.assertEqual(tutorial_repair_clue({"Dog"}, 1), ("Canine", 1))

    def test_second_round_uses_a_distinct_board_and_targets(self):
        self.assertEqual(
            TUTORIAL_ROUND_2_BOARD,
            ("Cat", "Dog", "Apple", "Table", "Orange", "River"),
        )
        experimental_words = {
            word.lower() for pool in WORD_BANKS.values() for word in pool
        }
        self.assertFalse(
            {word.lower() for word in TUTORIAL_ROUND_2_BOARD} & experimental_words
        )
        self.assertEqual(TUTORIAL_ROUND_2_TARGETS, {"Apple", "Orange"})
        self.assertEqual(TUTORIAL_ROUND_2_NEUTRALS, {"Cat", "Dog", "Table"})
        self.assertEqual(
            [TUTORIAL_ROUND_2_WORD_ROLES[word] for word in TUTORIAL_ROUND_2_BOARD],
            ["neutral", "neutral", "target", "neutral", "target", "bomb"],
        )
        self.assertEqual(simulated_ai_guesses(2), ["Apple", "Orange"])

    def test_tutorial_has_two_role_rounds_and_three_by_two_board(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        self.assertIn('step == "ai_clue_round"', source)
        self.assertIn('step == "human_clue_round"', source)
        self.assertGreaterEqual(source.count("column_count=3"), 2)
        self.assertIn("Which cards do you expect the AI to guess?", source)
        self.assertIn("General link (3–20 English words, no card names)", source)
        self.assertIn("How well do you expect the AI to understand your clue?", source)
        self.assertIn("After the guesses, how well do you think", source)
        self.assertIn('clickable=not bool(st.session_state.get("tutorial_practice_result"))', source)
        self.assertIn('key_prefix=f"tutorial_board_button_{repair_attempt}"', source)
        self.assertIn('key_prefix="tutorial_hint_target"', source)
        # Only the real target words are offered, like the real game -- not
        # the whole board with non-targets shown disabled.
        self.assertIn(
            "render_hint_target_selector(\n                tutorial_target_options,",
            source,
        )
        self.assertIn("Stop guessing and use 1 skip", source)
        self.assertIn("tutorial_skip_interpretation_", source)
        self.assertIn("MAX_SKIPS_PER_ROUND", source)
        self.assertIn("MAX_INTERACTIONS_PER_ROUND", source)
        ai_round = source[source.index('if step == "ai_clue_round"'):source.index('if step == "human_clue_round"')]
        self.assertLess(ai_round.index("Why do these cards fit the clue?"), ai_round.index("render_board("))

    def test_timer_reuses_central_human_limit(self):
        started = datetime(2026, 1, 1, 12, 0, 0)
        self.assertEqual(CLUE_TIMER_SECONDS, 90)
        self.assertEqual(tutorial_time_remaining(started.isoformat(), started), 90.0)
        self.assertEqual(
            tutorial_time_remaining(started.isoformat(), started + timedelta(seconds=90)),
            0.0,
        )

    def test_tutorial_has_no_ai_condition_or_experimental_recording_calls(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "screen_tutorial"
        )
        called = {
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse(
            called
            & {
                "ai_guess",
                "generate_ai_hint",
                "generate_ai_turn_explanation",
                "record_interaction",
                "record_skip",
                "record_timeout",
                "log_round",
                "log_event",
            }
        )
        referenced_names = {
            node.id for node in ast.walk(function) if isinstance(node, ast.Name)
        }
        self.assertNotIn("DEFAULT_CONDITION", referenced_names)

    def test_tutorial_precedes_board_setup(self):
        source = Path("app.py").read_text(encoding="utf-8-sig")
        self.assertLess(
            source.index("if not st.session_state.tutorial_completed"),
            source.index("if st.session_state.board is None"),
        )


if __name__ == "__main__":
    unittest.main()
