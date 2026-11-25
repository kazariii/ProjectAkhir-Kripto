#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_system.h>
#include <cstring>
#include "pqc_broker.h"

#ifdef DIAG_TOPIC_PREFIX
#define DIAG_PREFIX DIAG_TOPIC_PREFIX
#else
#define DIAG_PREFIX "lab/kimia/pqc/diag"
#endif
// On a public broker also echo the largest session header (docs/protokol-sesi-pqc.md).
constexpr size_t LARGE_FRAME = BROKER_PUBLIC ? 1519 : 0;

namespace {
constexpr char REQUEST[] = DIAG_PREFIX "/request";
constexpr char REPLY[] = DIAG_PREFIX "/reply";
WiFiClient tcp;
PubSubClient mqtt(tcp);
char runId[33], request[38], expected[37];
bool replied = false, finished = false, largeReplied = false, measured = false;
uint32_t started = 0, lastAttempt = 0, sentAt = 0, roundtrip = 0;
uint8_t large[LARGE_FRAME ? LARGE_FRAME : 1];

// Deterministic body after the "big:<run_id>:" header so the reply can be checked byte for byte.
void fillLarge() {
    int n = snprintf(reinterpret_cast<char*>(large), sizeof(large), "big:%s:", runId);
    for (size_t i=n; i<LARGE_FRAME; ++i) large[i] = static_cast<uint8_t>(i*31+7);
}

void received(char* topic, uint8_t* payload, unsigned int length) {
    if (strcmp(topic, REPLY) != 0) return;
    if (length == strlen(expected) && memcmp(payload, expected, length) == 0) replied = true;
    else if (LARGE_FRAME && length == LARGE_FRAME && memcmp(payload, large, length) == 0) largeReplied = true;
}
}
void setup() {
    Serial.begin(115200);
    Serial.println("MQTT_DIAG_BEGIN ticket=02 transport=MQTT-TCP");
    WiFi.mode(WIFI_STA);
    WiFi.begin("Wokwi-GUEST", "", 6);
    mqtt.setServer(BROKER_HOST, BROKER_PORT);
    mqtt.setCallback(received);
    mqtt.setSocketTimeout(3);
    mqtt.setKeepAlive(15);
    if (!mqtt.setBufferSize(LARGE_FRAME ? 2048 : 256)) {
        Serial.println("MQTT_DIAG_FAILED buffer allocation");
        finished = true;
    }
    started = millis();
}
void loop() {
    if (finished) { delay(100); return; }
    if (millis() - started > 120000) {
        Serial.println(LARGE_FRAME ? "MQTT_DIAG_FAILED timeout; check internet, public broker and responder"
                                   : "MQTT_DIAG_FAILED timeout; check Private Gateway, LXC route and responder");
        Serial.printf("MQTT_DIAG_STATE wifi_status=%d mqtt_state=%d\n", WiFi.status(), mqtt.state());
        finished = true;
        return;
    }
    // Log Wi-Fi transitions so a gateway failure is distinguishable from a broker failure.
    static int wifiStatus = -1;
    if (WiFi.status() != wifiStatus) {
        wifiStatus = WiFi.status();
        Serial.printf("MQTT_DIAG_WIFI_STATUS %d t=%lu\n", wifiStatus, static_cast<unsigned long>(millis()));
    }
    if (WiFi.status() != WL_CONNECTED) { delay(10); return; }
    if (!runId[0]) {
        uint8_t random[16]; esp_fill_random(random, sizeof(random));
        for (size_t i=0;i<sizeof(random);++i) snprintf(runId+2*i,3,"%02x",random[i]);
        snprintf(request,sizeof(request),"diag:%s",runId);
        snprintf(expected,sizeof(expected),"ack:%s",runId);
        if (LARGE_FRAME) fillLarge();
        Serial.printf("MQTT_DIAG_WIFI local_ip=%s\n", WiFi.localIP().toString().c_str());
    }
    if (!mqtt.connected()) {
        if (lastAttempt && millis() - lastAttempt < 3000) { delay(10); return; }
        lastAttempt = millis();
        char clientId[32]; snprintf(clientId,sizeof(clientId),"esp32-diag-%.12s",runId);
        if (!mqtt.connect(clientId,BROKER_USERNAME,BROKER_PASSWORD)) {
            Serial.printf("MQTT_DIAG_CONNECT_FAILED state=%d\n",mqtt.state());
            return;
        }
        if (!mqtt.subscribe(REPLY,0)) {
            Serial.println("MQTT_DIAG_FAILED subscribe send"); finished = true; return;
        }
        Serial.println("MQTT_DIAG_CONNECTED port=1883 tls=false");
        sentAt = 0;
    }
    mqtt.loop();
    if (replied && !measured) {
        measured = true;
        roundtrip = millis() - sentAt;
        sentAt = 0; // Send the large frame immediately when this build tests it.
    }
    bool needLarge = LARGE_FRAME && replied;
    if (!sentAt || millis() - sentAt >= 3000) {
        sentAt = millis();
        bool ok = needLarge ? mqtt.publish(REQUEST, large, LARGE_FRAME, false)
                            : mqtt.publish(REQUEST, request, false);
        if (!ok) {
            Serial.println("MQTT_DIAG_FAILED publish send"); finished = true; return;
        }
    }
    if (replied && (!LARGE_FRAME || largeReplied)) {
        Serial.printf("MQTT_DIAG_RESULT {\"passed\":true,\"run_id\":\"%s\",\"broker\":\"%s\",\"topic_prefix\":\"%s\",\"mqtt_port\":1883,\"tls\":false,\"local_ip\":\"%s\",\"roundtrip_ms\":%lu,\"large_frame_bytes\":%u}\n",
            runId,BROKER_HOST,DIAG_PREFIX,WiFi.localIP().toString().c_str(),static_cast<unsigned long>(roundtrip),
            static_cast<unsigned>(LARGE_FRAME));
        Serial.println("MQTT_DIAG_DONE");
        mqtt.disconnect();
        finished = true;
    }
    delay(10);
}
