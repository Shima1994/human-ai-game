"""The star bonus (GBP 1 per star, GBP 5 for all four) is announced in both
guides and told to the AI in both conditions alike, so it cannot explain a
difference between baseline and adaptive."""

import unittest
from pathlib import Path

from core import ai_service
from core.constants import ALL_STARS_BONUS_GBP, BONUS_PER_STAR_GBP


class TeamBonusTests(unittest.TestCase):
    def test_amounts(self):
        self.assertEqual(BONUS_PER_STAR_GBP, 1)
        self.assertEqual(ALL_STARS_BONUS_GBP, 5)

    def test_bonus_per_number_of_stars(self):
        from core.game_logic import star_bonus_gbp

        self.assertEqual([star_bonus_gbp(n) for n in range(5)], [0, 1, 2, 3, 5])

    def test_every_clue_and_guess_prompt_states_the_bonus(self):
        for name in (
            "HINT_SYSTEM_PROMPT",
            "BASELINE_HINT_SYSTEM_PROMPT",
            "GUESS_SYSTEM_PROMPT",
            "BASELINE_GUESS_SYSTEM_PROMPT",
        ):
            prompt = getattr(ai_service, name)
            self.assertIn("WHAT IS AT STAKE", prompt, name)
            self.assertIn("£1 per such round, and £5 instead of £4", prompt, name)

    def test_every_clue_and_guess_prompt_states_the_game_rules(self):
        for name in (
            "HINT_SYSTEM_PROMPT",
            "BASELINE_HINT_SYSTEM_PROMPT",
            "GUESS_SYSTEM_PROMPT",
            "BASELINE_GUESS_SYSTEM_PROMPT",
        ):
            prompt = getattr(ai_service, name)
            self.assertIn(ai_service.GAME_RULES, prompt, name)
            self.assertIn("at most 3 completed turns", prompt, name)
            self.assertNotIn("Persian", prompt, name)
            for word in ("adaptive", "baseline", "condition"):
                self.assertNotIn(word, prompt.lower(), name)

    def test_both_guides_state_the_bonus_in_bold(self):
        written = Path("ui/game_guide.py").read_text(encoding="utf-8-sig")
        self.assertIn("**Bonus: if you complete the study, you receive £1 for every star you earn.", written)
        visual = Path("ui/guide_walkthrough.py").read_text(encoding="utf-8-sig")
        self.assertIn('"**Bonus: if you complete the study, you receive £{BONUS_PER_STAR_GBP} for every star. "', visual)


if __name__ == "__main__":
    unittest.main()
