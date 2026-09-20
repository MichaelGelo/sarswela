"""
Hardware abstraction for KAPATID-VIBE.

Every piece of hardware is behind a small class here. On a Raspberry Pi the
real drivers load; anywhere else (your laptop, CI) they fall back to mocks
that print what they would have done. That means the whole state machine can
be tested before the board arrives.
"""

import sys
import threading
import time

import config

# --- Detect whether we are on real hardware -------------------------------

ON_PI = False
try:
    with open("/proc/device-tree/model", "rb") as handle:
        ON_PI = b"Raspberry Pi" in handle.read()
except OSError:
    ON_PI = False


# ===========================================================================
#  LCD
# ===========================================================================

class Lcd:
    """16x2 character LCD on an I2C backpack.

    Writes are serialised behind a lock. An I2C write takes a few
    milliseconds, which is far too slow to do from inside an audio callback,
    so only ever call this from the main thread or a button handler.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._last = None
        self._dev = None
        if ON_PI:
            from RPLCD.i2c import CharLCD
            self._dev = CharLCD(
                i2c_expander="PCF8574",
                address=config.LCD_ADDRESS,
                port=1,
                cols=config.LCD_COLS,
                rows=config.LCD_ROWS,
                charmap=config.LCD_CHARMAP,
                auto_linebreaks=False,
            )
            self._dev.clear()
            self._dev.backlight_enabled = True

    def show(self, line1, line2=""):
        """Display up to two lines. Repeated identical calls are ignored,
        which is what stopped the Arduino LCD from flickering."""
        payload = (line1[:config.LCD_COLS], line2[:config.LCD_COLS])
        with self._lock:
            if payload == self._last:
                return
            self._last = payload
            if self._dev is not None:
                # Overwrite with space-padded lines instead of clear().
                # clear() costs the HD44780 1.52ms and blanks the panel
                # first, which reads as a flicker on every mode change;
                # padding to the full width erases the old text just as
                # completely, in one pass.
                self._dev.cursor_pos = (0, 0)
                self._dev.write_string(payload[0].ljust(config.LCD_COLS))
                self._dev.cursor_pos = (1, 0)
                self._dev.write_string(payload[1].ljust(config.LCD_COLS))
            else:
                print(f"[LCD] {payload[0]!r} / {payload[1]!r}")

    def close(self):
        with self._lock:
            if self._dev is not None:
                self._dev.clear()
                self._dev.backlight_enabled = False
                self._dev.close()


# ===========================================================================
#  MOTOR  (TB6612FNG)
# ===========================================================================

class Motor:
    """Vibration motor on a 3-pin module (VCC / IN / GND).

    The module carries its own switching transistor and flyback diode, so
    this class only has to drive a logic input. PWM on that input varies
    intensity. Braking and direction are gone with the TB6612FNG, and
    neither was used.
    """

    def __init__(self):
        self._pwm = None
        self._digital = None
        self._level = 0.0
        self._hardware_pwm = False

        if not ON_PI:
            return

        if not config.MOTOR_PWM:
            # Plain on/off. Some vibration modules ignore a switching
            # waveform on IN entirely -- they run when the pin is held high
            # and stay dead under PWM at any duty. Morse needs only on and
            # off, so this costs nothing but MORSE_LEVEL.
            from gpiozero import DigitalOutputDevice
            self._digital = DigitalOutputDevice(config.PIN_MOTOR,
                                                initial_value=False)
        elif config.PWM_MODE == "hardware":
            # Kernel sysfs PWM. Needs dtoverlay=pwm-2chan in config.txt.
            # chip=0 is correct for Pi 1-4. Channel 0 == GPIO12, 1 == GPIO13.
            from rpi_hardware_pwm import HardwarePWM
            channel = 0 if config.PIN_MOTOR == 12 else 1
            self._pwm = HardwarePWM(pwm_channel=channel,
                                    hz=config.PWM_FREQUENCY, chip=0)
            self._pwm.start(0)
            self._hardware_pwm = True
        else:
            # Thread-timed software PWM, which works on any GPIO.
            from gpiozero import PWMOutputDevice
            self._pwm = PWMOutputDevice(config.PIN_MOTOR,
                                        frequency=config.PWM_SOFT_FREQUENCY,
                                        initial_value=0.0)

    def _apply(self, level):
        self._level = level

        if self._digital is not None:
            # Any non-zero level means "on" -- there are no shades here.
            self._digital.value = bool(level)
            return

        if self._pwm is None:
            print(f"[MOTOR] {level:.2f}")
            return

        if self._hardware_pwm:
            self._pwm.change_duty_cycle(level * 100.0)
        else:
            self._pwm.value = level

    def on(self, level=None):
        """Spin the motor, kicking briefly to full power to break stiction.

        Used by the non-textured Morse path. The textured path calls set()
        instead, because its bursts are shorter than KICK_TIME.
        """
        level = config.MORSE_LEVEL if level is None else level
        if config.MOTOR_PWM and level < 1.0:
            self._apply(config.KICK_LEVEL)
            time.sleep(config.KICK_TIME)
        self._apply(level)

    def set(self, level):
        """Apply a level with no stiction kick.

        The textured Morse burst train calls this: its bursts are shorter
        than KICK_TIME, so on()'s kick would swamp them and destroy the
        timing. Safe there because the mass is already turning -- stiction
        only has to be broken at the start of an element, not every burst.
        """
        self._apply(level)

    def off(self):
        """Cut the drive. Without a TB6612 there is no active brake, so the
        mass coasts for a few tens of milliseconds -- well inside one Morse
        unit, so the pattern still reads correctly."""
        self._apply(0.0)

    def close(self):
        self.off()
        if self._digital is not None:
            try:
                self._digital.close()
            except Exception:
                pass
        if self._pwm is not None:
            try:
                self._pwm.stop() if hasattr(self._pwm, "stop") \
                    else self._pwm.close()
            except Exception:
                pass


# ===========================================================================
#  CHILD MODE LIGHT
# ===========================================================================

class Light:
    """Indicator light for Child Mode.

    The GPIO drives a ULN2003 input, a transistor base, or a relay module's
    input -- never the LED strip itself, which draws far more current than a
    pin can source.

    Two switching styles, selected by config:

      push-pull (default)  drive HIGH for one state, LOW for the other.
      open-drain           drive LOW for on, RELEASE the pin for off.

    Open-drain exists for 5V-coil low-trigger relay modules, which a 3.3V
    pin cannot release by driving high. See CHILD_LIGHT_OPEN_DRAIN.
    """

    def __init__(self):
        self._dev = None
        self._pin = None
        self._open_drain = False
        self._on = False

        if not ON_PI or config.PIN_CHILD_LIGHT is None:
            return

        from gpiozero import DigitalOutputDevice
        self._dev = DigitalOutputDevice(
            config.PIN_CHILD_LIGHT,
            active_high=not config.CHILD_LIGHT_ACTIVE_LOW,
            initial_value=False)

        self._open_drain = bool(getattr(config, "CHILD_LIGHT_OPEN_DRAIN",
                                        False))
        if self._open_drain:
            # Hold the underlying pin so its direction can be changed.
            # gpiozero has no open-drain mode, but its pin objects expose
            # `function`, which is all this needs.
            self._pin = self._dev.pin
            self._release()

    def _release(self):
        """Float the pin, letting an external pull-up set the level."""
        try:
            self._pin.function = "input"
        except Exception as exc:                    # pragma: no cover
            print(f"[LIGHT] cannot release pin ({exc}); using push-pull",
                  file=sys.stderr)
            self._open_drain = False

    def _drive_low(self):
        try:
            self._pin.function = "output"
            self._pin.state = 0
        except Exception as exc:                    # pragma: no cover
            print(f"[LIGHT] cannot drive pin ({exc})", file=sys.stderr)

    def on(self):
        self._on = True
        if self._dev is None:
            print("[LIGHT] on")
        elif self._open_drain:
            self._drive_low()
        else:
            self._dev.on()

    def off(self):
        self._on = False
        if self._dev is None:
            print("[LIGHT] off")
        elif self._open_drain:
            self._release()
        else:
            self._dev.off()

    def close(self):
        self.off()
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass


# ===========================================================================
#  AUDIO
# ===========================================================================

class Audio:
    """Plays the narration clips.

    Streams from disk rather than loading whole files, so a long clip cannot
    exhaust the Pi 3 B+'s 1 GB of RAM.
    """

    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._sd = None
        self._sf = None
        self._np = None
        self._gain = 1.0
        try:
            import numpy
            import sounddevice
            import soundfile
            self._np = numpy
            self._sd = sounddevice
            self._sf = soundfile
        except Exception as exc:                    # pragma: no cover
            print(f"[AUDIO] library unavailable ({exc}); running silent",
                  file=sys.stderr)
            return
        self._gain = max(0.0, float(getattr(config, "VOLUME", 1.0)))
        if self._gain != 1.0:
            print(f"[AUDIO] volume x{self._gain:.2f}")
        self._select_device()

    def _select_device(self):
        """Resolve AUDIO_DEVICE now, at startup, rather than at first clip.

        Assigning sounddevice.default.device does NOT validate the name --
        PortAudio only resolves it when a stream is opened. So a name that
        matches nothing produces no startup error, and then fails every
        single clip for the rest of the run, printing to stderr where nobody
        looks. From the outside that is indistinguishable from broken
        speakers.

        So probe the name once, report it once with the list of what IS
        available, and fall back to the system default -- degraded audio
        beats no audio, and the message says what to fix.
        """
        wanted = config.AUDIO_DEVICE
        if not wanted:
            return                  # inherit whatever the OS already uses

        try:
            self._sd.query_devices(wanted, "output")
        except Exception as exc:
            outputs = []
            try:
                outputs = sorted({d["name"] for d in self._sd.query_devices()
                                  if d["max_output_channels"] > 0})
            except Exception:
                pass
            print(f"[AUDIO] AUDIO_DEVICE={wanted!r} matches no output device "
                  f"({exc}). Falling back to the system default. "
                  f"Outputs found: {outputs or 'none'}", file=sys.stderr)
            return

        self._sd.default.device = wanted
        print(f"[AUDIO] using {wanted!r}")

    # Above this the limiter starts bending the waveform. Below it, audio
    # passes through untouched, so VOLUME = 1.0 on a normalised clip is
    # bit-for-bit what is on disk.
    _LIMIT_KNEE = 0.7

    def _amplify(self, block):
        """Apply VOLUME, then keep the result inside full scale.

        Multiplying by the gain alone would wrap or clip hard at the driver,
        and a clipped speech peak is a click you can hear across the room.
        So anything past the knee is bent towards 1.0 along a tanh curve,
        which is asymptotic -- the output cannot reach full scale, let alone
        exceed it -- and joins the linear region smoothly, with no corner to
        make a click out of. Loud passages compress instead of tearing.
        """
        block = block * self._gain
        if self._gain <= 1.0:
            return block

        np = self._np
        knee = self._LIMIT_KNEE
        span = 1.0 - knee
        magnitude = np.abs(block)
        shaped = np.where(
            magnitude <= knee,
            magnitude,
            knee + span * np.tanh((magnitude - knee) / span),
        )
        return (np.sign(block) * shaped).astype("float32")

    def _worker(self, path):
        try:
            with self._sf.SoundFile(path) as handle:
                stream = self._sd.OutputStream(
                    samplerate=handle.samplerate,
                    channels=handle.channels,
                    dtype="float32",
                )
                with stream:
                    for block in handle.blocks(blocksize=2048,
                                               dtype="float32"):
                        if self._stop.is_set():
                            break
                        stream.write(self._amplify(block))
        except Exception as exc:                    # pragma: no cover
            print(f"[AUDIO] playback of {path} failed: {exc}",
                  file=sys.stderr)

    def play(self, path):
        """Start a clip, cutting off whatever was already playing."""
        self.stop()
        if self._sd is None or self._sf is None:
            print(f"[AUDIO] play {path}")
            return
        with self._lock:
            self._stop = threading.Event()
            self._thread = threading.Thread(
                target=self._worker, args=(path,), daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            thread, event = self._thread, self._stop
        if thread is not None and thread.is_alive():
            event.set()
            thread.join(timeout=1.0)
        if self._sd is None:
            print("[AUDIO] stop")

    def close(self):
        self.stop()


# ===========================================================================
#  BUTTONS
# ===========================================================================

class Buttons:
    """The seven mode buttons, wired pin -> switch -> GND as before.

    Note on debounce: the modern lgpio backend treats bounce_time as "the
    signal must be stable for this long before I report it", which is the
    opposite of old RPi.GPIO's "ignore further edges for this long". The
    practical effect is the same for a human pressing a button.
    """

    NAMES = ("deaf", "blind", "child", "foreign",
             "english", "indian", "mandarin")

    def __init__(self, on_press, on_release=None):
        self._devices = {}
        pins = {
            "deaf": config.PIN_DEAF,
            "blind": config.PIN_BLIND,
            "child": config.PIN_CHILD,
            "foreign": config.PIN_FOREIGN,
            "english": config.PIN_ENGLISH,
            "indian": config.PIN_INDIAN,
            "mandarin": config.PIN_MANDARIN,
        }
        if not ON_PI:
            print("[BUTTONS] mock mode")
            return

        from gpiozero import Button
        for name, pin in pins.items():
            button = Button(pin, pull_up=True, bounce_time=config.BOUNCE_TIME)
            button.when_pressed = (lambda n=name: on_press(n))
            if on_release is not None:
                button.when_released = (lambda n=name: on_release(n))
            self._devices[name] = button

        if config.PIN_SHUTDOWN is not None:
            holder = Button(config.PIN_SHUTDOWN, pull_up=True, hold_time=2.0)
            holder.when_held = self._shutdown
            self._devices["shutdown"] = holder

    @staticmethod
    def _shutdown():
        import subprocess
        print("[SYSTEM] shutdown requested")
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)

    def close(self):
        for device in self._devices.values():
            try:
                device.close()
            except Exception:
                pass
