"""One bounded lab fault while Wokwi keeps running. No private values are logged."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.telemetry.verify_lxc import journal_events


def run(kind, sid, seconds, output_dir=None):
    require(0 < seconds <= 30, "Fault must be bounded to at most 30 seconds")
    folder = output_dir or ROOT / "docs/evidence/pqc-ticket-05"
    folder.mkdir(parents=True, exist_ok=True)
    command = {"receiver": ["systemctl", "lab-kimia-pqc-session.service"],
               "broker": ["docker", "lab-kimia-mqtt-pqc-broker-1"],
               "influx": ["docker", "lab-kimia-suhu-influxdb-1"]}[kind]
    recent = [e for e in journal_events() if e["event"] == "telemetry_stored" and e.get("session_id") == sid]
    require(recent and time.time_ns()-recent[-1]["received_ns"] < 15_000_000_000, "Need a recent baseline on specified Wokwi session")
    result = {"kind": kind, "baseline_session": sid, "baseline_counter": recent[-1]["counter"],
              "started_ns": time.time_ns(), "utc": datetime.now(timezone.utc).isoformat()}
    subprocess.run([command[0], "stop", command[1]], check=True, stdout=subprocess.DEVNULL)
    try:
        print(json.dumps({"phase": "stopped", **result}), flush=True)
        time.sleep(seconds)
    finally:
        subprocess.run([command[0], "start", command[1]], check=True, stdout=subprocess.DEVNULL)
        result["restored_ns"] = time.time_ns()
    print(json.dumps({"phase": "restored", "kind": kind}), flush=True)
    deadline = time.monotonic()+110
    while time.monotonic() < deadline:
        events = journal_events()
        recovered = [e for e in events if e["event"] == "telemetry_stored" and e["received_ns"] > result["restored_ns"]
                     and (kind == "influx" or e["session_id"] != sid)]
        if recovered:
            point = recovered[0]
            result.update(recovered_session=point["session_id"], recovered_counter=point["counter"],
                          recovered_ns=point["received_ns"], passed=True)
            if kind == "influx":
                failures = [e for e in events if e["event"] == "write_failed" and e.get("session_id") == sid
                            and e["utc"] >= result["utc"]]
                require(bool(failures), "No attempted write during Influx outage")
                result["unconfirmed_writes"] = len(failures)
            with (folder / "wokwi-faults.jsonl").open("a") as output:
                output.write(json.dumps(result)+"\n")
            print(json.dumps(result), flush=True)
            return
        time.sleep(.5)
    raise RuntimeError("Wokwi failed to recover within 110 real seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("receiver", "broker", "influx"))
    parser.add_argument("session_id")
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, help="Directory for this run's appended fault records")
    args = parser.parse_args()
    run(args.kind, args.session_id, args.seconds, args.output_dir)
