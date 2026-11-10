"""One-connection, loopback-only TCP relay for the ticket-06 experiment.

No TLS endpoint or keys here. Frame complete TLS records across arbitrary TCP
chunks, then flip one body bit only when the test client explicitly arms it.
"""
from datetime import datetime, timezone
import hashlib
import select
import socket
import threading


def stamp():
    return datetime.now(timezone.utc).isoformat()


class TLSRelay:
    def __init__(self, broker_port, directory):
        self.broker_port = broker_port
        self.directory = directory
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.armed = threading.Event()
        self.stopping = threading.Event()
        self.events = []
        self.errors = []
        self.thread = threading.Thread(target=self.forward, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def arm_after_connack(self):
        self.events.append({"event": "armed_after_connack", "utc": stamp()})
        self.armed.set()

    def forward(self):
        sockets = []
        try:
            while not self.stopping.is_set():
                try:
                    client, _ = self.listener.accept()
                    break
                except socket.timeout:
                    continue
            else:
                return
            sockets.append(client)
            broker = socket.create_connection(("127.0.0.1", self.broker_port), timeout=10)
            client.settimeout(10)
            sockets.append(broker)
            peers = {client: broker, broker: client}
            buffers = {client: bytearray(), broker: bytearray()}
            counts = {client: 0, broker: 0}
            active = list(sockets)
            with (self.directory / "client-original.tls").open("wb") as original, \
                    (self.directory / "client-forwarded.tls").open("wb") as forwarded:
                while active and not self.stopping.is_set():
                    readable, _, _ = select.select(active, [], [], 0.1)
                    for source in readable:
                        chunk = source.recv(65536)
                        if not chunk:
                            if buffers[source]:
                                raise ValueError("Truncated TLS record at EOF")
                            active.remove(source)
                            peers[source].shutdown(socket.SHUT_WR)
                            self.events.append({"event": "tcp_eof", "utc": stamp(),
                                                "direction": "client" if source is client else "broker"})
                            continue
                        buffer = buffers[source]
                        buffer.extend(chunk)
                        while len(buffer) >= 5:
                            length = int.from_bytes(buffer[3:5], "big")
                            if length > 18432:
                                raise ValueError("TLS record exceeds experiment bound")
                            if len(buffer) < length + 5:
                                break
                            record = bytes(buffer[:length + 5])
                            del buffer[:length + 5]
                            counts[source] += 1
                            changed = record
                            if source is client:
                                original.write(record)
                                # CONNACK was decrypted by the client before arming.
                                # No client writes occur between arming and PUBLISH.
                                if self.armed.is_set() and not any(e["event"] == "bit_flip" for e in self.events):
                                    if record[0] != 23 or length < 32:
                                        raise ValueError("Expected protected application record after CONNACK")
                                    offset = 5 + length // 2
                                    changed = record[:offset] + bytes([record[offset] ^ 1]) + record[offset + 1:]
                                    self.events.append({"event": "bit_flip", "utc": stamp(),
                                                        "client_record": counts[source], "body_offset": offset - 5,
                                                        "header_before": record[:5].hex(), "header_after": changed[:5].hex(),
                                                        "record_bytes_before": len(record), "record_bytes_after": len(changed),
                                                        "byte_before": record[offset], "byte_after": changed[offset],
                                                        "xor_mask": 1,
                                                        "sha256_before": hashlib.sha256(record).hexdigest(),
                                                        "sha256_after": hashlib.sha256(changed).hexdigest()})
                                forwarded.write(changed)
                            peers[source].sendall(changed)
        except Exception as error:
            self.errors.append(type(error).__name__)
        finally:
            for connection in sockets:
                connection.close()

    def __exit__(self, *args):
        self.stopping.set()
        self.thread.join(timeout=12)
        self.listener.close()
        if self.thread.is_alive():
            raise RuntimeError("Relay did not stop")
