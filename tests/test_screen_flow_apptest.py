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
from datetime import datetime, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


GENERIC_HERO_MARKER = "hero-title"
TUTORIAL_MARKER = "Practice round"


_SAFE_AI_EXPLANATION = {
    "ai_relationship_type": "Other",
    "ai_explanation_raw": "",
    "ai_explanation_sanitized": "",
    "ai_explanation_is_valid": False,
    "ai_explanation_blocked_reason": "test",
}
_module_patchers = []


def setUpModule():
    """No test in this module may reach the real AI. The "Turn result" step
    fetches the AI's clue explanation and replacement cards itself, and a
    later turn of an AI-clue round fetches its clue itself, so tests that
    prepare such states would otherwise call OpenAI.
    Tests that care about these calls patch them again themselves."""
    for target, value in (
        ("ui.screens.generate_ai_turn_explanation", _SAFE_AI_EXPLANATION),
        ("ui.screens.generate_ai_wrong_guess_replacements", {"cards": [], "raw_response": ""}),
        # Later turns of an AI-clue round fetch the next clue on their own.
        ("ui.screens._generate_and_store_ai_hint", False),
    ):
        patcher = patch(target, return_value=value)
        patcher.start()
        _module_patchers.append(patcher)


def tearDownModule():
    for patcher in _module_patchers:
        patcher.stop()


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
        with patch("core.db.allocate_assignment", return_value=1), \
                patch("core.db.upsert_row", return_value=None), \
                patch("core.db.insert_row", return_value=None):
            buttons = {b.label: b for b in at.button}
            buttons["Continue"].click().run()

        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["nickname"], "MyRealName")
        self.assertNotEqual(at.session_state["participant_id"], "MyRealName")

    def test_blank_optional_nickname_stays_blank_in_storage(self):
        """A participant who leaves the (explicitly optional) nickname field
        blank must have an empty nickname in session/DB state -- not their
        own anonymous participant_id silently written in as if they'd typed
        it. Display code (e.g. the final screen) falls back to "Participant"
        on its own; storage must not bake that fallback into the stored
        value, or the nickname column can no longer distinguish "left blank"
        from "typed their ID," polluting analysis data."""
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.run()

        # Nickname text_input left untouched (blank).
        for radio in at.radio:
            radio.set_value(radio.options[0])
        at.run()

        with patch("core.db.allocate_assignment", return_value=1), \
                patch("core.db.upsert_row", return_value=None), \
                patch("core.db.insert_row", return_value=None):
            buttons = {b.label: b for b in at.button}
            buttons["Continue"].click().run()

        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["nickname"], "")
        self.assertTrue(at.session_state["participant_id"])
        self.assertRegex(at.session_state["participant_id"], r"^participant_[0-9a-f]{8}$")


class TurnResultPopupSkipInfoTests(unittest.TestCase):
    """The "Turn result" dialog itself (not just the adjacent History
    sidebar) must show what the skipping guesser thought the clue meant and
    why, gated the same way the sidebar already gates it (share_explanations,
    i.e. the adaptive condition) -- added on request so a participant isn't
    forced to look away from the popup to see this."""

    def _reach_pending_reflection_for_skip(self, at, condition):
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0003"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = condition
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "human_clue"
        at.session_state["board"] = None
        at.run()
        board_words = list(at.session_state["board"])
        at.session_state["role"] = "human_guesser"
        at.session_state["pending_reflection_turn"] = 1
        at.session_state["interaction_history"] = [
            {
                "turn": 1,
                "clue_giver": "ai",
                "guesser": "human",
                "hint": "test",
                "hint_number": 2,
                "outcome": "skip",
                "skipped": True,
                "skipped_by": "human",
                "guesses": [],
                "neutral_guesses": [],
                "correct_guesses": [],
                "bomb_guesses": [],
                "bomb_hit": False,
                "timed_out": False,
                "skip_interpreted_cards": board_words[:2],
                "guess_rationale": "I thought it meant something else entirely.",
            }
        ]
        with patch("ui.screens.log_event"):
            at.run()
        return at, board_words

    def test_skip_info_shown_in_popup_when_condition_shares_explanations(self):
        at, board_words = self._reach_pending_reflection_for_skip(
            _fresh_app(), "adaptive"
        )
        text = _all_markdown_text(at)
        self.assertIn("Guesser thought", text)
        self.assertIn(board_words[0], text)
        self.assertIn("I thought it meant something else entirely.", text)

    def test_skip_info_hidden_in_popup_when_condition_does_not_share_explanations(self):
        at, _ = self._reach_pending_reflection_for_skip(_fresh_app(), "baseline")
        text = _all_markdown_text(at)
        self.assertNotIn("Guesser thought", text)
        self.assertNotIn("I thought it meant something else entirely.", text)


