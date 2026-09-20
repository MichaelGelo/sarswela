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

echo "==> Tailoring the systemd unit to this install"
# kapatid.service is committed with one specific user and path baked in. The
# old advice was `sed -i "s|/home/pi/kapatid-pi|$HERE|g" kapatid.service`,
# which broke the moment those literal paths changed: the pattern matched
# nothing, said nothing, and left the unit pointing at a directory that need
# not exist -- which fails as status=200/CHDIR with no Python traceback.
#
# Anchor on the KEYS instead of on any path value, so this cannot go stale
# again, and write to a separate file so the repo stays clean for `git pull`.
RUN_USER="${SUDO_USER:-$(id -un)}"
sed -E     -e "s|^User=.*|User=${RUN_USER}|"     -e "s|^WorkingDirectory=.*|WorkingDirectory=${HERE}|"     -e "s|^ExecStart=.*|ExecStart=${HERE}/venv/bin/python ${HERE}/kapatid.py|"     "$HERE/kapatid.service" > "$HERE/kapatid.service.local"
echo "    wrote kapatid.service.local (User=${RUN_USER}, dir=${HERE})"

echo "==> Reducing idle heat (no performance needed for this workload)"
# This is a comfort tweak, never a requirement -- so it must not be allowed to
# abort the install. It used to: cpufrequtils was dropped in Debian 13
# (trixie), apt exited non-zero, and `set -e` killed the script here, silently
# skipping the I2C scan, the audio device list, the mixer setup and the
# closing instructions. Everything below this line matters more than this
# does, so it runs behind `|| true` and reports what it managed.
set_governor() {
    if sudo apt install -y cpufrequtils >/dev/null 2>&1; then
        echo 'GOVERNOR="powersave"' | sudo tee /etc/default/cpufrequtils >/dev/null
        echo "    powersave governor set via cpufrequtils (survives reboot)"
        return 0
    fi

    echo "    cpufrequtils unavailable (expected on Debian 13+) -- using sysfs"
    local governor found=0
    for governor in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        [[ -e $governor ]] || continue
        echo powersave | sudo tee "$governor" >/dev/null 2>&1 && found=1
    done
    if [[ $found -eq 1 ]]; then
        echo "    governor now: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
        echo "    note: set via sysfs, so it resets on reboot"
    else
        echo "    no cpufreq governor exposed; skipping (harmless)"
    fi
}
set_governor || true

echo "==> Checking hardware"
echo "--- Board revision (c03114 / c03115 are current) ---"
grep Revision /proc/cpuinfo || true
echo "--- I2C bus (expect 27, or 3f on some backpacks) ---"
sudo i2cdetect -y 1 || true
echo "--- Audio devices ---"
"$HERE/venv/bin/python" -m sounddevice || true
echo "--- Audio output level ---"
# The mixer does not default to maximum, and an unset level is the most
# common cause of "the box is too quiet". Claim it now rather than debugging
# it the night before a performance.
if [[ -x "$HERE/pi_audio.sh" ]]; then
    "$HERE/pi_audio.sh" --max || true
fi
echo "--- Temperature / throttling (want 0x0) ---"
vcgencmd measure_temp || true
vcgencmd get_throttled || true

cat <<EOF

Setup finished.

Next:
  1. Note the audio device name printed above and set AUDIO_DEVICE in
     config.py. "USB" if you fitted an adapter, "Headphones" for the jack.
  1b. Normalise the clips so every mode plays at the same, louder level:
       ./venv/bin/python normalize_audio.py          # report
       ./venv/bin/python normalize_audio.py --apply  # do it
  2. If i2cdetect showed 3f instead of 27, update LCD_ADDRESS in config.py.
  3. Test:   ./venv/bin/python kapatid.py
  4. Autostart. kapatid.service.local was generated above with this
     install's real user and paths, so nothing needs editing:
       sudo cp kapatid.service.local /etc/systemd/system/kapatid.service
       sudo systemctl daemon-reload
       sudo systemctl enable --now kapatid

No device-tree overlay is needed with the default PWM_MODE = "software".
EOF
