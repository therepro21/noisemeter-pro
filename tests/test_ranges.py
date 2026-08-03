from datetime import date
import unittest

# These tests only cover the date math and do not need a microphone.
from backend.app import backup_filename, period_range, report_filename

class PeriodRangeTest(unittest.TestCase):
    def test_day(self):
        self.assertEqual(period_range("day", "2026-07-29"), ("2026-07-29", "2026-07-30"))

    def test_iso_week(self):
        self.assertEqual(period_range("week", "2026-W01"), ("2025-12-29", "2026-01-05"))

    def test_month(self):
        self.assertEqual(period_range("month", "2026-02"), ("2026-02-01", "2026-03-01"))

    def test_report_filenames(self):
        self.assertEqual(report_filename("day", "2026-08-03", "2026-08-04"), "NoiseMeterPro_Tagesbericht_03-08-2026.pdf")
        self.assertEqual(report_filename("week", "2026-08-03", "2026-08-10"), "NoiseMeterPro_Wochenbericht_KW32_03-08-2026_bis_09-08-2026.pdf")
        self.assertEqual(report_filename("week", "2026-08-03", "2026-08-10", "en"), "NoiseMeterPro_WeeklyReport_CW32_03-08-2026_to_09-08-2026.pdf")
        self.assertEqual(backup_filename("week", "2026-08-03", "2026-08-10"), "NoiseMeterPro_Backup_KW32_03-08-2026_bis_09-08-2026.zip")

if __name__ == "__main__":
    unittest.main()
