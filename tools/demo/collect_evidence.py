"""Read-only demo closeout: revalidate existing MCU evidence and the new native run.

Does not start Wokwi, mutate frames, restart services, or overwrite prior tickets.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
from tools.deploy.migrate import verify_state
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.telemetry.verify_capture import verify
from tools.telemetry.verify_lxc import matched_points, request
from tools.telemetry.provision_influx import environment

FOLDER = ROOT / "docs/evidence/pqc-ticket-07"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def links(paths):
    checked = 0
    for path in paths:
        for target in re.findall(r"\[[^\]\n]+\]\(([^\s)]+)\)", path.read_text()):
            parsed = urlsplit(target.strip("<>"))
            if parsed.scheme or parsed.netloc:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            require(resolved == FOLDER / "summary.json" or resolved.exists(), "Broken local link: "+str(path)+" -> "+target)
            if parsed.fragment and resolved.suffix == ".md":
                headings = re.findall(r"(?m)^#{1,6}\s+(.+)$", resolved.read_text())
                anchors = [re.sub(r"[^\w\- ]", "", h.strip().lower()).replace(" ", "-") for h in headings]
                require(unquote(parsed.fragment) in anchors, "Broken heading link: "+target)
            checked += 1
    return checked


def main():
    state = verify_state()
    six = json.loads((ROOT / "docs/evidence/pqc-ticket-06/summary.json").read_text())
    require(six["verified"], "Migration evidence incomplete")
    for name, digest in six["source_sha256"].items():
        require(sha(ROOT / name) == digest, "Runtime/source changed since MCU validation: "+name)
    for name, digest in six["private_artifact_sha256"].items():
        require(sha(ROOT / "firmware/.pio/build/pqc-telemetry" / name) == digest, "MCU image changed since ticket 06")
    five = json.loads((ROOT / "docs/evidence/pqc-ticket-05/summary.json").read_text())
    for name in ("firmware/lib/pqc-proof/src/pqc_session.cpp", "firmware/lib/pqc-proof/src/pqc_session.h",
                 "tools/session/native.cpp", "tools/session/native.py"):
        require(sha(ROOT / name) == five["source_sha256"][name], "Session implementation changed since fault validation")
    reused = []
    for ticket, fault in (("05", True), ("06", False)):
        path = ROOT / f"docs/evidence/pqc-ticket-{ticket}/esp32-serial.txt"
        capture = verify(path, fault_test=fault)
        reused.append({"ticket": ticket, "source": "existing Wokwi run revalidated; not a new simulator run",
                       "run": capture["run"], "capture_mode": capture["capture_mode"], "capture_sha256": sha(path),
                       "sent": capture["sent_samples"], "acked": len(capture["acked_sensor_samples"]),
                       "unconfirmed": len(capture["unconfirmed_sent_frames"]), "four_states": True,
                       "all_acked_points_rechecked_in_influx_grafana": True,
                       "current_grafana_state": capture["grafana"]["current_alarm_state_at_verification"]})
    security = json.loads((FOLDER / "security.json").read_text())
    require(security["passed"] and len(security["cases"]) == 21 and len(matched_points(security["points"])) == 8,
            "Fresh native security controls incomplete")
    # Check the no-overwrite guard against a historical result, before any lab fault.
    protected = ROOT / "docs/evidence/pqc-ticket-05/security.json"
    before, pid = sha(protected), subprocess.check_output(["systemctl", "show", "lab-kimia-pqc-session", "--property=MainPID", "--value"], text=True)
    duplicate = subprocess.run([sys.executable, "-m", "tools.telemetry.check_security", "--output-dir", str(protected.parent)],
                               capture_output=True, text=True, timeout=10)
    require(duplicate.returncode != 0 and "Evidence already exists" in duplicate.stderr and sha(protected) == before,
            "Historical evidence overwrite was not rejected")
    require(subprocess.check_output(["systemctl", "show", "lab-kimia-pqc-session", "--property=MainPID", "--value"], text=True) == pid,
            "Duplicate-result check restarted receiver")
    logs = ROOT / "evidence/local"
    protocol = next(line for line in (logs / "ticket07-protocol.log").read_text().splitlines() if line.startswith("SESSION_NATIVE_RESULT "))
    protocol = json.loads(protocol.partition(" ")[2])
    require(protocol["passed"] and protocol["checks"] == 113, "Protocol regression failed")
    unit = (logs / "ticket07-unit.log").read_text()
    require("Ran 12 tests" in unit and unit.rstrip().endswith("OK"), "Unit regressions failed")
    sensors = (logs / "ticket07-sensors.log").read_text()
    require("PASS: PQC selection" in sensors and "PASS: PQC startup failure" in sensors, "Sensor regressions missing")
    health = {"influx": json.loads(request("http://127.0.0.1:8086/health"))["status"],
              "grafana": json.loads(request("http://10.34.211.141:3000/api/health"))["database"]}
    require(health == {"influx": "pass", "grafana": "ok"}, "Service health failed after controls")
    docs = [ROOT / name for name in ("README.md", "docs/demo-proyek.md", "docs/operasi-pqc.md", "docs/verifikasi-pqc-tiket-07.md")]
    count = links(docs)
    files = docs + [ROOT / name for name in ("tools/demo/collect_evidence.py", "tools/telemetry/check_security.py",
                                            "tools/telemetry/wokwi_fault.py", "tools/telemetry/verify_capture.py")]
    secret_values = {value for key, value in environment().items() if ("PASSWORD" in key or "TOKEN" in key) and len(value) >= 16}
    for name in ("mqtt-private/device.json", "mqtt-private/receiver.json", "session-private/influx.json"):
        private = json.loads((ROOT / "evidence/local" / name).read_text())
        secret_values.update(private[k] for k in ("password", "token") if k in private)
    public = [p for p in (ROOT / "docs").rglob("*") if p.is_file() and p.suffix in (".md", ".json", ".jsonl", ".txt")]
    for path in set(public+files):
        raw = path.read_bytes()
        require(not any(secret.encode() in raw for secret in secret_values), "Active secret found in public text: "+str(path))
    result = {"ticket": "07", "status": "done", "verified": True, "collected_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Complete demo guide, fresh native security checks, existing Wokwi/fault evidence revalidated",
              "state": state, "health": health, "runtime_matches_ticket06": True, "new_wokwi_run": False,
              "reused_wokwi": reused, "fresh_native_security": {"cases": 21, "stored_points": 8, "source": security["source"]},
              "protocol": protocol, "unit_tests": 12, "sensor_regressions": sensors.splitlines(),
              "historical_evidence_overwrite_rejected_before_faults": True, "local_links_checked": count,
              "public_texts_scanned_for_known_active_secrets": len(set(public+files)),
              "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in files},
              "limitations": ["Wokwi runs and interactive sensor/outage observations reused from tickets 05/06; not reenacted in ticket 07",
                              "Fresh mutations/restarts use native clients on the private lab broker, not physical sensors",
                              "No LXC reboot, acoustic recording, physical RNG/performance or safety certification",
                              "Prospective FN-DSA/custom lab protocol; no independent audit or final FIPS 206 claim",
                              "MQTT broker credentials and metadata remain visible without TLS"]}
    (FOLDER / "summary.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"verified": True, "fresh_native_cases": 21, "reused_wokwi_runs": len(reused), "links_checked": count}))


if __name__ == "__main__":
    main()
