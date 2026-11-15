"""Check MQTT/TLS -> production Telegraf/InfluxDB/Grafana and restart persistence.

Uses disposable Compose resources, local test credentials/CA, and a Mosquitto
fixture instead of EMQX. Does not simulate Wokwi or use the owner's .env/volumes.
Requires Docker Compose and OpenSSL (including the Git for Windows copy).
"""
import base64
import csv
from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


BROKER = "eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279"
TOPIC = "lab/kimia/meja01/telemetry"
ROOT = Path(__file__).resolve().parents[1]


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def wait_for(check, description):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise AssertionError("Timed out: " + description)


def request(url, headers=None, data=None):
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers or {}), timeout=10) as response:
        return response.read().decode()


def mqtt_publish(port, context, password, temperature, gas, gas_alarm, temperature_alarm):
    def mqtt_string(value):
        raw = value.encode()
        return struct.pack("!H", len(raw)) + raw

    def packet(kind, body):
        length = len(body)
        encoded = bytearray([kind])
        while True:
            encoded.append((length % 128) | (128 if length >= 128 else 0))
            length //= 128
            if not length:
                return bytes(encoded) + body

    def receive(connection, count):
        data = b""
        while len(data) < count:
            chunk = connection.recv(count - len(data))
            if not chunk:
                raise AssertionError("MQTT connection closed")
            data += chunk
        return data

    with socket.create_connection(("127.0.0.1", port), timeout=10) as tcp:
        with context.wrap_socket(tcp, server_hostname="mosquitto") as connection:
            # MQTT 3.1.1, clean session, username + password, keepalive 60s.
            connection.sendall(packet(0x10, b"\x00\x04MQTT\x04\xc2\x00\x3c"
                                     + mqtt_string("fixture-publisher")
                                     + mqtt_string("esp32-meja01") + mqtt_string(password)))
            assert receive(connection, 4) == b"\x20\x02\x00\x00", "MQTT authentication failed"
            sample = {"device_id": "esp32-meja01", "temperature_c": temperature, "gas_raw": gas}
            if gas_alarm is not None:
                sample.update(gas_alarm=gas_alarm, temperature_alarm=temperature_alarm)
            payload = json.dumps(sample).encode()
            connection.sendall(packet(0x30, mqtt_string(TOPIC) + payload))
            connection.sendall(b"\xc0\x00")
            assert receive(connection, 2) == b"\xd0\x00"
            connection.sendall(b"\xe0\x00")


