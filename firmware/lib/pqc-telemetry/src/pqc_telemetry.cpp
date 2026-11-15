#include "pqc_telemetry.h"
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_timer.h>
#include <cstring>
#include "pqc_session.h"
#include "pqc_session_identity.h"
#include "mqtt_diag_secrets.h"
#include "pending_sample.h"

namespace pqc_telemetry { namespace {
using namespace pqc;
using namespace pqc::session;
constexpr char UP[] = "lab/kimia/pqc/session/up", DOWN[] = "lab/kimia/pqc/session/down";
constexpr uint32_t SAMPLE_AGE_MS = 2000;
constexpr uint64_t ACK_TIMEOUT_MS = 10000;
constexpr uint64_t RETRY_MS = 5000;
enum class Command { Begin, Frame, Reset };
enum class Kind { Frame, Authenticated, Stored, Reconnect };
struct Input { Command command; uint32_t generation; Packet packet; };
struct Output {
    Kind kind = Kind::Frame;
    uint32_t generation = 0, measured = 0;
    uint64_t counter = 0;
    uint8_t sid[16] = {};
    Packet packet;
};
QueueHandle_t incoming, outgoing, latest;
WiFiClient tcp;
PubSubClient mqtt(tcp);
char run_id[33] = {};
uint64_t now() { return esp_timer_get_time()/1000; }
uint64_t counter(const uint8_t* data) {
    uint64_t n = 0;
    for (unsigned i=0; i<8; ++i) n |= uint64_t(data[21+i]) << (8*i);
    return n;
}
void emit(const Output& out) { xQueueSend(outgoing, &out, portMAX_DELAY); }
void received(char* topic, uint8_t* data, unsigned int size) {
    if (std::strcmp(topic, DOWN) || size < 5 || size > MAX_PACKET) return;
    Input in; in.command = Command::Frame;
    // Only the network task accesses generation, including this callback.
    extern uint32_t generation;
    in.generation = generation; in.packet.size = size;
    std::memcpy(in.packet.data, data, size);
    // A full queue drops the frame. The bounded handshake deadline reconnects.
    xQueueSend(incoming, &in, 0);
}
uint32_t generation = 0;
void worker(void*) {
    static Channel channel(Role::Client, SESSION_IDENTITY);
    uint32_t current = 0;
    uint64_t handshake_at = 0, retry_at = 0, sent = 0, stored = 0, progress_at = 0;
    unsigned retries = 0;
    bool pending = false, renewal_requested = false;
    auto begin = [&](Output& out) {
        pending = channel.begin(now(), out.packet); handshake_at = retry_at = now(); retries = 0;
        renewal_requested = false; xQueueReset(latest);
        if (!pending) out.kind = Kind::Reconnect;
    };
    Input in;
    for (;;) {
        if (xQueueReceive(incoming, &in, pdMS_TO_TICKS(10)) == pdTRUE) {
            Output out; out.generation = in.generation;
            if (in.command == Command::Reset || in.command == Command::Begin) {
                current = in.generation; channel.reset(); pending = renewal_requested = false; sent = stored = 0;
                xQueueReset(latest);
                if (in.command == Command::Reset) continue;
                begin(out);
                emit(out);
            } else if (in.generation == current) {
                uint8_t plain[MAX_MESSAGE]; size_t n;
                auto event = channel.receive(in.packet.data, in.packet.size, now(), out.packet, plain, n);
                if (event == Event::Established) {
                    pending = renewal_requested = false; sent = stored = 0;
                    xQueueReset(latest); // Discard readings collected during the signature/handshake.
                    out.kind = Kind::Authenticated; std::memcpy(out.sid, channel.id(), 16);
                    emit(out);
                } else if (event == Event::Plaintext) {
                    char ack[MAX_MESSAGE+1]; std::memcpy(ack, plain, n); ack[n] = 0;
                    if (n == sizeof("{\"renew_session\":true}")-1 &&
                        !std::memcmp(ack, "{\"renew_session\":true}", n) && !pending) renewal_requested = true;
                    unsigned long long accepted = 0; int consumed = 0;
                    if (sscanf(ack, "{\"stored_counter\":%llu}%n", &accepted, &consumed) == 1 &&
                        consumed == int(n) && accepted > stored && accepted <= sent) {
                        stored = accepted; progress_at = now(); out.counter = accepted; out.kind = Kind::Stored;
                        std::memcpy(out.sid, channel.id(), 16); emit(out);
                    }
                } else if (out.packet.size) { retry_at = now(); retries = 0; emit(out); }
                erase(plain, sizeof(plain));
            }
        }
        channel.tick(now());
        if (pending && now()-handshake_at >= HANDSHAKE_MS) {
            channel.reset(); pending = false; xQueueReset(latest);
            Output out; out.generation = current; out.kind = Kind::Reconnect; emit(out);
        }
        if (pending && now()-retry_at >= RETRY_MS) {
            Output out; out.generation = current;
            if (retries < 2 && channel.retry(now(), out.packet)) { ++retries; retry_at = now(); }
            else begin(out); // Peer may have restarted and lost its pending challenge.
            emit(out);
        }
        if (channel.active() && !pending && (renewal_requested || channel.renewal_due(now()) ||
            (sent > stored && now()-progress_at >= ACK_TIMEOUT_MS))) {
            Output out; out.generation = current;
            begin(out);
            emit(out);
        }
        if (!channel.active() || pending) { xQueueReset(latest); continue; }
        PendingSample sample;
        if (xQueueReceive(latest, &sample, 0) != pdTRUE || millis()-sample.measuredAtMs >= SAMPLE_AGE_MS) continue;
        const size_t length = strnlen(sample.payload, sizeof(sample.payload));
        Output out; out.generation = current; out.measured = sample.measuredAtMs;
        if (!length || length == sizeof(sample.payload) ||
            !channel.encrypt(reinterpret_cast<uint8_t*>(sample.payload), length, now(), out.packet)) continue;
        if (sent == stored) progress_at = now();
        out.counter = counter(out.packet.data); sent = out.counter;
        std::memcpy(out.sid, channel.id(), 16); emit(out);
        erase(&sample, sizeof(sample));
    }
}
void network(void*) {
    Serial.printf("TELEMETRY_BEGIN ticket=04 transport=MQTT-TCP profile=LK3/1\n");
    WiFi.mode(WIFI_STA); WiFi.begin("Wokwi-GUEST", "", 6);
    mqtt.setServer(MQTT_DIAG_HOST, 1883); mqtt.setCallback(received);
    // Wokwi's clock can lag wall time. Allow the measured signing interval and
    // short simulator stalls without a broker timeout; indefinite Pause still disconnects.
    mqtt.setKeepAlive(120); mqtt.setSocketTimeout(3);
    bool connected = false;
    uint64_t attempt = 0, wifi_attempt = 0;
    for (;;) {
        if (connected && (WiFi.status() != WL_CONNECTED || !mqtt.connected())) {
            connected = false; mqtt.disconnect(); ++generation;
            xQueueReset(incoming); xQueueReset(outgoing); xQueueReset(latest);
            Input in; in.command = Command::Reset; in.generation = generation;
            xQueueSend(incoming, &in, 0);
            Serial.println("TELEMETRY_DISCONNECTED keys reset; local alarms continue");
        }
        if (WiFi.status() != WL_CONNECTED) {
            if (now()-wifi_attempt >= 5000) { wifi_attempt = now(); WiFi.reconnect(); }
            vTaskDelay(pdMS_TO_TICKS(10)); continue;
        }
        if (!run_id[0]) {
            uint8_t bytes[16]; random_bytes(bytes, sizeof(bytes));
            for (unsigned i=0; i<16; ++i) snprintf(run_id+2*i, 3, "%02x", bytes[i]);
            Serial.printf("TELEMETRY_RUN {\"run_id\":\"%s\",\"local_ip\":\"%s\"}\n", run_id, WiFi.localIP().toString().c_str());
        }
        if (!mqtt.connected()) {
            xQueueReset(latest);
            if (attempt && now()-attempt < 5000) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
            attempt = now();
            char client[40]; snprintf(client, sizeof(client), "esp32-telemetry-%.12s", run_id);
            if (!mqtt.connect(client, MQTT_DIAG_USERNAME, MQTT_DIAG_PASSWORD)) {
                Serial.printf("TELEMETRY_CONNECT_FAILED state=%d\n", mqtt.state()); continue;
            }
            if (!mqtt.subscribe(DOWN, 0)) { mqtt.disconnect(); continue; }
            connected = true; ++generation;
            xQueueReset(incoming); xQueueReset(outgoing); xQueueReset(latest);
            Input in; in.command = Command::Begin; in.generation = generation;
            xQueueSend(incoming, &in, 0);
        }
        mqtt.loop();
        Output out;
        while (xQueueReceive(outgoing, &out, 0) == pdTRUE) {
            if (out.generation != generation) continue;
            if (out.kind == Kind::Reconnect) { mqtt.disconnect(); break; }
            char sid[33]; for (unsigned i=0; i<16; ++i) snprintf(sid+2*i, 3, "%02x", out.sid[i]);
            if (out.kind == Kind::Authenticated) {
                Serial.printf("TELEMETRY_AUTHENTICATED {\"run_id\":\"%s\",\"session_id\":\"%s\",\"mqtt_port\":1883,\"tls\":false}\n", run_id, sid);
            }
            if (out.kind == Kind::Stored) {
                Serial.printf("TELEMETRY_STORED {\"session_id\":\"%s\",\"counter\":%llu,\"ack_verified\":true}\n", sid, static_cast<unsigned long long>(out.counter));
            }
            if (out.packet.size) {
                if (out.counter && millis()-out.measured >= SAMPLE_AGE_MS) continue;
                if (!mqtt.publish(UP, out.packet.data, out.packet.size, false)) { mqtt.disconnect(); break; }
                if (out.counter) Serial.printf("TELEMETRY_SENT {\"session_id\":\"%s\",\"counter\":%llu,\"measured_ms\":%lu}\n", sid, static_cast<unsigned long long>(out.counter), static_cast<unsigned long>(out.measured));
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
} // namespace
bool start(QueueHandle_t latest_reading) {
    latest = latest_reading;
    incoming = xQueueCreate(4, sizeof(Input)); outgoing = xQueueCreate(4, sizeof(Output));
    if (!incoming || !outgoing || !mqtt.setBufferSize(4096)) {
        if (incoming) vQueueDelete(incoming);
        if (outgoing) vQueueDelete(outgoing);
        return false;
    }
    TaskHandle_t crypto = nullptr;
    if (xTaskCreatePinnedToCore(worker, "telemetry-crypto", 32768, nullptr, 0, &crypto, 0) != pdPASS) {
        vQueueDelete(incoming); vQueueDelete(outgoing); return false;
    }
    if (xTaskCreatePinnedToCore(network, "telemetry-mqtt", 8192, nullptr, 1, nullptr, 0) != pdPASS) {
        vTaskDelete(crypto); vQueueDelete(incoming); vQueueDelete(outgoing); return false;
    }
    return true;
}
}
