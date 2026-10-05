"""Pre-collection data-integrity checks: board material, round and timeout
context, alignment applicability, run type / eligibility, baseline prompt
isolation, and participant-visible AI explanations."""

import json
import os
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

from core import ai_service, game_logic, storage
from core.constants import BOARD_MATERIAL_VERSION
from core.words import ROUND_BOARDS


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


WORD_TYPES = {
    "Alpha": "abstract",
    "Beta": "abstract",
    "Neutral": "concrete",
    "Bomb": "concrete",
}


def game_state(role):
    return State(
        session_id="s1",
        participant_id="p1",
        condition="baseline",
        round=2,
        role=role,
        round_interactions=0,
        round_skips=0,
        interaction_history=[],
        board=["Beta", "Bomb", "Alpha", "Neutral"],
        board_template_id="B03",
        board_material_version=BOARD_MATERIAL_VERSION,
        board_instance_id="board-1",
        word_type_per_card=dict(WORD_TYPES),
        target_words=["Alpha", "Beta"],
        neutral_words=["Neutral"],
        bomb_words=["Bomb"],
        bomb_word="Bomb",
        found_targets=[],
        guesses=[],
        used_hints=[],
        current_turn_start_time="",
        clue_timer_started_at="",
        clue_timer_duration_seconds=90,
        clue_timer_timeout_consumed=False,
        pending_reflection_turn=None,
        ai_round_summaries=[],
        start_time="2026-01-01T00:00:00",
        round_start_time="2026-01-01T00:00:00",
        round_finished=False,
        round_end_reason="",
        round_bomb_hit=False,
        round_medal="none",
    )


class BoardMaterialTests(unittest.TestCase):
    def test_every_board_has_16_cards_5_targets_9_neutrals_2_bombs(self):
        for number, board in ROUND_BOARDS.items():
            with self.subTest(board=board["id"]):
                self.assertEqual(len(board["target"]), 5)
                self.assertEqual(len(board["neutral"]), 9)
                self.assertEqual(len(board["bomb"]), 2)
                words = [w for role in ("target", "neutral", "bomb") for w, _ in board[role]]
                self.assertEqual(len(set(words)), 16)

    def test_every_board_has_8_abstract_and_8_concrete_words(self):
        for number, board in ROUND_BOARDS.items():
            with self.subTest(board=board["id"]):
                types = Counter(t for role in ("target", "neutral", "bomb") for _, t in board[role])
                self.assertEqual(types, {"abstract": 8, "concrete": 8})


class _GameAndStorageState(unittest.TestCase):
    role = "human_clue"

    def setUp(self):
        self.originals = (game_logic.st, storage.st, game_logic.finish_round)
        self.state = game_state(self.role)
        game_logic.st = SimpleNamespace(session_state=self.state)
        storage.st = SimpleNamespace(session_state=self.state)
        game_logic.finish_round = lambda forced_loss_reason=None: None

    def tearDown(self):
        game_logic.st, storage.st, game_logic.finish_round = self.originals

    def turn_row(self):
        return storage._turn_analysis_row(
            "p1", self.state.interaction_history[-1], self.state.word_type_per_card
        )


class RoundContextTests(_GameAndStorageState):
    def test_round_row_has_board_material_version_and_displayed_card_order(self):
        row = storage._round_analysis_row("p1", "2026-01-01T00:05:00", 0)
        self.assertEqual(row["board_material_version"], BOARD_MATERIAL_VERSION)
        # all_board_words is stored in the shuffled on-screen order.
        self.assertEqual(json.loads(row["all_board_words"]), self.state.board)
        self.assertEqual(json.loads(row["word_type_per_card"]), WORD_TYPES)


