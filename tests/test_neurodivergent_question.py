"""The supervisor's optional neurodivergence question on the profile page:
never required, and the characteristics box only opens on "Yes"."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core import storage
from ui import screens


def _profile_page():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["consent_given"] = True
    at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
    at.session_state["started"] = True
    at.run()
    return at


def _widget(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


class NeurodivergentQuestionTests(unittest.TestCase):
    def test_wording_follows_the_request(self):
        self.assertEqual(screens.NEURODIVERGENT_QUESTION, "Are you neurodivergent? (optional)")
        self.assertEqual(screens.NEURODIVERGENT_OPTIONS, ["Yes", "No", "Prefer not to say"])
        self.assertEqual(
            screens.NEURODIVERGENT_CHARACTERISTICS_QUESTION,
            "If yes, what neurodivergent characteristics do you have? (optional)",
        )

    def test_characteristics_box_opens_only_on_yes(self):
        at = _profile_page()
        self.assertFalse(at.exception)
        question = _widget(at.radio, screens.NEURODIVERGENT_QUESTION)
        self.assertIsNone(question.value)
        labels = [widget.label for widget in at.text_input]
        self.assertNotIn(screens.NEURODIVERGENT_CHARACTERISTICS_QUESTION, labels)

        question.set_value("No").run()
        labels = [widget.label for widget in at.text_input]
        self.assertNotIn(screens.NEURODIVERGENT_CHARACTERISTICS_QUESTION, labels)

        _widget(at.radio, screens.NEURODIVERGENT_QUESTION).set_value("Yes").run()
        labels = [widget.label for widget in at.text_input]
        self.assertIn(screens.NEURODIVERGENT_CHARACTERISTICS_QUESTION, labels)

    def test_continue_works_without_answering_it(self):
        at = _profile_page()
        answers = {
            "What is your age group?": "25-34",
            "What is your gender?": "Female",
            "How would you describe your English proficiency?": "Advanced",
            "How often do you use AI tools such as ChatGPT, Gemini, or Claude?": "Daily",
            screens.ATTENTION_CHECK_PROFILE_QUESTION: "A few times a month",
            "Have you played Codenames before?": screens.CODENAMES_EXPERIENCE_OPTIONS[0],
        }
        for label, value in answers.items():
            _widget(at.radio, label).set_value(value)
        with patch("ui.screens.initialize_session_log", return_value=False) as register:
            next(b for b in at.button if b.label == "Continue").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(register.called)
        self.assertEqual(at.session_state["neurodivergent"], "")
        self.assertEqual(at.session_state["neurodivergent_characteristics"], "")

    def test_answers_are_stored_on_the_session_row(self):
        for field in ("neurodivergent", "neurodivergent_characteristics"):
            self.assertIn(field, storage.SESSIONS_LOG_FIELDS)
        state = {
            "neurodivergent": "Yes",
            "neurodivergent_characteristics": "ADHD",
        }
        fake_state = type("S", (dict,), {"__getattr__": dict.__getitem__})(state)
        with patch.object(storage, "st", SimpleNamespace(session_state=fake_state)):
            row = storage._session_row()
        self.assertEqual(row["neurodivergent"], "Yes")
        self.assertEqual(row["neurodivergent_characteristics"], "ADHD")


if __name__ == "__main__":
    unittest.main()
