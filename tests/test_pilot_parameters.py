import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from core import game_logic
from core.constants import AI_API_TIMEOUT_SECONDS, CLUE_TIMER_SECONDS


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
    )


class PilotParameterTests(unittest.TestCase):
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

    def test_three_normal_interactions_reach_turn_limit(self):
        for index in range(3):
            game_logic.record_interaction(f"clue{index}", 1, ["Delta"], ["Alpha"])
        self.assertEqual(self.state.round_interactions, 3)
        self.assertTrue(self.state.round_finished)
        self.assertEqual(
            [item["completed_turn_number"] for item in self.state.interaction_history],
            [1, 2, 3],
        )

    def test_two_full_skips_do_not_consume_completed_turns(self):
        game_logic.record_skip("first", 1, ["Alpha"], skipped_by="human")
        game_logic.record_skip("second", 1, ["Alpha"], skipped_by="human")
        self.assertEqual(self.state.round_interactions, 0)
        self.assertEqual(self.state.round_skips, 2)
        self.assertFalse(game_logic.can_skip_current_clue())
        self.assertEqual(
            [(item["turn"], item["completed_turn_number"], item["skip_number"])
             for item in self.state.interaction_history],
            [(1, 0, 1), (2, 0, 2)],
        )
        self.assertTrue(all(item["repair_required"] for item in self.state.interaction_history))

    def test_skip_availability_is_independent_of_completed_turn_count(self):
        self.state.round_interactions = 2
        self.assertTrue(game_logic.can_skip_current_clue())
        self.state.round_skips = 2
        self.assertFalse(game_logic.can_skip_current_clue())

    def test_partial_skip_is_one_interaction_and_one_skip(self):
        game_logic.record_interaction(
            "mixed",
            2,
            ["Alpha"],
            ["Alpha", "Beta"],
            partial_skip=True,
            skipped_by="human",
            skip_interpreted_cards=["Beta"],
        )
        item = self.state.interaction_history[-1]
        self.assertEqual(self.state.round_interactions, 1)
        self.assertEqual(self.state.round_skips, 1)
        self.assertEqual(item["completed_turn_number"], 1)
        self.assertEqual(item["skip_number"], 1)
        self.assertEqual(item["completed_guesses"], 1)
        self.assertEqual(item["skipped_guesses"], 1)

    def test_full_skip_repair_lineage_and_success(self):
        game_logic.record_skip("first", 1, ["Alpha"], skipped_by="human")
        skipped = self.state.interaction_history[-1]
        repair_context = {
            "skipped_turn": skipped["turn"],
            "unresolved_targets": ["Alpha"],
            "repair_chain_id": skipped["repair_chain_id"],
            "repair_attempt_number": 1,
        }
        game_logic.record_interaction(
            "repair", 1, ["Alpha"], ["Alpha"], repair_context=repair_context
        )
        repaired = self.state.interaction_history[-1]
        self.assertEqual(self.state.round_interactions, 1)
        self.assertEqual(self.state.round_skips, 1)
        self.assertEqual(repaired["repair_source_turn"], skipped["turn"])
        self.assertEqual(repaired["repair_chain_id"], skipped["repair_chain_id"])
        self.assertTrue(repaired["repair_same_targets_retried"])
        self.assertTrue(repaired["repair_success"])

    def test_human_timer_is_90_seconds_and_api_timeout_is_bounded(self):
        started = datetime(2026, 1, 1, 12, 0, 0)
        game_logic.start_participant_decision_timer(started.isoformat())
        self.assertEqual(CLUE_TIMER_SECONDS, 90)
        # Kept well under a minute: this is a per-request HTTP timeout, and it
        # compounds with the outer content-validation retry loops in
        # ai_service.py (2-3 attempts) and the OpenAI client's own
        # max_retries=1, so a large value here turns a real outage into
        # several minutes of silent, spinner-only waiting for a participant.
        self.assertLessEqual(AI_API_TIMEOUT_SECONDS, 30)
        self.assertEqual(
            game_logic.participant_decision_time_remaining(started + timedelta(seconds=89)),
            1.0,
        )
        self.assertTrue(
            game_logic.participant_decision_timer_expired(started + timedelta(seconds=90))
        )

    def test_timeout_consumes_a_skip_not_a_turn(self):
        """A timeout is treated like a skip, not a free/ordinary turn -- an
        expired decision must not let a participant collect clues without
        spending anything. (Once skips run out, a further timeout is a
        forced-loss case; see record_forced_timeout_loss.)"""
        game_logic.record_timeout("expired", 1, ["Alpha"])
        item = self.state.interaction_history[-1]
        self.assertEqual(self.state.round_interactions, 0)
        self.assertEqual(self.state.round_skips, 1)
        self.assertTrue(item["timed_out"])
        self.assertFalse(item["skipped"])
        self.assertEqual(item["completed_turn_number"], 0)
        self.assertEqual(item["skip_number"], 1)

    def test_forced_timeout_loss_ends_the_round_with_no_medal(self):
        """Once both skips are gone, a further timeout must not silently
        keep the round open (that would let a stalling participant hold the
        round -- and the clock -- open indefinitely)."""
        self.state.round_skips = 2
        game_logic.record_forced_timeout_loss("stalled", 1, ["Alpha"], ["Alpha"])
        item = self.state.interaction_history[-1]
        self.assertEqual(item["outcome"], "timeout_loss")
        self.assertTrue(item["human_timed_out"])
        self.assertTrue(self.state.round_finished)
        self.assertEqual(self.state.round_end_reason, "timeout_loss")
        # round_interactions/round_skips are untouched -- this isn't an
        # ordinary turn or skip, it's the round ending outright.
        self.assertEqual(self.state.round_skips, 2)

    def test_forced_timeout_loss_is_consumed_only_once(self):
        self.state.round_skips = 2
        game_logic.record_forced_timeout_loss("stalled", 1, ["Alpha"], ["Alpha"])
        history_len = len(self.state.interaction_history)
        game_logic.record_forced_timeout_loss("stalled", 1, ["Alpha"], ["Alpha"])
        self.assertEqual(len(self.state.interaction_history), history_len)


