#!/usr/bin/env python3
"""
Behavioural tests: does the Pi port do what the Arduino sketch did?

Runs anywhere (no Pi needed). Each test asserts against the behaviour of
src/main.cpp so we can prove parity before buying hardware.
"""

import sys
import time
import unittest
from unittest import mock

import config
import hardware
import kapatid


class FakeLcd:
    def __init__(self):
        self.history = []

    def show(self, line1, line2=""):
        entry = (line1, line2)
        if not self.history or self.history[-1] != entry:
            self.history.append(entry)

    def close(self):
        pass


class FakeMotor:
    def __init__(self):
        self.events = []
        self.on_count = 0

    def on(self, level=None):
        self.on_count += 1
        self.events.append(("on", level))

    def set(self, level):
        self.events.append(("set", level))
        if level:
            self.on_count += 1

    def off(self):
        self.events.append(("off", None))

    def close(self):
        pass


class FakeAudio:
    def __init__(self):
        self.played = []
        self.stops = 0

    def play(self, path):
        # Mirrors the real Audio.play(), which cuts off the previous clip
        # before starting a new one.
        self.stop()
        self.played.append(path.split("/")[-1])

    def stop(self):
        self.stops += 1

    def close(self):
        pass


class FakeLight:
    def __init__(self):
        self.state = False
        self.history = []

    def on(self):
        self.state = True
        self.history.append(True)

    def off(self):
        self.state = False
        self.history.append(False)

    def close(self):
        self.off()


class FakeButtons:
    def __init__(self, on_press, on_release=None):
        self.on_press = on_press

    def close(self):
        pass


