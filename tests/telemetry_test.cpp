#include <cassert>
#include <cstring>
#include <limits>
#include "telemetry.h"

int main() {
    const auto message = makeTelemetry(27.5f, true);
    assert(message.publish);
    assert(std::strcmp(message.payload,
        "{\"device_id\":\"esp32-meja01\",\"temperature_c\":27.50}") == 0);
    const float failedReads[] = {-127.0f, -55.1f, 125.1f,
        std::numeric_limits<float>::quiet_NaN(),
        std::numeric_limits<float>::infinity()};
    for (const float value : failedReads) {
        const auto rejected = makeTelemetry(value, true);
        assert(!rejected.publish);
        assert(rejected.payload[0] == '\0');
        assert(rejected.diagnostic[0] != '\0');
    }
    // 85 C is also the power-on scratchpad value: only a completed conversion
    // makes it a measurement. Real 85 C remains valid after conversion.
    assert(!makeTelemetry(85.0f, false).publish);
    assert(makeTelemetry(85.0f, true).publish);
    assert(makeTelemetry(-55.0f, true).publish);
    assert(makeTelemetry(125.0f, true).publish);
    return 0;
}
