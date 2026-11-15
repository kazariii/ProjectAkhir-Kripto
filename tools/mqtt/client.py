"""Shared plain-MQTT connection lifecycle and acknowledged control operations."""
import json
import queue
import secrets
import threading
import paho.mqtt.client as mqtt

class MqttConnection:
    def __init__(self, credentials, prefix="mqtt-check-"):
        self.connected = threading.Event()
        self.condition = threading.Condition()
        self.subacks, self.pubacks = {}, {}
        self.messages = queue.Queue()
        self.code = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=prefix + secrets.token_hex(12), protocol=mqtt.MQTTv5,
                                  reconnect_on_failure=False)
        if credentials.get("username") is not None:
            self.client.username_pw_set(credentials["username"], credentials["password"])
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_publish = self.on_publish
        self.client.on_message = lambda client, data, msg: self.messages.put(msg)
        self.client.connect(credentials["host"], credentials["port"], keepalive=15)
        self.client.loop_start()
        if not self.connected.wait(8):
            self.close()
            raise RuntimeError("MQTT CONNACK timeout")

    def on_connect(self, client, data, flags, reason, properties):
        self.code = reason.value
        self.connected.set()

    def on_subscribe(self, client, data, mid, reasons, properties):
        with self.condition:
            self.subacks[mid] = [reason.value for reason in reasons]
            self.condition.notify_all()

    def on_publish(self, client, data, mid, reason, properties):
        with self.condition:
            self.pubacks[mid] = reason.value
            self.condition.notify_all()

    def wait_ack(self, table, mid):
        with self.condition:
            if not self.condition.wait_for(lambda: mid in table, timeout=5):
                raise RuntimeError("MQTT acknowledgement timeout")
            return table.pop(mid)

    def subscribe(self, topic):
        result, mid = self.client.subscribe(topic, qos=0)
        require(result == mqtt.MQTT_ERR_SUCCESS, "SUBSCRIBE could not be sent")
        return self.wait_ack(self.subacks, mid)

    def publish(self, topic, payload):
        info = self.client.publish(topic, payload, qos=1, retain=False)
        require(info.rc == mqtt.MQTT_ERR_SUCCESS, "PUBLISH could not be sent")
        return self.wait_ack(self.pubacks, info.mid)

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def credentials(path):
    data = json.loads(path.read_text())
    require(data.get("port") == 1883 and data.get("host"), "Expected private TCP/1883 credentials")
    return data


