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


GENERIC_HERO_MARKER = "hero-title"
TUTORIAL_MARKER = "TUTORIAL · PRACTICE ROUND"


def _fresh_app():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at


def _all_markdown_text(at):
    return "\n".join(el.value for el in at.markdown)


class AppHeaderVisibilityTests(unittest.TestCase):
    """render_app_header() (the big blue/gold "Human-AI Cooperative Word
    Game" banner) is only used on the rare board-generation-error fallback
    now, not on any of the four onboarding screens -- each of those has its
    own matching hero instead. The tutorial's hero (with its own eyebrow
    label) should appear only on the tutorial screen."""

    def test_generic_hero_absent_on_consent_screen(self):
        at = _fresh_app()
        self.assertNotIn(GENERIC_HERO_MARKER, _all_markdown_text(at))

    def test_generic_hero_absent_on_welcome_screen(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.run()
        self.assertNotIn(GENERIC_HERO_MARKER, _all_markdown_text(at))

    def test_generic_hero_absent_on_participant_profile_screen(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.run()
        self.assertNotIn(GENERIC_HERO_MARKER, _all_markdown_text(at))

    def test_tutorial_marker_present_only_on_tutorial_screen(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0001"
        at.session_state["nickname"] = "Test"
        at.run()
        self.assertNotIn(GENERIC_HERO_MARKER, _all_markdown_text(at))
        self.assertIn(TUTORIAL_MARKER, _all_markdown_text(at))

    def test_tutorial_marker_absent_on_participant_profile_screen(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.run()
        self.assertNotIn(TUTORIAL_MARKER, _all_markdown_text(at))


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


class GuesserSkipButtonGatingTests(unittest.TestCase):
    """The "Stop guessing and use 1 skip" button intentionally requires the
    same reasoning text as clicking a board card (the study needs that
    reasoning whether the turn ends in a guess or a skip) -- but filling in
    only the skip-interpretation chips must not look like enough on its
    own, or a participant reasonably expects skip to work. Confirmed
    against a real screenshot where a participant had filled the skip
    interpretation but left the reasoning unset, and the button stayed
    disabled with no visible explanation."""

    def _reach_guesser_with_hint(self, at):
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0002"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "adaptive"
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "human_clue"
        at.session_state["board"] = None
        at.run()
        at.session_state["role"] = "human_guesser"
        at.session_state["hint"] = "trust"
        at.session_state["hint_number"] = 2
        at.session_state["previous_hint"] = None
        at.session_state["ai_clue_intro_seen"] = True
        at.session_state["hint_targets"] = list(at.session_state["target_words"])[:2]
        at.run()
        return at

    def test_skip_button_disabled_until_reasoning_is_set(self):
        at = self._reach_guesser_with_hint(_fresh_app())

        def skip_button():
            return next(b for b in at.button if "skip" in b.label.lower())

        # Only the skip-interpretation chips filled, nothing else: skip must
        # still be disabled, and the reason must be visible on the page.
        board_words = list(at.session_state["board"])
        if at.multiselect:
            at.multiselect[-1].set_value(board_words[:2]).run()
        self.assertTrue(skip_button().disabled)
        self.assertIn(
            "before you can skip too",
            " ".join(el.value for el in at.caption),
        )

        # A valid reasoning alone: now it unlocks.
        at.text_area[0].set_value("This connects to trust between two people").run()
        self.assertFalse(skip_button().disabled)


class GuesserTurnStateClearedBeforeAiExplanationTests(unittest.TestCase):
    """After a guess completes, the turn's state (hint, pending_guesses)
    must be cleared BEFORE the AI-explanation call, not after. That call is
    a real, occasionally slow API request, and the clue timer's autorefresh
    can interrupt an in-flight rerun -- code after the interruption point
    never runs. If state-clearing happened after the slow call, an
    interrupted run leaves the old hint and already-submitted guesses stuck
    on screen, which looks exactly like "the AI repeated its previous clue
    and everything is locked." Confirmed against a real participant
    screenshot showing precisely that (same clue, same guesses, still
    selected, right after a turn that history already shows as complete)."""

    def _reach_guesser_with_hint(self, at):
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0003"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "adaptive"
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "human_clue"
        at.session_state["board"] = None
        at.run()
        at.session_state["role"] = "human_guesser"
        at.session_state["hint"] = "trust"
        at.session_state["hint_number"] = 1
        at.session_state["previous_hint"] = None
        at.session_state["ai_clue_intro_seen"] = True
        at.session_state["hint_targets"] = list(at.session_state["target_words"])[:1]
        at.run()
        return at

    @patch("ui.screens.log_event")
    @patch("ui.screens.generate_ai_turn_explanation")
    def test_hint_and_pending_guesses_cleared_before_ai_explanation_call(
        self, mock_explain, _mock_log
    ):
        at = self._reach_guesser_with_hint(_fresh_app())
        snapshot = {}

        def _capture(*_args, **_kwargs):
            snapshot["hint"] = at.session_state["hint"]
            snapshot["pending_guesses"] = list(at.session_state["pending_guesses"])
            return {
                "ai_relationship_type": "",
                "ai_explanation_raw": "",
                "ai_explanation_sanitized": "",
                "ai_explanation_is_valid": True,
                "ai_explanation_blocked_reason": "",
            }

        mock_explain.side_effect = _capture

        target_word = at.session_state["target_words"][0]
        at.text_area[0].set_value("This connects to trust between two people").run()
        board_button = next(b for b in at.button if b.label == target_word)
        board_button.click().run()

        self.assertTrue(mock_explain.called)
        self.assertEqual(snapshot.get("hint"), "")
        self.assertEqual(snapshot.get("pending_guesses"), [])


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