class ParityTests(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(hardware, "Lcd", FakeLcd),
            mock.patch.object(hardware, "Motor", FakeMotor),
            mock.patch.object(hardware, "Audio", FakeAudio),
            mock.patch.object(hardware, "Light", FakeLight),
            mock.patch.object(hardware, "Buttons", FakeButtons),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.app = kapatid.Kapatid()
        self.addCleanup(self.app.close)

    # -- LCD --------------------------------------------------------------

    def test_idle_message_on_startup(self):
        """Arduino calls displayMessage(7) in setup()."""
        self.assertEqual(self.app.lcd.history[0], ("Select a mode", ""))

    def test_all_eight_lcd_states_reachable(self):
        expected = {
            "deaf": ("Deaf Mode", ""),
            "blind": ("Blind Mode", ""),
            "child": ("Child Mode", ""),
            "foreign": ("Foreign Lang", "Mode"),
            "english": ("English", ""),
            "spanish": ("Spanish", ""),
            "mandarin": ("Mandarin", ""),
        }
        self.app.on_press("foreign")   # arm the gate for the language modes
        for name, text in expected.items():
            self.app.on_press(name)
            self.assertEqual(self.app.lcd.history[-1], text,
                             f"LCD wrong for {name}")

    def test_repeated_identical_writes_are_suppressed(self):
        """Arduino guards with `if (state == lastState) return;`"""
        self.app.on_press("blind")
        before = len(self.app.lcd.history)
        self.app.on_press("blind")
        self.assertEqual(len(self.app.lcd.history), before)

    # -- Foreign-language gate -------------------------------------------

    def test_language_buttons_ignored_before_foreign(self):
        """`foreignGate` starts false, so these must do nothing."""
        for name in ("english", "spanish", "mandarin"):
            self.app.on_press(name)
        self.assertEqual(self.app.audio.played, [])
        self.assertEqual(self.app.lcd.history[-1], ("Select a mode", ""))

    def test_language_buttons_work_after_foreign(self):
        self.app.on_press("foreign")
        self.app.on_press("english")
        self.assertEqual(self.app.audio.played, ["English.mp3"])

    def test_gate_closes_when_another_mode_chosen(self):
        """Arduino sets foreignGate = false in the deaf/blind/child branches."""
        self.app.on_press("foreign")
        self.app.on_press("blind")
        self.app.on_press("spanish")     # gate should now be shut
        self.assertNotIn("Spanish.mp3", self.app.audio.played)

    # -- Audio ------------------------------------------------------------

    def test_each_mode_plays_the_right_clip(self):
        self.app.on_press("blind")
        self.app.on_press("child")
        self.app.on_press("foreign")
        self.app.on_press("english")
        self.app.on_press("spanish")
        self.app.on_press("mandarin")
        self.assertEqual(
            self.app.audio.played,
            ["Blind.mp3", "Child.mp3", "English.mp3",
             "Spanish.mp3", "Mandarin.mp3"])

    def test_new_clip_stops_the_previous_one(self):
        """audio_player.py calls sd.stop() before every sd.play()."""
        self.app.on_press("blind")
        self.app.on_press("child")
        self.assertGreaterEqual(self.app.audio.stops, 1)

    def test_deaf_and_foreign_send_stop(self):
        """Both emitted Serial 'STOP' on the Arduino."""
        self.app.on_press("blind")
        before = self.app.audio.stops
        self.app.on_press("deaf")
        self.assertGreater(self.app.audio.stops, before)
        before = self.app.audio.stops
        self.app.on_press("foreign")
        self.assertGreater(self.app.audio.stops, before)

    # -- Morse ------------------------------------------------------------

    def test_deaf_mode_drives_the_motor(self):
        self.app.on_press("deaf")
        time.sleep(0.5)
        self.assertGreater(self.app.motor.on_count, 0)

    def test_morse_is_interrupted_by_another_button(self):
        """The Arduino's interruptibleDelay() aborted Morse on any press.

        "Sarswela" is ~50 units; at 150 ms that is over 7 seconds. If the
        cancel works, pressing Blind returns almost immediately and the
        motor stops.
        """
        self.app.on_press("deaf")
        time.sleep(0.3)
        started = time.monotonic()
        self.app.on_press("blind")
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 1.0, "cancel took too long")
        self.assertFalse(self.app._morse_thread
                         and self.app._morse_thread.is_alive())
        self.assertEqual(self.app.motor.events[-1][0], "off",
                         "motor must be left braked")

    def test_morse_restarts_cleanly_on_second_press(self):
        """Arduino re-arms via `if (digitalRead(deaf_mode) == HIGH)`."""
        self.app.on_press("deaf")
        time.sleep(0.2)
        self.app.on_press("deaf")
        time.sleep(0.2)
        self.assertTrue(self.app._morse_thread.is_alive())

    def test_motor_is_off_after_shutdown(self):
        self.app.on_press("deaf")
        time.sleep(0.2)
        self.app.close()
        self.assertEqual(self.app.motor.events[-1][0], "off")

    # -- Motor supply safety ----------------------------------------------

    def _motor_volts(self):
        """(peak, average) volts at the motor for the current config."""
        effective = config.MOTOR_SUPPLY_V - config.MOTOR_DROP_V
        peak = effective * config.MORSE_LEVEL
        duty = config.MORSE_TEXTURE_DUTY if config.MORSE_TEXTURE else 1.0
        return peak, peak * duty

    def test_motor_average_is_within_rating(self):
        """Sustained average must not exceed what the motor is specified for.

        This is what cooks a coin motor -- not brief peaks. Change the rail
        without changing MORSE_LEVEL and this test says so.
        """
        _, average = self._motor_volts()
        limit = config.MOTOR_RATED_V * 1.05
        self.assertLessEqual(
            average, limit,
            f"average {average:.2f}V exceeds {limit:.2f}V. "
            f"MOTOR_SUPPLY_V={config.MOTOR_SUPPLY_V} with "
            f"MORSE_LEVEL={config.MORSE_LEVEL} is too much -- lower "
            f"MORSE_LEVEL to about "
            f"{config.MOTOR_RATED_V / (config.MOTOR_SUPPLY_V - config.MOTOR_DROP_V) / (config.MORSE_TEXTURE_DUTY if config.MORSE_TEXTURE else 1.0):.2f}")

    def test_motor_peak_is_a_deliberate_overdrive_at_most(self):
        """Peaks above rating are allowed -- Morse is intermittent -- but
        only within reason. 1.5x is the line between 'strong' and 'brief
        life'."""
        peak, _ = self._motor_volts()
        limit = config.MOTOR_RATED_V * 1.5
        self.assertLessEqual(peak, limit,
                             f"peak {peak:.2f}V exceeds {limit:.2f}V")

    def test_supply_is_a_real_rail(self):
        self.assertIn(config.MOTOR_SUPPLY_V, (3.3, 5.0),
                      "the header only offers 3.3V and 5V")

        # -- Responsiveness ---------------------------------------------------

    def test_light_is_updated_before_the_slow_work(self):
        """The light must not queue behind the LCD's I2C write.

        Setting a GPIO takes microseconds; clearing and rewriting 32
        characters over I2C takes tens of milliseconds. If the light waits
        for that, releasing a relay visibly lags the button.
        """
        order = []
        self.app.light.on = lambda: order.append("light")
        self.app.light.off = lambda: order.append("light")
        real_show = self.app.lcd.show
        def traced(*a, **k):
            order.append("lcd")
            return real_show(*a, **k)
        self.app.lcd.show = traced

        self.app.on_press("blind")
        self.assertEqual(order, ["light", "lcd"],
                         "light must be set before the LCD write")

    def test_bounce_time_stays_responsive(self):
        """Debounce is latency paid on every press, so it has a ceiling."""
        self.assertGreater(config.BOUNCE_TIME, 0.0)
        self.assertLessEqual(config.BOUNCE_TIME, 0.05,
                             "above ~50ms the delay before the light and "
                             "motor respond becomes noticeable")

    def test_every_non_child_mode_darkens_the_light(self):
        """Exhaustive, not just a sample: any mode but child must go dark."""
        for name in ("deaf", "blind", "foreign"):
            self.app.on_press("child")
            self.assertTrue(self.app.light.state)
            self.app.on_press(name)
            self.assertFalse(self.app.light.state,
                             f"{name} must darken the child light")

    # -- Textured buzz ----------------------------------------------------

    def test_texture_chops_an_element_into_bursts(self):
        """A textured dot must drive the motor more than once."""
        config.MORSE_TEXTURE = True
        self.app._buzz(config.MORSE_UNIT)
        drives = [e for e in self.app.motor.events if e[0] in ("on", "set")
                  and e[1]]
        self.assertGreater(len(drives), 1,
                           "textured buzz should be a burst train")

    def test_texture_off_holds_steady(self):
        """Without texture, one element is a single continuous drive."""
        config.MORSE_TEXTURE = False
        try:
            self.app._buzz(config.MORSE_UNIT)
            drives = [e for e in self.app.motor.events
                      if e[0] in ("on", "set") and e[1]]
            self.assertEqual(len(drives), 1)
        finally:
            config.MORSE_TEXTURE = True

    def test_texture_reaches_full_level(self):
        """Texture must not quietly reduce amplitude -- it trades duty, not
        peak. Every drive is at MORSE_LEVEL."""
        self.app._buzz(config.MORSE_UNIT)
        levels = [e[1] for e in self.app.motor.events
                  if e[0] in ("on", "set") and e[1]]
        self.assertTrue(levels)
        for level in levels:
            self.assertEqual(level, config.MORSE_LEVEL)

    def test_buzz_leaves_the_motor_off(self):
        self.app._buzz(config.MORSE_UNIT)
        self.assertEqual(self.app.motor.events[-1][0], "off")

    def test_texture_duty_and_rate_are_sane(self):
        self.assertGreater(config.MORSE_TEXTURE_HZ, 0)
        self.assertLess(config.MORSE_TEXTURE_HZ, 60,
                        "above ~40Hz the mass cannot follow, so there is no "
                        "perceptual gain")
        self.assertGreater(config.MORSE_TEXTURE_DUTY, 0.0)
        self.assertLessEqual(config.MORSE_TEXTURE_DUTY, 1.0)

    # -- Child mode light -------------------------------------------------

    def test_child_mode_lights_the_strip(self):
        self.app.on_press("child")
        self.assertTrue(self.app.light.state)

    def test_light_goes_dark_when_another_mode_is_chosen(self):
        self.app.on_press("child")
        self.app.on_press("blind")
        self.assertFalse(self.app.light.state)

    def test_light_stays_dark_for_modes_other_than_child(self):
        for name in ("deaf", "blind", "foreign", "english"):
            self.app.on_press(name)
            self.assertFalse(self.app.light.state,
                             f"light must be off for {name}")

    def test_light_survives_repeated_child_presses(self):
        self.app.on_press("child")
        self.app.on_press("child")
        self.assertTrue(self.app.light.state)

    def test_light_is_off_after_shutdown(self):
        self.app.on_press("child")
        self.app.close()
        self.assertFalse(self.app.light.state)

    def test_child_mode_still_plays_its_clip(self):
        """Adding the light must not break the original audio behaviour."""
        self.app.on_press("child")
        self.assertEqual(self.app.audio.played, ["Child.mp3"])

    # -- Morse table ------------------------------------------------------

    def test_morse_table_matches_arduino(self):
        arduino = [
            ".-", "-...", "-.-.", "-..", ".", "..-.", "--.", "....", "..",
            ".---", "-.-", ".-..", "--", "-.", "---", ".--.", "--.-", ".-.",
            "...", "-", "..-", "...-", ".--", "-..-", "-.--", "--..",
        ]
        for index, pattern in enumerate(arduino):
            letter = chr(ord("A") + index)
            self.assertEqual(kapatid.MORSE_TABLE[letter], pattern,
                             f"Morse mismatch for {letter}")

    def test_sarswela_encodes_correctly(self):
        expected = "... .- .-. ... .-- . .-.. .-"
        actual = " ".join(kapatid.MORSE_TABLE[c]
                          for c in config.MORSE_TEXT.upper())
        self.assertEqual(actual, expected)

    # -- Config sanity ----------------------------------------------------

    def test_no_duplicate_gpio_pins(self):
        pins = [config.PIN_DEAF, config.PIN_BLIND, config.PIN_CHILD,
                config.PIN_FOREIGN, config.PIN_ENGLISH, config.PIN_SPANISH,
                config.PIN_MANDARIN, config.PIN_MOTOR]
        if config.PIN_SHUTDOWN is not None:
            pins.append(config.PIN_SHUTDOWN)
        if config.PIN_CHILD_LIGHT is not None:
            pins.append(config.PIN_CHILD_LIGHT)
        self.assertEqual(len(pins), len(set(pins)), "duplicate GPIO assigned")

    def test_no_pin_collides_with_i2c(self):
        """GPIO2/3 belong to the LCD bus and must not be reused."""
        pins = [config.PIN_DEAF, config.PIN_BLIND, config.PIN_CHILD,
                config.PIN_FOREIGN, config.PIN_ENGLISH, config.PIN_SPANISH,
                config.PIN_MANDARIN, config.PIN_MOTOR,
                config.PIN_CHILD_LIGHT]
        self.assertNotIn(2, pins)
        self.assertNotIn(3, pins)

    def test_hardware_pwm_uses_a_real_pwm_pin(self):
        if config.PWM_MODE == "hardware":
            self.assertIn(config.PIN_MOTOR, (12, 13, 18, 19))

    def test_hardware_pwm_not_combined_with_the_headphone_jack(self):
        """The 3.5mm jack IS the PWM peripheral. Both is impossible."""
        if config.PWM_MODE == "hardware":
            self.assertNotEqual(config.AUDIO_DEVICE, "Headphones")


if __name__ == "__main__":
    unittest.main(verbosity=2)
