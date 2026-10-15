"""The adaptive end-of-round reflection gets an explicit fact list per turn
and a role-aware skip rule; the clue and guess prompts are unchanged."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import ai_service

TURN = {
    "clue_giver": "ai", "guesser": "human", "hint": "sticky", "hint_number": 2,
    "intended_targets": ["Honey", "Spider"], "guesses": ["Spider", "Honesty"],
    "correct_guesses": ["Spider", "Honesty"], "neutral_guesses": [], "bomb_guesses": [],
    "outcome": "correct",
}


class ReflectionFactsTests(unittest.TestCase):
    def test_fact_list_separates_intended_from_other_correct_cards(self):
        text = ai_service.format_reflection_turn_facts([TURN], "ai_clue")
        self.assertIn("In this round you (the AI) gave the clues and the human guessed.", text)
        self.assertIn("correct and intended: Spider", text)
        self.assertIn("correct but not intended (still a valid target): Honesty", text)
        self.assertIn("picked by the guesser (in order): Spider, Honesty", text)
        self.assertIn("skipped: no", text)

    def test_partial_skip_and_timeout_are_spelled_out(self):
        skipped = dict(TURN, guesses=["Spider"], correct_guesses=["Spider"], partial_skip=True, skipped=True)
        self.assertIn("skipped: yes, the human skipped after 1 card(s)", ai_service.format_reflection_turn_facts([skipped], "ai_clue"))
        clue_timeout = {"clue_giver": "human", "guesser": "ai", "hint": "", "timed_out": True}
        self.assertIn("time ran out before a clue was given", ai_service.format_reflection_turn_facts([clue_timeout], "human_clue"))

    def test_skip_rule_is_role_aware(self):
        prompt = ai_service.REFLECTION_SYSTEM_PROMPT
        self.assertIn("only the guesser can skip", prompt)
        self.assertIn("never talk about skipping yourself", prompt)
        self.assertIn("If nobody skipped, do not mention skips at all.", prompt)
        self.assertNotIn("Mention any skips and what made the clue feel risky.", prompt)

    def test_only_the_adaptive_reflection_uses_the_fact_list(self):
        calls = []
        with patch.object(ai_service, "call_openai_chat", side_effect=lambda s, u, **k: (calls.append(u) or ("ok", 0))), \
             patch.object(ai_service, "st", SimpleNamespace(session_state={})):
            for condition in ("adaptive", "baseline"):
                ai_service.generate_ai_round_reflection(
                    ["Honey", "Spider"], ["Mouse"], ["Honesty"], "mixed", "ai_clue", [TURN],
                    False, False, condition=condition,
                )
        self.assertIn("correct but not intended", calls[0])
        self.assertNotIn("correct but not intended", calls[1])
        self.assertNotIn("intended", calls[1].split("Interaction history:")[1])

    def test_clue_and_guess_prompts_keep_the_old_history_format(self):
        source = Path("core/ai_service.py").read_text(encoding="utf-8")
        # One call site (the reflection), besides the definition itself.
        self.assertEqual(source.count("format_reflection_turn_facts(history, role) if condition"), 1)
        hint = source[source.index("def build_hint_user_prompt"):source.index("def parse_hint_json")]
        guess = source[source.index("def build_guess_user_prompt"):source.index("def build_guess_repair_prompt")]
        for block in (hint, guess):
            self.assertIn("format_interaction_history(history)", block)
            self.assertNotIn("format_reflection_turn_facts", block)


if __name__ == "__main__":
    unittest.main()
