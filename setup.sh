#!/usr/bin/env bash
# KAPATID-VIBE — one-time setup for Raspberry Pi 4 Model B.
#   chmod +x setup.sh && ./setup.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOT_CONFIG=/boot/firmware/config.txt          # moved here in Bookworm
[[ -f $BOOT_CONFIG ]] || BOOT_CONFIG=/boot/config.txt

echo "==> Sanity checks"
grep -q "Raspberry Pi 4" /proc/device-tree/model 2>/dev/null \
    && echo "    board: $(tr -d '\0' </proc/device-tree/model)" \
    || echo "    WARNING: this does not look like a Pi 4"

ARCH="$(dpkg --print-architecture)"
echo "    architecture: $ARCH"
if [[ $ARCH != "arm64" ]]; then
    cat <<'WARN'
    !! You are running 32-bit Raspberry Pi OS.
       On 64-bit, the soundfile wheel bundles libsndfile 1.2.2 and MP3
       playback just works. On 32-bit there is no prebuilt wheel, so it
       falls back to the system libsndfile -- and on Bullseye that is
       version 1.0.31, which CANNOT decode MP3 at all.
       Strongly consider reflashing with 64-bit Raspberry Pi OS.
WARN
fi

echo "==> System packages"
sudo apt update
# libportaudio2 is NOT optional: sounddevice has no Linux wheel on any
# architecture, so PortAudio must come from apt.
sudo apt install -y i2c-tools libportaudio2 libsndfile1 \
                    python3-venv python3-dev python3-smbus2

echo "==> Enabling I2C for the LCD"
sudo raspi-config nonint do_i2c 0

echo "==> Python environment"
# --system-site-packages matters: without it we lose the preinstalled
# gpiozero / rpi-lgpio and would have to rebuild lgpio from source.
python3 -m venv --system-site-packages "$HERE/venv"
"$HERE/venv/bin/pip" install --upgrade pip
"$HERE/venv/bin/pip" install RPLCD sounddevice soundfile numpy

# Only needed if you set PWM_MODE = "hardware" in config.py.
"$HERE/venv/bin/pip" install rpi-hardware-pwm

echo "==> Reducing idle heat (no performance needed for this workload)"
if ! grep -q "^GOVERNOR=" /etc/default/cpufrequtils 2>/dev/null; then
    sudo apt install -y cpufrequtils
    echo 'GOVERNOR="powersave"' | sudo tee /etc/default/cpufrequtils >/dev/null
fi

echo "==> Checking hardware"
echo "--- Board revision (c03114 / c03115 are current) ---"
grep Revision /proc/cpuinfo || true
echo "--- I2C bus (expect 27, or 3f on some backpacks) ---"
sudo i2cdetect -y 1 || true
echo "--- Audio devices ---"
"$HERE/venv/bin/python" -m sounddevice || true
echo "--- Temperature / throttling (want 0x0) ---"
vcgencmd measure_temp || true
vcgencmd get_throttled || true

cat <<EOF

Setup finished.

Next:
  1. Note the audio device name printed above and set AUDIO_DEVICE in
     config.py. "USB" if you fitted an adapter, "Headphones" for the jack.
  2. If i2cdetect showed 3f instead of 27, update LCD_ADDRESS in config.py.
  3. Test:   ./venv/bin/python kapatid.py
  4. Autostart:
       sed -i "s|/home/pi/kapatid-pi|$HERE|g" kapatid.service
       sudo cp kapatid.service /etc/systemd/system/
       sudo systemctl enable --now kapatid

No device-tree overlay is needed with the default PWM_MODE = "software".
EOF