class HumanClueRepairReminderTests(unittest.TestCase):
    """After the AI skips a human clue, the next clue-giving turn shows a
    neutral reminder naming the participant's own unresolved intended
    cards -- a nudge, not a requirement."""

    def _clue_screen_after_ai_skip(self, intended):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0005"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "baseline"
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "human_clue"
        at.session_state["board"] = None
        at.run()
        targets = list(at.session_state["target_words"])
        at.session_state["interaction_history"] = [
            {
                "turn": 1,
                "clue_giver": "human",
                "guesser": "ai",
                "hint": "test",
                "hint_number": 1,
                "intended_targets": [targets[0]] if intended else [],
                "outcome": "skip",
                "skipped": True,
                "skipped_by": "ai",
                "repair_required": True,
                "guesses": [],
                "correct_guesses": [],
                "neutral_guesses": [],
                "bomb_guesses": [],
                "bomb_hit": False,
                "timed_out": False,
            }
        ]
        with patch("ui.screens.log_event"):
            at.run()
        return at, targets

    def test_reminder_names_the_unresolved_intended_card(self):
        at, targets = self._clue_screen_after_ai_skip(intended=True)
        self.assertFalse(at.exception)
        infos = " ".join(info.value for info in at.info)
        self.assertIn("The AI skipped your last clue", infos)
        self.assertIn(targets[0], infos)
        self.assertIn("free to choose any target cards", infos)

    def test_no_reminder_without_unresolved_cards(self):
        at, _ = self._clue_screen_after_ai_skip(intended=False)
        self.assertFalse(at.exception)
        infos = " ".join(info.value for info in at.info)
        self.assertNotIn("The AI skipped your last clue", infos)


