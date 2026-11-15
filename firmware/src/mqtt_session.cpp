#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_timer.h>
#include <new>
#include <cstring>
#include "pqc_session.h"
#include "pqc_session_identity.h"
#include "mqtt_diag_secrets.h"

namespace {
using namespace pqc;
using namespace pqc::session;
constexpr char UP[] = "lab/kimia/pqc/session/up", DOWN[] = "lab/kimia/pqc/session/down";
enum class Command { Begin, Frame, Reset };
struct Input { Command command; uint32_t generation; Packet packet; };
struct Output {
    uint32_t generation;
    Packet packet;
    bool authenticated = false, done = false, failed = false;
    uint8_t sid[16] = {};
};
QueueHandle_t incoming, outgoing;
WiFiClient tcp;
PubSubClient mqtt(tcp);
char runId[33] = {};
uint32_t generation = 0, lastAttempt = 0;
uint64_t started;
bool finished = false, wasConnected = false;
uint64_t now() { return esp_timer_get_time()/1000; }
void fail(const char* reason) {
    Serial.printf("SESSION_FAILED %s\n", reason); finished = true;
    mqtt.disconnect();
    Input reset; reset.command = Command::Reset; reset.generation = ++generation;
    xQueueReset(incoming); xQueueSend(incoming, &reset, 0);
}
void received(char* topic, uint8_t* data, unsigned int length) {
    if (std::strcmp(topic, DOWN) || length < 5 || length > MAX_PACKET) return;
    Input in; in.command = Command::Frame; in.generation = generation;
    std::memcpy(in.packet.data, data, length); in.packet.size = length;
    if (xQueueSend(incoming, &in, 0) != pdTRUE) fail("input queue full");
}
void worker(void*) {
    static Channel channel(Role::Client, SESSION_IDENTITY);
    uint32_t current = 0;
    Input in;
    for (;;) {
        if (xQueueReceive(incoming, &in, pdMS_TO_TICKS(250)) != pdTRUE) {
            channel.tick(now()); continue;
        }
        Output out; out.generation = in.generation;
        if (in.command == Command::Reset) { channel.reset(); current = in.generation; continue; }
        if (in.command == Command::Begin) {
            current = in.generation; channel.reset();
            out.failed = !channel.begin(now(), out.packet);
        } else {
            if (in.generation != current) continue;
            uint8_t plain[MAX_MESSAGE]; size_t n;
            auto event = channel.receive(in.packet.data, in.packet.size, now(), out.packet, plain, n);
            // Unauthenticated garbage is discarded; it never triggers plaintext fallback.
            if (event == Event::Rejected) continue;
            if (event == Event::Established) {
                out.authenticated = true; std::memcpy(out.sid, channel.id(), 16);
                char sample[MAX_MESSAGE+1];
                int size = snprintf(sample, sizeof(sample), "{\"device_id\":\"esp32-meja01\",\"probe\":\"ticket-03\",\"run_id\":\"%s\",\"temperature_c\":26.25}", runId);
                out.failed = size <= 0 || size > int(MAX_MESSAGE) ||
                    !channel.encrypt(reinterpret_cast<uint8_t*>(sample), size, now(), out.packet);
            }
            if (event == Event::Plaintext) {
                char expected[96];
                int size = snprintf(expected, sizeof(expected), "{\"accepted\":true,\"run_id\":\"%s\"}", runId);
                out.done = n == size_t(size) && !std::memcmp(plain, expected, n);
                out.failed = !out.done;
                std::memcpy(out.sid, channel.id(), 16);
                channel.reset();
            }
            erase(plain, sizeof(plain));
        }
        if (xQueueSend(outgoing, &out, pdMS_TO_TICKS(1000)) != pdTRUE) channel.reset();
    }
}
}
void setup() {
    Serial.begin(115200);
    Serial.println("SESSION_BEGIN ticket=03 profile=LK3/1 prospective-FN-DSA-512 ML-KEM-512 ChaCha20-Poly1305");
    incoming = xQueueCreate(4, sizeof(Input)); outgoing = xQueueCreate(4, sizeof(Output));
    if (!incoming || !outgoing) { Serial.println("SESSION_FAILED queue allocation"); finished = true; return; }
    WiFi.mode(WIFI_STA); WiFi.begin("Wokwi-GUEST", "", 6);
    mqtt.setServer(MQTT_DIAG_HOST, 1883); mqtt.setCallback(received);
    mqtt.setKeepAlive(15); mqtt.setSocketTimeout(3);
    if (!mqtt.setBufferSize(4096)) { fail("MQTT buffer allocation"); return; }
    // A separate owner keeps mqtt.loop() running during the ~12s FN-DSA sign.
    if (xTaskCreatePinnedToCore(worker, "pqc-session", 32768, nullptr, 0, nullptr, 0) != pdPASS) {
        fail("crypto worker allocation"); return;
    }
    started = now();
}
void loop() {
    if (finished) { delay(100); return; }
    if (now()-started > 180000) { fail("timeout; check Private Gateway and LXC session receiver"); return; }
    if (wasConnected && (WiFi.status() != WL_CONNECTED || !mqtt.connected())) {
        wasConnected = false;
        Input reset; reset.command = Command::Reset; reset.generation = ++generation;
        xQueueReset(incoming); xQueueSend(incoming, &reset, 0);
        Serial.println("SESSION_DISCONNECTED keys reset");
    }
    if (WiFi.status() != WL_CONNECTED) { delay(10); return; }
    if (!runId[0]) {
        uint8_t random[16]; random_bytes(random, sizeof(random));
        for (unsigned i=0; i<16; ++i) snprintf(runId+2*i, 3, "%02x", random[i]);
        Serial.printf("SESSION_WIFI local_ip=%s\n", WiFi.localIP().toString().c_str());
    }
    if (!mqtt.connected()) {
        if (lastAttempt && millis()-lastAttempt < 3000) { delay(10); return; }
        lastAttempt = millis();
        char clientId[40]; snprintf(clientId, sizeof(clientId), "esp32-session-%.12s", runId);
        if (!mqtt.connect(clientId, MQTT_DIAG_USERNAME, MQTT_DIAG_PASSWORD)) {
            Serial.printf("SESSION_CONNECT_FAILED state=%d\n", mqtt.state()); return;
        }
        // Clean MQTT session, QoS 0, retain=false on both directions. Broker ACL
        // forbids this device from publishing DOWN; no retained handshake exists.
        if (!mqtt.subscribe(DOWN, 0)) { fail("subscribe send"); return; }
        wasConnected = true; ++generation;
        xQueueReset(incoming); xQueueReset(outgoing);
        Input begin; begin.command = Command::Begin; begin.generation = generation;
        if (xQueueSend(incoming, &begin, 0) != pdTRUE) { fail("begin queue full"); return; }
        Serial.println("SESSION_CONNECTED port=1883 tls=false");
    }
    mqtt.loop();
    Output out;
    while (!finished && xQueueReceive(outgoing, &out, 0) == pdTRUE) {
        if (out.generation != generation) continue;
        if (out.failed) { fail("cryptographic operation/ACK validation"); break; }
        if (out.authenticated) Serial.println("SESSION_AUTHENTICATED mutual=true key_confirmation=true");
        if (out.packet.size && !mqtt.publish(UP, out.packet.data, out.packet.size, false)) { fail("publish send"); break; }
        if (out.done) {
            char sid[33]; for (unsigned i=0; i<16; ++i) snprintf(sid+2*i, 3, "%02x", out.sid[i]);
            Serial.printf("SESSION_RESULT {\"passed\":true,\"run_id\":\"%s\",\"session_id\":\"%s\",\"mqtt_port\":1883,\"tls\":false,\"local_ip\":\"%s\",\"mutual_auth\":true,\"key_confirmation\":true,\"encrypted_ack_verified\":true,\"elapsed_ms\":%llu}\n",
                runId, sid, WiFi.localIP().toString().c_str(), static_cast<unsigned long long>(now()-started));
            Serial.println("SESSION_DONE"); finished = true; mqtt.disconnect();
        }
    }
    delay(10);
}
