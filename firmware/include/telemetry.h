#pragma once

#include <cstdio>
#include <cmath>

struct TelemetryMessage {
    bool publish;
    const char* diagnostic;
    char payload[96];
};

// Public sensor-to-message boundary; no network or hardware dependencies.
inline TelemetryMessage makeTelemetry(float temperatureC, bool conversionComplete) {
    if (!conversionComplete) {
        return {false, "gagal baca DS18B20: konversi belum selesai; tidak dikirim", {0}};
    }
    if (!std::isfinite(temperatureC) || temperatureC < -55.0f || temperatureC > 125.0f) {
        return {false, "gagal baca DS18B20: nilai tidak valid; tidak dikirim", {0}};
    }
    TelemetryMessage message = {true, "suhu valid", {0}};
    std::snprintf(message.payload, sizeof(message.payload),
                  "{\"device_id\":\"esp32-meja01\",\"temperature_c\":%.2f}",
                  static_cast<double>(temperatureC));
    return message;
}
