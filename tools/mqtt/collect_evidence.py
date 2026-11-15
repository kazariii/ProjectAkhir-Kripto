"""Record actual broker checks; native success never stands in for Wokwi execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from diagnostic import check, verify_capture

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--capture", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
broker = json.loads(subprocess.check_output(["docker", "inspect", "lab-kimia-mqtt-pqc-broker-1"], text=True))[0]
ports = broker["HostConfig"]["PortBindings"]["1883/tcp"]
if not broker["State"]["Running"] or len(ports) != 1 or ports[0]["HostPort"] != "1883":
    raise SystemExit("FAIL: unexpected broker listener state")
address = ipaddress.ip_address(ports[0]["HostIp"])
if not any(address in ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):
    raise SystemExit("FAIL: broker is not bound exclusively to a private IPv4")
expected = json.loads(subprocess.check_output(
    ["docker", "compose", "-f", str(ROOT / "infra/mqtt/compose.yaml"), "config", "--format", "json"], text=True))
if broker["Config"]["Image"] != expected["services"]["broker"]["image"]:
    raise SystemExit("FAIL: running broker does not match pinned image")
build = (ROOT / "build-esp32.log").read_text()
ram = re.search(r"RAM:.*used (\d+) bytes from (\d+) bytes", build)
flash = re.search(r"Flash:.*used (\d+) bytes from (\d+) bytes", build)
if not ram or not flash or "[SUCCESS]" not in build:
    raise SystemExit("FAIL: no successful diagnostic ESP32 build")
network = json.loads((ROOT / "evidence/local/mqtt-private/laptop-network.json").read_text(encoding="utf-8-sig"))
if network.get("tcp_success") is not True:
    raise SystemExit("FAIL: laptop TCP reachability has not been verified")
report = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "ticket 02 diagnostic connectivity; no application cryptographic session or InfluxDB writes",
    "broker": {"image": broker["Config"]["Image"], "private_bind": str(address), "port": 1883,
               "read_only": broker["HostConfig"]["ReadonlyRootfs"], "container_user": broker["Config"]["User"]},
    "laptop_network": network,
    "native_controls": check(ROOT / "evidence/local/mqtt-private"),
    "broker_restart_controls": json.loads((ROOT / "evidence/local/restart-check.json").read_text()),
    "esp32_build": {"passed": True, "static_ram_bytes": int(ram[1]), "flash_bytes": int(flash[1]),
                    "image_sha256": hashlib.sha256((ROOT / "evidence/local/mqtt-diagnostic-full.bin").read_bytes()).hexdigest()},
    "simulator_runtime": {"verified": False, "reason": "awaiting Wokwi VS Code Private Gateway run"},
}
if args.capture:
    report["simulator_runtime"] = verify_capture(args.capture)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"native_passed": report["native_controls"]["passed"],
                  "wokwi_verified": report["simulator_runtime"]["verified"]}))
