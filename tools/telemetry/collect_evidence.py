"""Record ticket-04 checks; completion requires a separately verified real Wokwi capture."""
from datetime import datetime, timezone
import hashlib
import io
import json
import re
import subprocess
import sys
import unittest
from tools.session.native import ROOT
from tools.telemetry.verify_capture import verify
from tools.telemetry.verify_lxc import request
from tools.mqtt.client import require


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def main():
    folder = ROOT / "docs/evidence/pqc-ticket-04"
    folder.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromNames(["tests.test_pqc_telemetry", "tests.test_telemetry_capture"])
    output = io.StringIO()
    tests = unittest.TextTestRunner(stream=output).run(suite)
    require(tests.wasSuccessful(), "Telemetry/evidence unit checks failed")
    sensors = run(sys.executable, "-m", "tests.check_pqc_sensor_cycle")
    legacy = run(sys.executable, "tests/check_firmware_cycle.py", "--compiler", "/usr/bin/g++")
    protocol = json.loads(run(str(ROOT / "evidence/local/pqc-session-build/session-test")).partition("SESSION_NATIVE_RESULT ")[2])
    require(protocol["passed"] and protocol["checks"] >= 71, "Session regression failed")
    build = (ROOT / "evidence/local/telemetry-esp32-build.log").read_text()
    old_build = (ROOT / "evidence/local/telemetry-legacy-build.log").read_text()
    ram = re.search(r"RAM:.*used (\d+) bytes from (\d+) bytes", build)
    flash = re.search(r"Flash:.*used (\d+) bytes from (\d+) bytes", build)
    require(ram and flash and "[SUCCESS]" in build and "[SUCCESS]" in old_build, "Missing successful firmware builds")
    native = json.loads((folder / "native-storage-grafana.json").read_text())
    require(native["passed"], "Native storage/Grafana control failed")
    grafana = json.loads(request("http://10.34.211.141:3000/api/health"))
    influx = json.loads(request("http://127.0.0.1:8086/health"))
    require(grafana["database"] == "ok" and influx["status"] == "pass", "Monitoring health failed")
    services = {name: run("systemctl", "is-active", name).strip() for name in
                ("lab-kimia-pqc-session.service", "lab-kimia-mqtt-diagnostic.service")}
    require(all(s == "active" for s in services.values()), "Receiver service unavailable")
    capture = None
    capture_path = folder / "esp32-serial.txt"
    if capture_path.exists():
        capture = verify(capture_path)
        (folder / "capture-validation.json").write_text(json.dumps(capture, indent=2)+"\n")
    files = ["firmware/src/main.cpp", "firmware/include/pending_sample.h", "firmware/include/telemetry.h",
             "firmware/include/monitoring.h", "firmware/lib/pqc-telemetry/src/pqc_telemetry.cpp",
             "firmware/lib/pqc-telemetry/src/pqc_telemetry.h", "firmware/platformio.ini", "tools/session/receiver.py",
             "tools/telemetry/storage.py", "infra/mqtt/session.service", "infra/grafana/dashboards/suhu.json",
             "tools/telemetry/simulator/wokwi.toml", "tools/telemetry/simulator/diagram.json", "firmware/mq2-level.chip.wasm"]
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
    artifacts = {name: hashlib.sha256((ROOT / "evidence/local/telemetry-firmware" / name).read_bytes()).hexdigest()
                 for name in ("pqc-telemetry-full.bin", "firmware.elf")}
    result = {"ticket": "04", "implemented": True, "verified": capture is not None,
              "status": "done" if capture else "ready-for-human", "collected_utc": datetime.now(timezone.utc).isoformat(),
              "unit_tests": {"passed": True, "tests": tests.testsRun},
              "pqc_sensor_loop_regression": sensors.splitlines(), "legacy_sensor_loop_regression": legacy.splitlines(),
              "session_regression": protocol, "native_storage_grafana": "native-storage-grafana.json",
              "wokwi": None if capture is None else {"run": capture["run"], "acked_samples": len(capture["acked_sensor_samples"]),
                       "sent_samples": capture["sent_samples"], "unconfirmed_sent_frames": len(capture["unconfirmed_sent_frames"]),
                       "session_ids": sorted({e["session_id"] for e in capture["acked_sensor_samples"]}),
                       "four_states": capture["all_four_states"], "provenance": capture["provenance"]},
              "firmware_build": {"passed": True, "ram_bytes": int(ram[1]), "flash_bytes": int(flash[1]), "legacy_build_passed": True},
              "grafana_database": grafana["database"], "influx_status": influx["status"], "services": services,
              "source_sha256": hashes, "private_artifact_sha256": artifacts,
              "limitations": ["Prospective FN-DSA; custom lab protocol, no production security certification",
                              "MQTT metadata and broker credentials remain plaintext without TLS",
                              "Rekey at 180s endpoint age can pause telemetry about 12 simulated seconds; local sensors/alarms continue",
                              "Wokwi virtual time can lag LXC wall time; missing storage ACKs trigger a fresh handshake after 10 virtual seconds",
                              "Legacy ingress remains available until migration ticket 06; run one simulator at a time",
                              "Wokwi does not prove physical sensor calibration, RNG quality or hardware performance"]}
    (folder / "summary.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"implemented": True, "verified": result["verified"], "status": result["status"], "unit_tests": tests.testsRun}))


if __name__ == "__main__":
    main()
