from __future__ import annotations

from pathlib import Path
import shutil
import time

class SystemInfo:
    """Small dependency-free Linux/Raspberry Pi status reader."""
    def __init__(self, storage):
        if isinstance(storage, dict):
            self.storage_path = storage["audio_dir"]
            self.application_paths = [storage.get(key) for key in ("audio_dir", "database", "report_dir", "calibration_dir")]
        else:
            self.storage_path = storage
            self.application_paths = [storage]
        self.last_total = None
        self.last_idle = None

    def _cpu_percent(self):
        try:
            parts = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
            values = [int(value) for value in parts]
            total, idle = sum(values), values[3] + values[4]
            if self.last_total is None:
                percent = 0.0
            else:
                total_delta, idle_delta = total - self.last_total, idle - self.last_idle
                percent = 100 * (1 - idle_delta / total_delta) if total_delta else 0.0
            self.last_total, self.last_idle = total, idle
            return round(percent, 1)
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def _temperature():
        try:
            return round(int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000, 1)
        except (OSError, ValueError):
            return None

    def read(self):
        usage = shutil.disk_usage(self.storage_path)
        application_used = self._application_size()
        return {"cpu_percent": self._cpu_percent(), "cpu_temperature": self._temperature(),
                "disk_total": usage.total, "disk_used": application_used, "disk_free": usage.free,
                "checked_at": int(time.time())}

    def _application_size(self):
        """Bytes occupied by NoiseMeter Pro database, recordings, reports and calibration data."""
        total, visited = 0, set()
        for configured in self.application_paths:
            if not configured:
                continue
            path = Path(configured)
            candidates = [path] if path.is_file() else path.rglob("*") if path.is_dir() else []
            for candidate in candidates:
                try:
                    resolved = candidate.resolve()
                    if resolved in visited or not candidate.is_file() or candidate.is_symlink():
                        continue
                    visited.add(resolved)
                    total += candidate.stat().st_size
                except OSError:
                    continue
        return total
