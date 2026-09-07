#!/usr/bin/env python3
"""Adapt the KAPATID-VIBE port to the parts actually used in this build.

  * vibration motor on a 3-pin module (VCC / IN / GND) instead of a
    TB6612FNG, so one GPIO replaces PWM + IN1 + IN2 + STBY
  * an LED strip that lights during Child Mode, switched by a driver

Run it on the pristine files from kapatid-pi4.zip. Safe to re-run.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def edit(name, *pairs):
    path = HERE / name
    text = path.read_text()
    for old, new in pairs:
        if new in text and old not in text:
            continue                      # already applied
        if old not in text:
            sys.exit(f"{name}: could not find the text to replace. "
                     "Re-extract kapatid-pi4.zip and try again.")
        text = text.replace(old, new)
    path.write_text(text)
    print(f"  patched {name}")


print("Applying build-specific changes...")

# --------------------------------------------------------------- config.py
edit("config.py", ("""# TB6612FNG motor driver.
#   PWM  -> PWMA
#   IN1  -> AIN1
#   IN2  -> AIN2
#   STBY -> STBY   (held low at boot so the motor cannot twitch on power-up)
PIN_MOTOR_PWM = 12
PIN_MOTOR_IN1 = 6
PIN_MOTOR_IN2 = 16
PIN_MOTOR_STBY = 26""", """# Vibration motor on a 3-pin module (VCC / IN / GND). This pin drives IN
# only; the module's own transistor switches the motor and its flyback diode
# absorbs the back-EMF, so no external driver is needed.
#
# VCC goes to the Pi's 3.3V rail, GND to Pi GND. Software PWM on this pin
# varies intensity. What is lost versus a TB6612FNG is active braking and
# direction, neither of which this build uses.
PIN_MOTOR = 12

# ---------------------------------------------------------------------------
# CHILD MODE INDICATOR LIGHT
# ---------------------------------------------------------------------------
# An LED strip that lights while Child Mode is selected, and goes dark for
# every other mode.
#
# IMPORTANT -- this pin SWITCHES the strip, it does not power it. Nine LEDs
# draw about 160 mA against a 16 mA pin limit, so it needs a driver:
# GPIO -> ULN2003 input (or an NPN base via 1k), strip - -> the matching
# output, strip + -> 5V. Unlike the motor, the strip has no driver of its
# own, so this is the one load still needing an external switch.
#
# Set to None if no light is fitted.
PIN_CHILD_LIGHT = 16

# Both a ULN2003 channel and a plain NPN transistor light the load when the
# pin goes HIGH. Set True only for an active-low part such as a relay board.
CHILD_LIGHT_ACTIVE_LOW = False"""))

edit("config.py", ("""# Motor intensity, 0.0-1.0.
# An eccentric-mass motor will not start below roughly 0.35-0.40, so each
# pulse kicks briefly to KICK_LEVEL before settling at MORSE_LEVEL.
MORSE_LEVEL = 0.85""", """# Motor intensity, 0.0-1.0. These values assume a 10 mm coin motor on a
# 3-pin module with VCC on the Pi's 3.3V rail, putting roughly 3V at the
# motor -- its rated figure. The GPIO supplies only a logic signal, a few
# milliamps; the motor's 80-100 mA comes off the 3.3V rail.
#
# An eccentric mass will not start from rest at low duty, so each pulse
# kicks briefly to KICK_LEVEL before settling at MORSE_LEVEL.
#
# If you run the module's VCC from 5V instead, the motor sees about 4.7V --
# over its rating -- so drop MORSE_LEVEL to about 0.55 to compensate.
MORSE_LEVEL = 0.85"""))

# ------------------------------------------------------------- hardware.py
path = HERE / "hardware.py"
text = path.read_text()

MOTOR = '''class Motor:
    """Vibration motor on a 3-pin module (VCC / IN / GND).

    The module carries its own switching transistor and flyback diode, so
    this class only has to drive a logic input. PWM on that input varies
    intensity. Braking and direction are gone with the TB6612FNG, and
    neither was used.
    """

    def __init__(self):
        self._pwm = None
        self._level = 0.0
        self._hardware_pwm = False

        if not ON_PI:
            return

        if config.PWM_MODE == "hardware":
            # Kernel sysfs PWM. Needs dtoverlay=pwm-2chan in config.txt.
            # chip=0 is correct for Pi 1-4. Channel 0 == GPIO12, 1 == GPIO13.
            from rpi_hardware_pwm import HardwarePWM
            channel = 0 if config.PIN_MOTOR == 12 else 1
            self._pwm = HardwarePWM(pwm_channel=channel,
                                    hz=config.PWM_FREQUENCY, chip=0)
            self._pwm.start(0)
            self._hardware_pwm = True
        else:
            # Thread-timed software PWM, which works on any GPIO. Perfectly
            # adequate here: an eccentric mass has 20-50 ms of mechanical
            # inertia and cannot respond to PWM jitter.
            from gpiozero import PWMOutputDevice
            self._pwm = PWMOutputDevice(config.PIN_MOTOR,
                                        frequency=config.PWM_SOFT_FREQUENCY,
                                        initial_value=0.0)

    def _apply(self, level):
        self._level = level
        if self._pwm is None:
            print(f"[MOTOR] {level:.2f}")
            return
        if self._hardware_pwm:
            self._pwm.change_duty_cycle(level * 100.0)
        else:
            self._pwm.value = level

    def on(self, level=None):
        """Spin the motor, kicking briefly to full power to break stiction."""
        level = config.MORSE_LEVEL if level is None else level
        if level < 1.0:
            self._apply(config.KICK_LEVEL)
            time.sleep(config.KICK_TIME)
        self._apply(level)

    def off(self):
        """Cut the drive. Without a TB6612 there is no active brake, so the
        mass coasts for a few tens of milliseconds -- well inside one Morse
        unit, so the pattern still reads correctly."""
        self._apply(0.0)

    def close(self):
        self.off()
        if self._pwm is not None:
            try:
                self._pwm.stop() if hasattr(self._pwm, "stop") \\
                    else self._pwm.close()
            except Exception:
                pass


# ===========================================================================
#  CHILD MODE LIGHT
# ===========================================================================

class Light:
    """Indicator light for Child Mode.

    The GPIO drives a ULN2003 input or a transistor base -- never the LED
    strip itself, which draws far more current than a pin can source.
    """

    def __init__(self):
        self._dev = None
        self._on = False

        if not ON_PI or config.PIN_CHILD_LIGHT is None:
            return

        from gpiozero import DigitalOutputDevice
        self._dev = DigitalOutputDevice(
            config.PIN_CHILD_LIGHT,
            active_high=not config.CHILD_LIGHT_ACTIVE_LOW,
            initial_value=False)

    def on(self):
        self._on = True
        if self._dev is not None:
            self._dev.on()
        else:
            print("[LIGHT] on")

    def off(self):
        self._on = False
        if self._dev is not None:
            self._dev.off()
        else:
            print("[LIGHT] off")

    def close(self):
        self.off()
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass


'''

if "class Light:" not in text:
    start = text.index("class Motor:")
    end = text.index("""# ===========================================================================
