#pragma once
#include <stddef.h>
#include <stdint.h>

namespace pqc {
constexpr size_t KEM_PK = 800, KEM_SK = 1632, KEM_CT = 768;
constexpr size_t SIGN_SK = 1345, SIGN_PK = 897, SIGNATURE = 666;
constexpr size_t MAX_MESSAGE = 160, SIGN_WORKSPACE = 30239;
constexpr unsigned DEGREE = 9;
void erase(void*, size_t);
bool random_bytes(void*, size_t);
bool sha256(const void*, size_t, uint8_t hash[32]);
bool hkdf(const uint8_t secret[32], const uint8_t salt[32],
          const uint8_t* info, size_t info_length, uint8_t key[32]);
bool aead(bool decrypt, const uint8_t key[32], const uint8_t nonce[12],
          const uint8_t* aad, size_t aad_length, const uint8_t* input,
          size_t length, uint8_t* output, uint8_t tag[16]);
// Workspace belongs to the caller; never shared by concurrent channels.
bool sign(const uint8_t secret[SIGN_SK], const char* context,
          const void* message, size_t length, uint8_t signature[SIGNATURE], void* workspace);
bool verify(const uint8_t public_key[SIGN_PK], const char* context,
            const void* message, size_t length, const uint8_t signature[SIGNATURE], void* workspace);
}
