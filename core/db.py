"""Postgres storage layer.

Each experimental table keeps a handful of real, indexed columns for the
identifiers used to join tables and filter data, plus one JSONB ``data``
column holding every field described in the thesis's data model
(core/storage.py's *_LOG_FIELDS lists remain the source of truth for exactly
which keys that JSON document contains). This avoids hand-declaring on the
order of 150 typed SQL columns while keeping every value queryable in SQL
(``data->>'field_name'``) or in pandas (``json_normalize``).
"""

import json
import threading
import time

import psycopg2
import psycopg2.extensions
import psycopg2.extras
import streamlit as st

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    participant_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    condition TEXT NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT false,
    last_completed_stage TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (participant_id, session_id)
);

CREATE TABLE IF NOT EXISTS rounds (
    session_id TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    condition TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, round_number)
);

CREATE TABLE IF NOT EXISTS turns (
    session_id TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    turn_number INTEGER NOT NULL,
    condition TEXT NOT NULL,
    action_type TEXT NOT NULL,
    alignment_applicability TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, round_number, turn_number)
);

CREATE TABLE IF NOT EXISTS board_cards (
    session_id TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    board_instance_id TEXT NOT NULL,
    card_word TEXT NOT NULL,
    card_role TEXT NOT NULL,
    word_type TEXT NOT NULL,
    PRIMARY KEY (session_id, round_number, card_word)
);

-- One-time, idempotent migration for any table created before board_cards'
-- board_id column was renamed to board_instance_id (CREATE TABLE IF NOT
-- EXISTS above is a no-op against an already-existing table, so it can't
-- fix this on its own). Safe to run on every start: does nothing once the
-- rename has already happened.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'board_cards' AND column_name = 'board_id'
    ) THEN
        ALTER TABLE board_cards RENAME COLUMN board_id TO board_instance_id;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    condition TEXT NOT NULL,
    round_number TEXT NOT NULL,
    turn_number TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_payload JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS condition_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    assigned_count INTEGER NOT NULL DEFAULT 0
);
INSERT INTO condition_counter (id, assigned_count)
VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_rounds_session ON rounds (session_id);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns (session_id, round_number);
CREATE INDEX IF NOT EXISTS idx_board_cards_session ON board_cards (session_id, round_number);
CREATE INDEX IF NOT EXISTS idx_events_session ON events (session_id);

