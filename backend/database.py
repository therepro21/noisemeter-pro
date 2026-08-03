from __future__ import annotations

import sqlite3
import math
from contextlib import contextmanager
from pathlib import Path
from datetime import date, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
 id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL, db REAL NOT NULL, leq_db REAL
);
CREATE INDEX IF NOT EXISTS idx_measurements_time ON measurements(recorded_at);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, peak_db REAL NOT NULL,
 threshold_db REAL NOT NULL, period_name TEXT NOT NULL, filename TEXT NOT NULL UNIQUE,
 duration_seconds REAL NOT NULL, leq_db REAL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(occurred_at);
"""

class Database:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connection() as db:
            db.executescript(SCHEMA)
            self._add_column(db, "measurements", "leq_db", "REAL")
            self._add_column(db, "events", "leq_db", "REAL")

    @staticmethod
    def _add_column(db, table, column, definition):
        if column not in {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.create_aggregate("LEQ", 1, LeqAggregate)
        return db

    @contextmanager
    def connection(self):
        db = self.connect()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def add_measurement(self, timestamp: str, db_value: float, leq_db: float):
        with self.connection() as db:
            db.execute("INSERT INTO measurements(recorded_at, db, leq_db) VALUES (?, ?, ?)", (timestamp, db_value, leq_db))

    def add_event(self, event: dict):
        with self.connection() as db:
            db.execute("""INSERT INTO events(occurred_at, peak_db, threshold_db, period_name, filename, duration_seconds, leq_db)
                VALUES (:occurred_at,:peak_db,:threshold_db,:period_name,:filename,:duration_seconds,:leq_db)""", event)

    def events(self, start: str, end: str):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM events WHERE occurred_at >= ? AND occurred_at < ? ORDER BY occurred_at DESC", (start, end))]

    def summary(self, start: str, end: str):
        with self.connection() as db:
            event_summary = dict(db.execute("""SELECT COUNT(*) event_count, COALESCE(MAX(peak_db),0) peak_db,
              COALESCE(AVG(peak_db),0) average_db FROM events WHERE occurred_at >= ? AND occurred_at < ?""", (start, end)).fetchone())
            event_summary["leq_db"] = db.execute(
                "SELECT LEQ(leq_db) value FROM measurements WHERE recorded_at >= ? AND recorded_at < ?", (start, end)
            ).fetchone()["value"]
            return event_summary

    def level_peak(self, start: str, end: str) -> float:
        """Highest actual measured level, independent of recorded events."""
        with self.connection() as db:
            row = db.execute("SELECT COALESCE(MAX(db), 0) AS peak FROM measurements WHERE recorded_at >= ? AND recorded_at < ?", (start, end)).fetchone()
            return float(row["peak"])

    def day_history(self, start: str, end: str):
        """One maximum per five minutes keeps the web chart compact."""
        with self.connection() as db:
            return [dict(row) for row in db.execute("""
                SELECT substr(recorded_at, 1, 14) || printf('%02d', CAST(substr(recorded_at, 15, 2) AS INTEGER) / 5 * 5) AS minute, MAX(db) AS db, LEQ(leq_db) AS leq_db
                FROM measurements
                WHERE recorded_at >= ? AND recorded_at < ?
                GROUP BY substr(recorded_at, 1, 14), CAST(substr(recorded_at, 15, 2) AS INTEGER) / 5
                ORDER BY minute
            """, (start, end))]

    def report_history(self, kind: str, start: str, end: str):
        """Compact peak/Leq series sized for a PDF chart of the selected export period."""
        grouping = {
            "day": "substr(recorded_at, 1, 14) || printf('%02d', CAST(substr(recorded_at, 15, 2) AS INTEGER) / 5 * 5)",
            "week": "substr(recorded_at, 1, 13) || ':00'",
            "month": "substr(recorded_at, 1, 10)",
            "year": "strftime('%Y-W%W', recorded_at)",
        }[kind]
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                f"""SELECT {grouping} label, MAX(db) db, LEQ(leq_db) leq_db
                    FROM measurements WHERE recorded_at >= ? AND recorded_at < ?
                    GROUP BY {grouping} ORDER BY label""", (start, end)
            )]

    def level_breakdown(self, kind: str, start: str, end: str):
        grouping = {"day": "substr(recorded_at,12,2) || ':00'", "week": "substr(recorded_at,1,10)", "month": "strftime('%Y-W%W', recorded_at)", "year": "substr(recorded_at,1,7)"}[kind]
        with self.connection() as db:
            return [dict(row) for row in db.execute(f"SELECT {grouping} label, MAX(db) maximum_db, AVG(db) average_db, LEQ(leq_db) leq_db FROM measurements WHERE recorded_at >= ? AND recorded_at < ? GROUP BY {grouping} ORDER BY label", (start, end))]

    def daily_histories(self, start: str, end: str):
        """Return one five-minute curve per calendar day, including empty days."""
        current, stop = date.fromisoformat(start), date.fromisoformat(end)
        result = []
        while current < stop:
            next_day = current + timedelta(days=1)
            points = self.day_history(current.isoformat(), next_day.isoformat())
            result.append({
                "date": current.isoformat(),
                "points": [{"label": point["minute"], "db": point["db"], "leq_db": point["leq_db"]} for point in points],
            })
            current = next_day
        return result

    def period_statistics(self, selected_day: date, periods: list[dict]):
        """Measurement and event statistics for each configured clock-time period."""
        start, end = selected_day.isoformat(), (selected_day + timedelta(days=1)).isoformat()
        result = []
        with self.connection() as db:
            for period in periods:
                period_start, period_end = period["start"], period["end"]
                if period_start < period_end:
                    measurement_time = "time(recorded_at) >= ? AND time(recorded_at) < ?"
                    event_time = "time(occurred_at) >= ? AND time(occurred_at) < ?"
                    params = (period_start, period_end)
                else:
                    measurement_time = "(time(recorded_at) >= ? OR time(recorded_at) < ?)"
                    event_time = "(time(occurred_at) >= ? OR time(occurred_at) < ?)"
                    params = (period_start, period_end)
                levels = db.execute(
                    f"""SELECT COUNT(*) measurement_count, MIN(db) minimum_db,
                        MAX(db) maximum_db, AVG(db) average_db, LEQ(leq_db) leq_db FROM measurements
                        WHERE recorded_at >= ? AND recorded_at < ? AND {measurement_time}""",
                    (start, end, *params),
                ).fetchone()
                event_count = db.execute(
                    f"SELECT COUNT(*) count FROM events WHERE occurred_at >= ? AND occurred_at < ? AND {event_time}",
                    (start, end, *params),
                ).fetchone()["count"]
                result.append({
                    "name": period["name"], "start": period_start, "end": period_end,
                    "event_count": event_count, "measurement_count": levels["measurement_count"],
                    "minimum_db": levels["minimum_db"], "maximum_db": levels["maximum_db"],
                    "average_db": levels["average_db"], "leq_db": levels["leq_db"],
                })
        return result

    def delete_range(self, start: str, end: str):
        """Delete all measurements and events in [start, end), returning audio names."""
        with self.connection() as db:
            files = [row["filename"] for row in db.execute(
                "SELECT filename FROM events WHERE occurred_at >= ? AND occurred_at < ?", (start, end)
            )]
            event_count = db.execute(
                "SELECT COUNT(*) count FROM events WHERE occurred_at >= ? AND occurred_at < ?", (start, end)
            ).fetchone()["count"]
            measurement_count = db.execute(
                "SELECT COUNT(*) count FROM measurements WHERE recorded_at >= ? AND recorded_at < ?", (start, end)
            ).fetchone()["count"]
            db.execute("DELETE FROM events WHERE occurred_at >= ? AND occurred_at < ?", (start, end))
            db.execute("DELETE FROM measurements WHERE recorded_at >= ? AND recorded_at < ?", (start, end))
        return {"events": event_count, "measurements": measurement_count, "files": files}

    def remove_events_before(self, timestamp: str):
        with self.connection() as db:
            files = [row["filename"] for row in db.execute("SELECT filename FROM events WHERE occurred_at < ?", (timestamp,))]
            db.execute("DELETE FROM events WHERE occurred_at < ?", (timestamp,))
            return files


class LeqAggregate:
    """Energy-equivalent mean of equally spaced decibel samples."""
    def __init__(self):
        self.energy = 0.0
        self.count = 0

    def step(self, value):
        if value is not None and math.isfinite(float(value)):
            self.energy += 10 ** (float(value) / 10)
            self.count += 1

    def finalize(self):
        return 10 * math.log10(self.energy / self.count) if self.count else None
