import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import db, game_logic, storage
from core.constants import (
    CONDITION_ASSIGNMENT_VERSION,
    EXPERIMENT_VERSION,
    GUESS_MODEL_NAME,
    HINT_MODEL_NAME,
    REFLECTION_MODEL_NAME,
    SCHEMA_VERSION,
)


class FakeCursor:
    def __init__(self, fetchone_results=None):
        self.executed = []
        self._fetchone_results = list(fetchone_results or [])

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self, fetchone_results=None):
        self.cursor_obj = FakeCursor(fetchone_results)
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        return False


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def session_state():
    return State(
        participant_id="p1",
        nickname="P",
        session_id="s1",
        condition="baseline",
        starting_role="human_clue",
        session_start_time="2026-01-01T00:00:00",
        session_end_time="",
        consent_given=True,
        ai_round_summaries=[],
        interaction_history=[],
        round_finished=False,
        round_interactions=0,
        score=0,
        post_game_questionnaire={},
        last_activity_at="",
        last_completed_stage="participant_profile",
        session_end_reason="",
        withdrawal_requested=False,
        technical_termination=False,
    )


def game_state():
    return State(
        session_id="s1",
        round=1,
        role="human_clue",
        round_interactions=0,
        round_skips=0,
        interaction_history=[],
        target_words=["Alpha", "Beta"],
        neutral_words=["Neutral"],
        bomb_words=["Bomb"],
        bomb_word="Bomb",
        found_targets=[],
        guesses=[],
        used_hints=[],
        current_turn_start_time="",
        clue_timer_started_at="",
        clue_timer_duration_seconds=90,
        clue_timer_timeout_consumed=False,
        pending_reflection_turn=None,
        ai_round_summaries=[],
    )


class ProvenanceAndLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.original_storage_st = storage.st
        self.state = session_state()
        storage.st = SimpleNamespace(session_state=self.state)

    def tearDown(self):
        storage.st = self.original_storage_st

    def test_session_row_persists_canonical_provenance(self):
        row = storage._session_row()
        self.assertEqual(row["experiment_version"], EXPERIMENT_VERSION)
        self.assertEqual(row["schema_version"], SCHEMA_VERSION)
        self.assertEqual(row["condition_assignment_version"], CONDITION_ASSIGNMENT_VERSION)
        self.assertEqual(
            json.loads(row["model_identifier"]),
            {
                "hint": HINT_MODEL_NAME,
                "guess": GUESS_MODEL_NAME,
                "reflection": REFLECTION_MODEL_NAME,
            },
        )

    def test_code_commit_is_exact_when_available_and_blank_when_unavailable(self):
        with patch.object(storage, "CODE_COMMIT", "abc123"):
            self.assertEqual(storage._session_row()["code_commit"], "abc123")
        with patch.object(storage, "CODE_COMMIT", ""):
            self.assertEqual(storage._session_row()["code_commit"], "")

    def test_condition_assignment_alternates_atomically_via_db_counter(self):
        db._schema_ready = True
        try:
            fake_conn = FakeConnection(fetchone_results=[(1,)])
            with patch.object(db, "get_connection", return_value=fake_conn):
                condition = db.allocate_condition(
                    {"adaptive", "baseline"}, "adaptive"
                )
            self.assertEqual(condition, "baseline")
            select_sql = fake_conn.cursor_obj.executed[0][0]
            self.assertIn("FOR UPDATE", select_sql)
            update_sql = fake_conn.cursor_obj.executed[1][0]
            self.assertIn("UPDATE condition_counter", update_sql)
            self.assertTrue(fake_conn.committed)
            self.assertTrue(fake_conn.closed)
        finally:
            db._schema_ready = False

    def test_meaningful_progress_updates_lifecycle_but_row_render_does_not(self):
        with patch.object(storage, "log_session_state") as persist, patch.object(
            storage, "_iso_now", return_value="2026-01-01T00:01:00"
        ):
            storage.mark_session_progress("tutorial")
        self.assertEqual(self.state.last_activity_at, "2026-01-01T00:01:00")
        self.assertEqual(self.state.last_completed_stage, "tutorial")
        persist.assert_called_once_with(completed=False, persist_remote=True)
        before = self.state.last_activity_at
        storage._session_row()
        storage._session_row()
        self.assertEqual(self.state.last_activity_at, before)

    def test_completion_sets_known_end_reason_without_inventing_attrition(self):
        with patch.object(storage.db, "upsert_row"):
            storage.log_session_state(completed=True)
        row = storage._session_row(completed=True)
        self.assertEqual(row["session_end_reason"], "completed")
        self.assertEqual(row["last_completed_stage"], "completed")
        self.assertEqual(row["withdrawal_requested"], False)
        self.assertEqual(row["technical_termination"], False)

    def test_unknown_disappearance_and_api_failure_are_not_misclassified(self):
        row = storage._session_row(completed=False)
        self.assertEqual(row["session_end_reason"], "")
        self.assertEqual(row["withdrawal_requested"], False)
        self.assertEqual(row["technical_termination"], False)


