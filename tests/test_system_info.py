from pathlib import Path
import tempfile
import unittest

from backend.system_info import SystemInfo


class SystemInfoTest(unittest.TestCase):
    def test_application_storage_excludes_other_disk_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio, reports, calibration = root / "audio", root / "reports", root / "calibration"
            for directory in (audio, reports, calibration): directory.mkdir()
            (audio / "event.mp3").write_bytes(b"a" * 100)
            (reports / "report.pdf").write_bytes(b"b" * 200)
            (calibration / "profile.sen").write_bytes(b"c" * 50)
            database = root / "noisemeter.sqlite3"; database.write_bytes(b"d" * 300)
            info = SystemInfo({"audio_dir":str(audio), "report_dir":str(reports),
                               "calibration_dir":str(calibration), "database":str(database)}).read()
            self.assertEqual(info["disk_used"], 650)
            self.assertGreater(info["disk_free"], 650)


if __name__ == "__main__": unittest.main()