class TimeoutContextTests(_GameAndStorageState):
    def test_timeout_row_preserves_required_context(self):
        game_logic.record_timeout("letters", 1, ["Alpha"], ["Alpha"])
        row = self.turn_row()
        self.assertEqual(row["action_type"], "timeout")
        self.assertEqual(row["round_number"], 2)
        self.assertEqual(row["clue"], "letters")
        self.assertEqual(row["board_template_id"], "B03")
        # The actor who timed out is the human in their role this round.
        self.assertEqual(row["clue_giver"], "human")
        self.assertEqual(json.loads(row["remaining_targets_before_turn"]), ["Alpha", "Beta"])

    def test_timeout_alignment_is_not_applicable(self):
        game_logic.record_timeout("letters", 1, ["Alpha"], ["Alpha"])
        row = self.turn_row()
        self.assertEqual(row["alignment_applicability"], "timeout_no_behavioral_selection")
        self.assertEqual(row["jaccard_alignment"], "")


class FullSkipAlignmentTests(_GameAndStorageState):
    role = "ai_clue"

    def test_full_skip_alignment_is_not_an_observed_selection(self):
        game_logic.record_skip(
            "letters", 1, ["Alpha"], skipped_by="human", skip_interpreted_cards=["Beta"]
        )
        row = self.turn_row()
        self.assertEqual(row["action_type"], "full_skip")
        self.assertNotEqual(row["alignment_applicability"], "observed_completed_selection")
        self.assertEqual(row["jaccard_alignment"], "")

    def test_completed_guess_keeps_its_alignment_value(self):
        game_logic.record_interaction("letters", 1, ["Alpha"], ["Alpha"])
        row = self.turn_row()
        self.assertEqual(row["alignment_applicability"], "observed_completed_selection")
        self.assertNotEqual(row["jaccard_alignment"], "")


class RunTypeAndEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.original_st = storage.st
        self.state = State(
            participant_id="p1",
            session_id="s1",
            consent_given=True,
            consent_timestamp="2026-01-01T00:00:05",
            session_start_time="2026-01-01T00:00:00",
            prolific_pid="",
            attention_check_profile_answer="A few times a month",
            attention_check_post_game_answer=2,
        )
        storage.st = SimpleNamespace(session_state=self.state)

    def tearDown(self):
        storage.st = self.original_st

    def row(self, completed=True):
        with patch.dict(os.environ, {"RUN_TYPE": ""}):
            return storage._session_row(completed=completed)

    def test_consent_timestamp_is_persisted(self):
        self.assertEqual(self.row()["consent_timestamp"], "2026-01-01T00:00:05")

    def test_session_without_prolific_id_is_a_test_and_not_eligible(self):
        row = self.row()
        self.assertEqual(row["run_type"], "test")
        self.assertFalse(row["analysis_eligible"])

    def test_completed_prolific_participant_is_provisionally_eligible(self):
        self.state.prolific_pid = "5f1a2b3c4d5e6f7a8b9c0d1e"
        row = self.row()
        self.assertEqual(row["run_type"], "participant")
        self.assertTrue(row["analysis_eligible"])
        self.assertFalse(self.row(completed=False)["analysis_eligible"])

    def test_failing_both_attention_checks_is_not_eligible(self):
        self.state.prolific_pid = "5f1a2b3c4d5e6f7a8b9c0d1e"
        self.state.attention_check_profile_answer = "Daily"
        self.state.attention_check_post_game_answer = 5
        self.assertFalse(self.row()["analysis_eligible"])

    def test_pilot_deployment_is_labelled_pilot_and_not_eligible(self):
        self.state.prolific_pid = "5f1a2b3c4d5e6f7a8b9c0d1e"
        with patch.dict(os.environ, {"RUN_TYPE": "pilot"}):
            row = storage._session_row(completed=True)
        self.assertEqual(row["run_type"], "pilot")
        self.assertFalse(row["analysis_eligible"])


SENTINELS = {
    "intention": "SENTINEL_INTENDED",
    "expected": "SENTINEL_EXPECTED",
    "rationale": "SENTINEL_RATIONALE",
    "explanation": "SENTINEL_EXPLANATION",
    "interpretation": "SENTINEL_INTERPRETATION",
    "ai_reflection": "SENTINEL_AI_REFLECTION",
    "human_feedback": "SENTINEL_HUMAN_FEEDBACK",
}


