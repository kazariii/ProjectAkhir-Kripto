"""One-worker authenticated session receiver: telemetry storage and encrypted ACKs."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import ssl
import time
from urllib.error import URLError
from tools.telemetry.storage import Writer, parse
from tools.mqtt.client import MqttConnection, credentials, require, mqtt
from tools.session.native import Native, Channel, UP, DOWN


def log(event, **fields):
    print("SESSION_SERVER " + json.dumps({"event": event, "utc": datetime.now(timezone.utc).isoformat(), **fields}), flush=True)


def probe(plain):
    try:
        data = json.loads(plain)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or set(data) != {"device_id", "probe", "run_id", "temperature_c"}:
        return None
    if (data["device_id"] != "esp32-meja01" or data["probe"] != "ticket-03" or
            not isinstance(data["run_id"], str) or not re.fullmatch("[0-9a-f]{32}", data["run_id"]) or
            type(data["temperature_c"]) not in (float, int) or data["temperature_c"] != 26.25):
        return None
    return data


def process_telemetry(plain, packet, received_ns, channel, writer):
    """Called only after Channel returns authenticated Plaintext. ACK means stored."""
    data = parse(plain)
    if data is None:
        return None
    writer.write(data, received_ns)
    sequence = int.from_bytes(packet[21:29], "little")
    reply = channel.encrypt(json.dumps({"stored_counter": sequence}, separators=(",", ":")).encode())
    return data, sequence, reply


def serve(mqtt_path, identity_path, influx_path=None):
    # Crypto is never called from Paho's network thread. Its queue is bounded;
    # a dropped handshake fails closed at the client deadline.
    incoming = queue.Queue(maxsize=4)
    native = Native()
    writer = Writer(influx_path) if influx_path else None
    with Channel(native, identity_path.read_bytes(), server=True) as channel, \
            MqttConnection(credentials(mqtt_path), "lxc-session-") as connection:
        require(connection.code == 0, "Receiver MQTT authentication failed")
        require(not isinstance(connection.client.socket(), ssl.SSLSocket), "Unexpected TLS")

        def received(client, userdata, message):
            if message.topic != UP or message.retain or not 5 <= len(message.payload) <= 1519:
                return
            try:
                incoming.put_nowait((message.payload, time.monotonic(), time.time_ns()))
            except queue.Full:
                pass

        connection.client.on_message = received
        connection.client.on_publish = None
        require(connection.subscribe(UP) == [0], "Session subscription denied")
        log("ready", port=1883, tls=False, profile="LK3/1")
        renewal_at = 0
        while True:
            require(connection.client.is_connected(), "MQTT disconnected; discard session and restart")
            channel.tick()
            # Server wall time can run faster than the simulator. Ask for a new
            # handshake while the old keys still have 120 seconds of life.
            if channel.renewal_due() and time.monotonic()-renewal_at >= 5:
                renewal = channel.encrypt(b'{"renew_session":true}')
                result = connection.client.publish(DOWN, renewal, qos=0, retain=False)
                require(result.rc == mqtt.MQTT_ERR_SUCCESS, "Cannot queue authenticated renewal")
                renewal_at = time.monotonic()
                log("renewal_requested", session_id=channel.status()[1])
            try:
                packet, queued_at, received_ns = incoming.get(timeout=0.25)
            except queue.Empty:
                continue
            if packet[4] == 5 and time.monotonic()-queued_at >= 2:
                log("payload_discarded", reason="receiver queue age")
                continue
            event, reply, plain = channel.receive(packet)
            active, sid = channel.status()
            if event == 0:
                log("rejected", frame_type=packet[4])
                continue
            if event == 2:
                renewal_at = 0
                require(active, "Established event without active keys")
                log("session_established", session_id=sid, peer_authenticated=True, client_key_confirmed=True)
            if event == 3:
                data = probe(plain)
                if data is None:
                    if writer is None:
                        log("payload_discarded", session_id=sid, reason="no Influx writer")
                        continue
                    try:
                        stored = process_telemetry(plain, packet, received_ns, channel, writer)
                    except (OSError, URLError):
                        # Do not log credential-bearing request objects or response bodies.
                        log("write_failed", session_id=sid, reason="Influx write unconfirmed; no ACK or retry")
                        continue
                    if stored is None:
                        log("payload_discarded", session_id=sid, reason="invalid telemetry schema")
                        continue
                    data, sequence, reply = stored
                    log("telemetry_stored", session_id=sid, counter=sequence, received_ns=received_ns, **data)
                    result = connection.client.publish(DOWN, reply, qos=0, retain=False)
                    require(result.rc == mqtt.MQTT_ERR_SUCCESS, "Cannot queue stored ACK")
                    log("stored_ack_queued", session_id=sid, counter=sequence)
                    continue
                log("payload_accepted", session_id=sid, **data)
                ack = json.dumps({"accepted": True, "run_id": data["run_id"]}, separators=(",", ":")).encode()
                reply = channel.encrypt(ack)
            if reply:
                result = connection.client.publish(DOWN, reply, qos=0, retain=False)
                require(result.rc == mqtt.MQTT_ERR_SUCCESS, "Cannot queue encrypted protocol reply")
                if event == 3:
                    log("encrypted_ack_queued", session_id=sid, run_id=data["run_id"], bytes=len(reply))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(os.environ.get("CREDENTIALS_DIRECTORY", "/nonexistent"))
    parser.add_argument("--mqtt", type=Path, default=base / "mqtt.json")
    parser.add_argument("--identity", type=Path, default=base / "server.identity")
    parser.add_argument("--influx", type=Path)
    args = parser.parse_args()
    serve(args.mqtt, args.identity, args.influx)
