from __future__ import annotations

import sqlite3
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
        with self.connect() as db:
            db.executescript(SCHEMA)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def add_measurement(self, timestamp: str, db_value: float):
        with self.connect() as db:
            db.execute("INSERT INTO measurements(recorded_at, db) VALUES (?, ?)", (timestamp, db_value))

    def add_event(self, event: dict):
        with self.connect() as db:
            db.execute("""INSERT INTO events(occurred_at, peak_db, threshold_db, period_name, filename, duration_seconds)
                VALUES (:occurred_at,:peak_db,:threshold_db,:period_name,:filename,:duration_seconds)""", event)

    def events(self, start: str, end: str):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM events WHERE occurred_at >= ? AND occurred_at < ? ORDER BY occurred_at DESC", (start, end))]

    def summary(self, start: str, end: str):
        with self.connect() as db:
            return dict(db.execute("""SELECT COUNT(*) event_count, COALESCE(MAX(peak_db),0) peak_db,
              COALESCE(AVG(peak_db),0) average_db FROM events WHERE occurred_at >= ? AND occurred_at < ?""", (start, end)).fetchone())
