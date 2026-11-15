#include "pqc_crypto.h"
#include <cstring>
extern "C" {
#include "fndsa.h"
}
#ifdef ARDUINO
#include <esp_system.h>
#include "mbedtls_extra.h"
#include <mbedtls/sha256.h>
#else
#include <openssl/evp.h>
#include <openssl/kdf.h>
#include <openssl/rand.h>
#endif
namespace pqc {
void erase(void* ptr, size_t n) {
    volatile uint8_t* p = static_cast<volatile uint8_t*>(ptr);
    while (n--) *p++ = 0;
}
bool aead(bool decrypt, const uint8_t key[32], const uint8_t nonce[12],
          const uint8_t* aad, size_t aad_length, const uint8_t* input,
          size_t length, uint8_t* output, uint8_t tag[16]) {
    bool ok;
#ifdef ARDUINO
    mbedtls_chachapoly_context ctx;
    mbedtls_chachapoly_init(&ctx);
    ok = mbedtls_chachapoly_setkey(&ctx, key) == 0;
    if (ok) ok = (decrypt ?
        mbedtls_chachapoly_auth_decrypt(&ctx, length, nonce, aad, aad_length, tag, input, output) :
        mbedtls_chachapoly_encrypt_and_tag(&ctx, length, nonce, aad, aad_length, input, output, tag)) == 0;
    mbedtls_chachapoly_free(&ctx);
#else
    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    int written = 0, tail = 0;
    ok = ctx && EVP_CipherInit_ex(ctx, EVP_chacha20_poly1305(), nullptr, key, nonce, !decrypt) == 1 &&
         EVP_CipherUpdate(ctx, nullptr, &written, aad, static_cast<int>(aad_length)) == 1 &&
         EVP_CipherUpdate(ctx, output, &written, input, static_cast<int>(length)) == 1;
    if (ok && decrypt) ok = EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_TAG, 16, tag) == 1;
    if (ok) ok = EVP_CipherFinal_ex(ctx, output + written, &tail) == 1;
    if (ok && !decrypt) ok = EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_GET_TAG, 16, tag) == 1;
    EVP_CIPHER_CTX_free(ctx);
#endif
    if (!ok) erase(output, length);
    return ok;
}
bool random_bytes(void* out, size_t length) {
#ifdef ARDUINO
    // Caller enables the Wi-Fi radio first. Simulator entropy is not hardware assurance.
    esp_fill_random(out, length);
    return true;
#else
    return RAND_bytes(static_cast<unsigned char*>(out), static_cast<int>(length)) == 1;
#endif
}
bool sha256(const void* data, size_t length, uint8_t hash[32]) {
#ifdef ARDUINO
    return mbedtls_sha256_ret(static_cast<const uint8_t*>(data), length, hash, 0) == 0;
#else
    unsigned int n = 0;
    return EVP_Digest(data, length, hash, &n, EVP_sha256(), nullptr) == 1 && n == 32;
#endif
}
bool hkdf(const uint8_t secret[32], const uint8_t salt[32],
          const uint8_t* info, size_t length, uint8_t key[32]) {
#ifdef ARDUINO
    return mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), salt, 32,
                       secret, 32, info, length, key, 32) == 0;
#else
    EVP_PKEY_CTX* ctx = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, nullptr);
    size_t n = 32;
    bool ok = ctx && EVP_PKEY_derive_init(ctx) > 0 &&
        EVP_PKEY_CTX_set_hkdf_md(ctx, EVP_sha256()) > 0 &&
        EVP_PKEY_CTX_set1_hkdf_salt(ctx, salt, 32) > 0 &&
        EVP_PKEY_CTX_set1_hkdf_key(ctx, secret, 32) > 0 &&
        EVP_PKEY_CTX_add1_hkdf_info(ctx, info, length) > 0 &&
        EVP_PKEY_derive(ctx, key, &n) > 0 && n == 32;
    EVP_PKEY_CTX_free(ctx);
    if (!ok) erase(key, 32);
    return ok;
#endif
}
bool sign(const uint8_t secret[SIGN_SK], const char* context, const void* message,
          size_t length, uint8_t signature[SIGNATURE], void* workspace) {
    uint8_t seed[40];
    bool ok = random_bytes(seed, sizeof(seed)) &&
        fndsa_sign_seeded_temp(secret, SIGN_SK, context, std::strlen(context), FNDSA_HASH_ID_RAW,
          message, length, seed, sizeof(seed), signature, SIGNATURE,
          workspace, SIGN_WORKSPACE) == SIGNATURE;
    erase(seed, sizeof(seed)); erase(workspace, SIGN_WORKSPACE);
    if (!ok) erase(signature, SIGNATURE);
    return ok;
}
bool verify(const uint8_t public_key[SIGN_PK], const char* context, const void* message,
            size_t length, const uint8_t signature[SIGNATURE], void* workspace) {
    return fndsa_verify_temp(signature, SIGNATURE, public_key, SIGN_PK, context,
        std::strlen(context), FNDSA_HASH_ID_RAW, message, length, workspace, SIGN_WORKSPACE) == 1;
}
}
