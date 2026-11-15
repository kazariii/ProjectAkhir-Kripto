"""Acceptance evidence must join MCU, receiver and broker, never infer Wokwi from native tests."""
import copy
import json
from pathlib import Path
from tools.session.verify_capture import serial_result, match_events

ROOT = Path(__file__).resolve().parents[1]
capture = (ROOT / "docs/evidence/pqc-ticket-03/esp32-serial.txt").read_text()
evidence = json.loads((ROOT / "docs/evidence/pqc-ticket-03/capture-validation.json").read_text())
result = serial_result(capture)
journal = "\n".join("SESSION_SERVER " + json.dumps(e) for e in evidence["lxc_events"])
broker = "New client connected from private as " + evidence["broker_client_id"] + " (p4, c1, u'diag-device')."
assert match_events(result, journal, broker)["broker_device_connection_matched"]
checks = 1


def rejects(operation):
    global checks
    try:
        operation()
    except (RuntimeError, ValueError):
        checks += 1
    else:
        raise AssertionError("Invalid evidence accepted")


rejects(lambda: serial_result(capture + capture))
rejects(lambda: serial_result(capture.replace("SESSION_DONE", "")))
rejects(lambda: serial_result(capture + "\nSESSION_FAILED timeout\n"))
rejects(lambda: match_events(result, journal, broker.replace("esp32-session-", "native-session-")))
rejects(lambda: match_events(result, journal.replace("encrypted_ack_queued", "reply_failed"), broker))
wrong = copy.deepcopy(result); wrong["session_id"] = "0" * 32
rejects(lambda: match_events(wrong, journal, broker))
print(json.dumps({"passed": True, "evidence_checks": checks}))
