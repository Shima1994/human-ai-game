import unittest
from types import SimpleNamespace

from core import game_logic
from core.constants import (
    FINAL_MEDAL_BRONZE_MIN,
    FINAL_MEDAL_GOLD_MIN,
    FINAL_MEDAL_SILVER_MIN,
    MAX_POSSIBLE_SESSION_SCORE,
    N_ROUNDS,
    POINTS_EXACT_INTENDED_TARGET,
    POINTS_OTHER_TARGET,
    TARGET_COUNT,
)


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def base_state(role="ai_clue"):
    return State(
        session_id="test-session",
        round=1,
        role=role,
        round_interactions=0,
        round_skips=0,
        interaction_history=[],
        target_words=["Alpha", "Beta", "Gamma"],
        neutral_words=["Delta"],
        bomb_words=["Bomb"],
        bomb_word="Bomb",
        found_targets=[],
        guesses=[],
        used_hints=[],
        current_turn_start_time="",
        clue_timer_started_at="",
        clue_timer_duration_seconds=0,
        clue_timer_timeout_consumed=False,
        pending_reflection_turn=None,
        round_star=False,
        round_star_awarded_at="",
        total_stars_so_far=0,
    )


class TurnPointsTests(unittest.TestCase):
    """core.game_logic.record_interaction's per-card behavioural points --
    +2 for a guess matching the clue-giver's own intended card, +1 for any
    other valid target, 0 for neutral/bomb, and never scoring a partial
    skip's un-guessed remaining cards. See core/constants.py's
    POINTS_EXACT_INTENDED_TARGET/POINTS_OTHER_TARGET."""

    def setUp(self):
        self.original_st = game_logic.st
        self.original_finish_round = game_logic.finish_round
        self.state = base_state()
        game_logic.st = SimpleNamespace(session_state=self.state)
        game_logic.finish_round = lambda forced_loss_reason=None: (
            self.state.__setitem__("round_finished", True),
            self.state.__setitem__("round_end_reason", forced_loss_reason or ""),
        )

    def tearDown(self):
        game_logic.st = self.original_st
        game_logic.finish_round = self.original_finish_round

    def test_exact_intended_target_awards_two_points(self):
        game_logic.record_interaction("clue", 1, ["Alpha"], intended_targets=["Alpha"])
        item = self.state.interaction_history[-1]
        self.assertEqual(item["turn_points"], POINTS_EXACT_INTENDED_TARGET)

    def test_other_valid_target_awards_one_point(self):
        game_logic.record_interaction("clue", 1, ["Alpha"], intended_targets=["Beta"])
        item = self.state.interaction_history[-1]
        self.assertEqual(item["turn_points"], POINTS_OTHER_TARGET)

    def test_neutral_guess_awards_zero_points(self):
        game_logic.record_interaction("clue", 1, ["Delta"], intended_targets=["Alpha"])
        item = self.state.interaction_history[-1]
        self.assertEqual(item["turn_points"], 0)

    def test_bomb_guess_awards_zero_points(self):
        game_logic.record_interaction("clue", 1, ["Bomb"], intended_targets=["Alpha"])
        item = self.state.interaction_history[-1]
        self.assertEqual(item["turn_points"], 0)
        self.assertTrue(item["bomb_hit"])

    def test_mixed_turn_sums_points_per_card(self):
        game_logic.record_interaction(
            "clue", 3, ["Alpha", "Beta", "Delta"], intended_targets=["Alpha"]
        )
        item = self.state.interaction_history[-1]
        self.assertEqual(
            item["turn_points"], POINTS_EXACT_INTENDED_TARGET + POINTS_OTHER_TARGET
        )

    def test_partial_skip_only_scores_actual_guesses_made(self):
        """The un-guessed remaining cards of a partial skip must never be
        scored -- only what was actually selected before skipping."""
        game_logic.record_interaction(
            "clue",
            2,
            ["Alpha"],
            intended_targets=["Alpha", "Beta"],
            partial_skip=True,
            skipped_by="human",
            skip_interpreted_cards=["Beta"],
        )
        item = self.state.interaction_history[-1]
        self.assertEqual(item["turn_points"], POINTS_EXACT_INTENDED_TARGET)

    def test_full_skip_awards_zero_points(self):
        game_logic.record_skip("clue", 1, ["Alpha"], skipped_by="human")
        item = self.state.interaction_history[-1]
        self.assertEqual(item["turn_points"], 0)

    def test_forced_timeout_loss_awards_zero_points(self):
        self.state.round_skips = 2
        game_logic.record_forced_timeout_loss("stalled", 1, ["Alpha"], ["Alpha"])
        item = self.state.interaction_history[-1]
        self.assertEqual(item["turn_points"], 0)

    def test_compute_round_score_sums_turn_points_across_the_round(self):
        game_logic.record_interaction("c1", 1, ["Alpha"], intended_targets=["Alpha"])
        game_logic.record_interaction("c2", 1, ["Beta"], intended_targets=["Gamma"])
        game_logic.record_skip("c3", 1, ["Gamma"], skipped_by="human")
        self.assertEqual(
            game_logic.compute_round_score(self.state.interaction_history),
            POINTS_EXACT_INTENDED_TARGET + POINTS_OTHER_TARGET,
        )


