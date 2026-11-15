"""Read actual Influx/Grafana results with private credentials kept in-process."""
import base64
import csv
import io
import json
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.telemetry.provision_influx import environment, admin_request


def request(url, data=None, headers=None):
    with urlopen(Request(url, data=data, headers=headers or {}), timeout=10) as response:
        return response.read()


def journal_events():
    text = subprocess.check_output(["journalctl", "-u", "lab-kimia-pqc-session.service", "--no-pager", "-o", "cat"], text=True)
    return [json.loads(line.partition("SESSION_SERVER ")[2]) for line in text.splitlines() if line.startswith("SESSION_SERVER ")]


def query(flux, token=None):
    token = token or environment()["INFLUX_TOKEN"]
    raw = request("http://127.0.0.1:8086/api/v2/query?org=lab-kimia", flux.encode(),
                  {"Authorization": "Token " + token, "Content-Type": "application/vnd.flux", "Accept": "application/csv"})
    return list(csv.DictReader(io.StringIO("\n".join(line for line in raw.decode().splitlines() if not line.startswith("#")))))


def matched_points(events):
    require(bool(events), "No stored telemetry events")
    start = min(e["received_ns"] for e in events)
    stop = max(e["received_ns"] for e in events)+1
    flux = ('from(bucket:"telemetry") |> range(start:time(v:%d),stop:time(v:%d)) '
            '|> filter(fn:(r)=>r._measurement=="suhu" and r.device_id=="esp32-meja01") '
            '|> filter(fn:(r)=>r._field=="temperature_c" or r._field=="gas_raw" or r._field=="gas_alarm" or r._field=="temperature_alarm") '
            '|> pivot(rowKey:["_time"],columnKey:["_field"],valueColumn:"_value") '
            '|> map(fn:(r)=>({r with received_ns:int(v:r._time)}))') % (start, stop)
    rows = {int(row["received_ns"]): row for row in query(flux)}
    result = []
    for event in events:
        row = rows.get(event["received_ns"])
        require(row is not None, "Missing exact receiver timestamp in Influx")
        actual = {"temperature_c": float(row["temperature_c"]), "gas_raw": int(row["gas_raw"]),
                  "gas_alarm": row["gas_alarm"] == "true", "temperature_alarm": row["temperature_alarm"] == "true"}
        require(all(actual[k] == event[k] for k in actual), "Influx sensor fields differ from authenticated payload")
        result.append({"session_id": event["session_id"], "counter": event["counter"], "received_ns": event["received_ns"],
                       "influx_time": row["_time"], **actual})
    return result


def grafana_dashboard():
    env = environment()
    auth = "Basic " + base64.b64encode((env["GRAFANA_USERNAME"]+":"+env["GRAFANA_PASSWORD"]).encode()).decode()
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    dashboard = json.loads(request("http://10.34.211.141:3000/api/dashboards/uid/suhu-meja01", headers=headers))["dashboard"]
    require(dashboard["uid"] == "suhu-meja01" and len(dashboard["panels"]) == 7, "Dashboard contract changed")
    return dashboard, headers


