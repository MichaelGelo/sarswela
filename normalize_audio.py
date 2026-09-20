#!/usr/bin/env python3
"""
Loudness-normalise the narration clips so every mode plays at the same,
much louder level.

Why this exists: the clips came from different sources and landed 18 dB
apart -- Child.mp3 measured -31 dBFS RMS while English.mp3 measured -13.
Turning the system volume up far enough to hear Child then makes English
painful, so in practice everything gets run at Child's level and the whole
box sounds quiet. Normalising fixes the inconsistency AND raises the floor,
which is most of the loudness problem solved before any amplifier is bought.

Usage:
    python normalize_audio.py            # report only, changes nothing
    python normalize_audio.py --apply    # rewrite the clips (originals kept)

Originals are copied to Sounds/original/ before anything is overwritten.
Re-running --apply always works from those originals, never from an
already-normalised file, so the process cannot compound.
"""

import argparse
import math
import os
import shutil
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(HERE, "Sounds")
BACKUP_DIR = os.path.join(SOUNDS_DIR, "original")

# --- Tuning ---------------------------------------------------------------
# Target loudness, measured as gated RMS (silence excluded). Speech has a
# lower crest factor than music, so -12 dBFS is loud but still clean.
# -10 is louder and noticeably compressed; below -16 you are back where
# you started.
TARGET_RMS_DBFS = -12.0

# Nothing is allowed past this. -1 dBFS leaves room for the inter-sample
# peaks that MP3 encoding adds, which is why we do not aim at 0.
CEILING_DBFS = -1.0

# How far past the ceiling the raw peaks may be pushed before the limiter
# catches them. This is the loudness/distortion dial: 0 dB means peak
# normalisation only (clean but quiet clips stay quiet), 6 dB gets a quiet
# clip most of the way up at a distortion level speech tolerates well.
MAX_LIMITING_DB = 6.0

# Gating window for the loudness measurement.
WINDOW_MS = 50
RELATIVE_GATE_DB = 10.0     # ignore windows this far below the loud ones
ABSOLUTE_GATE_DBFS = -60.0  # ...and anything that is just noise floor


def db(x):
    return 20.0 * math.log10(max(float(x), 1e-12))


def undb(x):
    return 10.0 ** (x / 20.0)


def gated_rms(mono, samplerate):
    """RMS of the parts that are actually speech.

    A plain whole-file RMS is useless here: Blind.mp3 is 36 seconds with
    long gaps, so the silence drags its measurement down and a normaliser
    trusting it would overshoot by several dB and slam the limiter. This is
    BS.1770's gating idea without the K-weighting -- measure in short
    windows, throw away the quiet ones, average what is left.
    """
    win = max(1, int(samplerate * WINDOW_MS / 1000))
    usable = len(mono) - (len(mono) % win)
    if usable < win:
        return math.sqrt(float(np.mean(mono.astype(np.float64) ** 2)))

    windows = mono[:usable].astype(np.float64).reshape(-1, win)
    power = np.mean(windows ** 2, axis=1)

    keep = power > undb(ABSOLUTE_GATE_DBFS) ** 2
    if not keep.any():
        keep = np.ones_like(power, dtype=bool)

    # Relative gate, measured against the mean of what survived the
    # absolute gate.
    threshold = np.mean(power[keep]) * (undb(-RELATIVE_GATE_DB) ** 2)
    keep &= power > threshold
    if not keep.any():
        keep = np.ones_like(power, dtype=bool)

    return math.sqrt(float(np.mean(power[keep])))


def soft_limit(x, ceiling):
    """Bend everything above the knee smoothly down to the ceiling.

    Hard clipping a speech peak puts a corner in the waveform and you hear
    it as a click. tanh approaches the ceiling asymptotically instead, so
    the output can never exceed it and the transition at the knee has no
    discontinuity in value or slope.
    """
    knee = ceiling * 0.7
    magnitude = np.abs(x)
    span = ceiling - knee
    shaped = np.where(
        magnitude <= knee,
        magnitude,
        knee + span * np.tanh((magnitude - knee) / span),
    )
    return (np.sign(x) * shaped).astype(np.float32)


