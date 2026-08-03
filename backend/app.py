from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import logging
import signal
import zipfile
import shutil
import tempfile
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

def report_filename(kind: str, start: str, end: str, language: str = "de") -> str:
    titles = ({"day": "DailyReport", "week": "WeeklyReport", "month": "MonthlyReport", "year": "YearlyReport"} if language == "en" else
              {"day": "Tagesbericht", "week": "Wochenbericht", "month": "Monatsbericht", "year": "Jahresbericht"})
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    inclusive_end = datetime.strptime(end, "%Y-%m-%d").date() - timedelta(days=1)
    start_text, end_text = start_date.strftime("%d-%m-%Y"), inclusive_end.strftime("%d-%m-%Y")
    if kind == "day":
        period = start_text
    elif kind == "week":
        period = f"{'CW' if language == 'en' else 'KW'}{start_date.isocalendar().week:02d}_{start_text}_{'to' if language == 'en' else 'bis'}_{end_text}"
    else:
        period = f"{start_text}_{'to' if language == 'en' else 'bis'}_{end_text}"
    return f"NoiseMeterPro_{titles[kind]}_{period}.pdf"

def backup_filename(kind: str, start: str, end: str) -> str:
    pdf_name = report_filename(kind, start, end)
    period = pdf_name.split("_", 2)[2].rsplit(".", 1)[0]
    return f"NoiseMeterPro_Backup_{period}.zip"

