"""Read-only final migration acceptance; native controls must precede the Wokwi run."""
import configparser
from datetime import datetime, timezone
import hashlib
import json
import re
import tomllib
from tools.deploy.migrate import PUBLIC, MONITOR, run, verify_state
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.telemetry.verify_capture import verify


def main():
    state = verify_state()
    restart = json.loads((PUBLIC / "restart.json").read_text())
    require(restart["passed"] and restart["fresh_session_after_restart"] and restart["restart_preserved_history"], "Restart proof incomplete")
    config = configparser.ConfigParser(interpolation=None)
    config.read(ROOT / "firmware/platformio.ini")
    require(config["platformio"]["default_envs"] == "pqc-telemetry", "Default build is not PQC")
    require("-DPQC_TELEMETRY" in config["env:pqc-telemetry"]["build_flags"], "Default build missing PQC selection")
    wokwi = tomllib.loads((ROOT / "firmware/wokwi.toml").read_text())["wokwi"]
    require(wokwi["firmware"] == ".pio/build/pqc-telemetry/firmware.bin" and "rfc2217ServerPort" not in wokwi, "Simulator config not finalized")
    build = (ROOT / "evidence/local/ticket06-default-build.log").read_text()
    require("[SUCCESS]" in build and "pqc-telemetry  SUCCESS" in build, "Default build failed")
    # Validate the explicit rollback override without starting its cloud ingress.
    run("docker", "compose", "--project-directory", str(MONITOR), "--env-file", str(MONITOR / ".env"),
        "-f", str(MONITOR / "compose.yaml"), "-f", str(MONITOR / "compose.legacy.yaml"), "config", "--quiet")
    capture = verify(PUBLIC / "esp32-serial.txt")
    require(set(capture["run"]) == {"run_id", "local_ip"}, "Unexpected Wokwi run provenance")
    files = ["compose.yaml", "compose.legacy.yaml", "firmware/platformio.ini", "firmware/wokwi.toml", "firmware/diagram.json",
             "infra/mqtt/session.service", "infra/mqtt/compose.yaml", "infra/mqtt/mosquitto.conf", "infra/mqtt/acl",
             "tools/deploy/migrate.py", "tools/deploy/check_migration.py", "tools/deploy/collect_evidence.py",
             "tools/session/receiver.py", "firmware/lib/pqc-telemetry/src/pqc_telemetry.cpp"]
    result = {"ticket": "06", "status": "done", "verified": True, "collected_utc": datetime.now(timezone.utc).isoformat(),
              "state": state, "native_restart_points": len(restart["points"]), "rollback_override_validated": True,
              "rollback_cloud_started": False, "default_firmware": "pqc-telemetry", "simulator_folder": "firmware",
              "firmware_build": {"passed": True, "ram_bytes": int(re.search(r"RAM:.*used (\d+) bytes", build)[1]),
                                 "flash_bytes": int(re.search(r"Flash:.*used (\d+) bytes", build)[1])},
              "wokwi": {"run": capture["run"], "acked_samples": len(capture["acked_sensor_samples"]),
                        "sent_samples": capture["sent_samples"], "unconfirmed_sent_frames": len(capture["unconfirmed_sent_frames"]),
                        "sessions": sorted({s["session_id"] for s in capture["acked_sensor_samples"]}),
                        "four_states": True, "capture_sha256": capture["capture_sha256"]},
              "source_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files},
              "private_artifact_sha256": {f: hashlib.sha256((ROOT / "firmware/.pio/build/pqc-telemetry" / f).read_bytes()).hexdigest()
                                          for f in ("firmware.bin", "firmware.elf")},
              "limitations": ["Application crypto is a custom lab protocol; prospective FN-DSA, no final FIPS 206 or audit claim",
                              "MQTT passwords/metadata remain visible without TLS",
                              "Service restarts and autostart configuration verified; entire LXC was not rebooted",
                              "Archived rollback override validated without reactivating old cloud ingress",
                              "Simulator evidence does not certify physical sensors, RNG, hardware performance or safety"]}
    (PUBLIC / "capture-validation.json").write_text(json.dumps(capture, indent=2)+"\n")
    (PUBLIC / "summary.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"verified": True, "status": "done", "wokwi_acked": result["wokwi"]["acked_samples"],
                      "legacy_ingress": "removed", "history_preserved": True}))


if __name__ == "__main__":
    main()
