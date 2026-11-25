"""Outsider attacks on the public-broker path (wokwi-web-broker-publik ticket 04).

Anyone can publish and subscribe on a public broker, so these checks act as an
anonymous outsider: read traffic, forge, tamper, replay, leave retained junk and
flood handshakes. Expected result: no plaintext leaks, nothing unauthenticated is
stored or acknowledged, the receiver keeps running and sessions recover.

  native  Simulator stopped. A native client with the demo identity plays the device
          and uses the ticket-03 probe, so nothing is written to InfluxDB.
  attack  Wokwi web running. Only the outsider acts; it replays real ESP32 frames.
          Verify the serial log afterwards with verify_capture --public.

Runs on the LXC. The flood is deliberately small (rate and count bounded) because
the broker is a shared third-party service. Retained junk is always cleared.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import secrets
import subprocess
import time
from tools.mqtt.client import MqttConnection, credentials, require, mqtt
from tools.session.native import Native, Channel, ROOT, TOPIC_PREFIX, topics
from tools.telemetry.verify_lxc import journal_events, query

UNIT = "lab-kimia-pqc-session-public.service"
BROKER = ROOT / "evidence/local/public-broker/session.json"
IDENTITY = ROOT / "evidence/local/session-demo/client.identity"
HEADER = bytes.fromhex("4c4b3301")
FLOOD_RATE, FLOOD_SECONDS = 25, 12


def restarts():
    out = subprocess.check_output(["systemctl", "show", UNIT, "-p", "NRestarts", "-p", "ActiveState"], text=True)
    values = dict(line.split("=", 1) for line in out.split())
    return values["ActiveState"], int(values["NRestarts"])


def forged():
    """Well-formed headers with random bodies at every valid size, plus pure noise."""
    return [HEADER + b"\x01" + secrets.token_bytes(64), HEADER + b"\x03" + secrets.token_bytes(200),
            HEADER + b"\x05" + secrets.token_bytes(202), secrets.token_bytes(207), HEADER + b"\x09"]


def tampered(packet):
    changed = bytearray(packet)
    changed[-1] ^= 1
    return bytes(changed)


class Outsider:
    """Anonymous client: sees every frame under the prefix and publishes anything."""

    def __init__(self, broker, prefix):
        self.connection = MqttConnection(broker, "outsider-")
        require(self.connection.code == 0 and self.connection.subscribe(prefix + "/#") == [0], "Outsider denied")
        self.seen = []

    def drain(self):
        while True:
            try:
                message = self.connection.messages.get_nowait()
            except queue.Empty:
                return self.seen
            self.seen.append((message.topic, bytes(message.payload)))

    def send(self, topic, payload, retain=False):
        result = self.connection.client.publish(topic, payload, qos=0, retain=retain)
        require(result.rc == mqtt.MQTT_ERR_SUCCESS, "Outsider publish failed")

    def flood(self, topic, frames):
        sent, deadline = 0, time.monotonic() + FLOOD_SECONDS
        while time.monotonic() < deadline:
            self.send(topic, frames[sent % len(frames)])
            sent += 1
            time.sleep(1 / FLOOD_RATE)
        return sent


class Device:
    """Native stand-in for the ESP32, using the demo identity."""

    def __init__(self, broker, down):
        self.connection = MqttConnection(broker, "native-public-")
        require(self.connection.code == 0 and self.connection.subscribe(down) == [0], "Device denied")
        self.channel = Channel(Native(), IDENTITY.read_bytes())
        self.ignored = 0

    def replies(self, up, timeout):
        """Feed DOWN frames to the channel; junk from outsiders is counted, not fatal."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = self.connection.messages.get(timeout=0.2)
            except queue.Empty:
                continue
            event, reply, plain = self.channel.receive(bytes(message.payload))
            if event == 0:
                self.ignored += 1
                continue
            if reply:
                self.connection.client.publish(up, reply, qos=0)
            yield event, plain

    def handshake(self, up, timeout=40):
        self.channel.reset()
        hello = self.channel.begin()
        self.connection.client.publish(up, hello, qos=0)
        for event, _ in self.replies(up, timeout):
            if event == 2:
                return hello
        return None

    def probe(self, up, timeout=8):
        """Encrypted ticket-03 probe: acknowledged by the receiver, never stored."""
        run_id = secrets.token_hex(16)
        plain = json.dumps({"device_id": "esp32-meja01", "probe": "ticket-03", "run_id": run_id,
                            "temperature_c": 26.25}, separators=(",", ":")).encode()
        packet = self.channel.encrypt(plain)
        self.connection.client.publish(up, packet, qos=0)
        for event, ack in self.replies(up, timeout):
            if event == 3 and json.loads(ack) == {"accepted": True, "run_id": run_id}:
                return packet, plain
        return None, plain

    def silent(self, up, seconds=2):
        """True when no authenticated reply arrives (rejected input gets no answer)."""
        return not any(True for _ in self.replies(up, seconds))

    def close(self):
        self.channel.close()
        self.connection.close()


