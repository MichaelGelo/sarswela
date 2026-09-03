# Arduino Uno → Raspberry Pi 4: the conversion, start to finish

## What is actually changing

Read the old code and the split is clear. The Uno did the buttons, the LCD,
the mode logic and the Morse relay. The laptop did exactly one thing: run
`audio_player.py`, which read a line off the serial port and played an MP3.

So this is not really "replacing the Arduino." It is **collapsing two devices
into one.** The Pi takes over both jobs, and the serial link between them —
along with every workaround it needed — disappears.

| | Before | After |
|---|---|---|
| Buttons, LCD, mode logic | Arduino Uno | Pi GPIO |
| Audio playback | Laptop (Python) | Pi (same Python) |
| Link between them | USB serial @ 9600 | none — one process |
| Haptic output | Relay, on/off | TB6612FNG, variable + brake |
| Power | 9 V to VIN + laptop USB | 5 V USB-C + separate motor pack |

### Code that gets deleted outright

The serial protocol (`Serial.println("PLAY:blind")` and the parser that read
it), `find_arduino_port()`, the manual COM-port prompt, `Serial.flush()`
before the relay fires, and the whole `SerialException` reconnect loop. That
loop existed because relay switching was browning out the USB-serial chip;
once the motor is on its own rail behind a driver, the fault it was papering
over is gone.

### Code that survives essentially unchanged

The Morse table, `MORSE_UNIT = 150 ms`, all eight LCD messages, the
foreign-language gate, and the five audio files.

---

## Step 1 — Flash 64-bit Raspberry Pi OS

**Use 64-bit. This is not a preference, it is a correctness issue.**

The `soundfile` library has no prebuilt wheel for 32-bit ARM. On 64-bit, the
wheel bundles libsndfile 1.2.2 and MP3 decoding works out of the box. On
32-bit it falls back to whatever libsndfile the OS ships — and on Bullseye
that is 1.0.31, which **cannot decode MP3 at all**, because MP3 support only
landed in libsndfile 1.1.0.

In Raspberry Pi Imager choose **Raspberry Pi OS Lite (64-bit)**. Lite, not
Desktop — you will never look at a GUI once this is in the enclosure, and it
leaves more RAM for audio buffers.

Before writing, open Imager's settings gear and pre-seed the hostname, your
Wi-Fi credentials, a user, and **enable SSH**. That gives you a headless
setup and means the micro-HDMI cable is a convenience rather than a
requirement.

## Step 2 — First boot and a health check

SSH in, then:

```bash
grep Revision /proc/cpuinfo     # c03114 or c03115 on a current 4GB board
vcgencmd get_throttled          # want 0x0
vcgencmd measure_temp
```

`get_throttled` returning anything but `0x0` means a power problem — almost
always a thin USB-C cable, not a weak supply. The Pi logs undervoltage below
4.63 V.

## Step 3 — Run the setup script

```bash
git clone <your repo>   # or copy the folder over with scp
cd kapatid-pi
chmod +x setup.sh
./setup.sh
```

It installs the system packages, creates the virtual environment, enables
I2C, sets the CPU governor to `powersave` to cut idle heat, and then prints
your I2C address and audio device list.

Two details it handles that are easy to get wrong by hand. `libportaudio2`
must come from apt, because `sounddevice` ships no Linux wheel on any
architecture and is only bindings for PortAudio. And the virtual environment
is created with `--system-site-packages`, because without that flag you lose
the preinstalled `gpiozero` and `rpi-lgpio` and end up compiling `lgpio` from
source.

## Step 4 — Rewire

Full pin table is in `WIRING.md`. The short version:

**Buttons don't change at all.** Same switches, same wiring pattern — pin to
switch to GND, internal pull-ups in software. Only the pin numbers move.

**The LCD doesn't change.** Same module, same `0x27` address. SDA to GPIO2,
SCL to GPIO3, VCC to 5V. Note that A4/A5 on the Uno were never analog inputs
in your design — they were the I2C pins. Nothing in this project has ever
needed an ADC, which is why the Pi having no analog inputs is a non-issue.

**The relay comes out, a TB6612FNG goes in.** Four wires to the Pi (PWM,
IN1, IN2, STBY) instead of one. Your existing motor and battery pack stay.

Two things to add that the Arduino build didn't need:

*10 kΩ pulldowns* on PWM, IN1, IN2 and STBY. Pi GPIOs float during boot, and
a motor that spins up by itself around someone's neck is not acceptable. The
software also holds STBY low until it is ready, as a second layer.

*Bulk capacitance* at the driver — 100–470 µF electrolytic in parallel with
0.1 µF ceramic across VM and GND. This is the real fix for the brownout that
was corrupting your serial port.

Ground the Pi, the driver and the battery negative together at one point.

## Step 5 — Configure and test

```bash
python3 -m sounddevice          # note the exact device name
nano config.py                  # set AUDIO_DEVICE, LCD_ADDRESS if needed
./venv/bin/python kapatid.py
```

Press each button. The LCD should track modes, audio should play, and the
deaf button should buzz "Sarswela" in Morse — and stop the instant you press
anything else.

Before that, you can prove the logic on your laptop with no hardware at all:

```bash
python3 test_logic.py
```

19 tests, each asserting a specific behaviour from `main.cpp` — the gate, the
interruptible Morse, the LCD flicker suppression, stop-on-new-clip.

## Step 6 — Autostart

```bash
sed -i "s|/home/pi/kapatid-pi|$PWD|g" kapatid.service
sudo cp kapatid.service /etc/systemd/system/
sudo systemctl enable --now kapatid
sudo systemctl status kapatid
```

The unit waits 5 seconds before starting so ALSA has time to enumerate a USB
audio adapter.

## Step 7 — Harden it for competition day

A Pi is not an Arduino: it has a filesystem that can be corrupted by pulling
power. Three things worth doing.

Fit the **shutdown button** on GPIO21 (hold 2 s). Clone the **SD card** to a
spare once everything works — `dd` or Raspberry Pi Imager's clone function.
And **vent the enclosure**, slots top and bottom so convection works.

On thermals specifically: no fan is needed for this workload. The Pi 4 idles
around 2.1–2.7 W, throttling doesn't begin until 80 °C, and Raspberry Pi's
own worst-case open-air stress test only reached 65 °C. But the board is only
specified to 50 °C ambient, and a sealed print worn against a body in a warm
venue erodes that margin. Vents plus the `powersave` governor is enough.
Verify with `vcgencmd measure_temp` after a full rehearsal.

---

## Behaviour differences to expect

**Boot time.** The Arduino was instant. The Pi takes 20–30 seconds, and the
LCD stays blank until the service starts. Power it on before the audience
arrives.

**Debounce works differently.** The modern `lgpio` backend treats
`bounce_time` as "the signal must be stable for this long before I report
it," which is the inverse of old RPi.GPIO's "ignore further edges for this
long." Same result for a human finger, but don't be surprised by it.

**Buttons are now event-driven.** The Arduino polled in `loop()` and blocked
for 250 ms after each press. `gpiozero` fires callbacks instead, so nothing
blocks — which is why Morse can run on its own thread and still be cancelled
instantly.

**The motor behaves better.** Variable intensity instead of on/off, active
braking so the eccentric mass stops instead of coasting, and no relay click.
That last one matters more than it sounds: a relay clicking inside a necklace
during a quiet passage is audible to everyone seated nearby.

---

## Two things worth deciding now

**Is Morse code still the right output?** `playMorse("Sarswela")` ports fine
and it is kept. But deaf audiences don't generally read Morse, and a judge
may ask what it's for. The hardware you're now building — variable-intensity
PWM — is what makes real music-driven haptics possible, which is what Ms.
Medrana's advice actually pointed at. Worth a conversation.

**Vosk is a phase-2 feature, not an assumption.** A Filipino model does
exist (`vosk-model-tl-ph-generic-0.6`, 320 MB), and 4 GB of RAM is exactly
where that becomes comfortable — this is where the 4 GB board earns its
price over a 1 GB Pi 3.

But benchmark it before designing around it. Feed a 60-second WAV through
`KaldiRecognizer` and time it; if it takes longer than about 40 seconds you
won't get usable live latency. Two further cautions: the model's word error
rate on one of its own test sets is 97.9, which is near-total failure and
suggests real-world accuracy on noisy theatre audio with music underneath
could be poor. And it is licensed **CC-BY-NC-SA — non-commercial only**,
which directly conflicts with the "device sales" line in your Business Model
Canvas. If captioning ships in a product you sell, you need a different
model.
