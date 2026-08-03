from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
import logging
import queue
import re
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd

from .calibration import CalibrationProfile
from .database import Database

LOG = logging.getLogger(__name__)

class NoiseMonitor:
    def __init__(self, config: dict, database: Database):
        self.config, self.database = config, database
        audio = config["audio"]
        self.rate, self.channels = int(audio["sample_rate"]), int(audio["channels"])
        self.blocksize = max(1, int(self.rate * float(audio["block_seconds"])))
        self.pre_blocks = max(1, round(float(audio["pre_roll_seconds"]) * self.rate / self.blocksize))
        self.post_blocks = max(1, round(float(audio["post_roll_seconds"]) * self.rate / self.blocksize))
        self.ring = deque(maxlen=self.pre_blocks)
        self.energy_ring = deque(maxlen=self.pre_blocks)
        self.spectrum_energy_ring = deque(maxlen=self.pre_blocks)
        self.samples = queue.Queue(maxsize=64)
        self.current_db, self.last_update, self.running = 0.0, None, False
        self.current_uncalibrated_db, self.current_leq_db = 0.0, None
        self.current_spectrum, self.spectrum_sequence = None, 0
        self.device_available, self.device_error = False, None
        self.lock = threading.Lock()
        self.thread = None
        self.recording = None
        self.last_measurement = 0.0
        self.on_measurement = None
        self.last_retention_check = None
        self.smoothed_energy = None
        self.smoothed_uncalibrated_energy = None
        self.leq_window = deque(maxlen=max(1, round(60 / float(audio["block_seconds"]))))
        self.measurement_energy, self.measurement_blocks = 0.0, 0
        self.measurement_buffer, self.measurement_buffer_minute = [], None
        self.measurement_buffer_lock = threading.RLock()
        self.input_gain = {"percent": None, "channels": [], "enforced": False, "control": None, "card": None, "error": None}
        self.calibration = CalibrationProfile()
        self.reload_calibration()

    def reload_calibration(self):
        audio = self.config["audio"]
        angle = str(audio.get("calibration_angle", "0"))
        filename = (audio.get("calibration_files") or {}).get(angle) or audio.get("calibration_file")
        audio["calibration_file"] = filename
        path = Path(self.config["storage"]["calibration_dir"]) / filename if filename else None
        # Build completely before swapping so the audio thread never sees a half-loaded profile.
        profile = CalibrationProfile()
        profile.load(str(path) if path else None)
        self.calibration = profile
        self.reset_measurement_response()
        LOG.info("Loaded calibration profile: %s", filename or "none")

    def reset_measurement_response(self):
        self.smoothed_energy = None
        self.smoothed_uncalibrated_energy = None
        self.leq_window.clear()
        self.measurement_energy, self.measurement_blocks = 0.0, 0
        self.current_spectrum = None

    def start(self):
        if self.running: return
        while not self.samples.empty():
            try: self.samples.get_nowait()
            except queue.Empty: break
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="noise-monitor")
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=3)
        self.flush_measurements()

    def flush_measurements(self):
        """Write buffered second values as one transaction; safe before deletes and shutdown."""
        with self.measurement_buffer_lock:
            if not self.measurement_buffer:
                return
            buffered = list(self.measurement_buffer)
            try:
                self.database.add_measurements(buffered)
            except Exception:
                LOG.exception("Could not flush %d buffered measurements", len(buffered))
                return
            del self.measurement_buffer[:len(buffered)]

    def _buffer_measurement(self, timestamp: str, db_value: float, leq_db: float):
        with self.measurement_buffer_lock:
            minute = timestamp[:16]
            if self.measurement_buffer and minute != self.measurement_buffer_minute:
                self.flush_measurements()
            self.measurement_buffer.append((timestamp, db_value, leq_db))
            self.measurement_buffer_minute = minute

    def status(self):
        with self.lock:
            return {"db": round(self.current_db, 1) if self.device_available else None,
                    "uncalibrated_db": round(self.current_uncalibrated_db, 1) if self.device_available else None,
                    "leq_db": round(self.current_leq_db, 1) if self.device_available and self.current_leq_db is not None else None,
                    "calibration": self.calibration.metadata(), "input_gain": self.input_gain,
                    "spectrum": self.current_spectrum,
                    "available": self.device_available, "error": self.device_error,
                    "updated_at": self.last_update,
                    "recording": self.recording is not None, "device": self.config["audio"]["device"]}

    def input_devices(self):
        """Return only usable capture devices for the device picker."""
        devices = []
        for index, device in enumerate(sd.query_devices()):
            if device["max_input_channels"] > 0:
                devices.append({"id": index, "name": device["name"],
                                "channels": int(device["max_input_channels"])})
        return devices

    def select_device(self, device):
        """Switch the input stream without requiring a service restart."""
        self.stop()
        self.config["audio"]["device"] = device
        self.start()

    def _callback(self, indata, frames, timing, status):
        if status: LOG.warning("Audio status: %s", status)
        try: self.samples.put_nowait(indata.copy())
        except queue.Full: LOG.warning("Audio queue full; dropping a block")

    def _levels(self, block):
        weighting = self.config["audio"].get("weighting", "A")
        profile = self.calibration
        rms, uncalibrated_rms, frequencies, band_energies, dominant_hz = profile.weighted_analysis(block, self.rate, weighting)
        energy, uncalibrated_energy = rms * rms, uncalibrated_rms * uncalibrated_rms
        time_constant = 0.125 if self.config["audio"].get("time_weighting", "fast") == "fast" else 1.0
        alpha = np.exp(-(len(block) / self.rate) / time_constant)
        self.smoothed_energy = energy if self.smoothed_energy is None else alpha * self.smoothed_energy + (1 - alpha) * energy
        self.smoothed_uncalibrated_energy = uncalibrated_energy if self.smoothed_uncalibrated_energy is None else alpha * self.smoothed_uncalibrated_energy + (1 - alpha) * uncalibrated_energy
        base = profile.spl_offset(float(self.config["audio"]["calibration_offset_db"]))
        manual = float(self.config["audio"].get("manual_calibration_db", 0))
        db_value = base + manual + 10 * np.log10(max(self.smoothed_energy, 1e-24))
        # Same absolute sensitivity/manual basis; only the SEN frequency response is omitted.
        uncalibrated_db = base + manual + 10 * np.log10(max(self.smoothed_uncalibrated_energy, 1e-24))
        block_leq = base + manual + 10 * np.log10(max(energy, 1e-24))
        spectrum = {
            "frequencies": [round(float(value), 1) for value in frequencies],
            "levels_db": [round(base + manual + 10 * np.log10(max(float(value), 1e-24)), 1) for value in band_energies],
            "dominant_hz": round(dominant_hz, 1) if dominant_hz is not None else None,
            "interval_seconds": round(len(block) / self.rate, 3),
        }
        return db_value, uncalibrated_db, block_leq, spectrum, frequencies, band_energies

    def _active_period(self, now):
        current = now.strftime("%H:%M")
        for period in self.config.get("periods", []):
            if not period.get("enabled", True): continue
            start, end = period["start"], period["end"]
            active = start <= current < end if start < end else (current >= start or current < end)
            if active: return period
        return None

    def _run(self):
        audio = self.config["audio"]
        try:
            self.input_gain = self._set_input_gain_100()
            with sd.InputStream(device=audio.get("device"), samplerate=self.rate, channels=self.channels,
                                blocksize=self.blocksize, dtype="float32", callback=self._callback):
                with self.lock:
                    self.device_available, self.device_error = True, None
                LOG.info("Audio monitor started")
                while self.running:
                    try: block = self.samples.get(timeout=1)
                    except queue.Empty: continue
                    self._process(block)
        except Exception as error:
            with self.lock:
                self.device_available, self.device_error = False, str(error)
                self.current_db, self.last_update, self.recording = 0.0, None, None
            LOG.exception("Audio monitor stopped due to input error")
            self.running = False
        finally:
            self.flush_measurements()

    def _process(self, block):
        now = datetime.now()
        if self.last_retention_check != now.date():
            self._apply_retention(now)
            self.last_retention_check = now.date()
        db_value, uncalibrated_db, block_leq, spectrum, spectrum_frequencies, spectrum_energies = self._levels(block)
        block_energy = 10 ** (block_leq / 10)
        self.leq_window.append(block_energy)
        self.measurement_energy += block_energy
        self.measurement_blocks += 1
        live_leq = 10 * np.log10(sum(self.leq_window) / len(self.leq_window))
        with self.lock:
            self.spectrum_sequence += 1
            spectrum["sequence"] = self.spectrum_sequence
            self.current_db, self.current_uncalibrated_db, self.current_leq_db = db_value, uncalibrated_db, live_leq
            self.current_spectrum = spectrum
            self.last_update = now.isoformat(timespec="seconds")
        self.ring.append(block)
        self.energy_ring.append(block_energy)
        self.spectrum_energy_ring.append(spectrum_energies)
        if time.monotonic() - self.last_measurement >= 1:
            interval_leq = 10 * np.log10(self.measurement_energy / max(self.measurement_blocks, 1))
            timestamp = now.isoformat(timespec="seconds")
            self._buffer_measurement(timestamp, db_value, interval_leq)
            if self.on_measurement:
                self.on_measurement(timestamp, db_value, interval_leq)
            self.measurement_energy, self.measurement_blocks = 0.0, 0
            self.last_measurement = time.monotonic()
        if self.recording:
            self.recording["blocks"].append(block)
            self.recording["peak"] = max(self.recording["peak"], db_value)
            self.recording["energy"] += block_energy
            self.recording["energy_blocks"] += 1
            self.recording["spectrum_energy"] += spectrum_energies
            self.recording["remaining"] -= 1
            if self.recording["remaining"] <= 0: self._finish_recording()
            return
        period = self._active_period(now)
        if period and db_value >= float(period["threshold_db"]):
            pre_energy = sum(self.energy_ring)
            pre_spectrum_energy = np.sum(self.spectrum_energy_ring, axis=0)
            self.recording = {"blocks": list(self.ring), "remaining": self.post_blocks, "peak": db_value,
                              "energy": pre_energy, "energy_blocks": len(self.energy_ring),
                              "spectrum_energy": pre_spectrum_energy, "spectrum_frequencies": spectrum_frequencies,
                              "started": now, "period": period}
            LOG.info("Event started: %.1f dB (%s)", db_value, period["name"])

    def _finish_recording(self):
        record = self.recording
        self.recording = None
        started = record["started"]
        stamp = started.strftime("%Y-%m-%d_%H-%M-%S")
        safe_db = f"{record['peak']:.1f}dB".replace(".", ",")
        relative = Path(started.strftime("%Y")) / started.strftime("%m") / f"{stamp}_{safe_db}.mp3"
        target = Path(self.config["storage"]["audio_dir"]) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = np.concatenate(record["blocks"], axis=0)
        try:
            bitrate = int(self.config["audio"].get("mp3_bitrate_kbps", 128))
            command = ["ffmpeg", "-y", "-f", "f32le", "-ar", str(self.rate), "-ac", str(self.channels), "-i", "pipe:0", "-codec:a", "libmp3lame", "-b:a", f"{bitrate}k", str(target)]
            subprocess.run(command, input=raw.astype("float32").tobytes(), check=True, capture_output=True, timeout=30)
            self.database.add_event({"occurred_at": started.isoformat(timespec="seconds"), "peak_db": record["peak"],
                "threshold_db": float(record["period"]["threshold_db"]), "period_name": record["period"]["name"],
                "filename": relative.as_posix(), "duration_seconds": round(len(raw) / self.rate, 2),
                "leq_db": 10 * np.log10(record["energy"] / max(record["energy_blocks"], 1)),
                "dominant_frequency_hz": float(record["spectrum_frequencies"][np.argmax(record["spectrum_energy"])])})
            LOG.info("Event saved: %s", target)
        except Exception:
            LOG.exception("Could not encode event audio")

    def _apply_retention(self, now):
        days = int(self.config["storage"].get("retention_days", 360))
        if days <= 0:
            return
        cutoff = (now - timedelta(days=days)).isoformat(timespec="seconds")
        root = Path(self.config["storage"]["audio_dir"]).resolve()
        for filename in self.database.remove_events_before(cutoff):
            target = (root / filename).resolve()
            if target.is_relative_to(root):
                try: target.unlink(missing_ok=True)
                except OSError: LOG.warning("Could not remove expired audio: %s", target)
        LOG.info("Applied %d-day audio retention", days)

    def _set_input_gain_100(self):
        """Best-effort ALSA capture-gain enforcement for calibrated USB microphones."""
        result = {"percent": None, "channels": [], "enforced": False, "control": None, "card": None, "error": None}
        try:
            cards = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=5, check=True).stdout
            card_ids = re.findall(r"card\s+(\d+):[^\n]*USB", cards, re.I) or re.findall(r"card\s+(\d+):", cards, re.I)
            for card in card_ids:
                controls = subprocess.run(["amixer", "-c", card, "scontrols"], capture_output=True, text=True, timeout=5, check=True).stdout
                names = re.findall(r"Simple mixer control '([^']+)'", controls)
                for control in sorted(names, key=lambda name: 0 if re.search(r"capture|mic|input", name, re.I) else 1):
                    changed = subprocess.run(["amixer", "-c", card, "sset", control, "100%", "cap", "unmute"], capture_output=True, text=True, timeout=5)
                    if changed.returncode != 0:
                        continue
                    state = subprocess.run(["amixer", "-c", card, "sget", control], capture_output=True, text=True, timeout=5, check=True).stdout
                    percentages = [int(value) for value in re.findall(r"\[(\d+)%\]", state)]
                    if percentages:
                        result.update(percent=min(percentages), channels=percentages, enforced=all(value == 100 for value in percentages), control=control, card=int(card))
                        return result
            result["error"] = "Kein regelbarer ALSA-Aufnahmepegel gefunden"
        except Exception as error:
            result["error"] = str(error)
        return result
