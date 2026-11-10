"""Bounded MQTT session interruption for the owner's Wokwi demonstration.

python tests/demo_mqtt_outage.py --seconds 90
Uses the existing ESP32 account and client ID to displace the simulator.
Never publishes, subscribes, changes broker policy, or touches Telegraf's ID.
"""
import argparse
import json
import ssl
import sys
import time
from datetime import datetime, timezone

from check_mqtt_access import ROOT, configuration, require
from mqtt_probe import Probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=90, choices=range(1, 301),
                        metavar="1..300")
    args = parser.parse_args()
    report = {"started_utc": datetime.now(timezone.utc).isoformat(),
              "requested_seconds": args.seconds, "client_id": "esp32-meja01",
              "successful_takeovers": 0, "publishes": 0, "status": "running"}
    output = ROOT / "evidence/local/ticket-07/outage.json"
    try:
        env, firmware = configuration()
        context = ssl.create_default_context(cafile=str(ROOT / "infra/certs/emqx-ca.pem"))
        deadline = time.monotonic() + args.seconds
        print("Mengganggu sesi ESP32 pada broker demo; tidak mengirim telemetry. Ctrl+C untuk berhenti.", flush=True)
        while time.monotonic() < deadline:
            with Probe(env["MQTT_HOST"], 8883, context) as probe:
                require(probe.connect("esp32-meja01", firmware["MQTT_USERNAME"],
                                      firmware["MQTT_PASSWORD"]) == 0,
                        "Takeover did not receive CONNACK 0")
                report["successful_takeovers"] += 1
                time.sleep(min(0.3, max(0, deadline - time.monotonic())))
        report["status"] = "completed"
    except KeyboardInterrupt:
        report["status"] = "stopped"
    except Exception as error:
        # Exception messages/commands may contain local configuration. Log type only.
        report.update(status="failed", error_type=type(error).__name__)
        print("Gangguan gagal; lihat jenis error pada bukti lokal.", file=sys.stderr)
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Gangguan dihentikan; ESP32 dapat reconnect dengan konfigurasi semula.", flush=True)
        print("Bukti: " + str(output), flush=True)
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
