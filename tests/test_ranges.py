from datetime import date
import unittest

# These tests only cover the date math and do not need a microphone.
from backend.app import period_range

class PeriodRangeTest(unittest.TestCase):
    def test_day(self):
        self.assertEqual(period_range("day", "2026-07-29"), ("2026-07-29", "2026-07-30"))

    def test_iso_week(self):
        self.assertEqual(period_range("week", "2026-W01"), ("2025-12-29", "2026-01-05"))

    def test_month(self):
        self.assertEqual(period_range("month", "2026-02"), ("2026-02-01", "2026-03-01"))

if __name__ == "__main__":
    unittest.main()
