"""Join supplied ESP32 readings/ACKs with live authenticated receiver, Influx and Grafana."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.telemetry.verify_lxc import journal_events, matched_points, verify_dashboard


def hex_id(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{32}", value) is not None


def serial(text, fault_test=False):
    require(len(re.findall(r"(?m)^\s*TELEMETRY_BEGIN\b", text)) == 1, "Expected exactly one telemetry run")
    require(not re.search(r"panic|Guru Meditation|watchdog|LEDC is not initialized", text, re.I), "Failed startup in capture")
    require(fault_test or "TELEMETRY_CONNECT_FAILED" not in text, "Connection failure in nominal capture")
    entries = []
    samples = {}
    for index, row in enumerate(text.splitlines()):
        marker = re.match(r"\s*TELEMETRY_(RUN|AUTHENTICATED|SENT|STORED) (\{.*\})\s*$", row)
        if marker:
            entries.append((index, marker[1], json.loads(marker[2])))
        sample = re.search(r"Sampel lokal ms=(\d+) (\{.*\})\s*$", row)
        if sample:
            measured = int(sample[1])
            require(measured not in samples, "Duplicate local sample timestamp")
            samples[measured] = json.loads(sample[2])
    runs = [e for _, kind, e in entries if kind == "RUN"]
    require(len(runs) == 1 and hex_id(runs[0].get("run_id")) and runs[0].get("local_ip") == "10.13.37.2", "Missing private Wokwi run identity")
    auth, sent, stored = {}, {}, {}
    for index, kind, event in entries:
        if kind == "RUN":
            continue
        sid = event.get("session_id")
        require(hex_id(sid), "Invalid session identifier")
        if kind == "AUTHENTICATED":
            require(sid not in auth and event.get("run_id") == runs[0]["run_id"] and
                    event.get("mqtt_port") == 1883 and event.get("tls") is False, "Invalid authenticated session marker")
            auth[sid] = index
            continue
        sequence = event.get("counter")
        require(type(sequence) is int and 0 < sequence < 2**64 and sid in auth and auth[sid] < index, "Data lacks prior authenticated session")
        key = (sid, sequence)
        if kind == "SENT":
            require(key not in sent and event.get("measured_ms") in samples, "Missing/duplicate sensor sample for encrypted frame")
            sent[key] = (index, samples[event["measured_ms"]], event["measured_ms"])
        if kind == "STORED":
            require(key not in stored and key in sent and sent[key][0] < index and event.get("ack_verified") is True, "Stored ACK has no sent/verified sample")
            stored[key] = {"session_id": sid, "counter": sequence, "measured_ms": sent[key][2], "sample": sent[key][1]}
    require(bool(stored), "No encrypted storage ACKs in capture")
    states = {int(e["sample"]["gas_alarm"])+2*int(e["sample"]["temperature_alarm"]) for e in stored.values()}
    require(states == {0, 1, 2, 3}, "Capture does not cover all four sensor/alarm states")
    return runs[0], list(stored.values())


def match(run, samples, events, broker):
    client = "esp32-telemetry-"+run["run_id"][:12]
    require(any("New client connected" in row and (" as "+client+" (") in row and "u'diag-device'" in row
                for row in broker.splitlines()), "No ESP32 telemetry broker connection; native controls do not prove Wokwi")
    selected = []
    for sample in samples:
        sid, sequence = sample["session_id"], sample["counter"]
        session = [e for e in events if e.get("event") == "session_established" and e.get("session_id") == sid and
                   e.get("peer_authenticated") is True and e.get("client_key_confirmed") is True]
        stored = [e for e in events if e.get("event") == "telemetry_stored" and e.get("session_id") == sid and e.get("counter") == sequence]
        acks = [e for e in events if e.get("event") == "stored_ack_queued" and e.get("session_id") == sid and e.get("counter") == sequence]
        require(len(session) == len(stored) == len(acks) == 1, "Missing/ambiguous authenticated storage/ACK events")
        require(all(stored[0].get(k) == v for k, v in sample["sample"].items()), "Local sensor payload differs from stored payload")
        require(events.index(session[0]) < events.index(stored[0]) < events.index(acks[0]), "Server event order mismatch")
        selected.append(stored[0])
    return client, selected


def verify(path, fault_test=False):
    raw_text = path.read_text(encoding="utf-8-sig")
    run, samples = serial(raw_text, fault_test=fault_test)
    sent = [json.loads(m[1]) for m in re.finditer(r"(?m)^\s*TELEMETRY_SENT (\{[^\r\n]+\})\s*$", raw_text)]
    confirmed = {(e["session_id"], e["counter"]) for e in samples}
    unconfirmed = [e for e in sent if (e["session_id"], e["counter"]) not in confirmed]
    broker = subprocess.check_output(["docker", "logs", "lab-kimia-mqtt-pqc-broker-1"], stderr=subprocess.STDOUT, text=True)
    client, events = match(run, samples, journal_events(), broker)
    points = matched_points(events)
    # One representative point per state is enough for Grafana query validation.
    representatives = {}
    for point in points:
        state = int(point["gas_alarm"])+2*int(point["temperature_alarm"])
        representatives.setdefault(state, point)
    selected = sorted(representatives.values(), key=lambda p: p["received_ns"])
    source = "user-supplied Wokwi serial"
    provenance_path = path.with_suffix(".provenance.json")
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text())
        require(provenance.get("capture_sha256") == hashlib.sha256(path.read_bytes()).hexdigest(), "Serial provenance hash mismatch")
        source = provenance["source"]
    return {"verified": True, "capture_mode": "fault" if fault_test else "nominal", "collected_utc": datetime.now(timezone.utc).isoformat(),
            "provenance": source + "; sensor readings and encrypted storage ACKs matched to live LXC, InfluxDB and Grafana",
            "capture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "run": run, "broker_client_id": client,
            "sent_samples": len(sent), "unconfirmed_sent_frames": unconfirmed,
            "acked_sensor_samples": samples, "lxc_stored_events": events, "influx_points": points,
            "all_four_states": True, "grafana": verify_dashboard(selected)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--fault-test", action="store_true",
                        help="Allow expected connection failures in a recorded fault exercise; not nominal startup evidence")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/pqc-ticket-04/capture-validation.json")
    args = parser.parse_args()
    result = verify(args.capture, fault_test=args.fault_test)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"verified": True, "run_id": result["run"]["run_id"],
                      "acked_samples": len(result["acked_sensor_samples"]), "four_states": True, "grafana": True}))