class ClueGiverTurnResultTests(unittest.TestCase):
    """The AI's guess on a human clue is saved immediately (no separate,
    untimed "Save this turn" step), and behind the "Turn result" dialog only
    the cards selected so far are visible -- every other card is blurred."""

    def _clue_giver_turn_result(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0006"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "baseline"
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "human_clue"
        at.session_state["board"] = None
        at.run()
        targets = list(at.session_state["target_words"])
        neutrals = list(at.session_state["neutral_words"])
        guesses = [targets[0], neutrals[0]]
        at.session_state["guesses"] = guesses
        at.session_state["found_targets"] = [targets[0]]
        at.session_state["interaction_history"] = [
            {
                "turn": 1,
                "clue_giver": "human",
                "guesser": "ai",
                "hint": "test",
                "hint_number": 2,
                "intended_targets": [targets[0], targets[1]],
                "guesses": guesses,
                "correct_guesses": [targets[0]],
                "neutral_guesses": [neutrals[0]],
                "incorrect_guesses": [neutrals[0]],
                "bomb_guesses": [],
                "bomb_hit": False,
                "outcome": "partial_correct",
                "correct": True,
                "turn_points": 2,
            }
        ]
        at.session_state["pending_reflection_turn"] = 1
        with patch("ui.screens.log_event"):
            at.run()
        return at, guesses

    def test_unselected_cards_are_blurred_behind_the_turn_result(self):
        at, guesses = self._clue_giver_turn_result()
        self.assertFalse(at.exception)
        board_html = _all_markdown_text(at)
        blurred = board_html.count("word-blurred")
        self.assertEqual(blurred, 16 - len(guesses))
        for word in guesses:
            self.assertIn(f"<div>{word}</div>", board_html)

    def test_status_bar_includes_the_current_rounds_points(self):
        at, _ = self._clue_giver_turn_result()
        # score (earlier rounds) is 0 here; the turn just played earned 2.
        self.assertIn('<span class="medal-chip points">2 pts</span>', _all_markdown_text(at))

    def test_there_is_no_save_this_turn_step(self):
        at, _ = self._clue_giver_turn_result()
        self.assertNotIn("Save this turn", [button.label for button in at.button])


class SaveAiGuessTurnTests(unittest.TestCase):
    def test_ai_guess_is_recorded_immediately_with_repair_context(self):
        from types import SimpleNamespace

        from ui import screens

        state = SimpleNamespace(
            interaction_history=[{"turn": 1}],
            round_finished=False,
            hint="letters",
            hint_number=2,
            hint_targets=["A"],
            hint_expected_guesses=["A"],
            hint_explanation="x",
            current_hint_start_time="t",
            current_guess_start_time="t",
            current_reflection_start_time="t",
            previous_hint="",
            last_ai_guesses=[],
        )
        review = {"hint": "letters", "hint_number": 2, "guesses": ["A", "B"], "intended_targets": ["A"]}
        repair = {"skipped_turn": 0, "unresolved_targets": ["A"]}
        with patch.object(screens, "st", SimpleNamespace(session_state=state)), \
                patch.object(screens, "record_interaction") as record, \
                patch.object(screens, "log_event"), \
                patch.object(screens, "_attach_ai_wrong_guess_replacements") as replacements:
            screens._save_ai_guess_turn(review, repair)
        record.assert_called_once()
        self.assertEqual(record.call_args.args[2], ["A", "B"])
        self.assertIs(record.call_args.kwargs["repair_context"], repair)
        # The slow AI call is deferred to the result step, never run here.
        replacements.assert_not_called()
        self.assertEqual(state.last_ai_guesses, ["A", "B"])
        self.assertEqual(state.hint, "")
        self.assertEqual(state.previous_hint, "letters")


class TurnRecordingRaceTests(unittest.TestCase):
    """Regression tests for a recorded clue that stayed active (a refresh cut
    the recording run short) and was then recorded again as a timeout."""

    def _guesser_round(self):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0007"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "adaptive"
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "ai_clue"
        at.session_state["board"] = None
        at.run()
        return at

    def test_stale_recorded_clue_with_expired_timer_is_not_recorded_again(self):
        at = self._guesser_round()
        targets = list(at.session_state["target_words"])
        resolved = {
            "turn": 1,
            "clue_giver": "ai",
            "guesser": "human",
            "hint": "jewelry",
            "hint_number": 2,
            "intended_targets": targets[:2],
            "guesses": targets[:2],
            "correct_guesses": targets[:2],
            "neutral_guesses": [],
            "bomb_guesses": [],
            "bomb_hit": False,
            "outcome": "correct",
            "correct": True,
            "ai_explanation_attempted": True,
        }
        at.session_state["interaction_history"] = [resolved]
        at.session_state["found_targets"] = targets[:2]
        at.session_state["guesses"] = targets[:2]
        # The left-over state from the cut-short run: same clue, timer expired.
        at.session_state["hint"] = "jewelry"
        at.session_state["hint_number"] = 2
        at.session_state["current_guess_rationale"] = "not sure but"
        at.session_state["clue_timer_started_at"] = "2026-01-01T00:00:00+00:00"
        at.session_state["clue_timer_duration_seconds"] = 90
        at.session_state["clue_timer_timeout_consumed"] = False
        at.session_state["pending_reflection_turn"] = None
        with patch("ui.screens.log_event"):
            at.run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.session_state["interaction_history"]), 1)
        self.assertEqual(at.session_state["hint"], "")
        self.assertEqual(at.session_state["clue_timer_started_at"], "")

    def test_ai_explanation_is_fetched_once_on_the_result_step(self):
        at = self._guesser_round()
        targets = list(at.session_state["target_words"])
        at.session_state["interaction_history"] = [
            {
                "turn": 1,
                "clue_giver": "ai",
                "guesser": "human",
                "hint": "jewelry",
                "hint_number": 1,
                "intended_targets": targets[:1],
                "guesses": targets[:1],
                "correct_guesses": targets[:1],
                "neutral_guesses": [],
                "bomb_guesses": [],
                "bomb_hit": False,
                "outcome": "correct",
                "correct": True,
            }
        ]
        at.session_state["pending_reflection_turn"] = 1
        explanation = {
            "ai_relationship_type": "Other",
            "ai_explanation_raw": "shared idea",
            "ai_explanation_sanitized": "shared idea",
            "ai_explanation_is_valid": True,
            "ai_explanation_blocked_reason": "",
        }
        with patch("ui.screens.log_event"), patch(
            "ui.screens.generate_ai_turn_explanation", return_value=explanation
        ) as explain:
            at.run()
            at.run()
        self.assertFalse(at.exception)
        explain.assert_called_once()
        self.assertEqual(at.session_state["interaction_history"][0]["ai_explanation"], "shared idea")


