"""Native controls for the real receiver/storage path; never counts as Wokwi evidence."""
import json
import queue
import secrets
import time
from tools.session.native import Native, Channel, ROOT, UP, DOWN
from tools.mqtt.client import MqttConnection, credentials, require


def wait(connection, channel, wanted, timeout=10):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        try:
            message = connection.messages.get(timeout=0.2)
        except queue.Empty:
            continue
        if message.topic != DOWN or message.retain:
            continue
        event, reply, plain = channel.receive(message.payload)
        require(event != 0, "Native control rejected response")
        if reply:
            require(connection.publish(UP, reply) < 128, "Native key publish denied")
        if event == wanted:
            return plain
    raise RuntimeError("Native telemetry control timed out")


def no_ack(connection, timeout=0.5):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        try:
            message = connection.messages.get(timeout=0.1)
        except queue.Empty:
            continue
        require(message.topic != DOWN, "Rejected packet unexpectedly got response")


def main():
    run_id = secrets.token_hex(16)
    with Channel(Native(), (ROOT / "evidence/local/session-private/client.identity").read_bytes()) as channel, \
            MqttConnection(credentials(ROOT / "evidence/local/mqtt-private/device.json"), "native-telemetry-") as connection:
        require(connection.code == 0 and connection.subscribe(DOWN) == [0], "Native MQTT connection denied")
        connection.publish(UP, channel.begin()); wait(connection, channel, 2)
        sid = channel.status()[1]
        def payload(temperature, gas, ga, ta):
            return json.dumps({"device_id": "esp32-meja01", "temperature_c": temperature, "gas_raw": gas,
                               "gas_alarm": ga, "temperature_alarm": ta}, separators=(",", ":")).encode()
        # Schema failure does not reach storage/ACK, even when authenticated.
        connection.publish(UP, channel.encrypt(b'{}')); no_ack(connection)
        expected = []
        for values in ((25.0, 1200, False, False), (45.0, 1200, False, True),
                       (45.0, 3000, True, True), (25.0, 3000, True, False)):
            plain = payload(*values)
            packet = channel.encrypt(plain)
            sequence = int.from_bytes(packet[21:29], "little")
            changed = bytearray(packet); changed[-1] ^= 1
            connection.publish(UP, changed); no_ack(connection)
            connection.publish(UP, packet)
            ack = json.loads(wait(connection, channel, 3))
            require(ack == {"stored_counter": sequence}, "Storage ACK mismatch")
            expected.append({"counter": sequence, **json.loads(plain)})
            connection.publish(UP, packet); no_ack(connection)
        result = {"passed": True, "source": "native-control", "run_id": run_id, "session_id": sid,
                  "four_states": expected, "tamper_no_ack": True, "replay_no_ack": True, "schema_no_ack": True}
        folder = ROOT / "docs/evidence/pqc-ticket-04"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "native-mqtt.json").write_text(json.dumps(result, indent=2)+"\n")
        print(json.dumps({"passed": True, "source": "native-control", "session_id": sid, "stored_samples": 4}))


if __name__ == "__main__":
    main()
