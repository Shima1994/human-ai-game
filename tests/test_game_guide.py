import ast
import unittest
from pathlib import Path

from ui.game_guide import (
    CLUE_GIVER_INTRO,
    CLUE_GIVER_OUTRO,
    CLUE_GIVER_STEPS,
    GUIDE_OVERVIEW,
    GUIDE_REMINDERS,
    GUIDE_ROLE,
    GUIDE_SECTIONS,
)


class GameGuideTests(unittest.TestCase):
    def test_all_twelve_visual_sections_are_present(self):
        self.assertEqual(len(CLUE_GIVER_STEPS), 6)
        self.assertEqual(len(GUIDE_SECTIONS), 9)
        titles = [title for title, _ in GUIDE_SECTIONS]
        self.assertEqual(
            titles,
            [
                "When the AI Is the Clue-Giver",
                "Targets, Neutral Cards, and Bombs",
                "Try to Connect More Than One Target",
                "Interactions and Round Limit",
                "Skipping",
                "Communicative Repair",
                "Time Limit",
                "After an Interaction",
                "Medals and Performance",
            ],
        )

    def test_six_clue_giver_steps_are_in_required_order(self):
        self.assertEqual(
            [heading for heading, _ in CLUE_GIVER_STEPS],
            [
                "Give a one-word clue",
                "Choose the clue number",
                "Select your intended target cards",
                "Predict what the AI will choose",
                "Rate your expected shared understanding",
                "Briefly explain the general connection",
            ],
        )

    def test_required_instructional_content_is_complete(self):
        content = "\n".join(
            [GUIDE_OVERVIEW, GUIDE_ROLE, CLUE_GIVER_INTRO]
            + [heading + "\n" + body for heading, body in CLUE_GIVER_STEPS]
            + [CLUE_GIVER_OUTRO]
            + [heading + "\n" + body for heading, body in GUIDE_SECTIONS]
            + [GUIDE_REMINDERS]
        )
        required_phrases = (
            "You and the AI are on the same team.",
            "5 target cards",
            "9 neutral cards",
            "2 bomb cards",
            "Give a one-word clue",
            "Choose the clue number",
            "Select your intended target cards",
            "Predict what the AI will choose",
            "Rate your expected shared understanding",
            "Briefly explain the general connection",
            "When the AI Is the Clue-Giver",
            "Try to Connect More Than One Target",
            "maximum of 3 completed interactions",
            "Skip option up to 2 times",
            "Communicative Repair",
            "90 seconds",
            "A timeout does not use one of your skips.",
            "After an Interaction",
            "Gold Medal",
            "Silver Medal",
            "MOST IMPORTANT THINGS TO REMEMBER",
        )
        content += "\nMOST IMPORTANT THINGS TO REMEMBER"
        for phrase in required_phrases:
            self.assertIn(phrase, content)

    def test_screen_uses_expected_progressive_disclosure_and_navigation(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "screen_welcome"
        )
        screen_source = ast.get_source_segment(source, function)
        self.assertIn('"**1**　Overview", expanded=True', screen_source)
        self.assertIn('"**2**　Your Role", expanded=True', screen_source)
        self.assertIn('"**3**　When You Are the Clue-Giver"', screen_source)
        self.assertIn("zip(GUIDE_SECTIONS, section_icons)", screen_source)
        self.assertIn("expanded=False", screen_source)
        self.assertIn("st.session_state.started = True", screen_source)

    def test_each_guide_section_has_a_distinct_material_icon(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        icons = (
            ":material/groups:",
            ":material/switch_account:",
            ":material/lightbulb:",
            ":material/smart_toy:",
            ":material/target:",
            ":material/style:",
            ":material/sync:",
            ":material/skip_next:",
            ":material/forum:",
            ":material/schedule:",
            ":material/rate_review:",
            ":material/emoji_events:",
        )
        for icon in icons:
            self.assertIn(icon, source)

    def test_game_header_is_not_rendered_above_guide(self):
        source = Path("app.py").read_text(encoding="utf-8-sig")
        guide_branch = source[
            source.index("if not st.session_state.started"):
            source.index("if not st.session_state.participant_id")
        ]
        self.assertIn("screen_welcome()", guide_branch)
        self.assertNotIn("render_app_header()", guide_branch)


if __name__ == "__main__":
    unittest.main()
