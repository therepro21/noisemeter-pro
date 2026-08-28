#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Bitte mit sudo ausführen: sudo bash installer/install.sh"; exit 1; fi
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR=/opt/noisemeter-pro
echo "Installiere NoiseMeter Pro nach $APP_DIR ..."
apt-get update
apt-get install -y python3-venv python3-pip portaudio19-dev ffmpeg alsa-utils git
id -u noisemeter >/dev/null 2>&1 || useradd --system --home /var/lib/noisemeter --create-home --groups audio noisemeter
install -d -o noisemeter -g noisemeter /var/lib/noisemeter/audio /var/lib/noisemeter/reports /var/lib/noisemeter/calibration /etc/noisemeter
systemctl stop noisemeter.service 2>/dev/null || true
rm -rf "$APP_DIR"
install -d -o root -g root "$APP_DIR"
cp -a "$SOURCE_DIR/backend" "$SOURCE_DIR/requirements.txt" "$APP_DIR/"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
if [[ ! -f /etc/noisemeter/config.yaml ]]; then install -m 660 -o root -g noisemeter "$SOURCE_DIR/config/config.example.yaml" /etc/noisemeter/config.yaml; fi
if grep -q '^  port: 8080$' /etc/noisemeter/config.yaml; then
  sed -i 's/^  port: 8080$/  port: 8090/' /etc/noisemeter/config.yaml
  echo "Bestehenden Standard-Webport von 8080 auf 8090 migriert."
fi
install -m 644 "$SOURCE_DIR/systemd/noisemeter.service" /etc/systemd/system/noisemeter.service
install -m 755 "$SOURCE_DIR/installer/update.sh" /usr/local/sbin/noisemeter-update
install -m 644 "$SOURCE_DIR/systemd/noisemeter-update.service" /etc/systemd/system/noisemeter-update.service
install -m 644 "$SOURCE_DIR/systemd/noisemeter-update.path" /etc/systemd/system/noisemeter-update.path
systemctl daemon-reload
systemctl enable --now noisemeter-update.path
systemctl enable --now noisemeter.service
IP=$(hostname -I | awk '{print $1}')
echo "Fertig. Weboberfläche: http://${IP:-raspberrypi.local}:8090"