def create_app(config_path: str):
    config = load_config(config_path)
    app = Flask(__name__); app.config["SECRET_KEY"] = config["web"]["secret_key"]
    database = Database(config["storage"]["database"]); monitor = NoiseMonitor(config, database)
    mqtt = MqttPublisher(config["mqtt"], database); monitor.on_measurement = mqtt.publish_measurement
    mqtt.start()
    app.extensions["mqtt"] = mqtt
    system_info = SystemInfo(config["storage"])
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
    @app.get("/api/period-statistics")
    def period_statistics():
        try: selected_day = datetime.strptime(request.args.get("date", date.today().isoformat()), "%Y-%m-%d").date()
        except ValueError: abort(400, "Ungültiges Datum")
        return jsonify({"date": selected_day.isoformat(), "items": database.period_statistics(selected_day, config["periods"])})
    @app.get("/audio/<path:filename>")
    def audio(filename): return send_from_directory(config["storage"]["audio_dir"], filename, conditional=True)
    @app.get("/api/config")
    def get_config(): return jsonify({"site_name": config["site_name"], "site_data": config.get("site_data", {}), "version": "3.0.0", "web": {"refresh_seconds": config["web"].get("refresh_seconds", 5)}, "periods": config["periods"], "audio": {k: config["audio"].get(k) for k in ("calibration_offset_db", "device", "microphone_name", "mp3_bitrate_kbps", "calibration_file", "calibration_files", "calibration_angle", "calibration_graphic", "manual_calibration_db", "weighting", "time_weighting", "pre_roll_seconds", "post_roll_seconds")}, "input_gain": monitor.status()["input_gain"], "calibration": monitor.calibration.metadata(), "storage": {"retention_days": config["storage"]["retention_days"]}, "mqtt": {"enabled": config["mqtt"]["enabled"], "host": config["mqtt"]["host"], "port": config["mqtt"]["port"], "username": config["mqtt"]["username"], "discovery_prefix": config["mqtt"]["discovery_prefix"], "base_topic": config["mqtt"]["base_topic"], "has_password": bool(config["mqtt"].get("password"))}})
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
        microphone_name = str(payload.get("microphone_name", "")).strip()
        if len(microphone_name) > 100: abort(400, "Mikrofonname ist zu lang")
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
            config["audio"]["microphone_name"] = microphone_name
            save_config(config_path, config)
            return jsonify({"ok": True, "device": device, "microphone_name": microphone_name})
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
        angle = str(payload.get("microphone_angle", "0"))
        if angle not in ("0", "90"): abort(400, "Mikrofonausrichtung muss 0 oder 90 Grad sein")
        config["site_data"] = {key: str(payload.get(key, ""))[:100] for key in ("location", "orientation", "target_object", "ground_distance", "wall_distance", "microphone")}
        config["site_data"]["microphone_angle"] = angle
        config["audio"]["calibration_angle"] = angle
        monitor.reload_calibration()
        save_config(config_path, config); return jsonify({"ok": True})
    @app.delete("/api/data")
    def delete_data():
        payload = request.get_json(force=True) or {}
        try:
            start_date = datetime.strptime(str(payload["from"]), "%Y-%m-%d").date()
            end_date = datetime.strptime(str(payload["to"]), "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError): abort(400, "Ungültiger Löschzeitraum")
        if start_date > end_date: abort(400, "Das Von-Datum muss vor dem Bis-Datum liegen")
        start, end = start_date.isoformat(), (end_date + timedelta(days=1)).isoformat()
        monitor.flush_measurements()
        deleted = database.delete_range(start, end)
        root = Path(config["storage"]["audio_dir"]).resolve()
        removed_files = 0
        for filename in deleted.pop("files"):
            target = (root / filename).resolve()
            if target.is_relative_to(root) and target.is_file():
                try: target.unlink(); removed_files += 1
                except OSError: logging.warning("Could not delete audio file %s", target)
        return jsonify({"ok": True, **deleted, "audio_files": removed_files, "from": start_date.isoformat(), "to": end_date.isoformat()})
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
        if Path(filename).suffix.lower() not in (".zip", ".sen", ".txt", ".cal", ".csv"): abort(400, "Erlaubt sind ZIP, SEN, TXT, CAL oder CSV")
        target_dir = Path(config["storage"]["calibration_dir"]); target_dir.mkdir(parents=True, exist_ok=True)
        if Path(filename).suffix.lower() == ".zip":
            try:
                bundle = _install_calibration_zip(uploaded.stream, target_dir)
            except (ValueError, zipfile.BadZipFile) as error:
                abort(400, str(error))
            config["audio"]["calibration_files"] = bundle["files"]
            config["audio"]["calibration_graphic"] = bundle["graphic"]
            angle = str(config["audio"].get("calibration_angle", "0"))
            config["audio"]["calibration_file"] = bundle["files"][angle]
        else:
            uploaded.save(target_dir / filename)
            config["audio"]["calibration_file"] = filename
        monitor.reload_calibration(); save_config(config_path, config)
        return jsonify({"ok": True, "filename": config["audio"]["calibration_file"], "files": config["audio"].get("calibration_files"), "graphic": config["audio"].get("calibration_graphic")})
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
        language = "de" if request.args.get("lang") == "de" else "en"
        download_name = report_filename(kind, start, end, language)
        output = Path(config["storage"]["report_dir"]) / download_name
        items = database.events(start, end); period_map = {p["name"]: p for p in config["periods"]}
        for item in items:
            period = period_map.get(item["period_name"], {}); item["warning_db"] = float(period.get("warning_db", item["threshold_db"] + 10)); item["severe_db"] = float(period.get("severe_db", item["threshold_db"] + 15))
        titles = ({"day": "Daily report", "week": "Weekly report", "month": "Monthly report", "year": "Yearly report"} if language == "en" else
                  {"day": "Tagesbericht", "week": "Wochenbericht", "month": "Monatsbericht", "year": "Jahresbericht"})
        site_data = dict(config.get("site_data") or {})
        site_data["microphone"] = config["audio"].get("microphone_name") or site_data.get("microphone", "")
        gain = monitor.status()["input_gain"]
        gain_values = gain.get("channels") or ([gain["percent"]] if gain.get("percent") is not None else [])
        site_data["input_gain"] = " - ".join(f"{value} %" for value in gain_values) + (" (set automatically)" if language == "en" else " (automatisch gesetzt)") if gain_values else ("100% / unchanged" if language == "en" else "100 % / unverändert")
        site_data["calibration_file"] = config["audio"].get("calibration_file") or ("None" if language == "en" else "Keine")
        site_data["calibration_angle"] = f"{config['audio'].get('calibration_angle', '0')} {'degrees' if language == 'en' else 'Grad'}"
        logo = Path(app.static_folder) / "assets" / "noisemeter-logo.png"
        graphic_name = config["audio"].get("calibration_graphic")
        graphic = Path(config["storage"]["calibration_dir"]) / graphic_name if graphic_name else None
        daily_histories = database.daily_histories(start, end) if kind == "week" else None
        create_report(output, titles[kind], kind, value, start, end, database.summary(start, end), items, config["site_name"], site_data, database.level_breakdown(kind, start, end), logo, graphic, database.report_history(kind, start, end), daily_histories, language)
        return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=download_name)
    @app.get("/backup/<kind>/<value>.zip")
    def backup(kind, value):
        try: start, end = period_range(kind, value)
        except ValueError: abort(400)
        download_name = backup_filename(kind, start, end)
        output = Path(config["storage"]["report_dir"]) / download_name
        events = database.events(start, end); root = Path(config["storage"]["audio_dir"])
        from openpyxl import Workbook
        workbook = Workbook(); sheet = workbook.active; sheet.title = "Ereignisse"
        info = workbook.create_sheet("Exportinformationen", 0)
        info.append(["NoiseMeter Pro Export", kind])
        info.append(["Von", datetime.strptime(start, "%Y-%m-%d").strftime("%d-%m-%Y")])
        info.append(["Bis", (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=1)).strftime("%d-%m-%Y")])
        if kind == "week": info.append(["Kalenderwoche", datetime.strptime(start, "%Y-%m-%d").date().isocalendar().week])
        sheet.append(["Zeitpunkt", "Peak dB", "Leq dB", "Grenzwert dB", "Zeitbereich", "Ereignisdauer Sekunden", "Dominante Frequenz Hz", "MP3-Dateien"])
        for event in events:
            sheet.append([event["occurred_at"], event["peak_db"], event.get("leq_db"), event["threshold_db"], event["period_name"], event["duration_seconds"], event.get("dominant_frequency_hz"), " | ".join(event["audio_files"])])
        for column, width in zip("ABCDEFGH", (22, 12, 12, 15, 18, 16, 21, 42)): sheet.column_dimensions[column].width = width
        stream = BytesIO(); workbook.save(stream)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("ereignisse.xlsx", stream.getvalue())
            for event in events:
                for filename in event["audio_files"]:
                    audio = root / filename
                    if audio.is_file(): archive.write(audio, f"audio/{filename}")
        return send_file(output, as_attachment=True, download_name=download_name)
    return app

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", default="/etc/noisemeter/config.yaml"); args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app(args.config); monitor = app.extensions["monitor"]; monitor.start()
    def stop_service(signum, frame):
        monitor.stop()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop_service)
    try:
        app.run(host=app.extensions["nm_config"]["web"]["host"], port=int(app.extensions["nm_config"]["web"]["port"]), threaded=True)
    finally:
        monitor.stop()