class RoundBoardOrderTests(unittest.TestCase):
    """The 4 fixed boards (core.words.ROUND_BOARDS) must play in a shuffled
    order per session, not always B01 in round 1, B02 in round 2, etc. --
    see core.state._new_round_board_order and
    core.game_logic._board_number_for_round."""

    def setUp(self):
        self.original_st = game_logic.st
        self.state = base_state()
        game_logic.st = SimpleNamespace(session_state=self.state)

    def tearDown(self):
        game_logic.st = self.original_st

    def test_new_round_board_order_is_a_shuffled_permutation(self):
        from core.state import _new_round_board_order
        from core.words import ROUND_BOARDS

        order = _new_round_board_order()
        self.assertEqual(sorted(order), sorted(ROUND_BOARDS.keys()))

    def test_get_board_template_id_follows_the_shuffled_order(self):
        from core.words import ROUND_BOARDS

        self.state.round_board_order = [3, 1, 4, 2]
        self.assertEqual(game_logic.get_board_template_id(1), ROUND_BOARDS[3]["id"])
        self.assertEqual(game_logic.get_board_template_id(2), ROUND_BOARDS[1]["id"])
        self.assertEqual(game_logic.get_board_template_id(3), ROUND_BOARDS[4]["id"])
        self.assertEqual(game_logic.get_board_template_id(4), ROUND_BOARDS[2]["id"])

    def test_sample_fixed_round_words_follows_the_shuffled_order(self):
        from core.words import ROUND_BOARDS

        self.state.round_board_order = [3, 1, 4, 2]
        _board, _targets, _neutrals, _bombs, _roles, _types, template_type = (
            game_logic.sample_fixed_round_words(1)
        )
        self.assertEqual(template_type, ROUND_BOARDS[3]["id"])

    def test_falls_back_to_direct_mapping_without_a_shuffled_order(self):
        """An older/incomplete session_state with no round_board_order set
        must not crash -- it degrades to the original fixed 1:1 mapping."""
        from core.words import ROUND_BOARDS

        self.state.pop("round_board_order", None)
        self.assertEqual(game_logic.get_board_template_id(2), ROUND_BOARDS[2]["id"])


if __name__ == "__main__":
    unittest.main()
