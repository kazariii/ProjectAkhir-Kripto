"""Broker settings: private default unchanged, public broker only when declared explicitly."""
import json
from pathlib import Path
import tempfile
import unittest
from tools.mqtt.client import credentials
from tools.session.native import UP, DOWN, TOPIC_PREFIX, topics


def load(data):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "mqtt.json"
        path.write_text(json.dumps(data))
        return credentials(path)


class TopicTests(unittest.TestCase):
    def test_default_topics_unchanged(self):
        self.assertEqual((UP, DOWN), ("lab/kimia/pqc/session/up", "lab/kimia/pqc/session/down"))
        self.assertEqual(topics(TOPIC_PREFIX), (UP, DOWN))

    def test_custom_prefix(self):
        self.assertEqual(topics("lkpqc-demo/session"), ("lkpqc-demo/session/up", "lkpqc-demo/session/down"))

    def test_rejects_wildcards_and_empty(self):
        for prefix in ("", "a/#", "a/+/b", "trailing/"):
            with self.assertRaises(ValueError):
                topics(prefix)


class CredentialTests(unittest.TestCase):
    PRIVATE = {"host": "10.34.211.141", "port": 1883, "username": "diag-device", "password": "x"}

    def test_private_account_accepted(self):
        self.assertEqual(load(self.PRIVATE)["username"], "diag-device")

    def test_missing_account_rejected_unless_public(self):
        with self.assertRaises(RuntimeError):
            load({"host": "broker.emqx.io", "port": 1883})
        with self.assertRaises(RuntimeError):
            load({**self.PRIVATE, "password": None})

    def test_public_declared(self):
        data = load({"host": "broker.emqx.io", "port": 1883, "public": True, "topic_prefix": "lkpqc-demo/session"})
        self.assertTrue(data["public"])

    def test_public_with_account_rejected(self):
        with self.assertRaises(RuntimeError):
            load({**self.PRIVATE, "public": True})

    def test_port_must_be_1883(self):
        with self.assertRaises(RuntimeError):
            load({**self.PRIVATE, "port": 8883})


if __name__ == "__main__":
    unittest.main()
