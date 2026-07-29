# NoiseMeter Pro 1.0

Lärmüberwachung für Raspberry Pi 3B+, 4 und 5 mit USB-Mikrofon. Das Gerät misst permanent den Pegel, löst in drei frei definierbaren Zeitbereichen aus und speichert ein MP3 mit 3 Sekunden Vorlauf und 5 Sekunden Nachlauf.

## Installation auf Raspberry Pi OS Bookworm

Repository auf den Pi kopieren oder klonen und aus dem Projektordner ausführen:

```bash
sudo bash installer/install.sh
```

Danach ist die Weboberfläche unter `http://<IP-des-Pi>:8080` verfügbar. Der Dienst startet automatisch beim Booten. Status: `sudo systemctl status noisemeter`.

## Bedienung

Das Webinterface zeigt Live-Pegel, Tag, ISO-Woche und Monat. Die Ereignisliste spielt MP3-Dateien direkt ab und erzeugt Wochen- oder Monatsberichte als PDF. Die drei Zeitbereiche lassen sich dort ändern.

Audio liegt in `/var/lib/noisemeter/audio/JJJJ/MM/`. Die Namen enthalten Datum, Uhrzeit und Spitzenpegel. Konfiguration: `/etc/noisemeter/config.yaml`.

## Kalibrierung

`calibration_offset_db` ist vom Mikrofon abhängig und muss für reale dB(SPL)-Werte kalibriert werden. Mit einem 1-kHz-Kalibrator bei 94 dB den Wert so ändern, dass die Liveanzeige 94 dB zeigt, dann `sudo systemctl restart noisemeter` ausführen.
