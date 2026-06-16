import serial
import serial.tools.list_ports
import pygame
import time
import os

pygame.mixer.init()

SOUNDS_PATH = r"D:\download\Work Life\Robotics\button_v2\Sounds"

audio_files = {
    "PLAY:blind":    "Blind.wav",
    "PLAY:english":  "English.wav",
    "PLAY:spanish":  "Spanish.wav",
    "PLAY:mandarin": "Mandarin.wav",
}

# Auto-detect Arduino port
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Arduino" in port.description or "CH340" in port.description or "USB Serial" in port.description:
            return port.device
    return None

port = find_arduino_port()
if not port:
    port = input("Arduino port not found. Enter manually (e.g. COM3): ").strip()

print(f"Connecting to {port}...")
ser = serial.Serial(port, 9600)
time.sleep(2)  # wait for Arduino to reset
print("Ready. Listening for button presses...\n")

while True:
    try:
        line = ser.readline().decode('utf-8').strip()
        if not line:
            continue

        print(f"Received: {line}")

        if line in audio_files:
            filename = audio_files[line]
            filename = os.path.join(SOUNDS_PATH, filename)
            if os.path.exists(filename):
                pygame.mixer.music.stop()
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                print(f"Playing: {filename}")
            else:
                print(f"Audio file not found: {filename}")

    except KeyboardInterrupt:
        print("\nStopped.")
        ser.close()
        break
    except Exception as e:
        print(f"Error: {e}")
