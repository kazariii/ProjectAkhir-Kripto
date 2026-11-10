#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ctime>
#include <cstring>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include "telemetry.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

constexpr uint8_t SENSOR_PIN = 4;
constexpr uint8_t GAS_ANALOG_PIN = 34;  // ADC1: available while Wi-Fi is active.
constexpr uint8_t GAS_DIGITAL_PIN = 27;
constexpr uint8_t ALARM_LED_PIN = 25;
constexpr uint8_t BUZZER_PIN = 26;
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
bool attemptedWifi = false;
uint32_t sampleStartMs = 0;
uint32_t conversionStartMs = 0;
uint32_t lastMqttAttemptMs = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastStatusMs = 0;
AlarmState alarms;
bool alarmOutputActive = false;

// One copied sample, never a backlog. Only the network task owns WiFi/TLS/MQTT.
struct PendingSample {
    uint32_t measuredAtMs;
    char payload[160];
};
QueueHandle_t outgoing = nullptr;

void updateLocalAlarm() {
    // DOUT is independent of the ADC and of temperature conversion/failure.
    alarms.gas = digitalRead(GAS_DIGITAL_PIN) == LOW;
    const bool active = alarms.active();
    if (active != alarmOutputActive) {
        digitalWrite(ALARM_LED_PIN, active ? HIGH : LOW);
        if (active) tone(BUZZER_PIN, 2000);
        else noTone(BUZZER_PIN);
        alarmOutputActive = active;
        Serial.printf("Alarm lokal: gas=%s suhu=%s LED/buzzer=%s\n",
                      alarms.gas ? "aktif" : "normal",
                      alarms.temperature ? "aktif" : "normal", active ? "ON" : "OFF");
    }
}

void networkStep() {
    const uint32_t now = millis();
    if (WiFi.status() != WL_CONNECTED) {
        xQueueReset(outgoing);
        if (mqtt.connected()) mqtt.disconnect();
        if (!attemptedWifi || now - lastWifiAttemptMs >= 5000) {
            attemptedWifi = true;
            lastWifiAttemptMs = now;
            WiFi.reconnect();
        }
        return;
    }
    // NTP is required for certificate validity checks, not payload timestamps.
    if (std::time(nullptr) < 1767225600) {  // 2026-01-01 UTC
        xQueueReset(outgoing);
        return;
    }
    if (mqtt.connected()) {
        if (!mqtt.loop()) {
            xQueueReset(outgoing);
            return;
        }
        PendingSample sample;
        if (xQueueReceive(outgoing, &sample, 0) == pdTRUE &&
            millis() - sample.measuredAtMs < SAMPLE_INTERVAL_MS) {
            // QoS 0, not retained, no retries of a failed/expired sample.
            if (mqtt.publish(TOPIC, sample.payload, false)) {
                Serial.printf("Terkirim ms=%lu %s\n",
                              static_cast<unsigned long>(sample.measuredAtMs), sample.payload);
            } else {
                Serial.println("Pengiriman gagal; sampel tidak disimpan untuk dikirim ulang");
            }
        }
        return;
    }
    xQueueReset(outgoing);
    if (attemptedMqtt && now - lastMqttAttemptMs < 5000) return;
    attemptedMqtt = true;
    lastMqttAttemptMs = now;
    if (mqtt.connect(DEVICE_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
        Serial.println("MQTT/TLS tersambung: CA dan hostname diverifikasi");
    } else {
        char tlsError[160] = {};
        const int tlsCode = tls.lastError(tlsError, sizeof(tlsError));
        Serial.printf("MQTT/TLS gagal; status=%d; TLS=%d %s\n",
                      mqtt.state(), tlsCode, tlsError);
    }
    // Discard readings taken DURING the blocking handshake, even on success.
    xQueueReset(outgoing);
    if (now - lastStatusMs >= 10000 && !mqtt.connected()) {
        lastStatusMs = now;
        Serial.println("Menunggu MQTT; sensor dan alarm lokal tetap berjalan");
    }
}

void initializeNetwork() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
    tls.setCACert(MQTT_ROOT_CA);
    tls.setHandshakeTimeout(5);
    // The DNS hostname reaches WiFiClientSecure for SNI + certificate matching.
    mqtt.setServer(MQTT_HOST, 8883);
    mqtt.setSocketTimeout(5);
    mqtt.setBufferSize(256);
    Serial.println("Menunggu Wi-Fi dan NTP sebelum MQTT/TLS; monitoring lokal mandiri");
}

