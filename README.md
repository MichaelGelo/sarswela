# PIKAPATID v4

Raspberry Pi 4B controller for the KAPATID-VIBE assistive device. Eight buttons
select a mode; each mode shows a line on a 16x2 LCD and plays an audio clip.
Deaf Mode additionally buzzes "Sarswela" in Morse code on a vibration motor,
and Child Mode lights an LED strip.

Ported from an Arduino sketch plus a separate Python audio player into one
Python program. v4 documents the wiring as actually built, and
replaces Spanish with Hindi.

## What changed since v3

| | v3 | v4 |
|---|---|---|
| Third language | Spanish | Hindi (`Hindi.mp3`) |
| Pin map | generic | documented against the real header pins |
| `kapatid.service` | template, `User=pi` | correct user and paths |
| Light timing | after the LCD write | first in `on_press()` |

The `kapatid.service` fix matters: the v3 file was an unedited template
naming a user `pi` that does not exist on this Pi, which fails at boot with
`status=217/USER` and no traceback.

## Hardware

- Raspberry Pi 4 Model B, 64-bit Raspberry Pi OS (Bookworm)
- 16x2 character LCD with I2C backpack, address 0x27
- 8 momentary push buttons
- 10mm coin vibration motor on a 3-pin module (VCC / IN / GND)
- USB LED strip, 9 LEDs, ~160mA
- 1-channel relay module, low-level trigger (SRD-05VDC-SL-C)
- Powered speaker or headphones on the 3.5mm jack

## Pinout

All numbers are BCM GPIO; physical pin numbers are in parentheses.

### LCD -- I2C

| LCD | Pi | Header pin |
|---|---|---|
| VCC | 5V | 4 |
| GND | GND | 6 |
| SDA | GPIO2 | 3 |
| SCL | GPIO3 | 5 |

### Buttons

Each button bridges its GPIO to any ground pin. Internal pull-ups are enabled
in software, so no external resistors are needed.

| Button | GPIO | Physical |
|---|---|---|
| Deaf | 17 | 11 |
| Blind | 27 | 13 |
| Child | 22 | 15 |
| Foreign | 23 | 16 |
| English | 24 | 18 |
| Hindi | 25 | 22 |
| Mandarin | 5 | 29 |
| Shutdown | 21 | 40 (ground on pin 34) |

### Vibration motor -- 3-pin module

| Module | Pi | Header pin |
|---|---|---|
| IN | GPIO12 | 32 |
| VCC | 5V | 2 |
| GND | GND | 9 |

The module carries its own switching transistor and flyback diode, so GPIO12
supplies only a logic signal -- a few milliamps. The motor's 80-100mA comes
off the 5V rail, shared with the relay coil and the LCD.
**Do not connect a bare motor to a GPIO pin.**

The 5V rail puts about 4.7V at the motor, over its 3V rating, so `MORSE_LEVEL`
is capped at `0.85` and the burst texture keeps the *average* near 2.8V. The
peak is what the skin feels; the average is what heats the motor. Those two
numbers are tied together by `MOTOR_SUPPLY_V` in `config.py`, and three tests
enforce the relationship -- change the rail without changing the level and the
suite fails with the value you should have used.

### Child Mode light -- relay module

Coil side:

| Module | Pi | Header pin |
|---|---|---|
| IN | GPIO16 | 36 |
| VCC | 5V | 2 |
| GND | GND | 9 |

VCC must be 5V -- the SRD-05VDC-SL-C coil will not pull in reliably at 3.3V.

Contact side -- wire the relay into the strip's positive leg, using **NO**
(normally open) so the strip is dark when idle:

| Terminal | To |
|---|---|
| COM | 3.3V, header pin 17 |
| NO | strip + |
| -- | strip - to GND, header pin 9 |

Relay contacts are isolated, so if you power the strip externally its current
never touches the Pi. Only the coil side needs a shared ground.