def receiver_events(since):
    return journal_events(UNIT)[since:]


def influx_points(start_ns, stop_ns):
    return len(query('from(bucket:"telemetry") |> range(start:time(v:%d),stop:time(v:%d)) '
                     '|> filter(fn:(r)=>r._measurement=="suhu" and r.device_id=="esp32-meja01")' % (start_ns, stop_ns)))


def native(broker, up, down, prefix):
    results, start_ns, baseline = {}, time.time_ns(), len(journal_events(UNIT))
    state_before = restarts()
    outsider, device = Outsider(broker, prefix), Device(broker, down)
    try:
        hello = device.handshake(up)
        require(hello, "Initial demo handshake failed")
        packet, plain = device.probe(up)
        require(packet, "Initial probe not acknowledged")
        time.sleep(1)
        observed = outsider.drain()
        markers = (plain, b"temperature_c", b"esp32-meja01", b"ticket-03")
        results["confidentiality"] = {"frames_observed": len(observed),
                                      "plaintext_seen": any(m in p for _, p in observed for m in markers)}
        require(not results["confidentiality"]["plaintext_seen"], "Plaintext visible to outsider")

        # Tamper a fresh frame so rejection comes from the tag, not from the replay check.
        cases = {"forged": forged(), "tampered_data": [tampered(device.channel.encrypt(b'{"x":1}'))],
                 "replayed_data": [packet]}
        for name, frames in cases.items():
            before = len(journal_events(UNIT))
            for frame in frames:
                outsider.send(up, frame)
            no_reply = device.silent(up)
            rejected = sum(e["event"] == "rejected" for e in journal_events(UNIT)[before:])
            results[name] = {"frames": len(frames), "authenticated_reply": not no_reply, "receiver_rejected": rejected}
            require(no_reply, name + " produced an authenticated reply")
        require(device.probe(up)[0], "Session broken by rejected frames")

        # Replaying the device's own ClientHello: does it disturb the active session?
        outsider.send(up, hello)
        time.sleep(2)
        survived = device.probe(up)[0] is not None
        recovered = survived or (device.handshake(up) is not None and device.probe(up)[0] is not None)
        results["replayed_client_hello"] = {"active_session_survived": survived, "recovered": recovered}
        require(recovered, "No recovery after ClientHello replay")

        # Retained junk: delivered to later subscribers on both topics.
        junk = secrets.token_bytes(207)
        outsider.send(up, junk, retain=True)
        outsider.send(down, junk, retain=True)
        late = Device(broker, down)
        late_junk = sum(1 for _ in late.replies(up, 3))
        results["retained_junk"] = {"accepted_by_late_device": late_junk, "late_device_ignored": late.ignored}
        late.close()
        require(late_junk == 0 and late.ignored >= 1, "Retained junk not seen or not rejected")

        # Bounded handshake flood: random hellos and replays of a real hello.
        frames = [HEADER + b"\x01" + secrets.token_bytes(64) for _ in range(20)] + [hello]
        sent = outsider.flood(up, frames)
        state_after_flood = restarts()
        t0 = time.monotonic()
        recovered = device.handshake(up, timeout=60) is not None and device.probe(up)[0] is not None
        results["flood"] = {"frames": sent, "rate_per_s": FLOOD_RATE, "seconds": FLOOD_SECONDS,
                            "receiver_state": state_after_flood[0],
                            "receiver_restarts_during_test": state_after_flood[1] - state_before[1],
                            "session_recovered": recovered, "recovery_s": round(time.monotonic() - t0, 1)}
        require(state_after_flood[0] == "active" and state_after_flood[1] == state_before[1], "Receiver crashed")
        require(recovered, "No session after flood")
    finally:
        clear_retained(outsider, up, down)
        device.close()
        outsider.connection.close()
    stop_ns = time.time_ns()
    events = receiver_events(baseline)
    results["storage"] = {"telemetry_stored_events": sum(e["event"] == "telemetry_stored" for e in events),
                          "influx_points": influx_points(start_ns, stop_ns),
                          "rejected_events": sum(e["event"] == "rejected" for e in events)}
    require(results["storage"]["telemetry_stored_events"] == 0 and results["storage"]["influx_points"] == 0,
            "Unauthenticated or test data reached storage")
    return results


