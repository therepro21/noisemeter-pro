from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
 id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL, db REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_measurements_time ON measurements(recorded_at);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, peak_db REAL NOT NULL,
 threshold_db REAL NOT NULL, period_name TEXT NOT NULL, filename TEXT NOT NULL UNIQUE,
 duration_seconds REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(occurred_at);
"""

class Database:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connection() as db:
            db.executescript(SCHEMA)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def connection(self):
        db = self.connect()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def add_measurement(self, timestamp: str, db_value: float):
        with self.connection() as db:
            db.execute("INSERT INTO measurements(recorded_at, db) VALUES (?, ?)", (timestamp, db_value))

    def add_event(self, event: dict):
        with self.connection() as db:
            db.execute("""INSERT INTO events(occurred_at, peak_db, threshold_db, period_name, filename, duration_seconds)
                VALUES (:occurred_at,:peak_db,:threshold_db,:period_name,:filename,:duration_seconds)""", event)

    def events(self, start: str, end: str):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM events WHERE occurred_at >= ? AND occurred_at < ? ORDER BY occurred_at DESC", (start, end))]

    def summary(self, start: str, end: str):
        with self.connection() as db:
            return dict(db.execute("""SELECT COUNT(*) event_count, COALESCE(MAX(peak_db),0) peak_db,
              COALESCE(AVG(peak_db),0) average_db FROM events WHERE occurred_at >= ? AND occurred_at < ?""", (start, end)).fetchone())

    def level_peak(self, start: str, end: str) -> float:
        """Highest actual measured level, independent of recorded events."""
        with self.connection() as db:
            row = db.execute("SELECT COALESCE(MAX(db), 0) AS peak FROM measurements WHERE recorded_at >= ? AND recorded_at < ?", (start, end)).fetchone()
            return float(row["peak"])

    def day_history(self, start: str, end: str):
        """One maximum per five minutes keeps the web chart compact."""
        with self.connection() as db:
            return [dict(row) for row in db.execute("""
                SELECT substr(recorded_at, 1, 14) || printf('%02d', CAST(substr(recorded_at, 15, 2) AS INTEGER) / 5 * 5) AS minute, MAX(db) AS db
                FROM measurements
                WHERE recorded_at >= ? AND recorded_at < ?
                GROUP BY substr(recorded_at, 1, 14), CAST(substr(recorded_at, 15, 2) AS INTEGER) / 5
                ORDER BY minute
            """, (start, end))]

    def level_breakdown(self, kind: str, start: str, end: str):
        grouping = {"day": "substr(recorded_at,12,2) || ':00'", "week": "substr(recorded_at,1,10)", "month": "strftime('%Y-W%W', recorded_at)", "year": "substr(recorded_at,1,7)"}[kind]
        with self.connection() as db:
            return [dict(row) for row in db.execute(f"SELECT {grouping} label, MAX(db) maximum_db, AVG(db) average_db FROM measurements WHERE recorded_at >= ? AND recorded_at < ? GROUP BY {grouping} ORDER BY label", (start, end))]

    def remove_events_before(self, timestamp: str):
        with self.connection() as db:
            files = [row["filename"] for row in db.execute("SELECT filename FROM events WHERE occurred_at < ?", (timestamp,))]
            db.execute("DELETE FROM events WHERE occurred_at < ?", (timestamp,))
            return files
