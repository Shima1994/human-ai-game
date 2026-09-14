import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import psycopg2

from core import db, storage


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


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
    def __init__(self, fetchone_results=None, raise_on_execute=None):
        self.cursor_obj = FakeCursor(fetchone_results)
        self.committed = False
        self.closed = False
        self._raise_on_execute = raise_on_execute
        if raise_on_execute is not None:
            original_execute = self.cursor_obj.execute

            def execute(sql, params=None):
                original_execute(sql, params)
                raise raise_on_execute

            self.cursor_obj.execute = execute

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


class DurablePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_st = storage.st
        self.state = State(
            participant_id="p1",
            session_id="s1",
            condition="adaptive",
            round=1,
            round_interactions=1,
            remote_log_status="",
            remote_log_error="",
        )
        storage.st = SimpleNamespace(session_state=self.state)
        db._schema_ready = True
        # Flat-view creation is exercised separately; keep it a no-op here so
        # cursor.executed[0] is always the statement under test.
        storage._flat_views_ready = True

    def tearDown(self):
        storage.st = self.original_st
        db._schema_ready = False
        storage._flat_views_ready = False

    def test_log_event_writes_expected_row_and_reports_success(self):
        fake_conn = FakeConnection()
        with patch.object(db, "get_connection", return_value=fake_conn):
            storage.log_event("ai_clue_generation_failed", {"error": "x"}, round_number=2, turn_number=3)

        sql, params = fake_conn.cursor_obj.executed[0]
        self.assertIn("INSERT INTO events", sql)
        # session_id, participant_id, condition, round_number, turn_number, event_type, event_payload
        self.assertEqual(params[0], "s1")
        self.assertEqual(params[1], "p1")
        self.assertEqual(params[2], "adaptive")
        self.assertEqual(params[3], "2")
        self.assertEqual(params[4], "3")
        self.assertEqual(params[5], "ai_clue_generation_failed")
        self.assertEqual(json.loads(params[6]), {"error": "x"})
        self.assertTrue(fake_conn.committed)
        self.assertEqual(self.state.remote_log_status, "db_saved")

    def test_log_event_failure_is_reported_and_does_not_raise(self):
        fake_conn = FakeConnection(raise_on_execute=psycopg2.OperationalError("connection refused"))
        with patch.object(db, "get_connection", return_value=fake_conn):
            storage.log_event("submitted")  # must not raise
        self.assertEqual(self.state.remote_log_status, "db_failed")
        self.assertIn("connection refused", self.state.remote_log_error)

    def test_log_session_state_upserts_by_participant_and_session(self):
        fake_conn = FakeConnection()
        with patch.object(db, "get_connection", return_value=fake_conn):
            storage.log_session_state(completed=False)

        sql, params = fake_conn.cursor_obj.executed[0]
        self.assertIn("INSERT INTO sessions", sql)
        self.assertIn("ON CONFLICT (participant_id, session_id)", sql)
        self.assertIn("DO UPDATE SET", sql)
        self.assertEqual(self.state.remote_log_status, "db_saved")

    def test_log_session_state_failure_is_visible_and_does_not_raise(self):
        fake_conn = FakeConnection(raise_on_execute=psycopg2.OperationalError("offline"))
        with patch.object(db, "get_connection", return_value=fake_conn):
            storage.log_session_state(completed=False)  # must not raise
        self.assertEqual(self.state.remote_log_status, "db_failed")
        self.assertIn("offline", self.state.remote_log_error)

    def test_round_and_turn_rows_upsert_idempotently_on_session_round_turn_keys(self):
        round_row = {field: "" for field in storage.ROUNDS_LOG_FIELDS}
        round_row.update(session_id="s1", round_number=1, condition="adaptive")
        turn_row = {field: "" for field in storage.TURNS_LOG_FIELDS}
        turn_row.update(
            session_id="s1",
            round_number=1,
            turn_number=1,
            condition="adaptive",
            action_type="interaction",
            alignment_applicability="observed_completed_selection",
        )

        fake_conn = FakeConnection()
        with patch.object(db, "get_connection", return_value=fake_conn), patch.object(
            storage, "_round_analysis_row", return_value=round_row
        ), patch.object(
            storage, "_turn_analysis_row", return_value=turn_row
        ), patch.object(
            storage, "_board_card_rows", return_value=[]
        ):
            returned_round, returned_turns = storage.append_analysis_logs(
                "p1", "2026-01-01T00:00:00", 1, [{}]
            )

        executed_sql = [call[0] for call in fake_conn.cursor_obj.executed]
        self.assertTrue(any("INSERT INTO rounds" in sql and "ON CONFLICT (session_id, round_number)" in sql for sql in executed_sql))
        self.assertTrue(
            any(
                "INSERT INTO turns" in sql
                and "ON CONFLICT (session_id, round_number, turn_number)" in sql
                for sql in executed_sql
            )
        )
        self.assertEqual(returned_round, round_row)
        self.assertEqual(returned_turns, [turn_row])

    def test_log_round_reports_failure_without_losing_the_completed_interaction_events(self):
        self.state.update(
            guesses=[],
            target_words=["Alpha"],
            bomb_words=["Bomb"],
            round_interactions=1,
            round_medal="none",
            round_bomb_hit=False,
            score=0,
            last_score_change=0,
            interaction_history=[],
        )
        minimal_round_row = {"session_id": "s1", "round_number": 1, "condition": "adaptive"}
        fake_conn = FakeConnection(raise_on_execute=psycopg2.OperationalError("db down"))
        with patch.object(db, "get_connection", return_value=fake_conn), patch.object(
            storage, "_round_analysis_row", return_value=minimal_round_row
        ), patch.object(storage, "_board_card_rows", return_value=[]):
            storage.log_round("p1")  # must not raise despite the DB error
        self.assertEqual(self.state.remote_log_status, "db_failed")

    def test_initialize_session_log_retries_then_succeeds_after_transient_failures(self):
        del self.state["participant_id"]
        self.state.condition_assigned = False
        storage.st = SimpleNamespace(session_state=self.state, error=lambda *a, **k: None)

        failing_conn = FakeConnection(raise_on_execute=psycopg2.OperationalError("db down"))
        working_conn = FakeConnection(fetchone_results=[(0,)])
        # allocate_condition's first attempt gets the failing connection; every
        # later get_connection() call (the successful retry, plus the
        # log_session_state/log_event writes that follow registration) gets
        # the working one.
        with patch.object(
            db, "get_connection", side_effect=[failing_conn] + [working_conn] * 10
        ), patch.object(storage.time, "sleep", return_value=None):
            result = storage.initialize_session_log("participant_abc12345")

        self.assertTrue(result)
        self.assertEqual(self.state.participant_id, "participant_abc12345")
        self.assertTrue(self.state.condition_assigned)
        self.assertIn(self.state.condition, ("adaptive", "baseline"))

    def test_initialize_session_log_gives_up_after_repeated_failure(self):
        del self.state["participant_id"]
        self.state.condition_assigned = False
        storage.st = SimpleNamespace(session_state=self.state, error=lambda *a, **k: None)

        always_failing = FakeConnection(raise_on_execute=psycopg2.OperationalError("db down"))
        with patch.object(db, "get_connection", return_value=always_failing), patch.object(
            storage.time, "sleep", return_value=None
        ):
            result = storage.initialize_session_log("participant_abc12345")

        self.assertFalse(result)
        # Nothing participant-identifying may be committed on failure: app.py
        # routes past the profile screen purely on participant_id being set,
        # so a half-registered participant must never look "registered".
        self.assertNotIn("participant_id", self.state)
        self.assertFalse(self.state.condition_assigned)
        self.assertFalse(self.state.get("session_log_initialized"))


if __name__ == "__main__":
    unittest.main()
