#!/usr/bin/env python3
import datetime
import subprocess
import time

while True:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    result = subprocess.run(
        ["python3", "/home/kali/Documents/Argus/milix_hold.py", "--install"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    output = (result.stdout + result.stderr).strip().replace("\n", " | ")
    print(f"{now} {output}", flush=True)
    time.sleep(5)
