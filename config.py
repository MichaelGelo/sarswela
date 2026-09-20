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
#   None            -> whatever the system is already using. This is the
#                      default, and it is the right answer whenever
#                      `speaker-test` already works: the OS has picked a
#                      card, so inherit that choice instead of second-
#                      guessing it.
#   "Headphones"    -> force the Pi's built-in 3.5mm jack. An 11-bit
#                      PWM/sigma-delta output with dither, so it hisses
#                      audibly, but it is always present.
#   "USB"           -> a USB audio adapter, if one is actually fitted.
#                      Better sound, but naming a device that is not
#                      plugged in silences playback entirely.
#
# Run `./venv/bin/python -m sounddevice` on the Pi to list exact names.
#
# A name here must match a real output device. It is checked once at startup
# and, if it does not match, the code says so and falls back to the system
# default rather than failing every clip in silence.
AUDIO_DEVICE = None

# ---------------------------------------------------------------------------
# VOLUME
# ---------------------------------------------------------------------------
# Master gain applied to every clip, on top of the OS mixer. 1.0 is the file
# as recorded; 2.0 is +6 dB; 4.0 is +12 dB.
#
# Values above 1.0 are safe to try because playback runs through a soft
# limiter (see hardware.Audio), so nothing can ever exceed full scale -- you
# get compression rather than the crackle of digital clipping. But it is
# compression: past about 3.0 the clips stop getting meaningfully louder and
# just start sounding flat and strained. If 3.0 is still not enough, the
# shortfall is in the output stage, not here -- see "Sound is too quiet" in
# the README.
#
# Run `python normalize_audio.py` first. It raises every clip to the same
# level with no distortion at all, which is free loudness this dial cannot
# match. Run `./pi_audio.sh --max` too -- the mixer gain it claims is also
# free, and there is usually a lot of it.
#
# 1.0 is the right default, and raising it should be a last resort. This was
# briefly set to 2.0 on the theory that the Pi's 3.5mm jack needs all the help
# it can get. It does not: the ALSA mixer turned out to be sitting 24 dB below
# its maximum, and recovering that is clean gain, where this dial is not.
#
# Stacking them actively hurt. Normalised clips peak near 0 dBFS, 2.0 pushed
# them into the limiter, and a mixer left at +4 dB then clipped what was left
# -- which is heard as distortion, not volume. Claim the mixer gain first
# (./pi_audio.sh), and only reach for this if the result is still too quiet.
VOLUME = 1.0

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
# GPIO PIN MAP  (BCM numbering; physical header pins in the comments)
# ---------------------------------------------------------------------------
# This is the wiring as actually built. Physical pin numbers are the ones
# you count on the board; BCM numbers are what the code uses. They are not
# the same, and mixing them up is the most common wiring fault here.
#
#   HEADER            USED FOR
#   pin 2   5V        relay VCC + vibration module VCC
#   pin 3   GPIO2     LCD SDA
#   pin 4   5V        LCD VCC
#   pin 5   GPIO3     LCD SCL
#   pin 6   GND       LCD ground
#   pin 9   GND       common ground: buttons, relay, LED strip, motor
#   pin 11  GPIO17    deaf button
#   pin 13  GPIO27    blind button
#   pin 15  GPIO22    child button
#   pin 16  GPIO23    foreign button
#   pin 17  3.3V      LED strip supply, into the relay's COM terminal
#   pin 18  GPIO24    english button
#   pin 22  GPIO25    hindi button
#   pin 29  GPIO5     mandarin button
#   pin 32  GPIO12    vibration module IN
#   pin 34  GND       shutdown button ground
#   pin 36  GPIO16    relay IN
#   pin 40  GPIO21    shutdown button
#
# Buttons wire exactly as they did on the Arduino: pin -> button -> GND.
# Internal pull-ups are enabled in software, so no resistors are needed.
PIN_DEAF = 17            # header pin 11
PIN_BLIND = 27           # header pin 13
PIN_CHILD = 22           # header pin 15
PIN_FOREIGN = 23         # header pin 16
PIN_ENGLISH = 24         # header pin 18
PIN_HINDI = 25           # header pin 22
PIN_MANDARIN = 5         # header pin 29

# Momentary button, held 2 s, cleanly powers the Pi down -- which is what
# protects the SD card from the corruption that pulling power causes.
# Set to None if you are not fitting one.
PIN_SHUTDOWN = 21        # header pin 40, ground on pin 34

