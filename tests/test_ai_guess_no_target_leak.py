import copy
import re
import unittest
from unittest.mock import patch

from core.ai_service import ai_guess, hide_unfound_intended_cards


BOARD = [
    "Honesty", "Promise", "Mirror", "Ring", "Whistle",
    "Blame", "Police",
    "Boredom", "Loyalty", "Doubt", "Idea", "Mood", "Chocolate", "Chair", "Stadium", "Pen",
]

# Turn 1 of a human-clue round: the human meant Honesty, Promise and Ring;
# the AI found Ring and Promise and picked the neutral Loyalty. Honesty is an
# unfound target, so the AI guesser must not be told it was intended.
TURN_1 = {
    "turn": 1,
    "completed_turn_number": 1,
    "clue_giver": "human",
    "guesser": "ai",
    "hint": "betrothal",
    "hint_number": 3,
    "intended_targets": ["Honesty", "Promise", "Ring"],
    "expected_guesses": ["Ring", "Honesty", "Promise"],
    "guesses": ["Ring", "Promise", "Loyalty"],
    "correct": True,
    "correct_guesses": ["Ring", "Promise"],
    "neutral_guesses": ["Loyalty"],
    "bomb_guesses": [],
    "bomb_hit": False,
    "outcome": "partial_correct",
    "human_explanation_is_valid": True,
    "human_explanation_sanitized": "All relate to people getting engaged",
    "human_perceived_understanding_rating": 3,
}

INTENDED_OR_EXPECTED = re.compile(r"(?:intended|expected guesses|expected_guesses)=\[([^\]]*)\]")


def listed_cards(prompt):
    """Every card the prompt names as intended or expected by the human."""
    return {
        card.strip()
        for group in INTENDED_OR_EXPECTED.findall(prompt)
        for card in group.split(",")
        if card.strip() and card.strip() != "none"
    }


class HideUnfoundIntendedCardsTests(unittest.TestCase):
    def test_only_revealed_cards_stay_in_intended_and_expected(self):
        visible = hide_unfound_intended_cards([TURN_1], ["Ring", "Promise", "Loyalty"])
        self.assertEqual(visible[0]["intended_targets"], ["Promise", "Ring"])
        self.assertEqual(visible[0]["expected_guesses"], ["Ring", "Promise"])

    def test_a_card_found_later_becomes_visible(self):
        turn_2 = dict(TURN_1, turn=2, hint="truth", hint_number=1,
                      intended_targets=["Honesty"], expected_guesses=["Honesty"],
                      guesses=["Honesty"], correct_guesses=["Honesty"], neutral_guesses=[])
        visible = hide_unfound_intended_cards([TURN_1, turn_2], [])
        self.assertIn("Honesty", visible[0]["intended_targets"])
        self.assertEqual(visible[1]["intended_targets"], ["Honesty"])

    def test_stored_history_is_not_changed(self):
        history = [copy.deepcopy(TURN_1)]
        hide_unfound_intended_cards(history, ["Ring", "Promise", "Loyalty"])
        self.assertEqual(history[0], TURN_1)


class AiGuessPromptLeakTests(unittest.TestCase):
    def _guess(self, mock_call, condition):
        return ai_guess(
            BOARD,
            "transparency",
            2,
            history=[copy.deepcopy(TURN_1)],
            previous_guesses=["Ring", "Promise", "Loyalty"],
            round_summaries=[],
            remaining_skips=2,
            can_skip=True,
            condition=condition,
        )

    @patch("core.ai_service.call_openai_chat")
    def test_adaptive_prompt_never_names_an_unfound_intended_card(self, mock_call):
        mock_call.return_value = ('{"action": "guess", "reasoning": "clear", "guesses": ["Mirror", "Honesty"]}', 0.1)
        self._guess(mock_call, "adaptive")
        prompt = mock_call.call_args_list[0][0][1]
        # The adaptive prompt still shows what the human meant, for the cards
        # that are already revealed ...
        self.assertIn("Promise", listed_cards(prompt))
        self.assertIn("Ring", listed_cards(prompt))
        # ... but never the unfound target.
        self.assertNotIn("Honesty", listed_cards(prompt))

    @patch("core.ai_service.call_openai_chat")
    def test_repair_prompt_never_names_an_unfound_intended_card(self, mock_call):
        # First answer is unusable, so ai_guess sends the repair prompt.
        mock_call.side_effect = [
            ("not json", 0.1),
            ('{"reasoning": "clear", "guesses": ["Mirror", "Honesty"]}', 0.1),
        ]
        self._guess(mock_call, "adaptive")
        self.assertEqual(mock_call.call_count, 2)
        repair_prompt = mock_call.call_args_list[1][0][1]
        self.assertIn("Persistent teammate memory", repair_prompt)
        self.assertNotIn("Honesty", listed_cards(repair_prompt))

    @patch("core.ai_service.call_openai_chat")
    def test_baseline_prompt_has_no_intended_cards_at_all(self, mock_call):
        mock_call.return_value = ('{"action": "guess", "reasoning": "clear", "guesses": ["Mirror", "Honesty"]}', 0.1)
        self._guess(mock_call, "baseline")
        self.assertEqual(listed_cards(mock_call.call_args_list[0][0][1]), set())


if __name__ == "__main__":
    unittest.main()
