#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ctime>
#include <cstring>
#include "telemetry.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

constexpr uint8_t SENSOR_PIN = 4;
constexpr uint32_t SAMPLE_INTERVAL_MS = 2000;
constexpr uint32_t CONVERSION_MS = 750;  // DS18B20 12-bit maximum conversion time.
constexpr char TOPIC[] = "lab/kimia/meja01/telemetry";
constexpr char DEVICE_ID[] = "esp32-meja01";

OneWire oneWire(SENSOR_PIN);
DallasTemperature sensors(&oneWire);
WiFiClientSecure tls;
PubSubClient mqtt(tls);

bool configured = false;
bool converting = false;
bool sensorPresent = false;
bool sampleStarted = false;
bool attemptedMqtt = false;
uint32_t sampleStartMs = 0;
uint32_t lastMqttAttemptMs = 0;
uint32_t lastStatusMs = 0;

void maintainConnection(uint32_t now) {
    if (WiFi.status() != WL_CONNECTED) return;
    // NTP is required for certificate validity checks, not payload timestamps.
    if (std::time(nullptr) < 1767225600) return;  // 2026-01-01 UTC
    if (mqtt.connected()) {
        mqtt.loop();
        return;
    }
    if (attemptedMqtt && now - lastMqttAttemptMs < 5000) return;
    attemptedMqtt = true;
    lastMqttAttemptMs = now;
    if (mqtt.connect(DEVICE_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
        Serial.println("MQTT/TLS tersambung: CA dan hostname diverifikasi");
    } else {
        Serial.printf("MQTT/TLS gagal; status=%d (periksa waktu, CA, host, akun)\n",
                      mqtt.state());
    }
}

void setup() {
    Serial.begin(115200);
    configured = std::strstr(MQTT_HOST, "ISI_") == nullptr &&
                 std::strstr(MQTT_PASSWORD, "ISI_") == nullptr &&
                 std::strstr(MQTT_ROOT_CA, "ISI_") == nullptr &&
                 std::strlen(MQTT_HOST) > 0 && std::strlen(MQTT_PASSWORD) > 0;
    if (!configured) {
        Serial.println("Konfigurasi belum diisi: salin include/secrets.example.h ke secrets.h");
        return;
    }

    sensors.begin();
    sensors.setResolution(12);
    sensors.setWaitForConversion(false);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");

    tls.setCACert(MQTT_ROOT_CA);
    tls.setHandshakeTimeout(5);
    // The DNS hostname reaches WiFiClientSecure for SNI + certificate matching.
    mqtt.setServer(MQTT_HOST, 8883);
    mqtt.setSocketTimeout(5);
    mqtt.setBufferSize(256);
    Serial.println("Menunggu Wi-Fi dan NTP sebelum MQTT/TLS");
}

void loop() {
    if (!configured) {
        delay(1000);
        return;
    }
    uint32_t now = millis();
    maintainConnection(now);
    now = millis();

    if (!converting && (!sampleStarted || now - sampleStartMs >= SAMPLE_INTERVAL_MS)) {
        // Measure start-to-start. The 750 ms conversion is inside the 2 s period.
        sampleStarted = true;
        sampleStartMs = now;
        sensorPresent = oneWire.reset() != 0;
        if (sensorPresent) sensors.requestTemperatures();
        converting = true;
        Serial.printf("Konversi suhu dimulai ms=%lu\n", static_cast<unsigned long>(now));
    }

    if (converting && now - sampleStartMs >= CONVERSION_MS) {
        converting = false;
        const bool complete = sensorPresent && sensors.isConversionComplete();
        const float temperature = complete ? sensors.getTempCByIndex(0) : NAN;
        const auto message = makeTelemetry(temperature, complete);
        if (!message.publish) {
            Serial.println(message.diagnostic);
        } else if (mqtt.connected()) {
            // QoS 0, not retained: never replay an old sample as a new one.
            if (mqtt.publish(TOPIC, message.payload, false)) {
                Serial.printf("Terkirim ms=%lu %s\n", static_cast<unsigned long>(now), message.payload);
            } else {
                Serial.println("Pengiriman gagal; sampel tidak disimpan untuk dikirim ulang");
            }
        } else {
            Serial.println("Suhu valid; MQTT belum tersambung, sampel tidak dikirim");
        }
    }

    if (now - lastStatusMs >= 10000 && !mqtt.connected()) {
        lastStatusMs = now;
        Serial.printf("Menunggu koneksi: wifi=%d ntp=%s\n", WiFi.status(),
                      std::time(nullptr) >= 1767225600 ? "siap" : "belum sinkron");
    }
    delay(1);
}
