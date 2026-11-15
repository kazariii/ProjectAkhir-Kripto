"""Collect actual LXC controls, build measurements, and optional ESP32 serial proof.

Run on Linux after building the host tool and ESP32 proof. No monitoring service
is contacted. A build or a native control never sets esp32_runtime.verified true.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fixture", type=Path, default=ROOT / "evidence/local/fixture-01")
parser.add_argument("--capture", type=Path)
parser.add_argument("--runtime-image", type=Path,
                    help="the actual image supplied to the simulator, distinct from later rebuilds")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.capture and not args.runtime_image:
    parser.error("--capture requires --runtime-image to identify the tested firmware")
binary = ROOT / "evidence/local/pqc-build/pqc-proof"


def run_json(*command):
    return json.loads(subprocess.check_output([str(x) for x in command], text=True))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


lock_path = ROOT / "tools/pqc/sources.lock.json"
lock = json.loads(lock_path.read_text())
verified_sources = 0
for package in lock["packages"]:
    for name, expected in package["files"].items():
        if sha(ROOT / "firmware/lib" / package["name"] / name) != expected:
            raise SystemExit(f"FAIL: upstream source hash mismatch: {package['name']}/{name}")
        verified_sources += 1

native_response = ROOT / "evidence/local/native-response.bin"
metrics = run_json(binary, "respond", args.fixture, native_response)
positive = run_json(binary, "verify", args.fixture, native_response)
negative = run_json(binary, "selftest", args.fixture, native_response)
if not (positive.get("verified") is True and negative.get("passed") is True):
    raise SystemExit("FAIL: native controls did not pass")

build_log = (ROOT / "build-esp32.log").read_text()
ram = re.search(r"RAM:.*used (\d+) bytes from (\d+) bytes", build_log)
flash = re.search(r"Flash:.*used (\d+) bytes from (\d+) bytes", build_log)
if not ram or not flash or "[SUCCESS]" not in build_log:
    raise SystemExit("FAIL: no successful ESP32 build measurement")
report = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "ticket 01 isolated one-message proof; no MQTT session or production migration",
    "profile": "ML-KEM-512 / ChaCha20-Poly1305-IETF / prospective FN-DSA degree 512",
    "source_lock_sha256": sha(lock_path),
    "upstream_files_verified": verified_sources,
    "sources": [{k: p[k] for k in ("name", "commit", "revision", "url")} for p in lock["packages"]],
    "lxc_native": {"architecture": platform.machine(), "metrics": metrics,
                   "positive": positive, "negative": negative},
    "esp32_build": {"passed": True, "static_ram_bytes": int(ram[1]),
                    "ram_capacity_bytes": int(ram[2]), "flash_bytes": int(flash[1]),
                    "application_partition_bytes": int(flash[2]),
                    "full_image_sha256": sha(ROOT / "evidence/local/pqc-proof-full.bin")},
    "esp32_runtime": {"verified": False, "reason": "awaiting actual ESP32/Wokwi serial capture"},
}
if args.capture:
    response = ROOT / "evidence/local/esp32-response.bin"
    capture_meta = run_json("python3", ROOT / "tools/pqc/extract_capture.py", args.capture, response)
    cross_positive = run_json(binary, "verify", args.fixture, response)
    cross_negative = run_json(binary, "selftest", args.fixture, response)
    if not (cross_positive.get("verified") is True and cross_negative.get("passed") is True):
        raise SystemExit("FAIL: ESP32 response did not pass LXC verification")
    report["esp32_runtime"] = {
        "verified": True,
        "provenance": "supplied ESP32/Wokwi serial capture; not hardware attestation",
        "runtime_image_sha256": sha(args.runtime_image),
        **capture_meta, "lxc_verification": cross_positive, "negative_controls": cross_negative,
    }
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"report": str(args.output), "native_passed": True,
                  "esp32_runtime_verified": report["esp32_runtime"]["verified"]}))
