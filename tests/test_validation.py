import unittest

from core.validation import validate_guess_rationale


class GuessRationaleValidationTests(unittest.TestCase):
    BOARD = ["Cat", "Dog", "Apple", "Table", "Train", "River"]

    def test_accepts_board_independent_english_reason(self):
        self.assertEqual(
            validate_guess_rationale("Both are familiar household pets", self.BOARD),
            (True, ""),
        )

    def test_rejects_exact_and_inflected_card_names(self):
        self.assertEqual(
            validate_guess_rationale("Dog and Cat fit together", self.BOARD),
            (False, "board_word"),
        )
        self.assertEqual(
            validate_guess_rationale("Both cats are household pets", self.BOARD),
            (False, "board_word"),
        )

    def test_rejects_word_count_and_language_violations(self):
        self.assertEqual(
            validate_guess_rationale("household pets", self.BOARD),
            (False, "too_short"),
        )
        self.assertEqual(
            validate_guess_rationale(" ".join(["general"] * 31), self.BOARD),
            (False, "too_long"),
        )
        self.assertEqual(
            validate_guess_rationale("این یک توضیح است", self.BOARD),
            (False, "non_english"),
        )


if __name__ == "__main__":
    unittest.main()
