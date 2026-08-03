import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend.database import Database


class DatabaseLeqTest(unittest.TestCase):
    def test_energy_average_and_legacy_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "legacy.sqlite3"
            db = sqlite3.connect(path)
            try:
                db.execute("CREATE TABLE measurements (id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL, db REAL NOT NULL)")
                db.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, peak_db REAL NOT NULL, threshold_db REAL NOT NULL, period_name TEXT NOT NULL, filename TEXT NOT NULL UNIQUE, duration_seconds REAL NOT NULL)")
                db.commit()
            finally:
                db.close()
            database = Database(str(path))
            database.add_measurement("2026-08-01T10:00:00", 50.0, 50.0)
            database.add_measurements([
                ("2026-08-01T10:00:01", 70.0, 70.0),
                ("2026-08-03T10:00:01", 60.0, 60.0),
            ])
            with database.connection() as connection:
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM measurements").fetchone()[0], 3)
            expected = 10 * math.log10((10 ** 5 + 10 ** 7) / 2)
            actual = database.summary("2026-08-01", "2026-08-02")["leq_db"]
            self.assertAlmostEqual(actual, expected)

            histories = database.daily_histories("2026-08-01", "2026-08-04")
            self.assertEqual([item["date"] for item in histories], ["2026-08-01", "2026-08-02", "2026-08-03"])
            self.assertEqual(len(histories[0]["points"]), 1)
            self.assertEqual(histories[1]["points"], [])


if __name__ == "__main__": unittest.main()
