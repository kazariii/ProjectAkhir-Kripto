"""Boundary tests for authenticated data -> storage -> encrypted acknowledgement."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.telemetry.storage import parse, line, Writer
from tools.session.receiver import process_telemetry

SAMPLE = {"device_id": "esp32-meja01", "temperature_c": 25.0, "gas_raw": 1200,
          "gas_alarm": False, "temperature_alarm": False}


def encode(value):
    return json.dumps(value, separators=(",", ":")).encode()


class StorageTests(unittest.TestCase):
    def test_valid_four_states_and_rounding(self):
        for gas in (False, True):
            for hot in (False, True):
                data = dict(SAMPLE, gas_alarm=gas, temperature_alarm=hot, temperature_c=40.0 if hot else 25.0)
                self.assertEqual(parse(encode(data)), data)
        # Producer computes alarm from unrounded reading, then formats %.2f.
        rounded = dict(SAMPLE, temperature_c=40.0, temperature_alarm=False)
        self.assertEqual(parse(encode(rounded)), rounded)

    def test_invalid_schema_and_types(self):
        cases = [[], {}, dict(SAMPLE, extra="unexpected"), {k: v for k, v in SAMPLE.items() if k != "gas_alarm"}]
        for key, values in {"device_id": ["other", "x\nspoof"], "temperature_c": [True, "25", None, -56, 126, float("nan"), float("inf")],
                            "gas_raw": [True, 1.5, "12", -1, 4096], "gas_alarm": [0, "false", None],
                            "temperature_alarm": [1, "true"]}.items():
            cases += [dict(SAMPLE, **{key: value}) for value in values]
        for value in cases:
            with self.subTest(value=value):
                self.assertIsNone(parse(encode(value)))
        self.assertIsNone(parse(b'{"temperature_c":1,"temperature_c":2}'))
        self.assertIsNone(parse(b'\xff'))
        self.assertIsNone(parse(b' ' * 161))

    def test_one_point_with_existing_field_types(self):
        self.assertEqual(line(SAMPLE, 1234567890123456789),
                         b'suhu,device_id=esp32-meja01 temperature_c=25.0,gas_raw=1200i,gas_alarm=false,temperature_alarm=false 1234567890123456789\n')

    def test_schema_failure_cannot_write_or_ack(self):
        class Forbidden:
            def write(*args):
                raise AssertionError("invalid input reached storage")
            def encrypt(*args):
                raise AssertionError("invalid input got ACK")
        self.assertIsNone(process_telemetry(b'{}', bytes(207), 123, Forbidden(), Forbidden()))

    def test_ack_only_after_write_confirmation(self):
        events = []
        class Channel:
            def encrypt(self, plain):
                events.append(("ACK", json.loads(plain)))
                return b"encrypted"
        class Storage:
            def write(self, data, received_ns):
                events.append(("write", data, received_ns))
        packet = bytearray(207); packet[21:29] = (7).to_bytes(8, "little")
        result = process_telemetry(encode(SAMPLE), packet, 123, Channel(), Storage())
        self.assertEqual(result, (SAMPLE, 7, b"encrypted"))
        self.assertEqual(events, [("write", SAMPLE, 123), ("ACK", {"stored_counter": 7})])

    def test_failed_write_has_no_ack(self):
        class Channel:
            def encrypt(*args):
                raise AssertionError("failed write acknowledged")
        class Storage:
            def write(*args):
                raise OSError("database unavailable")
        with self.assertRaises(OSError):
            process_telemetry(encode(SAMPLE), bytes(207), 123, Channel(), Storage())

    def test_http_requires_204_and_sends_explicit_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "credential.json"
            path.write_text(json.dumps({"url": "http://127.0.0.1:8086", "org": "lab-kimia", "bucket": "telemetry", "token": "test-only"}))
            writer = Writer(path)
            for status in (204, 200, 500):
                with patch("tools.telemetry.storage.urlopen") as request:
                    request.return_value.__enter__.return_value.status = status
                    if status == 204:
                        writer.write(SAMPLE, 456)
                    else:
                        with self.assertRaises(OSError):
                            writer.write(SAMPLE, 456)
                    message = request.call_args[0][0]
                    self.assertIn("precision=ns", message.full_url)
                    self.assertEqual(message.data, line(SAMPLE, 456))
                    self.assertEqual(request.call_args[1]["timeout"], 2)


if __name__ == "__main__":
    unittest.main()
