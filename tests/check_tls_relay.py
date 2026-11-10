"""Framing regression: fragmented/coalesced TCP, pre-arm pass-through, one bit.

Synthetic records only here; real TLS rejection is tested by check_tls_security.py.
"""
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from tls_relay import TLSRelay


def exact(connection, count):
    result = b""
    while len(result) < count:
        chunk = connection.recv(count - len(result))
        if not chunk:
            raise ConnectionError("Unexpected EOF")
        result += chunk
    return result


def record(body, kind=23):
    return bytes([kind, 3, 3]) + len(body).to_bytes(2, "big") + body


class RelayTest(unittest.TestCase):
    def test_fragmented_and_coalesced_records(self):
        first = record(b"encrypted handshake before arming" * 2)
        target = record(b"publish ciphertext" * 4)
        last = record(b"next record remains intact" * 3)
        response = record(b"server handshake fragments", kind=22)
        received, errors = [], []
        with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(5)

            def broker():
                try:
                    with listener.accept()[0] as connection:
                        connection.settimeout(5)
                        received.append(exact(connection, len(first)))
                        connection.sendall(response[:2])
                        connection.sendall(response[2:6])
                        connection.sendall(response[6:])
                        received.append(exact(connection, len(target) + len(last)))
                except Exception as error:
                    errors.append(error)

            thread = threading.Thread(target=broker, daemon=True)
            thread.start()
            with TLSRelay(listener.getsockname()[1], Path(directory)) as relay:
                with socket.create_connection(("127.0.0.1", relay.port), timeout=5) as client:
                    for fragment in (first[:1], first[1:4], first[4:12], first[12:]):
                        client.sendall(fragment)
                    self.assertEqual(exact(client, len(response)), response)
                    self.assertEqual(received, [first])
                    self.assertFalse(any(e["event"] == "bit_flip" for e in relay.events))
                    relay.arm_after_connack()  # simulated gate; no TLS in this unit test
                    client.sendall(target + last)
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive())
                    self.assertFalse(errors)
                relay.thread.join(timeout=2)
            self.assertFalse(relay.errors)
            changed = received[1]
            expected = target + last
            differences = [(a ^ b).bit_count() for a, b in zip(expected, changed)]
            self.assertEqual(len(changed), len(expected))
            self.assertEqual(sum(differences), 1)
            self.assertEqual(changed[:5], target[:5])
            self.assertEqual(changed[len(target):], last)
            self.assertEqual(len([e for e in relay.events if e["event"] == "bit_flip"]), 1)


if __name__ == "__main__":
    unittest.main()
