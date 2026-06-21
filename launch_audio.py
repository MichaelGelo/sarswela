Import("env")
import subprocess
import os
import sys
import shutil


def find_python():
    """Find a real user Python interpreter, not PlatformIO's bundled one.

    PlatformIO runs this hook from inside its own environment
    (.platformio/penv), which is first on PATH and lacks the audio
    libraries. So we must skip any interpreter living under .platformio.
    Set the PYTHON env var to override all of this.
    """
    override = os.environ.get("PYTHON")
    if override:
        return override

    candidates = []
    # The `py` launcher (if present) always resolves a real install.
    launcher = shutil.which("py")
    if launcher:
        candidates.append(launcher)
    # Every python/python3 on PATH, in order.
    for name in ("python", "python3"):
        for path in _which_all(name):
            candidates.append(path)
    # Last resort: whatever is running this hook (likely penv).
    candidates.append(sys.executable)

    for path in candidates:
        if ".platformio" not in path.lower():
            return path
    return sys.executable


def _which_all(name):
    """Like shutil.which but returns every match on PATH, not just the first."""
    results = []
    exts = os.environ.get("PATHEXT", "").split(os.pathsep)
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        base = os.path.join(directory, name)
        for ext in [""] + exts:
            candidate = base + ext
            if os.path.isfile(candidate):
                results.append(candidate)
    return results


def launch_audio_player(source, target, env):
    script = os.path.join(env['PROJECT_DIR'], "audio_player.py")
    python = find_python()

    # Build the command as a single string and quote every path. This is what
    # makes it survive folders with spaces (e.g. "Sellyne Palar. project").
    # `start` needs an explicit window title first ("Audio Player"), otherwise
    # it treats the first quoted argument as the title instead of a command.
    inner = f'"{python}" "{script}"'
    command = f'cmd /c start "Audio Player" cmd /k "{inner}"'
    subprocess.Popen(command, shell=True)
    print(f"Audio player launched with: {python}")


env.AddPostAction("upload", launch_audio_player)
