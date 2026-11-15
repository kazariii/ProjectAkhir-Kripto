"""Synthetic evidence controls: they test the gate, not Wokwi acceptance itself."""
import json
import unittest
from tools.telemetry.verify_capture import serial, match


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.sid = "a" * 32
        self.run = {"run_id": "b"*32, "local_ip": "10.13.37.2"}
        rows = ["TELEMETRY_BEGIN ticket=04", "TELEMETRY_RUN " + json.dumps(self.run),
                "TELEMETRY_AUTHENTICATED " + json.dumps({"run_id": self.run["run_id"], "session_id": self.sid, "mqtt_port": 1883, "tls": False})]
        self.events = [{"event": "session_established", "session_id": self.sid, "peer_authenticated": True, "client_key_confirmed": True}]
        for i, (ga, ta) in enumerate(((False, False), (False, True), (True, True), (True, False)), 1):
            data = {"device_id": "esp32-meja01", "temperature_c": 45.0 if ta else 25.0, "gas_raw": 3000 if ga else 1200,
                    "gas_alarm": ga, "temperature_alarm": ta}
            rows += ["Sampel lokal ms=%d %s" % (i*2000, json.dumps(data)),
                     "TELEMETRY_SENT " + json.dumps({"session_id": self.sid, "counter": i, "measured_ms": i*2000}),
                     "TELEMETRY_STORED " + json.dumps({"session_id": self.sid, "counter": i, "ack_verified": True})]
            self.events += [{"event": "telemetry_stored", "session_id": self.sid, "counter": i, **data},
                            {"event": "stored_ack_queued", "session_id": self.sid, "counter": i}]
        self.text = "\n".join(rows)
        self.broker = "New client connected from private as esp32-telemetry-" + self.run["run_id"][:12] + " (u'diag-device')."

    def test_complete_synthetic_control(self):
        run, samples = serial(self.text)
        self.assertEqual(len(match(run, samples, self.events, self.broker)[1]), 4)

    def test_native_broker_cannot_prove_esp32(self):
        run, samples = serial(self.text)
        with self.assertRaises(RuntimeError):
            match(run, samples, self.events, self.broker.replace("esp32-telemetry-", "native-telemetry-"))

    def test_duplicate_incomplete_and_failed_runs(self):
        for text in (self.text+self.text, self.text.split("TELEMETRY_STORED")[0],
                     self.text+"\nGuru Meditation", self.text+"\nLEDC is not initialized", self.text.replace('"ack_verified": true', '"ack_verified": false'),
                     self.text.replace("Sampel lokal", "missing sample")):
            with self.subTest(text=text[-60:]), self.assertRaises((RuntimeError, ValueError)):
                serial(text)

    def test_receiver_must_match_sample_and_ack(self):
        run, samples = serial(self.text)
        for events in (self.events[:-1], [dict(e, temperature_c=99) if e["event"] == "telemetry_stored" else e for e in self.events]):
            with self.assertRaises(RuntimeError):
                match(run, samples, events, self.broker)

    def test_fault_mode_only_allows_expected_connection_failures(self):
        text = self.text+"\nTELEMETRY_CONNECT_FAILED state=-2"
        with self.assertRaises(RuntimeError):
            serial(text)
        self.assertEqual(len(serial(text, fault_test=True)[1]), 4)
        with self.assertRaises(RuntimeError):
            serial(text+"\nGuru Meditation", fault_test=True)


if __name__ == "__main__":
    unittest.main()
