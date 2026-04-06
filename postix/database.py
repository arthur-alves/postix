"""SQLite database layer for Postix."""
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".local" / "share" / "postix" / "notes.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    """Apply incremental migrations on existing databases."""
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "alarms" not in tables:
        return  # fresh install — CREATE TABLE below will include all columns
    existing = {row[1] for row in conn.execute("PRAGMA table_info(alarms)")}
    if "sound_path" not in existing:
        conn.execute("ALTER TABLE alarms ADD COLUMN sound_path TEXT")


def init_db():
    with get_connection() as conn:
        _migrate(conn)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                content     TEXT    DEFAULT '',
                x           INTEGER DEFAULT 120,
                y           INTEGER DEFAULT 120,
                width       INTEGER DEFAULT 260,
                height      INTEGER DEFAULT 280,
                color       TEXT    DEFAULT '#FFFF88',
                always_on_top INTEGER DEFAULT 1,
                created_at  TEXT    DEFAULT (datetime('now')),
                updated_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alarms (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id          INTEGER NOT NULL
                                    REFERENCES notes(id) ON DELETE CASCADE,
                alarm_type       TEXT    NOT NULL,
                once_datetime    TEXT,
                daily_time       TEXT,
                interval_minutes INTEGER,
                enabled          INTEGER DEFAULT 1,
                last_triggered   TEXT,
                sound_path       TEXT,
                created_at       TEXT    DEFAULT (datetime('now'))
            );
        """)


def create_note(x=120, y=120):
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO notes (x, y) VALUES (?, ?)", (x, y))
        return cur.lastrowid


def get_all_notes():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM notes ORDER BY id")]


def update_note(note_id, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [note_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE notes SET {cols} WHERE id = ?", values)


def delete_note(note_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))


def get_alarms_for_note(note_id):
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM alarms WHERE note_id = ?", (note_id,)
        )]


def get_all_enabled_alarms():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT a.*, n.content FROM alarms a "
            "JOIN notes n ON a.note_id = n.id "
            "WHERE a.enabled = 1"
        )]


def save_alarm(alarm_id, note_id, alarm_type, once_datetime,
               daily_time, interval_minutes, enabled, sound_path=None):
    with get_connection() as conn:
        if alarm_id:
            conn.execute(
                "UPDATE alarms SET alarm_type=?, once_datetime=?, daily_time=?,"
                " interval_minutes=?, enabled=?, sound_path=? WHERE id=?",
                (alarm_type, once_datetime, daily_time,
                 interval_minutes, enabled, sound_path, alarm_id),
            )
            return alarm_id
        else:
            cur = conn.execute(
                "INSERT INTO alarms "
                "(note_id, alarm_type, once_datetime, daily_time, interval_minutes, enabled, sound_path)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (note_id, alarm_type, once_datetime,
                 daily_time, interval_minutes, enabled, sound_path),
            )
            return cur.lastrowid


def delete_alarm(alarm_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM alarms WHERE id = ?", (alarm_id,))


def update_alarm_last_triggered(alarm_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE alarms SET last_triggered = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), alarm_id),
        )


def disable_alarm(alarm_id):
    with get_connection() as conn:
        conn.execute("UPDATE alarms SET enabled = 0 WHERE id = ?", (alarm_id,))
