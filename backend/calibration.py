from __future__ import annotations

from pathlib import Path
import re

import numpy as np


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"


class CalibrationProfile:
    """HiFi-Selbstbau/JustOct SEN and common frequency-response profiles."""
    def __init__(self):
        self.clear()

    def clear(self):
        self.frequencies = np.array([])
        self.corrections = np.array([])
        self.sensitivity_mv_pa = None
        self.db_offset = None
        self.title = ""
        self.path = None

    @property
    def loaded(self):
        return len(self.frequencies) >= 2

    def load(self, path: str | None):
        self.clear()
        source = Path(path) if path else None
        if not source or not source.is_file():
            return
        text = source.read_text(encoding="utf-8", errors="ignore")
        self.path = str(source)
        sen_format = source.suffix.lower() == ".sen" or "Sensitivity at 1000 Hz" in text
        pairs = []
        in_frequency_table = not sen_format
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            values = re.findall(NUMBER, line.replace(",", "."))
            if lower.startswith("sensitivity") and values:
                self.sensitivity_mv_pa = float(values[-1])
                continue
            if lower.startswith("db-offset") and values:
                self.db_offset = float(values[-1])
                continue
            if lower.startswith("title"):
                self.title = re.sub(r"^title\s*", "", line, flags=re.I).strip("\t :")
                continue
            if lower.startswith("f [hz]") or ("ampl" in lower and "phase" in lower):
                in_frequency_table = True
                continue
            if in_frequency_table and len(values) >= 2:
                frequency, response = float(values[0]), float(values[1])
                if 1 <= frequency <= 96000 and -60 <= response <= 60:
                    # SEN stores microphone response relative to 1 kHz; compensation is its inverse.
                    correction = -response if sen_format else response
                    pairs.append((frequency, correction))
        if len(pairs) >= 2:
            pairs.sort(key=lambda item: item[0])
            unique = {}
            for frequency, correction in pairs:
                unique[frequency] = correction
            self.frequencies = np.array(list(unique.keys()), dtype=float)
            self.corrections = np.array(list(unique.values()), dtype=float)

    def weighted_rms(self, samples: np.ndarray, rate: int, weighting: str, calibrated: bool = True) -> float:
        mono = samples[:, 0] if samples.ndim > 1 else samples
        spectrum = np.fft.rfft(mono)
        frequencies = np.fft.rfftfreq(len(mono), d=1 / rate)
        correction = np.interp(frequencies, self.frequencies, self.corrections,
                               left=self.corrections[0], right=self.corrections[-1]) if calibrated and self.loaded else 0
        frequency_weight = self._frequency_weight(frequencies, weighting)
        corrected = np.fft.irfft(spectrum * np.power(10, (correction + frequency_weight) / 20), n=len(mono))
        return float(np.sqrt(np.mean(np.square(corrected.astype(np.float64)))))

    def metadata(self):
        return {"loaded": self.loaded, "filename": Path(self.path).name if self.path else None,
                "title": self.title, "sensitivity_mv_pa": self.sensitivity_mv_pa,
                "db_offset": self.db_offset, "points": len(self.frequencies)}

    def spl_offset(self, fallback: float) -> float:
        """Convert normalized full-scale RMS to SPL using SEN sensitivity (1 FS = 1000 mV)."""
        if self.loaded and self.sensitivity_mv_pa and self.sensitivity_mv_pa > 0:
            reference = self.db_offset if self.db_offset is not None else 94.0
            return reference + 20 * np.log10(1000.0 / self.sensitivity_mv_pa)
        return float(fallback)

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
