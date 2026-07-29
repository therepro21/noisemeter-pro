from __future__ import annotations

from pathlib import Path
import shutil
import time

class SystemInfo:
    """Small dependency-free Linux/Raspberry Pi status reader."""
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
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
        return {"cpu_percent": self._cpu_percent(), "cpu_temperature": self._temperature(),
                "disk_total": usage.total, "disk_used": usage.used, "disk_free": usage.free,
                "checked_at": int(time.time())}
