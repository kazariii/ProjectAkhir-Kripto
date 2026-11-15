#pragma once
#include <stddef.h>
#include <stdint.h>
#include "pqc_crypto.h"

// Fixed-width, byte-only proof format; not the future MQTT wire protocol.
namespace pqc {
struct Challenge {
    uint8_t kem_public[KEM_PK];
    uint8_t device_public[SIGN_PK];
    uint8_t salt[32];
    uint8_t signature[SIGNATURE];
};
constexpr size_t CHALLENGE_BODY = KEM_PK + SIGN_PK + 32;
struct Response {
    uint8_t kem_ciphertext[KEM_CT];
    uint8_t signature[SIGNATURE];
    uint8_t nonce[12];
    uint8_t length[2]; // unsigned little-endian
    uint8_t ciphertext[MAX_MESSAGE];
    uint8_t tag[16];
};
struct Metrics {
    uint64_t server_verify_us = 0, encapsulate_us = 0;
    uint64_t sign_us = 0, encrypt_us = 0;
};
static_assert(sizeof(Challenge) == 2395, "challenge must have no padding");
static_assert(sizeof(Response) == 1624, "response must have no padding");
bool random_bytes(void* out, size_t length);
bool verify_challenge(const Challenge&, const uint8_t server_public[SIGN_PK]);
bool respond(const Challenge&, const uint8_t server_public[SIGN_PK],
             const uint8_t device_secret[SIGN_SK], const uint8_t* message,
             size_t length, Response&, Metrics&);
bool open(const Challenge&, const uint8_t server_public[SIGN_PK],
          const uint8_t kem_secret[KEM_SK], const Response&,
          uint8_t message[MAX_MESSAGE], size_t& length);
bool aead_self_test();
}