-- One row per registered session: the counterbalancing cell it was given
-- (see core.assignment). Written inside the same locked transaction that
-- chooses the cell, so concurrent registrations always see each other.
CREATE TABLE IF NOT EXISTS assignments (
    session_id TEXT PRIMARY KEY,
    cell_index INTEGER NOT NULL,
    condition TEXT NOT NULL,
    starting_role TEXT NOT NULL,
    board_order TEXT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_session_time ON events (session_id, timestamp);
"""


def _database_url():
    try:
        return st.secrets.get("DATABASE_URL", "")
    except Exception:
        return ""


# Connections are kept open and reused across reruns and sessions. Opening a
# new one for every write cost about 0.7 s each against Supabase (TCP + TLS +
# auth over the internet; its own "pooler" only pools the connections between
# the pooler and Postgres, not ours to the pooler), versus about 0.1 s for a
# query on an open connection -- and a single click can write several rows.
# At most this many idle connections are kept open for reuse; busier
# moments simply open extra ones, which are closed when handed back.
_POOL_MAX_IDLE = 10
_CONNECT_KWARGS = {
    # An explicit connect_timeout keeps a single attempt from hanging on the
    # OS's own (much longer) default when the database is briefly
    # unreachable -- e.g. Supabase's free tier pauses a project after
    # inactivity and takes a few seconds to wake back up.
    "connect_timeout": 8,
    # Keepalives stop an idle pooled connection from being dropped silently
    # by a firewall or the pooler between participants' clicks.
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}
_pool = None
_pool_lock = threading.Lock()


class _PooledConnection:
    """A connection borrowed from the pool. Callers use it exactly like a
    psycopg2 connection (cursor/commit/with-block); close() hands it back
    to the pool instead of closing it."""

    def __init__(self, conn, pool=None):
        self._conn = conn
        self._pool = pool

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._conn.__exit__(exc_type, exc, tb)

    def discard(self):
        """Close for real (a broken connection must not go back to the pool)."""
        conn, self._conn = self._conn, None
        if conn is None:
            return
        if self._pool is not None:
            self._pool.putconn(conn, close=True)
        else:
            conn.close()

    def close(self):
        conn = self._conn
        if conn is None:
            return
        if conn.closed:
            self.discard()
            return
        if conn.info.transaction_status != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
            # Never hand back a connection mid-transaction (e.g. after an error).
            try:
                conn.rollback()
            except psycopg2.Error:
                self.discard()
                return
        self._conn = None
        if self._pool is not None:
            self._pool.putconn(conn)
        else:
            conn.close()


class _IdleConnectionPool:
    """Keeps up to max_idle open connections for reuse, opens new ones on
    demand, never blocks or refuses. (psycopg2's own pools only keep
    `minconn` idle connections and close every other one when it is handed
    back, which with a small minconn meant reconnecting on almost every
    write; a large minconn would open them all at startup.)"""

    def __init__(self, database_url, max_idle):
        self._database_url = database_url
        self._max_idle = max_idle
        self._idle = []
        self._lock = threading.Lock()

    def getconn(self):
        with self._lock:
            while self._idle:
                conn = self._idle.pop()
                if not conn.closed:
                    return conn
        return psycopg2.connect(self._database_url, **_CONNECT_KWARGS)

    def putconn(self, conn, close=False):
        if not close and not conn.closed:
            with self._lock:
                if len(self._idle) < self._max_idle:
                    self._idle.append(conn)
                    return
        try:
            conn.close()
        except psycopg2.Error:
            pass


def _connection_pool(database_url):
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = _IdleConnectionPool(database_url, _POOL_MAX_IDLE)
        return _pool


def get_connection():
    """Borrow a connection; callers must close() it, which returns it to the
    pool for reuse."""
    database_url = _database_url()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Add it to the Streamlit app secrets."
        )
    pool = _connection_pool(database_url)
    return _PooledConnection(pool.getconn(), pool)


_RETRY_DELAYS_SECONDS = (0.4, 1.2)


def _with_connection(work):
    """Run work(conn) on a borrowed connection, retrying connection-level
    failures. Two kinds show up in practice: a pooled connection the server
    dropped while it sat idle (an error on first use), and opening a new
    connection timing out when many participants connect at the same moment
    (seen in a 30-user test). Each is retried on a fresh connection, up to
    three attempts in all, before the error is passed on. Every write in
    this module is safe to repeat (upserts and ON CONFLICT inserts)."""
    attempts = len(_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        conn = None
        try:
            conn = get_connection()
            return work(conn)
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            discard = getattr(conn, "discard", None)
            if discard:
                discard()
            if attempt == attempts - 1:
                raise
            time.sleep(_RETRY_DELAYS_SECONDS[attempt])
        finally:
            if conn is not None:
                conn.close()


_schema_ready = False


def ensure_schema():
    """Create tables if they do not exist yet. Safe to call on every rerun."""
    global _schema_ready
    if _schema_ready:
        return

    def work(conn):
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()

    _with_connection(work)
    _schema_ready = True


def _flat_view_sql(view_name, table, real_columns, all_field_names):
    """A read-only view that expands a JSONB `data` column into one plain
    text column per field, for analysis tools (R, pandas, SPSS, Excel) that
    expect a flat table rather than a JSON blob to unpack.

    Uses DROP + CREATE rather than CREATE OR REPLACE: Postgres refuses to
    REPLACE a view if it would rename/reorder an existing column position,
    which happens routinely here whenever a field is added anywhere but the
    very end of the *_LOG_FIELDS lists in core/storage.py. Dropping first is
    safe because these are pure read-only derived views with no dependents."""
    real_set = set(real_columns)
    select_parts = list(real_columns) + [
        f"data->>'{field}' AS {field}" for field in all_field_names if field not in real_set
    ]
    columns_sql = ",\n        ".join(select_parts)
    return (
        f"DROP VIEW IF EXISTS {view_name};\n"
        f"CREATE VIEW {view_name} AS\n    SELECT\n        {columns_sql}\n    FROM {table};"
    )


def ensure_flat_views(specs):
    """specs: iterable of (view_name, table, real_columns, all_field_names).

    Idempotent: CREATE OR REPLACE VIEW is safe to run every time the schema
    fields change, so callers can call this unconditionally at startup.
    """
    ensure_schema()

    def work(conn):
        with conn.cursor() as cur:
            for view_name, table, real_columns, all_field_names in specs:
                cur.execute(_flat_view_sql(view_name, table, real_columns, all_field_names))
        conn.commit()

    _with_connection(work)


def upsert_row(table, key_columns, extra_columns, data):
    """Insert or replace one row addressed by key_columns.

    extra_columns maps column name -> value for the real (non-JSONB) columns
    that also appear inside `data`; key_columns must be a subset of them.
    """
    ensure_schema()
    columns = list(extra_columns.keys()) + ["data"]
    values = list(extra_columns.values()) + [json.dumps(data, ensure_ascii=False)]
    placeholders = ", ".join(["%s"] * len(values))
    column_list = ", ".join(columns)
    update_columns = [c for c in columns if c not in key_columns]
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_columns)
    conflict_columns = ", ".join(key_columns)
    sql = (
        f"INSERT INTO {table} ({column_list}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_columns}) DO UPDATE SET {update_clause}"
    )
    _with_connection(lambda conn: _execute_and_commit(conn, sql, values))


def insert_row(table, columns, values):
    ensure_schema()
    column_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(values))
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    _with_connection(lambda conn: _execute_and_commit(conn, sql, values))


def _execute_and_commit(conn, sql, values):
    with conn.cursor() as cur:
        cur.execute(sql, values)
    conn.commit()


def insert_rows(table, columns, rows, conflict_columns=None):
    """Bulk insert. Pass conflict_columns (the table's primary/unique key)
    to make repeated calls with the same rows a no-op instead of raising --
    needed wherever a Streamlit rerun could plausibly replay the same
    insert (e.g. board_cards being logged again after a rerun interrupts
    the save before the round actually advances)."""
    if not rows:
        return
    ensure_schema()
    column_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    if conflict_columns:
        sql += f" ON CONFLICT ({', '.join(conflict_columns)}) DO NOTHING"

    def work(conn):
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, rows)
        conn.commit()

    _with_connection(work)


_CELL_OCCUPANCY_SQL = """
SELECT a.cell_index, COUNT(*)
FROM assignments a
WHERE EXISTS (
        SELECT 1 FROM sessions s WHERE s.session_id = a.session_id AND s.completed
    )
   OR GREATEST(
        a.assigned_at,
        COALESCE(
            (SELECT MAX(e.timestamp) FROM events e WHERE e.session_id = a.session_id),
            a.assigned_at
        )
    ) > now() - make_interval(mins => %s)
GROUP BY a.cell_index
"""


def allocate_assignment(session_id, cells, abandoned_after_minutes):
    """Give this session the least-occupied counterbalancing cell; return its index.

    A cell is occupied by sessions that completed or are still active (any
    logged activity within abandoned_after_minutes). Ties go to the lowest
    cell index, so cells fill in a fixed order. The condition_counter row is
    locked FOR UPDATE for the whole transaction, which serializes concurrent
    registrations: each one sees the cells already handed out to the others.
    Calling again for the same session returns its existing cell.
    """
    ensure_schema()
    return _with_connection(
        lambda conn: _allocate_assignment(conn, session_id, cells, abandoned_after_minutes)
    )


def _allocate_assignment(conn, session_id, cells, abandoned_after_minutes):
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM condition_counter WHERE id = 1 FOR UPDATE")
            cur.execute(
                "SELECT cell_index FROM assignments WHERE session_id = %s",
                [session_id],
            )
            existing = cur.fetchall()
            if existing:
                return int(existing[0][0])
            cur.execute(_CELL_OCCUPANCY_SQL, [int(abandoned_after_minutes)])
            occupancy = {int(index): int(count) for index, count in cur.fetchall()}
            cell = min(cells, key=lambda c: (occupancy.get(c["cell_index"], 0), c["cell_index"]))
            cur.execute(
                "INSERT INTO assignments "
                "(session_id, cell_index, condition, starting_role, board_order) "
                "VALUES (%s, %s, %s, %s, %s)",
                [
                    session_id,
                    cell["cell_index"],
                    cell["condition"],
                    cell["starting_role"],
                    json.dumps(cell["round_board_order"]),
                ],
            )
            cur.execute(
                "UPDATE condition_counter SET assigned_count = assigned_count + 1 WHERE id = 1"
            )
    return cell["cell_index"]
