#pragma once
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
namespace pqc_telemetry {
// Sensor code owns the one-entry latest-reading queue. Transport only consumes
// copied readings; it never reads hardware or changes alarm state.
bool start(QueueHandle_t latest_reading);
}