class TimerRefreshTests(unittest.TestCase):
    def test_timer_refreshes_at_the_deadline_not_every_few_seconds(self):
        from ui import components

        with patch.object(components, "st_autorefresh") as refresh,                 patch.object(components, "st_components"),                 patch.object(components, "st"):
            components.st.session_state = {"clue_timer_duration_seconds": 90}
            components.render_clue_timer(42.5, pinned=False)
            self.assertEqual(refresh.call_args.kwargs["interval"], 42500 + 800)
            components.render_clue_timer(0, pinned=False)
            self.assertEqual(refresh.call_args.kwargs["interval"], 1000)

    def test_ring_carries_what_the_browser_needs_to_animate_it(self):
        """With only one rerun per decision, the ring and the last-15-seconds
        warning are advanced in the browser every second, from the deadline
        and total duration written on the ring itself."""
        from ui import components

        with patch.object(components, "st_autorefresh"),                 patch.object(components, "st_components") as frames,                 patch.object(components, "st") as st_mock:
            st_mock.session_state = {"clue_timer_duration_seconds": 90}
            components.render_clue_timer(42.5, pinned=False)
        ring_html = st_mock.markdown.call_args.args[0]
        self.assertIn('data-total-ms="90000"', ring_html)
        self.assertIn("data-deadline-ms=", ring_html)
        script = frames.html.call_args.args[0]
        self.assertIn("--ring-progress", script)
        self.assertIn('classList.add("warn")', script)