# Vibration motor on a 3-pin module (VCC / IN / GND). This pin drives IN
# only; the module's own transistor switches the motor and its flyback diode
# absorbs the back-EMF, so no external driver is needed and the GPIO carries
# just a few milliamps of signal.
#
# VCC is on 5V (header pin 2), shared with the relay coil. See
# MOTOR_SUPPLY_V below -- the rail sets the safe ceiling on MORSE_LEVEL, and
# the two must be changed together.
PIN_MOTOR = 12           # header pin 32

# Drive the motor with PWM, or with plain on/off?
#
# False (default) uses a straight digital output: full rail when on, nothing
# when off. Some 3-pin vibration modules will not respond to a switching
# waveform on IN at all -- they run happily when the pin is held high and
# stay dead under PWM, even at 100% duty. If holding GPIO12 high with
# DigitalOutputDevice buzzes but PWMOutputDevice does not, this is why, and
# False is the setting you want.
#
# Morse loses nothing by it: dots and dashes are on/off, not shades. What
# goes away is MORSE_LEVEL and KICK_LEVEL -- in digital mode the motor is
# always driven at the full rail, so intensity is set by MOTOR_SUPPLY_V and
# MORSE_TEXTURE_DUTY instead.
#
# True restores PWM for modules that accept it, and re-enables MORSE_LEVEL.
MOTOR_PWM = False

# ---------------------------------------------------------------------------
# CHILD MODE INDICATOR LIGHT
# ---------------------------------------------------------------------------
# An LED strip that lights while Child Mode is selected and goes dark for
# every other mode.
#
# IMPORTANT -- this pin SWITCHES the strip, it does not power it. Nine LEDs
# draw about 160 mA against a 16 mA pin limit. As built, a low-trigger relay
# module does the switching:
#
#   GPIO16 (pin 36)  -> relay IN
#   5V     (pin 2)   -> relay VCC
#   GND    (pin 9)   -> relay GND
#   3.3V   (pin 17)  -> relay COM
#   relay NO         -> strip +
#   strip -          -> GND (pin 9)
#
# Use NO, not NC, so the strip is dark when the relay is idle. If the light
# is on constantly or inverted, that wire is on the wrong terminal.
#
# Set to None if no light is fitted -- the code then never touches GPIO16.
PIN_CHILD_LIGHT = 16     # header pin 36

# True for a LOW-level-trigger relay module (the SRD-05VDC-SL-C board), which
# energises when the pin is pulled LOW -- as built. Set False for a ULN2003
# channel or a plain NPN transistor, both of which light the load on a HIGH.
CHILD_LIGHT_ACTIVE_LOW = True

# Open-drain control: drive the pin LOW to switch on, and RELEASE it (back to
# a high-impedance input) to switch off, instead of driving it high.
#
# This exists for one specific and stubborn case: a low-trigger relay module
# whose coil needs 5V. Such a board pulls its IN pin up to 5V, and a Pi pin
# driven high only reaches 3.3V -- not enough to release the input, so the
# relay switches on and never off. Releasing the pin lets the module's own
# pull-up carry IN to the full 5V, which does release it.
#
#   pin driven LOW      ->  IN at 0V     ->  relay ON
#   pin driven HIGH     ->  IN at ~3.3V  ->  relay still ON   (the problem)
#   pin released (hi-Z) ->  IN at ~5V    ->  relay OFF        (the fix)
#
# WARNING -- while released, the pin sits at the module's 5V. Raspberry Pi
# GPIOs are 3.3V and NOT 5V tolerant: the clamp diode conducts, and the
# pull-up limits it to a milliamp or two, but this is out of spec and will
# degrade the pin over time. Put a 1k resistor in series between the GPIO
# and IN to make it safe, or better, drive the load through a transistor and
# leave this False.
#
# Only meaningful together with CHILD_LIGHT_ACTIVE_LOW = True.
CHILD_LIGHT_OPEN_DRAIN = False

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
MORSE_TEXTURE_DUTY = 0.60

# Where the audio lives, and which file each mode plays.
SOUNDS_DIR = "Sounds"
AUDIO_FILES = {
    "blind": "Blind.mp3",
    "child": "Child.mp3",
    "english": "English.mp3",
    "hindi": "Hindi.mp3",
    "mandarin": "Mandarin.mp3",
}
CHILD_LIGHT_OPEN_DRAIN = True
CHILD_LIGHT_OPEN_DRAIN = True
