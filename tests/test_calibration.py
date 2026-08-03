import math
from pathlib import Path
import tempfile
import unittest

from backend.calibration import CalibrationProfile


class SenCalibrationTest(unittest.TestCase):
    def test_hifi_selbstbau_metadata_and_response(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "MM2USB123_00d.sen"
            path.write_text("""Sensitivity at 1000 Hz in mV/dimension\t12.34
dB-offset\t94
Title\tMM2USB Demo
F [Hz]\tAmpl [dB]\tPhase [deg]
10.00\t-4.00\t0.00
1000.00\t0.00\t0.00
20000.00\t2.00\t0.00
""", encoding="utf-8")
            profile = CalibrationProfile(); profile.load(str(path))
            self.assertTrue(profile.loaded)
            self.assertEqual(profile.frequencies.tolist(), [10.0, 1000.0, 20000.0])
            self.assertEqual(profile.corrections.tolist(), [4.0, -0.0, -2.0])
            self.assertEqual(profile.sensitivity_mv_pa, 12.34)
            self.assertAlmostEqual(profile.spl_offset(94), 94 + 20 * math.log10(1000 / 12.34))


if __name__ == "__main__": unittest.main()