def plan_gain(mono):
    """Decide how much to turn this clip up, and say why."""
    measured = gated_rms(mono, plan_gain.samplerate)
    peak = float(np.max(np.abs(mono))) or 1e-12

    wanted_db = TARGET_RMS_DBFS - db(measured)
    # Ceiling-respecting gain, plus the allowance we let the limiter eat.
    allowed_db = (CEILING_DBFS - db(peak)) + MAX_LIMITING_DB
    applied_db = min(wanted_db, allowed_db)
    # Never turn a clip down to hit the target; the point is more volume.
    applied_db = max(applied_db, 0.0)
    return measured, peak, wanted_db, applied_db


def process(path, apply_changes):
    name = os.path.basename(path)

    # Always read the pristine copy if we have one, so repeated --apply
    # runs are idempotent rather than cumulative.
    source = os.path.join(BACKUP_DIR, name)
    if not os.path.exists(source):
        source = path

    data, samplerate = sf.read(source, dtype="float32", always_2d=True)
    mono = data.mean(axis=1)

    plan_gain.samplerate = samplerate
    measured, peak, wanted_db, applied_db = plan_gain(mono)

    out = soft_limit(data * undb(applied_db), undb(CEILING_DBFS))
    new_rms = gated_rms(out.mean(axis=1), samplerate)

    note = ""
    if applied_db < wanted_db - 0.1:
        note = f"  (capped: wanted +{wanted_db:.1f})"
    print(f"{name:<14} {db(measured):>7.1f} -> {db(new_rms):>6.1f} dBFS RMS"
          f"   gain +{applied_db:.1f} dB"
          f"   peak {db(peak):>6.1f} -> {db(np.max(np.abs(out))):.1f}{note}")

    if not apply_changes:
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = os.path.join(BACKUP_DIR, name)
    if not os.path.exists(backup):
        shutil.copy2(path, backup)

    # squeeze() because soundfile wants (n,) for mono, not (n, 1).
    payload = out if out.shape[1] > 1 else out[:, 0]
    try:
        sf.write(path, payload, samplerate, format="MP3",
                 subtype="MPEG_LAYER_III", bitrate_mode="VARIABLE",
                 compression_level=0.2)
    except TypeError:
        # soundfile < 0.13 has no bitrate controls; the default is fine.
        sf.write(path, payload, samplerate, format="MP3",
                 subtype="MPEG_LAYER_III")


def main():
    global TARGET_RMS_DBFS

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="rewrite the files (default is a dry run)")
    parser.add_argument("--target", type=float, default=TARGET_RMS_DBFS,
                        help=f"target RMS in dBFS (default {TARGET_RMS_DBFS})")
    args = parser.parse_args()

    TARGET_RMS_DBFS = args.target

    if not os.path.isdir(SOUNDS_DIR):
        sys.exit(f"No Sounds directory at {SOUNDS_DIR}")

    clips = sorted(f for f in os.listdir(SOUNDS_DIR)
                   if f.lower().endswith((".mp3", ".wav")))
    if not clips:
        sys.exit(f"No clips found in {SOUNDS_DIR}")

    print(f"Target {TARGET_RMS_DBFS:.1f} dBFS RMS, ceiling {CEILING_DBFS:.1f} dBFS, "
          f"up to {MAX_LIMITING_DB:.0f} dB of limiting")
    print(f"{'file':<14} {'before':>7}    {'after':>6}\n")

    for clip in clips:
        process(os.path.join(SOUNDS_DIR, clip), args.apply)

    if args.apply:
        print(f"\nDone. Originals are in {BACKUP_DIR}")
    else:
        print("\nDry run -- nothing written. Re-run with --apply.")


if __name__ == "__main__":
    main()
