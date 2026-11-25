"""Native MQTT control only. It cannot serve as ESP32/Wokwi acceptance evidence."""
import argparse
import json
from pathlib import Path
import queue
import secrets
import time
from tools.mqtt.client import MqttConnection, credentials, require
from tools.session.native import Native, Channel, ROOT, TOPIC_PREFIX, topics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker", type=Path, default=ROOT / "evidence/local/mqtt-private/device.json")
    parser.add_argument("--identity", type=Path, default=ROOT / "evidence/local/session-private/client.identity")
    args = parser.parse_args()
    broker = credentials(args.broker)
    UP, DOWN = topics(broker.get("topic_prefix", TOPIC_PREFIX))
    run_id = secrets.token_hex(16)
    payload = json.dumps({"device_id": "esp32-meja01", "probe": "ticket-03", "run_id": run_id,
                          "temperature_c": 26.25}, separators=(",", ":")).encode()
    with Channel(Native(), args.identity.read_bytes()) as channel, \
            MqttConnection(broker, "native-session-") as connection:
        require(connection.code == 0 and connection.subscribe(DOWN) == [0], "MQTT client denied")
        require(connection.publish(UP, channel.begin()) == 0, "Client hello denied")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                message = connection.messages.get(timeout=0.25)
            except queue.Empty:
                continue
            if message.topic != DOWN or message.retain:
                continue
            event, reply, plain = channel.receive(message.payload)
            require(event != 0, "Rejected native handshake/reply")
            if reply:
                require(connection.publish(UP, reply) == 0, "Client key denied")
            if event == 2:
                require(connection.publish(UP, channel.encrypt(payload)) == 0, "Encrypted probe denied")
            if event == 3:
                require(json.loads(plain) == {"accepted": True, "run_id": run_id}, "Invalid encrypted ACK")
                print(json.dumps({"passed": True, "source": "native-control", "broker": broker["host"],
                                  "topic_prefix": UP.rsplit("/", 1)[0], "run_id": run_id,
                                  "session_id": channel.status()[1], "encrypted_ack_verified": True}))
                return
        raise RuntimeError("Native MQTT session timeout")


if __name__ == "__main__":
    main()
