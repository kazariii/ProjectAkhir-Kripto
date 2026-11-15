#include <Arduino.h>
#include <WiFi.h>
#include <esp_timer.h>
#include <esp_heap_caps.h>
#include "pqc_proof.h"
#include "pqc_fixture.h"
#include <cstring>

namespace {
constexpr char MESSAGE[] = "{\"device_id\":\"pqc-proof-only\",\"temperature_c\":26.25,\"gas_raw\":321,\"gas_alarm\":false,\"temperature_alarm\":false}";
pqc::Challenge challenge;
pqc::Response response;
void proofTask(void*) {
    Serial.println("PQC_BEGIN prospective-FN-DSA-512 ML-KEM-512 ChaCha20-Poly1305");
    const size_t before = ESP.getFreeHeap();
    memcpy(&challenge,PROOF_CHALLENGE,sizeof(challenge));
    pqc::Metrics metrics;
    const int64_t start = esp_timer_get_time();
    const bool aead_ok = pqc::aead_self_test();
    const bool ok = aead_ok && pqc::respond(challenge,PROOF_SERVER_PUBLIC,PROOF_DEVICE_SECRET,
        reinterpret_cast<const uint8_t*>(MESSAGE),strlen(MESSAGE),response,metrics);
    Serial.printf("PQC_METRICS {\"target\":\"esp32\",\"passed\":%s,\"aead_rfc8439\":%s,\"server_verify_us\":%llu,\"encapsulate_us\":%llu,\"sign_us\":%llu,\"encrypt_us\":%llu,\"total_us\":%llu,\"heap_before\":%u,\"heap_after\":%u,\"minimum_heap\":%u,\"task_stack_free_bytes\":%u,\"response_bytes\":%u}\n",
        ok?"true":"false",aead_ok?"true":"false",metrics.server_verify_us,metrics.encapsulate_us,
        metrics.sign_us,metrics.encrypt_us,static_cast<uint64_t>(esp_timer_get_time()-start),
        unsigned(before),unsigned(ESP.getFreeHeap()),unsigned(ESP.getMinFreeHeap()),
        unsigned(uxTaskGetStackHighWaterMark(nullptr)),unsigned(sizeof(response)));
    if (ok) {
        Serial.print("PQC_RESPONSE ");
        const auto* p = reinterpret_cast<const uint8_t*>(&response);
        for (size_t i=0;i<sizeof(response);++i) Serial.printf("%02x",p[i]);
        Serial.println();
        Serial.println("PQC_DONE");
    } else Serial.println("PQC_FAILED");
    vTaskDelete(nullptr);
}
}
void setup() {
    Serial.begin(115200);
    // Enable radio entropy before using esp_fill_random. No MQTT or TLS connection.
    WiFi.mode(WIFI_STA);
    WiFi.begin("Wokwi-GUEST","",6);
    delay(100);
    if (xTaskCreatePinnedToCore(proofTask,"pqc-proof",32768,nullptr,0,nullptr,0) != pdPASS)
        Serial.println("PQC_FAILED task allocation");
}
void loop() { delay(100); }