def main():
    openssl = shutil.which("openssl") or "C:/Program Files/Git/usr/bin/openssl.exe"
    if not Path(openssl).is_file():
        raise RuntimeError("OpenSSL required")
    project = "monitoring-test-" + uuid.uuid4().hex[:12]
    token, password = secrets.token_hex(32), secrets.token_hex(16)
    mqtt_password = secrets.token_hex(16)
    env = dict(os.environ, INFLUX_USERNAME="test-admin", INFLUX_PASSWORD=password,
               INFLUX_TOKEN=token, GRAFANA_USERNAME="test-admin", GRAFANA_PASSWORD=password,
               MQTT_HOST="mosquitto", MQTT_TELEGRAF_USERNAME="telegraf-meja01",
               MQTT_TELEGRAF_PASSWORD=mqtt_password)
    with tempfile.TemporaryDirectory(prefix=project) as directory:
        fixture = Path(directory)
        # Never read the owner's .env. Render the actual production Compose file.
        base = ["docker", "compose", "--env-file", str(fixture / "empty.env"),
                "-p", project, "-f", str(ROOT / "compose.yaml"), "-f", str(ROOT / "compose.legacy.yaml")]
        (fixture / "empty.env").touch()
        config = json.loads(run(base + ["config", "--format", "json"], env=env))
        for service in ("influxdb", "grafana"):
            config["services"][service]["ports"][0]["published"] = "0"
        # The broker fixture uses two accounts with the production topic policy.
        (fixture / "acl").write_text(f"user esp32-meja01\ntopic write {TOPIC}\nuser telegraf-meja01\ntopic read {TOPIC}\n")
        mount = f"type=bind,source={directory},target=/test"
        for username, secret, create in (("esp32-meja01", password, True), ("telegraf-meja01", mqtt_password, False)):
            run(["docker", "run", "--rm", "--mount", mount, BROKER, "mosquitto_passwd", "-b"]
                + (["-c"] if create else []) + ["/test/passwords", username, secret])
        run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-subj", "/CN=Ticket03 Test CA", "-keyout", str(fixture / "ca.key"), "-out", str(fixture / "ca.pem")])
        run([openssl, "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=mosquitto",
             "-keyout", str(fixture / "server.key"), "-out", str(fixture / "server.csr")])
        (fixture / "extensions").write_text("subjectAltName=DNS:mosquitto\nextendedKeyUsage=serverAuth\n")
        run([openssl, "x509", "-req", "-days", "1", "-in", str(fixture / "server.csr"),
             "-CA", str(fixture / "ca.pem"), "-CAkey", str(fixture / "ca.key"), "-CAcreateserial",
             "-extfile", str(fixture / "extensions"), "-out", str(fixture / "server.pem")])
        (fixture / "mosquitto.conf").write_text(
            # Test-only: mounted temporary keys/password file are owned by root.
            "user root\nlistener 8883\nallow_anonymous false\npassword_file /test/passwords\nacl_file /test/acl\n"
            "certfile /test/server.pem\nkeyfile /test/server.key\nlog_dest stdout\nlog_type all\n")
        config["services"]["mosquitto"] = {
            "image": BROKER, "command": ["mosquitto", "-c", "/test/mosquitto.conf"],
            "ports": [{"target": 8883, "published": "0", "host_ip": "127.0.0.1"}],
            "volumes": [{"type": "bind", "source": directory, "target": "/test", "read_only": True}],
        }
        for volume in config["services"]["telegraf"]["volumes"]:
            if volume["target"] == "/etc/telegraf/emqx-ca.pem":
                volume["source"] = str(fixture / "ca.pem")
        (fixture / "compose.json").write_text(json.dumps(config), encoding="utf-8")
        compose = ["docker", "compose", "-p", project, "-f", str(fixture / "compose.json")]

        def port(service, target):
            return int(run(compose + ["port", service, str(target)]).strip().rsplit(":", 1)[1])

        influx = grafana = ""
        broker_port = 0

        def ready(subscription_count=1):
            nonlocal influx, grafana, broker_port
            # Docker may assign new ephemeral host ports on container restart.
            influx = f"http://127.0.0.1:{port('influxdb', 8086)}"
            grafana = f"http://127.0.0.1:{port('grafana', 3000)}"
            broker_port = port("mosquitto", 8883)
            wait_for(lambda: json.loads(request(influx + "/health"))["status"] == "pass", "InfluxDB health")
            wait_for(lambda: json.loads(request(grafana + "/api/health"))["database"] == "ok", "Grafana health")
            wait_for(lambda: run(compose + ["logs", "mosquitto"]).count("Received SUBSCRIBE from telegraf-meja01") >= subscription_count, "MQTT/TLS subscription")

        def points():
            flux = ('from(bucket: "telemetry") |> range(start: -1h) '
                    '|> filter(fn: (r) => r._measurement == "suhu" and r.device_id == "esp32-meja01") '
                    '|> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value") |> sort(columns: ["_time"])')
            result = request(influx + "/api/v2/query?org=lab-kimia",
                             {"Authorization": "Token " + token, "Content-Type": "application/vnd.flux", "Accept": "application/csv"}, flux.encode())
            rows = csv.DictReader(io.StringIO("\n".join(line for line in result.splitlines() if not line.startswith("#"))))
            return [(r["_time"], float(r["temperature_c"]), int(r["gas_raw"]),
                     r["gas_alarm"] == "true", r["temperature_alarm"] == "true") for r in rows]

        def panel_result(panel_id, at=None, historical=False):
            auth = {"Authorization": "Basic " + base64.b64encode(("test-admin:" + password).encode()).decode()}
            d = json.loads(request(grafana + "/api/dashboards/uid/suhu-meja01", auth))["dashboard"]
            assert len(d["panels"]) == 7
            panel = next(p for p in d["panels"] if p["id"] == panel_id)
            query = dict(panel["targets"][0], intervalMs=2000, maxDataPoints=1000)
            if at:
                query["query"] = 'import "array"\noption now = () => time(v: "' + at + '")\n' + query["query"].replace('import "array"\n', '')
            end = time.time() - (86400 if historical else 0)
            body = {"from": str(int((end - 3600) * 1000)), "to": str(int(end * 1000)), "queries": [query]}
            result = json.loads(request(grafana + "/api/ds/query", dict(auth, **{"Content-Type": "application/json"}), json.dumps(body).encode()))["results"]["A"]
            assert not result.get("error"), result
            return panel, result

        def numeric_values(result):
            return [v for frame in result.get("frames", [])
                    for field, column in zip(frame["schema"]["fields"], frame["data"]["values"])
                    if field["type"] == "number" for v in column if v is not None]

        def freshness(expected_state, at=None, historical=False):
            panel, result = panel_result(5, at, historical)
            assert numeric_values(result) == [expected_state], result
            mapping = panel["fieldConfig"]["defaults"]["mappings"][0]["options"]
            assert "Data terlambat" in mapping["-1"]["text"]
            assert mapping["-2"]["text"] == "Belum ada data"
            _, result = panel_result(7, at, historical)
            stamp = numeric_values(result)
            if expected_state == -2:
                assert stamp == [0], stamp
            else:
                last = datetime.fromisoformat(points()[-1][0].replace("Z", "+00:00"))
                assert abs(stamp[0] - last.timestamp() * 1000) < 1, stamp

        def dashboard(expected_temperature, expected_gas, gas_alarm, temperature_alarm, expected_history):
            d = json.loads((ROOT / "infra/grafana/dashboards/suhu.json").read_text(encoding="utf-8"))
            # Fix query clock only for deterministic regression of the four
            # fresh labels. Outage checks below use the actual server clock.
            last = datetime.fromisoformat(points()[-1][0].replace("Z", "+00:00"))
            at = (last + timedelta(seconds=1)).isoformat()
            for panel in d["panels"]:
                _, result = panel_result(panel["id"], at if panel["id"] in (1, 3, 5, 7) else None)
                values = numeric_values(result)
                if panel["id"] == 6:
                    records = []
                    for frame in result.get("frames", []):
                        names = [f["name"] for f in frame["schema"]["fields"]]
                        records += [dict(zip(names, row)) for row in zip(*frame["data"]["values"])]
                    assert len(records) == len(expected_history), records
                    records.sort(key=lambda row: row["_time"])
                    for row, (t, g, ga, ta) in zip(records, expected_history):
                        assert (row["temperature_c"], row["gas_raw"], row["gas_alarm"], row["temperature_alarm"]) == (t, g, ga, ta), row
                        assert type(row["gas_alarm"]) is bool and type(row["temperature_alarm"]) is bool, row
                        label = ("Peringatan gas dan suhu" if ga and ta else "Peringatan gas" if ga else "Peringatan suhu" if ta else "Normal")
                        assert row["kondisi"] == label, row
                else:
                    assert values, panel["title"]
                if panel["type"] == "stat":
                    if panel["id"] != 7:
                        expected_value = {1: expected_temperature, 3: expected_gas, 5: int(gas_alarm) + 2 * int(temperature_alarm)}[panel["id"]]
                        assert values == [expected_value], values
                    if panel["id"] == 5:
                        mappings = panel["fieldConfig"]["defaults"]["mappings"][0]["options"]
                        assert [mappings[str(i)]["text"] for i in range(4)] == ["Normal", "Peringatan gas", "Peringatan suhu", "Peringatan gas dan suhu"]

        try:
            run(compose + ["config", "--quiet"])
            run(compose + ["up", "-d"])
            ready()
            freshness(-2)
            print("PASS: empty bucket explicitly reports Belum ada data and no last receipt")
            context = ssl.create_default_context(cafile=str(fixture / "ca.pem"))
            expected = [(25, 1200, False, False), (25, 3000, True, False),
                        (40, 1200, False, True), (40, 3000, True, True),
                        (39.99, 1200, False, False)]
            for count, (temperature, gas, gas_alarm, temperature_alarm) in enumerate(expected, 1):
                mqtt_publish(broker_port, context, password, temperature, gas, gas_alarm, temperature_alarm)
                wait_for(lambda: len(points()) == count, "stored sensor/alarm sample")
                assert [row[1:] for row in points()] == expected[:count]
                dashboard(temperature, gas, gas_alarm, temperature_alarm, expected[:count])
            before = points()
            print("PASS: four independent alarm states and recovery via MQTT/TLS; booleans share sensor timestamps; seven Grafana queries and history labels")
            # Exact 10s is fresh; only >10s is stale. The picker is deliberately
            # yesterday, and now is also tested >1h after the last receipt.
            last = datetime.fromisoformat(before[-1][0].replace("Z", "+00:00"))
            freshness(0, (last + timedelta(seconds=10)).isoformat(), historical=True)
            freshness(-1, (last + timedelta(seconds=10, microseconds=1)).isoformat(), historical=True)
            freshness(-1, (last + timedelta(hours=2)).isoformat(), historical=True)
            run(compose + ["stop", "mosquitto"])
            wait_for(lambda: time.time() - last.timestamp() > 11, "10s receipt timeout")
            freshness(-1)
            assert points() == before
            run(compose + ["start", "mosquitto"])
            ready(2)
            print("PASS: broker outage marks old Normal stale; exact >10s boundary, old picker, >1h history and frozen last receipt")
            run(compose + ["restart"])
            ready(3)
            assert points() == before, "History changed after restart"
            mqtt_publish(broker_port, context, password, 25, 4000, True, False)
            wait_for(lambda: len(points()) == 6, "new point after restart")
            assert points()[:5] == before
            dashboard(25, 4000, True, False, expected + [(25, 4000, True, False)])
            history = points()
            for panel_id in (2, 4):
                panel, result = panel_result(panel_id)
                custom = panel["fieldConfig"]["defaults"]["custom"]
                assert custom["spanNulls"] is False and custom["insertNulls"] == 10000
                columns = [column for frame in result["frames"]
                           for field, column in zip(frame["schema"]["fields"], frame["data"]["values"])
                           if field["type"] == "number"]
                assert any(None in col for col in columns), "Outage must leave null graph buckets"
            freshness(1, (datetime.fromisoformat(history[-1][0].replace("Z", "+00:00")) + timedelta(seconds=1)).isoformat())
            # An updated old firmware must not expose a previous Normal/alarm
            # as the current condition when its latest message lacks booleans.
            mqtt_publish(broker_port, context, password, 25, 1200, None, None)
            wait_for(lambda: len(points()) == 7, "legacy reading after recovery")
            assert points()[:6] == history
            latest = datetime.fromisoformat(points()[-1][0].replace("Z", "+00:00"))
            freshness(4, (latest + timedelta(seconds=1)).isoformat())
            print("PASS: sensor/alarm history and dashboard survive restart; fresh telemetry continues")
            print("PASS: gap remains null, recovered data stays fresh, legacy missing alarm never falls back to an older state")
        except Exception:
            print(run(compose + ["logs", "--tail", "30", "mosquitto", "telegraf"]))
            raise
        finally:
            # Remove only this test's randomly named project and its own volumes.
            assert all(v["name"].startswith(project + "_") for v in config["volumes"].values())
            run(compose + ["down", "--volumes", "--remove-orphans"])


if __name__ == "__main__":
    main()
