"""Small synchronous MQTT 5 probe, not an application client.

CONNECT, one-filter SUBSCRIBE and QoS 1 PUBLISH for controlled MQTT tests.
No reconnect, retries, retained publishing, persistent sessions or secret logging.
Wire layout: https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html
"""
import socket
import struct


def mqtt_string(value):
    raw = value.encode("utf-8")
    return struct.pack("!H", len(raw)) + raw


def variable_integer(value):
    if not 0 <= value <= 268435455:
        raise ValueError("Invalid MQTT variable integer")
    encoded = bytearray()
    while True:
        encoded.append(value % 128 | (128 if value >= 128 else 0))
        value //= 128
        if not value:
            return bytes(encoded)


def read_integer(data, offset):
    value = 0
    for index in range(4):
        byte = data[offset + index]
        value += (byte & 127) << (7 * index)
        if not byte & 128:
            return value, offset + index + 1
    raise ValueError("Invalid MQTT variable integer")


class Probe:
    def __init__(self, host, port, context):
        tcp = socket.create_connection((host, port), timeout=10)
        try:
            # Plain TCP is only for the isolated ticket-06 comparison broker.
            self.connection = context.wrap_socket(tcp, server_hostname=host) if context is not None else tcp
        except BaseException:
            tcp.close()
            raise
        self.packet_id = 0
        self.connected = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            if self.connected:
                self.send(0xE0, b"")
        except OSError:
            pass
        finally:
            self.connection.close()

    def send(self, header, body):
        self.connection.sendall(bytes([header]) + variable_integer(len(body)) + body)

    def exact(self, count):
        result = bytearray()
        while len(result) < count:
            chunk = self.connection.recv(count - len(result))
            if not chunk:
                raise ConnectionError("MQTT connection closed without expected response")
            result.extend(chunk)
        return bytes(result)

    def receive(self):
        header = self.exact(1)[0]
        encoded = bytearray()
        for _ in range(4):
            encoded.extend(self.exact(1))
            if not encoded[-1] & 128:
                size, _ = read_integer(encoded, 0)
                if size > 65536:
                    raise ValueError("Unexpectedly large probe response")
                return header, self.exact(size)
        raise ValueError("Invalid MQTT remaining length")

    def connect(self, client_id, username=None, password=None):
        flags = 0x02  # Clean Start; default Session Expiry = 0; no Will.
        credentials = b""
        if username is not None:
            flags |= 0xC0
            credentials = mqtt_string(username) + mqtt_string(password)
        # Protocol name/version, flags, 60s keepalive, empty properties, payload.
        self.send(0x10, b"\x00\x04MQTT\x05" + bytes([flags]) + b"\x00\x3c\x00"
                  + mqtt_string(client_id) + credentials)
        header, body = self.receive()
        if header != 0x20 or len(body) < 3 or body[0] != 0:
            raise ValueError("Expected clean CONNACK")
        size, start = read_integer(body, 2)
        if start + size != len(body):
            raise ValueError("Invalid CONNACK properties")
        self.connected = body[1] == 0
        return body[1]

    def next_id(self):
        self.packet_id = self.packet_id % 65535 + 1
        return struct.pack("!H", self.packet_id)

    def acknowledgement(self, kind, packet_id):
        header, body = self.receive()
        if header != kind or body[:2] != packet_id:
            raise ValueError("Unexpected MQTT acknowledgement")
        return body

    def subscribe(self, topic):
        packet_id = self.next_id()
        # QoS 0 subscription; retain handling 2: never deliver retained data.
        self.send(0x82, packet_id + b"\x00" + mqtt_string(topic) + b"\x20")
        body = self.acknowledgement(0x90, packet_id)
        size, start = read_integer(body, 2)
        codes = body[start + size:]
        if len(codes) != 1:
            raise ValueError("Expected one SUBACK reason code")
        return codes[0]

    def publish(self, topic, payload):
        packet_id = self.next_id()
        # QoS 1, DUP=0, RETAIN=0; exactly one attempt.
        self.send(0x32, mqtt_string(topic) + packet_id + b"\x00" + payload)
        body = self.acknowledgement(0x40, packet_id)
        if len(body) < 2:
            raise ValueError("Truncated PUBACK")
        return body[2] if len(body) >= 3 else 0

    def message(self):
        header, body = self.receive()
        if header >> 4 != 3 or (header >> 1) & 3 != 0:
            raise ValueError("Expected QoS 0 PUBLISH")
        size = struct.unpack("!H", body[:2])[0]
        topic = body[2:2 + size].decode("utf-8")
        offset = 2 + size
        size, offset = read_integer(body, offset)
        return topic, body[offset + size:]