class ActionAndRoundClassificationTests(unittest.TestCase):
    def setUp(self):
        self.original_storage_st = storage.st
        self.original_game_st = game_logic.st
        self.state = game_state()
        storage.st = SimpleNamespace(session_state=self.state)
        game_logic.st = SimpleNamespace(session_state=self.state)

    def tearDown(self):
        storage.st = self.original_storage_st
        game_logic.st = self.original_game_st

    def test_action_and_alignment_controlled_classifications(self):
        cases = [
            (
                {"outcome": "wrong", "guesses": ["Neutral"]},
                "interaction",
                "observed_completed_selection",
            ),
            (
                {"outcome": "skip", "skipped": True, "guesses": [], "skip_interpreted_cards": ["Alpha"]},
                "full_skip",
                "interpreted_only_skip",
            ),
            (
                {"outcome": "partial_skip", "partial_skip": True, "guesses": ["Alpha"]},
                "partial_skip",
                "partial_selection",
            ),
            (
                {"outcome": "timeout", "timed_out": True, "guesses": []},
                "timeout",
                "timeout_no_behavioral_selection",
            ),
        ]
        for item, expected_action, expected_applicability in cases:
            with self.subTest(action=expected_action):
                self.assertEqual(storage._action_classification(item), expected_action)
                self.assertEqual(
                    storage._alignment_applicability(item), expected_applicability
                )

    def test_classification_fields_are_persisted_in_normalized_turn(self):
        item = {
            "turn": 1,
            "outcome": "wrong",
            "guesses": ["Neutral"],
            "incorrect_guesses": ["Neutral"],
            "neutral_guesses": ["Neutral"],
            "clue_giver": "human",
        }
        row = storage._turn_analysis_row(
            "p1", item, {"Alpha": "abstract", "Beta": "abstract", "Neutral": "concrete", "Bomb": "concrete"}
        )
        self.assertEqual(row["action_type"], "interaction")
        self.assertEqual(row["alignment_applicability"], "observed_completed_selection")

    def test_existing_full_partial_and_timeout_counters_are_unchanged(self):
        with patch.object(game_logic, "finish_round", lambda: None):
            game_logic.record_skip("skip", 1, ["Alpha"], skipped_by="ai")
            self.assertEqual((self.state.round_interactions, self.state.round_skips), (0, 1))
            game_logic.record_interaction(
                "partial", 1, ["Alpha"], ["Alpha"], partial_skip=True, skipped_by="ai"
            )
            self.assertEqual((self.state.round_interactions, self.state.round_skips), (1, 2))
            game_logic.record_timeout("timeout", 1, ["Beta"])
            self.assertEqual((self.state.round_interactions, self.state.round_skips), (2, 2))

    def test_round_end_reason_uses_actual_termination_state(self):
        with patch.object(game_logic, "append_ai_round_summary", lambda: None):
            self.state.guesses = ["Alpha", "Beta"]
            self.state.found_targets = ["Alpha", "Beta"]
            game_logic.finish_round()
            self.assertEqual(self.state.round_end_reason, "all_targets_found")

            self.state.guesses = ["Bomb"]
            self.state.found_targets = []
            game_logic.finish_round()
            self.assertEqual(self.state.round_end_reason, "bomb")

            self.state.guesses = []
            self.state.round_interactions = 3
            game_logic.finish_round()
            self.assertEqual(self.state.round_end_reason, "completed_turn_limit")

    def test_incomplete_round_has_no_normal_termination_reason(self):
        self.state.update(
            condition="baseline",
            board=["Alpha", "Beta", "Neutral", "Bomb"],
            board_id="board-1",
            board_template_type="A",
            word_type_per_card={
                "Alpha": "abstract",
                "Beta": "abstract",
                "Neutral": "concrete",
                "Bomb": "concrete",
            },
            start_time="2026-01-01T00:00:00",
            round_start_time="2026-01-01T00:00:00",
            round_finished=False,
            round_end_reason="completed_turn_limit",
            round_bomb_hit=False,
            round_medal="none",
        )
        row = storage._round_analysis_row("p1", "2026-01-01T00:01:00", 0)
        self.assertEqual(row["round_end_reason"], "")


if __name__ == "__main__":
    unittest.main()
