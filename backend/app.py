from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import logging
import zipfile
from io import BytesIO

from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from .config import load_config, save_config
from .database import Database
from .monitor import NoiseMonitor
from .mqtt import MqttPublisher
from .reports import create_report
from .system_info import SystemInfo

def period_range(kind: str, value: str):
    if kind == "day":
        start = datetime.strptime(value, "%Y-%m-%d").date()
        end = start + timedelta(days=1)
    elif kind == "week":
        year, week = map(int, value.split("-W")); start = date.fromisocalendar(year, week, 1); end = start + timedelta(days=7)
    elif kind == "month":
        start = datetime.strptime(value + "-01", "%Y-%m-%d").date(); end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    elif kind == "year":
        start = datetime.strptime(value + "-01-01", "%Y-%m-%d").date(); end = start.replace(year=start.year + 1)
    else: raise ValueError("invalid period")
    return start.isoformat(), end.isoformat()

def create_app(config_path: str):
    config = load_config(config_path)
    app = Flask(__name__); app.config["SECRET_KEY"] = config["web"]["secret_key"]
    database = Database(config["storage"]["database"]); monitor = NoiseMonitor(config, database)
    mqtt = MqttPublisher(config["mqtt"], database); monitor.on_measurement = mqtt.publish_measurement
    mqtt.start()
    app.extensions["mqtt"] = mqtt
    system_info = SystemInfo(config["storage"]["audio_dir"])
    app.extensions["monitor"], app.extensions["database"], app.extensions["nm_config"], app.extensions["config_path"] = monitor, database, config, config_path

    @app.get("/")
    def index(): return render_template("index.html")
    @app.get("/api/status")
    def status(): return jsonify(monitor.status())
    @app.get("/api/system")
    def system_status(): return jsonify(system_info.read())
    @app.get("/api/event-counts")
    def event_counts():
        today = date.today(); week = today - timedelta(days=today.weekday()); month = today.replace(day=1); year = today.replace(month=1, day=1)
        ranges = {"day": (today, today + timedelta(days=1)), "week": (week, week + timedelta(days=7)), "month": (month, (month.replace(day=28) + timedelta(days=4)).replace(day=1)), "year": (year, year.replace(year=year.year + 1))}
        return jsonify({name: database.summary(start.isoformat(), end.isoformat())["event_count"] for name, (start, end) in ranges.items()})
    @app.get("/api/events")
    def events():
        kind, value = request.args.get("kind", "day"), request.args.get("date", date.today().isoformat())
        try: start, end = period_range(kind, value)
        except ValueError: abort(400, "Ungültiger Zeitraum")
        items = database.events(start, end); periods = {p["name"]: p for p in config["periods"]}
        for item in items:
            period = periods.get(item["period_name"], {})
            item["warning_db"] = float(period.get("warning_db", item["threshold_db"] + 10))
            item["severe_db"] = float(period.get("severe_db", item["threshold_db"] + 15))
        return jsonify({"start": start, "end": end, "summary": database.summary(start, end), "events": items})
    @app.get("/api/history")
    def history():
        value = request.args.get("date", date.today().isoformat())
        try: start, end = period_range("day", value)
        except ValueError: abort(400, "Ungültiges Datum")
        return jsonify({"date": value, "points": database.day_history(start, end)})
    @app.get("/api/breakdown")
    def breakdown():
        kind, value = request.args.get("kind", "day"), request.args.get("date", date.today().isoformat())
        try: start, end = period_range(kind, value)
        except ValueError: abort(400)
        return jsonify({"items": database.level_breakdown(kind, start, end)})
    @app.get("/audio/<path:filename>")
    def audio(filename): return send_from_directory(config["storage"]["audio_dir"], filename, conditional=True)
    @app.get("/api/config")
    def get_config(): return jsonify({"site_name": config["site_name"], "site_data": config.get("site_data", {}), "web": {"refresh_seconds": config["web"].get("refresh_seconds", 5)}, "periods": config["periods"], "audio": {k: config["audio"][k] for k in ("calibration_offset_db", "device", "mp3_bitrate_kbps", "calibration_file", "manual_calibration_db", "weighting", "time_weighting", "pre_roll_seconds", "post_roll_seconds")}, "storage": {"retention_days": config["storage"]["retention_days"]}, "mqtt": {"enabled": config["mqtt"]["enabled"], "host": config["mqtt"]["host"], "port": config["mqtt"]["port"], "username": config["mqtt"]["username"], "discovery_prefix": config["mqtt"]["discovery_prefix"], "base_topic": config["mqtt"]["base_topic"], "has_password": bool(config["mqtt"].get("password"))}})
    @app.get("/api/audio-devices")
    def audio_devices():
        try:
            return jsonify({"devices": monitor.input_devices(), "selected": config["audio"].get("device")})
        except Exception as error:
            logging.exception("Could not list audio devices")
            return jsonify({"error": str(error), "devices": [], "selected": config["audio"].get("device")}), 500
    @app.put("/api/audio-device")
    def set_audio_device():
        payload = request.get_json(force=True) or {}
        device = payload.get("device")
        if device is not None:
            try: device = int(device)
            except (TypeError, ValueError): abort(400, "Ungültiges Mikrofon")
        try:
            available = {item["id"] for item in monitor.input_devices()}
        except Exception as error:
            return jsonify({"ok": False, "error": str(error)}), 500
        if device is not None and device not in available: abort(400, "Mikrofon nicht verfügbar")
        previous = config["audio"].get("device")
        try:
            monitor.select_device(device)
            save_config(config_path, config)
            return jsonify({"ok": True, "device": device})
        except Exception as error:
            config["audio"]["device"] = previous
            logging.exception("Could not switch audio input")
            return jsonify({"ok": False, "error": str(error)}), 500
    @app.put("/api/config/periods")
    def set_periods():
        periods = request.get_json(force=True)
        if not isinstance(periods, list) or len(periods) != 3: abort(400, "Genau drei Zeitbereiche erforderlich")
        for period in periods:
            if not all(key in period for key in ("name", "start", "end", "threshold_db")): abort(400, "Unvollständiger Zeitbereich")
            datetime.strptime(period["start"], "%H:%M"); datetime.strptime(period["end"], "%H:%M"); period["threshold_db"] = float(period["threshold_db"])
            period["warning_db"] = float(period.get("warning_db", period["threshold_db"] + 10)); period["severe_db"] = float(period.get("severe_db", period["threshold_db"] + 15)); period["enabled"] = bool(period.get("enabled", True))
            if not period["threshold_db"] < period["warning_db"] < period["severe_db"]: abort(400, "Pegel müssen aufsteigend sein")
        config["periods"] = periods; save_config(config_path, config); return jsonify({"ok": True})
    @app.put("/api/config/audio-storage")
    def set_audio_storage():
        payload = request.get_json(force=True) or {}
        try:
            bitrate, retention, pre, post = int(payload["mp3_bitrate_kbps"]), int(payload["retention_days"]), float(payload["pre_roll_seconds"]), float(payload["post_roll_seconds"])
        except (KeyError, TypeError, ValueError): abort(400, "Ungültige Audioeinstellungen")
        if bitrate not in (64, 96, 128, 192, 256, 320) or not 1 <= retention <= 3650 or not 0 <= pre <= 30 or not 0 <= post <= 60:
            abort(400, "Bitrate oder Aufbewahrungsdauer außerhalb des erlaubten Bereichs")
        config["audio"]["mp3_bitrate_kbps"] = bitrate
        config["storage"]["retention_days"] = retention
        config["audio"]["pre_roll_seconds"], config["audio"]["post_roll_seconds"] = pre, post
        save_config(config_path, config)
        return jsonify({"ok": True})
    @app.put("/api/config/site")
    def set_site():
        name = str((request.get_json(force=True) or {}).get("site_name", "")).strip()
        if not 1 <= len(name) <= 100: abort(400, "Ungültiger Messstellenname")
        payload = request.get_json(force=True) or {}; config["site_name"] = name
        config["site_data"] = {key: str(payload.get(key, ""))[:100] for key in ("location", "orientation", "target_object", "ground_distance", "wall_distance", "microphone")}
        save_config(config_path, config); return jsonify({"ok": True})
    @app.put("/api/config/refresh")
    def set_refresh():
        try: seconds = int((request.get_json(force=True) or {})["refresh_seconds"])
        except (KeyError, TypeError, ValueError): abort(400, "Ungültiges Aktualisierungsintervall")
        if not 5 <= seconds <= 3600: abort(400, "Intervall muss zwischen 5 und 3600 Sekunden liegen")
        config["web"]["refresh_seconds"] = seconds; save_config(config_path, config); return jsonify({"ok": True})
    @app.put("/api/config/calibration")
    def set_calibration():
        payload = request.get_json(force=True) or {}
        try: manual = float(payload["manual_calibration_db"])
        except (KeyError, TypeError, ValueError): abort(400, "Ungültige Kalibrierung")
        if not -30 <= manual <= 30: abort(400, "Manuelle Kalibrierung muss zwischen -30 und 30 dB liegen")
        config["audio"]["manual_calibration_db"] = manual; save_config(config_path, config)
        return jsonify({"ok": True})
    @app.put("/api/config/measurement")
    def set_measurement():
        payload = request.get_json(force=True) or {}
        weighting, response = str(payload.get("weighting", "")).upper(), str(payload.get("time_weighting", "")).lower()
        if weighting not in ("A", "C") or response not in ("fast", "slow"):
            abort(400, "Ungültige Messart")
        config["audio"]["weighting"] = weighting; config["audio"]["time_weighting"] = response
        monitor.reset_measurement_response(); save_config(config_path, config)
        return jsonify({"ok": True})
    @app.post("/api/config/calibration-file")
    def upload_calibration():
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename: abort(400, "Keine Kalibrierdatei ausgewählt")
        filename = secure_filename(uploaded.filename)
        if Path(filename).suffix.lower() not in (".txt", ".cal", ".csv"): abort(400, "Erlaubt sind TXT, CAL oder CSV")
        target_dir = Path(config["storage"]["calibration_dir"]); target_dir.mkdir(parents=True, exist_ok=True)
        uploaded.save(target_dir / filename)
        config["audio"]["calibration_file"] = filename; monitor.reload_calibration(); save_config(config_path, config)
        return jsonify({"ok": True, "filename": filename})
    @app.put("/api/config/mqtt")
    def set_mqtt():
        payload = request.get_json(force=True) or {}
        try:
            settings = {"enabled": bool(payload.get("enabled", False)), "host": str(payload["host"]).strip(), "port": int(payload["port"]), "username": str(payload.get("username", "")), "discovery_prefix": str(payload.get("discovery_prefix", "homeassistant")).strip("/"), "base_topic": str(payload.get("base_topic", "noisemeter")).strip("/")}
        except (KeyError, TypeError, ValueError): abort(400, "Ungültige MQTT-Einstellungen")
        if not settings["host"] or not 1 <= settings["port"] <= 65535 or not settings["base_topic"]: abort(400, "Ungültige MQTT-Einstellungen")
        password = payload.get("password")
        settings["password"] = config["mqtt"].get("password", "") if password in (None, "") else str(password)
        app.extensions["mqtt"].stop()
        config["mqtt"] = settings; save_config(config_path, config)
        replacement = MqttPublisher(config["mqtt"], database); replacement.start(); monitor.on_measurement = replacement.publish_measurement
        app.extensions["mqtt"] = replacement
        return jsonify({"ok": True})
    @app.get("/report/<kind>/<value>.pdf")
    def report(kind, value):
        if kind not in ("day", "week", "month", "year"): abort(404)
        try: start, end = period_range(kind, value)
        except ValueError: abort(400)
        output = Path(config["storage"]["report_dir"]) / f"{kind}_{value}.pdf"
        items = database.events(start, end); period_map = {p["name"]: p for p in config["periods"]}
        for item in items:
            period = period_map.get(item["period_name"], {}); item["warning_db"] = float(period.get("warning_db", item["threshold_db"] + 10)); item["severe_db"] = float(period.get("severe_db", item["threshold_db"] + 15))
        create_report(output, f"{kind.title()}bericht", start, end, database.summary(start, end), items, config["site_name"], config.get("site_data"), database.level_breakdown(kind, start, end))
        return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=output.name)
    @app.get("/backup/<kind>/<value>.zip")
    def backup(kind, value):
        try: start, end = period_range(kind, value)
        except ValueError: abort(400)
        output = Path(config["storage"]["report_dir"]) / f"backup_{kind}_{value}.zip"
        events = database.events(start, end); root = Path(config["storage"]["audio_dir"])
        from openpyxl import Workbook
        workbook = Workbook(); sheet = workbook.active; sheet.title = "Ereignisse"
        sheet.append(["Zeitpunkt", "Peak dB", "Grenzwert dB", "Zeitbereich", "Dauer Sekunden", "MP3-Datei"])
        for event in events:
            sheet.append([event["occurred_at"], event["peak_db"], event["threshold_db"], event["period_name"], event["duration_seconds"], event["filename"]])
        for column, width in zip("ABCDEF", (22, 12, 15, 18, 16, 42)): sheet.column_dimensions[column].width = width
        stream = BytesIO(); workbook.save(stream)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("ereignisse.xlsx", stream.getvalue())
            for event in events:
                audio = root / event["filename"]
                if audio.is_file(): archive.write(audio, f"audio/{event['filename']}")
        return send_file(output, as_attachment=True, download_name=output.name)
    return app

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", default="/etc/noisemeter/config.yaml"); args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app(args.config); app.extensions["monitor"].start()
    app.run(host=app.extensions["nm_config"]["web"]["host"], port=int(app.extensions["nm_config"]["web"]["port"]), threaded=True)
if __name__ == "__main__": main()
