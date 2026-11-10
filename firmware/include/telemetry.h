#pragma once

#include <cstdio>
#include "monitoring.h"

struct TelemetryMessage {
    bool publish;
    const char* diagnostic;
    char payload[160];
};

// Public sensor-to-message boundary; no network or hardware dependencies.
inline TelemetryMessage makeTelemetry(float temperatureC, bool conversionComplete, int gasRaw,
                                      const AlarmState& alarms) {
    if (!conversionComplete) {
        return {false, "gagal baca DS18B20: konversi belum selesai; tidak dikirim", {0}};
    }
    if (!isValidTemperature(temperatureC, conversionComplete)) {
        return {false, "gagal baca DS18B20: nilai tidak valid; tidak dikirim", {0}};
    }
    if (gasRaw < 0 || gasRaw > 4095) {
        return {false, "gagal baca MQ2: ADC di luar 0-4095; tidak dikirim", {0}};
    }
    TelemetryMessage message = {true, "suhu dan gas valid", {0}};
    std::snprintf(message.payload, sizeof(message.payload),
                  "{\"device_id\":\"esp32-meja01\",\"temperature_c\":%.2f,\"gas_raw\":%d,"
                  "\"gas_alarm\":%s,\"temperature_alarm\":%s}",
                  static_cast<double>(temperatureC), gasRaw,
                  alarms.gas ? "true" : "false", alarms.temperature ? "true" : "false");
    return message;
}
