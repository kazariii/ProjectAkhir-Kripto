#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_system.h>
#include <cstring>
#include "mqtt_diag_secrets.h"

namespace {
constexpr char REQUEST[] = "lab/kimia/pqc/diag/request";
constexpr char REPLY[] = "lab/kimia/pqc/diag/reply";
WiFiClient tcp;
PubSubClient mqtt(tcp);
char runId[33], request[38], expected[37];
bool replied = false, finished = false;
uint32_t started = 0, lastAttempt = 0, sentAt = 0;

void received(char* topic, uint8_t* payload, unsigned int length) {
    if (strcmp(topic, REPLY) == 0 && length == strlen(expected) &&
        memcmp(payload, expected, length) == 0) replied = true;
}
}
void setup() {
    Serial.begin(115200);
    Serial.println("MQTT_DIAG_BEGIN ticket=02 transport=MQTT-TCP");
    WiFi.mode(WIFI_STA);
    WiFi.begin("Wokwi-GUEST", "", 6);
    mqtt.setServer(MQTT_DIAG_HOST, 1883);
    mqtt.setCallback(received);
    mqtt.setSocketTimeout(3);
    mqtt.setKeepAlive(15);
    if (!mqtt.setBufferSize(256)) {
        Serial.println("MQTT_DIAG_FAILED buffer allocation");
        finished = true;
    }
    started = millis();
}
void loop() {
    if (finished) { delay(100); return; }
    if (millis() - started > 120000) {
        Serial.println("MQTT_DIAG_FAILED timeout; check Private Gateway, LXC route and responder");
        finished = true;
        return;
    }
    if (WiFi.status() != WL_CONNECTED) { delay(10); return; }
    if (!runId[0]) {
        uint8_t random[16]; esp_fill_random(random, sizeof(random));
        for (size_t i=0;i<sizeof(random);++i) snprintf(runId+2*i,3,"%02x",random[i]);
        snprintf(request,sizeof(request),"diag:%s",runId);
        snprintf(expected,sizeof(expected),"ack:%s",runId);
        Serial.printf("MQTT_DIAG_WIFI local_ip=%s\n", WiFi.localIP().toString().c_str());
    }
    if (!mqtt.connected()) {
        if (lastAttempt && millis() - lastAttempt < 3000) { delay(10); return; }
        lastAttempt = millis();
        char clientId[32]; snprintf(clientId,sizeof(clientId),"esp32-diag-%.12s",runId);
        if (!mqtt.connect(clientId,MQTT_DIAG_USERNAME,MQTT_DIAG_PASSWORD)) {
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
    if (!sentAt || millis() - sentAt >= 3000) {
        sentAt = millis();
        if (!mqtt.publish(REQUEST,request,false)) {
            Serial.println("MQTT_DIAG_FAILED publish send"); finished = true; return;
        }
    }
    if (replied) {
        Serial.printf("MQTT_DIAG_RESULT {\"passed\":true,\"run_id\":\"%s\",\"mqtt_port\":1883,\"tls\":false,\"local_ip\":\"%s\",\"roundtrip_ms\":%lu}\n",
            runId,WiFi.localIP().toString().c_str(),static_cast<unsigned long>(millis()-sentAt));
        Serial.println("MQTT_DIAG_DONE");
        mqtt.disconnect();
        finished = true;
    }
    delay(10);
}
