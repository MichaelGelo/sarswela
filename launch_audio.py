Import("env")
import subprocess
import os
import sys
import shutil


def launch_audio_player(source, target, env):
    script = os.path.join(env['PROJECT_DIR'], "audio_player.py")

    # Find a Python interpreter instead of hardcoding a path. Prefer one on
    # PATH (works on any laptop), fall back to the interpreter running this
    # script. Override with the PYTHON env var if needed.
    python = os.environ.get("PYTHON") or shutil.which("python") \
        or shutil.which("py") or sys.executable

    # Build the command as a single string and quote every path. This is what
    # makes it survive folders with spaces (e.g. "Sellyne Palar. project").
    # `start` needs an explicit window title first ("Audio Player"), otherwise
    # it treats the first quoted argument as the title instead of a command.
    inner = f'"{python}" "{script}"'
    command = f'cmd /c start "Audio Player" cmd /k "{inner}"'
    subprocess.Popen(command, shell=True)
    print(f"Audio player launched with: {python}")


env.AddPostAction("upload", launch_audio_player)
