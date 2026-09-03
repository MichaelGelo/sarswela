"""
KAPATID-VIBE — configuration for Raspberry Pi 4 Model B (4GB).

Everything you might need to change lives in this file.
Check AUDIO_DEVICE after your first run; everything else has a safe default.
"""

# ---------------------------------------------------------------------------
# AUDIO
# ---------------------------------------------------------------------------
# Which sound card to play through.
#
#   None            -> system default (risky: may pick HDMI)
#   "Headphones"    -> the Pi 4's built-in 3.5mm jack. Works, but it is an
#                      11-bit PWM/sigma-delta output with dither, so it
#                      hisses noticeably.
#   "USB"           -> a USB audio adapter. RECOMMENDED. About PHP 300 and
#                      the single biggest audio-quality gain available to
#                      this build. Draws ~50-100 mA of the Pi 4's 1.2 A
#                      USB budget, which you are not otherwise using.
#
# Run `python3 -m sounddevice` on the Pi to list exact names.
#
# NOTE: Raspberry Pi OS uses PipeWire. If PipeWire is holding the card,
# opening a raw "hw:0,0" fails. Prefer the name shown by the command above,
# or "default" / "pulse".
AUDIO_DEVICE = "USB"

# ---------------------------------------------------------------------------
# MOTOR PWM MODE
# ---------------------------------------------------------------------------
# "software" is the default and the right choice for a vibration motor.
#
# Why: an eccentric-mass motor has 20-50 ms of mechanical inertia, so it
# physically cannot respond to PWM jitter. Software PWM is entirely adequate,
# needs no device-tree overlay, and avoids a subtlety explained below.
#
# The subtlety, for the record: on a Pi 3 the 3.5mm jack and hardware PWM
# share one PWM controller and genuinely conflict. On a Pi 4 (BCM2711) there
# are TWO independent PWM controllers -- the jack sits on pwm1/GPIO40-41
# while `dtoverlay=pwm-2chan` drives pwm0/GPIO12-13 -- so the channel-level
# conflict is gone. However both blocks are fed from one shared clock
# generator, and Raspberry Pi still ships this warning for BCM2711:
#     "The onboard analogue audio output uses both PWM channels.
#      So be careful mixing audio and PWM."
# Rather than rely on that being benign, use software PWM. If you switch to
# "hardware", add to /boot/firmware/config.txt:
#     dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
# and then verify audio still works:  speaker-test -c2 -t wav
PWM_MODE = "software"

PWM_SOFT_FREQUENCY = 1000   # Hz. Used in "software" mode.
PWM_FREQUENCY = 20000       # Hz. Used in "hardware" mode only.

# ---------------------------------------------------------------------------
# GPIO PIN MAP  (BCM numbering)
# ---------------------------------------------------------------------------
# The Pi 4 header is fully backwards compatible with the Pi 3, so this map
# is identical on either board.
#
# Buttons wire exactly as they did on the Arduino: pin -> button -> GND.
# Internal pull-ups are enabled in software, no resistors needed.
PIN_DEAF = 17
PIN_BLIND = 27
PIN_CHILD = 22
PIN_FOREIGN = 23
PIN_ENGLISH = 24
PIN_SPANISH = 25
PIN_MANDARIN = 5

# Optional: momentary button, held 2 s, cleanly powers the Pi down.
# Protects the SD card. Set to None if you are not fitting one.
PIN_SHUTDOWN = 21

# Vibration motor on a 3-pin module (VCC / IN / GND). This pin drives IN
# only; the module's own transistor switches the motor and its flyback diode
# absorbs the back-EMF, so no external driver is needed and the GPIO carries
# just a few milliamps of signal.
#
# VCC is on the 5V rail, shared with the relay and the LCD. See
# MOTOR_SUPPLY_V below -- the rail choice sets the safe ceiling on
# MORSE_LEVEL, and the two must be changed together.
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

# True for a LOW-level-trigger relay module (the SRD-05VDC-SL-C board), which
# energises when the pin is pulled LOW. Set False for a ULN2003 channel or a
# plain NPN transistor, both of which light the load when the pin goes HIGH.
CHILD_LIGHT_ACTIVE_LOW = True

