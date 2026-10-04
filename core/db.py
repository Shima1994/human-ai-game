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

import psycopg2
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


def get_connection():
    """Open a new connection. Callers are responsible for closing it.

    An explicit connect_timeout keeps a single attempt from hanging on the
    OS's own (much longer) default when the database is briefly unreachable
    -- e.g. Supabase's free tier pauses a project after inactivity and takes
    a few seconds to wake back up. Without this, one slow attempt could eat
    the whole retry budget in callers like initialize_session_log.
    """
    database_url = _database_url()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Add it to the Streamlit app secrets."
        )
    return psycopg2.connect(database_url, connect_timeout=8)


_schema_ready = False


def ensure_schema():
    """Create tables if they do not exist yet. Safe to call on every rerun."""
    global _schema_ready
    if _schema_ready:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
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
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for view_name, table, real_columns, all_field_names in specs:
                cur.execute(_flat_view_sql(view_name, table, real_columns, all_field_names))
        conn.commit()
    finally:
        conn.close()


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
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
        conn.commit()
    finally:
        conn.close()


def insert_row(table, columns, values):
    ensure_schema()
    column_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(values))
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
        conn.commit()
    finally:
        conn.close()


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
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, rows)
        conn.commit()
    finally:
        conn.close()


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
    conn = get_connection()
    try:
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
    finally:
        conn.close()
