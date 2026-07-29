from __future__ import annotations

from pathlib import Path
import copy
import yaml

DEFAULT_CONFIG = {
    "audio": {"device": None, "sample_rate": 48000, "channels": 1, "mp3_bitrate_kbps": 128,
              "calibration_file": None, "manual_calibration_db": 0.0,
              "weighting": "A", "time_weighting": "fast",
              "block_seconds": 0.25, "calibration_offset_db": 94.0,
              "pre_roll_seconds": 3, "post_roll_seconds": 5},
    "storage": {"audio_dir": "/var/lib/noisemeter/audio", "calibration_dir": "/var/lib/noisemeter/calibration", "retention_days": 360,
                "database": "/var/lib/noisemeter/noisemeter.sqlite3",
                "report_dir": "/var/lib/noisemeter/reports"},
    "web": {"host": "0.0.0.0", "port": 8080, "secret_key": "change-me"},
    "mqtt": {"enabled": False, "host": "localhost", "port": 1883,
             "username": "", "password": "", "discovery_prefix": "homeassistant",
             "base_topic": "noisemeter"},
    "periods": []
}

def deep_update(base, update):
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base

def load_config(path: str) -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    source = Path(path)
    if source.exists():
        with source.open(encoding="utf-8") as handle:
            deep_update(config, yaml.safe_load(handle) or {})
    return config

def save_config(path: str, config: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)
