import serial
import serial.tools.list_ports
import numpy as np
import sounddevice as sd
import soundfile as sf
import time
import os

SOUNDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sounds")

# Master gain on top of the OS mixer. 1.0 is the file as recorded, 2.0 is
# +6 dB. Safe to raise because amplify() soft-limits rather than clips, but
# run `python normalize_audio.py` first -- that gives you loudness for free,
# where this dial pays for it in compression.
VOLUME = 1.0
LIMIT_KNEE = 0.7


def amplify(data):
    """Apply VOLUME, bending peaks down instead of letting them clip.

    tanh above the knee is asymptotic to full scale, so the result can never
    exceed it, and it meets the linear region below the knee without a
    corner -- a hard clip would put one there and you would hear it as a
    click on every plosive.
    """
    data = data * VOLUME
    if VOLUME <= 1.0:
        return data
    span = 1.0 - LIMIT_KNEE
    magnitude = np.abs(data)
    shaped = np.where(magnitude <= LIMIT_KNEE, magnitude,
                      LIMIT_KNEE + span * np.tanh((magnitude - LIMIT_KNEE) / span))
    return np.sign(data) * shaped

audio_files = {
    "PLAY:blind":    "Blind.mp3",
    "PLAY:child":    "Child.mp3",
    "PLAY:english":  "English.mp3",
    "PLAY:spanish":  "Spanish.mp3",
    "PLAY:mandarin": "Mandarin.mp3",
}

def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Arduino" in port.description or "CH340" in port.description or "USB Serial" in port.description:
            return port.device
    return None

def open_serial(port):
    ser = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)
    return ser

port = find_arduino_port()
if not port:
    port = input("Arduino port not found. Enter manually (e.g. COM3): ").strip()

print(f"Connecting to {port}...")
ser = open_serial(port)
print("Ready. Listening for button presses...\n")

while True:
    try:
        line = ser.readline().decode('utf-8').strip()
        if not line:
            continue

        print(f"Received: {line}")

        if line == "STOP":
            sd.stop()
            print("Stopped.")
        elif line in audio_files:
            filename = os.path.join(SOUNDS_PATH, audio_files[line])
            if os.path.exists(filename):
                sd.stop()
                data, samplerate = sf.read(filename)
                sd.play(amplify(data), samplerate)
                print(f"Playing: {filename}")
            else:
                print(f"Audio file not found: {filename}")

    except KeyboardInterrupt:
        print("\nStopped.")
        sd.stop()
        ser.close()
        break
    except serial.SerialException:
        # Relay switching browns out the USB-serial chip and corrupts the
        # COM port. Silently close and reopen so playback isn't disrupted.
        try:
            ser.close()
        except Exception:
            pass
        time.sleep(1)
        for attempt in range(10):
            try:
                ser = open_serial(port)
                try:
                    ser.reset_input_buffer()
                except Exception:
                    pass
                break
            except serial.SerialException:
                time.sleep(1)
        else:
            print("Could not reconnect to the Arduino. Exiting.")
            break
    except Exception as e:
        print(f"Error: {e}")
