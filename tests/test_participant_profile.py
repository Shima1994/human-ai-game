import ast
import unittest
from pathlib import Path

from ui.screens import (
    AGE_GROUP_OPTIONS,
    AI_EXPERIENCE_OPTIONS,
    CODENAMES_EXPERIENCE_OPTIONS,
    ENGLISH_PROFICIENCY_OPTIONS,
    GENDER_OPTIONS,
)


class ParticipantProfileTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(self.source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "screen_name"
        )
        self.screen_source = ast.get_source_segment(self.source, function)

    def test_existing_answer_options_are_unchanged(self):
        self.assertEqual(
            AGE_GROUP_OPTIONS,
            ["18-24", "25-34", "35-44", "45-54", "55+", "Prefer not to say"],
        )
        self.assertEqual(
            GENDER_OPTIONS,
            [
                "Female",
                "Male",
                "Non-binary",
                "Prefer not to say",
            ],
        )
        self.assertEqual(
            ENGLISH_PROFICIENCY_OPTIONS,
            ["Beginner", "Intermediate", "Advanced", "Native / Near-native"],
        )
        self.assertEqual(
            AI_EXPERIENCE_OPTIONS,
            [
                "Never",
                "Less than once a month",
                "A few times a month",
                "A few times a week",
                "Daily",
            ],
        )
        self.assertEqual(
            CODENAMES_EXPERIENCE_OPTIONS,
            ["Never", "Once or twice", "Occasionally", "Frequently"],
        )

    def test_question_wording_and_optional_labels_match_validation(self):
        questions = (
            "Nickname or pseudonym (optional — do not enter your real name)",
            "What is your age group?",
            "What is your gender?",
            "How would you describe your English proficiency?",
            "How often do you use AI tools such as ChatGPT, Gemini, or Claude?",
            "Have you played Codenames before?",
        )
        for question in questions:
            self.assertIn(question, self.screen_source)
        self.assertNotIn("All questions are optional", self.screen_source)
        self.assertNotIn("What is your gender? Optional", self.screen_source)

    def test_required_validation_is_preserved_without_self_describe(self):
        required_checks = (
            "if not age_group:",
            "if gender_choice is None:",
            "if english_proficiency is None:",
            "if ai_experience is None:",
            "if codenames_experience is None:",
        )
        for check in required_checks:
            self.assertIn(check, self.screen_source)
        self.assertNotIn("if not nickname", self.screen_source)
        self.assertNotIn("Prefer to self-describe", self.screen_source)
        self.assertNotIn("gender_self_describe", self.screen_source)

    def test_question_labels_are_not_styled_as_clickable_options(self):
        styles = Path("static/app.css").read_text(encoding="utf-8-sig")
        self.assertNotIn(
            ".st-key-participant_profile_panel .stRadio label {", styles
        )
        self.assertIn(
            '.st-key-participant_profile_panel .stRadio [role="radiogroup"] label {',
            styles,
        )

    def test_desktop_information_cards_use_only_existing_profile_text(self):
        self.assertIn('class="profile-aside"', self.screen_source)
        self.assertIn(
            'form_col, aside_col = st.columns([3.35, 1.15], gap="large")',
            self.screen_source,
        )
        self.assertIn("with form_col:", self.screen_source)
        self.assertIn("with aside_col:", self.screen_source)
        self.assertIn("Why we ask this", self.screen_source)
        self.assertIn("These answers help us analyze the game results.", self.screen_source)
        self.assertIn("Your privacy", self.screen_source)
        self.assertIn("Do not enter your real name.", self.screen_source)
        self.assertNotIn("All questions are optional", self.screen_source)


if __name__ == "__main__":
    unittest.main()
