#pragma once
#include <stdint.h>
// A copied latest reading, shared by the legacy and PQC transports.
struct PendingSample {
    uint32_t measuredAtMs;
    char payload[160];
};
