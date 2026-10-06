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

    def test_rejects_short_board_word_prefix_extension_bypass(self):
        # "Pen" is a real 3-letter board word (see core/words.py). Mirrors the
        # bounded prefix-extension check already applied to AI hints in
        # core/ai_service.py::is_hint_too_close_to_board.
        self.assertEqual(
            validate_guess_rationale(
                "I always use a pencil for drawing this", ["Pen", "Dog", "Apple", "Table"]
            ),
            (False, "board_word"),
        )

    def test_allows_unrelated_word_sharing_short_board_word_prefix(self):
        self.assertEqual(
            validate_guess_rationale(
                "Both are found near a pentagon shaped building", ["Pen", "Dog", "Apple", "Table"]
            ),
            (True, ""),
        )

    def test_allows_the_word_card_when_car_is_on_the_board(self):
        # Reported in testing: "card is hard" was rejected as naming "Car".
        board = ["Car", "Idea", "Dog", "Apple"]
        for text in (
            "i dont know my hint is good or not but card is hard",
            "These cards need careful thought",
            "An ideal match for daily life",
        ):
            self.assertEqual(validate_guess_rationale(text, board), (True, ""), text)

    def test_still_rejects_car_itself_and_its_plural(self):
        board = ["Car", "Dog", "Apple"]
        self.assertEqual(
            validate_guess_rationale("The car fits with the road", board),
            (False, "board_word"),
        )
        self.assertEqual(
            validate_guess_rationale("Both cars go on the road", board),
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
