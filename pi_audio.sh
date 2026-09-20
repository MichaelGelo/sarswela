#!/usr/bin/env bash
# KAPATID-VIBE -- inspect and maximise the Pi's analogue audio output.
#
# Why this exists: setup.sh installs the audio stack but never sets a level,
# so the box runs at whatever Raspberry Pi OS defaulted to. The bcm2835
# headphone control spans roughly -102 dB to +4 dB and does not default to
# the top, so there is often 15-20 dB sitting unclaimed -- far more than any
# software gain in config.py can give you, and free of distortion.
#
#   ./pi_audio.sh          report what the mixer is doing now
#   ./pi_audio.sh --max    open every playback control fully, and persist it
#   ./pi_audio.sh --force-max   ...including gain past 0 dB, which clips
#
# Run this ON THE PI, not on the laptop.

set -uo pipefail

MAX=0
FORCE=0
CARD=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --max)  MAX=1 ;;
        --force-max) MAX=1; FORCE=1 ;;
        --card) CARD="${2:-}"; shift ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

command -v amixer >/dev/null || { echo "amixer not found (apt install alsa-utils)" >&2; exit 1; }

echo "=== Playback devices ==="
aplay -l 2>/dev/null || echo "  aplay found nothing -- is dtparam=audio=on set in config.txt?"
echo

# Pick the analogue card unless one was named. On Pi OS it enumerates as
# "Headphones"; older images call it ALSA/bcm2835.
if [[ -z $CARD ]]; then
    CARD=$(aplay -l 2>/dev/null \
           | sed -n 's/^card \([0-9]\+\): \([^ ]*\) .*/\2/p' \
           | grep -iE 'headphone|bcm2835|ALSA' | head -1)
fi
if [[ -z $CARD ]]; then
    CARD=$(aplay -l 2>/dev/null | sed -n 's/^card \([0-9]\+\): \([^ ]*\) .*/\2/p' | head -1)
fi
[[ -z $CARD ]] && { echo "No playback card found." >&2; exit 1; }
echo "Using card: $CARD"
echo

# Control names differ across OS releases -- Headphone, PCM, Master, Digital.
# Ask the card rather than guessing.
mapfile -t CONTROLS < <(amixer -c "$CARD" scontrols 2>/dev/null \
                        | sed -n "s/^Simple mixer control '\(.*\)',[0-9]*$/\1/p")
if [[ ${#CONTROLS[@]} -eq 0 ]]; then
    echo "Card $CARD exposes no mixer controls." >&2
    exit 1
fi

echo "=== Current levels ==="
# Track whether any gain is actually left to claim, so the report does not
# nag about opening a mixer that is already wide open.
BELOW_MAX=0
for ctl in "${CONTROLS[@]}"; do
    line=$(amixer -c "$CARD" sget "$ctl" 2>/dev/null | grep -m1 -oE '\[[0-9]+%\].*')
    printf '  %-14s %s
' "$ctl" "${line:-(no playback level)}"
    pct=$(printf '%s' "$line" | grep -oE '^\[[0-9]+%\]' | tr -cd '0-9')
    if [[ -n $pct ]] && (( pct < 100 )); then
        BELOW_MAX=1
    fi
done
echo

if [[ $MAX -eq 0 ]]; then
    if [[ $BELOW_MAX -eq 1 ]]; then
        cat <<'NOTE'
Report only -- nothing changed.

Anything below 100% above is loudness you are throwing away. To claim it:

    ./pi_audio.sh --max

NOTE
    else
        cat <<'NOTE'
Report only -- nothing changed.

Every playback control is already fully open, so there is no mixer gain
left to claim here. If it is still too quiet the shortfall is in the
output stage, not the settings -- see "Sound is too quiet" in README.md.

NOTE
    fi
    exit 0
fi

echo "=== Opening everything up ==="
for ctl in "${CONTROLS[@]}"; do
    if ! amixer -c "$CARD" sset "$ctl" 100% unmute >/dev/null 2>&1; then
        # Capture-only and enum controls land here; harmless.
        echo "  $ctl -- skipped (not a playback level)"
        continue
    fi

    # 100% is not the same thing as unity gain. The bcm2835 PCM control
    # tops out at +4.00 dB, which is digital gain ABOVE full scale: feed it
    # a normalised clip that already peaks near 0 dBFS and it clips hard,
    # which sounds like distortion rather than volume. So read back what
    # 100% actually got us and walk it down to 0 dB when it went past.
    db=$(amixer -c "$CARD" sget "$ctl" 2>/dev/null          | grep -m1 -oE '\[-?[0-9.]+dB\]' | tr -cd '0-9.-')
    if [[ $FORCE -eq 0 && -n $db ]] && awk "BEGIN{exit !($db > 0)}"; then
        amixer -c "$CARD" sset "$ctl" 0dB >/dev/null 2>&1
        echo "  $ctl -> 0 dB (100% is +${db} dB, which clips -- use --force-max to insist)"
    else
        echo "  $ctl -> 100%${db:+ (${db} dB)}"
    fi
done
echo

# Without this the levels reset on reboot and the box is quiet again at the
# worst possible moment.
if sudo alsactl store 2>/dev/null; then
    echo "Levels saved -- they survive a reboot."
else
    echo "WARNING: could not run 'sudo alsactl store'; levels may reset on reboot." >&2
fi

# Bookworm routes through PipeWire, which keeps its own sink volume on top of
# ALSA. A maxed ALSA control behind a half-open sink is still half volume.
if command -v wpctl >/dev/null; then
    echo
    echo "=== PipeWire sink ==="
    wpctl set-mute   @DEFAULT_AUDIO_SINK@ 0   2>/dev/null
    wpctl set-volume @DEFAULT_AUDIO_SINK@ 1.0 2>/dev/null
    wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null || true
fi

cat <<'NOTE'

Now test:
    speaker-test -c2 -t wav -l 1
    ./venv/bin/python -c "import hardware; a=hardware.Audio(); a.play('Sounds/English.mp3'); import time; time.sleep(5)"

Still not enough? Then it is the jack, not the settings -- see
"Sound is too quiet" in README.md.
NOTE
