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
    args.add_argument("--telegraf", required=True, help="Path to Telegraf 1.40.3 executable")
    options = args.parse_args()
    root = Path(__file__).resolve().parents[1]
    production = (root / "infra/telegraf/telegraf.conf").read_text(encoding="utf-8")
    # Reuse the production parser verbatim, changing only the service input to a
    # deterministic file input. Service MQTT input cannot be tested with --test.
    parser = production[production.index("  [[inputs.mqtt_consumer.json_v2]]"):
                        production.index("[[outputs.influxdb_v2]]")]
    parser = parser.replace("inputs.mqtt_consumer", "inputs.file")
    cases = [
        ("valid float, identity tag, reception timestamp",
         {"device_id": "esp32-meja01", "temperature_c": 27.5, "timestamp": 0}, True),
        ("changed Celsius reaches metric",
         {"device_id": "esp32-meja01", "temperature_c": 35}, True),
        ("missing temperature rejected", {"device_id": "esp32-meja01"}, False),
        ("missing device identity rejected", {"temperature_c": 27.5}, False),
        ("nonnumeric temperature rejected",
         {"device_id": "esp32-meja01", "temperature_c": "broken"}, False),
    ]
    with tempfile.TemporaryDirectory(prefix="suhu-parser-") as directory:
        payload_path = Path(directory) / "payload.json"
        config = Path(directory) / "parser-test.conf"
        config.write_text(
            '[agent]\n  omit_hostname = true\n[[inputs.file]]\n  files = ['
            + json.dumps(payload_path.as_posix())
            + ']\n  data_format = "json_v2"\n' + parser
            + '\n[[outputs.file]]\n  files = ["stdout"]\n', encoding="utf-8")
        for name, payload, valid in cases:
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            before = time.time_ns()
            result = subprocess.run(
                [options.telegraf, "--config", str(config), "--test"],
                capture_output=True, text=True, timeout=20, check=False)
            after = time.time_ns()
            matches = re.findall(
                r"^> (suhu,device_id=esp32-meja01 temperature_c=([0-9.]+) ([0-9]+))$",
                result.stdout, re.M)
            if valid:
                assert result.returncode == 0, result.stderr
                assert len(matches) == 1, result.stdout + result.stderr
                metric, value, stamp = matches[0]
                assert float(value) == payload["temperature_c"], metric
                assert before - 1_000_000_000 <= int(stamp) <= after + 1_000_000_000, metric
                assert "E!" not in result.stderr, result.stderr
                print("PASS:", name, "|", metric)
            else:
                # Telegraf --test may exit zero despite a plugin parse error.
                assert "E! [inputs.file]" in result.stderr, result.stdout + result.stderr
                assert not re.search(r"^> ", result.stdout, re.M), result.stdout + result.stderr
                print("PASS:", name, "| parser error, no measurement")


if __name__ == "__main__":
    main()
