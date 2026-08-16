#!/bin/bash
set -eu
install -d -m 700 -o root -g root /root/.ssh
printf '%s\n' 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICPDBDKRfoXApV0SCMQcTUOiBbm1S5eD4Zv3OMfi40NL MiliX-koth' > /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
chown root:root /root/.ssh/authorized_keys
printf '%s\n' '[Unit]' 'Description=MiliX throne keeper' 'After=network.target' '' '[Service]' 'Type=simple' 'ExecStart=/bin/bash -c while\ true\;\ do\ printf\ MiliX\ \>\ /root/king.txt\;\ sleep\ 1\;\ done' 'Restart=always' 'RestartSec=1' '' '[Install]' 'WantedBy=multi-user.target' > /etc/systemd/system/milix-throne.service
chmod 644 /etc/systemd/system/milix-throne.service
systemctl daemon-reload
systemctl enable --now milix-throne.service
