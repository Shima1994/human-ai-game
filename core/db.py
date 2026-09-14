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
    board_id TEXT NOT NULL,
    card_word TEXT NOT NULL,
    card_role TEXT NOT NULL,
    word_type TEXT NOT NULL,
    PRIMARY KEY (session_id, round_number, card_word)
);

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
"""


def _database_url():
    try:
        return st.secrets.get("DATABASE_URL", "")
    except Exception:
        return ""


def get_connection():
    """Open a new connection. Callers are responsible for closing it."""
    database_url = _database_url()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Add it to the Streamlit app secrets."
        )
    return psycopg2.connect(database_url)


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


def insert_rows(table, columns, rows):
    if not rows:
        return
    ensure_schema()
    column_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, rows)
        conn.commit()
    finally:
        conn.close()


def allocate_condition(valid_conditions, default_condition):
    """Atomically alternate condition and return the assigned value.

    Uses a single row locked with SELECT ... FOR UPDATE inside a transaction,
    so concurrent registrations are serialized by Postgres itself rather than
    racing on a shared file or a process-local lock.
    """
    ensure_schema()
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT assigned_count FROM condition_counter WHERE id = 1 FOR UPDATE"
                )
                (count,) = cur.fetchone()
                ordered_conditions = [default_condition] + sorted(
                    c for c in valid_conditions if c != default_condition
                )
                condition = ordered_conditions[count % len(ordered_conditions)]
                cur.execute(
                    "UPDATE condition_counter SET assigned_count = assigned_count + 1 WHERE id = 1"
                )
        return condition
    finally:
        conn.close()
