# Button V2 — Assistive Device Controller

An Arduino-based assistive device that plays audio cues for different accessibility modes (deaf, blind, child, foreign language) and outputs Morse code via a relay. A Python script listens over serial and plays the corresponding WAV audio file.

---

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Software Requirements](#software-requirements)
3. [Step 1 — Install VS Code](#step-1--install-vs-code)
4. [Step 2 — Install Python](#step-2--install-python)
5. [Step 3 — Install Python Libraries](#step-3--install-python-libraries)
6. [Step 4 — Install PlatformIO in VS Code](#step-4--install-platformio-in-vs-code)
7. [Step 5 — Install Arduino Drivers](#step-5--install-arduino-drivers)
8. [Step 6 — Clone or Copy the Project](#step-6--clone-or-copy-the-project)
9. [Step 7 — Update the Python Path in launch_audio.py](#step-7--update-the-python-path-in-launch_audiopy)
10. [Step 8 — Update the Sounds Path in audio_player.py](#step-8--update-the-sounds-path-in-audio_playerpy)
11. [Step 9 — Upload the Code to Arduino](#step-9--upload-the-code-to-arduino)
12. [Wiring Reference](#wiring-reference)
13. [How It Works](#how-it-works)

---

## Hardware Requirements

| Component | Details |
|---|---|
| Arduino Uno | Any genuine or clone (CH340 chip) |
| I2C LCD (16x2) | Address `0x27` (most common) |
| Relay Module | Single-channel, 5V active-LOW |
| Push Buttons | 7 total (see wiring table below) |
| Jumper Wires | Male-to-male and male-to-female |
| USB-A to USB-B Cable | To connect Arduino to PC |
| PC / Laptop | Windows 10 or 11 |
| Speaker or Buzzer | Connected to relay output |

---

## Software Requirements

| Software | Version | Purpose |
|---|---|---|
| VS Code | Latest | Code editor and PlatformIO host |
| Python | 3.11 (recommended) | Runs the audio player script |
| PlatformIO IDE (VS Code extension) | Latest | Compiles and uploads Arduino code |
| Git (optional) | Latest | To clone the repo |

---

## Step 1 — Install VS Code

1. Go to [https://code.visualstudio.com](https://code.visualstudio.com)
2. Click **Download for Windows**
3. Run the installer (`.exe`)
4. During install, check these options:
   - **Add to PATH**
   - **Register Code as an editor for supported file types**
5. Click **Install**, then **Finish**
6. Open VS Code — you should see the welcome screen

---

## Step 2 — Install Python

> Python 3.11 is recommended because it matches the path already used in `launch_audio.py`.

1. Go to [https://www.python.org/downloads/release/python-3110](https://www.python.org/downloads/release/python-3110)
2. Scroll down and download **Windows installer (64-bit)**
3. Run the installer
4. **IMPORTANT:** Check **"Add Python to PATH"** at the bottom of the first screen before clicking Install
5. Click **Install Now**
6. When done, click **Close**

**Verify Python installed correctly** — open a terminal (`Win + R`, type `cmd`, press Enter) and run:

```
python --version
```

You should see something like `Python 3.11.x`.

---

## Step 3 — Install Python Libraries

This project uses two Python libraries. Open a terminal (`cmd` or PowerShell) and run these two commands one at a time:

```
pip install pyserial
pip install pygame
```

Wait for each to finish before running the next.

**Verify they installed:**

```
pip show pyserial
pip show pygame
```

Both should print info about the package without errors.

---

## Step 4 — Install PlatformIO in VS Code

1. Open VS Code
2. Click the **Extensions** icon on the left sidebar (or press `Ctrl+Shift+X`)
3. In the search box, type `PlatformIO`
4. Click the result named **PlatformIO IDE** (by PlatformIO)
5. Click **Install** and wait — it downloads several tools in the background (this can take 5–10 minutes the first time)
6. When done, VS Code will prompt you to **Reload** — click it
7. You should now see a PlatformIO icon (alien head) in the left sidebar

---

## Step 5 — Install Arduino Drivers

If your Arduino is a clone with a **CH340 chip** (very common for cheaper boards), Windows may not detect it automatically.

1. Download the CH340 driver: search for **"CH340 driver Windows"** and download from the manufacturer site, or use [https://www.wch-ic.com/downloads/CH341SER_EXE.html](https://www.wch-ic.com/downloads/CH341SER_EXE.html)
2. Run the installer and click **Install**
3. Plug in your Arduino via USB
4. Open **Device Manager** (`Win + X` → Device Manager)
5. Look under **Ports (COM & LPT)** — you should see something like `USB-SERIAL CH340 (COM3)`
6. Note the COM number (e.g., `COM3`) — you will need this if auto-detection fails

> If your board says "Arduino" in Device Manager without any CH340 driver, it is genuine and already works.

---

## Step 6 — Clone or Copy the Project

**Option A — Copy from USB/Drive:**

Copy the entire `button_v2` folder to your new laptop. Suggested path:

```
D:\download\Work Life\Robotics\button_v2
```

> The path matters because `audio_player.py` has a hardcoded path to the `Sounds` folder. You can put it anywhere but you will need to update the path (see Step 8).

**Option B — Clone from Git (if using GitHub):**

```
git clone <your-repo-url>
```

---

## Step 7 — Update the Python Path in launch_audio.py

The file [launch_audio.py](launch_audio.py) has a hardcoded path to your Python executable. On a new laptop this path will be different.

1. Find where Python is installed on the new laptop. Open `cmd` and run:

```
where python
```

Copy the full path it shows (e.g., `C:\Users\YourName\AppData\Local\...`).

2. Open [launch_audio.py](launch_audio.py) in VS Code
3. Find this line near the top:

```python
PYTHON = r"C:\Users\MichaelGelo\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe"
```

4. Replace the path with the one you copied from `where python`

---

## Step 8 — Update the Sounds Path in audio_player.py

The file [audio_player.py](audio_player.py) also has a hardcoded path to the `Sounds` folder.

1. Open [audio_player.py](audio_player.py) in VS Code
2. Find this line:

```python
SOUNDS_PATH = r"D:\download\Work Life\Robotics\button_v2\Sounds"
```

3. Update it to match where you put the project folder on the new laptop. Example:

```python
SOUNDS_PATH = r"C:\Users\YourName\Documents\button_v2\Sounds"
```

> Make sure the `Sounds` folder contains `Blind.wav`, `English.wav`, `Spanish.wav`, and `Mandarin.wav`.

---

## Step 9 — Upload the Code to Arduino

1. Plug your Arduino Uno into the laptop via USB
2. Open VS Code and open the `button_v2` folder (`File` → `Open Folder`)
3. Click the PlatformIO alien icon in the sidebar
4. Under **Project Tasks → uno**, click **Upload**
5. PlatformIO will compile the code and upload it to the Arduino
6. After upload completes, `launch_audio.py` will automatically open a new terminal window running `audio_player.py`
7. The audio player will auto-detect the Arduino's COM port and start listening

> If the audio player window says "Arduino port not found", type the COM port manually (e.g., `COM3`) and press Enter.

---

## Wiring Reference

| Button Function | Arduino Pin |
|---|---|
| Deaf Mode | D2 |
| Blind Mode | D3 |
| Child Mode | D4 |
| Foreign Language Mode | D5 |
| Foreign — English | D8 |
| Foreign — Spanish | D9 |
| Foreign — Mandarin | D10 |
| Relay (Morse output) | D7 |

| LCD (I2C) | Arduino |
|---|---|
| SDA | A4 |
| SCL | A5 |
| VCC | 5V |
| GND | GND |

All buttons are wired between their pin and **GND** (internal pull-up resistors are used — no external resistors needed).

---

## How It Works

1. When a button is pressed, the Arduino displays the mode on the LCD and sends a command over Serial (e.g., `PLAY:blind`, `STOP`)
2. The Python `audio_player.py` script reads those serial commands and plays the matching WAV file from the `Sounds` folder using `pygame`
3. In **Deaf Mode**, the Arduino also plays the word "Sarswela" in Morse code via the relay
4. The **Foreign Language** button is a gate — you must press it first, then press English / Spanish / Mandarin to trigger audio

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Arduino not detected | Install CH340 driver (Step 5) |
| `pip` not found | Python was not added to PATH — reinstall Python with PATH option checked |
| `ModuleNotFoundError: pygame` | Run `pip install pygame` |
| Audio player says "file not found" | Update `SOUNDS_PATH` in `audio_player.py` (Step 8) |
| Audio player doesn't open after upload | Update `PYTHON` path in `launch_audio.py` (Step 7) |
| LCD shows nothing | Check I2C address — try `0x3F` instead of `0x27` in `main.cpp` line 16 |
| Wrong COM port | Open Device Manager, check Ports section, enter correct COM number manually |
