#include "pqc_session.h"
#include "mlkem_native.h"
#include <cstring>
#include <limits>

namespace pqc { namespace session {
namespace {
constexpr size_t M2 = HELLO_SIZE, M3 = HELLO_SIZE + SERVER_SIZE;
constexpr size_t SERVER_BODY = 853, CLIENT_BODY = 773, CLIENT_SIGNED = 1439;
constexpr size_t DATA_HEADER = 31;
const uint8_t MAGIC[] = {'L', 'K', '3', 1};
constexpr char SERVER_CONTEXT[] = "lab-kimia/session-v1/server";
constexpr char CLIENT_CONTEXT[] = "lab-kimia/session-v1/device";
void header(uint8_t* p, unsigned type) { std::memcpy(p, MAGIC, 4); p[4] = type; }
bool equal(const uint8_t* a, const uint8_t* b, size_t n) {
    uint8_t different = 0;
    for (size_t i = 0; i < n; ++i) different |= a[i] ^ b[i];
    return different == 0;
}
void put64(uint8_t* p, uint64_t n) {
    for (unsigned i = 0; i < 8; ++i) { p[i] = n & 255; n >>= 8; }
}
uint64_t get64(const uint8_t* p) {
    uint64_t n = 0;
    for (unsigned i = 0; i < 8; ++i) n |= uint64_t(p[i]) << (8*i);
    return n;
}
}
Channel::Channel(Role role, const Identity& identity) : role_(role), identity_(identity) {
    // Canonical role order binds both pinned identities to every transcript.
    uint8_t keys[2*SIGN_PK];
    std::memcpy(keys, role == Role::Server ? identity.public_key : identity.peer, SIGN_PK);
    std::memcpy(keys+SIGN_PK, role == Role::Client ? identity.public_key : identity.peer, SIGN_PK);
    valid_ = sha256(keys, sizeof(keys), binding_);
    erase(keys, sizeof(keys));
}
Channel::~Channel() { reset(); erase(&identity_, sizeof(identity_)); erase(workspace_, sizeof(workspace_)); }
void Channel::clear_pending() { erase(&pending_, sizeof(pending_)); }
void Channel::reset() { clear_pending(); erase(&active_, sizeof(active_)); established_ = false; }
void Channel::tick(uint64_t now) {
    if (pending_.stage && now - pending_.started >= HANDSHAKE_MS) clear_pending();
    if (established_ && now - active_.started >= LIFETIME_MS) {
        erase(&active_, sizeof(active_)); established_ = false;
    }
}
bool Channel::begin(uint64_t now, Packet& out) {
    out.size = 0; tick(now);
    if (!valid_ || role_ != Role::Client) return false;
    clear_pending();
    auto* p = pending_.transcript;
    header(p, 1); std::memcpy(p+5, binding_, 32);
    if (!random_bytes(p+37, 32)) { clear_pending(); return false; }
    pending_.started = now; pending_.stage = 1;
    std::memcpy(out.data, p, HELLO_SIZE); out.size = HELLO_SIZE;
    return true;
}
bool Channel::retry(uint64_t now, Packet& out) {
    out.size = 0; tick(now);
    if (role_ != Role::Client) return false;
    if (pending_.stage == 1) {
        std::memcpy(out.data, pending_.transcript, HELLO_SIZE); out.size = HELLO_SIZE;
    } else if (pending_.stage == 3) {
        std::memcpy(out.data, pending_.transcript+M3, CLIENT_SIGNED);
        std::memcpy(out.data+CLIENT_SIGNED, pending_.finished, 16); out.size = KEY_SIZE;
    }
    return out.size != 0;
}
bool Channel::renewal_due(uint64_t now) const {
    return established_ && now-active_.started >= LIFETIME_MS-HANDSHAKE_MS;
}
bool Channel::derive(const uint8_t secret[32]) {
    uint8_t info[35];
    bool ok = sha256(pending_.transcript, sizeof(pending_.transcript), pending_.hash);
    std::memcpy(info, pending_.hash, 32); std::memcpy(info+32, "c2s", 3);
    if (ok) ok = hkdf(secret, pending_.transcript+M2+5, info, sizeof(info), pending_.c2s);
    std::memcpy(info+32, "s2c", 3);
    if (ok) ok = hkdf(secret, pending_.transcript+M2+5, info, sizeof(info), pending_.s2c);
    erase(info, sizeof(info));
    return ok;
}
bool Channel::confirmation(bool decrypt, bool client, uint8_t tag[16]) {
    uint8_t aad[47], nonce[12] = {}, dummy[1] = {};
    std::memcpy(aad, pending_.hash, 32);
    std::memcpy(aad+32, client ? "client-finished" : "server-finished", 15);
    return aead(decrypt, client ? pending_.c2s : pending_.s2c, nonce,
                aad, sizeof(aad), dummy, 0, dummy, tag);
}
void Channel::commit(uint64_t now) {
    erase(&active_, sizeof(active_));
    std::memcpy(active_.c2s, pending_.c2s, 32); std::memcpy(active_.s2c, pending_.s2c, 32);
    std::memcpy(active_.hash, pending_.hash, 32);
    std::memcpy(active_.sid, pending_.transcript+M2+37, 16);
    active_.started = now; established_ = true;
    clear_pending();
}
Event Channel::receive(const uint8_t* data, size_t size, uint64_t now, Packet& out,
                       uint8_t plain[MAX_MESSAGE], size_t& length) {
    out.size = 0; length = 0; erase(plain, MAX_MESSAGE); tick(now);
    if (!valid_ || !data || size < 5 || size > MAX_PACKET || !equal(data, MAGIC, 4)) return Event::Rejected;
    auto* t = pending_.transcript;
    if (role_ == Role::Server && data[4] == 1 && size == HELLO_SIZE) {
        if (!equal(data+5, binding_, 32)) return Event::Rejected;
        if (pending_.stage == 2 && equal(data, t, HELLO_SIZE)) {
            std::memcpy(out.data, t+M2, SERVER_SIZE); out.size = SERVER_SIZE;
            return Event::Send; // Duplicate M1 must not change keys or deadline.
        }
        clear_pending(); std::memcpy(t, data, size); header(t+M2, 2);
        uint8_t coins[64];
        bool ok = random_bytes(t+M2+5, 48) && random_bytes(coins, sizeof(coins)) &&
            pqc_mlkem_keypair_derand(t+M2+53, pending_.kem_secret, coins) == 0 &&
            sign(identity_.secret, SERVER_CONTEXT, t, M2+SERVER_BODY, t+M2+SERVER_BODY, workspace_);
        erase(coins, sizeof(coins));
        if (!ok) { clear_pending(); return Event::Rejected; }
        pending_.started = now; pending_.stage = 2;
        std::memcpy(out.data, t+M2, SERVER_SIZE); out.size = SERVER_SIZE;
        return Event::Send;
    }
    if (role_ == Role::Client && data[4] == 2 && size == SERVER_SIZE && pending_.stage == 1) {
        std::memcpy(t+M2, data, size);
        if (!verify(identity_.peer, SERVER_CONTEXT, t, M2+SERVER_BODY, t+M2+SERVER_BODY, workspace_)) return Event::Rejected;
        header(t+M3, 3);
        uint8_t coins[32], secret[32] = {};
        bool ok = random_bytes(coins, sizeof(coins)) &&
            pqc_mlkem_enc_derand(t+M3+5, secret, t+M2+53, coins) == 0 &&
            sign(identity_.secret, CLIENT_CONTEXT, t, M3+CLIENT_BODY, t+M3+CLIENT_BODY, workspace_) && derive(secret);
        erase(coins, sizeof(coins)); erase(secret, sizeof(secret));
        if (ok) {
            std::memcpy(out.data, t+M3, CLIENT_SIGNED);
            ok = confirmation(false, true, out.data+CLIENT_SIGNED);
        }
        if (!ok) { clear_pending(); return Event::Rejected; }
        std::memcpy(pending_.finished, out.data+CLIENT_SIGNED, 16);
        pending_.stage = 3; out.size = KEY_SIZE;
        return Event::Send;
    }
    if (role_ == Role::Server && data[4] == 3 && size == KEY_SIZE && established_) {
        uint8_t digest[32];
        const bool duplicate = sha256(data, size, digest) && equal(digest, active_.client_finish_hash, 32);
        erase(digest, sizeof(digest));
        if (duplicate) {
            header(out.data, 4); std::memcpy(out.data+5, active_.sid, 16);
            std::memcpy(out.data+21, active_.server_finish, 16); out.size = FINISH_SIZE;
            return Event::Send; // No recommit, TTL extension, or replay-state reset.
        }
    }
    if (role_ == Role::Server && data[4] == 3 && size == KEY_SIZE && pending_.stage == 2) {
        std::memcpy(t+M3, data, CLIENT_SIGNED);
        if (!verify(identity_.peer, CLIENT_CONTEXT, t, M3+CLIENT_BODY, t+M3+CLIENT_BODY, workspace_)) return Event::Rejected;
        uint8_t secret[32] = {}, tag[16]; std::memcpy(tag, data+CLIENT_SIGNED, 16);
        bool ok = pqc_mlkem_dec(secret, t+M3+5, pending_.kem_secret) == 0 && derive(secret) && confirmation(true, true, tag);
        erase(secret, sizeof(secret));
        if (!ok) return Event::Rejected;
        header(out.data, 4); std::memcpy(out.data+5, t+M2+37, 16);
        if (!confirmation(false, false, out.data+21)) { clear_pending(); return Event::Rejected; }
        uint8_t digest[32];
        if (!sha256(data, size, digest)) { clear_pending(); return Event::Rejected; }
        out.size = FINISH_SIZE; commit(now);
        std::memcpy(active_.client_finish_hash, digest, 32);
        std::memcpy(active_.server_finish, out.data+21, 16); erase(digest, sizeof(digest));
        return Event::Established;
    }
    if (role_ == Role::Client && data[4] == 4 && size == FINISH_SIZE && pending_.stage == 3) {
        if (!equal(data+5, t+M2+37, 16)) return Event::Rejected;
        uint8_t tag[16]; std::memcpy(tag, data+21, 16);
        if (!confirmation(true, false, tag)) return Event::Rejected;
        commit(now); return Event::Established;
    }
    if (data[4] != 5 || size != DATA_SIZE || !established_ || !equal(data+5, active_.sid, 16)) return Event::Rejected;
    const uint64_t counter = get64(data+21);
    const size_t n = data[29] | (size_t(data[30]) << 8);
    if (!counter || counter <= active_.received || !n || n > MAX_MESSAGE) return Event::Rejected;
    for (size_t i = n; i < MAX_MESSAGE; ++i) if (data[DATA_HEADER+i]) return Event::Rejected;
    uint8_t nonce[12] = {}, aad[DATA_HEADER+32], tag[16];
    put64(nonce+4, counter); std::memcpy(aad, data, DATA_HEADER);
    std::memcpy(aad+DATA_HEADER, active_.hash, 32); std::memcpy(tag, data+DATA_HEADER+MAX_MESSAGE, 16);
    if (!aead(true, role_ == Role::Server ? active_.c2s : active_.s2c, nonce, aad, sizeof(aad),
              data+DATA_HEADER, n, plain, tag)) return Event::Rejected;
    active_.received = counter; length = n;
    return Event::Plaintext;
}
bool Channel::encrypt(const uint8_t* plain, size_t length, uint64_t now, Packet& out) {
    out.size = 0; tick(now);
    if (!established_ || !plain || !length || length > MAX_MESSAGE || active_.sent == std::numeric_limits<uint64_t>::max()) return false;
    std::memset(out.data, 0, DATA_SIZE); header(out.data, 5);
    std::memcpy(out.data+5, active_.sid, 16); put64(out.data+21, ++active_.sent);
    out.data[29] = length & 255; out.data[30] = length >> 8;
    uint8_t nonce[12] = {}, aad[DATA_HEADER+32]; put64(nonce+4, active_.sent);
    std::memcpy(aad, out.data, DATA_HEADER); std::memcpy(aad+DATA_HEADER, active_.hash, 32);
    if (!aead(false, role_ == Role::Client ? active_.c2s : active_.s2c, nonce, aad, sizeof(aad),
              plain, length, out.data+DATA_HEADER, out.data+DATA_HEADER+MAX_MESSAGE)) return false;
    out.size = DATA_SIZE; return true;
}
} }
