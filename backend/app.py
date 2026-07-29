from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import logging

from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory

from .config import load_config, save_config
from .database import Database
from .monitor import NoiseMonitor
from .reports import create_report

def period_range(kind: str, value: str):
    if kind == "day":
        start = datetime.strptime(value, "%Y-%m-%d").date()
        end = start + timedelta(days=1)
    elif kind == "week":
        year, week = map(int, value.split("-W")); start = date.fromisocalendar(year, week, 1); end = start + timedelta(days=7)
    elif kind == "month":
        start = datetime.strptime(value + "-01", "%Y-%m-%d").date(); end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    else: raise ValueError("invalid period")
    return start.isoformat(), end.isoformat()

def create_app(config_path: str):
    config = load_config(config_path)
    app = Flask(__name__); app.config["SECRET_KEY"] = config["web"]["secret_key"]
    database = Database(config["storage"]["database"]); monitor = NoiseMonitor(config, database)
    app.extensions["monitor"], app.extensions["database"], app.extensions["nm_config"], app.extensions["config_path"] = monitor, database, config, config_path

    @app.get("/")
    def index(): return render_template("index.html")
    @app.get("/api/status")
    def status(): return jsonify(monitor.status())
    @app.get("/api/events")
    def events():
        kind, value = request.args.get("kind", "day"), request.args.get("date", date.today().isoformat())
        try: start, end = period_range(kind, value)
        except ValueError: abort(400, "Ungültiger Zeitraum")
        return jsonify({"start": start, "end": end, "summary": database.summary(start, end), "events": database.events(start, end)})
    @app.get("/audio/<path:filename>")
    def audio(filename): return send_from_directory(config["storage"]["audio_dir"], filename, conditional=True)
    @app.get("/api/config")
    def get_config(): return jsonify({"periods": config["periods"], "audio": {k: config["audio"][k] for k in ("calibration_offset_db", "device")}})
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
        config["periods"] = periods; save_config(config_path, config); return jsonify({"ok": True})
    @app.get("/report/<kind>/<value>.pdf")
    def report(kind, value):
        if kind not in ("week", "month"): abort(404)
        try: start, end = period_range(kind, value)
        except ValueError: abort(400)
        output = Path(config["storage"]["report_dir"]) / f"{kind}_{value}.pdf"
        create_report(output, f"{kind.title()}bericht", start, end, database.summary(start, end), database.events(start, end))
        return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=output.name)
    return app

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", default="/etc/noisemeter/config.yaml"); args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app(args.config); app.extensions["monitor"].start()
    app.run(host=app.extensions["nm_config"]["web"]["host"], port=int(app.extensions["nm_config"]["web"]["port"]), threaded=True)
if __name__ == "__main__": main()
