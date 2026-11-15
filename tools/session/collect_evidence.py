"""Collect ticket-03 proof from current binaries, controls and the supplied MCU capture."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.session.verify_capture import verify


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect():
    folder = ROOT / "docs/evidence/pqc-ticket-03"
    folder.mkdir(parents=True, exist_ok=True)
    capture = verify(folder / "esp32-serial.txt")
    (folder / "capture-validation.json").write_text(json.dumps(capture, indent=2) + "\n")
    output = run(str(ROOT / "evidence/local/pqc-session-build/session-test"))
    native = json.loads(output.partition("SESSION_NATIVE_RESULT ")[2])
    require(native["passed"] is True and native["checks"] >= 71, "Native protocol controls failed")
    fixture = Path("/opt/lab-kimia-suhu/pqc-proof/evidence/local")
    proof = json.loads(run(str(ROOT / "evidence/local/pqc-build/pqc-proof"), "selftest",
                          str(fixture / "fixture-01"), str(fixture / "esp32-response.bin")))
    network = json.loads(run(sys.executable, "tools/mqtt/diagnostic.py", "check"))
    require(proof["passed"] and network["passed"], "Earlier ticket regression failed")
    services = {name: run("systemctl", "is-active", name).strip() for name in
                ("lab-kimia-pqc-session.service", "lab-kimia-mqtt-diagnostic.service")}
    require(all(state == "active" for state in services.values()), "Receiver unavailable")
    containers = run("docker", "ps", "--format", "{{.Names}}:{{.Status}}")
    require(all(name + ":Up " in containers for name in
                ("lab-kimia-mqtt-pqc-broker-1", "lab-kimia-suhu-telegraf-1", "lab-kimia-suhu-influxdb-1", "lab-kimia-suhu-grafana-1")), "Required container unavailable")
    grafana = json.loads(run("curl", "-fsS", "http://10.34.211.141:3000/api/health"))
    influx = json.loads(run("curl", "-fsS", "http://127.0.0.1:8086/health"))
    require(grafana["database"] == "ok" and influx["status"] == "pass", "Monitoring health failed")
    build = (ROOT / "evidence/local/session-esp32-build.log").read_text()
    ram = re.search(r"RAM:.*used (\d+) bytes from (\d+) bytes", build)
    flash = re.search(r"Flash:.*used (\d+) bytes from (\d+) bytes", build)
    require(ram and flash and "[SUCCESS]" in build, "Missing successful ESP32 build")
    proof_build = (ROOT / "evidence/local/proof-esp32-regression.log").read_text()
    require("[SUCCESS]" in proof_build, "Proof firmware regression build missing")
    files = ["firmware/src/mqtt_session.cpp", "firmware/platformio.ini", "tools/session/native.cpp",
             "firmware/lib/pqc-proof/src/pqc_crypto.cpp", "firmware/lib/pqc-proof/src/pqc_crypto.h",
             "firmware/lib/pqc-proof/src/pqc_session.cpp", "firmware/lib/pqc-proof/src/pqc_session.h"]
    result = {"ticket": "03", "verified": True, "collected_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "one synthetic encrypted probe and encrypted ACK; sensors/Influx integration is ticket 04",
              "native_protocol": native, "ticket01_regression": proof, "ticket02_regression": network,
              "wokwi": capture["esp32"], "capture_provenance": capture["provenance"],
              "services": services, "grafana_database": grafana["database"], "influx_status": influx["status"],
              "esp32_build": {"passed": True, "ram_bytes": int(ram[1]), "ram_capacity": int(ram[2]),
                              "flash_bytes": int(flash[1]), "flash_capacity": int(flash[2])},
              "proof_esp32_regression_build": True,
              "source_sha256": {name: sha(ROOT / name) for name in files},
              "private_artifact_sha256": {name: sha(ROOT / "evidence/local" / name) for name in
                  ("session-firmware/pqc-session-full.bin", "session-firmware/firmware.elf", "pqc-session-build/libpqc-session.so")},
              "limitations": ["Prospective FN-DSA pinned to ticket-01 commit; no claim of final FIPS 206 compliance",
                              "Custom lab protocol, not an independently audited secure transport",
                              "MQTT credentials, topic metadata and availability are not protected by TLS",
                              "Wokwi success does not establish hardware RNG quality or physical performance"]}
    (folder / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verified": True, "native_checks": native["checks"],
                      "wokwi_run_id": capture["esp32"]["run_id"], "session_id": capture["esp32"]["session_id"]}))


if __name__ == "__main__":
    collect()
