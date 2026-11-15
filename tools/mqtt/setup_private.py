"""Create diagnostic-only credentials without printing passwords or passing them in argv."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bind", required=True)
args = parser.parse_args()
address = ipaddress.ip_address(args.bind)
if not any(address in ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):
    raise SystemExit("Use an RFC1918 private IPv4 address; public/wildcard/loopback bind is not allowed")
private = ROOT / "evidence/local/mqtt-private"
private.mkdir(parents=True, exist_ok=True)
private.chmod(0o700)
files = [private / "device.json", private / "receiver.json"]
if any(p.exists() for p in files) and not all(p.exists() for p in files):
    raise SystemExit("Partial credential state: preserve it and investigate before generating anything")
for role, path in zip(("device", "receiver"), files):
    if path.exists():
        data = json.loads(path.read_text())
        if data.get("host") != args.bind or data.get("port") != 1883 or data.get("username") != f"diag-{role}":
            raise SystemExit("Existing credentials do not match this deployment; refusing implicit rotation")
    else:
        path.write_text(json.dumps({"host": args.bind, "port": 1883, "username": f"diag-{role}",
                                    "password": secrets.token_urlsafe(32)}, indent=2) + "\n")
    path.chmod(0o600)
credentials = [json.loads(p.read_text()) for p in files]
passwords = private / "passwords"
if not passwords.exists():
    passwords.write_text("".join(f"{c['username']}:{c['password']}\n" for c in credentials))
    passwords.chmod(0o600)
    subprocess.run(["docker", "run", "--rm", "--user", "0:0", "-v", f"{private}:/private", IMAGE,
                    "mosquitto_passwd", "-U", "/private/passwords"], check=True)
    os.chown(passwords, 1883, 1883)
    passwords.chmod(0o600)
else:
    if not passwords.read_text().startswith("diag-device:$7$"):
        raise SystemExit("Password file is not the expected hashed Mosquitto format")
(ROOT / "infra/mqtt/.env").write_text(f"MQTT_BIND_ADDRESS={args.bind}\n")
device = credentials[0]
header = ROOT / "firmware/include/mqtt_diag_secrets.h"
header.parent.mkdir(parents=True, exist_ok=True)
header.write_text("#pragma once\n// Private diagnostic-only credentials. Never commit.\n" +
                  "\n".join(f"constexpr char MQTT_DIAG_{key.upper()}[] = {json.dumps(device[key])};"
                            for key in ("host", "username", "password")) + "\n")
header.chmod(0o600)
print(json.dumps({"configured": True, "private_bind": args.bind, "credentials_printed": False}))
