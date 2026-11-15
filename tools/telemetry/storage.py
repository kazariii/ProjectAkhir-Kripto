"""Strict sensor schema and one synchronous Influx point per authenticated reading."""
import json
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FIELDS = {"device_id", "temperature_c", "gas_raw", "gas_alarm", "temperature_alarm"}


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON key")
        result[name] = value
    return result


def parse(plain):
    if not 1 <= len(plain) <= 160:
        return None
    try:
        data = json.loads(plain, object_pairs_hook=unique_object)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or set(data) != FIELDS or data["device_id"] != "esp32-meja01":
        return None
    temperature, gas = data["temperature_c"], data["gas_raw"]
    if (type(temperature) not in (int, float) or not math.isfinite(temperature) or not -55 <= temperature <= 125 or
            type(gas) is not int or not 0 <= gas <= 4095 or
            type(data["gas_alarm"]) is not bool or type(data["temperature_alarm"]) is not bool):
        return None
    # DOUT is independent of ADC. Temperature is rounded for transport; its
    # alarm was computed before rounding. Preserve both authenticated flags.
    return data


def line(data, received_ns):
    # IDs are allowlisted, fields are typed/range checked before this function.
    # Float always has a decimal marker: preserve the existing Influx field type.
    temperature = repr(float(data["temperature_c"]))
    return ("suhu,device_id=esp32-meja01 temperature_c=" + temperature +
            ",gas_raw=" + str(data["gas_raw"]) + "i,gas_alarm=" + str(data["gas_alarm"]).lower() +
            ",temperature_alarm=" + str(data["temperature_alarm"]).lower() + " " + str(received_ns) + "\n").encode()


class Writer:
    def __init__(self, path):
        self.config = json.loads(path.read_text())
        if (self.config.get("url") != "http://127.0.0.1:8086" or self.config.get("org") != "lab-kimia" or
                self.config.get("bucket") != "telemetry" or not self.config.get("token")):
            raise ValueError("Expected local InfluxDB telemetry write credential")
        self.url = self.config["url"] + "/api/v2/write?" + urlencode({"org": self.config["org"],
                    "bucket": self.config["bucket"], "precision": "ns"})

    def write(self, data, received_ns):
        request = Request(self.url, data=line(data, received_ns), method="POST",
                          headers={"Authorization": "Token " + self.config["token"],
                                   "Content-Type": "text/plain; charset=utf-8"})
        # No retry/backlog. Influx must confirm the write before an encrypted ACK.
        with urlopen(request, timeout=2) as response:
            if response.status != 204:
                raise OSError("Influx write was not confirmed")