def _install_calibration_zip(stream, target_dir: Path):
    """Validate then replace a 0/90-degree SEN calibration bundle."""
    with zipfile.ZipFile(stream) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) > 12 or sum(item.file_size for item in members) > 20 * 1024 * 1024:
            raise ValueError("Kalibrier-ZIP ist zu groß")
        selected = {}
        graphic = None
        for item in members:
            name = secure_filename(Path(item.filename).name)
            lower = name.lower()
            if lower.endswith(".sen") and "_00d" in lower:
                selected["0"] = (item, name)
            elif lower.endswith(".sen") and "_90d" in lower:
                selected["90"] = (item, name)
            elif Path(lower).suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif") and graphic is None:
                graphic = (item, name)
        if set(selected) != {"0", "90"} or graphic is None:
            raise ValueError("ZIP muss je eine *_00d.sen-, *_90d.sen- und eine Bilddatei enthalten")
        with tempfile.TemporaryDirectory(dir=target_dir.parent) as temporary:
            temp = Path(temporary)
            for item, name in [*selected.values(), graphic]:
                with archive.open(item) as source, (temp / name).open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            from .calibration import CalibrationProfile
            for item, name in selected.values():
                profile = CalibrationProfile(); profile.load(str(temp / name))
                if not profile.loaded:
                    raise ValueError(f"{name} enthält keine gültige SEN-Frequenztabelle")
            for existing in target_dir.iterdir():
                if existing.is_file(): existing.unlink()
            for source in temp.iterdir(): shutil.move(str(source), target_dir / source.name)
    return {"files": {angle: value[1] for angle, value in selected.items()}, "graphic": graphic[1]}


if __name__ == "__main__": main()