## Replacing an existing install

The one thing worth protecting is `Sounds/` -- your recordings are not in
this archive -- and `venv/`, which takes a few minutes to rebuild. Everything
else is disposable.

```bash
cd ~

# 1. keep a full copy, in case something here is wrong
cp -r sarswela sarswela-backup-$(date +%m%d)
ls sarswela-backup-*/

# 2. clear out the code, keeping Sounds/ and venv/
cd ~/sarswela
rm -f *.py *.md *.html *.service *.sh
ls -la                      # Sounds/ and venv/ should still be here

# 3. copy the new files in, then check nothing is missing
ls *.py Sounds/
```

If `Sounds/` did get lost, restore it from the backup:

```bash
cp -r ~/sarswela-backup-*/Sounds ~/sarswela/
```

Delete the backup once the new code has run correctly -- not before.

## Install

```bash
cd ~
mkdir -p sarswela && cd sarswela
# unzip pikapatid_v3.zip here

chmod +x setup.sh && ./setup.sh      # dependencies, I2C

./venv/bin/python test_logic.py      # 25 tests, no hardware needed
i2cdetect -y 1                       # expect 27

sudo cp kapatid.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kapatid
sudo systemctl status kapatid         # want: active (running)
```

`audio_player.py` and `launch_audio.py` from your existing install are not in
this archive and are not needed by `kapatid.py`, which plays audio itself.
Leave them in place if you still use them standalone.

Audio clips live in `Sounds/`, named exactly as `AUDIO_FILES` in `config.py`
lists them: `Blind.mp3`, `Child.mp3`, `English.mp3`, `Hindi.mp3`,
`Mandarin.mp3`. Only `Hindi.mp3` ships in this archive -- the rest are
yours, so **do not delete `Sounds/` when replacing the code**.

Deaf and Foreign play no clip by design: Deaf buzzes Morse instead, and
Foreign only arms the language gate.

## Tuning

Everything adjustable lives in `config.py`.

| Setting | Default | Notes |
|---|---|---|
| `VOLUME` | `1.0` | Master playback gain. `2.0` is +6 dB. Soft-limited, so it cannot clip -- but past ~`3.0` it only compresses. Normalise the clips first. |
| `MOTOR_SUPPLY_V` | `5.0` | Which rail VCC is on. Must match reality -- it sets the safe ceiling on `MORSE_LEVEL`. |
| `MORSE_LEVEL` | `0.85` | Motor duty during Morse. `0.85` at 5V; use `1.0` if you move VCC to 3.3V. |
| `KICK_LEVEL` | `1.0` | Brief full-power pulse that breaks stiction. |
| `KICK_TIME` | `0.060` | Length of that pulse, seconds. |
| `MORSE_UNIT` | `0.200` | One Morse time unit. Raise to ~0.200 if the pattern is hard to feel. |
| `MORSE_TEXTURE` | `True` | Chop each dot and dash into a burst train instead of a steady hold. Costs no amplitude and feels considerably stronger. |
| `MORSE_TEXTURE_HZ` | `14` | Bursts per second. 10-15 throbs hardest; above ~40 the mass cannot follow and the gain disappears. |
| `MORSE_TEXTURE_DUTY` | `0.70` | Fraction of each burst period driven. Lower digs deeper troughs; below ~0.5 the mass never reaches speed. |
| `PIN_CHILD_LIGHT` | `16` | Set to `None` to disable the light entirely. |
| `CHILD_LIGHT_ACTIVE_LOW` | `True` | `True` for a low-trigger relay; `False` for a ULN2003 or NPN transistor. |
| `PWM_MODE` | `software` | Leave it. Hardware PWM claims the same peripheral as the 3.5mm jack. |
| `BOUNCE_TIME` | `0.04` | Latency paid on every press -- nothing responds until it elapses. Raise only if one press registers twice. |

After any edit: `sudo systemctl restart kapatid`

