"""Behavioral replacements for the screen-flow checks that used to compare
literal substring positions inside app.py/screens.py source text (fragile:
a harmless reformat breaks them even with zero behavior change; they also
can't observe what the running app actually renders). These drive the real
app via streamlit.testing.v1.AppTest instead.

No test here makes a real OpenAI call or a real database write: every
storage/logging function reachable from the screens under test is patched
on ui.screens (where it was imported by name, not on core.storage, since
patching the origin module doesn't affect an already-bound `from x import y`
reference).
"""
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


HERO_MARKER = "hero-title"


def _fresh_app():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at


def _all_markdown_text(at):
    return "\n".join(el.value for el in at.markdown)


class AppHeaderVisibilityTests(unittest.TestCase):
    """render_app_header() (the big "Human-AI Cooperative Word Game" hero)
    is only meant to appear above the tutorial screen -- not consent,
    welcome/game-guide, or the participant profile."""

    def test_header_absent_on_consent_screen(self):
        at = _fresh_app()
        self.assertNotIn(HERO_MARKER, _all_markdown_text(at))

    def test_header_absent_on_welcome_screen(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.run()
        self.assertNotIn(HERO_MARKER, _all_markdown_text(at))

    def test_header_absent_on_participant_profile_screen(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.run()
        self.assertNotIn(HERO_MARKER, _all_markdown_text(at))

    def test_header_present_on_tutorial_screen(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0001"
        at.session_state["nickname"] = "Test"
        at.run()
        self.assertIn(HERO_MARKER, _all_markdown_text(at))


class ParticipantIdAnonymityTests(unittest.TestCase):
    """participant_id must always be the anonymous session-derived ID, even
    when the participant types a nickname -- never the free-text nickname
    itself (two participants could otherwise collide their data under one
    participant_id, or de-anonymize themselves)."""

    def test_participant_id_is_not_the_typed_nickname(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.run()

        at.text_input[0].set_value("MyRealName").run()
        at.selectbox[0].set_value("25-34").run()
        for radio in at.radio:
            radio.set_value(radio.options[0])
        at.run()

        # Let the real initialize_session_log run (this is what actually
        # decides participant_id), but stub out its Postgres calls so the
        # test exercises the real success path without a network round trip.
        with patch("core.db.allocate_condition", return_value="baseline"), \
                patch("core.db.upsert_row", return_value=None), \
                patch("core.db.insert_row", return_value=None):
            buttons = {b.label: b for b in at.button}
            buttons["Continue"].click().run()

        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["nickname"], "MyRealName")
        self.assertNotEqual(at.session_state["participant_id"], "MyRealName")
        self.assertRegex(at.session_state["participant_id"], r"^participant_[0-9a-f]{8}$")


class DebriefingGateOrderingTests(unittest.TestCase):
    """The debriefing document (with the real completion code) must not
    render before the post-game questionnaire is submitted."""

    def _base_state(self, at):
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0001"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = True
        at.session_state["score"] = 10
        at.session_state["medal_counts"] = {"gold": 1, "silver": 1, "none": 2}
        at.session_state["condition"] = "baseline"
        at.session_state["completion_code"] = "TESTCODE1"
        at.session_state["session_completed_logged"] = True

    def test_debriefing_hidden_until_questionnaire_submitted(self):
        at = _fresh_app()
        self._base_state(at)
        at.session_state["post_game_questionnaire_submitted"] = False
        at.run()

        self.assertFalse(at.exception)
        rendered = _all_markdown_text(at)
        self.assertNotIn("TESTCODE1", rendered)
        self.assertIn("Final questions", rendered)

    def test_debriefing_shown_with_completion_code_after_questionnaire(self):
        at = _fresh_app()
        self._base_state(at)
        at.session_state["post_game_questionnaire_submitted"] = True
        at.session_state["debriefing_acknowledged"] = False
        at.run()

        self.assertFalse(at.exception)
        rendered = _all_markdown_text(at)
        self.assertIn("TESTCODE1", rendered)
        self.assertIn("Your completion code", rendered)


if __name__ == "__main__":
    unittest.main()