class AskAiForClueTests(unittest.TestCase):
    """The first turn of every AI-clue round waits for "Ask AI for a clue"
    (time to study the new board before the timer starts); later turns of
    the round get their clue automatically."""

    def _ai_clue_round(self, history):
        at = _fresh_app()
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0008"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "baseline"
        at.session_state["condition_assigned"] = True
        # Started as clue-giver, so round 2 is their first AI-clue round.
        at.session_state["round"] = 2
        at.session_state["starting_role"] = "human_clue"
        at.session_state["board"] = None
        at.run()
        at.session_state["interaction_history"] = history
        with patch("ui.screens.log_event"), patch(
            "ui.screens._generate_and_store_ai_hint", return_value=False
        ) as generate:
            at.run()
        return at, generate

    def test_first_ai_clue_round_waits_for_the_button_even_in_round_2(self):
        at, generate = self._ai_clue_round([])
        self.assertFalse(at.exception)
        self.assertIn("Ask AI for a clue", [b.label for b in at.button])
        generate.assert_not_called()

    def test_later_turns_of_the_round_get_the_clue_automatically(self):
        done = {
            "turn": 1, "clue_giver": "ai", "guesser": "human", "hint": "first",
            "hint_number": 1, "guesses": [], "correct_guesses": [], "neutral_guesses": [],
            "bomb_guesses": [], "bomb_hit": False, "outcome": "skip", "skipped": True,
        }
        at, generate = self._ai_clue_round([done])
        self.assertFalse(at.exception)
        self.assertNotIn("Ask AI for a clue", [b.label for b in at.button])
        generate.assert_called()


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

    def test_skip_without_reasoning_explains_instead_of_skipping(self):
        at = self._reach_guesser_with_hint(_fresh_app())

        def skip_button():
            return next(b for b in at.button if b.label.lower() == "skip")

        # The button is always enabled (a disabled one cost an extra click
        # once the reasoning was typed); without reasoning, clicking it says
        # why and does not open the skip dialog.
        self.assertFalse(skip_button().disabled)
        self.assertIn("before you can skip too", " ".join(el.value for el in at.caption))
        with patch("ui.screens.log_event"):
            skip_button().click().run()
        self.assertFalse(at.session_state["guesser_skip_dialog_open"] if "guesser_skip_dialog_open" in at.session_state else False)
        self.assertTrue(at.error)

    def test_skip_works_with_one_click_once_reasoning_is_typed(self):
        at = self._reach_guesser_with_hint(_fresh_app())
        at.text_area[0].set_value("This connects to trust between two people")
        with patch("ui.screens.log_event"):
            next(b for b in at.button if b.label.lower() == "skip").click().run()
        self.assertTrue(at.session_state["guesser_skip_dialog_open"])

    def test_card_is_selected_with_one_click_once_reasoning_is_typed(self):
        """The reasoning is saved and the card selected in the same click --
        the cards are buttons from the start, not only after the reasoning
        has been saved."""
        at = self._reach_guesser_with_hint(_fresh_app())
        neutral = list(at.session_state["neutral_words"])[0]
        card = next(b for b in at.button if b.label == neutral)
        self.assertFalse(card.disabled)
        at.text_area[0].set_value("This connects to trust between two people")
        with patch("ui.screens.log_event"):
            card.click().run()
        self.assertEqual(at.session_state["pending_guesses"], [neutral])
        # ...and it is shown as selected straight after that one click, not
        # only after the next one.
        self.assertIn(f"word-selected'><div>{neutral}</div>", _all_markdown_text(at))
        self.assertNotIn(neutral, [b.label for b in at.button])


class ClueTimerLabelingTests(unittest.TestCase):
    """The countdown pill deliberately no longer restates the participant's
    role ("Guessing"/"Giving your clue") in its ordinary states -- the role
    is already obvious from the screen, and the label just made the pill
    wider without adding information. It must still switch to a distinct
    "Final chance" state once both skips are gone and the one last
    forced-guess window is running -- that's a real state change, not a
    restated role, and stays labeled."""

    def _reach_guesser_with_hint(self, at):
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test0004"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "adaptive"
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "human_clue"
        at.session_state["board"] = None
        at.run()
        at.session_state["role"] = "ai_clue"
        at.session_state["hint"] = "trust"
        at.session_state["hint_number"] = 2
        at.session_state["previous_hint"] = None
        at.session_state["ai_clue_intro_seen"] = True
        at.session_state["hint_targets"] = list(at.session_state["target_words"])[:2]
        at.session_state["clue_timer_started_at"] = datetime.now(timezone.utc).isoformat()
        at.session_state["clue_timer_duration_seconds"] = 90
        at.run()
        return at

    def test_guesser_timer_has_no_role_label(self):
        at = self._reach_guesser_with_hint(_fresh_app())
        text = _all_markdown_text(at)
        self.assertNotIn("Guessing —", text)
        self.assertNotIn("Giving your clue", text)
        self.assertIn(" left", text)

    def test_final_guess_deadline_shows_final_chance_label(self):
        at = self._reach_guesser_with_hint(_fresh_app())
        at.session_state["final_guess_deadline_active"] = True
        at.run()
        text = _all_markdown_text(at)
        self.assertIn("Final chance", text)
        # The ordinary phase label must not also be showing at the same time.
        self.assertNotIn("Guessing —", text)


