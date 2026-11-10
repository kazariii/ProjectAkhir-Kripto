"""Run the real firmware loop with a controlled clock and hardware boundaries.

The sensor fixture models the pinned DallasTemperature request timestamp AFTER
the OneWire command. This is a host regression test, not a Wokwi/TLS demo.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


BOUNDARIES = r'''
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <string>
#include <vector>
#include <cmath>
#include <cstring>
#include <functional>
static uint32_t clockMs = 1000;
static bool sensorOnBus = true;
static uint32_t conversionDurationMs = 750;
static float sensorTemperature = 25.0f;
static bool mqttOnline = true;
static bool brokerAvailable = true, wifiOnline = true, publishOk = true;
static int connectCalls = 0, wifiRetries = 0;
static std::function<void()> duringConnect;
static int gasDigital = 1;
static bool ledOn = false, buzzerOn = false;
static std::vector<std::string> logs, published;
uint32_t millis() { return clockMs; }
void delay(unsigned int ms) { clockMs += ms; }
struct SerialPort {
    void begin(int) {}
    void println(const char* value) { logs.push_back(value); }
    void printf(const char* format, ...) {
        char buffer[512]; va_list args; va_start(args, format);
        vsnprintf(buffer, sizeof(buffer), format, args); va_end(args);
        logs.push_back(buffer);
    }
} Serial;
enum { WL_CONNECTED = 3, WIFI_STA = 1, INPUT = 0, OUTPUT = 1, ADC_11db = 3, LOW = 0, HIGH = 1 };
void pinMode(int, int) {}
void digitalWrite(int pin, int value) { assert(pin == 25); ledOn = value == HIGH; }
void tone(int pin, int frequency) { assert(pin == 26 && frequency == 2000); buzzerOn = true; }
void noTone(int pin) { assert(pin == 26); buzzerOn = false; }
int analogRead(int) { return 1200; }
int digitalRead(int pin) { assert(pin == 27); return gasDigital; }
void analogReadResolution(int) {}
void analogSetPinAttenuation(int, int) {}
void configTime(int, int, const char*, const char*) {}
struct Wifi {
    int status() { return wifiOnline ? WL_CONNECTED : 0; }
    void mode(int) {}
    void begin(const char*, const char*, int) {}
    void reconnect() { ++wifiRetries; }
} WiFi;
struct WiFiClientSecure {
    void setCACert(const char* ca) { assert(std::strcmp(ca, "test") == 0); }
    void setHandshakeTimeout(int) {}
    int lastError(char* buffer, size_t size) {
        snprintf(buffer, size, "fixture TLS failure"); return -123;
    }
};
struct PubSubClient {
    explicit PubSubClient(WiFiClientSecure&) {}
    bool connected() { return mqttOnline; }
    bool loop() { return mqttOnline; }
    bool connect(const char* id, const char* user, const char* password) {
        assert(std::strcmp(id, "esp32-meja01") == 0);
        assert(std::strcmp(user, "test") == 0 && std::strcmp(password, "test") == 0);
        ++connectCalls;
        if (duringConnect) duringConnect();
        mqttOnline = brokerAvailable;
        return mqttOnline;
    }
    void disconnect() { mqttOnline = false; }
    int state() { return 0; }
    void setServer(const char* host, int port) { assert(std::strcmp(host, "test.invalid") == 0 && port == 8883); }
    void setSocketTimeout(int) {}
    void setBufferSize(int) {}
    bool publish(const char*, const char* payload, bool retained) {
        assert(!retained);
        if (publishOk) published.push_back(payload);
        return publishOk;
    }
};
struct OneWire {
    explicit OneWire(int) {}
    int reset() { ++clockMs; return sensorOnBus; }
};
struct DallasTemperature {
    struct request_t { bool result; unsigned long timestamp; };
    uint32_t requestedAt = 0;
    explicit DallasTemperature(OneWire*) {}
    void begin() {}
    void setResolution(int) {}
    void setWaitForConversion(bool) {}
    request_t requestTemperatures() {
        // Sending the OneWire command takes time before conversion starts.
        clockMs += 2; requestedAt = clockMs;
        return {true, requestedAt};
    }
    bool isConversionComplete() {
        return uint32_t(clockMs - requestedAt) >= conversionDurationMs;
    }
    float getTempCByIndex(int) { return sensorOnBus ? sensorTemperature : -127.0f; }
};
// Controlled scheduler: queue operations copy like FreeRTOS. A connect hook
// advances the sensor task while the network task is suspended in its socket.
struct TestQueue { std::vector<char> bytes; size_t itemSize; bool full = false; };
using QueueHandle_t = TestQueue*;
constexpr int pdTRUE = 1, pdPASS = 1;
static bool queueFails = false, taskFails = false;
static void (*createdTask)(void*) = nullptr;
QueueHandle_t xQueueCreate(int length, size_t size) {
    assert(length == 1);
    if (queueFails) return nullptr;
    auto q = new TestQueue; q->itemSize = size; q->bytes.resize(size); return q;
}
int xQueueReset(QueueHandle_t q) { q->full = false; return pdPASS; }
int xQueueOverwrite(QueueHandle_t q, const void* data) {
    std::memcpy(q->bytes.data(), data, q->itemSize); q->full = true; return pdPASS;
}
int xQueueReceive(QueueHandle_t q, void* data, int timeout) {
    assert(timeout == 0);
    if (!q->full) return 0;
    std::memcpy(data, q->bytes.data(), q->itemSize); q->full = false; return pdTRUE;
}
void vQueueDelete(QueueHandle_t q) { delete q; }
int xTaskCreatePinnedToCore(void (*fn)(void*), const char*, int stack, void*, int, void*, int core) {
    assert(stack >= 8192 && core == 0); createdTask = fn; return taskFails ? 0 : pdPASS;
}
int pdMS_TO_TICKS(int ms) { return ms; }
void vTaskDelay(int) { throw 1; }
'''

SCENARIO = r'''
#include <cassert>
#include <iostream>
#include "FIRMWARE_SOURCE"
void cycle() {
    loop();
    if (configured && outgoing) networkStep();
}
void reconnectScenario() {
    initializeNetwork();
    cycle(); clockMs = 1754; cycle();
    assert(published.size() == 1);
    mqttOnline = false; brokerAvailable = false;
    // A blocked DNS/TCP/TLS/MQTT operation lasts 20 simulated seconds while
    // the real loop still samples every two seconds and drives local outputs.
    const size_t before = published.size();
    duringConnect = [] {
        for (int n = 1; n <= 10; ++n) {
            sensorTemperature = n >= 3 ? 40.0f : 25.0f;
            gasDigital = n == 2 ? LOW : HIGH;
            clockMs = 1000 + n * 2000;
            loop();
            assert(sampleStartMs == clockMs - 4);
            clockMs = 1754 + n * 2000;
            loop();
            assert(alarms.gas == (n == 2));
            assert(alarms.temperature == (n >= 3));
            assert(ledOn == (n >= 2) && buzzerOn == ledOn);
        }
    };
    networkStep();
    assert(connectCalls == 1 && published.size() == before && !outgoing->full);
    duringConnect = nullptr;
    // Retry interval is respected, including across millis() rollover.
    clockMs = lastMqttAttemptMs + 4999; networkStep(); assert(connectCalls == 1);
    clockMs = 23000; networkStep(); assert(connectCalls == 2);
    brokerAvailable = true;
    clockMs = 28000; networkStep(); assert(mqttOnline && connectCalls == 3);
    networkStep(); assert(published.size() == before); // no offline replay
    sensorTemperature = 25; clockMs = 30000; cycle(); clockMs = 30754; cycle();
    assert(published.size() == before + 1 && !alarms.active());
    // Expired/failed samples cannot be retried or relabelled as fresh.
    PendingSample expired = {}; expired.measuredAtMs = clockMs - SAMPLE_INTERVAL_MS;
    xQueueOverwrite(outgoing, &expired); networkStep(); assert(published.size() == before + 1);
    publishOk = false; clockMs = 32000; cycle(); clockMs = 32754; cycle();
    publishOk = true; networkStep(); assert(published.size() == before + 1);
    // Wi-Fi failure/reassociation stays entirely on the network side.
    wifiOnline = false; networkStep(); assert(wifiRetries == 1 && !mqttOnline);
    networkStep(); assert(wifiRetries == 1);
    clockMs += 5000; networkStep(); assert(wifiRetries == 2);
    wifiOnline = true; clockMs += 5000; networkStep(); assert(mqttOnline);
    lastMqttAttemptMs = UINT32_MAX - 1000; attemptedMqtt = true; mqttOnline = false;
    clockMs = 3998; const int calls = connectCalls; networkStep(); assert(connectCalls == calls);
    clockMs = 3999; networkStep(); assert(connectCalls == calls + 1);
    std::cout << "PASS: blocked reconnect preserves sensor cadence and local alarms; Wi-Fi/MQTT recover with same TLS/auth; no replay, expiry, failed publish, retry/rollover\n";
}
int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "queue-failure") queueFails = true;
    if (argc > 1 && std::string(argv[1]) == "task-failure") taskFails = true;
    setup();
    if (queueFails || taskFails) {
        assert(!outgoing);
        gasDigital = LOW; loop(); assert(ledOn && buzzerOn);
        std::cout << "PASS: network allocation failure preserves local alarm\n";
        return 0;
    }
    assert(createdTask == networkTask);
    if (argc > 1 && std::string(argv[1]) == "reconnect") { reconnectScenario(); return 0; }
    // The device may still report busy at the first whole-millisecond check.
    if (argc > 1) conversionDurationMs = 751;
    if (argc > 2) {
        conversionDurationMs = 100000;
        configured = true;
        cycle();
        clockMs = 1753; cycle();
        assert(published.empty());
        clockMs = 3003; cycle();
        assert(published.empty());
        bool timeoutReported = false;
        for (const auto& log : logs) {
            if (log.find("konversi belum selesai") != std::string::npos) timeoutReported = true;
        }
        assert(timeoutReported);
        std::cout << "PASS: stuck conversion times out without publishing a fake temperature\n";
        return 0;
    }
    configured = true;
    cycle();                       // sample starts at 1000; command ends at 1003
    clockMs = 1750; cycle();        // 750 since sample, only 747 since command
    clockMs = 1753; cycle();        // complete 750 ms conversion
    clockMs = 1754; cycle();        // retry if the completion bit was still busy
    if (published.size() != 1) {
        for (const auto& log : logs) std::cerr << log << '\n';
        std::cerr << "FAIL: a completed conversion did not produce telemetry\n";
        return 1;
    }
    assert(published[0] == "{\"device_id\":\"esp32-meja01\",\"temperature_c\":25.00,\"gas_raw\":1200,\"gas_alarm\":false,\"temperature_alarm\":false}");
    clockMs = 3000; cycle();        // next sample still starts at 2 seconds
    clockMs = 3754; cycle();
    assert(published.size() == 2);
    sensorOnBus = false;
    clockMs = 5000; cycle();
    clockMs = 5753; cycle();
    assert(published.size() == 2); // disconnection cannot produce normal data
    bool missingReported = false;
    for (const auto& log : logs) {
        if (log.find("sensor tidak terdeteksi") != std::string::npos) missingReported = true;
    }
    assert(missingReported);
    // A failed/missing temperature cannot prevent a gas-only local alarm.
    gasDigital = LOW;
    cycle();
    assert(alarms.gas && ledOn && buzzerOn);
    gasDigital = HIGH;
    cycle();
    assert(!alarms.active() && !ledOn && !buzzerOn);

    // Exercise all four states in the real loop, including threshold equality.
    sensorOnBus = true;
    sensorTemperature = 40.0f;
    clockMs = 7000; cycle();
    clockMs = 7754; cycle();
    assert(!alarms.gas && alarms.temperature && ledOn && buzzerOn);
    assert(published.back().find("\"temperature_alarm\":true") != std::string::npos);
    gasDigital = LOW;
    clockMs = 9000; cycle();
    clockMs = 9754; cycle();
    assert(alarms.gas && alarms.temperature && ledOn && buzzerOn);
    assert(published.back().find("\"gas_alarm\":true") != std::string::npos);
    assert(published.back().find("\"temperature_alarm\":true") != std::string::npos);

    // Sensor failure after a hot reading must latch the temperature alarm.
    const auto beforeFailure = published.size();
    sensorOnBus = false;
    gasDigital = HIGH;
    clockMs = 11000; cycle();
    assert(!alarms.gas && alarms.temperature && ledOn && buzzerOn);
    assert(published.size() == beforeFailure);
    sensorOnBus = true;
    sensorTemperature = NAN;
    clockMs = 13000; cycle();
    clockMs = 13754; cycle();
    assert(alarms.temperature && ledOn && buzzerOn);
    assert(published.size() == beforeFailure);
    sensorTemperature = 39.99f;
    clockMs = 15000; cycle();
    clockMs = 15754; cycle();
    assert(!alarms.active() && !ledOn && !buzzerOn);
    assert(published.back().find("\"temperature_alarm\":false") != std::string::npos);

    gasDigital = LOW;
    clockMs = 17000; cycle();
    clockMs = 17754; cycle();
    assert(alarms.gas && !alarms.temperature && ledOn && buzzerOn);
    assert(published.back().find("\"gas_alarm\":true") != std::string::npos);
    assert(published.back().find("\"temperature_alarm\":false") != std::string::npos);

    // No broker and no credentials: local sensing/output still works.
    mqttOnline = false;
    configured = false;
    gasDigital = HIGH;
    sensorTemperature = 41.0f;
    clockMs = 19000; cycle();
    clockMs = 19754; cycle();
    assert(!alarms.gas && alarms.temperature && ledOn && buzzerOn);
    sensorTemperature = 25.0f;
    clockMs = 21000; cycle();
    clockMs = 21754; cycle();
    assert(!alarms.active() && !ledOn && !buzzerOn);
    std::cout << "PASS: independent gas/temperature, four states, LED/buzzer, invalid-reading latch, valid recovery, local operation without MQTT/config\n";
    std::cout << "PASS: actual firmware loop waits for command completion, keeps 2s cadence, rejects disconnected sensor\n";
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default=str(Path.home() / '.platformio/packages/toolchain-gccmingw32/bin/g++.exe'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    compiler = Path(args.compiler).resolve()
    env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get('PATH', ''))
    with tempfile.TemporaryDirectory(prefix='firmware-cycle-') as directory:
        fixture = Path(directory)
        (fixture / 'boundaries.h').write_text(BOUNDARIES, encoding='utf-8')
        (fixture / 'freertos').mkdir()
        for header in ('freertos/FreeRTOS.h', 'freertos/queue.h', 'freertos/task.h', 'Arduino.h', 'WiFi.h', 'WiFiClientSecure.h', 'PubSubClient.h', 'OneWire.h', 'DallasTemperature.h'):
            (fixture / header).write_text('#include "boundaries.h"\n', encoding='utf-8')
        # Never compile the owner's secrets into the test executable.
        (fixture / 'secrets.h').write_text(
            'constexpr char WIFI_SSID[]="test", WIFI_PASSWORD[]="", MQTT_HOST[]="test.invalid", '
            'MQTT_USERNAME[]="test", MQTT_PASSWORD[]="test", MQTT_ROOT_CA[]="test";\n', encoding='utf-8')
        source = fixture / 'scenario.cpp'
        source.write_text(SCENARIO.replace('FIRMWARE_SOURCE', (root / 'firmware/src/main.cpp').as_posix()), encoding='utf-8')
        executable = fixture / 'scenario.exe'
        subprocess.run([str(compiler), '-std=c++11', '-I' + str(fixture),
                        '-I' + str(root / 'firmware/include'), str(source), '-o', str(executable)],
                       check=True, env=env)
        for scenario in ([], ['completion-bit-next-tick'], ['stuck', 'conversion'], ['reconnect'], ['queue-failure'], ['task-failure']):
            subprocess.run([str(executable)] + scenario, check=True, env=env)


if __name__ == '__main__':
    main()
