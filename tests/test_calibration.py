import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

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

            # SEN requires logarithmic interpolation: sqrt(10 * 1000) is halfway.
            geometric_midpoint = math.sqrt(10 * 1000)
            gain = profile._gain(2000, int(geometric_midpoint * 4), "A", True)
            frequencies = np.fft.rfftfreq(2000, d=1 / int(geometric_midpoint * 4))
            midpoint_index = int(np.argmin(np.abs(frequencies - geometric_midpoint)))
            frequency_weight = profile._frequency_weight(frequencies, "A")
            correction = 20 * np.log10(gain[midpoint_index]) - frequency_weight[midpoint_index]
            self.assertAlmostEqual(correction, 2.0, delta=0.05)

    def test_parseval_rms_matches_time_domain_and_pair(self):
        profile = CalibrationProfile()
        profile.frequencies = np.array([10.0, 1000.0, 22050.0])
        profile.corrections = np.array([3.0, 0.0, -2.0])
        random = np.random.default_rng(42)
        samples = random.normal(0, 0.1, (12000, 1)).astype(np.float32)
        spectrum = np.fft.rfft(samples[:, 0])
        for calibrated in (False, True):
            gain = profile._gain(len(samples), 48000, "A", calibrated)
            expected = float(np.sqrt(np.mean(np.square(np.fft.irfft(spectrum * gain, n=len(samples)).astype(np.float64)))))
            actual = profile.weighted_rms(samples, 48000, "A", calibrated)
            self.assertAlmostEqual(actual, expected, places=12)
        pair = profile.weighted_rms_pair(samples, 48000, "A")
        self.assertAlmostEqual(pair[0], profile.weighted_rms(samples, 48000, "A", True), places=12)
        self.assertAlmostEqual(pair[1], profile.weighted_rms(samples, 48000, "A", False), places=12)

        time_axis = np.arange(12000) / 48000
        tone = (0.1 * np.sin(2 * np.pi * 1000 * time_axis)).astype(np.float32)[:, None]
        calibrated, uncalibrated, frequencies, band_energies, dominant = profile.weighted_analysis(tone, 48000, "A")
        expected_pair = profile.weighted_rms_pair(tone, 48000, "A")
        self.assertAlmostEqual(calibrated, expected_pair[0], places=12)
        self.assertAlmostEqual(uncalibrated, expected_pair[1], places=12)
        self.assertEqual(len(frequencies), 48)
        self.assertEqual(len(band_energies), 48)
        self.assertAlmostEqual(dominant, 1000.0, delta=4.0)
        self.assertAlmostEqual(float(np.sum(band_energies)), calibrated * calibrated, delta=1e-8)

        response_profile = CalibrationProfile()
        response_profile.frequencies = np.array([20.0, 80.0, 1000.0])
        response_profile.corrections = np.array([0.0, -0.4, 0.0])
        tone_80 = (0.1 * np.sin(2 * np.pi * 80 * time_axis)).astype(np.float32)[:, None]
        calibrated_80, raw_80 = response_profile.weighted_rms_pair(tone_80, 48000, "A")
        self.assertAlmostEqual(20 * math.log10(calibrated_80 / raw_80), -0.4, delta=0.01)

    def test_all_file_formats_subtract_deviation(self):
        with tempfile.TemporaryDirectory() as temporary:
            for suffix in (".sen", ".txt", ".csv", ".cal"):
                path = Path(temporary) / f"profile{suffix}"
                header = "F [Hz]\tAmpl [dB]\tPhase [deg]\n" if suffix == ".sen" else "# frequency response\n"
                path.write_text(header + "20 0\n80 0.4\n1000 -0.4\n", encoding="utf-8")
                profile = CalibrationProfile(); profile.load(str(path))
                self.assertEqual(profile.corrections.tolist(), [-0.0, -0.4, 0.4])


if __name__ == "__main__": unittest.main()
