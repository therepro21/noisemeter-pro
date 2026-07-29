from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
import logging
import queue
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd

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
        self.samples = queue.Queue(maxsize=64)
        self.current_db, self.last_update, self.running = 0.0, None, False
        self.lock = threading.Lock()
        self.thread = None
        self.recording = None
        self.last_measurement = 0.0

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

    def status(self):
        with self.lock:
            return {"db": round(self.current_db, 1), "updated_at": self.last_update,
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

    def _db(self, block):
        rms = float(np.sqrt(np.mean(np.square(block.astype(np.float64)))))
        return float(self.config["audio"]["calibration_offset_db"]) + 20 * np.log10(max(rms, 1e-12))

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
            with sd.InputStream(device=audio.get("device"), samplerate=self.rate, channels=self.channels,
                                blocksize=self.blocksize, dtype="float32", callback=self._callback):
                LOG.info("Audio monitor started")
                while self.running:
                    try: block = self.samples.get(timeout=1)
                    except queue.Empty: continue
                    self._process(block)
        except Exception:
            LOG.exception("Audio monitor stopped due to input error")
            self.running = False

    def _process(self, block):
        now = datetime.now()
        db_value = self._db(block)
        with self.lock:
            self.current_db, self.last_update = db_value, now.isoformat(timespec="seconds")
        self.ring.append(block)
        if time.monotonic() - self.last_measurement >= 1:
            self.database.add_measurement(now.isoformat(timespec="seconds"), db_value)
            self.last_measurement = time.monotonic()
        if self.recording:
            self.recording["blocks"].append(block)
            self.recording["peak"] = max(self.recording["peak"], db_value)
            self.recording["remaining"] -= 1
            if self.recording["remaining"] <= 0: self._finish_recording()
            return
        period = self._active_period(now)
        if period and db_value >= float(period["threshold_db"]):
            self.recording = {"blocks": list(self.ring), "remaining": self.post_blocks, "peak": db_value,
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
            command = ["ffmpeg", "-y", "-f", "f32le", "-ar", str(self.rate), "-ac", str(self.channels), "-i", "pipe:0", "-codec:a", "libmp3lame", "-q:a", "3", str(target)]
            subprocess.run(command, input=raw.astype("float32").tobytes(), check=True, capture_output=True, timeout=30)
            self.database.add_event({"occurred_at": started.isoformat(timespec="seconds"), "peak_db": record["peak"],
                "threshold_db": float(record["period"]["threshold_db"]), "period_name": record["period"]["name"],
                "filename": relative.as_posix(), "duration_seconds": round(len(raw) / self.rate, 2)})
            LOG.info("Event saved: %s", target)
        except Exception:
            LOG.exception("Could not encode event audio")
