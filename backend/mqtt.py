from __future__ import annotations

from datetime import date, timedelta
import json
import logging
import time

from .database import Database

LOG = logging.getLogger(__name__)

class MqttPublisher:
    """Publishes level states and Home Assistant MQTT Discovery metadata."""
    def __init__(self, config: dict, database: Database):
        self.config, self.database = config, database
        self.client = None
        self.last_current = 0.0
        self.last_peaks = 0.0

    def start(self):
        if not self.config.get("enabled", False):
            return
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client(client_id="noisemeter-pro")
            if self.config.get("username"):
                self.client.username_pw_set(self.config["username"], self.config.get("password", ""))
            self.client.on_connect = self._connected
            self.client.connect_async(self.config["host"], int(self.config.get("port", 1883)), keepalive=60)
            self.client.loop_start()
        except Exception:
            LOG.exception("MQTT could not be started; monitoring continues without MQTT")
            self.client = None

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    @property
    def topic(self): return self.config.get("base_topic", "noisemeter").strip("/")

    def _connected(self, client, userdata, flags, reason_code, properties=None):
        LOG.info("Connected to MQTT broker")
        device = {"identifiers": ["noisemeter_pro"], "name": "NoiseMeter Pro", "manufacturer": "therepro21", "model": "NoiseMeter Pro"}
        sensors = [
            ("current_db", "Aktueller Schallpegel", "dB", "measurement"),
            ("daily_peak_db", "Tageshöchstwert", "dB", "measurement"),
            ("weekly_peak_db", "Wochenhöchstwert", "dB", "measurement"),
            ("monthly_peak_db", "Monatshöchstwert", "dB", "measurement"),
        ]
        prefix = self.config.get("discovery_prefix", "homeassistant").strip("/")
        for object_id, name, unit, state_class in sensors:
            payload = {"name": name, "unique_id": f"noisemeter_pro_{object_id}", "state_topic": f"{self.topic}/{object_id}/state", "unit_of_measurement": unit, "state_class": state_class, "device_class": "sound_pressure", "device": device}
            client.publish(f"{prefix}/sensor/noisemeter_pro/{object_id}/config", json.dumps(payload), retain=True)

    def publish_measurement(self, timestamp: str, db_value: float):
        if not self.client:
            return
        now = time.monotonic()
        if now - self.last_current >= 5:
            self.client.publish(f"{self.topic}/current_db/state", f"{db_value:.1f}", retain=True)
            self.last_current = now
        if now - self.last_peaks >= 60:
            today = date.fromisoformat(timestamp[:10])
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)
            peaks = {"daily_peak_db": self.database.level_peak(today.isoformat(), (today + timedelta(days=1)).isoformat()),
                     "weekly_peak_db": self.database.level_peak(week_start.isoformat(), (week_start + timedelta(days=7)).isoformat()),
                     "monthly_peak_db": self.database.level_peak(month_start.isoformat(), (month_start.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat())}
            for name, value in peaks.items(): self.client.publish(f"{self.topic}/{name}/state", f"{value:.1f}", retain=True)
            self.last_peaks = now
