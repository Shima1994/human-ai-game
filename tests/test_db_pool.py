"""The pooled connection layer: connections are reused instead of opened per
write, a connection the server dropped is retried once, and nothing is ever
handed back to the pool mid-transaction."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2
import psycopg2.extensions

from core import db


def fake_raw_connection(status=psycopg2.extensions.TRANSACTION_STATUS_IDLE, closed=0):
    conn = MagicMock()
    conn.closed = closed
    conn.info = SimpleNamespace(transaction_status=status)
    return conn


class PooledConnectionTests(unittest.TestCase):
    def test_close_returns_the_connection_to_the_pool(self):
        pool, raw = MagicMock(), fake_raw_connection()
        db._PooledConnection(raw, pool).close()
        pool.putconn.assert_called_once_with(raw)
        raw.close.assert_not_called()

    def test_close_twice_is_harmless(self):
        pool, raw = MagicMock(), fake_raw_connection()
        conn = db._PooledConnection(raw, pool)
        conn.close()
        conn.close()
        pool.putconn.assert_called_once()

    def test_open_transaction_is_rolled_back_before_reuse(self):
        pool = MagicMock()
        raw = fake_raw_connection(status=psycopg2.extensions.TRANSACTION_STATUS_INERROR)
        db._PooledConnection(raw, pool).close()
        raw.rollback.assert_called_once()
        pool.putconn.assert_called_once_with(raw)

    def test_broken_connection_is_discarded_not_reused(self):
        pool, raw = MagicMock(), fake_raw_connection(closed=2)
        db._PooledConnection(raw, pool).close()
        pool.putconn.assert_called_once_with(raw, close=True)


class IdleConnectionPoolTests(unittest.TestCase):
    def test_returned_connection_is_reused_instead_of_reconnecting(self):
        raw = fake_raw_connection()
        with patch.object(db.psycopg2, "connect", return_value=raw) as connect:
            pool = db._IdleConnectionPool("postgres://x", max_idle=2)
            first = pool.getconn()
            pool.putconn(first)
            self.assertIs(pool.getconn(), raw)
        connect.assert_called_once()

    def test_extra_connections_beyond_max_idle_are_closed(self):
        conns = [fake_raw_connection() for _ in range(3)]
        with patch.object(db.psycopg2, "connect", side_effect=conns):
            pool = db._IdleConnectionPool("postgres://x", max_idle=2)
            borrowed = [pool.getconn() for _ in range(3)]
            for conn in borrowed:
                pool.putconn(conn)
        conns[2].close.assert_called_once()
        conns[0].close.assert_not_called()

    def test_closed_idle_connection_is_skipped(self):
        dead, live = fake_raw_connection(closed=1), fake_raw_connection()
        with patch.object(db.psycopg2, "connect", return_value=live):
            pool = db._IdleConnectionPool("postgres://x", max_idle=2)
            pool._idle.append(dead)
            self.assertIs(pool.getconn(), live)


class RetryTests(unittest.TestCase):
    def test_stale_connection_is_retried_once_on_a_fresh_one(self):
        stale, fresh = MagicMock(), MagicMock()
        calls = []

        def work(conn):
            calls.append(conn)
            if conn is stale:
                raise psycopg2.OperationalError("server closed the connection unexpectedly")
            return "ok"

        with patch.object(db, "get_connection", side_effect=[stale, fresh]), patch.object(db.time, "sleep"):
            self.assertEqual(db._with_connection(work), "ok")
        self.assertEqual(calls, [stale, fresh])
        stale.discard.assert_called_once()
        fresh.close.assert_called_once()

    def test_failure_is_raised_after_three_attempts(self):
        conn = MagicMock()
        attempts = []

        def work(_conn):
            attempts.append(1)
            raise psycopg2.OperationalError("database is down")

        with patch.object(db, "get_connection", return_value=conn), patch.object(db.time, "sleep"):
            with self.assertRaises(psycopg2.OperationalError):
                db._with_connection(work)
        self.assertEqual(len(attempts), 3)

    def test_timeout_while_opening_a_connection_is_retried(self):
        """Seen with 30 participants connecting at once: opening a new
        connection timed out for one or two of them."""
        fresh = MagicMock()
        with patch.object(
            db,
            "get_connection",
            side_effect=[psycopg2.OperationalError("timeout expired"), fresh],
        ), patch.object(db.time, "sleep"):
            self.assertEqual(db._with_connection(lambda conn: "ok"), "ok")
        fresh.close.assert_called_once()

    def test_ordinary_sql_errors_are_not_retried(self):
        conn = MagicMock()
        attempts = []

        def work(_conn):
            attempts.append(1)
            raise psycopg2.errors.UniqueViolation("duplicate key")

        with patch.object(db, "get_connection", return_value=conn):
            with self.assertRaises(psycopg2.errors.UniqueViolation):
                db._with_connection(work)
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
