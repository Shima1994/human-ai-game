import unittest

from ui.screens import _guess_outcome_summary


class GuessOutcomeMessageTests(unittest.TestCase):
    """Red (error) is reserved for a bomb hit; other wrong guesses are amber."""

    def test_bomb_hit_is_red(self):
        kind, message = _guess_outcome_summary(
            {"outcome": "bomb", "guesses": ["Fire"], "bomb_guesses": ["Fire"]}
        )
        self.assertEqual(kind, "error")
        self.assertIn("Bomb hit", message)

    def test_single_neutral_guess_is_a_warning_not_red(self):
        kind, message = _guess_outcome_summary(
            {"outcome": "neutral", "guesses": ["Loyalty"], "neutral_guesses": ["Loyalty"]}
        )
        self.assertEqual(kind, "warning")
        self.assertEqual(message, "Wrong: Loyalty was a neutral card, not a target.")

    def test_several_neutral_guesses_use_plural_wording(self):
        kind, message = _guess_outcome_summary(
            {"outcome": "neutral", "guesses": ["Risk", "Helmet"], "neutral_guesses": ["Risk", "Helmet"]}
        )
        self.assertEqual(kind, "warning")
        self.assertEqual(message, "Wrong: Risk, Helmet were neutral cards, not targets.")

    def test_partly_right_is_a_warning(self):
        kind, _message = _guess_outcome_summary(
            {
                "outcome": "partial_correct",
                "guesses": ["Apple", "Lamp"],
                "correct_guesses": ["Apple"],
                "neutral_guesses": ["Lamp"],
            }
        )
        self.assertEqual(kind, "warning")


if __name__ == "__main__":
    unittest.main()
