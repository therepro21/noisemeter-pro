# NoiseMeter Pro 2.0

Lärmüberwachung für Raspberry Pi 3B+, 4 und 5 mit USB-Messmikrofon. NoiseMeter Pro misst den aktuellen frequenz- und zeitbewerteten Schallpegel, den energieäquivalenten Dauerschallpegel Leq und zeichnet Grenzwertüberschreitungen als MP3 auf.

## Raspberry Pi unter Windows einrichten - Schritt für Schritt

1. Eine geeignete microSD-Karte (mindestens 16 GB) in den Windows-PC einlegen. Alle vorhandenen Daten auf der Karte werden beim Schreiben gelöscht.
2. [Raspberry Pi Imager](https://www.raspberrypi.com/software/) herunterladen, installieren und starten.
3. Raspberry-Pi-Modell auswählen.
4. Als Betriebssystem **Raspberry Pi OS with desktop (64-bit), Bookworm oder neuer** auswählen.
5. Die microSD-Karte als Ziel auswählen.
6. In der OS-Anpassung Hostname, Benutzername, ein sicheres Passwort, WLAN und Zeitzone eintragen.
7. Im Bereich **Raspberry Pi Connect** Connect aktivieren und mit der eigenen Raspberry-Pi-ID verknüpfen. Optional zusätzlich SSH aktivieren.
8. Betriebssystem schreiben und verifizieren lassen, microSD-Karte sicher entfernen und in den ausgeschalteten Raspberry Pi stecken.
9. USB-Messmikrofon anschließen, Raspberry Pi mit Strom versorgen und den ersten Start abwarten.
10. Am Windows-PC [connect.raspberrypi.com](https://connect.raspberrypi.com/) öffnen, anmelden, den Raspberry Pi auswählen und **Remote shell** öffnen.
11. Diese Befehle vollständig in das Browser-Terminal kopieren:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/therepro21/noisemeter-pro.git
cd noisemeter-pro
sudo bash installer/install.sh
```

12. Nach Abschluss `http://<IP-des-Pi>:8080` im Browser öffnen. Die IP wird am Ende der Installation angezeigt. Der Dienst startet zukünftig automatisch.

Status und Protokoll prüfen:

```bash
sudo systemctl status noisemeter
sudo journalctl -u noisemeter -n 100 --no-pager
```

Ein bestehendes System aktualisieren:

```bash
cd ~/noisemeter-pro
git pull origin main
sudo bash installer/install.sh
```

## Kalibrierung

Das Webinterface akzeptiert ein ZIP-Kalibrierpaket mit drei Dateien:

- `MM2USB..._00d.sen` für 0° frontal zur Schallquelle
- `MM2USB..._90d.sen` für 90° seitlich zur Schallquelle
- eine PNG-, JPG-, JPEG- oder WebP-Grafik des Kalibriergangs

Beide SEN-Profile und die Grafik werden gespeichert. Unter **Messstellendaten** wird der Mikrofonwinkel 0° oder 90° gewählt; NoiseMeter Pro aktiviert sofort das passende Profil. Erst ein neu hochgeladenes Kalibrierpaket ersetzt die alten Dateien. Die Grafik erscheint verkleinert im PDF-Bericht.

Beim Start versucht NoiseMeter Pro den regelbaren ALSA-Aufnahmepegel des USB-Mikrofons auf 100 % zu setzen. Der tatsächlich ermittelte Wert und das verwendete Mischpult-Steuerelement erscheinen in Status und PDF. Falls die Hardware keinen softwareseitig regelbaren Aufnahmepegel anbietet, wird dies ausdrücklich als nicht ermittelbar ausgewiesen.

Im Livebereich stehen der kalibrierte Pegel, der kleine unkalibrierte Vergleichswert und Leq über die letzten 60 Sekunden nebeneinander.

### Beispiel für ein kalibriertes Mikrofon

Die folgende Shop-URL ist nur ein Beispiel. Für die Entwicklung wurde dank freundlicher Unterstützung ein Demo-Kalibrierfile zum Testen zur Verfügung gestellt:

[Omnitronic MM-2USB, individuell mit 0°- und 90°-Kalibrierung](https://shop.hifi-selbstbau.de/produkt/omnitronic-mm-2usb/)

## Leq - äquivalenter Dauerschallpegel

Leq ist kein normaler arithmetischer Mittelwert von dB-Werten. NoiseMeter Pro wandelt jeden linearen Messabschnitt in Schallenergie um, mittelt diese über den jeweiligen Zeitraum und rechnet das Ergebnis logarithmisch nach dB zurück. Damit entspricht der Wert einem konstanten Pegel mit demselben Energieinhalt wie der schwankende Schall. Bei A-Bewertung wird er als LAeq, bei C-Bewertung als LCeq verstanden.

Leq wird zusätzlich im Livebereich (rollierende 60 Sekunden), Tagesverlauf, allen Übersichten, Tageszeit-Auswertungen, Ereignissen, ZIP/XLSX-Backups, MQTT und PDF-Berichten geführt. Fast/Slow beeinflusst den Momentanpegel, nicht die lineare Leq-Integration.

Fachliche Definition: [Svantek - Leq äquivalenter Dauerschallpegel](https://svantek.com/de/akademie/leq-aequivalenter-dauerschallpegel/)

## Bedienung und Daten

Das responsive Webinterface bietet Tages-, ISO-Wochen-, Monats- und Jahresübersichten. Die drei konfigurierten Tageszeiten enthalten Ereignisanzahl, Minimum, arithmetischen Durchschnitt, Maximum und Leq. Das Dark Theme ist standardmäßig aktiv.

Jeder PDF-Bericht enthält den blau hinterlegten Pegel-/Leq-Verlauf des ausgewählten Zeitraums. PDF-Dateien beginnen mit `NoiseMeterPro`, verwenden Datumsangaben im Format `TT-MM-JJJJ` und führen bei Wochenberichten zusätzlich die Kalenderwoche. Die kompakte Fußleiste des Webinterfaces bleibt dauerhaft sichtbar; ihr belegter Speicherwert umfasst ausschließlich NoiseMeter-Pro-Datenbank, MP3-Aufnahmen, Berichte und Kalibrierdateien.

Fehlmessungen können unter **Einstellungen → Messdaten löschen** vollständig entfernt werden. Dabei werden Messwerte, Ereignisse und zugehörige MP3-Dateien dauerhaft gelöscht.

Audio liegt in `/var/lib/noisemeter/audio/JJJJ/MM/`, die Datenbank in `/var/lib/noisemeter/noisemeter.sqlite3` und die Konfiguration in `/etc/noisemeter/config.yaml`.

## Home Assistant per MQTT

MQTT ist standardmäßig deaktiviert und kann im Webinterface konfiguriert werden. Veröffentlicht werden aktueller Schallpegel, aktueller Leq sowie Tages-, Wochen- und Monatshöchstwert.
