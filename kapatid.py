#!/usr/bin/env python3
"""
KAPATID-VIBE — Raspberry Pi controller.

A direct port of the Arduino sketch (src/main.cpp) plus the laptop-side
audio player (audio_player.py), merged into one program. The laptop and the
serial link are gone; everything runs on the Pi.

Feature parity with the Arduino version:
  * seven mode buttons with internal pull-ups
  * 16x2 I2C LCD showing all eight of the original messages
  * "Sarswela" in Morse code on the haptic motor, in deaf mode
  * Morse is interruptible: pressing any other button cancels it
  * deaf button is edge-detected, so Morse plays once per press
  * the foreign-language gate: press Foreign before English/Spanish/Mandarin
  * starting a clip stops whatever was playing
  * "Select a mode" shows until the first press

Differences, all deliberate:
  * the relay is replaced by a TB6612FNG driver, so vibration has variable
    intensity, brakes cleanly and makes no clicking noise
  * buttons are event-driven rather than polled, so nothing blocks
  * no serial protocol, no COM port detection, no reconnect loop
"""

import os
import signal
import sys
import threading
import time

import config
import hardware

HERE = os.path.dirname(os.path.abspath(__file__))

MORSE_TABLE = {
    "A": ".-",    "B": "-...",  "C": "-.-.",  "D": "-..",   "E": ".",
    "F": "..-.",  "G": "--.",   "H": "....",  "I": "..",    "J": ".---",
    "K": "-.-",   "L": ".-..",  "M": "--",    "N": "-.",    "O": "---",
    "P": ".--.",  "Q": "--.-",  "R": ".-.",   "S": "...",   "T": "-",
    "U": "..-",   "V": "...-",  "W": ".--",   "X": "-..-",  "Y": "-.--",
    "Z": "--..",
}

# The eight LCD states from the Arduino's displayMessage().
MESSAGES = {
    "deaf":     ("Deaf Mode", ""),
    "blind":    ("Blind Mode", ""),
    "child":    ("Child Mode", ""),
    "foreign":  ("Foreign Lang", "Mode"),
    "english":  ("English", ""),
    "spanish":  ("Spanish", ""),
    "mandarin": ("Mandarin", ""),
    "idle":     ("Select a mode", ""),
}


