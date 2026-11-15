"""Ticket 05 destructive lab checks. Run on the private LXC with simulator stopped.

Temporarily restarts only the experimental receiver/broker and Influx container.
Every stopped service is restored in finally. Does not alter credentials/volumes.
Native controls are explicitly separate from ESP32 evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import time
from contextlib import contextmanager
from tools.mqtt.client import MqttConnection, credentials, require
from tools.session.native import Channel, Native, ROOT, UP, DOWN
from tools.telemetry.verify_lxc import query, journal_events, matched_points, verify_dashboard

FOLDER = ROOT / "docs/evidence/pqc-ticket-05"
PRIVATE = ROOT / "evidence/local"
IDENTITY = (PRIVATE / "session-private/client.identity")
SAMPLE = b'{"device_id":"esp32-meja01","temperature_c":27.5,"gas_raw":1234,"gas_alarm":false,"temperature_alarm":false}'
BROKER = "lab-kimia-mqtt-pqc-broker-1"
INFLUX = "lab-kimia-suhu-influxdb-1"


def command(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


@contextmanager
def stopped(kind, name):
    command(kind, "stop", name)
    try:
        yield
    finally:
        command(kind, "start", name)


def wait_ready(kind):
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        if kind == "influx":
            try:
                query('from(bucket:"telemetry") |> range(start:-1s) |> limit(n:1)')
                return
            except OSError:
                pass
        else:
            events = journal_events()
            if events and events[-1]["event"] == "ready":
                return
        time.sleep(.2)
    raise RuntimeError("Service failed to become ready")


class Device:
    def __init__(self, observer, identity=None):
        self.observer = observer
        self.channel = Channel(Native(), identity or IDENTITY.read_bytes())
        self.connection = MqttConnection(credentials(PRIVATE / "mqtt-private/device.json"), "security-control-")
        require(self.connection.code == 0 and self.connection.subscribe(DOWN) == [0], "Device MQTT denied")
        self.wire = []

    def close(self):
        self.connection.close()
        self.channel.close()

    def publish(self, packet):
        self.wire.append({"type": packet[4] if len(packet) >= 5 else None, "bytes": len(packet),
                          "sha256": hashlib.sha256(packet).hexdigest()})
        require(self.connection.publish(UP, packet) < 128, "Publish denied")
        observed = self.observer.messages.get(timeout=3)
        require(observed.topic == UP and bytes(observed.payload) == packet,
                "Independent MQTT subscriber did not observe the exact wire payload")

    def message(self, timeout=3):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            message = self.connection.messages.get(timeout=max(.01, deadline-time.monotonic()))
            if message.topic == DOWN and not message.retain:
                return bytes(message.payload)
        raise queue.Empty

    def handshake(self, drop_m2=False, drop_m4=False, hello=None):
        self.publish(hello or self.channel.begin())
        m2 = self.message()
        if drop_m2:
            self.publish(self.channel.retry())
            require(self.message() == m2, "M2 retry changed challenge")
        event, m3, _ = self.channel.receive(m2)
        require(event == 1 and m3, "M2 authentication failed")
        self.publish(m3)
        m4 = self.message()
        if drop_m4:
            self.publish(self.channel.retry())
            require(self.message() == m4, "M4 retry changed confirmation")
        require(self.channel.receive(m4)[0] == 2, "M4 confirmation failed")
        return self.channel.status()[1]

    def sample(self):
        packet = self.channel.encrypt(SAMPLE)
        require(SAMPLE not in packet and b'"temperature_c"' not in packet and b'esp32-meja01' not in packet,
                "Known plaintext visible in encrypted MQTT payload")
        self.publish(packet)
        event, _, ack = self.channel.receive(self.message())
        require(event == 3 and json.loads(ack) == {"stored_counter": int.from_bytes(packet[21:29], "little")},
                "Stored ACK mismatch")
        return packet

    def reject(self, packet, label):
        start = time.time_ns()
        self.publish(packet)
        try:
            self.message(.6)
        except queue.Empty:
            pass
        else:
            raise RuntimeError(label+": unexpected response")
        stop = time.time_ns()
        rows = query('from(bucket:"telemetry") |> range(start:time(v:%d),stop:time(v:%d)) '
                     '|> filter(fn:(r)=>r._measurement=="suhu" and r._field=="temperature_c" '
                     'and r.device_id=="esp32-meja01")' % (start, stop))
        require(not rows, label+": unexpected database point")
        return {"case": label, "no_reply": True, "influx_points": 0, "start_ns": start, "stop_ns": stop}


def main(output_dir=FOLDER):
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "security.json"
    require(not result_path.exists(), "Evidence already exists; choose a new --output-dir before running lab faults")
    started = time.time_ns()
    results, sessions = [], []
    observer = MqttConnection(credentials(PRIVATE / "mqtt-private/receiver.json"), "security-observer-")
    require(observer.code == 0 and observer.subscribe(UP) == [0], "Observer MQTT denied")
    device = Device(observer)
    try:
        sessions.append(device.handshake(drop_m2=True, drop_m4=True))
        old = device.sample()
        results.append(device.reject(old, "duplicate telemetry counter"))
        pending = device.channel.encrypt(SAMPLE)
        for offset, name in ((0, "magic"), (3, "version"), (4, "type"), (5, "session id"),
                             (21, "counter"), (29, "length"), (31, "ciphertext"), (206, "tag"),
                             (31+len(SAMPLE), "padding")):
            changed = bytearray(pending); changed[offset] ^= 1
            results.append(device.reject(bytes(changed), "modified "+name))
        results.append(device.reject(pending[:-1], "truncated packet"))
        results.append(device.reject(SAMPLE, "plaintext JSON"))
        # Invalid tags must not consume the valid counter.
        device.publish(pending)
        event, _, ack = device.channel.receive(device.message())
        require(event == 3 and json.loads(ack)["stored_counter"] == int.from_bytes(pending[21:29], "little"),
                "Invalid tag advanced receiver counter")
        newer = device.channel.encrypt(SAMPLE)
        newest = device.channel.encrypt(SAMPLE)
        device.publish(newest)
        require(device.channel.receive(device.message())[0] == 3, "Newer packet failed")
        results.append(device.reject(newer, "out of order old counter"))
        results.append(device.reject(device.channel.encrypt(b'{}'), "authenticated invalid schema"))
        # Copied public identity and valid broker password do not prove possession.
        forged = bytearray(IDENTITY.read_bytes())
        forged[:1345] = Native().keypair()[0]
        attacker = Device(observer, bytes(forged))
        try:
            attacker.publish(attacker.channel.begin())
            event, m3, _ = attacker.channel.receive(attacker.message())
            require(event == 1, "Impostor setup failed")
            # Both connections see DOWN; discard the challenge on the valid client.
            device.message()
            results.append(attacker.reject(m3, "wrong signing secret with correct public binding"))
        finally:
            attacker.close()
        device.sample()  # Invalid rekey did not destroy the current active keys.
        sessions.append(device.handshake())
        results.append(device.reject(old, "previous session after rekey"))
        device.sample()
        with stopped("systemctl", "lab-kimia-pqc-session.service"):
            hello = device.channel.begin()
            device.publish(hello)
            try:
                device.message(.6)
            except queue.Empty:
                pass
            else:
                raise RuntimeError("Stopped receiver replied")
        wait_ready("receiver")
        sessions.append(device.handshake(hello=device.channel.retry()))
        device.sample()
        results.append({"case": "receiver restart", "fresh_session": True, "stored_after": True})
        with stopped("docker", INFLUX):
            failed = device.channel.encrypt(SAMPLE)
            device.publish(failed)
            try:
                device.message(2.5)
            except queue.Empty:
                pass
            else:
                raise RuntimeError("Unconfirmed Influx write received ACK")
        wait_ready("influx")
        results.append(device.reject(failed, "failed write never replayed"))
        device.sample()
        results.append({"case": "Influx unavailable", "no_stored_ack": True, "fresh_sample_after": True})
        device.close(); device = None
        observer.close()
        with stopped("docker", BROKER):
            time.sleep(1)
        time.sleep(4)  # systemd RestartSec=3, then subscribe.
        observer = MqttConnection(credentials(PRIVATE / "mqtt-private/receiver.json"), "security-observer-")
        require(observer.code == 0 and observer.subscribe(UP) == [0], "Observer MQTT reconnect denied")
        device = Device(observer)
        sessions.append(device.handshake())
        results.append(device.reject(old, "previous session after broker restart"))
        device.sample()
        results.append({"case": "broker restart", "fresh_session": True, "stored_after": True})
        require(len(set(sessions)) == len(sessions), "Session ID reused after recovery")
        events = [e for e in journal_events() if e["event"] == "telemetry_stored" and e["received_ns"] >= started]
        points = matched_points(events)
        graph = verify_dashboard(points)
        require(any(e["event"] == "write_failed" and e.get("session_id") in sessions for e in journal_events()),
                "Missing failed-write receiver evidence")
        result = {"passed": True, "source": "native-client on real MQTT/LXC", "started_ns": started,
                  "sessions": sessions, "cases": results, "lost_m2_recovered": True, "lost_m4_recovered": True,
                  "known_plaintext_absent_in_data_frames": True, "points": points,
                  "independent_mqtt_subscriber_matched_published_bytes": True,
                  "wire_metadata_only": device.wire, "grafana": graph}
        result_path.write_text(json.dumps(result, indent=2)+"\n")
        print(json.dumps({"passed": True, "cases": len(results), "sessions": len(sessions), "stored": len(points)}))
    finally:
        if device:
            device.close()
        observer.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=FOLDER,
                        help="Fresh evidence directory; an existing security.json is never overwritten")
    args = parser.parse_args()
    main(args.output_dir)
