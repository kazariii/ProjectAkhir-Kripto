#include <cassert>
#include <cstring>
#include <limits>
#include <initializer_list>
#include "telemetry.h"

TelemetryMessage sample(float temperature, bool complete, int gasRaw, bool gasAlarm = false) {
    AlarmState alarms;
    alarms.gas = gasAlarm;
    alarms.observeTemperature(temperature, complete);
    return makeTelemetry(temperature, complete, gasRaw, alarms);
}

int main() {
    const auto message = sample(27.5f, true, 1200);
    assert(message.publish);
    assert(std::strcmp(message.payload,
        "{\"device_id\":\"esp32-meja01\",\"temperature_c\":27.50,\"gas_raw\":1200,\"gas_alarm\":false,\"temperature_alarm\":false}") == 0);
    // Independent changes must preserve the other sensor in the same payload.
    const auto increasedGas = sample(27.5f, true, 3000);
    assert(increasedGas.publish);
    assert(std::strcmp(increasedGas.payload,
        "{\"device_id\":\"esp32-meja01\",\"temperature_c\":27.50,\"gas_raw\":3000,\"gas_alarm\":false,\"temperature_alarm\":false}") == 0);
    const auto increasedTemperature = sample(40.0f, true, 1200);
    assert(increasedTemperature.publish);
    assert(std::strcmp(increasedTemperature.payload,
        "{\"device_id\":\"esp32-meja01\",\"temperature_c\":40.00,\"gas_raw\":1200,\"gas_alarm\":false,\"temperature_alarm\":true}") == 0);
    assert(sample(27.5f, true, 0).publish);
    assert(sample(27.5f, true, 4095).publish);
    const int failedGasReads[] = {-1, 4096};
    for (const int value : failedGasReads) {
        const auto rejected = sample(27.5f, true, value);
        assert(!rejected.publish);
        assert(rejected.payload[0] == '\0');
        assert(rejected.diagnostic[0] != '\0');
    }
    const float failedReads[] = {-127.0f, -55.1f, 125.1f,
        std::numeric_limits<float>::quiet_NaN(),
        std::numeric_limits<float>::infinity()};
    for (const float value : failedReads) {
        const auto rejected = sample(value, true, 1200);
        assert(!rejected.publish);
        assert(rejected.payload[0] == '\0');
        assert(rejected.diagnostic[0] != '\0');
    }
    // 85 C is also the power-on scratchpad value: only a completed conversion
    // makes it a measurement. Real 85 C remains valid after conversion.
    assert(!sample(85.0f, false, 1200).publish);
    assert(sample(85.0f, true, 1200).publish);
    assert(sample(-55.0f, true, 1200).publish);
    assert(sample(125.0f, true, 1200).publish);
    // Four independent conditions; ADC does not decide the digital gas alarm.
    for (const bool gas : {false, true}) {
        for (const bool hot : {false, true}) {
            const auto value = sample(hot ? 40.0f : 39.99f, true, 4095, gas);
            assert(value.publish);
            assert(std::strstr(value.payload, gas ? "\"gas_alarm\":true" : "\"gas_alarm\":false"));
            assert(std::strstr(value.payload, hot ? "\"temperature_alarm\":true" : "\"temperature_alarm\":false"));
            assert(std::strlen(value.payload) < sizeof(value.payload) - 1);
        }
    }
    AlarmState latched;
    latched.observeTemperature(40.0f, true);
    assert(latched.temperature && latched.active());
    for (const float value : failedReads) {
        latched.observeTemperature(value, true);
        assert(latched.temperature && latched.active());
        assert(!makeTelemetry(value, true, 1200, latched).publish);
    }
    latched.observeTemperature(25.0f, false);
    assert(latched.temperature);
    latched.observeTemperature(39.99f, true);
    assert(!latched.temperature && !latched.active());
    latched.gas = true;
    assert(latched.active());
    latched.observeTemperature(25.0f, true);
    assert(latched.active());
    latched.gas = false;
    assert(!latched.active());
    return 0;
}