class HistorySidebarAlwaysVisibleTests(unittest.TestCase):
    """The live history sidebar must be visible from the very start of a
    round (showing "No hints or guesses yet."), not only once the first
    turn completes -- a participant should see it in the same place the
    whole time, not have it appear partway through."""

    def _reach_guesser(self, at, interaction_history):
        at.session_state["consent_given"] = True
        at.session_state["consent_timestamp"] = "2026-01-01T00:00:00"
        at.session_state["started"] = True
        at.session_state["participant_id"] = "participant_test_history"
        at.session_state["nickname"] = "Test"
        at.session_state["tutorial_completed"] = True
        at.session_state["game_over"] = False
        at.session_state["condition"] = "adaptive"
        at.session_state["condition_assigned"] = True
        at.session_state["round"] = 1
        at.session_state["starting_role"] = "ai_clue"
        at.session_state["board"] = None
        at.run()
        at.session_state["interaction_history"] = interaction_history
        at.run()
        return at

    def test_sidebar_visible_with_no_turns_yet(self):
        at = self._reach_guesser(_fresh_app(), [])
        self.assertFalse(at.exception)
        sidebar_text = "\n".join(el.value for el in at.sidebar.markdown)
        self.assertIn("History", sidebar_text)
        self.assertIn("No hints or guesses yet", sidebar_text)

    def test_sidebar_shows_turn_once_one_exists(self):
        at = self._reach_guesser(
            _fresh_app(),
            [{"turn": 1, "clue_giver": "ai", "guesser": "human", "hint": "trust", "hint_number": 1, "guesses": []}],
        )
        self.assertFalse(at.exception)
        sidebar_text = "\n".join(el.value for el in at.sidebar.markdown)
        self.assertIn("History", sidebar_text)


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

    def test_completion_code_still_visible_on_the_final_thank_you_screen(self):
        """The debriefing page is not the participant's last stop -- clicking
        "Finish study" moves on to a final thank-you screen. A participant
        who didn't copy the code down on the debriefing page must still be
        able to see it here, since this is the screen they're actually
        looking at when they go paste it into Prolific."""
        at = _fresh_app()
        self._base_state(at)
        at.session_state["post_game_questionnaire_submitted"] = True
        at.session_state["debriefing_acknowledged"] = True
        at.session_state["remote_log_status"] = ""
        at.run()

        self.assertFalse(at.exception)
        rendered = _all_markdown_text(at)
        self.assertIn("TESTCODE1", rendered)

    def test_prolific_participant_gets_return_to_prolific_link(self):
        at = _fresh_app()
        self._base_state(at)
        at.session_state["prolific_pid"] = "5f1a2b3c4d5e6f7a8b9c0d1e"
        at.session_state["post_game_questionnaire_submitted"] = True
        at.session_state["debriefing_acknowledged"] = True
        at.session_state["remote_log_status"] = ""
        at.run()

        self.assertFalse(at.exception)
        link_urls = [
            element.proto.url
            for element in at.main
            if element.type == "link_button"
        ]
        self.assertIn(
            "https://app.prolific.com/submissions/complete?cc=TESTCODE1",
            link_urls,
        )


if __name__ == "__main__":
    unittest.main()
