"""Prove that native controls and incomplete logs cannot close the Wokwi acceptance gate."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
summary = json.loads((ROOT / "docs/evidence/pqc-ticket-02/summary.json").read_text())
native_id = summary["native_controls"]["run_id"]
fake_result = {"passed": True, "run_id": native_id, "mqtt_port": 1883, "tls": False,
               "local_ip": "10.13.37.2", "roundtrip_ms": 1}
native_as_esp32 = "MQTT_DIAG_BEGIN ticket=02 transport=MQTT-TCP\nMQTT_DIAG_RESULT " + json.dumps(fake_result) + "\nMQTT_DIAG_DONE\n"
cases = [
    ("native run cannot prove Wokwi", native_as_esp32, "native checks do not prove Wokwi"),
    ("incomplete serial capture", native_as_esp32.replace("MQTT_DIAG_DONE", ""), "Expected one complete"),
    ("multiple runs mixed", native_as_esp32 + native_as_esp32, "Expected one complete"),
]
checks = []
with tempfile.TemporaryDirectory(prefix="mqtt-capture-") as directory:
    for index, (name, capture, expected) in enumerate(cases):
        file = Path(directory) / f"case-{index}.txt"
        file.write_text(capture)
        result = subprocess.run([sys.executable, str(ROOT / "tools/mqtt/diagnostic.py"),
                                 "verify-capture", "--capture", str(file)], capture_output=True, text=True)
        if result.returncode == 0 or expected not in result.stderr:
            raise SystemExit(f"FAIL: {name} was not rejected by the intended gate")
        checks.append({"case": name, "rejected": True})
report = {"passed": True, "checks": checks}
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
