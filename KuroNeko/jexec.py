#!/usr/bin/env python3
import http.cookiejar
import json
import sys
import time
import urllib.request
import uuid

import websocket

BASE = "http://159.223.40.205:8888"
command = " ".join(sys.argv[1:])
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(BASE + "/tree").read()
xsrf = next(cookie.value for cookie in cj if cookie.name == "_xsrf")
cookie_header = "; ".join(f"{cookie.name}={cookie.value}" for cookie in cj)
request = urllib.request.Request(
    BASE + "/api/kernels",
    data=b"{}",
    headers={"Content-Type": "application/json", "X-XSRFToken": xsrf, "Cookie": cookie_header},
    method="POST",
)
kernel_id = json.load(opener.open(request))["id"]
session_id = str(uuid.uuid4())
socket = websocket.create_connection(
    f"ws://159.223.40.205:8888/api/kernels/{kernel_id}/channels?session_id={session_id}",
    origin=BASE,
    cookie=cookie_header,
    timeout=60,
)
message_id = str(uuid.uuid4())
code = f"import subprocess; result=subprocess.run(['sh','-lc',{command!r}], capture_output=True, text=True); print(result.stdout); print(result.stderr)"
message = {
    "header": {"msg_id": message_id, "username": "MiliX", "session": session_id, "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "msg_type": "execute_request", "version": "5.3"},
    "parent_header": {}, "metadata": {},
    "content": {"code": code, "silent": False, "store_history": False, "user_expressions": {}, "allow_stdin": False, "stop_on_error": True},
    "channel": "shell", "buffers": [],
}
socket.send(json.dumps(message))
while True:
    reply = json.loads(socket.recv())
    if reply.get("parent_header", {}).get("msg_id") != message_id:
        continue
    kind = reply.get("msg_type") or reply.get("header", {}).get("msg_type")
    content = reply.get("content", {})
    if kind == "stream":
        print(content.get("text", ""), end="")
    elif kind == "error":
        print(content)
    elif kind == "status" and content.get("execution_state") == "idle":
        break
