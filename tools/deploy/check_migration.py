"""Native storage controls and service restart proof, distinct from Wokwi evidence."""
import json
import time
from tools.deploy.migrate import PUBLIC, RECEIVER, compose, run, verify_state
from tools.session.native import Native, Channel, ROOT, UP, DOWN
from tools.mqtt.client import MqttConnection, credentials, require
from tools.telemetry.check_mqtt import wait
from tools.telemetry.verify_lxc import journal_events, matched_points, verify_dashboard, token_scope


def control():
    plain = b'{"device_id":"esp32-meja01","temperature_c":26.75,"gas_raw":1001,"gas_alarm":false,"temperature_alarm":false}'
    with Channel(Native(), (ROOT / "evidence/local/session-private/client.identity").read_bytes()) as channel, \
            MqttConnection(credentials(ROOT / "evidence/local/mqtt-private/device.json"), "migration-control-") as connection:
        require(connection.code == 0 and connection.subscribe(DOWN) == [0], "Migration client denied")
        connection.publish(UP, channel.begin()); wait(connection, channel, 2)
        sid = channel.status()[1]
        connection.publish(UP, channel.encrypt(plain))
        require(json.loads(wait(connection, channel, 3)) == {"stored_counter": 1}, "Storage ACK mismatch")
    deadline = time.monotonic()+3
    while time.monotonic() < deadline:
        selected = [e for e in journal_events() if e["event"] == "telemetry_stored" and e["session_id"] == sid]
        if selected:
            require(len(selected) == 1, "Unexpected duplicate stored control")
            return matched_points(selected)[0]
        time.sleep(.1)
    raise RuntimeError("No receiver event for stored control")


def main():
    verify_state()
    before = control()
    # Existing volume/container identities survive service restarts. No host reboot.
    compose("restart")
    compose("up", "-d", "--wait", "--wait-timeout", "120")
    compose("restart", broker=True)
    run("systemctl", "restart", RECEIVER)
    deadline = time.monotonic()+15
    while time.monotonic() < deadline:
        ready = journal_events()
        if ready and ready[-1]["event"] == "ready":
            break
        time.sleep(.2)
    after = control()
    require(before["session_id"] != after["session_id"], "Restart reused old session")
    # Re-query both timestamped points after the restart.
    points = matched_points([dict(p) for p in (before, after)])
    result = {"passed": True, "source": "native-control", "points": points,
              "restart_preserved_history": True, "fresh_session_after_restart": True,
              "state": verify_state(), "token": token_scope(), "grafana": verify_dashboard(points)}
    (PUBLIC / "restart.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"passed": True, "native_points": 2, "services_restarted": True, "history_preserved": True}))


if __name__ == "__main__":
    main()
