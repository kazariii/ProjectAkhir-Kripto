#pragma once
// Arduino's SDK exports these headers but omits these four implementation units.
// Include this header to make PlatformIO link the matching supplementary library.
#include <mbedtls/chachapoly.h>
#include <mbedtls/hkdf.h>
#include <mbedtls/version.h>
#if MBEDTLS_VERSION_NUMBER != 0x021C0700
#error Review supplementary Mbed TLS sources when changing the Arduino SDK
#endif
#if !defined(MBEDTLS_CHACHA20_C) || !defined(MBEDTLS_POLY1305_C) || !defined(MBEDTLS_CHACHAPOLY_C) || !defined(MBEDTLS_HKDF_C)
#error Enable all four CONFIG_MBEDTLS crypto components in the proof build
#endif
