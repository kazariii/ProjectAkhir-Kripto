"""Bounded diagnostic MQTT echo, broker controls, and ESP32/LXC evidence matching."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import ssl
import subprocess
import time
import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "lab/kimia/pqc/diag/request"
REPLY = "lab/kimia/pqc/diag/reply"
TOKEN = re.compile(rb"diag:([0-9a-f]{32})\Z")


import sys
sys.path.insert(0, str(ROOT))
from tools.mqtt.client import MqttConnection as Session, credentials, require


def log(event, **fields):
    print("MQTT_DIAG_SERVER " + json.dumps({"event": event, "utc": datetime.now(timezone.utc).isoformat(),
                                          **fields}), flush=True)


def serve(path):
    with Session(credentials(path), "lxc-diag-") as session:
        require(session.code == 0, "Diagnostic receiver authentication failed")
        require(not isinstance(session.client.socket(), ssl.SSLSocket), "Unexpected TLS transport")

        def received(client, data, message):
            match = TOKEN.fullmatch(message.payload)
            if message.topic != REQUEST or message.retain or not match:
                log("discarded", reason="invalid diagnostic message")
                return
            run_id = match[1].decode("ascii")
            log("request_received", run_id=run_id)
            result = client.publish(REPLY, "ack:" + run_id, qos=0, retain=False)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                log("reply_queued", run_id=run_id)
            else:
                log("reply_failed", run_id=run_id)

        session.client.on_message = received
        # The responder does not wait for QoS-0 acknowledgements or retain their MIDs.
        session.client.on_publish = None
        require(session.subscribe(REQUEST) == [0], "Receiver subscription denied")
        log("ready", port=1883, tls=False)
        while True:
            # Fail/restart instead of pretending a disconnected echo process is ready.
            time.sleep(1)
            require(session.client.is_connected(), "Receiver disconnected")


def check(private):
    device = credentials(private / "device.json")
    receiver = credentials(private / "receiver.json")
    run_id = secrets.token_hex(16)
    with Session(device) as session:
        require(session.code == 0, "Device authentication failed")
        require(not isinstance(session.client.socket(), ssl.SSLSocket), "Unexpected TLS transport")
        require(session.subscribe(REPLY) == [0], "Reply subscription denied")
        request_suback = session.subscribe(REQUEST)
        request_code = session.publish(REQUEST, "diag:" + run_id)
        require(request_code < 128, "Authorized request rejected")
        matched, leaked = False, False
        deadline = time.monotonic() + 5
        last_request = time.monotonic()
        while time.monotonic() < deadline:
            try:
                message = session.messages.get(timeout=0.3)
            except queue.Empty:
                if matched:
                    break
                if time.monotonic() - last_request >= 1:
                    require(session.publish(REQUEST, "diag:" + run_id) < 128, "Authorized retry rejected")
                    last_request = time.monotonic()
                continue
            leaked |= message.topic == REQUEST
            if message.topic == REPLY and not message.retain and message.payload == ("ack:" + run_id).encode():
                matched = True
        require(matched and not leaked, "Missing correlated reply or unauthorized request delivery")
        reply_denied = session.publish(REPLY, "ack:" + run_id)
        telemetry_denied = session.publish("lab/kimia/meja01/telemetry", "diag:" + run_id)
        require(reply_denied == 135 and telemetry_denied == 135, "Out-of-scope device publish accepted")
    with Session(receiver) as session:
        require(session.code == 0, "Receiver authentication failed")
        receiver_denied = session.publish(REQUEST, "diag:" + run_id)
        require(receiver_denied == 135, "Receiver published in device direction")
    bad = {**device, "password": secrets.token_urlsafe(32)}
    with Session(bad, "mqtt-reject-") as session:
        wrong_password = session.code
        require(wrong_password in (134, 135), "Wrong password was not rejected")
    with Session({**device, "username": None}, "mqtt-anon-") as session:
        anonymous = session.code
        require(anonymous in (134, 135), "Anonymous access was not rejected")
    return {"passed": True, "transport": "MQTT over TCP", "port": 1883, "tls": False,
            "run_id": run_id, "correlated_roundtrip": True, "device_request_read_leaked": False,
            "unauthorized_request_suback": request_suback,
            "device_reply_publish": reply_denied, "device_telemetry_publish": telemetry_denied,
            "receiver_request_publish": receiver_denied, "wrong_password_connack": wrong_password,
            "anonymous_connack": anonymous}


def verify_capture(capture):
    text = capture.read_text(encoding="utf-8")
    results = [json.loads(line.partition("MQTT_DIAG_RESULT ")[2]) for line in text.splitlines()
               if "MQTT_DIAG_RESULT " in line]
    require(len(results) == 1 and text.count("MQTT_DIAG_BEGIN ") == 1
            and text.count("MQTT_DIAG_DONE") == 1 and "MQTT_DIAG_FAILED" not in text,
            "Expected one complete successful ESP32 run")
    result = results[0]
    require(result.get("passed") is True and result.get("mqtt_port") == 1883 and result.get("tls") is False,
            "ESP32 did not report a TCP/1883 round trip")
    run_id = result.get("run_id", "")
    require(re.fullmatch(r"[0-9a-f]{32}", run_id), "Invalid run identifier")
    require(result.get("local_ip") == "10.13.37.2", "Expected the documented Wokwi Private Gateway address")
    journal = subprocess.check_output(["journalctl", "-u", "lab-kimia-mqtt-diagnostic.service",
                                       "-o", "cat", "--no-pager"], text=True)
    events = []
    for line in journal.splitlines():
        if line.startswith("MQTT_DIAG_SERVER "):
            event = json.loads(line.partition("MQTT_DIAG_SERVER ")[2])
            if event.get("run_id") == run_id:
                events.append(event)
    require({"request_received", "reply_queued"} <= {e["event"] for e in events},
            "ESP32 identifier has no matching receiver request/reply")
    client_id = "esp32-diag-" + run_id[:12]
    broker_log = subprocess.check_output(["docker", "logs", "lab-kimia-mqtt-pqc-broker-1"],
                                         stderr=subprocess.STDOUT, text=True)
    require(any("New client connected" in line and (" as " + client_id + " (") in line
                and "u'diag-device'" in line for line in broker_log.splitlines()),
            "No matching ESP32 client connection in broker log; native checks do not prove Wokwi")
    return {"verified": True, "provenance": "supplied Wokwi VS Code serial log matched to LXC journal",
            "capture_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
            "esp32": result, "lxc_events": events, "broker_client_id": client_id,
            "broker_device_connection_matched": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "check", "verify-capture"))
    parser.add_argument("--credentials", type=Path)
    parser.add_argument("--private", type=Path, default=ROOT / "evidence/local/mqtt-private")
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "serve":
        credential_path = args.credentials
        if credential_path is None:
            credential_path = Path(os.environ["CREDENTIALS_DIRECTORY"]) / "mqtt.json"
        serve(credential_path)
        return
    if args.command == "check":
        result = check(args.private)
    else:
        require(args.capture is not None, "--capture is required")
        result = verify_capture(args.capture)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
