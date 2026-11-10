"""Exercise the production JSON parser with Telegraf's native file input.

This checks the parser boundary, not MQTT, TLS, InfluxDB, or Grafana runtime.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time


def main():
    args = argparse.ArgumentParser(description=__doc__)
    runner = args.add_mutually_exclusive_group(required=True)
    runner.add_argument("--telegraf", help="Path to Telegraf 1.40.3 executable")
    runner.add_argument("--docker", action="store_true", help="Use the pinned Compose image")
    options = args.parse_args()
    root = Path(__file__).resolve().parents[1]
    production = (root / "infra/telegraf/telegraf.conf").read_text(encoding="utf-8")
    # Reuse the production parser verbatim, changing only the service input to a
    # deterministic file input. Service MQTT input cannot be tested with --test.
    parser = production[production.index("  [[inputs.mqtt_consumer.json_v2]]"):
                        production.index("[[outputs.influxdb_v2]]")]
    parser = parser.replace("inputs.mqtt_consumer", "inputs.file")
    cases = [
        ("same metric, numeric sensors, identity tag, reception timestamp",
         {"device_id": "esp32-meja01", "temperature_c": 27.5, "gas_raw": 1200, "timestamp": 0}, True),
        ("gas rises with fixed temperature",
         {"device_id": "esp32-meja01", "temperature_c": 27.5, "gas_raw": 3000}, True),
        ("temperature rises with fixed gas",
         {"device_id": "esp32-meja01", "temperature_c": 40, "gas_raw": 1200}, True),
        ("zero gas is a measured integer",
         {"device_id": "esp32-meja01", "temperature_c": 27.5, "gas_raw": 0}, True),
        ("ticket-01 payload remains compatible without invented gas",
         {"device_id": "esp32-meja01", "temperature_c": 27.5}, True),
        ("missing temperature rejected", {"device_id": "esp32-meja01"}, False),
        ("missing device identity rejected", {"temperature_c": 27.5, "gas_raw": 1200}, False),
        ("nonnumeric temperature rejected",
         {"device_id": "esp32-meja01", "temperature_c": "broken"}, False),
        ("nonnumeric gas rejected",
         {"device_id": "esp32-meja01", "temperature_c": 27.5, "gas_raw": "broken"}, False),
    ]
    for gas_alarm, temperature_alarm in ((False, False), (True, False), (False, True), (True, True)):
        cases.append((f"boolean alarm pair gas={gas_alarm} temperature={temperature_alarm}",
                      {"device_id": "esp32-meja01", "temperature_c": 40 if temperature_alarm else 25,
                       "gas_raw": 1200, "gas_alarm": gas_alarm, "temperature_alarm": temperature_alarm}, True))
    with tempfile.TemporaryDirectory(prefix="telemetry-parser-") as directory:
        payload_path = Path(directory) / "payload.json"
        config = Path(directory) / "parser-test.conf"
        config.write_text(
            '[agent]\n  omit_hostname = true\n[[inputs.file]]\n  files = ['
            + json.dumps("/parser/payload.json" if options.docker else payload_path.as_posix())
            + ']\n  data_format = "json_v2"\n' + parser
            + '\n[[outputs.file]]\n  files = ["stdout"]\n', encoding="utf-8")
        if options.docker:
            compose = (root / "compose.yaml").read_text(encoding="utf-8")
            image = re.search(r"image: (telegraf:[^\s]+)", compose).group(1)
            command = ["docker", "run", "--rm", "--network", "none", "--mount",
                       f"type=bind,source={directory},target=/parser,readonly", image,
                       "telegraf", "--config", "/parser/parser-test.conf", "--test"]
        else:
            command = [options.telegraf, "--config", str(config), "--test"]
        for name, payload, valid in cases:
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            before = time.time_ns()
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=30, check=False)
            after = time.time_ns()
            matches = re.findall(
                r"^> suhu,device_id=esp32-meja01 ([^ ]+) ([0-9]+)$",
                result.stdout, re.M)
            if valid:
                assert result.returncode == 0, result.stderr
                assert len(matches) == 1, result.stdout + result.stderr
                fields, stamp = matches[0]
                values = dict(field.split("=", 1) for field in fields.split(","))
                assert float(values.pop("temperature_c")) == payload["temperature_c"], fields
                if "gas_raw" in payload:
                    assert values.pop("gas_raw") == str(payload["gas_raw"]) + "i", fields
                for field in ("gas_alarm", "temperature_alarm"):
                    if field in payload:
                        assert values.pop(field) == str(payload[field]).lower(), fields
                assert not values, fields
                assert before - 1_000_000_000 <= int(stamp) <= after + 1_000_000_000, stamp
                assert "E!" not in result.stderr, result.stderr
                print("PASS:", name, "|", fields, stamp)
            else:
                # Telegraf --test may exit zero despite a plugin parse error.
                assert "E! [inputs.file]" in result.stderr, result.stdout + result.stderr
                assert not re.search(r"^> ", result.stdout, re.M), result.stdout + result.stderr
                print("PASS:", name, "| parser error, no measurement")


if __name__ == "__main__":
    main()