## If the buzz feels weak

Roughly in order of how much difference they make:

1. **Mounting.** A motor dangling on wires has nothing to react against and
   feels feeble regardless of voltage. Bond it flat to a rigid surface or press
   it against skin. This usually matters more than any setting.
2. **`MORSE_TEXTURE = True`** (the default). Skin adapts to steady vibration
   within a few hundred milliseconds -- the receptors respond to change, so a
   constant buzz fades even at full power. Chopping each element into bursts
   stops that adaptation. It gives up no amplitude, which makes it the one
   free improvement here. Tune `MORSE_TEXTURE_HZ` down toward 10 for a deeper
   throb, up toward 25 for a rougher buzz.
3. **`MORSE_LEVEL = 1.0`.** At 3.3V that is within the motor's rating, so
   there is no reason to hold back.
4. **Longer `KICK_TIME`** so each dot starts at full power.
5. **Raise `MORSE_UNIT`** to 0.200 so each element lasts longer.
6. **Already on 5V** in this configuration. Going further means raising
   `MORSE_LEVEL` toward 1.0 and spending motor lifespan for amplitude -- the
   tests will fail if you do, which is the point: it should be a decision,
   not an accident.

If all of that is exhausted and it is still too weak, the motor is the limit,
not the tuning. Some 3-pin breakouts include a series resistor that caps the
current whatever you feed them; a bare 10mm motor driven through the relay, or
a physically larger ERM, is the answer for anything that must be felt through
clothing.

## Troubleshooting

**Service will not start.** Read the traceback:

```bash
sudo journalctl -u kapatid -n 50 --no-pager
```

**`GPIOPinInUse: pin GPIO16 is already in use`.** Two objects claiming one pin
in the same process. Check for a duplicated line:

```bash
grep -c "hardware.Light()" kapatid.py     # must be 1
```

If it is more than 1, delete the extras.

**LCD backlit but blank.** The program is not running -- check the service
status. Lit-but-blank means power reached the backpack but nothing wrote to it.

**Motor silent but the LCD changes mode.** The logic is fine; test the motor
alone. Stop the service first or the pin will be busy:

```bash
sudo systemctl stop kapatid
./venv/bin/python -c "
from gpiozero import PWMOutputDevice
import time
m = PWMOutputDevice(12, frequency=1000)
m.value = 1.0; time.sleep(2); m.value = 0; m.close()
"
sudo systemctl start kapatid
```

**Light on constantly, or inverted.** The relay is on NC instead of NO -- move
the wire to the other outer terminal. If it is backwards in software, flip
`CHILD_LIGHT_ACTIVE_LOW`.

**Light lags the button.** Three things add up here, and all three are fixed
in v3: `BOUNCE_TIME` is latency on every press, the LCD's I2C write takes tens
of milliseconds, and the light used to be updated *after* both. It is now set
first in `on_press()`, before cancelling Morse and before the LCD. If it still
lags, lower `BOUNCE_TIME` -- but not below about 0.02, or a single press starts
registering twice.

**Relay pulls in but never releases.** Not a wiring fault. A low-level-trigger
module running its coil from 5V wants its IN pin driven near 5V to switch off;
a Pi pin only reaches 3.3V, which can leave the module's input transistor
partly conducting. Replace the relay with an NPN transistor (`CHILD_LIGHT_ACTIVE_LOW
= False`), which switches on a high signal and has no threshold problem.

**No audio.**

```bash
aplay -l
amixer sset 'Master' 90%
```

**Sound is too quiet, even at full volume.** Work through these in order --
the first two are free and fix most of it, and there is no point buying
hardware before they are done.

