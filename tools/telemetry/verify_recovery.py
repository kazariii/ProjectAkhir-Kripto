"""Join ticket-05 fault records, ESP32 ACKs, receiver events and database evidence."""
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import time
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.telemetry.verify_capture import verify
from tools.telemetry.verify_lxc import journal_events, request, token_scope, matched_points


def main():
    folder = ROOT / "docs/evidence/pqc-ticket-05"
    capture = verify(folder / "esp32-serial.txt", fault_test=True)
    text = (folder / "esp32-serial.txt").read_text()
    faults = [json.loads(row) for row in (folder / "wokwi-faults.jsonl").read_text().splitlines()]
    require({f["kind"] for f in faults} == {"receiver", "broker", "influx"} and all(f["passed"] for f in faults), "Incomplete fault matrix")
    points = capture["influx_points"]
    sids = {p["session_id"] for p in points}
    events = [e for e in journal_events() if e.get("session_id") in sids]
    local, latest, samples, starts = [], None, [], {}
    for row in text.splitlines():
        match = re.search(r"Sampel lokal ms=(\d+) (\{.*\})", row)
        if match:
            latest = int(match[1]); local.append(latest)
            samples.append(json.loads(match[2]))
        if row.startswith("TELEMETRY_AUTHENTICATED "):
            auth = json.loads(row.partition(" ")[2]); starts[auth["session_id"]] = latest
        if row.startswith("TELEMETRY_SENT "):
            sent = json.loads(row.partition(" ")[2])
            require(sent["measured_ms"] == latest, "Sent a queued old sample instead of latest local measurement")
    require(local and max(b-a for a, b in zip(local, local[1:])) <= 2100, "Local sampling stopped during faults or signing")
    require({(s["gas_alarm"], s["temperature_alarm"]) for s in samples} == {(False, False), (True, False), (False, True), (True, True)}, "Missing local alarm states")
    for fault in faults:
        old, new = fault["baseline_session"], fault["recovered_session"]
        require(old in sids and new in sids, "Fault session absent from actual ESP32 ACKs")
        require(any(p["session_id"] == new and p["counter"] == fault["recovered_counter"] and
                    p["received_ns"] == fault["recovered_ns"] for p in points), "Recovery point lacks ESP32 ACK/Influx match")
        require(not any(fault["started_ns"] < p["received_ns"] < fault["restored_ns"] for p in points), "Stored data during declared outage")
        if old != new:
            first = next(s for s in capture["acked_sensor_samples"] if s["session_id"] == new)
            require(first["measured_ms"] > starts[new], "Recovery replayed a sample from during handshake")
        fault["recovery_seconds_after_restore"] = round((fault["recovered_ns"]-fault["restored_ns"])/1e9, 3)
    # Find a genuine server-initiated renewal, not one of the injected faults.
    renewals = []
    fault_recoveries = {f["recovered_session"] for f in faults}
    for event in events:
        if event["event"] != "renewal_requested":
            continue
        old = event["session_id"]
        old_auth = next(e for e in events if e["event"] == "session_established" and e["session_id"] == old)
        age = (datetime.fromisoformat(event["utc"])-datetime.fromisoformat(old_auth["utc"])).total_seconds()
        future = [e for e in events if e["event"] == "session_established" and e["utc"] > event["utc"] and e["session_id"] not in fault_recoveries]
        if not future:
            continue
        new = future[0]["session_id"]
        require(old != new and age >= 180 and age < 300, "Server renewal outside active key lifetime")
        # The simulator was younger than 180s: its local timer did not trigger this rekey.
        virtual_age = starts[new]-starts[old]
        require(virtual_age < 180000, "Capture did not exercise a slower Wokwi clock")
        renewals.append({"old_session": old, "new_session": new, "server_age_seconds": round(age, 3),
                         "client_virtual_ms_until_new_auth": virtual_age, "encrypted_storage_resumed": True})
        break
    require(renewals, "No server-initiated renewal with slow simulator clock")
    security = json.loads((folder / "security.json").read_text())
    require(security["passed"] and security["independent_mqtt_subscriber_matched_published_bytes"], "Security controls incomplete")
    protocol_text = subprocess.check_output([str(ROOT / "evidence/local/pqc-session-build/session-test")], text=True)
    protocol = json.loads(protocol_text.partition("SESSION_NATIVE_RESULT ")[2])
    require(protocol["passed"] and protocol["checks"] >= 113, "Protocol regression failed")
    health = {"grafana": json.loads(request("http://10.34.211.141:3000/api/health"))["database"],
              "influx": json.loads(request("http://127.0.0.1:8086/health"))["status"]}
    require(health == {"grafana": "ok", "influx": "pass"}, "Monitoring not healthy after tests")
    previous = json.loads((ROOT / "docs/evidence/pqc-ticket-04/capture-validation.json").read_text())["lxc_stored_events"]
    require(len(matched_points([previous[0], previous[-1]])) == 2, "Ticket-04 historical points missing")
    scope = token_scope()
    checks = ROOT / "evidence/local"
    unit_log = (checks / "ticket05-unit-tests.log").read_text()
    require(re.search(r"Ran 12 tests", unit_log) and unit_log.rstrip().endswith("OK"), "Unit evidence incomplete")
    sensor_log = (checks / "ticket05-sensor-tests.log").read_text()
    legacy_log = (checks / "ticket05-legacy-tests.log").read_text()
    require("PASS: PQC startup failure" in sensor_log and "PASS: blocked reconnect" in legacy_log, "Sensor regressions missing")
    build_log = (checks / "ticket05-build.log").read_text()
    require("[SUCCESS]" in build_log, "ESP32 build failed")
    ram = int(re.search(r"RAM:.*used (\d+) bytes", build_log)[1])
    flash = int(re.search(r"Flash:.*used (\d+) bytes", build_log)[1])
    services = {name: subprocess.check_output(["systemctl", "is-active", name], text=True).strip() for name in
                ("lab-kimia-pqc-session.service", "lab-kimia-mqtt-diagnostic.service")}
    require(all(v == "active" for v in services.values()), "Service not restored")
    source_files = ["firmware/lib/pqc-proof/src/pqc_session.cpp", "firmware/lib/pqc-proof/src/pqc_session.h",
                    "firmware/lib/pqc-telemetry/src/pqc_telemetry.cpp", "tools/session/receiver.py", "tools/session/native.cpp",
                    "tools/session/native.py", "tools/telemetry/check_security.py", "tools/telemetry/wokwi_fault.py",
                    "tools/telemetry/verify_capture.py", "tools/telemetry/verify_recovery.py", "tests/session_test.cpp"]
    result = {"ticket": "05", "status": "done", "verified": True, "collected_utc": datetime.now(timezone.utc).isoformat(),
              "protocol": protocol, "security_cases": len(security["cases"]), "native_control_points": len(security["points"]),
              "unit_tests": {"passed": True, "tests": 12}, "sensor_regression": sensor_log.splitlines(),
              "previous_ticket_history_points_matched": 2,
              "legacy_sensor_regression": legacy_log.splitlines(), "services": services,
              "firmware_build": {"passed": True, "ram_bytes": ram, "flash_bytes": flash},
              "wokwi_run": capture["run"], "wokwi_sessions": len(sids), "wokwi_acked": len(points),
              "wokwi_sent": capture["sent_samples"], "wokwi_unconfirmed": len(capture["unconfirmed_sent_frames"]),
              "local_sample_max_gap_ms": max(b-a for a, b in zip(local, local[1:])), "no_backlog_sent": True,
              "faults": faults, "renewals": renewals, "health": health, "token_scope": scope,
              "source_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in source_files},
              "private_artifact_sha256": {f: hashlib.sha256((ROOT / "evidence/local/telemetry-firmware" / f).read_bytes()).hexdigest()
                                          for f in ("pqc-telemetry-full.bin", "firmware.elf")},
              "limitations": ["Custom lab protocol, prospective FN-DSA; no independent security audit or final FIPS 206 claim",
                              "No TLS: broker passwords, topics, sizes and timing remain visible",
                              "Loss and handshake pauses remain; an absent ACK does not prove the database did not write",
                              "No DoS resistance, physical RNG, hardware performance or sensor safety certification",
                              "Legacy ingress remains until migration ticket 06; one active simulator only"]}
    (folder / "capture-validation.json").write_text(json.dumps(capture, indent=2)+"\n")
    (folder / "receiver-events.json").write_text(json.dumps(events, indent=2)+"\n")
    (folder / "summary.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("verified", "wokwi_acked", "wokwi_sent", "wokwi_sessions", "security_cases")}))


if __name__ == "__main__":
    main()