void networkTask(void*) {
    initializeNetwork();
    for (;;) {
        networkStep();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void setup() {
    Serial.begin(115200);
    // Local monitoring works even before network credentials are supplied.
    sensors.begin();
    sensors.setResolution(12);
    sensors.setWaitForConversion(false);
    pinMode(GAS_ANALOG_PIN, INPUT);
    pinMode(GAS_DIGITAL_PIN, INPUT);
    pinMode(ALARM_LED_PIN, OUTPUT);
    digitalWrite(ALARM_LED_PIN, LOW);
    pinMode(BUZZER_PIN, OUTPUT);
    noTone(BUZZER_PIN);
    analogReadResolution(12);
    analogSetPinAttenuation(GAS_ANALOG_PIN, ADC_11db);
    updateLocalAlarm();
    configured = std::strstr(MQTT_HOST, "ISI_") == nullptr &&
                 std::strstr(MQTT_PASSWORD, "ISI_") == nullptr &&
                 std::strstr(MQTT_ROOT_CA, "ISI_") == nullptr &&
                 std::strlen(MQTT_HOST) > 0 && std::strlen(MQTT_PASSWORD) > 0;
    if (!configured) {
        Serial.println("Konfigurasi belum diisi: salin include/secrets.example.h ke secrets.h; alarm lokal tetap berjalan");
        return;
    }

    outgoing = xQueueCreate(1, sizeof(PendingSample));
    if (!outgoing) {
        Serial.println("Antrean jaringan gagal dibuat; alarm lokal tetap berjalan");
        return;
    }
    if (xTaskCreatePinnedToCore(networkTask, "telemetry-network", 8192, nullptr,
                              1, nullptr, 0) != pdPASS) {
        vQueueDelete(outgoing);
        outgoing = nullptr;
        Serial.println("Tugas jaringan gagal dibuat; alarm lokal tetap berjalan");
    }
}

void loop() {
    updateLocalAlarm();
    uint32_t now = millis();

    if (!converting && (!sampleStarted || now - sampleStartMs >= SAMPLE_INTERVAL_MS)) {
        // Measure start-to-start. The 750 ms conversion is inside the 2 s period.
        sampleStarted = true;
        sampleStartMs = now;
        sensorPresent = oneWire.reset() != 0;
        if (sensorPresent) {
            const auto request = sensors.requestTemperatures();
            conversionStartMs = request.timestamp;
            converting = request.result;
            Serial.printf("Konversi suhu dimulai ms=%lu\n",
                          static_cast<unsigned long>(conversionStartMs));
        } else {
            Serial.println("gagal baca DS18B20: sensor tidak terdeteksi di GPIO 4; periksa VCC, GND, DQ; tidak dikirim");
        }
    }

    // The library timestamps AFTER sending the command. Bus traffic belongs
    // to the sample period, but must not shorten the sensor's conversion time.
    now = millis();
    if (converting && now - conversionStartMs >= CONVERSION_MS) {
        const bool complete = sensorPresent && sensors.isConversionComplete();
        // A busy bit at the first deadline check is not a failed reading.
        // Poll again, with a bounded wait of one sample period.
        if (!complete && now - conversionStartMs < SAMPLE_INTERVAL_MS) {
            delay(1);
            return;
        }
        converting = false;
        const float temperature = complete ? sensors.getTempCByIndex(0) : NAN;
        // Read both MQ2 outputs in the same cycle as the completed temperature.
        const int gasRaw = analogRead(GAS_ANALOG_PIN);
        alarms.observeTemperature(temperature, complete);
        updateLocalAlarm();
        Serial.printf("MQ2 gas_raw=%d ADC; ambang=%s (DOUT=%s)\n", gasRaw,
                      alarms.gas ? "terlampaui" : "belum terlampaui",
                      alarms.gas ? "LOW" : "HIGH");
        const auto message = makeTelemetry(temperature, complete, gasRaw, alarms);
        if (!message.publish) {
            Serial.println(message.diagnostic);
        } else if (outgoing) {
            PendingSample sample = {};
            sample.measuredAtMs = now;
            std::memcpy(sample.payload, message.payload, sizeof(sample.payload));
            xQueueOverwrite(outgoing, &sample);  // Nonblocking; copy, no shared sensor state.
            Serial.printf("Sampel lokal ms=%lu %s\n", static_cast<unsigned long>(now), message.payload);
        } else {
            Serial.println("Suhu dan gas valid; jaringan tidak tersedia, sampel tidak dikirim");
        }
    }

    delay(1);
}
