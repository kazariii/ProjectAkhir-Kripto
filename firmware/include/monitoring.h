#pragma once

#include <cmath>

// Simulation demonstration setting, not a laboratory safety standard.
constexpr float TEMPERATURE_ALARM_C = 40.0f;

inline bool isValidTemperature(float temperatureC, bool conversionComplete) {
    return conversionComplete && std::isfinite(temperatureC) &&
           temperatureC >= -55.0f && temperatureC <= 125.0f;
}

struct AlarmState {
    bool gas = false;
    bool temperature = false;

    void observeTemperature(float temperatureC, bool conversionComplete) {
        // A failed reading cannot clear a previously observed hot condition.
        if (isValidTemperature(temperatureC, conversionComplete)) {
            temperature = temperatureC >= TEMPERATURE_ALARM_C;
        }
    }

    bool active() const { return gas || temperature; }
};