1. *Normalise the clips.* This is usually the whole problem. The clips came
   from different sources and arrived up to 18 dB apart: `Child.mp3` measured
   -31 dBFS RMS against `English.mp3` at -13. You end up setting the system
   volume for the quietest one, so everything runs quiet.

   ```bash
   ./venv/bin/python normalize_audio.py           # report, changes nothing
   ./venv/bin/python normalize_audio.py --apply   # rewrite them
   ```

   Originals are kept in `Sounds/original/`, and re-running always works from
   those, so it is safe to repeat and safe to undo. Pass `--target -10` for
   more still, at the cost of some compression.

2. *Claim the mixer gain nobody set.* `setup.sh` installs the audio stack
   but never sets a level, so the box runs at whatever the OS defaulted to --
   and the bcm2835 headphone control spans roughly -102 dB to +4 dB without
   defaulting to the top. This is often the single biggest win available, and
   it costs no quality at all.

   ```bash
   ./pi_audio.sh          # what is the mixer doing right now?
   ./pi_audio.sh --max    # open it fully, and persist across reboots
   ```

   It finds the analogue card itself (ignoring HDMI), handles the control
   being named `Headphone`, `PCM` or `Master` depending on OS release, runs
   `alsactl store` so the setting survives a reboot, and opens the PipeWire
   sink too -- on Bookworm a maxed ALSA control behind a half-open PipeWire
   sink is still half volume.

3. *Raise `VOLUME` in `config.py`.* Playback runs through a soft limiter, so
   values above `1.0` compress rather than clip. Returns fall off fast, and
   this is measured, not guessed: on a normalised clip, `1.5` buys +3.3 dB,
   `2.0` buys +5.3 dB, `3.0` buys +7.5 dB, and `6.0` buys only +9.9 dB. Past
   `3.0` you are trading a lot of dynamics for very little volume.

4. *Then, and only then, blame the hardware -- and believe it.* If
   normalised clips at `VOLUME = 2.0` with the mixer maxed are still weak,
   nothing in software will save you. The Pi's 3.5mm jack is not a headphone
   output. It is an 11-bit PWM signal through a passive filter, with no
   amplifier behind it, spec'd to feed a powered speaker or a line input. It
   cannot drive earphones to a comfortable level, and high-impedance ones are
   hopeless. Pushing `VOLUME` higher to compensate only compresses the clips
   into a flat, strained wall that is barely louder.

   A USB sound card -- the $5 kind -- has a real headphone amplifier, and is
   both considerably louder and much cleaner (the jack's PWM hiss disappears
   with it). It also frees the PWM peripheral, which removes the motor/audio
   conflict discussed under `PWM_MODE` entirely. After fitting one:

   ```bash
   ./venv/bin/python -m sounddevice   # get the exact device name
   ```

   then set `AUDIO_DEVICE` in `config.py` to that name and drop `VOLUME` back
   to `1.0`. A small powered speaker on the jack works just as well if the
   exhibit does not need earphones.

**LCD not on the bus.** `i2cdetect -y 1` showing nothing means I2C is off or
the wiring is wrong. Enable it with `sudo raspi-config` -> Interface Options ->
I2C. If it shows `3f` instead of `27`, set `LCD_ADDRESS` in `config.py`.

## Tests

```bash
./venv/bin/python test_logic.py
```

25 tests, no hardware required -- they mock the GPIO layer. They cover mode
transitions, the Morse table, the foreign-language gate, clip selection, light
behaviour, and pin-assignment sanity (no duplicates, nothing on the I2C pins).
Run them before deploying any config change; a duplicate pin assignment gets
caught here rather than at 2am before a performance.

## Files

| File | Purpose |
|---|---|
| `kapatid.py` | Main program. Run this. |
| `hardware.py` | GPIO, LCD, motor, light, audio. Mocks itself off-Pi. |
| `config.py` | Every pin and timing constant. |
| `test_logic.py` | 25 tests, no hardware needed. |
| `kapatid.service` | systemd unit for autostart. |
| `setup.sh` | Installs dependencies, enables I2C. |
| `pikapatid_v4.html` | Build and wiring guide. Open in a browser. |
