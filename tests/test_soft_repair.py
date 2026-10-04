"""Repair after a skip is a nudge, never a requirement, in both directions:
the AI clue-giver is asked to strongly consider the skipped targets, and the
human clue-giver is reminded of them, but either may choose other targets."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import ai_service, game_logic


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def base_state(role):
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


REPAIR_CONTEXT = {
    "skipped_turn": 1,
    "skipped_hint": "letters",
    "unresolved_targets": ["Alpha"],
    "participant_interpretation": ["SENTINEL_INTERPRETATION"],
    "participant_reasoning": "SENTINEL_REASONING",
    "participant_reflection": "",
    "repair_chain_id": "c1",
    "repair_attempt_number": 1,
}


class SkipInvitesRepairTests(unittest.TestCase):
    def test_both_directions_invite_repair(self):
        self.assertTrue(game_logic.skip_invites_repair("ai", "human"))
        self.assertTrue(game_logic.skip_invites_repair("human", "ai"))
        self.assertFalse(game_logic.skip_invites_repair("human", ""))
        self.assertFalse(game_logic.skip_invites_repair("ai", ""))


class RecordedRepairFieldsTests(unittest.TestCase):
    def setUp(self):
        self.original_st = game_logic.st
        self.original_finish_round = game_logic.finish_round
        game_logic.finish_round = lambda forced_loss_reason=None: None

    def tearDown(self):
        game_logic.st = self.original_st
        game_logic.finish_round = self.original_finish_round

    def _use_state(self, role):
        self.state = base_state(role)
        game_logic.st = SimpleNamespace(session_state=self.state)

    def test_ai_skip_of_a_human_clue_now_invites_repair(self):
        self._use_state("human_clue")
        game_logic.record_skip("letters", 1, ["Alpha"], skipped_by="ai")
        self.assertTrue(self.state.interaction_history[-1]["repair_required"])

    def test_next_clue_may_add_other_targets(self):
        self._use_state("human_clue")
        game_logic.record_interaction(
            "greek", 2, ["Alpha", "Beta"], ["Alpha", "Beta"], repair_context=REPAIR_CONTEXT
        )
        item = self.state.interaction_history[-1]
        self.assertTrue(item["repair_attempt"])
        self.assertTrue(item["repair_targets_included"])
        self.assertFalse(item["repair_same_targets_retried"])

    def test_next_clue_may_choose_different_targets(self):
        self._use_state("human_clue")
        game_logic.record_interaction(
            "second", 1, ["Beta"], ["Beta"], repair_context=REPAIR_CONTEXT
        )
        item = self.state.interaction_history[-1]
        self.assertTrue(item["repair_attempt"])
        self.assertFalse(item["repair_targets_included"])


class AiRepairPromptTests(unittest.TestCase):
    def setUp(self):
        self.original_st = ai_service.st
        ai_service.st = SimpleNamespace(session_state=State(word_type_per_card={}))

    def tearDown(self):
        ai_service.st = self.original_st

    def _prompt(self, condition):
        return ai_service.build_hint_user_prompt(
            ["Alpha", "Beta", "Gamma"],
            ["Bomb"],
            ["Delta"],
            "mixed",
            [],
            condition=condition,
            repair_context=REPAIR_CONTEXT,
        )

    def test_prompt_recommends_but_does_not_require_the_skipped_targets(self):
        prompt = self._prompt("baseline")
        self.assertIn("not mandatory", prompt)
        self.assertIn("Alpha", prompt)
        self.assertNotIn("MANDATORY", prompt)
        self.assertNotIn("Do not replace, add, or drop targets", prompt)

    def test_baseline_repair_prompt_has_no_participant_context(self):
        prompt = self._prompt("baseline")
        self.assertNotIn("SENTINEL_INTERPRETATION", prompt)
        self.assertNotIn("SENTINEL_REASONING", prompt)

    def test_adaptive_repair_prompt_includes_participant_context(self):
        prompt = self._prompt("adaptive")
        self.assertIn("SENTINEL_INTERPRETATION", prompt)

    @patch("core.ai_service.call_openai_chat")
    def test_clue_for_other_targets_is_accepted_during_repair(self, mock_call):
        mock_call.return_value = (
            json.dumps(
                {
                    "reasoning": "r",
                    "clue": "second",
                    "number": 1,
                    "targets": ["Beta"],
                    "expected_guesses": ["Beta"],
                }
            ),
            0.01,
        )
        result = ai_service.generate_ai_hint(
            ["Alpha", "Beta", "Gamma"],
            ["Bomb"],
            ["Delta"],
            "mixed",
            history=[],
            condition="baseline",
            repair_context=REPAIR_CONTEXT,
        )
        self.assertEqual(result["intended_targets"], ["Beta"])
        self.assertEqual(result["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