def _history_with_sentinels():
    return [
        {
            "turn": 1,
            "clue_giver": "human",
            "guesser": "ai",
            "hint": "letters",
            "hint_number": 1,
            "intended_targets": [SENTINELS["intention"]],
            "expected_guesses": [SENTINELS["expected"]],
            "guesses": ["Alpha"],
            "correct_guesses": ["Alpha"],
            "incorrect_guesses": [],
            "guess_rationale": SENTINELS["rationale"],
            "human_explanation_raw": SENTINELS["explanation"],
            "human_explanation_sanitized": SENTINELS["explanation"],
            "skip_interpreted_cards": [SENTINELS["interpretation"]],
            "human_perceived_understanding_rating": 4,
            "outcome": "correct",
            "correct": True,
        }
    ]


def _round_summaries_with_sentinels():
    return [
        {
            "round": 1,
            "success": False,
            "bomb_hit": False,
            "medal": "none",
            "interactions": _history_with_sentinels(),
            "ai_reflection": SENTINELS["ai_reflection"],
            "human_feedback": SENTINELS["human_feedback"],
        }
    ]


class BaselinePromptIsolationTests(unittest.TestCase):
    def setUp(self):
        self.original_st = ai_service.st
        ai_service.st = SimpleNamespace(session_state=State(word_type_per_card={}))

    def tearDown(self):
        ai_service.st = self.original_st

    def _hint_prompt(self, condition):
        return ai_service.build_hint_user_prompt(
            ["Alpha", "Beta"],
            ["Bomb"],
            ["Neutral"],
            "mixed",
            _history_with_sentinels(),
            round_summaries=_round_summaries_with_sentinels(),
            condition=condition,
        )

    def _guess_prompt(self, condition):
        return ai_service.build_guess_user_prompt(
            ["Alpha", "Beta", "Neutral", "Bomb"],
            "letters",
            1,
            _history_with_sentinels(),
            [],
            _round_summaries_with_sentinels(),
            2,
            True,
            condition=condition,
        )

    def test_baseline_prompts_exclude_adaptive_only_fields(self):
        for prompt in (self._hint_prompt("baseline"), self._guess_prompt("baseline")):
            for sentinel in SENTINELS.values():
                self.assertNotIn(sentinel, prompt)

    def test_adaptive_prompts_do_include_them(self):
        # Guards the test above: the sentinels really are reachable data.
        prompt = self._hint_prompt("adaptive")
        self.assertIn(SENTINELS["rationale"], prompt)
        self.assertIn(SENTINELS["human_feedback"], prompt)


class AiExplanationSafetyTests(unittest.TestCase):
    BOARD = ["Alpha", "Beta", "Neutral", "Bomb"]

    def _explain(self, *responses):
        with patch("core.ai_service.call_openai_chat") as mock_call:
            mock_call.side_effect = [
                (json.dumps({"relationship_type": "Other", "explanation": text}), 0.01)
                for text in responses
            ]
            return ai_service.generate_ai_turn_explanation(
                "letters", 1, ["Alpha"], ["Alpha"], self.BOARD
            )

    def _assert_no_board_word(self, text):
        lowered = text.lower()
        for word in self.BOARD:
            self.assertNotIn(word.lower(), lowered)

    def test_explanation_naming_a_board_word_is_regenerated(self):
        result = self._explain("It points straight at Alpha.", "Both relate to written symbols.")
        self.assertTrue(result["ai_explanation_is_valid"])
        self._assert_no_board_word(result["ai_explanation_sanitized"])

    def test_explanation_that_keeps_naming_board_words_falls_back_safely(self):
        result = self._explain("Alpha and Beta.", "Still Alpha.")
        self.assertFalse(result["ai_explanation_is_valid"])
        self._assert_no_board_word(result["ai_explanation_sanitized"])
        self.assertNotIn("bomb", result["ai_explanation_sanitized"].lower())


if __name__ == "__main__":
    unittest.main()
