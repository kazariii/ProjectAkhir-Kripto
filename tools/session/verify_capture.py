"""Match exactly one user-supplied Wokwi run to authenticated LXC and broker events."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tools.mqtt.client import require


def serial_result(text):
    for marker in ("SESSION_BEGIN", "SESSION_CONNECTED", "SESSION_AUTHENTICATED", "SESSION_RESULT", "SESSION_DONE"):
        require(len(re.findall(r"(?m)^\s*" + marker + r"\b", text)) == 1, "Missing/duplicate marker: " + marker)
    require(not re.search(r"SESSION_FAILED|panic|Guru Meditation|watchdog", text, re.I), "Failed run in capture")
    require(text.index("SESSION_BEGIN") < text.index("SESSION_AUTHENTICATED") < text.index("SESSION_RESULT") < text.index("SESSION_DONE"), "Mixed/out-of-order run")
    match = re.search(r"(?m)^\s*SESSION_RESULT (\{[^\r\n]+\})\s*$", text)
    require(match is not None, "Malformed result JSON")
    result = json.loads(match[1])
    for name in ("passed", "mutual_auth", "key_confirmation", "encrypted_ack_verified"):
        require(result.get(name) is True, "Missing successful " + name)
    for name in ("run_id", "session_id"):
        require(isinstance(result.get(name), str) and re.fullmatch("[0-9a-f]{32}", result[name]), "Invalid " + name)
    require(result.get("mqtt_port") == 1883 and result.get("tls") is False and
            result.get("local_ip") == "10.13.37.2", "Not the private plain-MQTT Wokwi run")
    require(type(result.get("elapsed_ms")) is int and 0 < result["elapsed_ms"] <= 180000, "Invalid elapsed time")
    return result


def match_events(result, journal, broker):
    events = []
    for line in journal.splitlines():
        if line.startswith("SESSION_SERVER "):
            event = json.loads(line.partition("SESSION_SERVER ")[2])
            if event.get("session_id") == result["session_id"]:
                events.append(event)
    established = [e for e in events if e.get("event") == "session_established" and
                   e.get("peer_authenticated") is True and e.get("client_key_confirmed") is True]
    accepted = [e for e in events if e.get("event") == "payload_accepted" and
                e.get("run_id") == result["run_id"] and e.get("device_id") == "esp32-meja01" and
                e.get("temperature_c") == 26.25 and e.get("probe") == "ticket-03"]
    ack = [e for e in events if e.get("event") == "encrypted_ack_queued" and
           e.get("run_id") == result["run_id"] and e.get("bytes") == 207]
    require(len(established) == len(accepted) == len(ack) == 1, "Missing/ambiguous authenticated LXC events")
    require(events.index(established[0]) < events.index(accepted[0]) < events.index(ack[0]), "LXC event order mismatch")
    client = "esp32-session-" + result["run_id"][:12]
    require(any("New client connected" in line and (" as " + client + " (") in line and "u'diag-device'" in line
                for line in broker.splitlines()), "No matching ESP32 broker connection; native control cannot prove Wokwi")
    return {"lxc_events": established + accepted + ack, "broker_client_id": client,
            "broker_device_connection_matched": True}


def verify(path):
    result = serial_result(path.read_text(encoding="utf-8-sig"))
    journal = subprocess.check_output(["journalctl", "-u", "lab-kimia-pqc-session.service", "--no-pager", "-o", "cat"], text=True)
    broker = subprocess.check_output(["docker", "logs", "lab-kimia-mqtt-pqc-broker-1"], stderr=subprocess.STDOUT, text=True)
    return {"verified": True, "provenance": "user-supplied Wokwi VS Code serial matched to live LXC journal and broker",
            "capture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "esp32": result,
            **match_events(result, journal, broker)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.capture)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
