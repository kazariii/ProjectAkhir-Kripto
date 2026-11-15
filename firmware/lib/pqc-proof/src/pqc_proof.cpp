#include "pqc_proof.h"
#include "mlkem_native.h"
extern "C" {
#include "fndsa.h"
}
#include <cstring>
#ifdef ARDUINO
#include <esp_timer.h>
#else
#include <chrono>
#endif

namespace pqc {
namespace {
// Single-worker proof only. Explicit workspace avoids the small Arduino stack.
alignas(8) uint8_t sign_workspace[30239];
constexpr char SERVER_CONTEXT[] = "lab-kimia/proof-v1/server";
constexpr char DEVICE_CONTEXT[] = "lab-kimia/proof-v1/device";
uint64_t now_us() {
#ifdef ARDUINO
    return esp_timer_get_time();
#else
    return std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
#endif
}
void transcript(const Challenge& c, const Response& r, uint8_t* out) {
    std::memcpy(out, &c, CHALLENGE_BODY);
    std::memcpy(out + CHALLENGE_BODY, r.kem_ciphertext, KEM_CT);
}
bool derive(const uint8_t secret[32], const uint8_t salt[32],
            const uint8_t* binding, size_t length, uint8_t key[32]) {
    uint8_t hash[32];
    bool ok = sha256(binding, length, hash) && hkdf(secret, salt, hash, sizeof(hash), key);
    erase(hash, sizeof(hash));
    return ok;
}
}
bool verify_challenge(const Challenge& c, const uint8_t public_key[SIGN_PK]) {
    return fndsa_verify_temp(c.signature, SIGNATURE, public_key, SIGN_PK,
        SERVER_CONTEXT, sizeof(SERVER_CONTEXT)-1, FNDSA_HASH_ID_RAW,
        &c, CHALLENGE_BODY, sign_workspace, sizeof(sign_workspace)) == 1;
}
bool respond(const Challenge& c, const uint8_t public_key[SIGN_PK],
             const uint8_t secret_key[SIGN_SK], const uint8_t* message,
             size_t length, Response& r, Metrics& metrics) {
    if (!message || !length || length > MAX_MESSAGE) return false;
    r = {};
    uint64_t start = now_us();
    if (!verify_challenge(c, public_key)) return false;
    metrics.server_verify_us = now_us() - start;
    uint8_t coins[32], secret[32] = {}, seed[40], key[32] = {};
    uint8_t binding[CHALLENGE_BODY + KEM_CT];
    bool ok = random_bytes(coins, sizeof(coins)) && random_bytes(seed, sizeof(seed));
    start = now_us();
    if (ok) ok = pqc_mlkem_enc_derand(r.kem_ciphertext, secret, c.kem_public, coins) == 0;
    metrics.encapsulate_us = now_us() - start;
    transcript(c, r, binding);
    start = now_us();
    if (ok) ok = fndsa_sign_seeded_temp(secret_key, SIGN_SK,
        DEVICE_CONTEXT, sizeof(DEVICE_CONTEXT)-1, FNDSA_HASH_ID_RAW,
        binding, sizeof(binding), seed, sizeof(seed), r.signature, SIGNATURE,
        sign_workspace, sizeof(sign_workspace)) == SIGNATURE;
    metrics.sign_us = now_us() - start;
    erase(sign_workspace, sizeof(sign_workspace));
    start = now_us();
    if (ok) ok = derive(secret, c.salt, binding, sizeof(binding), key);
    r.length[0] = length & 255;
    r.length[1] = length >> 8;
    // Exactly one message under this freshly encapsulated key. Counter/nonce = 0.
    // This is NOT a reusable multi-message session or an anti-replay protocol.
    if (ok) ok = aead(false, key, r.nonce, binding, sizeof(binding), message, length,
                      r.ciphertext, r.tag);
    metrics.encrypt_us = now_us() - start;
    erase(coins, sizeof(coins)); erase(seed, sizeof(seed));
    erase(secret, sizeof(secret)); erase(key, sizeof(key));
    if (!ok) r = {};
    return ok;
}
bool open(const Challenge& c, const uint8_t public_key[SIGN_PK],
          const uint8_t secret_key[KEM_SK], const Response& r,
          uint8_t message[MAX_MESSAGE], size_t& length) {
    length = 0;
    erase(message, MAX_MESSAGE);
    const size_t n = r.length[0] | (size_t(r.length[1]) << 8);
    if (!n || n > MAX_MESSAGE || !verify_challenge(c, public_key)) return false;
    for (size_t i = n; i < MAX_MESSAGE; ++i) if (r.ciphertext[i] != 0) return false;
    uint8_t binding[CHALLENGE_BODY + KEM_CT];
    transcript(c, r, binding);
    if (fndsa_verify_temp(r.signature, SIGNATURE, c.device_public, SIGN_PK,
        DEVICE_CONTEXT, sizeof(DEVICE_CONTEXT)-1, FNDSA_HASH_ID_RAW,
        binding, sizeof(binding), sign_workspace, sizeof(sign_workspace)) != 1) return false;
    uint8_t secret[32] = {}, key[32] = {}, tag[16];
    std::memcpy(tag, r.tag, sizeof(tag));
    bool ok = pqc_mlkem_dec(secret, r.kem_ciphertext, secret_key) == 0 &&
              derive(secret, c.salt, binding, sizeof(binding), key) &&
              aead(true, key, r.nonce, binding, sizeof(binding), r.ciphertext, n, message, tag);
    erase(secret, sizeof(secret)); erase(key, sizeof(key));
    if (ok) length = n;
    return ok;
}
bool aead_self_test() {
    // RFC 8439 section 2.8.2. Both OpenSSL and ESP32 mbedTLS must match this tag.
    uint8_t key[32]; for (unsigned i=0; i<32; ++i) key[i] = 0x80 + i;
    const uint8_t nonce[] = {7,0,0,0,0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x47};
    const uint8_t aad[] = {0x50,0x51,0x52,0x53,0xc0,0xc1,0xc2,0xc3,0xc4,0xc5,0xc6,0xc7};
    const char text[] = "Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it.";
    const uint8_t expected[] = {0x1a,0xe1,0x0b,0x59,0x4f,0x09,0xe2,0x6a,0x7e,0x90,0x2e,0xcb,0xd0,0x60,0x06,0x91};
    uint8_t ciphertext[sizeof(text)] = {}, tag[16], plain[sizeof(text)] = {};
    return aead(false, key, nonce, aad, sizeof(aad), reinterpret_cast<const uint8_t*>(text),
                sizeof(text)-1, ciphertext, tag) && std::memcmp(tag, expected, 16) == 0 &&
           aead(true, key, nonce, aad, sizeof(aad), ciphertext, sizeof(text)-1, plain, tag) &&
           std::memcmp(plain, text, sizeof(text)-1) == 0;
}
}
