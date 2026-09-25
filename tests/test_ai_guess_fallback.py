import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from core.ai_service import ai_guess


class AiGuessForcedFallbackTests(unittest.TestCase):
    """When the model's response can't be parsed into a guess and there is
    no skip or reroll left, the game rules only allow guess / skip /
    timeout -- ai_guess must never return an empty guess list, since that
    would record as an incoherent "wrong guess with nothing guessed" turn.
    """

    def setUp(self):
        self.board = ["Cat", "Dog", "Table", "Train", "River", "Apple"]

    @patch("core.ai_service.call_openai_chat")
    def test_unparseable_response_with_no_skip_or_reroll_forces_a_real_guess(
        self, mock_call
    ):
        mock_call.return_value = ("not valid json at all", 0.05)
        result = ai_guess(
            self.board,
            "pet",
            2,
            0,
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
    def test_api_failure_with_no_skip_or_reroll_forces_a_real_guess(self, mock_call):
        mock_call.side_effect = RuntimeError("boom")
        result = ai_guess(
            self.board,
            "pet",
            2,
            0,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=0,
            can_skip=False,
        )
        self.assertEqual(result["action"], "guess")
        self.assertTrue(result["guesses"])

    @patch("core.ai_service.call_openai_chat")
    def test_unparseable_response_still_skips_when_a_skip_is_available(
        self, mock_call
    ):
        mock_call.return_value = ("not valid json at all", 0.05)
        result = ai_guess(
            self.board,
            "pet",
            2,
            0,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=1,
            can_skip=True,
        )
        self.assertEqual(result["action"], "skip")
        self.assertEqual(result["guesses"], [])


class AiGuessRerollWiringTests(unittest.TestCase):
    """ai_guess's own reroll literal-token handling. The caller
    (ui/screens.py) must pass the participant's real remaining
    st.session_state.ai_rerolls count as remaining_rerolls -- it used to
    hardcode 0, which silently discarded every REROLL_HINT response the
    model ever sent (the system prompt documents REROLL_HINT as the
    correct response to a genuinely unusable clue). These tests pin down
    ai_guess's side of that contract so a future regression back to a
    hardcoded 0 at the call site would be caught by end-to-end coverage of
    "reroll ever happens", not just by reading the call site.
    """

    def setUp(self):
        self.board = ["Cat", "Dog", "Table", "Train", "River", "Apple"]

    @patch("core.ai_service.call_openai_chat")
    def test_reroll_hint_token_is_honored_when_rerolls_remain(self, mock_call):
        mock_call.return_value = ("REROLL_HINT", 0.05)
        result = ai_guess(
            self.board,
            "pet",
            2,
            2,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=0,
            can_skip=False,
        )
        self.assertEqual(result["action"], "reroll")
        self.assertEqual(result["guesses"], [])

    @patch("core.ai_service.call_openai_chat")
    def test_reroll_hint_token_is_ignored_when_no_rerolls_remain(self, mock_call):
        mock_call.return_value = ("REROLL_HINT", 0.05)
        result = ai_guess(
            self.board,
            "pet",
            2,
            0,
            history=[],
            previous_guesses=[],
            round_summaries=[],
            remaining_skips=0,
            can_skip=False,
        )
        self.assertNotEqual(result["action"], "reroll")
        self.assertEqual(result["action"], "guess")
        self.assertTrue(result["guesses"])


class AiGuessCallSiteWiringTests(unittest.TestCase):
    """screen_human_clue used to call ai_guess(..., 0, ...) -- a hardcoded
    literal that silently disabled the reroll feature regardless of how
    many st.session_state.ai_rerolls actually remained. Guard against that
    exact regression at the source level, since a plain integer there is
    always wrong (max_guesses/remaining_rerolls swap or a copy-paste 0
    would both pass every ai_guess-level test above and still be broken).
    """

    def test_remaining_rerolls_argument_is_not_a_hardcoded_literal(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "screen_human_clue"
        )
        call = next(
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ai_guess"
        )
        remaining_rerolls_arg = call.args[3]
        self.assertFalse(
            isinstance(remaining_rerolls_arg, ast.Constant),
            "ai_guess's remaining_rerolls argument must read the participant's "
            "actual ai_rerolls count, not a hardcoded literal.",
        )


if __name__ == "__main__":
    unittest.main()
