# NoiseMeter Pro 2.0

Lärmüberwachung für Raspberry Pi 3B+, 4 und 5 mit USB-Mikrofon. Das Gerät misst permanent den Pegel, löst in drei frei definierbaren Zeitbereichen aus und speichert Ereignisse als MP3 mit konfigurierbarem Vor- und Nachlauf.

## Installation auf Raspberry Pi OS Bookworm

Repository auf den Pi kopieren oder klonen und aus dem Projektordner ausführen:

```bash
sudo bash installer/install.sh
```

Danach ist die Weboberfläche unter `http://<IP-des-Pi>:8080` verfügbar. Der Dienst startet automatisch beim Booten. Status: `sudo systemctl status noisemeter`.

## Bedienung

Das responsive Webinterface zeigt Live-Pegel sowie Tages-, ISO-Wochen-, Monats- und Jahresübersichten. In der Tagesübersicht werden die drei konfigurierten Tageszeiten mit Ereignisanzahl sowie Minimal-, Durchschnitts- und Maximalpegel ausgewertet. Die Ereignisliste spielt MP3-Dateien direkt ab; deutsche PDF-Berichte und ZIP-Backups stehen für alle Übersichten bereit.

Das Dark Theme ist standardmäßig aktiv und kann über das Sonnensymbol im Kopfbereich umgeschaltet werden. In den Einstellungen lassen sich USB-Gerät und ein kurzer eigener Messmikrofonname festlegen. Dieser Name erscheint auch in den PDF-Berichten. Ist kein Messmikrofon verfügbar, werden keine künstlichen Pegelwerte angezeigt oder gespeichert.

Fehlmessungen können unter **Einstellungen → Messdaten löschen** für einen Datumsbereich vollständig entfernt werden. Dabei werden Messwerte, Ereignisse und zugehörige MP3-Dateien dauerhaft gelöscht; vorher ist eine ausdrückliche Bestätigung erforderlich.

Audio liegt in `/var/lib/noisemeter/audio/JJJJ/MM/`. Die Namen enthalten Datum, Uhrzeit und Spitzenpegel. Konfiguration: `/etc/noisemeter/config.yaml`.

## Kalibrierung

`calibration_offset_db` ist vom Mikrofon abhängig und muss für reale dB(SPL)-Werte kalibriert werden. Mit einem 1-kHz-Kalibrator bei 94 dB den Wert so ändern, dass die Liveanzeige 94 dB zeigt, dann `sudo systemctl restart noisemeter` ausführen.

## Home Assistant per MQTT

MQTT ist standardmäßig deaktiviert und kann im Webinterface konfiguriert werden. Alternativ lässt sich der Abschnitt in `/etc/noisemeter/config.yaml` bearbeiten:

```yaml
mqtt:
  enabled: true
  host: homeassistant.local
  port: 1883
  username: mqtt-benutzer
  password: mqtt-passwort
  discovery_prefix: homeassistant
  base_topic: noisemeter
```

Nach dem Neustart (`sudo systemctl restart noisemeter`) erscheinen automatisch Sensoren in Home Assistant. Die Messwerte werden als dB veröffentlicht.
