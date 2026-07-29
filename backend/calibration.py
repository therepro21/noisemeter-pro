from __future__ import annotations

from pathlib import Path
import re

import numpy as np

class CalibrationProfile:
    """Frequency response corrections from common UMIK/MM-2 text files."""
    def __init__(self):
        self.frequencies = np.array([])
        self.corrections = np.array([])

    def load(self, path: str | None):
        self.frequencies = np.array([]); self.corrections = np.array([])
        if not path or not Path(path).is_file(): return
        pairs = []
        for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
            values = re.findall(r"[-+]?\d*\.?\d+", line.replace(",", "."))
            if len(values) >= 2:
                frequency, correction = float(values[0]), float(values[1])
                if frequency > 0 and frequency <= 96000 and -60 <= correction <= 60: pairs.append((frequency, correction))
        if len(pairs) >= 2:
            pairs.sort()
            self.frequencies, self.corrections = np.array(pairs).T

    def weighted_rms(self, samples: np.ndarray, rate: int, weighting: str) -> float:
        mono = samples[:, 0] if samples.ndim > 1 else samples
        spectrum = np.fft.rfft(mono)
        frequencies = np.fft.rfftfreq(len(mono), d=1 / rate)
        correction = np.interp(frequencies, self.frequencies, self.corrections, left=self.corrections[0], right=self.corrections[-1]) if len(self.frequencies) else 0
        frequency_weight = self._frequency_weight(frequencies, weighting)
        corrected = np.fft.irfft(spectrum * np.power(10, (correction + frequency_weight) / 20), n=len(mono))
        return float(np.sqrt(np.mean(np.square(corrected.astype(np.float64)))))

    @staticmethod
    def _frequency_weight(frequency: np.ndarray, weighting: str) -> np.ndarray:
        """IEC 61672 A/C frequency response in dB (DC is discarded)."""
        f2 = np.square(frequency)
        with np.errstate(divide="ignore", invalid="ignore"):
            if weighting.upper() == "C":
                response = 20 * np.log10((12194**2 * f2) / ((f2 + 20.6**2) * (f2 + 12194**2))) + 0.06
            else:
                response = 20 * np.log10((12194**2 * np.square(f2)) / ((f2 + 20.6**2) * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * (f2 + 12194**2))) + 2.0
        return np.where(np.isfinite(response), response, -120.0)