def panel_result(dashboard, headers, panel_id, start_ns, stop_ns, clock_ns=None):
    panel = next(p for p in dashboard["panels"] if p["id"] == panel_id)
    target = dict(panel["targets"][0], intervalMs=2000, maxDataPoints=1000)
    if clock_ns is not None:
        query_text = target["query"]
        prefix = 'import "array"\n' if 'import "array"\n' in query_text else ''
        if prefix:
            query_text = query_text.replace(prefix, "", 1)
        target["query"] = prefix + 'option now = () => time(v: %d)\n' % clock_ns + query_text
    body = {"from": str(start_ns//1_000_000), "to": str(stop_ns//1_000_000+1), "queries": [target]}
    result = json.loads(request("http://10.34.211.141:3000/api/ds/query", json.dumps(body).encode(), headers))["results"]["A"]
    require(not result.get("error"), "Grafana datasource query failed for panel " + str(panel_id))
    return result


def numbers(result):
    return [v for frame in result.get("frames", []) for field, values in zip(frame["schema"]["fields"], frame["data"]["values"])
            if field["type"] == "number" for v in values if v is not None]


def verify_dashboard(points):
    dashboard, headers = grafana_dashboard()
    start = min(p["received_ns"] for p in points)-1_000_000_000
    stop = max(p["received_ns"] for p in points)+1_000_000_000
    # Run the actual provisioned history panels against Grafana's datasource.
    history = {}
    for panel_id in (2, 4, 6):
        response = panel_result(dashboard, headers, panel_id, start, stop)
        require(bool(response.get("frames")), "Missing Grafana history frame")
        history[str(panel_id)] = response
    records = []
    for frame in history["6"]["frames"]:
        names = [field["name"] for field in frame["schema"]["fields"]]
        records.extend(dict(zip(names, row)) for row in zip(*frame["data"]["values"]))
    for point in points:
        require(any(abs(row["_time"]-point["received_ns"]/1_000_000) < 1 and
                    all(row.get(key) == point[key] for key in ("temperature_c", "gas_raw", "gas_alarm", "temperature_alarm"))
                    for row in records), "Grafana history table does not contain exact sensor point")
    statuses = []
    for point in points:
        clock = point["received_ns"]+100_000_000
        expected = int(point["gas_alarm"])+2*int(point["temperature_alarm"])
        state = numbers(panel_result(dashboard, headers, 5, start, stop, clock))
        require(state == [expected], "Grafana alarm state does not match stored sensor flags")
        statuses.append({"counter": point["counter"], "session_id": point["session_id"], "state": expected,
                         "query_clock": "receiver time + 100ms for historical state validation"})
    last = points[-1]
    clock = last["received_ns"]+100_000_000
    require(numbers(panel_result(dashboard, headers, 1, start, stop, clock)) == [last["temperature_c"]], "Temperature stat mismatch")
    require(numbers(panel_result(dashboard, headers, 3, start, stop, clock)) == [last["gas_raw"]], "Gas stat mismatch")
    stamp = numbers(panel_result(dashboard, headers, 7, start, stop, clock))
    require(len(stamp) == 1 and abs(stamp[0]-last["received_ns"]//1_000_000) < 1, "Receiver time stat mismatch")
    current = numbers(panel_result(dashboard, headers, 5, start, time.time_ns()))
    return {"history_panel_results": history, "history_table_points_matched": True, "historical_alarm_states": statuses,
            "latest_stats_matched_at_sample_time": True, "current_alarm_state_at_verification": current}


def token_scope():
    config = json.loads((ROOT / "evidence/local/session-private/influx.json").read_text())
    auth = admin_request("/api/v2/authorizations/"+config["authorization_id"])
    require(len(auth["permissions"]) == 1 and auth["permissions"][0]["action"] == "write" and
            auth["permissions"][0]["resource"]["id"] == config["bucket_id"], "Influx token is not bucket-write-only")
    flux = 'from(bucket:"telemetry") |> range(start:0) |> filter(fn:(r)=>r._measurement=="suhu" and r._field=="temperature_c") |> first()'
    require(bool(query(flux)), "Read permission control has no data")
    denied = False
    behavior = ""
    try:
        # Flux can filter unauthorized buckets to an empty result (HTTP 200),
        # rather than returning an HTTP auth error. Compare the same nonempty
        # admin query; never interpret an arbitrary empty time range as denial.
        denied = not query(flux, config["token"])
        behavior = "empty permission-filtered result"
    except HTTPError as error:
        # InfluxDB 2.9.1 hides a bucket without read access with HTTP 404.
        # The identical admin query above proves this endpoint/bucket exists.
        denied = error.code in (401, 403, 404)
        behavior = "HTTP " + str(error.code)
    require(denied, "Receiver write token unexpectedly permitted reads")
    return {"bucket_write_only": True, "read_data_visible": False,
            "read_control_nonempty_admin": True, "read_behavior": behavior}


def main():
    control = json.loads((ROOT / "docs/evidence/pqc-ticket-04/native-mqtt.json").read_text())
    events = [e for e in journal_events() if e.get("event") == "telemetry_stored" and e.get("session_id") == control["session_id"]]
    require(len(events) == 4, "Tamper/replay/schema caused unexpected stored points")
    points = matched_points(events)
    require({int(p["gas_alarm"])+2*int(p["temperature_alarm"]) for p in points} == {0, 1, 2, 3}, "Missing native alarm state")
    legacy = query('from(bucket:"telemetry") |> range(start:0,stop:time(v:%d)) |> filter(fn:(r)=>r._measurement=="suhu" and r._field=="temperature_c" and r.device_id=="esp32-meja01") |> first()' % points[0]["received_ns"])
    require(bool(legacy), "Legacy history missing")
    result = {"passed": True, "source": "native-control", "influx_points": points,
              "token": token_scope(), "legacy_history_still_present": True, "oldest_temperature_time": legacy[0]["_time"],
              "grafana": verify_dashboard(points)}
    (ROOT / "docs/evidence/pqc-ticket-04/native-storage-grafana.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"passed": True, "source": "native-control", "influx_points": len(points),
                      "grafana_four_states": True, "token_write_only": True, "legacy_history_present": True}))


if __name__ == "__main__":
    main()
