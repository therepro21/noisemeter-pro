from __future__ import annotations

from datetime import date, timedelta
import json
import logging
import ssl
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
        self.connected = False

    def start(self):
        if not self.config.get("enabled", False):
            return
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client(client_id=self.config.get("client_id", "noisemeter-pro"))
            if self.config.get("username"):
                self.client.username_pw_set(self.config["username"], self.config.get("password", ""))
            self.client.on_connect = self._connected
            self.client.on_disconnect = self._disconnected
            availability = f"{self.topic}/availability"
            qos = int(self.config.get("qos", 0))
            self.client.will_set(availability, "offline", qos=qos, retain=True)
            if self.config.get("tls_enabled", False):
                ca_file = self.config.get("tls_ca_file") or None
                self.client.tls_set(ca_certs=ca_file, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            self.client.reconnect_delay_set(min_delay=1, max_delay=120)
            self.client.connect_async(self.config["host"], int(self.config.get("port", 1883)), keepalive=int(self.config.get("keepalive", 60)))
            self.client.loop_start()
        except Exception:
            LOG.exception("MQTT could not be started; monitoring continues without MQTT")
            self.client = None

    def stop(self):
        if self.client:
            if self.connected:
                message = self.client.publish(f"{self.topic}/availability", "offline", qos=int(self.config.get("qos", 0)), retain=True)
                try: message.wait_for_publish(timeout=2)
                except (RuntimeError, ValueError): pass
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    @property
    def topic(self): return self.config.get("base_topic", "noisemeter").strip("/")

    def _connected(self, client, userdata, flags, reason_code, properties=None):
        result_code = getattr(reason_code, "value", reason_code)
        if result_code != 0:
            LOG.error("MQTT connection rejected: %s", reason_code)
            self.connected = False
            return
        self.connected = True
        LOG.info("Connected to MQTT broker")
        device = {"identifiers": ["noisemeter_pro"], "name": "NoiseMeter Pro", "manufacturer": "therepro21", "model": "NoiseMeter Pro"}
        sensors = [
            ("current_db", "Aktueller Schallpegel", "dB", "measurement"),
            ("current_leq_db", "LAeq 60 Sekunden", "dB", "measurement"),
            ("daily_peak_db", "Tageshöchstwert", "dB", "measurement"),
            ("weekly_peak_db", "Wochenhöchstwert", "dB", "measurement"),
            ("monthly_peak_db", "Monatshöchstwert", "dB", "measurement"),
        ]
        entity_ids = {
            "current_db": "sensor.noisemeter_pro_schallpegel",
            "current_leq_db": "sensor.noisemeter_pro_laeq_60_sekunden",
            "daily_peak_db": "sensor.noisemeter_pro_tageshochstwert",
            "weekly_peak_db": "sensor.noisemeter_pro_wochenhochstwert",
            "monthly_peak_db": "sensor.noisemeter_pro_monatshochstwert",
        }
        prefix = self.config.get("discovery_prefix", "homeassistant").strip("/")
        qos, retain = int(self.config.get("qos", 0)), bool(self.config.get("retain", True))
        availability = f"{self.topic}/availability"
        client.publish(availability, "online", qos=qos, retain=True)
        for object_id, name, unit, state_class in sensors:
            payload = {"name": name, "default_entity_id": entity_ids[object_id], "unique_id": f"noisemeter_pro_{object_id}", "state_topic": f"{self.topic}/{object_id}/state", "availability_topic": availability, "payload_available": "online", "payload_not_available": "offline", "unit_of_measurement": unit, "state_class": state_class, "device_class": "sound_pressure", "device": device}
            client.publish(f"{prefix}/sensor/noisemeter_pro/{object_id}/config", json.dumps(payload), qos=qos, retain=True)

    def _disconnected(self, client, userdata, *args):
        self.connected = False
        LOG.warning("Disconnected from MQTT broker: %s", args[-1] if args else "unknown")

    def publish_measurement(self, timestamp: str, db_value: float, leq_db: float):
        if not self.client:
            return
        qos, retain = int(self.config.get("qos", 0)), bool(self.config.get("retain", True))
        now = time.monotonic()
        if now - self.last_current >= 5:
            self.client.publish(f"{self.topic}/current_db/state", f"{db_value:.1f}", qos=qos, retain=retain)
            self.client.publish(f"{self.topic}/current_leq_db/state", f"{leq_db:.1f}", qos=qos, retain=retain)
            self.last_current = now
        if now - self.last_peaks >= 60:
            today = date.fromisoformat(timestamp[:10])
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)
            peaks = {"daily_peak_db": self.database.level_peak(today.isoformat(), (today + timedelta(days=1)).isoformat()),
                     "weekly_peak_db": self.database.level_peak(week_start.isoformat(), (week_start + timedelta(days=7)).isoformat()),
                     "monthly_peak_db": self.database.level_peak(month_start.isoformat(), (month_start.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat())}
            for name, value in peaks.items(): self.client.publish(f"{self.topic}/{name}/state", f"{value:.1f}", qos=qos, retain=retain)
            self.last_peaks = now
