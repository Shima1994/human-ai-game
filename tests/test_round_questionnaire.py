"""The questionnaire is asked after every round: the participant's answers
and the AI's mirrored self-report are stored on that round's row."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core import ai_service, storage
from core.constants import N_ROUNDS
from tests.test_data_integrity import _GameAndStorageState
from ui import screens


HUMAN_COLUMNS = {
    "i_understood_ai_clues": "round_questionnaire_i_understood_ai_clues",
    "predict_ai_interpretation": "round_questionnaire_predict_ai_interpretation",
    "adapted_to_ai_behavior": "round_questionnaire_adapted_to_ai_behavior",
    "reflection_helped": "round_questionnaire_reflection_helped",
    "shared_understanding": "round_questionnaire_shared_understanding",
}
AI_COLUMNS = {
    "i_understood_human_clues": "ai_round_questionnaire_i_understood_human_clues",
    "predict_human_interpretation": "ai_round_questionnaire_predict_human_interpretation",
    "adapted_to_human_behavior": "ai_round_questionnaire_adapted_to_human_behavior",
    "reflection_helped": "ai_round_questionnaire_reflection_helped",
    "shared_understanding": "ai_round_questionnaire_shared_understanding",
}


class RoundQuestionnaireItemTests(unittest.TestCase):
    def test_items_are_the_former_end_of_game_items_framed_as_this_round(self):
        self.assertEqual(
            [text for _, text in screens.ROUND_QUESTIONS],
            [
                "In this round, I felt that I understood what the AI meant when it gave clues.",
                "In this round, I could predict how the AI would interpret my clues.",
                "In this round, I adapted my communication based on the AI's behaviour.",
                "In this round, the reflection steps helped me recover from misunderstandings with the AI.",
                "In this round, I felt that the AI and I had developed a shared understanding.",
            ],
        )

    def test_human_and_ai_items_mirror_each_other(self):
        self.assertEqual([key for key, _ in screens.ROUND_QUESTIONS], list(HUMAN_COLUMNS))
        self.assertEqual(list(ai_service.AI_ROUND_QUESTIONNAIRE_KEYS), list(AI_COLUMNS))

    def _items(self, role, round_number):
        with patch.object(screens, "st") as fake_st:
            fake_st.session_state = type("S", (dict,), {"__getattr__": dict.__getitem__})(
                role=role, round=round_number
            )
            return [key for key, _ in screens._round_questionnaire_items()]

    def test_understanding_ai_clues_only_when_the_ai_gave_the_clues(self):
        ai_clue = self._items("ai_clue", 1)
        human_clue = self._items("human_clue", 1)
        self.assertIn("i_understood_ai_clues", ai_clue)
        self.assertNotIn("predict_ai_interpretation", ai_clue)
        self.assertIn("predict_ai_interpretation", human_clue)
        self.assertNotIn("i_understood_ai_clues", human_clue)
        for ids in (ai_clue, human_clue):
            self.assertEqual(len(ids), 4)
            self.assertEqual(
                ids[-3:], ["adapted_to_ai_behavior", "reflection_helped", "shared_understanding"]
            )

    def test_attention_check_only_after_round_2(self):
        for role in ("ai_clue", "human_clue"):
            for round_number in range(1, N_ROUNDS + 1):
                ids = self._items(role, round_number)
                if round_number != 2:
                    self.assertNotIn(screens.ATTENTION_CHECK_MID_GAME_ID, ids)
                    self.assertEqual(len(ids), 4)
                else:
                    self.assertEqual(ids[2], screens.ATTENTION_CHECK_MID_GAME_ID)
                    self.assertEqual(len(ids), 5)

    def test_no_end_of_game_questionnaire_is_left(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        self.assertNotIn("POST_GAME_QUESTIONS", source)
        self.assertNotIn("post_game_questionnaire", source)
        self.assertNotIn("generate_ai_post_game_reflection", source)


class RoundQuestionnaireStorageTests(_GameAndStorageState):
    def test_answers_are_stored_on_the_round_row(self):
        self.state.round_questionnaire = {
            "i_understood_ai_clues": 4,
            "predict_ai_interpretation": 3,
            "adapted_to_ai_behavior": 5,
            "reflection_helped": 2,
            "shared_understanding": 4,
        }
        self.state.ai_round_questionnaire = {
            "i_understood_human_clues": 2,
            "predict_human_interpretation": 3,
            "adapted_to_human_behavior": 4,
            "reflection_helped": 1,
            "shared_understanding": 2,
            "reasoning": "The second guess missed.",
            "raw_response": "{}",
            "blocked_reason": "",
        }
        row = storage._round_analysis_row("p1", "2026-01-01T00:05:00", 0)
        for key, column in HUMAN_COLUMNS.items():
            self.assertEqual(row[column], self.state.round_questionnaire[key])
        for key, column in AI_COLUMNS.items():
            self.assertEqual(row[column], self.state.ai_round_questionnaire[key])
        self.assertEqual(row["ai_round_questionnaire_reasoning"], "The second guess missed.")
        self.assertEqual(json.loads(row["round_questionnaire_json"]), self.state.round_questionnaire)
        self.assertEqual(
            json.loads(row["ai_round_questionnaire_json"]), self.state.ai_round_questionnaire
        )
        self.assertEqual(set(row), set(storage.ROUNDS_LOG_FIELDS))

    def test_unanswered_round_stays_blank(self):
        self.state.round_questionnaire = {}
        self.state.ai_round_questionnaire = {}
        row = storage._round_analysis_row("p1", "2026-01-01T00:05:00", 0)
        for column in list(HUMAN_COLUMNS.values()) + list(AI_COLUMNS.values()):
            self.assertEqual(row[column], "")

    def test_session_row_no_longer_has_end_of_game_questionnaire_columns(self):
        for field in storage.SESSIONS_LOG_FIELDS:
            self.assertFalse(field.startswith("post_game_"), field)
            self.assertFalse(field.startswith("ai_post_game_"), field)
        self.assertIn("attention_check_mid_game_answer", storage.SESSIONS_LOG_FIELDS)


class AIRoundQuestionnaireTests(unittest.TestCase):
    def _call(self, raw, role="human_clue", condition="adaptive"):
        with patch("core.ai_service.call_openai_chat", return_value=(raw, None)) as mock_call:
            result = ai_service.generate_ai_round_questionnaire(
                role, [], False, False, condition=condition
            )
        return result, mock_call

    def test_ai_items_mirror_the_human_roles(self):
        # Human clue round: the AI rates understanding the human's clues.
        self.assertEqual(
            ai_service.ai_round_questionnaire_keys("human_clue"),
            ("i_understood_human_clues", "adapted_to_human_behavior", "reflection_helped", "shared_understanding"),
        )
        # AI clue round: the AI rates predicting the human's interpretation.
        self.assertEqual(
            ai_service.ai_round_questionnaire_keys("ai_clue"),
            ("predict_human_interpretation", "adapted_to_human_behavior", "reflection_helped", "shared_understanding"),
        )

    def test_valid_answer_is_parsed(self):
        for role in ("human_clue", "ai_clue"):
            keys = ai_service.ai_round_questionnaire_keys(role)
            answer = {key: 3 for key in keys}
            answer["reasoning"] = "Fine."
            result, mock_call = self._call(json.dumps(answer), role=role)
            for key in keys:
                self.assertEqual(result[key], 3)
            self.assertEqual(result["blocked_reason"], "")
            other = (set(ai_service.AI_ROUND_QUESTIONNAIRE_KEYS) - set(keys)).pop()
            self.assertNotIn(other, result)
            self.assertNotIn(other, mock_call.call_args.args[0])

    def test_out_of_range_rating_is_not_guessed(self):
        keys = ai_service.ai_round_questionnaire_keys("human_clue")
        answer = {key: 3 for key in keys}
        answer["shared_understanding"] = 7
        result, _ = self._call(json.dumps(answer))
        self.assertEqual(result["blocked_reason"], "invalid_rating")
        self.assertTrue(all(result[key] is None for key in keys))

    def test_prompt_is_about_this_round(self):
        _, mock_call = self._call("{}")
        system_prompt, user_prompt = mock_call.call_args.args[:2]
        self.assertIn("this round only", system_prompt)
        self.assertIn("Interaction history of this round:\n", user_prompt)


if __name__ == "__main__":
    unittest.main()