def attack(broker, up, down, prefix, wait_seconds, frames_wanted=5):
    """Outsider only, while the Wokwi ESP32 is running. Waits until the device sends
    data, so it can be started before the simulator (owner may be off the LXC network)."""
    results, baseline = {}, len(journal_events(UNIT))
    state_before = restarts()
    outsider = Outsider(broker, prefix)
    try:
        deadline = time.monotonic() + wait_seconds
        captured = []
        while len(captured) < frames_wanted and time.monotonic() < deadline:
            time.sleep(1)
            if not outsider.connection.client.is_connected():
                # Public broker may drop an idle client; the connection never reconnects
                # by itself, so a lost subscription would silently hide the ESP32.
                outsider.connection.close()
                outsider = Outsider(broker, prefix)
                print(json.dumps({"event": "outsider_reconnected"}), flush=True)
            captured = [p for t, p in outsider.drain() if t == up and len(p) == 207 and p[4] == 5]
        hellos = [p for t, p in outsider.seen if t == up and len(p) == 69 and p[4] == 1]
        require(captured, "No ESP32 data frames observed; is the simulator running?")
        results["attack_started_utc"] = datetime.now(timezone.utc).isoformat()
        markers = (b"temperature_c", b"esp32-meja01", b"gas_raw")
        results["confidentiality"] = {"frames_observed": len(outsider.seen),
                                      "plaintext_seen": any(m in p for _, p in outsider.seen for m in markers)}
        for frame in captured:
            outsider.send(up, frame)
            outsider.send(up, tampered(frame))
        for frame in forged():
            outsider.send(up, frame)
            outsider.send(down, frame)
        outsider.send(down, captured[0], retain=True)
        results["replayed_and_tampered_data"] = len(captured)
        frames = [HEADER + b"\x01" + secrets.token_bytes(64) for _ in range(20)] + hellos[-1:]
        results["flood"] = {"frames": outsider.flood(up, frames), "rate_per_s": FLOOD_RATE, "seconds": FLOOD_SECONDS}
    finally:
        clear_retained(outsider, up, down)
        outsider.connection.close()
    time.sleep(3)
    events = receiver_events(baseline)
    stored = [(e["session_id"], e["counter"]) for e in events if e["event"] == "telemetry_stored"]
    state_after = restarts()
    results["receiver"] = {"state": state_after[0], "restarts": state_after[1] - state_before[1],
                           "rejected_events": sum(e["event"] == "rejected" for e in events),
                           "stored_events": len(stored), "duplicate_stored": len(stored) - len(set(stored))}
    require(not results["confidentiality"]["plaintext_seen"], "Plaintext visible to outsider")
    require(state_after[0] == "active" and results["receiver"]["restarts"] == 0, "Receiver crashed")
    require(results["receiver"]["duplicate_stored"] == 0, "Replay stored twice")
    return results


def clear_retained(outsider, up, down):
    for topic in (up, down):
        outsider.send(topic, b"", retain=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("native", "attack"))
    parser.add_argument("--wait-seconds", type=int, default=900, help="attack: max wait for ESP32 data")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Evidence already exists; choose a new --output")
    broker = credentials(BROKER)
    require(broker.get("public") is True, "Public broker settings expected")
    prefix = broker.get("topic_prefix", TOPIC_PREFIX)
    up, down = topics(prefix)
    started = datetime.now(timezone.utc).isoformat()
    if args.mode == "native":
        results = native(broker, up, down, prefix)
    else:
        results = attack(broker, up, down, prefix, args.wait_seconds)
    report = {"passed": True, "mode": args.mode, "source": "native-control" if args.mode == "native" else
              "outsider attack during Wokwi web run", "broker": broker["host"], "topic_prefix": prefix,
              "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(), **results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
