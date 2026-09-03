# KAPATID-VIBE — Raspberry Pi 4 Model B wiring

## Pin map (BCM numbering)

### Buttons — wire exactly as on the Arduino

Each button goes from its GPIO pin to **GND**. Internal pull-ups are enabled in
software, so no external resistors. Physical pin numbers are given so you can
count along the header.

| Function | Was (Uno) | Now (BCM) | Physical pin |
|---|---|---|---|
| Deaf Mode | D2 | GPIO17 | 11 |
| Blind Mode | D3 | GPIO27 | 13 |
| Child Mode | D4 | GPIO22 | 15 |
| Foreign Mode | D5 | GPIO23 | 16 |
| Foreign — English | D8 | GPIO24 | 18 |
| Foreign — Spanish | D9 | GPIO25 | 22 |
| Foreign — Mandarin | D10 | GPIO5 | 29 |
| Safe shutdown (new, optional) | — | GPIO21 | 40 |

Any GND pin works: 6, 9, 14, 20, 25, 30, 34, 39.

### LCD — unchanged module, new pins

| LCD backpack | Pi | Physical pin |
|---|---|---|
| SDA | GPIO2 | 3 |
| SCL | GPIO3 | 5 |
| VCC | **5V** | 2 or 4 |
| GND | GND | 6 |

The display is 5V but the I2C lines idle at 3.3V from the Pi's pull-ups, which
every PCF8574 backpack tolerates. Same `0x27` address as before. If the screen
stays blank, run `sudo i2cdetect -y 1` — some backpacks answer at `0x3f`.

### Motor — TB6612FNG replaces the relay

| TB6612FNG | Connects to | Physical pin |
|---|---|---|
| PWMA | GPIO12 | 32 |
| AIN1 | GPIO6 | 31 |
| AIN2 | GPIO16 | 36 |
| STBY | GPIO26 | 37 |
| VCC | Pi **3.3V** | 1 |
| GND | Pi GND **and** battery − | 39 |
| VM | Battery + (6–12V) | — |
| AO1 / AO2 | Motor terminals | — |

**Add 10 kΩ pulldowns** from PWMA, AIN1, AIN2 and STBY to GND. Pi GPIOs float
during boot, and you do not want the motor spinning up by itself while the
device is around someone's neck. STBY also starts low in software as a second
layer of protection.

**Add bulk capacitance** across VM and GND at the driver: 100–470 µF
electrolytic in parallel with a 0.1 µF ceramic. This is what stops the motor's
inrush from dragging down the supply — the same fault that was corrupting your
COM port on the Arduino build.

**Ground the two supplies together at one point only.** Pi GND, driver GND and
battery negative all meet at the driver's GND pin.

---

## PWM and audio: the Pi 4 is better than the Pi 3 here

On a **Pi 3** the 3.5 mm jack and hardware PWM share one PWM controller and
genuinely conflict. On a **Pi 4** they do not: BCM2711 has two independent PWM
controllers. The jack lives on `pwm1` (GPIO40/41, driven by firmware, with the
Linux driver deliberately disabled) while `dtoverlay=pwm-2chan` drives `pwm0`
(GPIO12/13/18/19). Different peripherals.

They do still share one clock generator, and Raspberry Pi ships this warning
for BCM2711 anyway:

> The onboard analogue audio output uses both PWM channels. So be careful
> mixing audio and PWM.

**So don't rely on it. Use software PWM** — the default in `config.py`. An
eccentric-mass motor has 20–50 ms of mechanical inertia and physically cannot
respond to PWM jitter, so software PWM is entirely adequate. It needs no
overlay and removes the question altogether.

If you want hardware PWM anyway, add to `/boot/firmware/config.txt`:

```
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

then set `PWM_MODE = "hardware"` and **verify audio still works** with
`speaker-test -c2 -t wav` while a duty cycle is running. Use `chip=0` — correct
for Pi 1 through 4 on every kernel.

Separately, fit a **USB audio adapter** (~₱300). The Pi 4's analogue jack is an
11-bit PWM/sigma-delta output with dither and it hisses audibly. For a device
whose whole purpose is narration to a blind listener, that matters. It draws
50–100 mA of a 1.2 A USB budget you aren't using.

---

## Power

Two separate supplies, joined only at ground.

**Pi:** 5 V / 3 A (15 W) via **USB-C** — note the Pi 4 changed from the Pi 3's
micro-USB. Official figures: 600 mA idle, 1.25 A peak under stress, 850 mA at
boot. Undervoltage is logged below 4.63 V.

Use a **short, thick (20 AWG or better) USB-C cable**. Voltage sag from a thin
cable is the usual cause of trouble, not an underrated supply. Check with
`vcgencmd get_throttled` — anything but `0x0` means a power problem.

A power bank works if a single port sustains a genuine 3 A. A 10,000 mAh bank
gives roughly 10 hours at this workload, which covers any performance. Watch
for banks that auto-shut-off at low draw.

The 2019 rev 1.1 USB-C e-marked-cable bug cannot reach you — check with
`grep Revision /proc/cpuinfo`; `c03114` or `c03115` are current 4 GB boards.

**Motor:** your existing battery pack straight to the driver's VM. Never off
the Pi's 5 V rail.

---

## Setup peripherals

The Pi 4 has **2× micro-HDMI**, not full-size, so first boot needs a
**micro-HDMI-to-HDMI cable or adapter** — unlike the Pi 3. You can skip it
entirely by pre-seeding Wi-Fi and SSH in Raspberry Pi Imager and going
headless, which is the better route for an embedded build.

---

## Boot configuration

`setup.sh` handles this, but for reference, in `/boot/firmware/config.txt`:

```
dtparam=i2c_arm=on
```

That's all you need with the default software PWM. The `pwm-2chan` overlay is
only for `PWM_MODE = "hardware"`.

---

## If you add the NeoPixel strip later

Your circuit diagram shows a WS2812 strip for the young-audience mode that was
never in the Arduino code. If you add it, drive it over **SPI (GPIO10, physical
pin 19)** — not PWM or PCM. PWM mode collides with both your audio and your
motor; SPI is the only method that coexists with analogue audio.

On a Pi 4 the core clock scales 200–500 MHz under DVFS, and the SPI clock
derives from it, so add `core_freq_fixed=1` to config.txt to keep the bit
timing stable. For strips over ~340 LEDs you also need `spidev.bufsiz=32768`
on the kernel command line.

The same `core_freq_fixed=1` is the first thing to try if the LCD ever glitches
intermittently — though at 100 kHz on a character display it is unlikely.
