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

    @patch("core.ai_service.call_openai_chat")
    def test_markdown_is_removed_because_the_page_shows_plain_text(self, mock_call):
        # Real gpt-5.4 output style: bold markers, bullets and line breaks.
        mock_call.return_value = (
            "I was aiming directly.\n\n**Engagement (2)** was for **Promise + Ring**.\n"
            "- **Ring**: engagement ring.\n- *Promise*: a vow to marry.\n### Next time\n1. Be clearer.",
            0.05,
        )
        result = self._call()
        self.assertEqual(
            result,
            "I was aiming directly.\nEngagement (2) was for Promise + Ring.\n"
            "Ring: engagement ring.\nPromise: a vow to marry.\nNext time\nBe clearer.",
        )
        self.assertNotIn("*", result)
        self.assertNotIn("#", result)

    @patch("core.ai_service.call_openai_chat")
    def test_word_cap_keeps_one_point_per_line(self, mock_call):
        mock_call.return_value = ("\n".join(["one two three four five"] * 60), 0.05)
        result = self._call()
        lines = result.splitlines()
        self.assertEqual(len(result.split()), 260)
        self.assertEqual(len(lines), 52)
        self.assertTrue(all(line == "one two three four five" for line in lines))


if __name__ == "__main__":
    unittest.main()
