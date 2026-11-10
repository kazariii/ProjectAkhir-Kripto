"""Repeat ticket 05 against the owner's configured EMQX and running local stack.

Run from the repository root: python tests/check_mqtt_access.py
Reads ignored .env / secrets.h; prints only allowlisted evidence, never secrets.
Publishes two synthetic controls under unique device_id tags, not esp32-meja01.
Requires live ESP32 telemetry before/after; does not modify broker policy or data.
"""
import base64
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import ssl
import sys
import time
import urllib.request
import uuid

from mqtt_probe import Probe


ROOT = Path(__file__).resolve().parents[1]
TOPIC = "lab/kimia/meja01/telemetry"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def configuration():
    # These files use the simple literal format documented by the project.
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    source = (ROOT / "firmware/include/secrets.h").read_text(encoding="utf-8-sig")
    firmware = {}
    for name in ("MQTT_HOST", "MQTT_USERNAME", "MQTT_PASSWORD"):
        match = re.search(r'constexpr char ' + name + r'\[\]\s*=\s*"([^"\\]*)";', source)
        require(match is not None, "Expected literal firmware configuration: " + name)
        firmware[name] = match[1]
    require(env["MQTT_HOST"] == firmware["MQTT_HOST"], "MQTT host configurations differ")
    require(env["MQTT_TELEGRAF_USERNAME"] != firmware["MQTT_USERNAME"], "MQTT accounts must differ")
    for value in (firmware["MQTT_PASSWORD"], env["MQTT_TELEGRAF_PASSWORD"], env["INFLUX_TOKEN"], env["GRAFANA_PASSWORD"]):
        require(bool(value) and not value.startswith("ISI_"), "Local credentials are incomplete")
    return env, firmware


def post(url, headers, body):
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode()


def points(env, device_id, start):
    flux = ('from(bucket:"telemetry") |> range(start: time(v: ' + json.dumps(start) + ')) '
            '|> filter(fn:(r)=>r._measurement=="suhu" and r.device_id==' + json.dumps(device_id) + ') '
            '|> pivot(rowKey:["_time"],columnKey:["_field"],valueColumn:"_value") |> sort(columns:["_time"])')
    result = post("http://127.0.0.1:8086/api/v2/query?org=lab-kimia",
                  {"Authorization": "Token " + env["INFLUX_TOKEN"],
                   "Content-Type": "application/vnd.flux", "Accept": "application/csv"}, flux.encode())
    return list(csv.DictReader(io.StringIO("\n".join(line for line in result.splitlines() if not line.startswith("#")))))


def wait_for(check, description):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(1)
    raise AssertionError("Timed out: " + description)


def grafana_points(env, device_id, start):
    # Use the production datasource through Grafana, with an isolated test tag.
    flux = ('from(bucket:"telemetry") |> range(start: time(v: ' + json.dumps(start) + ')) '
            '|> filter(fn:(r)=>r._measurement=="suhu" and r.device_id==' + json.dumps(device_id)
            + ' and r._field=="temperature_c") |> sort(columns:["_time"])')
    auth = base64.b64encode((env["GRAFANA_USERNAME"] + ":" + env["GRAFANA_PASSWORD"]).encode()).decode()
    body = {"from": str(int((time.time() - 3600) * 1000)), "to": str(int(time.time() * 1000)),
            "queries": [{"refId": "A", "datasource": {"type": "influxdb", "uid": "influx-suhu"},
                         "query": flux, "intervalMs": 2000, "maxDataPoints": 1000}]}
    result = json.loads(post("http://127.0.0.1:3000/api/ds/query",
                            {"Authorization": "Basic " + auth, "Content-Type": "application/json"},
                            json.dumps(body).encode()))["results"]["A"]
    require(not result.get("error"), "Grafana datasource query failed")
    return [v for frame in result.get("frames", [])
            for field, values in zip(frame["schema"]["fields"], frame["data"]["values"])
            if field["type"] == "number" for v in values if v is not None]


