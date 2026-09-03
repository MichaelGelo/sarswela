# PIKAPATID v3

Raspberry Pi 4B controller for the KAPATID-VIBE assistive device. Eight buttons
select a mode; each mode shows a line on a 16x2 LCD and plays an audio clip.
Deaf Mode additionally buzzes "Sarswela" in Morse code on a vibration motor,
and Child Mode lights an LED strip.

Ported from an Arduino sketch plus a separate Python audio player into one
Python program. v3 replaces the TB6612FNG motor driver with a 3-pin coin
motor module and adds the Child Mode light.

## What changed since v2

| | v2 | v3 |
|---|---|---|
| Motor driver | TB6612FNG, 4 GPIO pins | 3-pin module, 1 GPIO pin |
| Motor supply | 5V via driver | 5V direct to module |
| Child Mode light | none | LED strip via relay on GPIO16 |
| Braking | active brake via TB6612 | coast (mass stops in ~30ms) |

GPIO6, 13 and 26 are freed by the motor change and are now unused.

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

| LCD | Pi |
|---|---|
| VCC | 5V (2) |
| GND | GND (6) |
| SDA | GPIO2 (3) |
| SCL | GPIO3 (5) |

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
| Spanish | 25 | 22 |
| Mandarin | 5 | 29 |
| Shutdown | 21 | 40 |

### Vibration motor -- 3-pin module

| Module | Pi |
|---|---|
| IN | GPIO12 (32) |
| VCC | 5V (4) |
| GND | GND (39) |

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

| Module | Pi |
|---|---|
| VCC | 5V (4) |
| GND | GND (34) |
| IN | GPIO16 (36) |

VCC must be 5V -- the SRD-05VDC-SL-C coil will not pull in reliably at 3.3V.

Contact side -- wire the relay into the strip's positive leg, using **NO**
(normally open) so the strip is dark when idle:

| Terminal | To |
|---|---|
| COM | 3.3V (17), or an external 5V supply |
| NO | strip + |
| -- | strip - to the same supply's ground |

Relay contacts are isolated, so if you power the strip externally its current
never touches the Pi. Only the coil side needs a shared ground.

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

Audio clips belong in the directory named by `AUDIO_DIR` in `config.py`, using
the filenames listed in `CLIPS`.

## Tuning

Everything adjustable lives in `config.py`.

| Setting | Default | Notes |
|---|---|---|
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
| `pikapatid_v3.html` | Build and wiring guide. Open in a browser. |
