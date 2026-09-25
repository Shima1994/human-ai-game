import unittest
from unittest.mock import patch

from core.ai_service import generate_ai_round_reflection


class AiRoundReflectionFallbackTests(unittest.TestCase):
    """A successful API call that returns blank/whitespace content raises no
    exception, so without an explicit check the blank text would be stored
    and shown to the participant as a real (if terse) reflection --
    indistinguishable from an actual API failure.
    """

    def _call(self):
        return generate_ai_round_reflection(
            ["Cat", "Dog"],
            ["River"],
            ["Table"],
            "mixed",
            "human_clue",
            history=[],
            round_success=True,
            round_bomb_hit=False,
            round_medal="gold",
        )

    @patch("core.ai_service.call_openai_chat")
    def test_blank_response_falls_back_to_apology_text(self, mock_call):
        mock_call.return_value = ("", 0.05)
        result = self._call()
        self.assertTrue(result.strip())
        self.assertIn("could not generate a reflection", result)

    @patch("core.ai_service.call_openai_chat")
    def test_whitespace_only_response_falls_back_to_apology_text(self, mock_call):
        mock_call.return_value = ("   \n  ", 0.05)
        result = self._call()
        self.assertIn("could not generate a reflection", result)

    @patch("core.ai_service.call_openai_chat")
    def test_api_exception_falls_back_to_apology_text(self, mock_call):
        mock_call.side_effect = RuntimeError("boom")
        result = self._call()
        self.assertIn("could not generate a reflection", result)

    @patch("core.ai_service.call_openai_chat")
    def test_real_response_is_returned_unchanged(self, mock_call):
        mock_call.return_value = ("A genuine reflection about the round.", 0.05)
        result = self._call()
        self.assertEqual(result, "A genuine reflection about the round.")


if __name__ == "__main__":
    unittest.main()
