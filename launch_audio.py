Import("env")
import subprocess
import os

PYTHON = r"C:\Users\MichaelGelo\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe"

def launch_audio_player(source, target, env):
    script = os.path.join(env['PROJECT_DIR'], "audio_player.py")
    subprocess.Popen(
        ["cmd", "/c", "start", "cmd", "/k", PYTHON, script],
        shell=True
    )
    print("Audio player launched.")

env.AddPostAction("upload", launch_audio_player)