def main():
    run_id = "ticket05-" + uuid.uuid4().hex[:12]
    output = ROOT / "evidence/local/ticket-05" / (run_id + ".json")
    report = {"run_id": run_id, "started_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "EMQX project accounts; Python MQTT5 probes and live ESP32; production Telegraf/InfluxDB/Grafana",
              "checks": [], "status": "running"}
    step = "configuration"

    def record(name, **details):
        report["checks"].append(dict(check=name, **details))
        print("PASS: " + name, flush=True)

    try:
        env, firmware = configuration()
        trusted = ssl.create_default_context(cafile=str(ROOT / "infra/certs/emqx-ca.pem"))
        host = env["MQTT_HOST"]
        accounts = {"sender": (firmware["MQTT_USERNAME"], firmware["MQTT_PASSWORD"]),
                    "receiver": (env["MQTT_TELEGRAF_USERNAME"], env["MQTT_TELEGRAF_PASSWORD"])}
        # All client IDs are fresh; never take over the simulator or Telegraf.
        def connect(role, context=trusted, credentials=None):
            probe = Probe(host, 8883, context)
            try:
                code = probe.connect("t05-" + uuid.uuid4().hex[:18], *(credentials if credentials is not None else accounts[role]))
                require(code == 0, "Valid account did not receive CONNACK 0")
                return probe
            except BaseException:
                probe.__exit__()
                raise

        start = report["started_utc"]
        identifiers = {name: run_id + "-" + name for name in
                       ("before", "after", "wrong-user", "wrong-password", "anonymous", "denied-publish", "outside", "untrusted-ca")}
        report["device_ids"] = identifiers
        outside = "lab/kimia/ticket05/" + run_id
        report["outside_topic"] = outside

        def payload(name, temperature=25.5):
            return json.dumps({"device_id": identifiers[name], "temperature_c": temperature,
                               "gas_raw": 1000, "gas_alarm": False, "temperature_alarm": False}).encode()

        def live_control(stage):
            # A point received AFTER this call proves current flow, not old data.
            since = datetime.now(timezone.utc).isoformat()
            rows = wait_for(lambda: points(env, "esp32-meja01", since), "new ESP32 sample")
            wait_for(lambda: grafana_points(env, "esp32-meja01", since), "ESP32 in Grafana")
            record("live ESP32 -> Telegraf -> InfluxDB -> Grafana " + stage,
                   received_at=rows[-1]["_time"], device_id="esp32-meja01")

        def positive(stage):
            with connect("receiver") as receiver:
                code = receiver.subscribe(TOPIC)
                require(code == 0, "Allowed subscription did not receive SUBACK 0")
                with connect("sender") as sender:
                    code = sender.publish(TOPIC, payload(stage))
                    require(code == 0, "Allowed publication did not receive PUBACK 0")
                    deadline = time.monotonic() + 10
                    while True:
                        topic, body = receiver.message()
                        if topic == TOPIC and body == payload(stage):
                            break
                        require(time.monotonic() < deadline, "Positive subscriber marker missing")
            rows = wait_for(lambda: points(env, identifiers[stage], start), "control stored by Telegraf")
            require(len(rows) == 1 and float(rows[0]["temperature_c"]) == 25.5, "Unexpected control measurement")
            require(grafana_points(env, identifiers[stage], start) == [25.5], "Control missing in Grafana")
            record("tagged positive control " + stage, connack=0, suback=0, puback=0,
                   independent_subscriber=True, influx_rows=1, grafana_temperature_c=25.5,
                   received_at=rows[0]["_time"])

        step = "positive controls before negatives"
        live_control("before")
        positive("before")

        step = "authentication"
        for name, credentials in (("wrong-user", (run_id, accounts["sender"][1])),
                                  ("wrong-password", (accounts["sender"][0], uuid.uuid4().hex)),
                                  ("anonymous", ())):
            with Probe(host, 8883, trusted) as probe:
                code = probe.connect("t05-" + uuid.uuid4().hex[:18], *credentials)
                require(code in (134, 135), "Expected explicit authentication rejection")
                # Sending PUBLISH after a rejected CONNECT would violate MQTT.
                record("authentication " + name, connack=code, publish_sent=False)

        step = "authorization"
        for role in ("sender", "receiver"):
            # Each denial authenticates successfully first. Fresh sessions avoid
            # confusing normal subscribed telemetry with an acknowledgement.
            for topic in ([TOPIC, outside, "lab/kimia/#"] if role == "sender" else [outside, "lab/kimia/#"]):
                with connect(role) as probe:
                    code = probe.subscribe(topic)
                    require(code == 135, "Expected SUBACK 135 (Not authorized)")
                    record("authorization " + role + " subscribe " + topic, suback=code)
            for topic in ([outside] if role == "sender" else [TOPIC, outside]):
                with connect(role) as probe:
                    name = "denied-publish" if topic == TOPIC else "outside"
                    code = probe.publish(topic, payload(name))
                    require(code == 135, "Expected PUBACK 135 (Not authorized)")
                    record("authorization " + role + " publish " + topic, puback=code)

        step = "server certificate verification"
        # Empty trust store, CERT_REQUIRED and check_hostname remain enabled.
        # No MQTT credentials or PUBLISH are sent before a verified TLS handshake.
        untrusted = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        require(untrusted.verify_mode == ssl.CERT_REQUIRED and untrusted.check_hostname,
                "TLS verification must remain enabled")
        try:
            with Probe(host, 8883, untrusted):
                raise AssertionError("Untrusted server unexpectedly completed TLS")
        except ssl.SSLCertVerificationError as error:
            record("untrusted server CA rejected", exception="SSLCertVerificationError",
                   verify_code=error.verify_code, mqtt_connect_sent=False, publish_sent=False)

        step = "positive controls after negatives"
        positive("after")
        live_control("after")

        step = "negative markers absent"
        # Longer than Telegraf's 2s flush; explicit rejection remains primary proof.
        time.sleep(5)
        for name in ("wrong-user", "wrong-password", "anonymous", "denied-publish", "outside", "untrusted-ca"):
            require(not points(env, identifiers[name], start), "Negative marker reached storage")
        record("no negative markers in InfluxDB", observation_seconds=5,
               device_ids=[identifiers[n] for n in identifiers if n not in ("before", "after")])
        report["status"] = "passed"
    except Exception as error:
        # Never serialize exception text/tracebacks: they can include credentials,
        # HTTP headers or service responses. Keep the failed stage and error type.
        report.update(status="failed", failed_step=step, error_type=type(error).__name__)
        print("FAIL: " + step + " (" + type(error).__name__ + "); check local configuration/service health", file=sys.stderr)
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Evidence: " + str(output))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
