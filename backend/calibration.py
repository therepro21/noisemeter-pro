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
        self._gain_cache = {}
        self._spectrum_layout_cache = {}

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
                    # Every supported calibration file describes the measured
                    # microphone deviation. Compensation is measurement minus
                    # file value: +0.4 dB becomes -0.4 dB, -0.4 dB becomes +0.4 dB.
                    correction = -response
                    pairs.append((frequency, correction))
        if len(pairs) >= 2:
            pairs.sort(key=lambda item: item[0])
            unique = {}
            for frequency, correction in pairs:
                unique[frequency] = correction
            self.frequencies = np.array(list(unique.keys()), dtype=float)
            self.corrections = np.array(list(unique.values()), dtype=float)

    def weighted_rms(self, samples: np.ndarray, rate: int, weighting: str, calibrated: bool = True) -> float:
        """Frequency-weighted RMS using Parseval's theorem without an inverse FFT."""
        mono = samples[:, 0] if samples.ndim > 1 else samples
        spectrum = np.fft.rfft(mono)
        return self._spectrum_rms(spectrum, self._gain(len(mono), rate, weighting, calibrated), len(mono))

    def weighted_rms_pair(self, samples: np.ndarray, rate: int, weighting: str) -> tuple[float, float]:
        """Return calibrated and raw-microphone weighted RMS from a single FFT."""
        mono = samples[:, 0] if samples.ndim > 1 else samples
        spectrum = np.fft.rfft(mono)
        length = len(mono)
        calibrated = self._spectrum_rms(spectrum, self._gain(length, rate, weighting, True), length)
        uncalibrated = self._spectrum_rms(spectrum, self._gain(length, rate, weighting, False), length)
        return calibrated, uncalibrated

    def weighted_analysis(self, samples: np.ndarray, rate: int, weighting: str, band_count: int = 48):
        """RMS pair plus log-band energies and dominant frequency from the same FFT."""
        mono = samples[:, 0] if samples.ndim > 1 else samples
        spectrum = np.fft.rfft(mono)
        length = len(mono)
        calibrated_gain = self._gain(length, rate, weighting, True)
        calibrated = self._spectrum_rms(spectrum, calibrated_gain, length)
        uncalibrated = self._spectrum_rms(spectrum, self._gain(length, rate, weighting, False), length)
        frequencies, centers, band_indexes, valid, factors = self._spectrum_layout(length, rate, band_count)
        bin_energies = np.square(np.abs(spectrum * calibrated_gain), dtype=np.float64) * factors / (length * length)
        band_energies = np.bincount(band_indexes[valid], weights=bin_energies[valid], minlength=band_count)
        audible = (frequencies >= 20.0) & (frequencies <= min(20000.0, rate / 2))
        dominant_hz = float(frequencies[np.argmax(np.where(audible, bin_energies, -1.0))]) if np.any(audible) else None
        return calibrated, uncalibrated, centers, band_energies, dominant_hz

    def _spectrum_layout(self, length: int, rate: int, band_count: int):
        key = (length, rate, band_count)
        cached = self._spectrum_layout_cache.get(key)
        if cached is not None:
            return cached
        frequencies = np.fft.rfftfreq(length, d=1 / rate)
        upper = min(20000.0, rate / 2)
        edges = np.geomspace(20.0, upper, band_count + 1)
        centers = np.sqrt(edges[:-1] * edges[1:])
        band_indexes = np.searchsorted(edges, frequencies, side="right") - 1
        valid = (band_indexes >= 0) & (band_indexes < band_count)
        factors = np.full(len(frequencies), 2.0)
        factors[0] = 1.0
        if length % 2 == 0:
            factors[-1] = 1.0
        cached = (frequencies, centers, band_indexes, valid, factors)
        self._spectrum_layout_cache[key] = cached
        return cached

    def _gain(self, length: int, rate: int, weighting: str, calibrated: bool) -> np.ndarray:
        key = (length, rate, weighting.upper(), calibrated)
        cached = self._gain_cache.get(key)
        if cached is not None:
            return cached
        frequencies = np.fft.rfftfreq(length, d=1 / rate)
        correction = 0.0
        if calibrated and self.loaded:
            # SEN specifies logarithmic interpolation between its frequency points.
            safe_frequencies = np.maximum(frequencies, self.frequencies[0])
            correction = np.interp(
                np.log10(safe_frequencies), np.log10(self.frequencies), self.corrections,
                left=self.corrections[0], right=self.corrections[-1],
            )
        gain = np.power(10.0, (correction + self._frequency_weight(frequencies, weighting)) / 20.0)
        self._gain_cache[key] = gain
        return gain

    @staticmethod
    def _spectrum_rms(spectrum: np.ndarray, gain: np.ndarray, length: int) -> float:
        power = np.square(np.abs(spectrum * gain), dtype=np.float64)
        if len(power) == 1:
            total = power[0]
        elif length % 2 == 0:
            total = power[0] + power[-1] + 2.0 * np.sum(power[1:-1])
        else:
            total = power[0] + 2.0 * np.sum(power[1:])
        return float(np.sqrt(total) / length)

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