#  AUDIO""")
    text = text[:start] + MOTOR + text[end:]
    path.write_text(text)
print("  patched hardware.py")

# -------------------------------------------------------------- kapatid.py
edit("kapatid.py",
     ("""        self.audio = hardware.Audio()""",
      """        self.audio = hardware.Audio()
        self.light = hardware.Light()"""),
     ("""            self.lcd.show(*MESSAGES[name])

            if name == "deaf":""",
      """            self.lcd.show(*MESSAGES[name])

            # The indicator light tracks Child Mode and nothing else, so any
            # other press darkens it.
            if name == "child":
                self.light.on()
            else:
                self.light.off()

            if name == "deaf":"""),
     ("""        for part in (self.audio, self.motor, self.buttons, self.lcd):""",
      """        for part in (self.audio, self.motor, self.light, self.buttons,
                     self.lcd):"""))

# ------------------------------------------------------------ test_logic.py
edit("test_logic.py",
     ("""class FakeButtons:""",
      """class FakeLight:
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


class FakeButtons:"""),
     ("""            mock.patch.object(hardware, "Audio", FakeAudio),""",
      """            mock.patch.object(hardware, "Audio", FakeAudio),
            mock.patch.object(hardware, "Light", FakeLight),"""),
     ("""    # -- Morse table ------------------------------------------------------""",
      """    # -- Child mode light -------------------------------------------------

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
        \"\"\"Adding the light must not break the original audio behaviour.\"\"\"
        self.app.on_press("child")
        self.assertEqual(self.app.audio.played, ["Child.mp3"])

    # -- Morse table ------------------------------------------------------"""),
     ("""                config.PIN_MANDARIN, config.PIN_MOTOR_PWM,
                config.PIN_MOTOR_IN1, config.PIN_MOTOR_IN2,
                config.PIN_MOTOR_STBY]
        if config.PIN_SHUTDOWN is not None:
            pins.append(config.PIN_SHUTDOWN)""",
      """                config.PIN_MANDARIN, config.PIN_MOTOR]
        if config.PIN_SHUTDOWN is not None:
            pins.append(config.PIN_SHUTDOWN)
        if config.PIN_CHILD_LIGHT is not None:
            pins.append(config.PIN_CHILD_LIGHT)"""),
     ("""                config.PIN_MANDARIN, config.PIN_MOTOR_PWM,
                config.PIN_MOTOR_IN1, config.PIN_MOTOR_IN2,
                config.PIN_MOTOR_STBY]
        self.assertNotIn(2, pins)""",
      """                config.PIN_MANDARIN, config.PIN_MOTOR,
                config.PIN_CHILD_LIGHT]
        self.assertNotIn(2, pins)"""),
     ("""            self.assertIn(config.PIN_MOTOR_PWM, (12, 13, 18, 19))""",
      """            self.assertIn(config.PIN_MOTOR, (12, 13, 18, 19))"""))

print("\nDone. Now run:  ./venv/bin/python test_logic.py")