class Kapatid:
    def __init__(self):
        self.lcd = hardware.Lcd()
        self.motor = hardware.Motor()
        self.audio = hardware.Audio()
        self.light = hardware.Light()

        # Mirrors the Arduino's `foreignGate`: English/Spanish/Mandarin are
        # ignored until the Foreign button has been pressed.
        self.foreign_gate = False

        # Mirrors `anyPressed`: once something is pressed we stop showing
        # the idle prompt.
        self.any_pressed = False

        # Morse runs on its own thread so a long sequence never blocks the
        # button handlers. `_morse_cancel` is this port's equivalent of the
        # Arduino's interruptibleDelay() polling.
        self._morse_thread = None
        self._morse_cancel = threading.Event()
        self._lock = threading.RLock()
        self._running = True

        self.buttons = hardware.Buttons(self.on_press)
        self.lcd.show(*MESSAGES["idle"])

    # -- Morse ------------------------------------------------------------

    def _sleep(self, seconds):
        """Interruptible wait. Returns True if cancelled part-way."""
        return self._morse_cancel.wait(timeout=seconds)

    def _buzz(self, duration):
        """Drive the motor for `duration`, leaving it off. True if cancelled.

        With config.MORSE_TEXTURE the element is delivered as a burst train
        instead of a steady hold. Peak amplitude is unchanged -- the motor
        still reaches MORSE_LEVEL -- but the skin cannot adapt to it, which
        is what makes the same power feel stronger. The first burst goes
        through motor.on() so its stiction kick still applies; the rest use
        motor.set(), since the mass is turning by then and a kick per burst
        would be longer than the burst itself.
        """
        if not config.MORSE_TEXTURE:
            self.motor.on(config.MORSE_LEVEL)
            cancelled = self._sleep(duration)
            self.motor.off()
            return cancelled

        period = 1.0 / config.MORSE_TEXTURE_HZ
        on_span = period * config.MORSE_TEXTURE_DUTY
        off_span = period - on_span

        remaining = duration
        first = True
        try:
            while remaining > 0:
                span = min(on_span, remaining)
                if first:
                    self.motor.on(config.MORSE_LEVEL)
                    first = False
                else:
                    self.motor.set(config.MORSE_LEVEL)
                if self._sleep(span):
                    return True
                remaining -= span
                if remaining <= 0:
                    break
                span = min(off_span, remaining)
                self.motor.set(0.0)
                if self._sleep(span):
                    return True
                remaining -= span
        finally:
            self.motor.off()
        return False

    def _play_morse(self, text):
        unit = config.MORSE_UNIT
        try:
            for char in text.upper():
                if char == " ":
                    if self._sleep(unit * 7):
                        return
                    continue
                pattern = MORSE_TABLE.get(char)
                if pattern is None:
                    continue
                for symbol in pattern:
                    length = unit if symbol == "." else unit * 3
                    if self._buzz(length):
                        return
                    if self._sleep(unit):
                        return
                if self._sleep(unit * 3):     # gap between letters
                    return
        finally:
            self.motor.off()

    def start_morse(self, text):
        self.cancel_morse()
        self._morse_cancel = threading.Event()
        self._morse_thread = threading.Thread(
            target=self._play_morse, args=(text,), daemon=True)
        self._morse_thread.start()

    def cancel_morse(self):
        thread = self._morse_thread
        if thread is not None and thread.is_alive():
            self._morse_cancel.set()
            thread.join(timeout=2.0)
        self._morse_thread = None

    # -- Buttons ----------------------------------------------------------

    def on_press(self, name):
        with self._lock:
            if not self._running:
                return

            # The gate: language buttons do nothing until Foreign is armed.
            if name in ("english", "spanish", "mandarin") \
                    and not self.foreign_gate:
                return

            # The indicator light tracks Child Mode and nothing else, so any
            # other press darkens it.
            #
            # This runs FIRST, before cancelling Morse and before the LCD.
            # Both of those take real time -- joining the Morse thread, and
            # an I2C write of 32 characters -- and a light that lags a
            # button by a tenth of a second reads as a fault. Setting one
            # GPIO costs microseconds, so nothing is gained by making it
            # queue behind the slow work.
            if name == "child":
                self.light.on()
            else:
                self.light.off()

            # Any press cancels a Morse sequence in progress. This is what
            # the Arduino's interruptibleDelay()/otherButtonPressed() did.
            self.cancel_morse()

            self.any_pressed = True
            self.foreign_gate = name in ("foreign", "english",
                                         "spanish", "mandarin")
            self.lcd.show(*MESSAGES[name])

            if name == "deaf":
                self.audio.stop()
                self.start_morse(config.MORSE_TEXT)
            elif name == "foreign":
                self.audio.stop()
            else:
                filename = config.AUDIO_FILES.get(name)
                if filename:
                    self.audio.play(os.path.join(
                        HERE, config.SOUNDS_DIR, filename))

    # -- Lifecycle --------------------------------------------------------

    def run(self):
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        print("KAPATID-VIBE ready. Waiting for button presses.")
        try:
            while not stop.is_set():
                stop.wait(timeout=0.5)
        finally:
            self.close()

    def close(self):
        with self._lock:
            self._running = False
        print("\nShutting down.")
        self.cancel_morse()
        for part in (self.audio, self.motor, self.light, self.buttons,
                     self.lcd):
            try:
                part.close()
            except Exception as exc:
                print(f"  cleanup warning: {exc}", file=sys.stderr)


def main():
    missing = []
    for filename in config.AUDIO_FILES.values():
        if not os.path.exists(os.path.join(HERE, config.SOUNDS_DIR, filename)):
            missing.append(filename)
    if missing:
        print(f"Warning: missing audio files: {', '.join(missing)}",
              file=sys.stderr)

    if config.PWM_MODE == "hardware" and config.AUDIO_DEVICE == "Headphones":
        print("WARNING: hardware PWM together with the 3.5mm jack is not "
              "guaranteed. On a Pi 4 the jack (pwm1) and GPIO12/13 (pwm0) "
              "are separate controllers, but they share a clock generator "
              "and Raspberry Pi still warns against mixing them. Verify "
              "with `speaker-test -c2 -t wav` while the motor runs, or set "
              "PWM_MODE='software'.", file=sys.stderr)

    Kapatid().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
