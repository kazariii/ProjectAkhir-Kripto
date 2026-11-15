"""Validate a complete real ESP32 serial capture before extracting its proof response."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("capture", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
text = args.capture.read_text(encoding="utf-8")
lines = text.splitlines()
begins = [line for line in lines if "PQC_BEGIN " in line]
ends = [line for line in lines if line.strip().endswith("PQC_DONE")]
metrics_lines = [line.partition("PQC_METRICS ")[2] for line in lines if "PQC_METRICS " in line]
responses = [line.partition("PQC_RESPONSE ")[2].strip() for line in lines if "PQC_RESPONSE " in line]
if (len(begins) != 1 or len(ends) != 1 or len(metrics_lines) != 1 or len(responses) != 1
        or any("PQC_FAILED" in line for line in lines)):
    raise SystemExit("FAIL: capture must contain exactly one completed ESP32 proof")
metrics = json.loads(metrics_lines[0])
if metrics.get("target") != "esp32" or metrics.get("passed") is not True or metrics.get("aead_rfc8439") is not True:
    raise SystemExit("FAIL: ESP32 did not report success")
response = bytes.fromhex(responses[0])
if len(response) != 1624 or metrics.get("response_bytes") != len(response):
    raise SystemExit("FAIL: wrong response length")
args.output.write_bytes(response)
print(json.dumps({"capture_sha256": hashlib.sha256(args.capture.read_bytes()).hexdigest(),
                  "response_sha256": hashlib.sha256(response).hexdigest(), "esp32_metrics": metrics}, indent=2))
