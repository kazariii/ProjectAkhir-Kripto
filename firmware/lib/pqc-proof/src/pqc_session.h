#pragma once
#include "pqc_crypto.h"

namespace pqc {
namespace session {
constexpr size_t MAX_PACKET = 1519, HELLO_SIZE = 69, SERVER_SIZE = 1519;
constexpr size_t KEY_SIZE = 1455, FINISH_SIZE = 37, DATA_SIZE = 207;
constexpr uint64_t HANDSHAKE_MS = 120000, LIFETIME_MS = 300000;
struct Identity {
    uint8_t secret[SIGN_SK], public_key[SIGN_PK], peer[SIGN_PK];
};
static_assert(sizeof(Identity) == 3139, "identity byte format");
struct Packet { uint8_t data[MAX_PACKET] = {}; size_t size = 0; };
enum class Role { Client, Server };
enum class Event { Rejected = 0, Send = 1, Established = 2, Plaintext = 3 };

// A channel has one owner/worker. Transport must discard retained MQTT messages
// and reset the channel on disconnect. All wire fields have explicit widths.
class Channel {
public:
    Channel(Role, const Identity&);
    ~Channel();
    Channel(const Channel&) = delete;
    Channel& operator=(const Channel&) = delete;
    bool begin(uint64_t now, Packet&);
    // Resend the exact pending handshake bytes; never reuse a nonce for new data.
    bool retry(uint64_t now, Packet&);
    bool renewal_due(uint64_t now) const;
    Event receive(const uint8_t*, size_t, uint64_t now, Packet& reply,
                  uint8_t plaintext[MAX_MESSAGE], size_t& length);
    bool encrypt(const uint8_t*, size_t, uint64_t now, Packet&);
    void tick(uint64_t now);
    void reset();
    bool active() const { return established_; }
    const uint8_t* id() const { return active_.sid; }
private:
    struct Pending {
        uint8_t transcript[3027], kem_secret[KEM_SK];
        uint8_t c2s[32], s2c[32], hash[32], finished[16];
        uint64_t started;
        unsigned stage;
    } pending_ = {};
    struct Active {
        uint8_t c2s[32], s2c[32], hash[32], sid[16];
        uint8_t client_finish_hash[32], server_finish[16];
        uint64_t sent, received, started;
    } active_ = {};
    Role role_;
    Identity identity_;
    uint8_t binding_[32] = {};
    bool valid_ = false, established_ = false;
    alignas(8) uint8_t workspace_[SIGN_WORKSPACE];
    bool derive(const uint8_t secret[32]);
    bool confirmation(bool decrypt, bool client, uint8_t tag[16]);
    void commit(uint64_t);
    void clear_pending();
};
}
}