class RoundStarTests(unittest.TestCase):
    """core.game_logic.finish_round's round-completion star: awarded only
    when all TARGET_COUNT targets are found and no bomb was selected."""

    def setUp(self):
        self.original_st = game_logic.st
        self.original_summary = game_logic.append_ai_round_summary
        self.state = base_state()
        game_logic.st = SimpleNamespace(session_state=self.state)
        # append_ai_round_summary needs a fully-populated board/word-type
        # context this test doesn't set up -- it's irrelevant to star
        # scoring, so it's stubbed out the same way finish_round is stubbed
        # in TurnPointsTests above.
        game_logic.append_ai_round_summary = lambda: None

    def tearDown(self):
        game_logic.st = self.original_st
        game_logic.append_ai_round_summary = self.original_summary

    def test_star_awarded_when_all_targets_found_without_a_bomb(self):
        game_logic.record_interaction(
            "c1", 3, ["Alpha", "Beta", "Gamma"], intended_targets=["Alpha"]
        )
        self.assertTrue(self.state.round_star)
        self.assertNotEqual(self.state.round_star_awarded_at, "")
        self.assertEqual(self.state.total_stars_so_far, 1)

    def test_no_star_on_bomb_hit_even_if_targets_also_found(self):
        game_logic.record_interaction(
            "c1", 4, ["Alpha", "Beta", "Gamma", "Bomb"], intended_targets=["Alpha"]
        )
        self.assertFalse(self.state.round_star)
        self.assertEqual(self.state.round_star_awarded_at, "")
        self.assertEqual(self.state.total_stars_so_far, 0)

    def test_no_star_when_round_ends_without_finding_all_targets(self):
        for index in range(3):
            game_logic.record_interaction(f"c{index}", 1, ["Delta"], intended_targets=["Alpha"])
        self.assertTrue(self.state.round_finished)
        self.assertFalse(self.state.round_star)
        self.assertEqual(self.state.total_stars_so_far, 0)

    def test_partial_skip_does_not_itself_block_a_star(self):
        game_logic.record_interaction(
            "c1",
            2,
            ["Alpha"],
            intended_targets=["Alpha", "Beta"],
            partial_skip=True,
            skipped_by="human",
            skip_interpreted_cards=["Beta"],
        )
        game_logic.record_interaction(
            "c2", 2, ["Beta", "Gamma"], intended_targets=["Beta", "Gamma"]
        )
        self.assertTrue(self.state.round_star)
        self.assertEqual(self.state.total_stars_so_far, 1)


class FinalMedalTests(unittest.TestCase):
    def test_max_possible_session_score_matches_four_rounds_of_exact_matches(self):
        self.assertEqual(
            MAX_POSSIBLE_SESSION_SCORE,
            N_ROUNDS * TARGET_COUNT * POINTS_EXACT_INTENDED_TARGET,
        )

    def test_thresholds_match_the_documented_bands(self):
        self.assertEqual(game_logic.get_final_medal(FINAL_MEDAL_GOLD_MIN), "gold")
        self.assertEqual(game_logic.get_final_medal(MAX_POSSIBLE_SESSION_SCORE), "gold")
        self.assertEqual(game_logic.get_final_medal(FINAL_MEDAL_GOLD_MIN - 1), "silver")
        self.assertEqual(game_logic.get_final_medal(FINAL_MEDAL_SILVER_MIN), "silver")
        self.assertEqual(game_logic.get_final_medal(FINAL_MEDAL_SILVER_MIN - 1), "bronze")
        self.assertEqual(game_logic.get_final_medal(FINAL_MEDAL_BRONZE_MIN), "bronze")
        self.assertEqual(game_logic.get_final_medal(FINAL_MEDAL_BRONZE_MIN - 1), "none")
        self.assertEqual(game_logic.get_final_medal(0), "none")


class TurnPointsMessageTests(unittest.TestCase):
    """ui.screens._turn_points_message's exact player-facing wording, as
    specified: 'Great match! +2 points' for an exact intended target,
    'Valid target found! +1 point' for any other valid target -- and no
    message at all for a bomb, skip, or all-neutral turn."""

    def setUp(self):
        from ui import screens

        self.screens = screens

    def test_exact_intended_target_wording(self):
        message = self.screens._turn_points_message(
            {
                "outcome": "correct",
                "correct_guesses": ["Alpha"],
                "intended_targets": ["Alpha"],
                "turn_points": 2,
            }
        )
        self.assertEqual(message, "Great match! +2 points")

    def test_other_valid_target_wording(self):
        message = self.screens._turn_points_message(
            {
                "outcome": "correct",
                "correct_guesses": ["Alpha"],
                "intended_targets": ["Beta"],
                "turn_points": 1,
            }
        )
        self.assertEqual(message, "Valid target found! +1 point")

    def test_bomb_turn_has_no_points_message(self):
        message = self.screens._turn_points_message(
            {
                "outcome": "bomb",
                "correct_guesses": [],
                "intended_targets": ["Alpha"],
                "turn_points": 0,
            }
        )
        self.assertEqual(message, "")

    def test_all_neutral_turn_has_no_points_message(self):
        message = self.screens._turn_points_message(
            {
                "outcome": "wrong",
                "correct_guesses": [],
                "intended_targets": ["Alpha"],
                "turn_points": 0,
            }
        )
        self.assertEqual(message, "")

    def test_multi_card_turn_uses_generic_wording(self):
        message = self.screens._turn_points_message(
            {
                "outcome": "correct",
                "correct_guesses": ["Alpha", "Beta"],
                "intended_targets": ["Alpha"],
                "turn_points": 3,
            }
        )
        self.assertEqual(message, "+3 points this turn")


if __name__ == "__main__":
    unittest.main()
