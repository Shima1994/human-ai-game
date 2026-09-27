import unittest
from unittest.mock import patch

from core.ai_service import ai_guess


class AiGuessForcedFallbackTests(unittest.TestCase):
    """When the model's response can't be parsed into a guess and there is
    no skip left, the game rules only allow guess / skip / timeout --
    ai_guess must never return an empty guess list, since that would
    record as an incoherent "wrong guess with nothing guessed" turn.
    """

    def setUp(self):
        self.board = ["Cat", "Dog", "Table", "Train", "River", "Apple"]

    @patch("core.ai_service.call_openai_chat")
    def test_unparseable_response_with_no_skip_forces_a_real_guess(self, mock_call):
        mock_call.return_value = ("not valid json at all", 0.05)
        result = ai_guess(
            self.board,
            "pet",
            2,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=0,
            can_skip=False,
        )
        self.assertEqual(result["action"], "guess")
        self.assertTrue(result["guesses"])
        self.assertTrue(all(word in self.board for word in result["guesses"]))
        self.assertLessEqual(len(result["guesses"]), 2)

    @patch("core.ai_service.call_openai_chat")
    def test_api_failure_with_no_skip_forces_a_real_guess(self, mock_call):
        mock_call.side_effect = RuntimeError("boom")
        result = ai_guess(
            self.board,
            "pet",
            2,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=0,
            can_skip=False,
        )
        self.assertEqual(result["action"], "guess")
        self.assertTrue(result["guesses"])

    @patch("core.ai_service.call_openai_chat")
    def test_undersized_guess_with_no_skip_is_padded_to_the_full_clue_count(
        self, mock_call
    ):
        """The one legitimate way to submit fewer than N guesses is
        partial_skip, which costs a skip -- if no skip is available, a
        genuinely undersized "guess" response must never be recorded as a
        complete, satisfied answer to the clue. It must be padded up to the
        full required count instead (from the model's own interpreted_cards,
        or whatever's left on the board), never silently accepted short."""
        mock_call.return_value = (
            '{"guesses": ["Cat", "Dog"], "reasoning": "Two safe picks.", '
            '"interpreted_cards": ["Table", "Train"]}',
            0.05,
        )
        result = ai_guess(
            self.board,
            "animal",
            5,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=0,
            can_skip=False,
        )
        self.assertEqual(result["action"], "guess")
        self.assertEqual(len(result["guesses"]), 5)
        self.assertIn("Cat", result["guesses"])
        self.assertIn("Dog", result["guesses"])
        self.assertTrue(all(word in self.board for word in result["guesses"]))
        self.assertEqual(len(set(result["guesses"])), 5)

    @patch("core.ai_service.call_openai_chat")
    def test_unparseable_response_still_skips_when_a_skip_is_available(
        self, mock_call
    ):
        """The one skip path with no interpreted_cards to report (nothing
        parseable at all to base them on) must still carry a rationale
        explaining why, rather than skipping silently with no reason."""
        mock_call.return_value = ("not valid json at all", 0.05)
        result = ai_guess(
            self.board,
            "pet",
            2,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=1,
            can_skip=True,
        )
        self.assertEqual(result["action"], "skip")
        self.assertEqual(result["guesses"], [])
        self.assertTrue(result["guess_rationale"])


if __name__ == "__main__":
    unittest.main()
