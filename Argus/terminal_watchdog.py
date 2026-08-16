#!/usr/bin/env python3
import subprocess
import time

while True:
    try:
        subprocess.run(
            ["python3", "/home/kali/Documents/Argus/terminal_sudo_probe.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=45,
        )
    except Exception:
        pass
    time.sleep(5)
