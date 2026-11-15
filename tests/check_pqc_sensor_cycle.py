"""Run the actual sensor/alarm loop selected by PQC_TELEMETRY with a held transport."""
from pathlib import Path
import subprocess
import tempfile
from tests.check_firmware_cycle import BOUNDARIES

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = r'''
#include <cassert>
#include <iostream>
#include "FIRMWARE"
int main(int argc, char**) {
    pqcStartFails = argc > 1;
    setup();
    assert(pqcStartCalled);
    if (pqcStartFails) {
        assert(!outgoing);
        gasDigital = LOW; loop(); assert(ledOn && buzzerOn);
        std::cout << "PASS: PQC startup failure preserves local alarm\n";
        return 0;
    }
    assert(outgoing == pqcQueue);
    // Hold the transport for six 2s cycles, longer than ESP32 FN-DSA sign.
    // The real main.cpp loop continues overwriting one latest reading.
    for (int i=0; i<6; ++i) {
        clockMs = 1000 + i*2000; sensorTemperature = i >= 2 ? 45 : 25;
        gasDigital = i % 2 ? LOW : HIGH;
        loop(); assert(sampleStartMs == uint32_t(1000+i*2000));
        clockMs = 1754+i*2000; loop();
        assert(alarms.gas == bool(i%2) && alarms.temperature == (i>=2));
        assert(ledOn == alarms.active() && buzzerOn == ledOn);
        assert(outgoing->full && outgoing->itemSize == sizeof(PendingSample));
        PendingSample sample; std::memcpy(&sample, outgoing->bytes.data(), sizeof(sample));
        assert(sample.measuredAtMs == clockMs-1);
        assert(std::strstr(sample.payload, "\"gas_raw\":1200"));
        assert(std::strstr(sample.payload, i%2 ? "\"gas_alarm\":true" : "\"gas_alarm\":false"));
    }
    // Invalid temperature cannot clear the hot alarm, gas stays independent.
    sensorOnBus = false; gasDigital = HIGH; clockMs=13000; loop();
    assert(alarms.temperature && !alarms.gas && ledOn);
    sensorOnBus = true; sensorTemperature=25; clockMs=15000; loop(); clockMs=15754; loop();
    assert(!alarms.active() && !ledOn && !buzzerOn);
    std::cout << "PASS: PQC selection shares actual sensor loop, all four alarm states, 2s cadence, latest-only readings, invalid latch/recovery\n";
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix="pqc-sensors-") as folder:
        fixture = Path(folder)
        (fixture / "boundaries.h").write_text(BOUNDARIES)
        (fixture / "freertos").mkdir()
        for header in ("Arduino.h", "WiFi.h", "OneWire.h", "DallasTemperature.h", "freertos/FreeRTOS.h", "freertos/queue.h", "freertos/task.h"):
            (fixture / header).write_text('#include "boundaries.h"\n')
        (fixture / "pqc_telemetry.h").write_text('''#pragma once
#include "boundaries.h"
static bool pqcStartCalled=false, pqcStartFails=false;
static QueueHandle_t pqcQueue=nullptr;
namespace pqc_telemetry { bool start(QueueHandle_t queue) {
    pqcStartCalled=true; pqcQueue=queue; return !pqcStartFails;
} }
''')
        (fixture / "scenario.cpp").write_text(SCENARIO.replace("FIRMWARE", (ROOT / "firmware/src/main.cpp").as_posix()))
        program = fixture / "sensor-test"
        subprocess.run(["g++", "-std=c++11", "-DPQC_TELEMETRY", "-I"+str(fixture),
                        "-I"+str(ROOT / "firmware/include"), str(fixture / "scenario.cpp"), "-o", str(program)], check=True)
        subprocess.run([str(program)], check=True)
        subprocess.run([str(program), "startup-failure"], check=True)


if __name__ == "__main__":
    main()
