"""Cut over the existing private LXC without rotating secrets or moving data volumes.

Run from /opt/lab-kimia-mqtt after copying the reviewed source. Backups stay
private. Failure never starts the archived TLS ingress automatically.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.mqtt.client import require
from tools.session.native import ROOT
from tools.telemetry.verify_lxc import matched_points, grafana_dashboard

MONITOR = Path("/opt/lab-kimia-suhu")
PRIVATE = ROOT / "evidence/local/migration06"
PUBLIC = ROOT / "docs/evidence/pqc-ticket-06"
DATA_CONTAINERS = ("lab-kimia-suhu-influxdb-1", "lab-kimia-suhu-grafana-1")
BROKER = "lab-kimia-mqtt-pqc-broker-1"
TELEGRAF = "lab-kimia-suhu-telegraf-1"
RECEIVER = "lab-kimia-pqc-session.service"
DIAGNOSTIC = "lab-kimia-mqtt-diagnostic.service"


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE)


def compose(*args, broker=False, source=None):
    directory = ROOT / "infra/mqtt" if broker else MONITOR
    return run("docker", "compose", "--project-directory", str(directory), "--env-file", str(directory / ".env"),
               "-f", str(source or directory / "compose.yaml"), *args)


def snapshot():
    mounts = {}
    for name in DATA_CONTAINERS:
        info = json.loads(run("docker", "inspect", name))[0]
        mounts[name] = {m["Destination"]: m["Name"] for m in info["Mounts"] if m["Type"] == "volume"}
    require(mounts == {
        DATA_CONTAINERS[0]: {"/var/lib/influxdb2": "lab-kimia-suhu_influx-data", "/etc/influxdb2": "lab-kimia-suhu_influx-config"},
        DATA_CONTAINERS[1]: {"/var/lib/grafana": "lab-kimia-suhu_grafana-data"}}, "Unexpected initialized data volumes")
    dashboard, _ = grafana_dashboard()
    token = json.loads((ROOT / "evidence/local/session-private/influx.json").read_text())
    files = [MONITOR / ".env", ROOT / "infra/mqtt/.env",
             *(ROOT / "evidence/local/mqtt-private" / n for n in ("device.json", "receiver.json", "passwords")),
             *(ROOT / "evidence/local/session-private" / n for n in ("client.identity", "server.identity", "influx.json")),
             *(ROOT / "firmware/include" / n for n in ("mqtt_diag_secrets.h", "pqc_session_identity.h"))]
    return {"volumes": mounts, "dashboard_uid": dashboard["uid"], "bucket_id": token["bucket_id"],
            "private_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}


def history():
    selected = []
    for ticket in ("04", "05"):
        prior = json.loads((ROOT / f"docs/evidence/pqc-ticket-{ticket}/capture-validation.json").read_text())["lxc_stored_events"]
        selected += [prior[0], prior[-1]]
    return matched_points(selected)


def default_without_cloud():
    # Exercise actual Compose interpolation with all archived MQTT variables absent.
    lines = [line for line in (MONITOR / ".env").read_text().splitlines()
             if line.partition("=")[0].strip().startswith(("INFLUX_", "GRAFANA_"))]
    env = {key: value for key, value in os.environ.items() if not key.startswith(("MQTT_", "COMPOSE_"))}
    with tempfile.NamedTemporaryFile(mode="w", dir=PRIVATE, prefix="minimal-env-", suffix=".env") as file:
        file.write("\n".join(lines)+"\n"); file.flush()
        subprocess.run(["docker", "compose", "--project-directory", str(MONITOR), "--env-file", file.name,
                        "-f", str(MONITOR / "compose.yaml"), "config", "--quiet"], env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def verify_state():
    baseline = json.loads((PRIVATE / "baseline.json").read_text())
    require(snapshot() == baseline, "Initialized volumes, dashboard, bucket, credentials or pins changed")
    default_without_cloud()
    require(set(compose("config", "--services").split()) == {"influxdb", "grafana"}, "Default Compose still contains legacy ingress")
    require(subprocess.run(["docker", "inspect", TELEGRAF], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0,
            "Legacy Telegraf container still exists")
    require(run("systemctl", "is-active", RECEIVER).strip() == "active" and run("systemctl", "is-enabled", RECEIVER).strip() == "enabled",
            "Receiver is not active/enabled")
    require(subprocess.run(["systemctl", "is-active", DIAGNOSTIC], stdout=subprocess.DEVNULL).returncode != 0,
            "Diagnostic proof service still active")
    for name in (*DATA_CONTAINERS, BROKER):
        info = json.loads(run("docker", "inspect", name))[0]
        require(info["State"]["Running"] and info["HostConfig"]["RestartPolicy"]["Name"] == "unless-stopped", "Container restart policy mismatch")
    broker = json.loads(run("docker", "inspect", BROKER))[0]
    require(broker["HostConfig"]["PortBindings"] == {"1883/tcp": [{"HostIp": "10.34.211.141", "HostPort": "1883"}]},
            "Broker listener no longer bound to private TCP/1883")
    require(run("systemctl", "is-enabled", "docker.service").strip() == "enabled", "Docker autostart disabled")
    return {"preserved_initialized_state": True, "historical_points": history(), "default_services": ["influxdb", "grafana"],
            "telegraf_removed": True, "receiver_active_enabled": True, "diagnostic_stopped": True,
            "private_mqtt_port": 1883, "tls": False, "autostart_configured": True, "lxc_reboot_tested": False,
            "default_compose_without_cloud_credentials": True,
            "volumes": baseline["volumes"], "dashboard_uid": baseline["dashboard_uid"]}


def main():
    require(os.geteuid() == 0 and ROOT == Path("/opt/lab-kimia-mqtt"), "Run as root in the existing private LXC deployment")
    PRIVATE.mkdir(parents=True, exist_ok=True); PRIVATE.chmod(0o700)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    compose("config", "--quiet", source=ROOT / "compose.yaml")
    compose("config", "--quiet", broker=True)
    before = snapshot()
    history()
    baseline = PRIVATE / "baseline.json"
    backup = PRIVATE / "compose.before.yaml"
    if baseline.exists():
        require(json.loads(baseline.read_text()) == before and backup.exists(), "Previous migration baseline differs; investigate before continuing")
    else:
        shutil.copyfile(MONITOR / "compose.yaml", backup); backup.chmod(0o600)
        baseline.write_text(json.dumps(before, indent=2)+"\n"); baseline.chmod(0o600)
    shutil.copyfile(ROOT / "compose.yaml", MONITOR / "compose.yaml")
    shutil.copyfile(ROOT / "compose.legacy.yaml", MONITOR / "compose.legacy.yaml")
    if subprocess.run(["docker", "inspect", TELEGRAF], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        run("docker", "stop", TELEGRAF)
        run("docker", "rm", TELEGRAF)  # Stateless ingress only. Never remove a data volume.
    compose("up", "-d", "--wait", "--wait-timeout", "120")
    compose("up", "-d", "--wait", "--wait-timeout", "60", broker=True)
    run("systemctl", "disable", "--now", DIAGNOSTIC)
    run("systemctl", "enable", "--now", RECEIVER)
    result = {"cutover_utc": datetime.now(timezone.utc).isoformat(), **verify_state()}
    (PUBLIC / "cutover.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"cutover": True, "history_points_matched": len(result["historical_points"]), "private_state_preserved": True}))


if __name__ == "__main__":
    main()
