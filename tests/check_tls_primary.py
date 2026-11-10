"""Inspect actual ESP32/Telegraf captures without TLS decryption keys.

python tests/check_tls_primary.py --esp32-capture <Wokwi PCAP> --telegraf-capture <PCAPNG>
Does not create traffic, restart services, or claim to decrypt MQTT inside TLS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from check_tls_security import executable, fields, PROTECTED, require, ROOT, wire_bytes
from tls_relay import stamp


def inspect(tshark, path, label):
    display_filter = "tcp.port == 8883"
    packets = fields(tshark, path, display_filter, ["frame.number"])
    protected = fields(tshark, path, display_filter + " && " + PROTECTED,
                       ["frame.number"], [(8883, "tls")])
    hellos = fields(tshark, path, "tls.handshake.type == 2",
                    ["tls.handshake.version", "tls.handshake.ciphersuite"], [(8883, "tls")])
    require(bool(packets) and bool(protected), label + ": expected protected TLS records on port 8883")
    directions = wire_bytes(tshark, path, display_filter)
    # Search field names + sensor ID, not a generic number such as 25 which can
    # coincidentally occur in a certificate/record. Absence alone isn't TLS proof.
    needles = (b"temperature_c", b"gas_raw", b'"device_id"', b"esp32-meja01")
    require(not any(needle in stream for needle in needles for stream in directions),
            label + ": telemetry plaintext is visible")
    require(not fields(tshark, path, display_filter + " && mqtt", ["frame.number"]),
            label + ": decrypted/plain MQTT unexpectedly visible")
    return {"link": label, "capture": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "mqtt_port": 8883, "tcp_frames": len(packets), "protected_tls_frames": len(protected),
            "server_hellos": [{"legacy_version": r[0], "cipher_suite": r[1]} for r in hellos],
            "telemetry_plaintext_found": False, "decryption_keys_supplied": False,
            "limitation": "MQTT identity/content established by project configuration and live flow, not decrypted capture"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--esp32-capture", type=Path, required=True)
    parser.add_argument("--telegraf-capture", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "evidence/local/ticket-06/primary-result.json"
    report = {"checked_utc": stamp(), "status": "running", "checks": []}
    try:
        tshark = executable("tshark", "C:/Program Files/Wireshark/tshark.exe")
        for label, path in (("ESP32 -> EMQX", args.esp32_capture), ("Telegraf -> EMQX", args.telegraf_capture)):
            report["checks"].append(inspect(tshark, path, label))
            print("PASS: " + label)
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__)
        if isinstance(error, AssertionError):
            report["failure"] = str(error)
        print("FAIL: primary capture validation", file=sys.stderr)
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Evidence: " + str(output))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