# I2C for the LCD uses GPIO2 (SDA) and GPIO3 (SCL). Not configurable.
# (A Pi 4 actually has up to 6 I2C buses via dtoverlay=i2c3..i2c6 if you
# ever need to move the display off bus 1. A Pi 3 cannot do that.)

# ---------------------------------------------------------------------------
# LCD
# ---------------------------------------------------------------------------
LCD_ADDRESS = 0x27        # try 0x3F if the screen stays blank
LCD_COLS = 16
LCD_ROWS = 2
# Most cheap PCF8574 backpacks are 'A00'. If you see garbled characters,
# switch this to 'A02'.
LCD_CHARMAP = "A00"

# ---------------------------------------------------------------------------
# BEHAVIOUR  (matches the original Arduino sketch)
# ---------------------------------------------------------------------------
MORSE_UNIT = 0.200        # seconds. Was `#define UNIT 150` on the Arduino.
MORSE_TEXT = "Sarswela"
# Seconds a button must read stable before the press is reported. This is
# latency paid on EVERY press: nothing downstream runs until it elapses, so
# it sets the floor on how quickly the light and motor can respond. 0.04 is
# comfortably longer than the few milliseconds a tactile switch chatters for,
# while halving the old 0.08 delay. Raise it only if a single press starts
# registering twice.
BOUNCE_TIME = 0.04

# ---------------------------------------------------------------------------
# MOTOR SUPPLY -- keep this honest, the tests check it
# ---------------------------------------------------------------------------
# Which rail the module's VCC is on. The motor is rated for 3V, so this
# number decides how much duty is safe: change the rail and you must change
# MORSE_LEVEL with it. test_motor_voltage_is_within_rating enforces the
# relationship rather than trusting anyone to remember.
MOTOR_SUPPLY_V = 5.0      # 3.3 or 5.0, whichever pin VCC is on
MOTOR_DROP_V = 0.3        # across the module's switching transistor
MOTOR_RATED_V = 3.0       # what the coin motor is specified for

# Motor intensity, 0.0-1.0, applied during Morse.
#
# At 5V the module delivers about 4.7V, well over the motor's 3V rating, so
# full duty is not on. Two things keep 0.85 comfortable:
#
#   * the bursts. With MORSE_TEXTURE the motor is driven only
#     MORSE_TEXTURE_DUTY of the time within an element, so the average over
#     a dash is 0.85 x 0.70 = 0.60 duty -- about 2.8V, just under rating.
#   * the intermittency. "Sarswela" is a few seconds of buzzing, not
#     continuous running, so brief peaks above rating do little harm.
#
# The peak still reaches ~4.0V, and that peak is what the skin feels. This
# is the whole point of moving to 5V: more amplitude per burst, without more
# average heating.
#
# Raise toward 1.0 for a harder buzz, accepting shortened motor life. If you
# move VCC back to 3.3V, set MOTOR_SUPPLY_V = 3.3 and MORSE_LEVEL = 1.0 --
# at that rail full duty is inside rating.
MORSE_LEVEL = 0.85

# Brief full-power pulse that breaks stiction. An eccentric mass will not
# start from rest at low duty. Short enough not to matter thermally.
KICK_LEVEL = 1.0
KICK_TIME = 0.060         # seconds

MORSE_TEXTURE = True

# Bursts per second. The eccentric mass takes 20-50ms to spin up or down, so
# this interacts with its mechanics:
#   10-15 Hz  deep modulation, an insistent throb -- strongest sensation
#   20-30 Hz  shallower, reads as a rough buzz
#   above 40  the mass cannot follow and it feels steady again, i.e. no gain
# If a dot starts to feel like separate taps rather than one buzz, raise it.
MORSE_TEXTURE_HZ = 14

# Fraction of each burst period the motor is driven. Lower digs the troughs
# deeper (more contrast, less average power); higher approaches steady drive.
# Below about 0.5 the mass never gets fully up to speed.
MORSE_TEXTURE_DUTY = 0.70

# Where the audio lives, and which file each mode plays.
SOUNDS_DIR = "Sounds"
AUDIO_FILES = {
    "blind": "Blind.mp3",
    "child": "Child.mp3",
    "english": "English.mp3",
    "spanish": "Spanish.mp3",
    "mandarin": "Mandarin.mp3",
}
